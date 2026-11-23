"""Offline contracts exercise the production graph and transactions using scripted model responses."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from clinic_inbox import db, graph
from clinic_inbox.__main__ import config, process
from clinic_inbox.screen import URGENT_REPLY
from clinic_inbox.tools import make_tools
from reset_db import reset

ROOT = Path(__file__).resolve().parents[1]


class Script:
    def __init__(self, *turns, loop=False):
        self.turns = iter(turns)
        self.loop = loop
        self.count = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.count += 1
        if self.loop:
            calls = (
                [("route_to_staff", {"queue": "front_desk"})]
                if self.count == 1
                else [("get_patient_summary", {})]
            )
        else:
            calls = next(self.turns)
        return AIMessage(
            content="",
            tool_calls=[
                {"id": f"call-{self.count}-{n}", "name": name, "args": args}
                for n, (name, args) in enumerate(calls)
            ],
        )


@pytest.fixture
def clinic(tmp_path):
    path = tmp_path / "clinic.db"
    reset(path)
    con = db.connect(path)
    with SqliteSaver.from_conn_string(str(path)) as saver:
        yield path, con, saver
    con.close()


def start(clinic, model, mid="M001"):
    _, con, saver = clinic
    agent = graph.build(con, saver, "fake", model)
    msg = con.execute("SELECT * FROM messages WHERE message_id=?", (mid,)).fetchone()
    return agent, process(con, agent, msg, "fake")


def decision(con, mid, approve):
    return {
        "reviewer": "demo-reviewer",
        "choices": {
            str(r["proposal_id"]): "approved" if r["kind"] in approve else "rejected"
            for r in con.execute("SELECT * FROM proposals WHERE message_id=?", (mid,))
        },
    }


def test_scoped_tools(clinic):
    _, con, _ = clinic
    tools = {t.name: t for t in make_tools(con, "P05", "2026-11-06")}
    assert all("patient_id" not in t.args for t in tools.values())
    assert tools["get_patient_summary"].invoke({})["doctor"].startswith("Dr ")
    assert {r["status"] for r in tools["get_lab_status"].invoke({})} == {"pending"}
    assert all("value" not in r for r in tools["get_lab_status"].invoke({}))
    meds = {t.name: t for t in make_tools(con, "P04", "2026-11-06")}[
        "get_active_medications"
    ].invoke({})
    assert meds and "Amlodipine" in meds[0]
    with pytest.raises(ValueError):
        tools["draft_reply"].invoke({"topic": "nurse", "test_id": "O01"})
    with pytest.raises(db.CalendarConflict):
        tools["propose_appointment_change"].invoke({"action": "cancel", "appointment_id": "A05"})
    free = tools["search_slots"].invoke(
        {
            "date_from": "2026-11-09",
            "date_to": "2026-11-10",
            "doctor_id": "PR1",
            "time_of_day": "afternoon",
        }
    )
    assert free and all(r["practitioner_id"] == "PR1" and r["start"][11:13] >= "12" for r in free)
    busy = con.execute("SELECT slot_id FROM slots WHERE status='busy' LIMIT 1").fetchone()[0]
    with pytest.raises(db.CalendarConflict):
        tools["propose_appointment_change"].invoke({"action": "book", "slot_id": busy})


@pytest.mark.parametrize("action", ["book", "reschedule", "cancel"])
def test_approved_calendar_and_audit(clinic, action):
    _, con, _ = clinic
    slot = con.execute(
        "SELECT slot_id FROM slots WHERE status='free' ORDER BY start LIMIT 1"
    ).fetchone()[0]
    old = con.execute("SELECT slot_id FROM appointments WHERE appointment_id='A05'").fetchone()[0]
    payload = {"action": action}
    if action != "book":
        payload["appointment_id"] = "A05"
    if action != "cancel":
        payload["slot_id"] = slot
    agent, row = start(
        clinic,
        Script(
            [("route_to_staff", {"queue": "front_desk"})], [("propose_appointment_change", payload)]
        ),
    )
    assert row["error"] is None
    assert agent.get_state(config("M001")).next == ("review",)
    assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
    assert con.execute("SELECT status FROM slots WHERE slot_id=?", (slot,)).fetchone()[0] == "free"
    assert con.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    choice = decision(con, "M001", {"appointment", "route"})
    agent.invoke(Command(resume=choice), config("M001"))
    db.execute(con, "M001", choice)  # commit replay is idempotent
    assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 3
    assert con.execute("SELECT COUNT(*) FROM staff_queue").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    if action != "cancel":
        assert (
            con.execute(
                "SELECT patient_id FROM appointments WHERE status='booked' AND slot_id=?", (slot,)
            ).fetchone()[0]
            == "P07"
        )
    if action != "book":
        assert (
            con.execute("SELECT status FROM slots WHERE slot_id=?", (old,)).fetchone()[0] == "free"
        )
    if action == "cancel":
        assert (
            con.execute("SELECT status FROM appointments WHERE appointment_id='A05'").fetchone()[0]
            == "cancelled"
        )
        assert (
            con.execute(
                "SELECT flags_shown FROM audit_log JOIN proposals USING(proposal_id) WHERE kind='appointment'"
            ).fetchone()[0]
            == '["cancellation"]'
        )


def test_slot_taken_after_proposal(clinic):
    _, con, _ = clinic
    slot = con.execute("SELECT slot_id FROM slots WHERE status='free' LIMIT 1").fetchone()[0]
    agent, _ = start(
        clinic,
        Script(
            [("route_to_staff", {"queue": "front_desk"})],
            [
                (
                    "propose_appointment_change",
                    {"action": "reschedule", "appointment_id": "A05", "slot_id": slot},
                )
            ],
        ),
    )
    with con:
        con.execute("UPDATE slots SET status='busy' WHERE slot_id=?", (slot,))
    agent.invoke(Command(resume=decision(con, "M001", {"appointment"})), config("M001"))
    assert (
        json.loads(
            con.execute(
                "SELECT result FROM audit_log JOIN proposals USING(proposal_id) WHERE kind='appointment'"
            ).fetchone()[0]
        )["status"]
        == "failed"
    )
    assert (
        con.execute("SELECT slot_id FROM appointments WHERE appointment_id='A05'").fetchone()[0]
        != slot
    )


def test_urgent_review_in_new_process(clinic):
    path, con, _ = clinic
    model = Script()
    agent, row = start(clinic, model, "M026")
    assert model.count == row["tool_calls"] == 0
    assert row["proposals"][1]["text"] == URGENT_REPLY
    assert list(agent.get_state_history(config("M026")))
    assert con.execute("SELECT count(*) FROM staff_queue").fetchone()[0] == 0
    call = subprocess.run(
        [
            sys.executable,
            "-m",
            "clinic_inbox",
            "review",
            "--db",
            str(path),
            "--reviewer",
            "staff-01",
        ],
        input="a\na\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=True,
        env={**os.environ, "AGENT_MODEL": ""},
    )
    assert "from_safety_screen" in call.stdout
    assert con.execute("SELECT text FROM outbox").fetchone()[0] == URGENT_REPLY
    audit = con.execute("SELECT reviewer,flags_shown FROM audit_log").fetchall()
    assert len(audit) == 2 and all(
        tuple(r) == ("staff-01", '["from_safety_screen"]') for r in audit
    )


@pytest.mark.parametrize(
    "model,error",
    [
        (Script(loop=True), "GraphRecursionError"),
        (Script([("approve_everything", {})]), "InvalidPlan"),
        (Script([("get_lab_status", {"patient_id": "P10"})]), "InvalidPlan"),
        (
            Script([("draft_reply", {"text": "Your prescription has been approved."})]),
            "InvalidPlan",
        ),
        (Script([]), "InvalidPlan"),
        (Script(), "RuntimeError"),
    ],
)
def test_fail_closed(clinic, model, error):
    _, con, _ = clinic
    _, row = start(clinic, model)
    assert row["error"] == error and row["proposals"] == []
    assert tuple(
        con.execute("SELECT status,error FROM messages WHERE message_id='M001'").fetchone()
    ) == ("error", error)
    assert con.execute("SELECT count(*) FROM proposals").fetchone()[0] == 0


def test_flags(clinic):
    assert graph.flags(
        {"kind": "reply", "text": "Rohan Kapoor's result is normal and has been sent."},
        "P08",
        False,
    ) == ["claims_completion", "possible_result_interpretation", "mentions_other_patient"]


def test_reject_all_preserves_calendar(clinic):
    _, con, _ = clinic
    before = con.execute("SELECT * FROM appointments").fetchall()
    agent, _ = start(
        clinic,
        Script(
            [("route_to_staff", {"queue": "front_desk"})],
            [("propose_appointment_change", {"action": "cancel", "appointment_id": "A05"})],
        ),
    )
    agent.invoke(Command(resume=decision(con, "M001", set())), config("M001"))
    assert con.execute("SELECT * FROM appointments").fetchall() == before
    assert con.execute("SELECT COUNT(*) FROM staff_queue").fetchone()[0] == 0
    assert (
        con.execute("SELECT COUNT(*) FROM audit_log WHERE decision='rejected'").fetchone()[0] == 3
    )

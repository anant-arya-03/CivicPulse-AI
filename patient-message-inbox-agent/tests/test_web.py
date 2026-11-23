"""Exercise the staff web controller against real graph checkpoints, offline."""

from contextlib import closing
import sqlite3

import pytest

from clinic_inbox.db import connect
from clinic_inbox.web import RequestError, change, snapshot
from reset_db import reset


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "inbox.db"
    reset(path)
    return path


def test_review_api_requires_complete_choices_and_prevents_replay(db):
    change(db, "", "M026", "prepare", {})
    with closing(connect(db)) as con:
        first = snapshot(con)[0]
    assert first["urgent"] and first["message_id"] == "M026"
    assert len(first["proposals"]) == 2
    expected = {
        str(p["id"]): "approved" if p["kind"] == "route" else "rejected"
        for p in first["proposals"]
    }
    for invalid in (
        {"reviewer": " ", "choices": expected},
        {"reviewer": "Staff", "choices": {}},
        {"reviewer": "Staff", "choices": {**expected, "77": "approved"}},
    ):
        with pytest.raises(RequestError) as error:
            change(db, "", "M026", "review", invalid)
        assert error.value.status == 400
    decision = {"reviewer": "Demo staff", "choices": expected}
    change(db, "", "M026", "review", decision)
    with pytest.raises(RequestError) as stale:
        change(db, "", "M026", "review", decision)
    assert stale.value.status == 409
    with closing(connect(db)) as con:
        m = next(row for row in snapshot(con) if row["message_id"] == "M026")
        assert m["status"] == "done"
        assert {p["status"] for p in m["proposals"]} == {"applied", "rejected"}
        assert all(p["reviewer"] == "Demo staff" for p in m["proposals"])
        assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0


def test_unknown_message_and_busy_database(db):
    with pytest.raises(RequestError) as missing:
        change(db, "", "unknown", "prepare", {})
    assert missing.value.status == 404
    with closing(sqlite3.connect(str(db) + ".lock")) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(RequestError) as busy:
            change(db, "", "M026", "prepare", {})
        assert busy.value.status == 409


def test_transient_retry_and_manual_error(db):
    with closing(connect(db)) as con, con:
        con.execute(
            "UPDATE messages SET status='error',error='ConnectError' WHERE message_id='M026'"
        )
        con.execute(
            "UPDATE messages SET status='error',error='InvalidPlan' WHERE message_id='M001'"
        )
    change(db, "", "M026", "prepare", {})
    with pytest.raises(RequestError) as error:
        change(db, "", "M001", "prepare", {})
    assert error.value.status == 409
    with closing(connect(db)) as con:
        assert tuple(
            con.execute(
                "SELECT status,error FROM messages WHERE message_id='M026'"
            ).fetchone()
        ) == ("awaiting_review", None)

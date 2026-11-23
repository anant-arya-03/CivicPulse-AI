import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .db import connect
from .graph import PROMPT_VERSION, build


def config(mid):
    return {"configurable": {"thread_id": mid}, "recursion_limit": 24}


def process(con, graph, msg, model_name):
    mid = msg["message_id"]
    cfg = config(mid)
    result = {
        "message_id": mid,
        "model": model_name or "unconfigured",
        "prompt_version": PROMPT_VERSION,
        "error": None,
        "tool_calls": 0,
        "proposals": [],
    }
    try:
        initial = {
            "message_id": mid,
            "patient_id": msg["patient_id"],
            "today": msg["sent"][:10],
            "messages": [HumanMessage(content=msg["text"])],
            "tool_calls": 0,
            "proposals": [],
        }
        # A killed process can leave a checkpoint while the inbox row is still new.
        previous = graph.get_state(cfg)
        state = graph.invoke(None if previous.next else initial, cfg)
        if not state.get("__interrupt__"):
            raise RuntimeError("Missing review pause")
        result.update(proposals=state["proposals"], tool_calls=state["tool_calls"])
    except Exception as exc:  # noqa: BLE001 - isolate provider and graph failures per message
        result["error"] = type(exc).__name__
        with con:
            con.execute(
                "UPDATE messages SET status='error',error=? WHERE message_id=?",
                (result["error"], mid),
            )
        state = graph.get_state(cfg)
        result["tool_calls"] = sum(
            len(getattr(m, "tool_calls", [])) for m in state.values.get("messages", [])
        )
    return result


def review(con, graph, reviewer):
    for r in con.execute(
        "SELECT message_id,error FROM messages WHERE status='error' ORDER BY sent"
    ):
        print(f"Manual follow-up required: {r['message_id']} ({r['error']})")
    messages = con.execute(
        "SELECT * FROM messages WHERE status='awaiting_review' "
        "ORDER BY EXISTS(SELECT 1 FROM proposals p WHERE p.message_id=messages.message_id "
        "AND json_extract(p.payload,'$.priority')='urgent') DESC, sent"
    ).fetchall()
    for msg in messages:
        mid = msg["message_id"]
        print(f"\n{mid} · {msg['patient_id']} · {msg['sent']}\n{msg['text']}")
        cfg = config(mid)
        saved = graph.get_state(cfg)
        if not saved.interrupts:
            # Recover a crash between the record transaction and review checkpoint,
            # or finish a previously checkpointed human decision.
            if saved.next not in {("record",), ("review",), ("execute",)}:
                print("Missing review checkpoint. Manual follow-up required.")
                continue
            graph.invoke(None, cfg)
            if not graph.get_state(cfg).interrupts:
                continue
        choices = {}
        proposals = con.execute(
            "SELECT * FROM proposals WHERE message_id=? ORDER BY proposal_id", (mid,)
        ).fetchall()
        for r in proposals:
            print(f"  #{r['proposal_id']} {r['payload']}  flags={r['flags']}")
        for r in proposals:
            while True:
                try:
                    answer = (
                        input(f"  #{r['proposal_id']} [a]pprove / [r]eject / [q]uit > ")
                        .strip()
                        .lower()
                    )
                except EOFError:
                    return
                if answer in {"q", "quit"}:
                    return
                if answer in {"a", "approve", "r", "reject"}:
                    break
            choices[str(r["proposal_id"])] = "approved" if answer.startswith("a") else "rejected"
        decision = {"reviewer": reviewer, "choices": choices}
        graph.invoke(Command(resume=decision), config(mid))
        for row in con.execute(
            "SELECT proposal_id,result FROM audit_log JOIN proposals USING(proposal_id) "
            "WHERE message_id=? ORDER BY proposal_id",
            (mid,),
        ):
            print(f"  #{row['proposal_id']} {row['result']}")
    print("Review queue complete.")


def main():
    load_dotenv(Path.cwd() / ".env")
    parser = argparse.ArgumentParser(description="Synthetic patient message review")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--ids", help="Comma-separated message IDs")
    rev = sub.add_parser("review")
    rev.add_argument("--reviewer", required=True)
    for p in (run, rev):
        p.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("Create the clinic database using reset_db.py first")
    if args.command == "run" and args.out.resolve() == args.db.resolve():
        parser.error("Choose a results file separate from the clinic database")
    if args.command == "review" and not args.reviewer.strip():
        parser.error("A reviewer name is required")
    model_name = os.getenv("AGENT_MODEL", "")
    # A separate SQLite writer lock serializes CLI sessions without locking the checkpoint database.
    with (
        closing(sqlite3.connect(str(args.db) + ".lock", timeout=1)) as lock,
        closing(connect(args.db)) as con,
        SqliteSaver.from_conn_string(str(args.db)) as saver,
    ):
        try:
            lock.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            parser.exit(
                2, "Another run or review is using this database. Retry when it finishes.\n"
            )
        graph = build(con, saver, model_name)
        if args.command == "review":
            review(con, graph, args.reviewer.strip())
            return
        ids = {s.strip() for s in args.ids.split(",")} if args.ids else None
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as out:
            for msg in con.execute(
                "SELECT * FROM messages WHERE status='new' ORDER BY sent,message_id"
            ).fetchall():
                if ids is None or msg["message_id"] in ids:
                    row = process(con, graph, msg, model_name)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    print(row["message_id"], row["error"] or "awaiting review", flush=True)


if __name__ == "__main__":
    main()

"""Local staff inbox. Run with python -m clinic_inbox.web."""

import argparse
import json
import logging
import os
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from reset_db import reset
from .__main__ import config, process
from .db import connect
from .graph import build
from .record import summary
from .screen import screen

STATIC = Path(__file__).with_name("static")
ASSETS = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}
TRANSIENT = {
    "ConnectError",
    "ConnectionError",
    "ReadTimeout",
    "ConnectTimeout",
    "TimeoutError",
    "APIConnectionError",
    "APITimeoutError",
    "RateLimitError",
    "ServiceUnavailable",
}


class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def snapshot(con):
    messages = {}
    for row in con.execute(
        "SELECT message_id,patient_id,text,sent,status,error FROM messages ORDER BY sent,message_id"
    ):
        m = dict(row)
        try:
            m["patient"] = summary(m["patient_id"])
        except KeyError:
            m["patient"] = {
                "name": m["patient_id"],
                "doctor": "Unknown",
                "language": "Unknown",
            }
        m.update(proposals=[], urgent=False, retryable=m["error"] in TRANSIENT)
        messages[m["message_id"]] = m
    for row in con.execute("""SELECT p.*, a.reviewer, a.at, a.result
                              FROM proposals p LEFT JOIN audit_log a USING(proposal_id)
                              ORDER BY p.proposal_id"""):
        m = messages[row["message_id"]]
        payload = json.loads(row["payload"])
        p = {
            "id": row["proposal_id"],
            "kind": row["kind"],
            "payload": payload,
            "flags": json.loads(row["flags"]),
            "status": row["status"],
            "reviewer": row["reviewer"],
            "at": row["at"],
            "outcome": json.loads(row["result"]) if row["result"] else None,
        }
        if payload.get("priority") == "urgent":
            m["urgent"] = True
        if p["kind"] == "appointment":
            for key in ("original_slot_id", "slot_id"):
                slot = con.execute(
                    "SELECT start, practitioner_id FROM slots WHERE slot_id=?",
                    (payload.get(key),),
                ).fetchone()
                if slot:
                    p[key] = dict(slot)
        m["proposals"].append(p)
    return sorted(
        messages.values(),
        key=lambda m: (
            m["status"] != "awaiting_review",
            not m["urgent"],
            m["sent"],
            m["message_id"],
        ),
    )


def change(path, model, mid, action, body):
    with (
        closing(sqlite3.connect(str(path) + ".lock", timeout=0.2)) as lock,
        closing(connect(path)) as con,
    ):
        try:
            lock.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise RequestError(
                409,
                "Another review or preparation is running. Wait a moment and refresh.",
            ) from exc
        m = con.execute("SELECT * FROM messages WHERE message_id=?", (mid,)).fetchone()
        if m is None:
            raise RequestError(
                404, "This message could not be found. Refresh the inbox."
            )
        with SqliteSaver.from_conn_string(str(path)) as saver:
            graph = build(con, saver, model)
            if action == "prepare":
                if m["status"] != "new" and not (
                    m["status"] == "error" and m["error"] in TRANSIENT
                ):
                    raise RequestError(
                        409,
                        "This message has already been processed. Refresh the inbox.",
                    )
                row = process(con, graph, m, model)
                if row["error"] is None:
                    with con:
                        con.execute(
                            "UPDATE messages SET error=NULL WHERE message_id=?", (mid,)
                        )
                return
            if m["status"] != "awaiting_review":
                raise RequestError(
                    409,
                    "The message is no longer awaiting review. Refresh to see its latest status.",
                )
            reviewer, choices = body.get("reviewer"), body.get("choices")
            if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80:
                raise RequestError(
                    400, "Enter a reviewer name between 1 and 80 characters."
                )
            expected = {
                str(r[0])
                for r in con.execute(
                    "SELECT proposal_id FROM proposals WHERE message_id=? AND status='pending'",
                    (mid,),
                )
            }
            if (
                not expected
                or not isinstance(choices, dict)
                or set(choices) != expected
                or any(v not in ("approved", "rejected") for v in choices.values())
            ):
                raise RequestError(
                    400, "Choose Approve or Reject for every proposal before saving."
                )
            cfg = config(mid)
            saved = graph.get_state(cfg)
            if not saved.interrupts:
                if saved.next in {("record",), ("review",), ("execute",)}:
                    graph.invoke(None, cfg)
                if not graph.get_state(cfg).interrupts:
                    raise RequestError(
                        409,
                        "The review checkpoint is unavailable or already completed. Refresh before continuing.",
                    )
            graph.invoke(
                Command(resume={"reviewer": reviewer.strip(), "choices": choices}), cfg
            )


class Handler(BaseHTTPRequestHandler):
    def send_payload(self, status, data, kind):
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(data)

    def json(self, status, data):
        self.send_payload(status, json.dumps(data).encode(), "application/json")

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            raise RequestError(403, "Open the app using its local address.")
        if self.command == "POST" and self.headers.get("Origin") not in {
            None,
            *("http://" + h for h in hosts),
        }:
            raise RequestError(403, "Submit this change from the local inbox.")

    def dispatch(self):
        self.local_request()
        path = urlsplit(self.path).path
        if self.command == "GET":
            if path in ASSETS:
                filename, mime = ASSETS[path]
                self.send_payload(200, (STATIC / filename).read_bytes(), mime)
                return
            if path == "/api/inbox":
                with closing(connect(self.server.db)) as con:
                    con.execute("BEGIN")
                    self.json(200, {"messages": snapshot(con)})
                return
        if self.command == "POST":
            parts = path.strip("/").split("/")
            if (
                len(parts) == 4
                and parts[:2] == ["api", "messages"]
                and parts[3] in {"review", "prepare"}
            ):
                if self.headers.get_content_type() != "application/json":
                    raise RequestError(415, "Send the review as JSON.")
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise RequestError(400, "Invalid request length.") from exc
                if not 0 < length <= 16384:
                    raise RequestError(400, "Invalid request size.")
                try:
                    body = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeError) as exc:
                    raise RequestError(400, "Invalid JSON request.") from exc
                if not isinstance(body, dict):
                    raise RequestError(400, "Invalid request format.")
                change(
                    self.server.db, self.server.model, unquote(parts[2]), parts[3], body
                )
                self.json(200, {"ok": True})
                return
        raise RequestError(404, "Page not found.")

    def handle_request(self):
        try:
            self.dispatch()
        except RequestError as exc:
            self.json(exc.status, {"error": str(exc)})
        except (ConnectionResetError, BrokenPipeError):
            return
        except Exception:
            logging.exception("Inbox request failed")
            self.json(
                500,
                {
                    "error": "The operation could not be confirmed. Refresh to check its status before retrying."
                },
            )

    do_GET = handle_request
    do_POST = handle_request


def main():
    parser = argparse.ArgumentParser(
        description="Local staff inbox for synthetic teaching records"
    )
    parser.add_argument("--db", type=Path, default=Path("staff-demo.db"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env")
    model = os.getenv("AGENT_MODEL") or "ollama:qwen2.5:7b"
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.db, server.model = args.db, model
        if not args.db.exists():
            # Reserve the new path exclusively so two launches cannot reset one another's data.
            args.db.parent.mkdir(parents=True, exist_ok=True)
            with args.db.open("xb"):
                pass
            reset(args.db)
            with closing(connect(args.db)) as con:
                first = next(
                    (
                        r
                        for r in con.execute("SELECT * FROM messages ORDER BY sent")
                        if screen(r["text"])
                    ),
                    None,
                )
            if first:
                change(args.db, model, first["message_id"], "prepare", {})
        print(
            f"Staff inbox running at http://127.0.0.1:{server.server_port}", flush=True
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

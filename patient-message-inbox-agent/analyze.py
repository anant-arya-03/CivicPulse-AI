"""Reproduce the report tables from JSONL, optionally inspect saved per-message checkpoints."""

import argparse
import json
from collections import Counter
from contextlib import closing
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from clinic_inbox.__main__ import config
from clinic_inbox.db import connect
from clinic_inbox.graph import build, flags
from clinic_inbox.record import BUNDLE
from clinic_inbox.screen import screen
from score import baseline_rows, load_bundle_facts, load_results, score_row, summarize


def analyze(out):
    report = {}
    facts = load_bundle_facts(BUNDLE)
    for name, source in (("dev", "data/messages_dev.json"), ("redteam", "redteam_messages.json")):
        messages = json.loads(Path(source).read_text())
        results, problems = load_results(out / (name + ".jsonl"))
        if problems or set(results) != {m["id"] for m in messages}:
            raise ValueError(f"Incomplete or malformed {name} results: {problems}")
        scored = [score_row(m, results[m["id"]], *facts) for m in messages]
        fp, fn, items, marks, actions = [], [], 0, Counter(), Counter()
        details = []
        for m, r in zip(messages, scored, strict=True):
            mid = m["id"]
            detected = screen(m["text"])
            if detected and not r["red_flag"]:
                fp.append(mid)
            if not detected and r["red_flag"]:
                fn.append(mid)
            proposals = results[mid]["proposals"]
            items += len(proposals)
            local_flags = [flag for p in proposals for flag in flags(p, m["patient_id"], detected)]
            marks.update(local_flags)
            actions.update(r["actions"])
            if (
                detected
                or r["queue"] != r["expected"]
                or r["flags"]
                or local_flags
                or name == "redteam"
            ):
                details.append(
                    {
                        "id": mid,
                        "screen": detected,
                        "expected": r["expected"],
                        "queue": r["queue"],
                        "error": r["error"],
                        "review_flags": local_flags,
                        "scorer_flags": r["flags"],
                        "actions": r["actions"],
                    }
                )
        report[name] = {
            "agent": summarize(scored),
            "baseline": summarize(baseline_rows(messages)),
            "screen": {
                "tp": sum(r["red_flag"] for r in scored) - len(fn),
                "misses": fn,
                "false_alarms": fp,
            },
            "proposals": items,
            "proposals_per_message": items / len(messages),
            "review_hours_at_300": items / len(messages) * 300 * 20 / 3600,
            "review_flags": dict(marks),
            "appointment_actions": dict(actions),
            "inspect": details,
        }
    subset = [m for m in json.loads(Path("data/messages_dev.json").read_text()) if m["subset"]]
    queues = {m["id"]: [] for m in subset}
    for i in range(1, 4):
        results, problems = load_results(out / f"subset{i}.jsonl")
        if problems or set(results) != set(queues):
            raise ValueError(f"Incomplete subset run {i}")
        for m in subset:
            queues[m["id"]].append(score_row(m, results[m["id"]], *facts)["queue"])
    report["repeatability"] = {
        "stable_queues": sum(q[0] is not None and len(set(q)) == 1 for q in queues.values()),
        "always_failed": [mid for mid, q in queues.items() if q == [None] * 3],
        "changed": {mid: q for mid, q in queues.items() if len(set(q)) > 1},
    }
    return report


def show_trace(db, mid):
    with closing(connect(db)) as con, SqliteSaver.from_conn_string(str(db)) as saver:
        graph = build(con, saver, "")
        state = graph.get_state(config(mid))
        for m in state.values.get("messages", []):
            print(m.type, getattr(m, "name", "") or "", getattr(m, "tool_calls", []) or m.content)
        print("next", state.next, "errors", [t.error for t in state.tasks if t.error])
        print("proposals", state.values.get("proposals", []))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--trace", nargs=2, metavar=("DB", "ID"))
    args = parser.parse_args()
    if args.trace:
        show_trace(*args.trace)
    else:
        print(json.dumps(analyze(args.results), indent=2))

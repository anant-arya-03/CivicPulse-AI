"""Reset before each measured run. Labels are read by the scorer, never the agent."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from reset_db import DEFAULT_MESSAGES, reset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--work", type=Path, help="Directory for fresh evaluation databases and traces"
    )
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    subset = ",".join(m["id"] for m in json.loads(DEFAULT_MESSAGES.read_text()) if m["subset"])
    with tempfile.TemporaryDirectory() as tmp:
        work = args.work or Path(tmp)
        for name, messages, ids in [
            ("dev", DEFAULT_MESSAGES, None),
            ("redteam", "redteam_messages.json", None),
            *((f"subset{i}", DEFAULT_MESSAGES, subset) for i in range(1, 4)),
        ]:
            db = work / (name + ".db")
            reset(db, messages_path=messages)
            result = args.out / (name + ".jsonl")
            cmd = [
                sys.executable,
                "-m",
                "clinic_inbox",
                "run",
                "--db",
                str(db),
                "--out",
                str(result),
            ]
            subprocess.run(cmd + (["--ids", ids] if ids else []), check=True)
            subprocess.run(
                [sys.executable, "score.py", str(result), "--messages", str(messages), "--show"]
                + (["--ids", ids] if ids else []),
                check=True,
            )
        subprocess.run(
            [
                sys.executable,
                "score.py",
                *[str(args.out / f"subset{i}.jsonl") for i in range(1, 4)],
                "--ids",
                subset,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()

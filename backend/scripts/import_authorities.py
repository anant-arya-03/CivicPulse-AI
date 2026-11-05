"""Import VERIFIED real government departments into the directory.

Usage (from backend/):
    python -m scripts.import_authorities path/to/authorities.json          # check only
    python -m scripts.import_authorities path/to/authorities.json --apply  # write to the database

The file is a JSON list of records like docs/authorities.example.json. Every record is checked
before anything is written: an https:// source page, a verification date within the last year,
a valid email that isn't a reserved demo domain, and known issue categories. Re-importing the
same department (same name and place) updates it.

Only add contacts you have checked yourself on an official government website. Adding a record
does NOT send anything: submissions stay simulated (see ALLOW_REAL_SUBMISSIONS).
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

import app.models  # noqa: F401  (registers every ORM model)
from app.core.database import SessionLocal
from app.modules.authorities import service
from app.modules.authorities.schemas import AuthorityImport


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true", help="write to the database")
    args = parser.parse_args()

    try:
        raw = json.loads(args.file.read_text(encoding="utf-8"))
        records = TypeAdapter(list[AuthorityImport]).validate_python(raw)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"Could not read {args.file}: {exc}")
    except ValidationError as exc:
        print(f"{exc.error_count()} problem(s) found; nothing was imported:\n")
        for error in exc.errors():
            location = " / ".join(str(part) for part in error["loc"])
            print(f"  record {location}: {error['msg']}")
        sys.exit(1)

    print(f"{len(records)} record(s) are valid.")
    if not args.apply:
        print("Check only. Run again with --apply to write them to the database.")
        return
    with SessionLocal() as db:
        count = service.import_authorities(db, records)
    print(f"Imported or updated {count} department(s).")


if __name__ == "__main__":
    main()

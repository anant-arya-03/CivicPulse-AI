"""Run the scheduled actions that are due, then exit.

Usage (from backend/):
    python -m app.workers.run_pending                              # check "now"
    python -m app.workers.run_pending --now 2026-12-01T10:00:00Z   # demo time travel

Run it every 15 minutes or so (Windows Task Scheduler, cron), or by hand during a demo. It is
safe to run several copies at once: each action is claimed with a row lock and runs only once.

It never sends anything. At most it drafts a reminder that the citizen must approve, or
records that escalation is recommended.
"""

import argparse
import sys
from datetime import UTC, datetime

import app.models  # noqa: F401  (registers every ORM model)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.ai_providers.factory import get_ai_provider
from app.integrations.email_providers.factory import get_email_provider
from app.modules.monitoring.service import run_due_actions


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Give a time zone, e.g. 2026-12-01T10:00:00Z")
    return parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run due follow-up checks once.")
    parser.add_argument(
        "--now",
        type=_parse_time,
        help="pretend it is this time (development/demo only; needs ENABLE_SIMULATION=true)",
    )
    parser.add_argument("--limit", type=int, default=100, help="maximum actions to run")
    args = parser.parse_args()

    if args.now is not None and not get_settings().enable_simulation:
        sys.exit("--now is only allowed with ENABLE_SIMULATION=true (never in production).")

    with SessionLocal() as db:
        ran = run_due_actions(
            db,
            ai=get_ai_provider(),
            email=get_email_provider(),
            now=args.now,
            limit=args.limit,
        )
        for action in ran:
            print(
                f"{action.execution_status:<9} {action.id}  {action.outcome or action.last_error}"
            )
        print(f"{len(ran)} action(s) run.")


if __name__ == "__main__":
    main()

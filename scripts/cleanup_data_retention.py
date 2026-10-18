"""CLI for bounded data retention cleanup."""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal
from services.maintenance.retention import run_bounded_staging_cleanup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Bounded data retention cleanup for PostgreSQL.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Retention period in days for PROMOTED staging records (default: 30).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Perform actual deletion. Without this flag, script runs in DRY-RUN mode.",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        logger.info("Running in DRY RUN mode. Pass --execute to delete.")
    else:
        logger.warning(f"EXECUTING real deletion of PROMOTED staging records older than {args.days} days.")

    db = SessionLocal()
    try:
        res = run_bounded_staging_cleanup(db, retention_days=args.days, dry_run=dry_run)
        logger.info(f"Summary: {res}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

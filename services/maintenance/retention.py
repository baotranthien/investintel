"""Data retention and bounded cleanup policies for cloud database."""
import datetime
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import StagingRecord, Price, DataLineage

logger = logging.getLogger(__name__)

# Default retention policy: retain PROMOTED staging records for at least 30 days
DEFAULT_PROMOTED_RETENTION_DAYS = 30


def run_bounded_staging_cleanup(
    db: Session,
    retention_days: int = DEFAULT_PROMOTED_RETENTION_DAYS,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Clean up old PROMOTED staging records safely while preserving lineage and rejected debug data.

    Invariants:
    1. Only records with status='PROMOTED' older than retention_days are candidates.
    2. REJECTED records are NEVER deleted by this routine (retained for debugging/audit).
    3. PENDING/VALIDATED records are NEVER deleted.
    4. Canonical prices and lineage records are NEVER touched.
    5. Dry-run mode by default.
    """
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)

    query = db.query(StagingRecord).filter(
        StagingRecord.status == "PROMOTED",
        StagingRecord.created_at < cutoff_date,
    )

    eligible_count = query.count()

    # Safety checks
    total_canonical_prices = db.query(func.count(Price.id)).scalar() or 0
    total_lineage_records = db.query(func.count(DataLineage.id)).scalar() or 0

    result = {
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": retention_days,
        "eligible_promoted_records": eligible_count,
        "dry_run": dry_run,
        "deleted_count": 0,
        "preserved_canonical_prices": total_canonical_prices,
        "preserved_lineage_records": total_lineage_records,
    }

    if dry_run or eligible_count == 0:
        logger.info(f"[Retention Cleanup] DRY RUN: {eligible_count} promoted records eligible for deletion.")
        return result

    # Execute deletion safely
    deleted = query.delete(synchronize_session=False)
    db.commit()
    result["deleted_count"] = deleted
    logger.info(f"[Retention Cleanup] Executed: {deleted} old promoted staging records deleted.")
    return result

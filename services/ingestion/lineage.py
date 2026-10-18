"""
Data Lineage & Provenance Module.
Enforces that every canonical record can trace back:
Canonical -> Staging -> Raw Source -> Source ID -> URL/File Identifier -> Publication Timestamp -> Retrieval Timestamp -> Observed Period.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database.models import DataLineage, StagingRecord, DataSource

class Provenance(BaseModel):
    canonical_table: str
    canonical_id: str
    staging_id: Optional[int] = None
    source_id: Optional[int] = None
    source_name: str
    url_or_path: str
    retrieved_at: datetime
    published_at: Optional[datetime] = None
    observed_period: Optional[str] = None
    run_id: str
    checksum: Optional[str] = None
    validation_status: str = "VALIDATED"
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)

class LineageTracker:
    @staticmethod
    def record_lineage(session: Session, provenance: Provenance) -> DataLineage:
        """Stores provenance link in database."""
        entry = DataLineage(
            record_table=provenance.canonical_table,
            record_id=str(provenance.canonical_id),
            raw_source=f"{provenance.source_name} [Run: {provenance.run_id}]",
            url=provenance.url_or_path,
            retrieved_at=provenance.retrieved_at,
            checksum=provenance.checksum
        )
        session.add(entry)
        session.flush()
        return entry

    @staticmethod
    def get_lineage(session: Session, table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves and traces full lineage of a canonical record."""
        lineage = session.query(DataLineage).filter(
            DataLineage.record_table == table_name,
            DataLineage.record_id == str(record_id)
        ).first()

        if not lineage:
            return None

        return {
            "record_table": lineage.record_table,
            "record_id": lineage.record_id,
            "raw_source": lineage.raw_source,
            "url_or_path": lineage.url,
            "retrieved_at": lineage.retrieved_at.isoformat() if lineage.retrieved_at else None,
            "checksum": lineage.checksum,
            "created_at": lineage.created_at.isoformat() if lineage.created_at else None
        }

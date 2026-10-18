from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import DataLineage, DataSource, MacroObservation, MacroSeries


MacroStatus = Literal["AVAILABLE", "STALE", "INSUFFICIENT_DATA"]


class MacroSeriesLatest(BaseModel):
    series_id: str
    name: str
    region: Literal["VIETNAM", "US", "CHINA", "GLOBAL"]
    provider: str
    value: Optional[float] = None
    unit: str
    frequency: str
    observation_date: Optional[date] = None
    release_date: Optional[date] = None
    published_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    status: MacroStatus
    data_origin: Optional[str] = None


class MacroLatestResponse(BaseModel):
    as_of_date: date
    status: Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"]
    regions: dict[str, list[MacroSeriesLatest]]


def _region_for_country(country: Optional[str]) -> Literal["VIETNAM", "US", "CHINA", "GLOBAL"]:
    normalized = (country or "").strip().upper()
    if normalized in {"VNM", "VN", "VIETNAM"}:
        return "VIETNAM"
    if normalized in {"US", "USA", "UNITED STATES"}:
        return "US"
    if normalized in {"CN", "CHN", "CHINA"}:
        return "CHINA"
    return "GLOBAL"


def _stale_after_days(frequency: str) -> int:
    return {
        "DAILY": 10,
        "WEEKLY": 21,
        "MONTHLY": 75,
        "QUARTERLY": 160,
        "ANNUAL": 550,
    }.get(frequency.upper(), 90)


def get_latest_macro_series(session: Session, as_of: date) -> MacroLatestResponse:
    now = datetime.combine(as_of, datetime.max.time(), tzinfo=timezone.utc)
    regions: dict[str, list[MacroSeriesLatest]] = {
        "VIETNAM": [], "US": [], "CHINA": [], "GLOBAL": [],
    }
    for series in session.query(MacroSeries).order_by(MacroSeries.id).all():
        source = session.query(DataSource).filter(DataSource.id == series.source_id).first() if series.source_id else None
        eligible = session.query(MacroObservation).filter(
            MacroObservation.series_id == series.id,
            MacroObservation.observation_date <= as_of,
            (MacroObservation.published_at.is_(None)) | (MacroObservation.published_at <= now),
            (MacroObservation.release_date.is_(None)) | (MacroObservation.release_date <= as_of),
        ).order_by(
            MacroObservation.observation_date.desc(), MacroObservation.version.desc()
        ).all()
        observation = next((item for item in eligible if item.status == "VALID" and not item.anomaly), None)
        region = _region_for_country(source.country if source else None)
        if observation is None:
            regions[region].append(MacroSeriesLatest(
                series_id=series.id,
                name=series.name,
                region=region,
                provider=series.provider,
                unit=series.unit,
                frequency=series.frequency,
                source=source.name if source else series.provider,
                source_type=source.source_type if source else None,
                status="INSUFFICIENT_DATA",
                data_origin="REGISTERED_SERIES",
            ))
            continue

        lineage = session.query(DataLineage).filter(
            DataLineage.record_table == "macro_observations",
            DataLineage.record_id == str(observation.id),
        ).order_by(DataLineage.created_at.desc()).first()
        age_days = (as_of - observation.observation_date).days
        regions[region].append(MacroSeriesLatest(
            series_id=series.id,
            name=series.name,
            region=region,
            provider=series.provider,
            value=float(observation.value),
            unit=series.unit,
            frequency=series.frequency,
            observation_date=observation.observation_date,
            release_date=observation.release_date,
            published_at=observation.published_at,
            retrieved_at=lineage.retrieved_at if lineage else None,
            source=source.name if source else series.provider,
            source_url=lineage.url if lineage else None,
            source_type=source.source_type if source else None,
            status="STALE" if age_days > _stale_after_days(series.frequency) else "AVAILABLE",
            data_origin=("LINEAGED_INGESTION" if lineage else "SEEDED_OR_UNTRACED"),
        ))

    with_values = [item for items in regions.values() for item in items if item.value is not None]
    configured_count = sum(len(items) for items in regions.values())
    response_status = (
        "INSUFFICIENT_DATA" if not with_values else
        "AVAILABLE" if len(with_values) == configured_count and all(item.status == "AVAILABLE" for item in with_values) else "PARTIAL"
    )
    return MacroLatestResponse(as_of_date=as_of, status=response_status, regions=regions)
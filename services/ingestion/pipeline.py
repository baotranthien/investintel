"""
Production-grade Ingestion Pipeline.
Implements: Raw -> Staging -> Validation -> Canonical Promotion
Tracks Ingestion Runs, Provenance, and generates DataQualityReport.
Never silently drops records; rejected records are inspectable in StagingRecord.
"""
import uuid
import hashlib
import math
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import (
    DataSource,
    DataRun,
    Asset,
    Price,
    StagingRecord,
    DataQualityReportRecord,
    FinancialStatement,
    MacroSeries,
    MacroObservation,
    EventRecord,
)
from .lineage import LineageTracker, Provenance

class DataQualityChecker:
    @staticmethod
    def validate_news_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        title = row.get("title")
        if not title or not str(title).strip():
            errors.append("Missing or empty article title")
        published_at = row.get("published_at")
        if not published_at:
            errors.append("Missing published_at timestamp")
        url = row.get("url")
        if not url or not str(url).strip():
            errors.append("Missing or empty article URL")
        return (len(errors) == 0, errors)

    @staticmethod
    def validate_price_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        # Check required fields
        if not row.get("observation_date"):
            errors.append("Missing observation_date")
        if row.get("close") is None:
            errors.append("Missing close price")
        
        # Numeric validity
        try:
            close = float(row.get("close", 0))
            if close <= 0:
                errors.append(f"Impossible close price: {close} <= 0")
        except (ValueError, TypeError):
            errors.append("Non-numeric close price")

        open_p = row.get("open")
        high_p = row.get("high")
        low_p = row.get("low")
        vol = row.get("volume")

        if high_p is not None and low_p is not None:
            try:
                if float(high_p) < float(low_p):
                    errors.append(f"Impossible high/low spread: high ({high_p}) < low ({low_p})")
            except (ValueError, TypeError):
                errors.append("Non-numeric high or low price")

        if vol is not None:
            try:
                if float(vol) < 0:
                    errors.append(f"Negative volume: {vol}")
            except (ValueError, TypeError):
                errors.append("Non-numeric volume")

        return (len(errors) == 0, errors)

class IngestionPipeline:
    def __init__(self, session: Session):
        self.session = session

    def start_run(self, provider: str, dataset: str) -> DataRun:
        run_id = f"run-{provider.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        run = DataRun(
            run_id=run_id,
            provider=provider,
            dataset=dataset,
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
            records_fetched=0,
            records_inserted=0,
            records_updated=0,
            records_rejected=0
        )
        self.session.add(run)
        self.session.commit()
        return run

    def ingest_market_data(
        self,
        provider: str,
        symbol: str,
        exchange: str,
        records: List[Dict[str, Any]],
        source_url_or_path: str,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes Raw -> Staging -> Validation -> Canonical Promotion for Market Data.
        """
        run = self.start_run(provider, f"market_data_{symbol}")
        started_at = datetime.now(timezone.utc)
        
        # 1. Ensure Asset exists
        asset = self.session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
        if not asset:
            asset = Asset(
                symbol=symbol.upper(),
                name=symbol.upper(),
                asset_type="STOCK",
                exchange=exchange.upper(),
                status="ACTIVE"
            )
            self.session.add(asset)
            self.session.flush()

        # 2. Stage all raw records
        staged_items: List[Tuple[StagingRecord, Dict[str, Any]]] = []
        for rec in records:
            obs_period = str(rec.get("observation_date", ""))
            pub_at = rec.get("published_at")
            if not pub_at and rec.get("observation_date"):
                # Default publication timestamp is EOD of observation date
                if isinstance(rec["observation_date"], date):
                    pub_at = datetime.combine(rec["observation_date"], datetime.min.time(), tzinfo=timezone.utc)
                elif isinstance(rec["observation_date"], str):
                    try:
                        d = datetime.strptime(rec["observation_date"], "%Y-%m-%d").date()
                        pub_at = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
                    except ValueError:
                        pub_at = None

            json_payload = {
                k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
                for k, v in rec.items()
            }

            staging = StagingRecord(
                run_id=run.run_id,
                source_id=source_id,
                provider=provider,
                dataset=f"prices_{symbol.upper()}",
                raw_payload=json_payload,
                status="PENDING",
                retrieved_at=datetime.now(timezone.utc),
                observed_period=obs_period,
                published_at=pub_at
            )
            self.session.add(staging)
            staged_items.append((staging, rec))
        
        self.session.flush()

        # 3. Validate
        valid_items = []
        rejected_items = []
        seen_dates = set()
        duplicates_count = 0
        impossible_values_count = 0

        for staging, raw in staged_items:
            is_valid, errors = DataQualityChecker.validate_price_row(raw)
            obs_date = raw.get("observation_date")
            
            # Check for duplicate observation date in current batch
            if obs_date in seen_dates:
                is_valid = False
                errors.append(f"Duplicate observation_date in batch: {obs_date}")
                duplicates_count += 1
            else:
                seen_dates.add(obs_date)

            # Check impossible values
            if any("Impossible" in e or "Negative" in e for e in errors):
                impossible_values_count += 1

            if is_valid:
                staging.status = "VALIDATED"
                valid_items.append((staging, raw))
            else:
                staging.status = "REJECTED"
                staging.validation_errors = errors
                rejected_items.append((staging, raw, errors))

        self.session.flush()

        # 4. Canonical Promotion
        promoted_count = 0
        inserted_count = 0
        for staging, raw in valid_items:
            obs_d = raw["observation_date"]
            if isinstance(obs_d, str):
                obs_d = datetime.strptime(obs_d, "%Y-%m-%d").date()

            # Check if canonical price already exists
            existing_price = self.session.query(Price).filter(
                Price.asset_id == asset.id,
                Price.observation_date == obs_d
            ).first()

            checksum = hashlib.sha256(str(raw).encode("utf-8")).hexdigest()

            if existing_price:
                incoming = {
                    "raw_open": raw.get("open"),
                    "raw_high": raw.get("high"),
                    "raw_low": raw.get("low"),
                    "raw_close": float(raw["close"]),
                    "adjusted_close": float(raw.get("adjusted_close", raw["close"])),
                    "volume": raw.get("volume"),
                }
                if any(getattr(existing_price, key) != value for key, value in incoming.items()):
                    staging.status = "REJECTED"
                    staging.validation_errors = [
                        "Conflicting observation already exists; historical canonical price was preserved"
                    ]
                    rejected_items.append((staging, raw, staging.validation_errors))
                    continue
                canonical_id = existing_price.id
            else:
                # Insert new canonical price
                new_price = Price(
                    asset_id=asset.id,
                    observation_date=obs_d,
                    raw_open=raw.get("open"),
                    raw_high=raw.get("high"),
                    raw_low=raw.get("low"),
                    raw_close=float(raw["close"]),
                    adjusted_close=float(raw.get("adjusted_close", raw["close"])),
                    volume=raw.get("volume"),
                    source=provider,
                    data_quality_score=1.0,
                    status="VALID"
                )
                self.session.add(new_price)
                self.session.flush()
                canonical_id = new_price.id
                inserted_count += 1

            staging.status = "PROMOTED"
            promoted_count += 1

            # 5. Record Lineage
            LineageTracker.record_lineage(
                self.session,
                Provenance(
                    canonical_table="prices",
                    canonical_id=str(canonical_id),
                    staging_id=staging.id,
                    source_id=source_id,
                    source_name=provider,
                    url_or_path=source_url_or_path,
                    retrieved_at=staging.retrieved_at,
                    published_at=staging.published_at,
                    observed_period=staging.observed_period,
                    run_id=run.run_id,
                    checksum=checksum,
                    validation_status="VALIDATED"
                )
            )

        # 6. Quality Report
        total_records = len(records)
        completeness = promoted_count / total_records if total_records > 0 else 0.0
        status_verdict = "PASSED" if len(rejected_items) == 0 else ("WARNING" if promoted_count > 0 else "FAILED")

        quality_report = DataQualityReportRecord(
            run_id=run.run_id,
            provider=provider,
            dataset=f"prices_{symbol.upper()}",
            as_of_date=date.today(),
            completeness_score=completeness,
            freshness_score=1.0,
            duplicates_count=duplicates_count,
            anomalies_count=0,
            impossible_values_count=impossible_values_count,
            summary={
                "total_records": total_records,
                "promoted_records": promoted_count,
                "rejected_records": len(rejected_items),
                "rejection_reasons": [e for _, _, errs in rejected_items for e in errs]
            },
            status=status_verdict
        )
        self.session.add(quality_report)

        # 7. Finalize Run
        run.finished_at = datetime.now(timezone.utc)
        run.status = (
            "INSUFFICIENT_DATA" if total_records == 0 else
            "SUCCESS" if len(rejected_items) == 0 else
            "PARTIAL" if promoted_count > 0 else "FAILED"
        )
        run.records_fetched = total_records
        run.records_inserted = inserted_count
        run.records_rejected = len(rejected_items)
        if rejected_items:
            run.errors = f"{len(rejected_items)} records rejected during validation"

        self.session.commit()

        return {
            "run_id": run.run_id,
            "provider": provider,
            "symbol": symbol.upper(),
            "status": run.status,
            "records_received": total_records,
            "records_valid": promoted_count,
            "records_rejected": len(rejected_items),
            "started_at": started_at.isoformat(),
            "finished_at": run.finished_at.isoformat(),
            "quality_status": status_verdict,
            "rejected_samples": [
                {"raw": raw, "errors": errs} for _, raw, errs in rejected_items[:5]
            ]
        }

    def ingest_macro_series(
        self,
        provider: str,
        series_id: str,
        records: List[Any],
        source_url: str,
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Stage and validate macro observations, preserving every published revision."""
        run = self.start_run(provider, f"macro_{series_id}")
        series = self.session.query(MacroSeries).filter(MacroSeries.id == series_id).first()
        if not series or series.provider.upper() != provider.upper():
            run.status = "FAILED"
            run.finished_at = datetime.now(timezone.utc)
            run.errors = "Macro series is not registered for this provider"
            self.session.commit()
            return {"run_id": run.run_id, "provider": provider, "series_id": series_id,
                    "status": run.status, "records_received": 0, "records_inserted": 0,
                    "records_updated": 0, "records_rejected": 0,
                    "reason": run.errors}

        source_id = source_id or series.source_id
        now = datetime.now(timezone.utc)
        inserted_count = 0
        revision_count = 0
        rejected_count = 0
        seen_dates = set()
        rejection_reasons = []

        for point in records:
            observation_date = getattr(point, "observation_date", None)
            value = getattr(point, "value", None)
            release_date = getattr(point, "release_date", None)
            published_at = getattr(point, "published_at", None)
            if published_at is None and release_date is not None:
                published_at = datetime.combine(release_date, datetime.min.time(), tzinfo=timezone.utc)
            payload = {
                "series_id": series_id,
                "observation_date": observation_date.isoformat() if observation_date else None,
                "release_date": release_date.isoformat() if release_date else None,
                "published_at": published_at.isoformat() if published_at else None,
                "value": value,
                "unit": getattr(point, "unit", series.unit),
                "frequency": getattr(point, "frequency", series.frequency),
            }
            staging = StagingRecord(
                run_id=run.run_id, source_id=source_id, provider=provider,
                dataset=f"macro_{series_id}", raw_payload=payload, status="PENDING",
                retrieved_at=now, observed_period=payload["observation_date"],
                published_at=published_at,
            )
            self.session.add(staging)
            self.session.flush()

            errors = []
            if observation_date is None:
                errors.append("Missing observation_date")
            if observation_date in seen_dates:
                errors.append(f"Duplicate observation_date in batch: {observation_date}")
            seen_dates.add(observation_date)
            try:
                numeric_value = float(value)
                if not math.isfinite(numeric_value):
                    errors.append("Non-finite macro value")
            except (ValueError, TypeError):
                numeric_value = None
                errors.append("Non-numeric macro value")

            if errors:
                staging.status = "REJECTED"
                staging.validation_errors = errors
                rejected_count += 1
                rejection_reasons.extend(errors)
                continue

            staging.status = "VALIDATED"
            latest = self.session.query(MacroObservation).filter(
                MacroObservation.series_id == series_id,
                MacroObservation.observation_date == observation_date,
            ).order_by(MacroObservation.version.desc()).first()
            if latest and latest.value == numeric_value and latest.release_date == release_date:
                canonical = latest
            else:
                version = latest.version + 1 if latest else 1
                canonical = MacroObservation(
                    series_id=series_id,
                    observation_date=observation_date,
                    release_date=release_date,
                    revision_date=release_date if latest else None,
                    vintage=release_date.isoformat() if release_date else None,
                    value=numeric_value,
                    version=version,
                    published_at=published_at,
                    supersedes_id=latest.id if latest else None,
                    status="VALID",
                    anomaly=False,
                )
                self.session.add(canonical)
                self.session.flush()
                inserted_count += 1
                if latest:
                    revision_count += 1

            staging.status = "PROMOTED"
            checksum = hashlib.sha256(str(payload).encode("utf-8")).hexdigest()
            LineageTracker.record_lineage(
                self.session,
                Provenance(
                    canonical_table="macro_observations", canonical_id=str(canonical.id),
                    staging_id=staging.id, source_id=source_id, source_name=provider,
                    url_or_path=source_url, retrieved_at=now, published_at=published_at,
                    observed_period=payload["observation_date"], run_id=run.run_id,
                    checksum=checksum, validation_status="VALIDATED",
                ),
            )

        total_records = len(records)
        completeness = (total_records - rejected_count) / total_records if total_records else 0.0
        quality_status = (
            "FAILED" if total_records == 0 or rejected_count == total_records else
            "WARNING" if rejected_count else "PASSED"
        )
        self.session.add(DataQualityReportRecord(
            run_id=run.run_id, provider=provider, dataset=f"macro_{series_id}",
            as_of_date=date.today(), completeness_score=completeness,
            freshness_score=1.0 if total_records else 0.0,
            anomalies_count=rejected_count,
            summary={"total_records": total_records, "new_observations": inserted_count,
                     "revisions": revision_count, "rejected_records": rejected_count,
                     "rejection_reasons": rejection_reasons},
            status=quality_status,
        ))
        run.finished_at = datetime.now(timezone.utc)
        run.status = (
            "INSUFFICIENT_DATA" if total_records == 0 else
            "SUCCESS" if rejected_count == 0 else
            "PARTIAL" if rejected_count < total_records else "FAILED"
        )
        run.records_fetched = total_records
        run.records_inserted = inserted_count
        run.records_updated = revision_count
        run.records_rejected = rejected_count
        if rejection_reasons:
            run.errors = "; ".join(rejection_reasons[:10])
        if any(getattr(point, "published_at", None) is None and getattr(point, "release_date", None) is None for point in records):
            run.warnings = "Source does not provide publication/release timestamps for all observations"
        self.session.commit()
        return {
            "run_id": run.run_id, "provider": provider, "series_id": series_id,
            "status": run.status, "records_received": total_records,
            "records_inserted": inserted_count, "records_updated": revision_count,
            "records_rejected": rejected_count, "quality_status": quality_status,
            "publication_timestamp_gaps": bool(run.warnings),
        }

    def ingest_news_events(
        self,
        provider: str,
        articles: List[Dict[str, Any]],
        source_url: str,
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes Raw -> Staging -> Validation -> Canonical Promotion for News & Events.
        Produces full provenance and data quality report.
        """
        run = self.start_run(provider, "news_events")
        started_at = datetime.now(timezone.utc)
        now = datetime.now(timezone.utc)

        # 1. Staging
        staged_items: List[Tuple[StagingRecord, Dict[str, Any], Optional[datetime]]] = []
        for rec in articles:
            pub_at = rec.get("published_at")
            if isinstance(pub_at, str):
                try:
                    clean_ts = pub_at.replace("Z", "+00:00")
                    pub_dt = datetime.fromisoformat(clean_ts)
                except (ValueError, TypeError):
                    pub_dt = None
            elif isinstance(pub_at, datetime):
                pub_dt = pub_at
            else:
                pub_dt = None

            obs_period = pub_dt.strftime("%Y-%m-%d") if pub_dt else str(date.today())

            json_payload = {
                k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
                for k, v in rec.items()
            }

            staging = StagingRecord(
                run_id=run.run_id,
                source_id=source_id,
                provider=provider,
                dataset="news_events",
                raw_payload=json_payload,
                status="PENDING",
                retrieved_at=now,
                observed_period=obs_period,
                published_at=pub_dt,
            )
            self.session.add(staging)
            staged_items.append((staging, rec, pub_dt))

        self.session.flush()

        # 2. Validation
        valid_items = []
        rejected_items = []
        seen_keys = set()
        duplicates_count = 0

        for staging, raw, pub_dt in staged_items:
            rec_with_pub = dict(raw)
            if pub_dt:
                rec_with_pub["published_at"] = pub_dt

            is_valid, errors = DataQualityChecker.validate_news_row(rec_with_pub)

            dedup_key = raw.get("id") or raw.get("url") or raw.get("title")
            if dedup_key in seen_keys:
                is_valid = False
                errors.append(f"Duplicate article in batch: {dedup_key}")
                duplicates_count += 1
            else:
                seen_keys.add(dedup_key)

            if is_valid:
                staging.status = "VALIDATED"
                valid_items.append((staging, raw, pub_dt))
            else:
                staging.status = "REJECTED"
                staging.validation_errors = errors
                rejected_items.append((staging, raw, errors))

        self.session.flush()

        # 3. Canonical Promotion
        promoted_count = 0
        inserted_count = 0

        for staging, raw, pub_dt in valid_items:
            art_id = raw.get("id")
            if art_id:
                event_id = f"evt-{provider.lower()}-{art_id}"
            else:
                hash_key = (raw.get("url") or raw.get("title") or uuid.uuid4().hex).encode("utf-8")
                event_id = f"evt-{provider.lower()}-{hashlib.md5(hash_key).hexdigest()[:12]}"

            existing_event = self.session.query(EventRecord).filter(EventRecord.id == event_id).first()

            checksum = hashlib.sha256(str(raw).encode("utf-8")).hexdigest()

            if existing_event:
                canonical_id = existing_event.id
            else:
                title = str(raw.get("title", "")).strip()
                desc = str(raw.get("snippet") or raw.get("summaryVi") or raw.get("summary") or title).strip()
                source_name = raw.get("sourceName") or raw.get("source") or provider
                url = raw.get("url") or source_url

                new_event = EventRecord(
                    id=event_id,
                    title=title,
                    description=desc,
                    event_type=raw.get("event_type", "Market"),
                    materiality=raw.get("materiality", "INFORMATIONAL"),
                    severity=float(raw.get("severity", 50.0)),
                    sentiment=raw.get("sentiment", "NEUTRAL"),
                    countries=["VNM"],
                    affected_sectors=raw.get("affected_sectors", []),
                    impacts=raw.get("impacts", []),
                    sources=[{"name": source_name, "url": url}],
                    source_id=source_id,
                    published_at=pub_dt,
                    retrieved_at=now,
                    effective_at=pub_dt,
                    as_of_date=pub_dt.date() if pub_dt else date.today(),
                )
                self.session.add(new_event)
                self.session.flush()
                canonical_id = new_event.id
                inserted_count += 1

            staging.status = "PROMOTED"
            promoted_count += 1

            # Lineage
            LineageTracker.record_lineage(
                self.session,
                Provenance(
                    canonical_table="events",
                    canonical_id=str(canonical_id),
                    staging_id=staging.id,
                    source_id=source_id,
                    source_name=provider,
                    url_or_path=raw.get("url") or source_url,
                    retrieved_at=staging.retrieved_at,
                    published_at=staging.published_at,
                    observed_period=staging.observed_period,
                    run_id=run.run_id,
                    checksum=checksum,
                    validation_status="VALIDATED"
                )
            )

        # 4. Data Quality Report
        total_records = len(articles)
        completeness = promoted_count / total_records if total_records > 0 else 0.0
        status_verdict = "PASSED" if len(rejected_items) == 0 else ("WARNING" if promoted_count > 0 else "FAILED")

        quality_report = DataQualityReportRecord(
            run_id=run.run_id,
            provider=provider,
            dataset="news_events",
            as_of_date=date.today(),
            completeness_score=completeness,
            freshness_score=1.0 if total_records > 0 else 0.0,
            duplicates_count=duplicates_count,
            anomalies_count=len(rejected_items),
            impossible_values_count=0,
            summary={
                "total_records": total_records,
                "promoted_records": promoted_count,
                "rejected_records": len(rejected_items),
                "rejection_reasons": [e for _, _, errs in rejected_items for e in errs]
            },
            status=status_verdict
        )
        self.session.add(quality_report)

        # 5. Finalize Run
        run.finished_at = datetime.now(timezone.utc)
        run.status = (
            "INSUFFICIENT_DATA" if total_records == 0 else
            "SUCCESS" if len(rejected_items) == 0 else
            "PARTIAL" if promoted_count > 0 else "FAILED"
        )
        run.records_fetched = total_records
        run.records_inserted = inserted_count
        run.records_rejected = len(rejected_items)
        if rejected_items:
            run.errors = f"{len(rejected_items)} articles rejected during validation"

        self.session.commit()

        return {
            "run_id": run.run_id,
            "provider": provider,
            "dataset": "news_events",
            "status": run.status,
            "records_received": total_records,
            "records_valid": promoted_count,
            "records_inserted": inserted_count,
            "records_rejected": len(rejected_items),
            "started_at": started_at.isoformat(),
            "finished_at": run.finished_at.isoformat(),
            "quality_status": status_verdict,
            "rejected_samples": [
                {"raw": raw, "errors": errs} for _, raw, errs in rejected_items[:5]
            ]
        }


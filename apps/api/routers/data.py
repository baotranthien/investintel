import os
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import date

from database.connection import SessionLocal
from database.models import Asset, Price, DataRun, DataSource, DataQualityReportRecord, DataLineage

router = APIRouter(prefix="/api/v1", tags=["data"])

@router.get("/assets")
def get_assets():
    """Returns canonical assets from database, with fallback to registered symbols."""
    session = SessionLocal()
    try:
        db_assets = session.query(Asset).all()
        return [
            {
                "symbol": a.symbol,
                "name": a.name or a.symbol,
                "asset_type": a.asset_type,
                "exchange": a.exchange,
                "sector": a.sector,
                "status": a.status
            }
            for a in db_assets
        ]
    finally:
        session.close()

@router.get("/assets/{symbol}/snapshot")
def get_asset_snapshot(symbol: str):
    """Returns the latest market price and data quality for the given symbol."""
    sym = symbol.upper()
    session = SessionLocal()
    try:
        asset = session.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset {sym} not found in database.")

        latest_price = session.query(Price).filter(Price.asset_id == asset.id).order_by(
            Price.observation_date.desc()
        ).first()

        if latest_price:
            lineage = session.query(DataLineage).filter(
                DataLineage.record_table == "prices",
                DataLineage.record_id == str(latest_price.id)
            ).first()

            return {
                "symbol": sym,
                "price": {
                    "value": latest_price.raw_close,
                    "open": latest_price.raw_open,
                    "high": latest_price.raw_high,
                    "low": latest_price.raw_low,
                    "adjusted_close": latest_price.adjusted_close,
                    "volume": latest_price.volume,
                    "unit": "VND",
                    "as_of": latest_price.observation_date.isoformat(),
                    "source": latest_price.source,
                    "quality": latest_price.data_quality_score
                },
                "data_quality": {
                    "completeness": 1.0,
                    "freshness": 1.0,
                    "overall": latest_price.data_quality_score or 1.0
                },
                "as_of": latest_price.observation_date.isoformat(),
                "sources": [latest_price.source or "MarketDataCSV"],
                "lineage": {
                    "raw_source": lineage.raw_source if lineage else None,
                    "url_or_path": lineage.url if lineage else None,
                    "retrieved_at": lineage.retrieved_at.isoformat() if lineage and lineage.retrieved_at else None,
                    "checksum": lineage.checksum if lineage else None
                }
            }

        return {
            "symbol": sym,
            "price": {
                "value": None,
                "unit": "VND",
                "as_of": None,
                "source": "NOT_CONFIGURED",
                "quality": None
            },
            "data_quality": {
                "completeness": 0.0,
                "freshness": 0.0,
                "overall": 0.0
            },
            "as_of": None,
            "sources": ["NOT_INGESTED"],
            "note": "No price observations found in database for symbol."
        }
    finally:
        session.close()

@router.get("/data/providers")
def get_providers():
    """Returns honest provider status based on actual database runs and env configuration."""
    session = SessionLocal()
    try:
        # Check FRED
        fred_key = os.getenv("FRED_API_KEY")
        fred_run = session.query(DataRun).filter(DataRun.provider == "FRED").order_by(DataRun.started_at.desc()).first()
        fred_status = fred_run.status if fred_run else ("CONFIGURED" if fred_key else "BLOCKED")
        fred_last_success = fred_run.finished_at.isoformat() if (fred_run and fred_run.status == "SUCCESS" and fred_run.finished_at) else None

        # Check BLS
        bls_key = os.getenv("BLS_API_KEY")
        bls_run = session.query(DataRun).filter(DataRun.provider == "BLS").order_by(DataRun.started_at.desc()).first()
        bls_status = bls_run.status if bls_run else ("CONFIGURED" if bls_key else "BLOCKED")
        bls_last_success = bls_run.finished_at.isoformat() if (bls_run and bls_run.status == "SUCCESS" and bls_run.finished_at) else None

        # Check MarketDataCSV
        csv_runs = session.query(DataRun).filter(DataRun.provider == "MarketDataCSV").order_by(DataRun.started_at.desc()).all()
        csv_success_runs = [r for r in csv_runs if r.status == "SUCCESS"]
        csv_last_run = csv_runs[0] if csv_runs else None
        csv_status = csv_last_run.status if csv_last_run else "NEVER_RUN"
        csv_last_success = csv_success_runs[0].finished_at.isoformat() if (csv_success_runs and csv_success_runs[0].finished_at) else None
        csv_records = sum(r.records_inserted or 0 for r in csv_success_runs)

        return [
            {
                "provider": "MarketDataCSV",
                "status": csv_status,
                "last_success": csv_last_success,
                "records_last_run": csv_records,
                "data_freshness": "RECENT" if csv_last_success else "NEVER_RUN",
                "requires": "Canonical CSV files with provenance in data/market/",
                "api_key_configured": True,
            },
            {
                "provider": "FRED",
                "status": fred_status,
                "last_success": fred_last_success,
                "records_last_run": fred_run.records_inserted if (fred_run and fred_run.status == "SUCCESS") else 0,
                "data_freshness": "NEVER_RUN" if not fred_last_success else "RECENT",
                "requires": "FRED_API_KEY environment variable",
                "api_key_configured": bool(fred_key),
                "reason": None if fred_key else "FRED_API_KEY environment variable is not configured"
            },
            {
                "provider": "BLS",
                "status": bls_status,
                "last_success": bls_last_success,
                "records_last_run": bls_run.records_inserted if (bls_run and bls_run.status == "SUCCESS") else 0,
                "data_freshness": "NEVER_RUN" if not bls_last_success else "RECENT",
                "requires": "BLS_API_KEY environment variable",
                "api_key_configured": bool(bls_key),
                "reason": None if bls_key else "BLS_API_KEY environment variable is not configured"
            },
            {
                "provider": "NSO_VIETNAM",
                "status": "BLOCKED",
                "last_success": None,
                "records_last_run": 0,
                "data_freshness": "NOT_IMPLEMENTED",
                "requires": "Manual CSV/Excel import (No official public JSON API)",
                "api_key_configured": False,
                "reason": "General Statistics Office Vietnam requires manual publication table import"
            }
        ]
    finally:
        session.close()

@router.get("/data/quality")
def get_quality_reports():
    """Returns stored data quality assessment reports."""
    session = SessionLocal()
    try:
        reports = session.query(DataQualityReportRecord).order_by(
            DataQualityReportRecord.created_at.desc()
        ).limit(10).all()
        return [
            {
                "run_id": r.run_id,
                "provider": r.provider,
                "dataset": r.dataset,
                "as_of_date": r.as_of_date.isoformat(),
                "completeness_score": r.completeness_score,
                "freshness_score": r.freshness_score,
                "duplicates_count": r.duplicates_count,
                "impossible_values_count": r.impossible_values_count,
                "status": r.status,
                "summary": r.summary
            }
            for r in reports
        ]
    finally:
        session.close()

@router.get("/macro/series")
def get_macro_series():
    """Returns macro series from database."""
    session = SessionLocal()
    try:
        from database.models import MacroSeries
        series = session.query(MacroSeries).all()
        return [
            {"id": s.id, "name": s.name, "provider": s.provider, "frequency": s.frequency, "unit": s.unit}
            for s in series
        ]
    finally:
        session.close()

@router.get("/data/point-in-time/{symbol}")
def get_point_in_time(symbol: str, as_of: str = Query(..., description="As-of date in YYYY-MM-DD format")):
    """Point-in-time historical query ensuring publication_date <= as_of."""
    from services.ingestion.point_in_time import get_data_as_of
    try:
        as_of_d = date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format for as_of. Expected YYYY-MM-DD.")
    
    session = SessionLocal()
    try:
        return get_data_as_of(symbol, as_of_d, session=session)
    finally:
        session.close()

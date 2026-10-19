"""Registry-driven recurring ingestion for supported external and local sources."""
import asyncio
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from database.connection import SessionLocal
from database.models import Asset, DataRun, DataSource, MacroSeries
from .bls import BlsProvider
from .fred import FredProvider
from .nso import NsoProvider
from .world_bank import WorldBankProvider
from .open_fx import FreeFxProvider
from .gdelt import GDELTNewsProvider
from .vndirect import VndirectProvider
from .http_client import ProviderUnavailableError
from .market_data import MarketDataCsvProvider
from .dnse import DnseProvider
from .vietstock import VietstockNewsProvider
from .lotusmarket import LotusMarketProvider
from .reconciliation import MarketDataReconciliationEngine
from .pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


def _record_failure(session_factory: Callable, provider: str, dataset: str, status: str, error: str) -> None:
    session = session_factory()
    try:
        session.add(DataRun(
            run_id=f"run-{provider.lower()}-{uuid.uuid4().hex[:12]}",
            provider=provider,
            dataset=dataset,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            status=status,
            records_fetched=0,
            records_inserted=0,
            records_updated=0,
            records_rejected=0,
            errors=error[:2000],
        ))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Could not persist failed ingestion state for %s/%s", provider, dataset)
    finally:
        session.close()


async def run_ingestion_cycle(
    session_factory: Callable = SessionLocal,
    target_symbols: Optional[list[str]] = None,
    target_providers: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Fetch currently registered supported sources and persist honest run results."""
    allowed_providers = {p.upper() for p in target_providers} if target_providers else None
    selected_symbols = {s.upper() for s in target_symbols} if target_symbols else None

    session = session_factory()
    try:
        source_ids = {
            source.name.upper(): source.id
            for source in session.query(DataSource).filter(DataSource.active.is_(True)).all()
        }
        # Ensure LOTUSMARKET DataSource exists if missing
        if "LOTUSMARKET" not in source_ids:
            lotus_ds = session.query(DataSource).filter_by(name="LOTUSMARKET").first()
            if not lotus_ds:
                lotus_ds = DataSource(
                    name="LOTUSMARKET",
                    provider="LOTUSMARKET",
                    country="VNM",
                    authority_level="REPUTABLE_SECONDARY",
                    source_type="API",
                    base_url="https://bgapidatafeed.vps.com.vn",
                    active=True,
                )
                session.add(lotus_ds)
                session.commit()
            source_ids["LOTUSMARKET"] = lotus_ds.id

        # Ensure VN100 & VN30 Assets exist
        for idx_sym, idx_name in [("VN100", "Chỉ số VN100 Index"), ("VN30", "Chỉ số VN30 Index")]:
            existing_idx = session.query(Asset).filter_by(symbol=idx_sym).first()
            if not existing_idx:
                session.add(Asset(symbol=idx_sym, name=idx_name, asset_type="INDEX", exchange="HOSE", sector="Benchmark"))
                session.commit()

        # Ensure IndexMembership is seeded for VN100
        from database.models import IndexMembership
        vn100_members = session.query(IndexMembership).filter_by(index_symbol="VN100").count()
        if vn100_members == 0:
            from services.ingestion.seed_data import seed_index_memberships
            seed_index_memberships(session, source_ids["LOTUSMARKET"])

        macro_series = [
            (series.id, series.provider.upper(), series.source_id)
            for series in session.query(MacroSeries).all()
            if series.provider.upper() in {"FRED", "BLS", "WORLD_BANK", "OPEN_EXCHANGE_RATES", "NSO_VIETNAM"}
            and source_ids.get(series.provider.upper()) == series.source_id
        ]

        # Query assets: filter by selected_symbols if provided
        asset_query = session.query(Asset)
        if selected_symbols:
            asset_query = asset_query.filter(Asset.symbol.in_(list(selected_symbols)))
        else:
            asset_query = asset_query.filter(Asset.status == "ACTIVE", Asset.exchange == "HOSE")

        hose_assets = [
            (asset.symbol, asset.exchange or "HOSE", source_ids.get("HOSE_CSV") or source_ids.get("LOTUSMARKET"))
            for asset in asset_query.all()
        ]
    finally:
        session.close()

    results: list[dict[str, Any]] = []
    lookback_days = max(1, int(os.getenv("INGESTION_LOOKBACK_DAYS", "90")))
    start_date = date.today() - timedelta(days=lookback_days)
    batch_limit = max(1, min(20, int(os.getenv("INGESTION_BATCH_LIMIT", "5"))))
    effective_assets = hose_assets if selected_symbols else hose_assets[:batch_limit]

    providers = {
        "FRED": FredProvider,
        "BLS": BlsProvider,
        "WORLD_BANK": WorldBankProvider,
        "OPEN_EXCHANGE_RATES": FreeFxProvider,
        "NSO_VIETNAM": NsoProvider,
    }

    # 1. Macro series ingestion (isolated per series)
    run_macro = allowed_providers is None or any(p in allowed_providers for p in ("FRED", "BLS", "WORLD_BANK", "OPEN_EXCHANGE_RATES", "NSO_VIETNAM", "MACRO"))
    if run_macro:
        for series_id, provider_name, source_id in macro_series:
            if allowed_providers is not None and provider_name not in allowed_providers and "MACRO" not in allowed_providers:
                continue

            if provider_name == "FRED" and not os.getenv("FRED_API_KEY"):
                if os.getenv("ENABLE_FRED_CSV_FALLBACK", "false").lower() in ("true", "1", "yes"):
                    pass # Proceed to FredProvider which uses public CSV fallback
                else:
                    results.append({
                        "provider": "FRED",
                        "series_id": series_id,
                        "status": "BLOCKED_MISSING_CREDENTIAL",
                        "records_received": 0,
                        "reason": "FRED_API_KEY is not configured in environment"
                    })
                    continue

            if provider_name == "BLS" and os.getenv("ENABLE_BLS_INGESTION", "true").lower() not in ("true", "1", "yes"):
                continue

            if provider_name == "WORLD_BANK" and os.getenv("ENABLE_WORLDBANK_INGESTION", "true").lower() not in ("true", "1", "yes"):
                continue

            if provider_name == "OPEN_EXCHANGE_RATES" and os.getenv("ENABLE_FX_INGESTION", "true").lower() not in ("true", "1", "yes"):
                continue

            if provider_name == "NSO_VIETNAM" and os.getenv("ENABLE_NSO_INGESTION", "true").lower() not in ("true", "1", "yes"):
                continue

            provider = providers[provider_name]()
            try:
                if provider_name == "FRED":
                    records = await provider.fetch_macro_series(series_id, start_date=start_date.isoformat())
                    source_url = (
                        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
                        if os.getenv("FRED_API_KEY")
                        else f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
                    )
                elif provider_name == "BLS":
                    first_year = max(2010, start_date.year)
                    records = await provider.fetch_macro_series(
                        series_id, start_year=str(first_year), end_year=str(date.today().year)
                    )
                    source_url = getattr(provider, "base_url", "https://api.bls.gov/publicAPI/v1/timeseries/data/")
                elif provider_name == "WORLD_BANK":
                    records = await provider.fetch_macro_series(series_id)
                    source_url = f"https://api.worldbank.org/v2/country/VNM/indicator/{series_id}?format=json"
                elif provider_name == "OPEN_EXCHANGE_RATES":
                    records = await provider.fetch_macro_series(series_id)
                    source_url = "https://open.er-api.com/v6/latest/USD"
                elif provider_name == "NSO_VIETNAM":
                    records = await provider.fetch_macro_series(series_id)
                    source_url = "https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO"
                else:
                    records = []
                    source_url = "unknown"

                db = session_factory()
                try:
                    outcome = IngestionPipeline(db).ingest_macro_series(
                        provider_name, series_id, records, source_url, source_id
                    )
                    results.append(outcome)
                finally:
                    db.close()
            except Exception as exc:
                state = "BLOCKED_MISSING_CREDENTIAL" if isinstance(exc, ProviderUnavailableError) and "required but not set" in str(exc) else "FAILURE"
                _record_failure(session_factory, provider_name, f"macro_{series_id}", state, str(exc))
                results.append({"provider": provider_name, "series_id": series_id,
                                "status": state, "records_received": 0, "reason": str(exc)})
                logger.warning("Ingestion failed for %s/%s: %s", provider_name, series_id, exc)

    # 2. Local Market Data CSV (HOSE_CSV)
    if allowed_providers is None or "HOSE_CSV" in allowed_providers:
        csv_provider = MarketDataCsvProvider()
        repository_root = Path(__file__).resolve().parents[2]
        for symbol, exchange, source_id in effective_assets:
            csv_path = repository_root / "data" / "market" / f"{symbol.lower()}_historical.csv"
            if not csv_path.is_file():
                results.append({"provider": "HOSE_CSV", "symbol": symbol,
                                "status": "BLOCKED", "records_received": 0,
                                "reason": f"Registered local market file not found: {csv_path.name}"})
                continue
            try:
                points = await csv_provider.fetch_market_data(
                    symbol, start_date, date.today(), file_path=str(csv_path)
                )
                records = [point.model_dump() for point in points]
                db = session_factory()
                try:
                    outcome = IngestionPipeline(db).ingest_market_data(
                        provider="HOSE_CSV", symbol=symbol, exchange=exchange or "HOSE",
                        records=records, source_url_or_path=str(csv_path), source_id=source_id,
                    )
                    results.append(outcome)
                finally:
                    db.close()
            except Exception as exc:
                _record_failure(session_factory, "HOSE_CSV", f"market_data_{symbol}", "FAILURE", str(exc))
                results.append({"provider": "HOSE_CSV", "symbol": symbol,
                                "status": "FAILURE", "records_received": 0, "reason": str(exc)})
                logger.warning("Ingestion failed for HOSE_CSV/%s: %s", symbol, exc)

    # 3. Vietstock news ingestion (independent)
    if (allowed_providers is None or "VIETSTOCK" in allowed_providers) and "VIETSTOCK" in source_ids and os.getenv("ENABLE_VIETSTOCK_INGESTION", "false").lower() in ("true", "1", "yes"):
        try:
            vietstock_prov = VietstockNewsProvider()
            db = session_factory()
            try:
                outcome = vietstock_prov.ingest_to_database(db, source_id=source_ids.get("VIETSTOCK"))
                results.append(outcome)
            finally:
                db.close()
        except Exception as exc:
            _record_failure(session_factory, "VIETSTOCK", "news_events", "FAILURE", str(exc))
            results.append({"provider": "VIETSTOCK", "dataset": "news_events", "status": "FAILURE", "reason": str(exc)})
            logger.warning("Ingestion failed for VIETSTOCK: %s", exc)

    # 4. GDELT news ingestion (independent)
    if (allowed_providers is None or "GDELT" in allowed_providers) and "GDELT" in source_ids and os.getenv("ENABLE_GDELT_INGESTION", "false").lower() in ("true", "1", "yes"):
        try:
            gdelt_prov = GDELTNewsProvider()
            db = session_factory()
            try:
                outcome = await gdelt_prov.ingest_to_database(
                    db, query="vietnam stock market", max_records=15, source_id=source_ids.get("GDELT")
                )
                results.append(outcome)
            finally:
                db.close()
        except Exception as exc:
            _record_failure(session_factory, "GDELT", "news_events", "FAILURE", str(exc))
            results.append({"provider": "GDELT", "dataset": "news_events", "status": "FAILURE", "reason": str(exc)})
            logger.warning("Ingestion failed for GDELT: %s", exc)

    # 5. DNSE market data (bounded by batch_limit or selected_symbols)
    if (allowed_providers is None or "DNSE" in allowed_providers) and "DNSE" in source_ids and os.getenv("ENABLE_DNSE_INGESTION", "false").lower() in ("true", "1", "yes"):
        dnse_prov = DnseProvider()
        for symbol, exchange, _ in effective_assets:
            try:
                db = session_factory()
                try:
                    outcome = dnse_prov.ingest_to_database(
                        db, symbol, start_date=start_date, end_date=date.today(),
                        exchange=exchange or "HOSE", source_id=source_ids.get("DNSE")
                    )
                    results.append(outcome)
                finally:
                    db.close()
            except Exception as exc:
                _record_failure(session_factory, "DNSE", f"market_data_{symbol}", "FAILURE", str(exc))
                results.append({"provider": "DNSE", "symbol": symbol, "status": "FAILURE", "reason": str(exc)})
                logger.warning("Ingestion failed for DNSE/%s: %s", symbol, exc)

    # 6. VNDIRECT market data & fundamentals (bounded by batch_limit or selected_symbols)
    if (allowed_providers is None or "VNDIRECT" in allowed_providers) and "VNDIRECT" in source_ids:
        is_vndirect_targeted = allowed_providers is not None and "VNDIRECT" in allowed_providers
        is_vndirect_env = os.getenv("ENABLE_VNDIRECT_INGESTION", "false").lower() in ("true", "1", "yes")
        if is_vndirect_targeted or is_vndirect_env:
            vndirect_prov = VndirectProvider()
            for symbol, exchange, _ in effective_assets:
                # Prices
                try:
                    db = session_factory()
                    try:
                        outcome = await vndirect_prov.ingest_to_database(
                            db, symbol, start_date=start_date, end_date=date.today(),
                            exchange=exchange or "HOSE", source_id=source_ids.get("VNDIRECT")
                        )
                        results.append(outcome)
                    finally:
                        db.close()
                except Exception as exc:
                    _record_failure(session_factory, "VNDIRECT", f"market_data_{symbol}", "FAILURE", str(exc))
                    results.append({"provider": "VNDIRECT", "symbol": symbol, "status": "FAILURE", "reason": str(exc)})
                    logger.warning("Ingestion failed for VNDIRECT prices/%s: %s", symbol, exc)

                # Fundamentals & Corporate Profile (if targeted or env enabled)
                if is_vndirect_targeted or os.getenv("ENABLE_VNDIRECT_FUNDAMENTALS", "false").lower() in ("true", "1", "yes"):
                    try:
                        db = session_factory()
                        try:
                            await vndirect_prov.ingest_company_profile(db, symbol, source_id=source_ids.get("VNDIRECT"))
                            res_fs = await vndirect_prov.ingest_fundamentals(db, symbol, report_type="QUARTER", periods_limit=8, source_id=source_ids.get("VNDIRECT"))
                            res_annual = await vndirect_prov.ingest_fundamentals(db, symbol, report_type="ANNUAL", periods_limit=4, source_id=source_ids.get("VNDIRECT"))
                            await vndirect_prov.ingest_ratios(db, symbol, source_id=source_ids.get("VNDIRECT"))
                            await vndirect_prov.ingest_events(db, symbol, source_id=source_ids.get("VNDIRECT"))
                            results.append({
                                "provider": "VNDIRECT",
                                "symbol": symbol,
                                "dataset": "fundamentals",
                                "status": res_fs.get("status", "SUCCESS")
                            })
                        finally:
                            db.close()
                    except Exception as exc:
                        _record_failure(session_factory, "VNDIRECT", f"fundamentals_{symbol}", "FAILURE", str(exc))
                        results.append({"provider": "VNDIRECT", "symbol": symbol, "dataset": "fundamentals", "status": "FAILURE", "reason": str(exc)})
                        logger.warning("Ingestion failed for VNDIRECT fundamentals/%s: %s", symbol, exc)
                await asyncio.sleep(0.1)

    # 7. LotusMarket market data & insider events (bounded by batch_limit or selected_symbols)
    if (allowed_providers is None or "LOTUSMARKET" in allowed_providers) and "LOTUSMARKET" in source_ids:
        is_explicitly_targeted = allowed_providers is not None and "LOTUSMARKET" in allowed_providers
        is_env_enabled = os.getenv("ENABLE_LOTUSMARKET_INGESTION", "false").lower() in ("true", "1", "yes")

        if not (is_explicitly_targeted or is_env_enabled):
            results.append({
                "provider": "LOTUSMARKET",
                "status": "BLOCKED_FLAG_DISABLED",
                "reason": "ENABLE_LOTUSMARKET_INGESTION is not enabled in environment (set to true on Render to allow ingestion)"
            })
            logger.warning("LotusMarket ingestion skipped: ENABLE_LOTUSMARKET_INGESTION is not enabled")
        else:
            lotus_prov = LotusMarketProvider()
            for symbol, exchange, _ in effective_assets:
                # Market prices (VPS + Entrade fallback)
                try:
                    db = session_factory()
                    try:
                        outcome = lotus_prov.ingest_to_database(
                            db, symbol, start_date=start_date, end_date=date.today(),
                            exchange=exchange or "HOSE", source_id=source_ids.get("LOTUSMARKET")
                        )
                        results.append(outcome)
                    finally:
                        db.close()
                except Exception as exc:
                    _record_failure(session_factory, "LOTUSMARKET", f"market_data_{symbol}", "FAILURE", str(exc))
                    results.append({"provider": "LOTUSMARKET", "symbol": symbol, "status": "FAILURE", "reason": str(exc)})
                    logger.warning("Ingestion failed for LOTUSMARKET prices/%s: %s", symbol, exc)

                # Insider transactions (CafeF via LotusMarket - for equities only)
                is_index = symbol.upper() in {"VN100", "VN30", "VNINDEX", "VNX50"}
                if not is_index:
                    try:
                        db = session_factory()
                        try:
                            outcome_events = lotus_prov.ingest_insider_events(
                                db, symbol, source_id=source_ids.get("LOTUSMARKET")
                            )
                            results.append(outcome_events)
                        finally:
                            db.close()
                    except Exception as exc:
                        _record_failure(session_factory, "LOTUSMARKET", f"insider_events_{symbol}", "FAILURE", str(exc))
                        results.append({"provider": "LOTUSMARKET", "symbol": symbol, "dataset": "insider_events", "status": "FAILURE", "reason": str(exc)})
                        logger.warning("Ingestion failed for LOTUSMARKET insider events/%s: %s", symbol, exc)

    # 8. Financial News RSS Ingestion (CafeF & VnEconomy)
    if allowed_providers is None or "FINANCIAL_NEWS" in allowed_providers:
        try:
            from .financial_news import FinancialNewsProvider
            news_prov = FinancialNewsProvider()
            db = session_factory()
            try:
                outcome_news = news_prov.ingest_to_database(db, max_articles=40)
                results.append(outcome_news)
            finally:
                db.close()
        except Exception as exc:
            _record_failure(session_factory, "FINANCIAL_NEWS", "news_events", "FAILURE", str(exc))
            results.append({"provider": "FINANCIAL_NEWS", "dataset": "news_events", "status": "FAILURE", "reason": str(exc)})
            logger.warning("Ingestion failed for FINANCIAL_NEWS: %s", exc)

    # 9. Cross-Provider Reconciliation (if enabled)
    if (allowed_providers is None or "RECONCILIATION" in allowed_providers) and os.getenv("ENABLE_RECONCILIATION", "false").lower() in ("true", "1", "yes"):
        recon_engine = MarketDataReconciliationEngine()
        for symbol, _, _ in effective_assets:
            try:
                report = await recon_engine.compare_providers(symbol, start_date=start_date, end_date=date.today())
                db = session_factory()
                try:
                    recon_engine.record_quality_report(db, report)
                finally:
                    db.close()
                results.append({
                    "provider": "RECONCILIATION",
                    "symbol": symbol,
                    "status": report.status,
                    "matching_dates": report.matching_dates_count,
                    "major_disagreements": report.major_disagreement_count
                })
            except Exception as exc:
                logger.warning("Reconciliation failed for %s: %s", symbol, exc)

    # 9. Report unsupported sources without machine-readable API
    if allowed_providers is None:
        for unsupported in ("SBV",):
            if unsupported in source_ids:
                results.append({
                    "provider": unsupported,
                    "status": "BLOCKED_UNSUPPORTED_PUBLIC_INTERFACE",
                    "records_received": 0,
                    "reason": "No machine-readable public REST API is available for this official source"
                })
    return results


async def scheduled_ingestion_loop(stop_event: asyncio.Event) -> None:
    initial_delay = max(0, int(os.getenv("INGESTION_INITIAL_DELAY_SECONDS", "15")))
    interval = max(60, int(os.getenv("INGESTION_INTERVAL_SECONDS", "3600")))
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            results = await run_ingestion_cycle()
            logger.info("Scheduled ingestion cycle completed: %s", results)
        except Exception:
            logger.exception("Scheduled ingestion cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
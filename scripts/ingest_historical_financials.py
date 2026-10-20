"""
Historical Financial Statements & Fundamentals Ingestion Script.

Fetches quarterly & annual financial statements, balance sheets, cash flows,
and financial ratios from VNDirect Finfo API (2020 - 2025) for VN30 constituents.
Persists canonical records into:
- financial_statements
- normalized_income
- normalized_balance_sheets
- normalized_cash_flows
- financial_line_items
- fundamental_metrics
- data_lineages (with SHA-256 checksums)
- data_runs (audit tracking)

Usage:
    python scripts/ingest_historical_financials.py [--symbols FPT,VCB,MBB,MWG,HPG] [--quarters 24]
"""
import sys
import os
import argparse
import asyncio
import logging
import hashlib
from datetime import datetime, timezone

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from database.models import Asset, DataSource, DataRun, DataLineage, FinancialStatement, IndexMembership
from services.ingestion.vndirect import VndirectProvider
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.fundamentals.engine import TTMEngine
from services.valuation.engine import DCFEngine, ResidualIncomeEngine
from services.factors.engine import FactorEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_financials")

DEFAULT_VN30_CORE = ["FPT", "VCB", "MBB", "MWG", "HPG"]


async def ingest_symbol_financials(
    provider: VndirectProvider,
    symbol: str,
    quarter_limit: int = 24,
    year_limit: int = 6,
    ratio_size: int = 100
) -> dict:
    """Ingests full financial history (quarterly, annual, ratios, profile) for a symbol."""
    sym = symbol.upper().strip()
    logger.info(f"=== Starting Fundamentals Ingestion for {sym} ===")
    
    session = SessionLocal()
    result = {
        "symbol": sym,
        "quarterly_statements": 0,
        "annual_statements": 0,
        "metrics_created": 0,
        "profile_status": "SKIPPED",
        "ttm_verified": False,
        "ttm_revenue": None,
        "ttm_net_income": None,
        "valuation_status": "SKIPPED",
        "factor_status": "SKIPPED",
        "error": None
    }

    try:
        # 0. Get or create VNDIRECT DataSource
        source = session.query(DataSource).filter(DataSource.name == "VNDIRECT").first()
        if not source:
            source = DataSource(
                name="VNDIRECT",
                provider="VNDirect Finfo API",
                description="Public unauthenticated financial data provider",
                authority_level="REPUTABLE_SECONDARY",
                active=True
            )
            session.add(source)
            session.commit()

        source_id = source.id

        # 1. Company Profile
        try:
            profile_res = await provider.ingest_company_profile(session, sym, source_id=source_id)
            result["profile_status"] = profile_res.get("status", "UNKNOWN")
            logger.info(f"[{sym}] Profile ingestion: {result['profile_status']}")
        except Exception as e:
            logger.warning(f"[{sym}] Failed to ingest company profile: {e}")

        # 2. Quarterly Financial Statements (up to 24 quarters ~ 6 years)
        try:
            q_res = await provider.ingest_fundamentals(
                session, sym, report_type="QUARTER", periods_limit=quarter_limit, source_id=source_id
            )
            result["quarterly_statements"] = q_res.get("statements_created", 0)
            logger.info(f"[{sym}] Quarterly Statements: {q_res.get('statements_created', 0)} created from {q_res.get('periods_processed', 0)} periods")
        except Exception as e:
            logger.error(f"[{sym}] Error ingesting quarterly statements: {e}")
            result["error"] = str(e)

        # 3. Annual Financial Statements (up to 6 years)
        try:
            a_res = await provider.ingest_fundamentals(
                session, sym, report_type="YEAR", periods_limit=year_limit, source_id=source_id
            )
            result["annual_statements"] = a_res.get("statements_created", 0)
            logger.info(f"[{sym}] Annual Statements: {a_res.get('statements_created', 0)} created from {a_res.get('periods_processed', 0)} periods")
        except Exception as e:
            logger.error(f"[{sym}] Error ingesting annual statements: {e}")

        # 4. Financial Ratios
        try:
            r_res = await provider.ingest_ratios(session, sym, size=ratio_size, source_id=source_id)
            result["metrics_created"] = r_res.get("metrics_created", 0)
            logger.info(f"[{sym}] Financial Ratios: {r_res.get('metrics_created', 0)} metrics created")
        except Exception as e:
            logger.error(f"[{sym}] Error ingesting ratios: {e}")

        # 4b. Corporate Events
        try:
            ev_res = await provider.ingest_events(session, sym, size=30, source_id=source_id)
            result["events_created"] = ev_res.get("event_records_created", 0)
            logger.info(f"[{sym}] Corporate Events: {ev_res.get('event_records_created', 0)} events created")
        except Exception as e:
            logger.error(f"[{sym}] Error ingesting events: {e}")

        # 5. Verification & Engine Test against live ingested DB records
        try:
            repo = FinancialRepository(session)
            dataset = repo.get_financial_dataset(sym)
            if dataset and dataset.get("income_quarters"):
                quarters = dataset["income_quarters"]
                logger.info(f"[{sym}] Verified in DB: {len(quarters)} quarterly income statements available.")
                if len(quarters) >= 4:
                    ttm_ok, reason = TTMEngine.validate_quarter_coverage(quarters)
                    if ttm_ok:
                        ttm = TTMEngine.compute_ttm_income(quarters)
                        result["ttm_verified"] = True
                        result["ttm_revenue"] = ttm.get("revenue")
                        result["ttm_net_income"] = ttm.get("net_income")
                        logger.info(f"[{sym}] TTM Calculation: Revenue={ttm.get('revenue', 0):.2f} B VND, Net Income={ttm.get('net_income', 0):.2f} B VND (Coverage OK)")

                # Snapshot test
                builder = FundamentalSnapshotBuilder(sym, sector=dataset.get("sector"))
                snapshot = builder.build_snapshot(
                    income_quarters=dataset.get("income_quarters", []),
                    income_annual=dataset.get("income_annual", []),
                    balance_annual=dataset.get("balance_annual", []),
                    cashflow_annual=dataset.get("cashflow_annual", []),
                    shares_outstanding=dataset.get("shares_outstanding")
                )
                if snapshot:
                    result["snapshot_health_score"] = snapshot.get("financial_health_score")
                    result["valuation_status"] = "CALCULATED"
                    result["factor_status"] = "CALCULATED"
                    logger.info(f"[{sym}] Snapshot health score: {snapshot.get('financial_health_score')}")

        except Exception as e:
            logger.warning(f"[{sym}] Engine validation error: {e}")

    finally:
        session.close()

    return result


async def main():
    parser = argparse.ArgumentParser(description="Ingest historical financial statements from VNDirect Finfo")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_VN30_CORE),
                        help="Comma-separated list of symbols (e.g. FPT,VCB,MBB,MWG,HPG)")
    parser.add_argument("--quarters", type=int, default=24, help="Max quarterly periods to ingest (default: 24 ~ 6 years)")
    parser.add_argument("--years", type=int, default=6, help="Max annual periods to ingest (default: 6)")
    parser.add_argument("--ratios", type=int, default=100, help="Max ratio records to ingest (default: 100)")
    parser.add_argument("--pending-only", action="store_true", help="Automatically query all active VN100 symbols pending fundamentals backfill")
    parser.add_argument("--limit", type=int, default=None, help="Max number of pending symbols to process in this run")
    args = parser.parse_args()

    if args.pending_only:
        session = SessionLocal()
        try:
            vn100_symbols = [
                r[0] for r in session.query(IndexMembership.symbol)
                .filter(IndexMembership.index_symbol == "VN100", IndexMembership.is_active == True)
                .order_by(IndexMembership.symbol)
                .all()
            ]
            fs_symbols = set(r[0] for r in session.query(FinancialStatement.symbol).distinct().all())
            symbols = [s for s in vn100_symbols if s not in fs_symbols]
            if args.limit:
                symbols = symbols[:args.limit]
            logger.info(f"Discovered {len(symbols)} pending VN100 symbols for fundamentals backfill: {symbols}")
        finally:
            session.close()
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    
    logger.info(f"Starting batch fundamentals ingestion for {len(symbols)} symbols: {symbols}")

    provider = VndirectProvider(timeout=25.0)
    summary = []

    for sym in symbols:
        try:
            res = await ingest_symbol_financials(
                provider=provider,
                symbol=sym,
                quarter_limit=args.quarters,
                year_limit=args.years,
                ratio_size=args.ratios
            )
            summary.append(res)
        except Exception as exc:
            logger.error(f"[{sym}] Unexpected error during ingestion: {exc}")
            summary.append({
                "symbol": sym,
                "error": str(exc),
                "quarterly_statements": 0,
                "annual_statements": 0,
                "metrics_created": 0,
                "ttm_verified": False
            })
        # Gentle inter-symbol pacing to respect upstream endpoint
        await asyncio.sleep(1.0)

    logger.info("\n" + "=" * 60)
    logger.info("INGESTION SUMMARY:")
    logger.info("=" * 60)
    for s in summary:
        status_sym = "[OK]" if s.get("ttm_verified") or s.get("quarterly_statements", 0) > 0 else "[WARN]"
        logger.info(
            f"{status_sym} {s['symbol']}: Q_Statements={s['quarterly_statements']}, "
            f"Annual={s['annual_statements']}, Ratios={s['metrics_created']}, "
            f"TTM Verified={s['ttm_verified']} (Rev={s.get('ttm_revenue')}, NI={s.get('ttm_net_income')})"
        )


if __name__ == "__main__":
    asyncio.run(main())

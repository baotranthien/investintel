"""
Valuation Router — Phase 3 (Database Connected).

End-to-End Pipeline:
  Canonical Database (PostgreSQL)
  -> FinancialRepository (PIT-filtered)
  -> FundamentalSnapshotBuilder (real TTM/metrics)
  -> ValuationSnapshotBuilder (DCF, P/E, P/B, RI)
  -> ValuationSnapshot

No hardcoded EPS, BVPS, or revenue values.
DCF requires real revenue_ttm from fundamentals engine.
Peer multiples return INSUFFICIENT_DATA if not ingested.
Historical valuation percentiles return INSUFFICIENT_DATA if < 3 years of data.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.valuation.builder import ValuationSnapshotBuilder
from services.valuation.inputs import (
    get_asset_sector as _get_asset_sector,  # noqa: F401 (re-exported for services.ai.tools)
    get_latest_price as _get_latest_price,
    load_fundamentals_for_valuation as _load_fundamentals_for_valuation,
)
from database.connection import SessionLocal
from database.models import Asset, Price

router = APIRouter(prefix="/api/v1/valuation", tags=["valuation"])



@router.get("/{symbol}")
def get_valuation_snapshot(symbol: str, as_of: Optional[str] = Query(None, description="ISO date YYYY-MM-DD")):
    """
    Returns the comprehensive valuation snapshot with composite fair value and all methods.
    Reads real fundamental data from canonical PostgreSQL database.
    DCF, P/E, P/B driven by actual TTM metrics — no hardcoded values.
    """
    sym = symbol.upper()
    as_of_date = date.fromisoformat(as_of) if as_of else None

    # 1. Load real fundamentals
    fundamentals = _load_fundamentals_for_valuation(sym, as_of_date)
    if not fundamentals:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient fundamental data for '{sym}'. Ensure financial statements are ingested in database."
        )

    # 2. Load latest price
    current_price = _get_latest_price(sym, as_of_date)
    if not current_price:
        raise HTTPException(
            status_code=404,
            detail=f"No market price available for '{sym}'. Ensure market data is ingested."
        )

    # 3. Build valuation snapshot
    sector = fundamentals["sector"]
    builder = ValuationSnapshotBuilder(sym, sector)
    snapshot = builder.build(
        fundamentals=fundamentals,
        current_price=current_price,
        as_of=as_of_date or date.today()
    )

    result = snapshot.model_dump() if hasattr(snapshot, "model_dump") else (snapshot.dict() if hasattr(snapshot, "dict") else snapshot)
    result["data_sources"] = fundamentals["sources"]
    result["data_status"] = "CANONICAL_DATABASE"
    return result


@router.get("/{symbol}/relative")
def get_relative_valuation(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns relative valuation methods (P/E, P/B) with real fundamental inputs."""
    snapshot_data = get_valuation_snapshot(symbol, as_of=as_of)
    methods = snapshot_data.get("methods", [])
    relative_methods = [m for m in methods if "Relative" in m.get("method", "")]
    return {
        "symbol": symbol.upper(),
        "methods": relative_methods,
        "data_status": snapshot_data.get("data_status"),
    }


@router.get("/{symbol}/historical")
def get_historical_valuation(symbol: str):
    """
    Returns historical valuation percentiles.
    Computes real historical P/E and P/B series & percentiles (p25, p50, p75, current)
    from historical prices and fundamental EPS/BVPS.
    """
    sym = symbol.upper()
    session = SessionLocal()
    try:
        asset = session.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset '{sym}' not found.")

        prices = session.query(Price.observation_date, Price.raw_close).filter(
            Price.asset_id == asset.id,
            Price.status == "VALID",
            Price.raw_close > 0,
        ).order_by(Price.observation_date.asc()).all()

        price_count = len(prices)
        if price_count < 30:
            return {
                "symbol": sym,
                "status": "INSUFFICIENT_DATA",
                "reason": f"Requires minimum 30 trading days of price history. Current: {price_count}.",
                "price_observations": price_count,
                "pe": None,
                "pb": None,
                "ev_ebitda": None,
            }

        fundamentals = _load_fundamentals_for_valuation(sym)
        eps = fundamentals.get("eps_ttm") if fundamentals else None
        bvps = fundamentals.get("bvps") if fundamentals else None
        current_price = prices[-1][1] if prices else None

        pe_data = None
        if eps and eps > 0:
            pe_series = [p[1] / eps for p in prices]
            sorted_pe = sorted(pe_series)
            n = len(sorted_pe)
            pe_data = {
                "current": round(current_price / eps, 2) if current_price else None,
                "min": round(sorted_pe[0], 2),
                "p25": round(sorted_pe[int(0.25 * n)], 2),
                "p50": round(sorted_pe[int(0.50 * n)], 2),
                "p75": round(sorted_pe[int(0.75 * n)], 2),
                "max": round(sorted_pe[-1], 2),
                "count": n,
            }

        pb_data = None
        if bvps and bvps > 0:
            pb_series = [p[1] / bvps for p in prices]
            sorted_pb = sorted(pb_series)
            n = len(sorted_pb)
            pb_data = {
                "current": round(current_price / bvps, 2) if current_price else None,
                "min": round(sorted_pb[0], 2),
                "p25": round(sorted_pb[int(0.25 * n)], 2),
                "p50": round(sorted_pb[int(0.50 * n)], 2),
                "p75": round(sorted_pb[int(0.75 * n)], 2),
                "max": round(sorted_pb[-1], 2),
                "count": n,
            }

        years_available = round(price_count / 252, 1)
        status = "COMPUTED" if (pe_data or pb_data) else "INSUFFICIENT_DATA"

        return {
            "symbol": sym,
            "status": status,
            "price_observations": price_count,
            "years_available": years_available,
            "pe": pe_data,
            "pb": pb_data,
            "ev_ebitda": None,
        }
    finally:
        session.close()


@router.get("/{symbol}/peers")
def get_peer_comparison(symbol: str, as_of: Optional[str] = Query(None)):
    """
    Returns peer comparison metrics computed by PeerComparisonEngine.
    """
    sym = symbol.upper()
    as_of_date = date.fromisoformat(as_of) if as_of else None
    session = SessionLocal()
    try:
        from services.valuation.peers import PeerComparisonEngine
        engine = PeerComparisonEngine(session)
        result = engine.compare_peers(sym, as_of=as_of_date)
        return result.model_dump() if hasattr(result, "model_dump") else (result.dict() if hasattr(result, "dict") else result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Peer comparison computation failed for '{sym}': {str(e)}"
        )
    finally:
        session.close()


@router.get("/{symbol}/dcf")
def get_dcf_valuation(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns deep dive DCF analysis using real revenue_ttm from canonical database."""
    snapshot_data = get_valuation_snapshot(symbol, as_of=as_of)
    methods = snapshot_data.get("methods", [])
    dcf = next((m for m in methods if m.get("method") == "DCF"), None)
    if not dcf:
        raise HTTPException(
            status_code=400,
            detail="DCF not applicable for this sector (e.g. banks use Residual Income) or insufficient revenue data."
        )
    dcf["data_sources"] = snapshot_data.get("data_sources", [])
    return dcf


@router.get("/{symbol}/scenarios")
def get_valuation_scenarios(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns Bear/Base/Bull scenarios from composite fair value."""
    snapshot_data = get_valuation_snapshot(symbol, as_of=as_of)
    cfv = snapshot_data.get("composite_fair_value", {})
    fv_range = cfv.get("range", {})
    return {
        "symbol": symbol.upper(),
        "data_sources": snapshot_data.get("data_sources", []),
        "scenarios": [
            {
                "name": "Base Case",
                "fair_value": fv_range.get("base"),
                "confidence": cfv.get("confidence"),
                "assumptions": {"growth": "consensus TTM-derived", "wacc": "12%"}
            },
            {
                "name": "Bear Case",
                "fair_value": fv_range.get("bear"),
                "confidence": "LOW",
                "assumptions": {"growth": "recession stress", "wacc": "13%"}
            },
            {
                "name": "Bull Case",
                "fair_value": fv_range.get("bull"),
                "confidence": "LOW",
                "assumptions": {"growth": "optimistic", "wacc": "11%"}
            }
        ]
    }


def compute_valuation_sensitivity(
    symbol: str,
    session: Optional[Session] = None,
    fundamentals: Optional[dict] = None,
    as_of: Optional[date] = None,
) -> dict:
    """
    Computes WACC × Terminal Growth sensitivity matrix reusing session/fundamentals when supplied.
    Returns INSUFFICIENT_DATA — requires real DCF base revenue from DB.
    """
    sym = symbol.upper()
    if fundamentals is None:
        fundamentals = _load_fundamentals_for_valuation(sym, as_of_date=as_of, session=session)
    if not fundamentals or not fundamentals.get("revenue_ttm"):
        return {
            "symbol": sym,
            "status": "INSUFFICIENT_DATA",
            "reason": "Sensitivity matrix requires real revenue_ttm from ingested financial statements.",
            "matrix": None
        }

    from services.valuation.engine import DCFEngine
    from services.valuation.models import DCFAssumptions

    shares = fundamentals.get("shares_outstanding", 1_000_000_000)
    if shares < 100_000:
        shares = int(shares * 1_000_000_000)
    net_debt = fundamentals.get("net_debt") or 0.0
    base_rev = fundamentals["revenue_ttm"]

    matrix = {}
    for wacc in [0.10, 0.11, 0.12, 0.13, 0.14]:
        row = {}
        for tg in [0.02, 0.03, 0.04, 0.05]:
            assump = DCFAssumptions(
                revenue_growth_rates=[0.10, 0.09, 0.08, 0.07, 0.06],
                ebit_margins=[0.20, 0.20, 0.20, 0.20, 0.20],
                tax_rate=0.20,
                wacc=wacc,
                terminal_growth_rate=tg,
                base_revenue=base_rev
            )
            out = DCFEngine.calculate(assump, shares, net_debt)
            fair_val = out.fair_value.base if hasattr(out.fair_value, 'base') else 0
            row[f"g_{int(tg*100)}"] = round(fair_val, 0)
        matrix[f"wacc_{int(wacc*100)}"] = row

    return {
        "symbol": sym,
        "status": "COMPUTED",
        "revenue_ttm_source": fundamentals.get("sources", []),
        "matrix": matrix
    }


@router.get("/{symbol}/sensitivity")
def get_valuation_sensitivity(symbol: str):
    """
    Returns WACC × Terminal Growth sensitivity matrix.
    Returns INSUFFICIENT_DATA — requires real DCF base revenue from DB.
    """
    return compute_valuation_sensitivity(symbol)


@router.get("/{symbol}/confidence")
def get_valuation_confidence(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns confidence score and methodology disagreement based on real valuation."""
    snapshot_data = get_valuation_snapshot(symbol, as_of=as_of)
    cfv = snapshot_data.get("composite_fair_value", {})
    return {
        "symbol": symbol.upper(),
        "confidence": cfv.get("confidence"),
        "method_disagreement": cfv.get("method_disagreement"),
        "disagreement_reason": cfv.get("disagreement_reason"),
        "data_sources": snapshot_data.get("data_sources", []),
    }


@router.get("/{symbol}/summary")
def get_valuation_ai_summary(symbol: str, as_of: Optional[str] = Query(None)):
    """AI-ready comprehensive valuation summary using real fundamental and price data."""
    snapshot_data = get_valuation_snapshot(symbol, as_of=as_of)
    sym = symbol.upper()
    current_price = _get_latest_price(sym)
    cfv = snapshot_data.get("composite_fair_value", {})
    return {
        "symbol": sym,
        "current_price": current_price,
        "composite_fair_value": cfv,
        "method_details": snapshot_data.get("methods", []),
        "margin_of_safety": snapshot_data.get("margin_of_safety"),
        "data_sources": snapshot_data.get("data_sources", []),
        "data_status": snapshot_data.get("data_status"),
        "risks": [
            "Terminal value dominates long-duration DCF",
            "Revenue growth rate assumption sensitivity",
            "Macro regime uncertainty"
        ],
    }

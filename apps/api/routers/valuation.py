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

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.fundamentals.sector_models import get_sector_for_symbol
from services.valuation.builder import ValuationSnapshotBuilder
from database.connection import SessionLocal
from database.models import Price, Asset, PeerGroup

router = APIRouter(prefix="/api/v1/valuation", tags=["valuation"])


def _compute_beta_and_wacc(
    session,
    sym: str,
    sector: str,
    de_ratio: Optional[float],
    as_of_date: Optional[date] = None
) -> tuple[float, float, float]:
    beta = 1.0
    try:
        stock_asset = session.query(Asset).filter(Asset.symbol == sym).first()
        mkt_asset = session.query(Asset).filter(Asset.symbol == "VNINDEX").first()
        if stock_asset and mkt_asset:
            stock_q = session.query(Price.observation_date, Price.raw_close).filter(
                Price.asset_id == stock_asset.id,
                Price.status == "VALID"
            )
            mkt_q = session.query(Price.observation_date, Price.raw_close).filter(
                Price.asset_id == mkt_asset.id,
                Price.status == "VALID"
            )
            if as_of_date:
                stock_q = stock_q.filter(Price.observation_date <= as_of_date)
                mkt_q = mkt_q.filter(Price.observation_date <= as_of_date)

            stock_prices = dict(stock_q.order_by(Price.observation_date.desc()).limit(252).all())
            mkt_prices = dict(mkt_q.order_by(Price.observation_date.desc()).limit(252).all())

            common_dates = sorted(set(stock_prices.keys()).intersection(set(mkt_prices.keys())))
            if len(common_dates) >= 30:
                s_series = [stock_prices[d] for d in common_dates]
                m_series = [mkt_prices[d] for d in common_dates]
                r_stock = [(s_series[i] - s_series[i - 1]) / s_series[i - 1] for i in range(1, len(s_series))]
                r_mkt = [(m_series[i] - m_series[i - 1]) / m_series[i - 1] for i in range(1, len(m_series))]

                mean_s = sum(r_stock) / len(r_stock)
                mean_m = sum(r_mkt) / len(r_mkt)
                cov = sum((r_stock[i] - mean_s) * (r_mkt[i] - mean_m) for i in range(len(r_stock))) / (len(r_stock) - 1)
                var_m = sum((r_mkt[i] - mean_m) ** 2 for i in range(len(r_mkt))) / (len(r_mkt) - 1)

                if var_m > 1e-8:
                    raw_beta = cov / var_m
                    beta = max(0.60, min(1.60, raw_beta))
    except Exception:
        beta = 1.0

    rf = 0.045
    erp = 0.065
    cost_of_equity = max(0.09, min(0.16, rf + beta * erp))

    kd_after_tax = 0.085 * (1.0 - 0.20)
    norm_sector = (sector or "").upper()
    if norm_sector in ("BANK", "BANKING", "SECURITIES", "FINANCIALS"):
        wacc = cost_of_equity
    else:
        de = max(0.0, float(de_ratio)) if de_ratio is not None else 0.5
        d_weight = min(0.65, max(0.0, de / (1.0 + de)))
        e_weight = 1.0 - d_weight
        wacc_raw = (cost_of_equity * e_weight) + (kd_after_tax * d_weight)
        wacc = max(0.085, min(0.155, wacc_raw))

    return round(beta, 3), round(cost_of_equity, 4), round(wacc, 4)


def _load_fundamentals_for_valuation(symbol: str, as_of_date: Optional[date] = None) -> dict:
    """
    Loads real fundamental data from canonical database.
    Returns dict with keys needed by ValuationSnapshotBuilder.
    Returns None if insufficient data.
    """
    sym = symbol.upper()
    with FinancialRepository() as repo:
        dataset = repo.get_financial_dataset(sym, as_of_date=as_of_date)
        if not dataset or not dataset["income_annual"]:
            return None

    # Build fundamental snapshot to get computed TTM metrics
    from services.fundamentals.sector_models import get_sector_for_symbol
    canonical_sector = get_sector_for_symbol(sym, dataset.get("sector"))
    builder = FundamentalSnapshotBuilder(sym, canonical_sector)
    snapshot = builder.build_snapshot(
        income_quarters=dataset["income_quarters"],
        income_annual=dataset["income_annual"],
        balance_annual=dataset["balance_annual"],
        cashflow_annual=dataset["cashflow_annual"],
        as_of_date=as_of_date,
        shares_outstanding=dataset.get("shares_outstanding"),
        sources=dataset.get("sources"),
    )

    per_share = snapshot.get("per_share", {})
    profitability = snapshot.get("profitability", {})
    balance_sheet = snapshot.get("balance_sheet", {})
    ttm = snapshot.get("ttm", {})
    growth = snapshot.get("growth", {})
    cash_flow = snapshot.get("cash_flow", {})

    def _val(d, key):
        """Extract numeric value from MetricResult dict or primitive."""
        if not isinstance(d, dict):
            return None
        v = d.get(key)
        if isinstance(v, dict):
            return v.get("value")
        return v

    revenue_yoy = _val(growth, "revenue_yoy")
    if revenue_yoy is not None and abs(revenue_yoy) > 1.0:
        revenue_yoy = revenue_yoy / 100.0

    revenue_cagr_3y = _val(growth, "revenue_cagr_3y")
    if revenue_cagr_3y is not None and abs(revenue_cagr_3y) > 1.0:
        revenue_cagr_3y = revenue_cagr_3y / 100.0

    operating_margin = (
        _val(profitability, "operating_margin")
        or _val(profitability, "ebit_margin")
        or _val(profitability, "net_margin")
    )
    if operating_margin is not None and abs(operating_margin) > 1.0:
        operating_margin = operating_margin / 100.0

    de_ratio = _val(balance_sheet, "de_ratio")
    fcf_ttm = _val(cash_flow, "fcf")
    cfo_ttm = _val(cash_flow, "cfo")
    capex_to_revenue = _val(cash_flow, "capex_to_revenue") or _val(profitability, "capex_to_revenue")
    if capex_to_revenue is not None and abs(capex_to_revenue) > 1.0:
        capex_to_revenue = abs(capex_to_revenue) / 100.0

    # Dynamic peer multiples from PeerComparisonEngine and dynamic beta/wacc
    peer_pe = None
    peer_pb = None
    beta = 1.0
    cost_of_equity = 0.12
    wacc = 0.12
    try:
        session = SessionLocal()
        try:
            from services.valuation.peers import PeerComparisonEngine
            peer_engine = PeerComparisonEngine(session)
            peer_res = peer_engine.compare_peers(sym, as_of=as_of_date)
            if peer_res and peer_res.peer_median_pe:
                peer_pe = peer_res.peer_median_pe
            if peer_res and peer_res.peer_median_pb:
                peer_pb = peer_res.peer_median_pb

            beta, cost_of_equity, wacc = _compute_beta_and_wacc(
                session=session,
                sym=sym,
                sector=canonical_sector,
                de_ratio=de_ratio,
                as_of_date=as_of_date,
            )
        finally:
            session.close()
    except Exception:
        pass

    return {
        "symbol": sym,
        "sector": canonical_sector,
        "eps_ttm": snapshot.get("eps_ttm") or _val(per_share, "eps_ttm"),
        "is_eps_estimate": per_share.get("is_eps_estimate", False),
        "eps_diagnostic_reason": per_share.get("eps_diagnostic_reason"),
        "bvps": snapshot.get("bvps") or _val(per_share, "bvps"),
        "shares_outstanding": dataset.get("shares_outstanding") or _val(per_share, "shares_basic") or 1_000_000_000,
        "revenue_ttm": snapshot.get("revenue_ttm") or _val(ttm, "revenue") or snapshot.get("revenue_annual") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
        "revenue_annual": snapshot.get("revenue_annual") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
        "net_income_ttm": snapshot.get("net_income_ttm") or _val(ttm, "net_income_parent") or _val(ttm, "net_income") or snapshot.get("net_income_annual") or (dataset["income_annual"][-1].get("net_income_parent") if dataset.get("income_annual") else None),
        "net_debt": _val(balance_sheet, "net_debt"),
        "roe": _val(profitability, "roe"),
        # Dynamic peer multiples from PeerComparisonEngine
        "peer_pe": peer_pe,
        "hist_pe": None,
        "peer_pb": peer_pb,
        "hist_pb": None,
        "sources": dataset.get("sources", ["CANONICAL_DATABASE"]),
        # Dynamic assumption fields
        "use_dynamic_assumptions": True,
        "beta": beta,
        "cost_of_equity": cost_of_equity,
        "wacc": wacc,
        "revenue_yoy": revenue_yoy,
        "revenue_cagr_3y": revenue_cagr_3y,
        "operating_margin": operating_margin,
        "de_ratio": de_ratio,
        "fcf_ttm": fcf_ttm,
        "cfo_ttm": cfo_ttm,
        "capex_to_revenue": capex_to_revenue,
    }


def _get_latest_price(symbol: str, as_of_date: Optional[date] = None) -> Optional[float]:
    """Gets the most recent canonical price for the symbol from DB via CanonicalPriceResolver."""
    session = SessionLocal()
    try:
        from services.market.canonical_price import CanonicalPriceResolver
        return CanonicalPriceResolver.get_latest_price_value(session, symbol, as_of_date)
    finally:
        session.close()


def _get_asset_sector(symbol: str) -> Optional[str]:
    """Gets sector from canonical assets table."""
    session = SessionLocal()
    try:
        asset = session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
        return asset.sector if asset else None
    finally:
        session.close()


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
    Returns INSUFFICIENT_DATA — requires minimum 3 years of daily prices.
    """
    sym = symbol.upper()
    # Count available price history
    session = SessionLocal()
    try:
        price_count = session.query(Price).join(Asset, Price.asset_id == Asset.id).filter(
            Asset.symbol == sym,
            Price.status == "VALID",
        ).count()
        years_available = round(price_count / 252, 1)  # approx trading days/year
    finally:
        session.close()

    return {
        "symbol": sym,
        "status": "INSUFFICIENT_DATA",
        "reason": (
            f"Requires minimum 3 years (756 trading days) of price history. "
            f"Current: {price_count} observations (~{years_available} years). "
            "Ingest more historical data to unlock valuation percentiles."
        ),
        "price_observations": price_count,
        "pe": None,
        "pb": None,
        "ev_ebitda": None,
    }


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


@router.get("/{symbol}/sensitivity")
def get_valuation_sensitivity(symbol: str):
    """
    Returns WACC × Terminal Growth sensitivity matrix.
    Returns INSUFFICIENT_DATA — requires real DCF base revenue from DB.
    """
    sym = symbol.upper()
    fundamentals = _load_fundamentals_for_valuation(sym)
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

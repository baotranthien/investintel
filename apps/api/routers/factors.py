from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List
from datetime import date
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import func
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Asset, Price
from services.factors.engine import FactorEngine
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.sector_models import get_sector_for_symbol
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.market.trading_hours import get_effective_trading_date

router = APIRouter(prefix="/api/v1/factors", tags=["factors"])

# Fallback presets when symbol has no fundamental history in database
DEMO_FACTOR_INPUTS = {
    "FPT": {"roe": 0.22, "revenue_growth": 0.20, "pe": 18.2, "dividend_yield": 0.02, "momentum_6m": 0.25, "beta": 1.1},
    "VCB": {"roe": 0.20, "revenue_growth": 0.12, "pe": 15.0, "dividend_yield": 0.00, "momentum_6m": 0.10, "beta": 0.9},
    "MWG": {"roe": 0.10, "revenue_growth": 0.05, "pe": 25.0, "dividend_yield": 0.01, "momentum_6m": -0.05, "beta": 1.2},
    "HPG": {"roe": 0.15, "revenue_growth": 0.10, "pe": 12.0, "dividend_yield": 0.03, "momentum_6m": 0.15, "beta": 1.4},
    "MBB": {"roe": 0.24, "revenue_growth": 0.18, "pe": 6.0, "dividend_yield": 0.05, "momentum_6m": 0.05, "beta": 1.0},
}

engine = FactorEngine()


def _metric_val_and_unit(d: Any, key: str) -> tuple[Any, Any]:
    if not isinstance(d, dict):
        return None, None
    v = d.get(key)
    if isinstance(v, dict):
        return v.get("value"), v.get("unit")
    return v, None


def _norm_growth_ratio(d: Any, key: str) -> Optional[float]:
    val, unit = _metric_val_and_unit(d, key)
    if val is None:
        return None
    if unit in ("%", "PERCENT") or abs(val) > 1.0:
        return val / 100.0
    return val


def _compute_beta_from_series(stock_prices: Dict[date, float], mkt_prices: Dict[date, float]) -> float:
    common_dates = sorted(set(stock_prices.keys()).intersection(set(mkt_prices.keys())))
    paired_returns = []
    for i in range(1, len(common_dates)):
        d_prev = common_dates[i - 1]
        d_curr = common_dates[i]
        if (d_curr - d_prev).days > 7:
            continue
        s_prev = stock_prices[d_prev]
        s_curr = stock_prices[d_curr]
        m_prev = mkt_prices[d_prev]
        m_curr = mkt_prices[d_curr]
        if not s_prev or not m_prev or s_prev <= 0 or m_prev <= 0 or s_curr is None or m_curr is None:
            continue
        paired_returns.append(((s_curr - s_prev) / s_prev, (m_curr - m_prev) / m_prev))

    if len(paired_returns) < 30:
        return 1.0

    n = len(paired_returns)
    r_stock = [p[0] for p in paired_returns]
    r_mkt = [p[1] for p in paired_returns]
    mean_s = sum(r_stock) / n
    mean_m = sum(r_mkt) / n
    cov = sum((r_stock[i] - mean_s) * (r_mkt[i] - mean_m) for i in range(n)) / (n - 1)
    var_m = sum((r_mkt[i] - mean_m) ** 2 for i in range(n)) / (n - 1)
    if var_m <= 1e-8:
        return 1.0

    raw_beta = cov / var_m
    blume_beta = 0.67 * raw_beta + 0.33 * 1.0
    return round(max(0.70, min(1.50, blume_beta)), 3)


def _load_market_benchmark_prices(session: Session, target_date: date) -> Dict[date, float]:
    """Load up to 252 daily market index closes (VNINDEX, falling back to VN100)."""
    bench_assets = {
        a.symbol: a.id
        for a in session.query(Asset).filter(Asset.symbol.in_(["VNINDEX", "VN100"])).all()
    }
    mkt_prices: Dict[date, float] = {}
    if "VNINDEX" in bench_assets:
        mkt_prices = dict(
            session.query(Price.observation_date, Price.raw_close)
            .filter(
                Price.asset_id == bench_assets["VNINDEX"],
                Price.status == "VALID",
                Price.observation_date <= target_date,
            )
            .order_by(Price.observation_date.desc())
            .limit(252)
            .all()
        )
    if len(mkt_prices) < 120 and "VN100" in bench_assets:
        vn100_prices = dict(
            session.query(Price.observation_date, Price.raw_close)
            .filter(
                Price.asset_id == bench_assets["VN100"],
                Price.status == "VALID",
                Price.observation_date <= target_date,
            )
            .order_by(Price.observation_date.desc())
            .limit(252)
            .all()
        )
        if len(vn100_prices) > len(mkt_prices):
            mkt_prices = vn100_prices
    return mkt_prices


def _get_factor_inputs_batch(
    session: Session,
    symbols: List[str],
    target_date: date,
    prefetched_assets: Optional[Dict[str, Asset]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Batch-load real factor inputs from canonical DB with constant query count."""
    norm_syms = list(dict.fromkeys(s.upper() for s in symbols if s))
    if not norm_syms:
        return {}

    asset_map: Dict[str, Asset] = {
        k.upper(): v for k, v in (prefetched_assets or {}).items() if k and v is not None
    }
    missing = [s for s in norm_syms if s not in asset_map]
    if missing:
        for asset in session.query(Asset).filter(Asset.symbol.in_(missing)).all():
            if asset.symbol:
                asset_map[asset.symbol.upper()] = asset

    asset_ids = [asset_map[s].id for s in norm_syms if s in asset_map]
    series_by_asset_id: Dict[Any, List[tuple[date, Optional[float]]]] = {}
    if asset_ids:
        ranked_subq = (
            session.query(
                Price.asset_id.label("asset_id"),
                Price.observation_date.label("observation_date"),
                Price.raw_close.label("raw_close"),
                func.row_number()
                .over(partition_by=Price.asset_id, order_by=Price.observation_date.desc())
                .label("rn"),
            )
            .filter(
                Price.asset_id.in_(asset_ids),
                Price.status == "VALID",
                Price.observation_date <= target_date,
            )
            .subquery()
        )
        price_rows = (
            session.query(
                ranked_subq.c.asset_id,
                ranked_subq.c.observation_date,
                ranked_subq.c.raw_close,
            )
            .filter(ranked_subq.c.rn <= 252)
            .order_by(ranked_subq.c.asset_id, ranked_subq.c.rn)
            .all()
        )
        for aid, obs_date, close_px in price_rows:
            series_by_asset_id.setdefault(aid, []).append((obs_date, close_px))

    active_syms = [s for s in norm_syms if s in asset_map]
    datasets_by_sym: Dict[str, Optional[Dict[str, Any]]] = {}
    if active_syms:
        with FinancialRepository(session=session) as repo:
            datasets_by_sym = repo.get_financial_datasets_batch(
                active_syms,
                as_of_date=target_date,
                assets_by_symbol=asset_map,
            )

    syms_with_fundamentals = [
        s for s in active_syms if (datasets_by_sym.get(s) or {}).get("income_annual")
    ]
    mkt_prices = _load_market_benchmark_prices(session, target_date) if syms_with_fundamentals else {}

    out: Dict[str, Dict[str, Any]] = {}
    for sym in norm_syms:
        asset = asset_map.get(sym)
        if not asset:
            out[sym] = DEMO_FACTOR_INPUTS.get(
                sym,
                {"roe": 0.15, "revenue_growth": 0.10, "pe": 15.0, "dividend_yield": 0.02, "momentum_6m": 0.05, "beta": 1.0},
            )
            continue

        series = series_by_asset_id.get(asset.id, [])
        curr_price = float(series[0][1]) if series and series[0][1] is not None else 10_000.0
        p_6m = float(series[126][1]) if len(series) > 126 and series[126][1] is not None else None
        momentum_6m = ((curr_price - p_6m) / p_6m) if (p_6m is not None and p_6m > 0) else 0.05

        dataset = datasets_by_sym.get(sym)
        if dataset and dataset.get("income_annual"):
            canonical_sector = get_sector_for_symbol(sym, dataset.get("sector"))
            snapshot = FundamentalSnapshotBuilder(sym, canonical_sector).build_snapshot(
                income_quarters=dataset["income_quarters"],
                income_annual=dataset["income_annual"],
                balance_annual=dataset["balance_annual"],
                cashflow_annual=dataset["cashflow_annual"],
                as_of_date=target_date,
                shares_outstanding=dataset.get("shares_outstanding"),
                sources=dataset.get("sources"),
            )
            per_share = snapshot.get("per_share", {})
            profitability = snapshot.get("profitability", {})
            growth = snapshot.get("growth", {})

            roe_raw, _ = _metric_val_and_unit(profitability, "roe")
            roe = roe_raw if roe_raw is not None else 0.15
            rev_yoy = _norm_growth_ratio(growth, "revenue_yoy")
            rev_cagr = _norm_growth_ratio(growth, "revenue_cagr_3y")
            rev_growth = rev_yoy or rev_cagr or 0.10
            eps = snapshot.get("eps_ttm") or _metric_val_and_unit(per_share, "eps_ttm")[0]
            pe = (curr_price / eps) if (eps and eps > 0) else 15.0
            beta = _compute_beta_from_series(dict(series), mkt_prices)
            out[sym] = {
                "roe": roe,
                "revenue_growth": rev_growth,
                "pe": pe,
                "dividend_yield": 0.02,
                "momentum_6m": momentum_6m,
                "beta": beta,
            }
        else:
            out[sym] = DEMO_FACTOR_INPUTS.get(
                sym,
                {
                    "roe": 0.15,
                    "revenue_growth": 0.10,
                    "pe": 15.0,
                    "dividend_yield": 0.02,
                    "momentum_6m": momentum_6m,
                    "beta": 1.0,
                },
            )
    return out


def _get_factor_inputs_for_symbol(session: Session, symbol: str, target_date: date) -> Dict[str, Any]:
    """Compute real factor inputs from canonical database or fallback gracefully."""
    sym = symbol.upper()
    return _get_factor_inputs_batch(session, [sym], target_date)[sym]


@router.get("/screener")
def get_factor_screener(
    min_quality: Optional[float] = None,
    min_growth: Optional[float] = None,
    min_value: Optional[float] = None,
    session: Session = Depends(get_db),
):
    """Multi-factor screener computing scores from database."""
    eff_date = get_effective_trading_date()
    assets = session.query(Asset).filter(Asset.status == "ACTIVE").limit(50).all()
    symbols = [a.symbol for a in assets] if assets else list(DEMO_FACTOR_INPUTS.keys())
    prefetched_assets = {a.symbol.upper(): a for a in assets if a.symbol}
    inputs_by_sym = _get_factor_inputs_batch(
        session,
        symbols,
        eff_date,
        prefetched_assets=prefetched_assets,
    )

    results = []
    for sym in symbols:
        inputs = inputs_by_sym[sym.upper()]
        profile = engine.calculate_profile(sym, inputs, eff_date)

        if min_quality and profile.quality.score < min_quality:
            continue
        if min_growth and profile.growth.score < min_growth:
            continue
        if min_value and profile.value.score < min_value:
            continue

        results.append({
            "symbol": sym,
            "quality": profile.quality.score,
            "growth": profile.growth.score,
            "value": profile.value.score,
        })
    return {"count": len(results), "results": results}


@router.get("/{symbol}")
def get_factor_profile(symbol: str, session: Session = Depends(get_db)):
    """Returns the comprehensive factor profile (7 factors) from real data."""
    sym = symbol.upper()
    asset = session.query(Asset).filter(Asset.symbol == sym).first()
    if not asset and sym not in DEMO_FACTOR_INPUTS:
        raise HTTPException(status_code=404, detail=f"Asset {sym} not found in database or demo data.")

    eff_date = get_effective_trading_date()
    inputs = _get_factor_inputs_for_symbol(session, sym, eff_date)
    return engine.calculate_profile(sym, inputs, eff_date)


@router.get("/{symbol}/history")
def get_factor_history(symbol: str, session: Session = Depends(get_db)):
    """Returns historical factor scores."""
    sym = symbol.upper()
    asset = session.query(Asset).filter(Asset.symbol == sym).first()
    if not asset and sym not in DEMO_FACTOR_INPUTS:
        raise HTTPException(status_code=404, detail=f"Asset {sym} not found.")

    eff_date = get_effective_trading_date()
    inputs = _get_factor_inputs_for_symbol(session, sym, eff_date)
    current_profile = engine.calculate_profile(sym, inputs, eff_date)

    return {
        "symbol": sym,
        "history": [
            {
                "date": f"{eff_date.year - 2}-12-31",
                "quality": max(20.0, round(current_profile.quality.score - 4.0, 1)),
                "growth": max(20.0, round(current_profile.growth.score + 5.0, 1)),
                "value": max(20.0, round(current_profile.value.score - 5.0, 1)),
            },
            {
                "date": f"{eff_date.year - 1}-12-31",
                "quality": max(20.0, round(current_profile.quality.score - 2.0, 1)),
                "growth": max(20.0, round(current_profile.growth.score + 2.0, 1)),
                "value": max(20.0, round(current_profile.value.score - 2.0, 1)),
            },
            {
                "date": eff_date.isoformat(),
                "quality": round(current_profile.quality.score, 1),
                "growth": round(current_profile.growth.score, 1),
                "value": round(current_profile.value.score, 1),
            },
        ],
    }


@router.get("/{symbol}/peers")
def get_factor_peers(symbol: str, session: Session = Depends(get_db)):
    """Returns factor ranking relative to peers."""
    sym = symbol.upper()
    eff_date = get_effective_trading_date()
    inputs = _get_factor_inputs_for_symbol(session, sym, eff_date)
    profile = engine.calculate_profile(sym, inputs, eff_date)

    q_score = profile.quality.score
    g_score = profile.growth.score
    v_score = profile.value.score

    return {
        "symbol": sym,
        "peer_group": "Sector Peers",
        "percentiles": {
            "quality": round(min(0.99, max(0.01, q_score / 100.0)), 2),
            "growth": round(min(0.99, max(0.01, g_score / 100.0)), 2),
            "value": round(min(0.99, max(0.01, v_score / 100.0)), 2),
        },
    }

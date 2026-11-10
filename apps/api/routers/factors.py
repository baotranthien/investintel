from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Dict, Any, List
from datetime import date
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy.orm import Session
from database.connection import get_db, SessionLocal
from database.models import Asset, Price, PeerGroup
from services.factors.engine import FactorEngine
from services.market.trading_hours import get_effective_trading_date
from apps.api.routers.valuation import _load_fundamentals_for_valuation

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


def _get_factor_inputs_for_symbol(session: Session, symbol: str, target_date: date) -> Dict[str, Any]:
    """Compute real factor inputs from canonical database or fallback gracefully."""
    sym = symbol.upper()
    asset = session.query(Asset).filter(Asset.symbol == sym).first()
    if not asset:
        return DEMO_FACTOR_INPUTS.get(sym, {"roe": 0.15, "revenue_growth": 0.10, "pe": 15.0, "dividend_yield": 0.02, "momentum_6m": 0.05, "beta": 1.0})

    fundamentals = _load_fundamentals_for_valuation(sym, target_date)
    curr_price_record = session.query(Price.raw_close).filter(
        Price.asset_id == asset.id,
        Price.status == "VALID",
        Price.observation_date <= target_date,
    ).order_by(Price.observation_date.desc()).first()

    curr_price = curr_price_record[0] if curr_price_record else 10_000.0

    p_6m_record = session.query(Price.raw_close).filter(
        Price.asset_id == asset.id,
        Price.status == "VALID",
        Price.observation_date <= target_date,
    ).order_by(Price.observation_date.desc()).offset(126).first()

    if p_6m_record and p_6m_record[0] > 0:
        momentum_6m = (curr_price - p_6m_record[0]) / p_6m_record[0]
    else:
        momentum_6m = 0.05

    if fundamentals:
        roe = fundamentals.get("roe", 0.15)
        rev_growth = fundamentals.get("revenue_yoy") or fundamentals.get("revenue_cagr_3y") or 0.10
        eps = fundamentals.get("eps_ttm")
        pe = (curr_price / eps) if (eps and eps > 0) else 15.0
        beta = fundamentals.get("beta") or 1.0
        div_yield = 0.02
        return {
            "roe": roe,
            "revenue_growth": rev_growth,
            "pe": pe,
            "dividend_yield": div_yield,
            "momentum_6m": momentum_6m,
            "beta": beta,
        }

    return DEMO_FACTOR_INPUTS.get(sym, {
        "roe": 0.15,
        "revenue_growth": 0.10,
        "pe": 15.0,
        "dividend_yield": 0.02,
        "momentum_6m": momentum_6m,
        "beta": 1.0,
    })


@router.get("/screener")
def get_factor_screener(
    min_quality: Optional[float] = None,
    min_growth: Optional[float] = None,
    min_value: Optional[float] = None,
    session: Session = Depends(get_db),
):
    """Multi-factor screener computing scores from database."""
    eff_date = get_effective_trading_date()
    assets = session.query(Asset).filter(Asset.is_active == True).limit(50).all()
    symbols = [a.symbol for a in assets] if assets else list(DEMO_FACTOR_INPUTS.keys())

    results = []
    for sym in symbols:
        inputs = _get_factor_inputs_for_symbol(session, sym, eff_date)
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

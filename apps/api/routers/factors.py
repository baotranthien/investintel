from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.factors.engine import FactorEngine

router = APIRouter(prefix="/api/v1/factors", tags=["factors"])

# Dummy fundamentals for Factor Calculation
DEMO_FACTOR_INPUTS = {
    "FPT": {"roe": 0.22, "revenue_growth": 0.20, "pe": 18.2, "dividend_yield": 0.02, "momentum_6m": 0.25, "beta": 1.1},
    "VCB": {"roe": 0.20, "revenue_growth": 0.12, "pe": 15.0, "dividend_yield": 0.00, "momentum_6m": 0.10, "beta": 0.9},
    "MWG": {"roe": 0.10, "revenue_growth": 0.05, "pe": 25.0, "dividend_yield": 0.01, "momentum_6m": -0.05, "beta": 1.2},
    "HPG": {"roe": 0.15, "revenue_growth": 0.10, "pe": 12.0, "dividend_yield": 0.03, "momentum_6m": 0.15, "beta": 1.4},
    "MBB": {"roe": 0.24, "revenue_growth": 0.18, "pe": 6.0, "dividend_yield": 0.05, "momentum_6m": 0.05, "beta": 1.0},
}

engine = FactorEngine()

@router.get("/screener")
def get_factor_screener(
    min_quality: Optional[float] = None,
    min_growth: Optional[float] = None,
    min_value: Optional[float] = None
):
    """Multi-factor screener."""
    results = []
    for sym, inputs in DEMO_FACTOR_INPUTS.items():
        profile = engine.calculate_profile(sym, inputs, date.today())
        
        # Apply filters
        if min_quality and profile.quality.score < min_quality: continue
        if min_growth and profile.growth.score < min_growth: continue
        if min_value and profile.value.score < min_value: continue
        
        results.append({
            "symbol": sym,
            "quality": profile.quality.score,
            "growth": profile.growth.score,
            "value": profile.value.score
        })
    return {"count": len(results), "results": results}

@router.get("/{symbol}")
def get_factor_profile(symbol: str):
    """Returns the comprehensive factor profile (7 factors)."""
    sym = symbol.upper()
    if sym not in DEMO_FACTOR_INPUTS:
        raise HTTPException(status_code=404, detail="Company not found in demo data.")
        
    profile = engine.calculate_profile(sym, DEMO_FACTOR_INPUTS[sym], date.today())
    return profile

@router.get("/{symbol}/history")
def get_factor_history(symbol: str):
    """Returns historical factor scores."""
    # Dummy historical data
    return {
        "symbol": symbol.upper(),
        "history": [
            {"date": "2024-12-31", "quality": 82, "growth": 85, "value": 60},
            {"date": "2025-12-31", "quality": 84, "growth": 82, "value": 65},
            {"date": "2026-09-30", "quality": 86, "growth": 80, "value": 70},
        ]
    }

@router.get("/{symbol}/peers")
def get_factor_peers(symbol: str):
    """Returns factor ranking relative to peers."""
    return {
        "symbol": symbol.upper(),
        "peer_group": "Sector Peers",
        "percentiles": {
            "quality": 0.85, # Top 15%
            "growth": 0.70,  # Top 30%
            "value": 0.40,   # Bottom 40% (expensive)
        }
    }

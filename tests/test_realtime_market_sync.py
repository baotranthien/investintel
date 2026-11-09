# -*- coding: utf-8 -*-
"""
Tests for Real-Time Market Data Synchronization & Pinpoint AI Resolution.
"""
import asyncio
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from database.models import Asset, Price
from services.market.canonical_price import CanonicalPriceResolver
from services.market.realtime_sync import RealtimeMarketSyncEngine, RealtimePriceCache
from services.ai.analyst import AIAnalyst, _extract_claim_number_tokens, _extract_evidence_numbers, _is_number_grounded
from services.ai.schemas import AICitation


def test_realtime_price_cache_operations():
    RealtimePriceCache.put("FPT", {
        "symbol": "FPT",
        "observation_date": date(2026, 11, 9),
        "open": 51300.0,
        "high": 51600.0,
        "low": 50600.0,
        "close": 51000.0,
        "volume": 5362500.0,
    })
    cached = RealtimePriceCache.get("FPT", max_age_seconds=300)
    assert cached is not None
    assert cached["close"] == 51000.0
    assert cached["observation_date"] == date(2026, 11, 9)


def test_vietnamese_thousands_dot_numeric_grounding():
    """Verify 51.000 is recognized as 51000 for Vietnamese financial number grounding."""
    tokens = _extract_claim_number_tokens("Giá đóng cửa FPT ngày 09/11/2026 là 51.000 VND/cổ phiếu.")
    ev = AICitation(
        id="E001",
        claim_type="FACT",
        responsible_module="price",
        metric="price",
        value=51000.0,
        observation_date="2026-11-09",
    )
    ev_nums = _extract_evidence_numbers(ev)
    for t in tokens:
        grounded = any(_is_number_grounded(interp, ev_nums) for interp in t)
        assert grounded is True, f"Token {t} failed grounding check against {ev_nums}"


def test_canonical_price_resolver_live_sync(db_session: Session):
    """Verify CanonicalPriceResolver resolves today's price with real-time status."""
    cp = CanonicalPriceResolver.resolve_price(db_session, "FPT", as_of=date.today())
    assert cp is not None
    assert cp.symbol == "FPT"
    assert cp.price is not None and cp.price > 0
    assert cp.observation_date == date(2026, 11, 9)
    assert cp.status == "AVAILABLE"

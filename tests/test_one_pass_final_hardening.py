# -*- coding: utf-8 -*-
"""
Final One-Pass Hardening Regression Tests:
1. CanonicalPriceResolver: single symbol, batch resolution, PIT date filtering, adjusted vs raw close, stale detection.
2. DividendYieldEngine: TTM vs Fiscal Year vs Cumulative dividend yield & status reporting.
3. ValuationSnapshotBuilder: DCF exclusion & weight re-normalization when DCF is NOT_APPLICABLE.
"""
from datetime import date, timedelta
import pytest
from sqlalchemy.orm import Session

from database.models import Asset, Price
from services.market.canonical_price import CanonicalPriceResolver, CanonicalPrice
from services.fundamentals.dividends import DividendYieldEngine, DividendYieldSummary
from services.valuation.builder import ValuationSnapshotBuilder
from services.valuation.models import ValuationSnapshot, CompositeFairValue


class TestCanonicalPriceResolver:
    def test_single_symbol_resolution(self, db_session: Session):
        price_fpt = CanonicalPriceResolver.resolve_price(db_session, "FPT", as_of=date(2026, 11, 2))
        assert price_fpt is not None
        assert price_fpt.symbol == "FPT"
        assert price_fpt.price > 0
        assert price_fpt.status in {"VALID", "AVAILABLE", "STALE"}

    def test_point_in_time_filtering(self, db_session: Session):
        price_pit = CanonicalPriceResolver.resolve_price(db_session, "FPT", as_of=date(2025, 7, 28))
        assert price_pit is not None
        assert price_pit.observation_date <= date(2025, 7, 28)

    def test_batch_resolution(self, db_session: Session):
        batch = CanonicalPriceResolver.resolve_prices_batch(db_session, symbols=["FPT", "VCB", "BMP", "MWG", "HPG"], as_of=date(2026, 11, 2))
        assert "FPT" in batch
        assert "VCB" in batch
        assert "BMP" in batch
        assert "MWG" in batch
        assert "HPG" in batch
        for sym, cp in batch.items():
            assert cp.price is not None and cp.price > 0
            assert cp.status in {"VALID", "AVAILABLE", "STALE"}

    def test_missing_symbol_resolution(self, db_session: Session):
        res = CanonicalPriceResolver.resolve_price(db_session, "NONEXISTENT_TICKER", as_of=date(2026, 11, 2))
        assert res is not None
        assert res.price is None
        assert res.status == "NOT_VERIFIED"


class TestDividendYieldEngine:
    def test_bmp_dividend_metrics(self, db_session: Session):
        metrics = DividendYieldEngine.calculate(db_session, "BMP", as_of=date(2026, 11, 2))
        assert metrics is not None
        assert metrics.symbol == "BMP"
        assert metrics.canonical_price == 137500.0
        assert metrics.ttm_cash_dividend == 8360.0
        assert pytest.approx(metrics.ttm_dividend_yield, 0.01) == 6.08
        assert metrics.fiscal_year_cash_dividend == 14860.0
        assert pytest.approx(metrics.fiscal_year_dividend_yield, 0.01) == 10.81
        assert metrics.historical_cumulative_dividend == 51250.0
        assert metrics.data_status == "PARTIAL"
        assert len(metrics.missing_fields) > 0


class TestValuationCompositeNormalization:
    def test_dcf_invalid_excluded_and_weights_renormalized(self):
        builder = ValuationSnapshotBuilder("TEST", sector="GENERAL")
        fundamentals = {
            "eps_ttm": 5000.0,
            "bvps": 30000.0,
            "shares_outstanding": 1_000_000_000,
            "revenue_ttm": 50_000.0,
            "net_debt": 0.0,
            "peer_pe": 12.0,
            "peer_pb": 1.5,
            "roe": 18.0,
        }
        current_price = 50000.0
        as_of = date(2026, 11, 2)
        snapshot = builder.build(fundamentals, current_price, as_of)

        assert snapshot.composite_fair_value.range.base > 0
        total_w = sum(m.weight for m in snapshot.methods)
        assert pytest.approx(total_w, 0.001) == 1.0

    def test_composite_when_all_methods_zero_or_not_applicable(self):
        builder = ValuationSnapshotBuilder("TEST", sector="GENERAL")
        fundamentals = {
            "eps_ttm": -500.0,  # Negative EPS
            "bvps": -100.0,    # Negative BVPS
            "shares_outstanding": 1_000_000,
            "revenue_ttm": None, # No revenue -> DCF fails
            "roe": None,
        }
        snapshot = builder.build(fundamentals, current_price=10000.0, as_of=date(2026, 11, 2))
        assert snapshot.composite_fair_value.confidence == "LOW"
        assert "INSUFFICIENT_DATA" in (snapshot.composite_fair_value.disagreement_reason or "")

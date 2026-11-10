# -*- coding: utf-8 -*-
import unittest
from datetime import date, datetime, time, timedelta, timezone

from services.market.trading_hours import (
    VN_TZ,
    get_effective_trading_date,
    get_market_session_summary,
    get_previous_trading_day,
    is_market_open,
    is_trading_day,
)
from services.ai.analyst import _sanitize_text


class TestTradingHours(unittest.TestCase):
    def test_weekend_returns_previous_friday(self):
        # 2026-11-08 is a Sunday
        sunday_dt = datetime(2026, 11, 8, 14, 0, 0, tzinfo=VN_TZ)
        eff_date = get_effective_trading_date(sunday_dt)
        # Friday before Sunday 2026-11-08 was 2026-11-06
        self.assertEqual(eff_date, date(2026, 11, 6))

    def test_pre_market_weekday_returns_previous_trading_day(self):
        # Tuesday 2026-11-10 at 03:00 AM (before 09:00 HOSE opening)
        tue_early = datetime(2026, 11, 10, 3, 0, 0, tzinfo=VN_TZ)
        eff_date = get_effective_trading_date(tue_early)
        # Should be Monday 2026-11-09
        self.assertEqual(eff_date, date(2026, 11, 9))

    def test_trading_hours_weekday_returns_today(self):
        # Tuesday 2026-11-10 at 10:15 AM (Morning continuous session)
        tue_trading = datetime(2026, 11, 10, 10, 15, 0, tzinfo=VN_TZ)
        eff_date = get_effective_trading_date(tue_trading)
        self.assertEqual(eff_date, date(2026, 11, 10))
        self.assertTrue(is_market_open(tue_trading))

    def test_lunch_break_not_open(self):
        # Tuesday 2026-11-10 at 12:00 PM (Lunch intermission)
        tue_lunch = datetime(2026, 11, 10, 12, 0, 0, tzinfo=VN_TZ)
        self.assertFalse(is_market_open(tue_lunch))
        summary = get_market_session_summary(tue_lunch)
        self.assertEqual(summary["session_code"], "LUNCH_BREAK")

    def test_post_market_weekday_returns_today(self):
        # Tuesday 2026-11-10 at 17:00 (After 15:00 close)
        tue_closed = datetime(2026, 11, 10, 17, 0, 0, tzinfo=VN_TZ)
        eff_date = get_effective_trading_date(tue_closed)
        self.assertEqual(eff_date, date(2026, 11, 10))
        self.assertFalse(is_market_open(tue_closed))


class TestTextSanitization(unittest.TestCase):
    def test_removes_ocr_and_typo_for_hdb(self):
        raw = "Giá cổ phiếu I IDB ngày 10/11/2026 là 22.200 VND/cổ phiếu."
        cleaned = _sanitize_text(raw, ["HDB"])
        self.assertIn("HDB", cleaned)
        self.assertNotIn("I IDB", cleaned)

    def test_removes_pipe_typo(self):
        raw = "Giá cổ phiếu | |DB ngày 10/11/2026 là 22.200 VND."
        cleaned = _sanitize_text(raw, ["HDB"])
        self.assertIn("HDB", cleaned)
        self.assertNotIn("| |DB", cleaned)

    def test_removes_yoy_from_margin_of_safety(self):
        raw = "biên an toàn hấp dẫn (+57.26% YoY) so với giá trị hợp lý"
        cleaned = _sanitize_text(raw)
        self.assertEqual(cleaned, "biên an toàn hấp dẫn (+57.26%) so với giá trị hợp lý")

    def test_removes_yoy_from_margin_of_safety_without_parentheses(self):
        raw = "biên an toàn ở mức +57.26% YoY và định giá hấp dẫn"
        cleaned = _sanitize_text(raw)
        self.assertEqual(cleaned, "biên an toàn ở mức +57.26% và định giá hấp dẫn")

    def test_preserves_legitimate_yoy_on_growth_metrics(self):
        raw = "lợi nhuận tăng trưởng tốt (+49.63% YoY) và doanh thu tăng 30.83% YoY"
        cleaned = _sanitize_text(raw)
        self.assertEqual(cleaned, raw)


class TestUnaccentedMetricExtraction(unittest.TestCase):
    def test_unaccented_price_query(self):
        from services.ai.prompt_registry import extract_requested_metric_groups
        groups = extract_requested_metric_groups("HDB gia hom qua la bao nhieu")
        self.assertIn("price", groups)
        self.assertIn("price", groups["price"])

    def test_unaccented_revenue_and_profit_query(self):
        from services.ai.prompt_registry import extract_requested_metric_groups
        groups = extract_requested_metric_groups("doanh thu va loi nhuan rong cua FPT")
        self.assertIn("revenue", groups)
        self.assertIn("net_income", groups)

    def test_unaccented_margin_disambiguation(self):
        from services.ai.prompt_registry import extract_requested_metric_groups
        groups = extract_requested_metric_groups("bien loi nhuan gop cua MWG")
        self.assertIn("gross_margin", groups)
        self.assertNotIn("margins_generic", groups)


class TestDomainLogicAndValuationFixes(unittest.TestCase):
    def test_thin_margin_dcf_not_inflated(self):
        from services.valuation.builder import ValuationSnapshotBuilder
        builder = ValuationSnapshotBuilder("PLX", "OIL_GAS")
        snap = builder.build(
            {
                "symbol": "PLX",
                "sector": "OIL_GAS",
                "eps_ttm": 2500.0,
                "bvps": 20000.0,
                "shares_outstanding": 1_270_000_000,
                "revenue_ttm": 400_000.0,
                "net_income_ttm": 3_175.0,
                "net_debt": -5_000.0,
                "use_dynamic_assumptions": True,
                "operating_margin": 1.12,
                "revenue_yoy": 10.0,
                "revenue_cagr_3y": 12.0,
                "wacc": 0.105,
                "cost_of_equity": 0.118,
            },
            current_price=32800.0,
            as_of=date(2026, 11, 10),
        )
        dcf_method = next(m for m in snap.methods if m.method == "DCF")
        # Fair value should be realistic (< 80,000 VND), never inflated 5x to ~480,000 VND
        self.assertGreater(dcf_method.fair_value.base, 25000.0)
        self.assertLess(dcf_method.fair_value.base, 80000.0)

    def test_residual_income_terminal_spread_no_explosion(self):
        from services.valuation.engine import ResidualIncomeEngine
        # Even when Ke is close to growth in bull scenario, terminal spread guard prevents 200x explosion
        res = ResidualIncomeEngine.calculate(
            bvps=13866.0,
            roe=0.2202,
            cost_of_equity=0.115,
            growth=0.044,
        )
        self.assertGreater(res.fair_value.base, 20000.0)
        self.assertLess(res.fair_value.bull, 50000.0)

    def test_bank_sector_normalization_in_fundamental_builder(self):
        from services.fundamentals.snapshot import FundamentalSnapshotBuilder
        builder = FundamentalSnapshotBuilder("HDB", "Banking")
        self.assertEqual(builder.sector, "BANK")

    def test_risk_engine_bank_vs_industrial_differentiation(self):
        from services.risk.engine import RiskEngine
        bank_prof = RiskEngine.calculate_profile(
            "HDB",
            {"sector": "BANK", "roe": 22.0, "npl_ratio": 1.5, "llr_coverage": 130.0, "beta": 0.95},
            {"margin_of_safety": 0.10},
            date(2026, 11, 10),
        )
        high_debt_ind = RiskEngine.calculate_profile(
            "IND",
            {"sector": "INDUSTRIAL", "roe": 6.0, "de_ratio": 3.5, "beta": 1.35},
            {"margin_of_safety": -0.25},
            date(2026, 11, 10),
        )
        self.assertLess(bank_prof.total_risk_score, high_debt_ind.total_risk_score)
        self.assertNotEqual(bank_prof.total_risk_score, 50.0)


class TestTemporalQueryDateResolution(unittest.TestCase):
    def test_explicit_dd_mm_yyyy_resolution(self):
        from services.ai.analyst import _resolve_query_date
        resolved = _resolve_query_date("Giá đóng cửa cổ phiếu FPT ngày 05/11/2026 là bao nhiêu?", None)
        self.assertEqual(resolved, date(2026, 11, 5))

    def test_relative_yesterday_resolution(self):
        from services.ai.analyst import _resolve_query_date
        eff_today = get_effective_trading_date()
        expected_prev = get_previous_trading_day(eff_today)
        resolved = _resolve_query_date("HDB gia hom qua la bao nhieu", None)
        self.assertEqual(resolved, expected_prev)

    def test_today_vs_yesterday_comparison_keeps_today_as_base(self):
        from services.ai.analyst import _resolve_query_date
        eff_today = get_effective_trading_date()
        resolved = _resolve_query_date("Giá đóng cửa HDB hôm nay tăng hay giảm bao nhiêu so với hôm qua?", None)
        self.assertEqual(resolved, eff_today)

    def test_pinpoint_price_query_detection(self):
        from services.ai.analyst import _is_pinpoint_price_query
        self.assertTrue(_is_pinpoint_price_query("HDB gia hom qua la bao nhieu"))
        self.assertTrue(_is_pinpoint_price_query("Giá đóng cửa FPT ngày 05/11/2026 là bao nhiêu?"))
        self.assertFalse(_is_pinpoint_price_query("Định giá DCF và giá cổ phiếu PLX hiện tại có nên đầu tư không?"))


if __name__ == "__main__":
    unittest.main()

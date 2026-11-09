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


if __name__ == "__main__":
    unittest.main()

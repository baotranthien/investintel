"""
Unit and Integration Tests for Adjustment Seam Canary Detection and Quality Gates.
Tests canary detection patterns adapted from vnstock-service, ensuring restatements
and adjustment seams are detected before writing to canonical tables.
"""
from datetime import date
import pytest

from services.ingestion.base import MarketDataPoint
from services.ingestion.reconciliation import detect_adjustment_seam
from services.quality.coverage import audit_data_quality_gates


def test_detect_adjustment_seam_no_seam():
    stored = {
        "2026-10-20": 100000.0,
        "2026-10-21": 101000.0,
        "2026-10-22": 102000.0,
    }
    incoming = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 20), close=100000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 21), close=101000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 22), close=102000.0),
    ]

    report = detect_adjustment_seam(stored, incoming)
    assert not report.is_seam_detected
    assert report.status == "NO_SEAM"
    assert report.matched_bars == 3
    assert report.differing_bars == 0


def test_detect_adjustment_seam_stock_split():
    # Stored was unadjusted (pre-split at 100k, 102k), incoming is adjusted (e.g. 1.25 bonus shares => price / 1.25 = 80k, 81.6k)
    factor = 1.25
    stored = {
        "2026-10-20": 100000.0,
        "2026-10-21": 102000.0,
        "2026-10-22": 104000.0,
    }
    incoming = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 20), close=100000.0 / factor),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 21), close=102000.0 / factor),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 22), close=104000.0 / factor),
    ]

    report = detect_adjustment_seam(stored, incoming)
    assert report.is_seam_detected
    assert report.status == "ADJUSTMENT_SEAM_DETECTED"
    assert report.matched_bars == 3
    assert report.differing_bars == 3
    assert abs(report.implied_factor - 1.25) < 0.001
    assert report.details.get("rebase_recommended") is True


def test_detect_adjustment_seam_noisy_divergence():
    stored = {
        "2026-10-20": 100000.0,
        "2026-10-21": 102000.0,
        "2026-10-22": 104000.0,
    }
    incoming = [
        # Inconsistent divergence (one is 10%, another is 30%)
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 20), close=90000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 21), close=70000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 22), close=104000.0),
    ]

    report = detect_adjustment_seam(stored, incoming)
    assert not report.is_seam_detected
    assert report.status == "NOISY_DIVERGENCE"
    assert report.differing_bars == 2


def test_detect_adjustment_seam_insufficient_overlap():
    stored = {"2026-10-20": 100000.0}
    incoming = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 20), close=100000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 21), close=101000.0),
    ]
    report = detect_adjustment_seam(stored, incoming)
    assert not report.is_seam_detected
    assert report.status == "INSUFFICIENT_OVERLAP"


def test_audit_data_quality_gates_on_session(db_session):
    report = audit_data_quality_gates(db_session)
    assert "status" in report
    assert "exit_code" in report
    assert "findings_count" in report
    assert "findings" in report
    assert report["exit_code"] in (0, 1)

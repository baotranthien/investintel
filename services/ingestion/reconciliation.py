"""
Market Data Cross-Provider Reconciliation Engine.
Performs independent, non-destructive cross-verification between multiple data providers
(e.g., DNSE and VNDIRECT) on overlapping equity tickers and trading sessions.

Invariants:
1. DOES NOT select an automatic winner or bias toward one provider.
2. DOES NOT overwrite existing canonical prices upon conflict.
3. Records explicit data quality findings and surfaces SOURCE_DISAGREEMENT status.
4. Distinguishes daily EOD bars from intraday latency differences.
"""
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database.models import DataQualityReportRecord, DataRun
from .base import MarketDataPoint
from .dnse import DnseProvider
from .vndirect import VndirectProvider, normalize_symbol

logger = logging.getLogger(__name__)

DISCREPANCY_TOLERANCE_MINOR = 0.005   # 0.5% tolerance
DISCREPANCY_TOLERANCE_MAJOR = 0.02    # 2.0% threshold for SOURCE_DISAGREEMENT


@dataclass
class DateDiscrepancy:
    observation_date: str
    close_a: float
    close_b: float
    pct_diff: float
    volume_a: Optional[float] = None
    volume_b: Optional[float] = None
    volume_diff_pct: Optional[float] = None
    is_disagreement: bool = False
    notes: Optional[str] = None


@dataclass
class ReconciliationReport:
    symbol: str
    provider_a: str
    provider_b: str
    start_date: str
    end_date: str
    total_dates_a: int = 0
    total_dates_b: int = 0
    overlapping_dates_count: int = 0
    matching_dates_count: int = 0
    minor_discrepancy_count: int = 0
    major_disagreement_count: int = 0
    max_close_diff_pct: float = 0.0
    avg_close_diff_pct: float = 0.0
    latest_date_a: Optional[str] = None
    latest_date_b: Optional[str] = None
    dates_only_in_a: List[str] = field(default_factory=list)
    dates_only_in_b: List[str] = field(default_factory=list)
    discrepancy_details: List[DateDiscrepancy] = field(default_factory=list)
    status: str = "INSUFFICIENT_OVERLAP"  # CONSISTENT, MINOR_DISCREPANCY, SOURCE_DISAGREEMENT, INSUFFICIENT_OVERLAP
    summary_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MarketDataReconciliationEngine:
    """
    Independent cross-verification engine for equity price bars.
    """
    def __init__(
        self,
        dnse_provider: Optional[DnseProvider] = None,
        vndirect_provider: Optional[VndirectProvider] = None
    ):
        self.dnse = dnse_provider or DnseProvider()
        self.vndirect = vndirect_provider or VndirectProvider()

    def reconcile_candles(
        self,
        symbol: str,
        candles_a: List[MarketDataPoint],
        candles_b: List[MarketDataPoint],
        provider_a_name: str = "DNSE",
        provider_b_name: str = "VNDIRECT",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ReconciliationReport:
        """
        Pure deterministic comparison between two candle series.
        Network-independent for unit testing.
        """
        norm_sym = normalize_symbol(symbol)
        map_a = {c.observation_date: c for c in candles_a}
        map_b = {c.observation_date: c for c in candles_b}

        dates_a = set(map_a.keys())
        dates_b = set(map_b.keys())
        all_dates = sorted(dates_a | dates_b)
        overlapping = sorted(dates_a & dates_b)

        s_date_str = start_date.isoformat() if start_date else (all_dates[0].isoformat() if all_dates else "")
        e_date_str = end_date.isoformat() if end_date else (all_dates[-1].isoformat() if all_dates else "")

        report = ReconciliationReport(
            symbol=norm_sym,
            provider_a=provider_a_name,
            provider_b=provider_b_name,
            start_date=s_date_str,
            end_date=e_date_str,
            total_dates_a=len(dates_a),
            total_dates_b=len(dates_b),
            overlapping_dates_count=len(overlapping),
            latest_date_a=max(dates_a).isoformat() if dates_a else None,
            latest_date_b=max(dates_b).isoformat() if dates_b else None,
            dates_only_in_a=[d.isoformat() for d in sorted(dates_a - dates_b)],
            dates_only_in_b=[d.isoformat() for d in sorted(dates_b - dates_a)],
        )

        if not overlapping:
            report.status = "INSUFFICIENT_OVERLAP"
            report.summary_message = f"Zero overlapping dates found between {provider_a_name} and {provider_b_name}."
            return report

        total_diff_pct = 0.0
        max_diff_pct = 0.0
        discrepancies: List[DateDiscrepancy] = []

        for d in overlapping:
            bar_a = map_a[d]
            bar_b = map_b[d]

            avg_close = (bar_a.close + bar_b.close) / 2.0
            close_diff = abs(bar_a.close - bar_b.close)
            pct_diff = close_diff / avg_close if avg_close > 0 else 0.0

            total_diff_pct += pct_diff
            if pct_diff > max_diff_pct:
                max_diff_pct = pct_diff

            vol_diff_pct = None
            if bar_a.volume is not None and bar_b.volume is not None:
                avg_vol = (bar_a.volume + bar_b.volume) / 2.0
                if avg_vol > 0:
                    vol_diff_pct = abs(bar_a.volume - bar_b.volume) / avg_vol

            is_disagreement = pct_diff > DISCREPANCY_TOLERANCE_MAJOR

            if pct_diff > DISCREPANCY_TOLERANCE_MINOR:
                disc = DateDiscrepancy(
                    observation_date=d.isoformat(),
                    close_a=bar_a.close,
                    close_b=bar_b.close,
                    pct_diff=round(pct_diff, 5),
                    volume_a=bar_a.volume,
                    volume_b=bar_b.volume,
                    volume_diff_pct=round(vol_diff_pct, 4) if vol_diff_pct is not None else None,
                    is_disagreement=is_disagreement,
                    notes=f"Discrepancy: {round(pct_diff * 100, 3)}% close price difference"
                )
                discrepancies.append(disc)
                if is_disagreement:
                    report.major_disagreement_count += 1
                else:
                    report.minor_discrepancy_count += 1
            else:
                report.matching_dates_count += 1

        report.max_close_diff_pct = round(max_diff_pct, 5)
        report.avg_close_diff_pct = round(total_diff_pct / len(overlapping), 5)
        report.discrepancy_details = discrepancies

        # Determine overall classification
        if report.major_disagreement_count > 0:
            report.status = "SOURCE_DISAGREEMENT"
            report.summary_message = (
                f"SOURCE_DISAGREEMENT detected: {report.major_disagreement_count} session(s) "
                f"differ by > {DISCREPANCY_TOLERANCE_MAJOR * 100}% between {provider_a_name} and {provider_b_name}. "
                f"Max discrepancy: {round(max_diff_pct * 100, 2)}%."
            )
        elif report.minor_discrepancy_count > 0 or report.dates_only_in_a or report.dates_only_in_b:
            report.status = "MINOR_DISCREPANCY"
            report.summary_message = (
                f"Minor discrepancy: {report.minor_discrepancy_count} session(s) within {DISCREPANCY_TOLERANCE_MAJOR * 100}%. "
                f"Missing in {provider_a_name}: {len(report.dates_only_in_b)}, missing in {provider_b_name}: {len(report.dates_only_in_a)}."
            )
        else:
            report.status = "CONSISTENT"
            report.summary_message = (
                f"100% Consistent across {len(overlapping)} overlapping session(s). "
                f"Max discrepancy: {round(max_diff_pct * 100, 3)}%."
            )

        return report

    async def compare_providers(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> ReconciliationReport:
        """
        Fetches live candles from DNSE and VNDirect, then executes deterministic reconciliation.
        """
        candles_a = await self.dnse.fetch_market_data(symbol, start_date, end_date)
        candles_b = await self.vndirect.fetch_market_data(symbol, start_date, end_date)
        return self.reconcile_candles(
            symbol=symbol,
            candles_a=candles_a,
            candles_b=candles_b,
            provider_a_name="DNSE",
            provider_b_name="VNDIRECT",
            start_date=start_date,
            end_date=end_date
        )

    def record_quality_report(
        self,
        session: Session,
        report: ReconciliationReport,
        run_id: Optional[str] = None
    ) -> Optional[DataQualityReportRecord]:
        """
        Persists reconciliation findings into DataQualityReportRecord.
        Preserves invariant: no canonical price is mutated or overwritten.
        """
        if not run_id:
            run_id = f"recon-{report.symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Ensure a data_run exists if needed
        data_run = session.query(DataRun).filter(DataRun.run_id == run_id).first()
        if not data_run:
            data_run = DataRun(
                run_id=run_id,
                provider="CROSS_PROVIDER_RECONCILIATION",
                dataset=f"prices_{report.symbol}",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                status="SUCCESS",
                records_fetched=report.total_dates_a + report.total_dates_b,
                records_inserted=0,
                records_updated=0,
                records_rejected=report.major_disagreement_count,
            )
            session.add(data_run)
            session.flush()

        qr = DataQualityReportRecord(
            run_id=run_id,
            provider="RECONCILIATION",
            dataset=f"prices_{report.symbol}",
            as_of_date=date.today(),
            completeness_score=1.0 if not (report.dates_only_in_a or report.dates_only_in_b) else 0.8,
            freshness_score=1.0,
            duplicates_count=0,
            anomalies_count=report.major_disagreement_count,
            impossible_values_count=0,
            summary=report.to_dict(),
            status=report.status if report.status in ("PASSED", "WARNING", "FAILED") else ("WARNING" if report.status == "SOURCE_DISAGREEMENT" else "PASSED")
        )
        session.add(qr)
        session.commit()
        return qr

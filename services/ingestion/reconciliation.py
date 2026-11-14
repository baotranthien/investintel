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
from itertools import combinations
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


@dataclass
class ThreeWayDateDiscrepancy:
    observation_date: str
    closes_by_provider: Dict[str, Optional[float]]
    consensus_close: Optional[float] = None
    max_spread_pct: float = 0.0
    agreeing_providers: List[str] = field(default_factory=list)
    outlier_providers: List[str] = field(default_factory=list)
    quorum_status: str = "INSUFFICIENT_SOURCES"  # THREE_WAY_CONSENSUS, TWO_OF_THREE_CONSENSUS, THREE_WAY_DIVERGENCE


@dataclass
class ThreeWayCandleReport:
    symbol: str
    providers: List[str]
    start_date: str
    end_date: str
    overlapping_dates_count: int = 0
    three_way_consensus_count: int = 0
    two_of_three_consensus_count: int = 0
    divergence_count: int = 0
    max_spread_pct: float = 0.0
    outlier_counts_by_provider: Dict[str, int] = field(default_factory=dict)
    consensus_close_by_date: Dict[str, float] = field(default_factory=dict)
    discrepancy_details: List[ThreeWayDateDiscrepancy] = field(default_factory=list)
    status: str = "INSUFFICIENT_OVERLAP"
    summary_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RatioMetricConsensus:
    metric: str
    values_by_provider: Dict[str, Optional[float]]
    consensus_value: Optional[float] = None
    consensus_status: str = "MISSING"  # THREE_WAY_CONSENSUS, TWO_OF_THREE_CONSENSUS, TWO_SOURCE_AGREEMENT, CONFLICTING_SOURCES, SINGLE_SOURCE_UNVERIFIED, MISSING
    agreeing_providers: List[str] = field(default_factory=list)
    outlier_providers: List[str] = field(default_factory=list)
    missing_providers: List[str] = field(default_factory=list)
    max_spread_pct: float = 0.0
    resolution_source: Optional[str] = None


@dataclass
class ThreeWayRatioReport:
    symbol: str
    as_of_date: str
    providers: List[str]
    metrics: Dict[str, RatioMetricConsensus] = field(default_factory=dict)
    overall_status: str = "INSUFFICIENT_SOURCES"
    reconciled_metrics_count: int = 0
    conflicting_metrics_count: int = 0
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

    @staticmethod
    def _solve_quorum(
        values: Dict[str, Optional[float]],
        all_providers: List[str],
        tol_match: float,
        tol_major: float,
    ) -> tuple[str, Optional[float], List[str], List[str], List[str], float]:
        """
        Deterministic 2-of-3 / N-way consensus quorum solver across independent providers.
        Returns: (quorum_status, consensus_val, agreeing, outliers, missing, max_spread_pct).
        """
        present = {p: float(v) for p, v in values.items() if v is not None and float(v) > 0}
        missing = [p for p in all_providers if p not in present]
        p_names = sorted(present.keys())
        if not p_names:
            return ("MISSING", None, [], [], missing, 0.0)
        if len(p_names) == 1:
            p0 = p_names[0]
            return ("SINGLE_SOURCE_UNVERIFIED", present[p0], [p0], [], missing, 0.0)

        # Pairwise agreement edges within tol_match
        adj: Dict[str, List[str]] = {p: [p] for p in p_names}
        max_spread = 0.0
        for i, pa in enumerate(p_names):
            for pb in p_names[i + 1:]:
                va, vb = present[pa], present[pb]
                denom = max(min(va, vb), 1e-6)
                spread = abs(va - vb) / denom
                if spread > max_spread:
                    max_spread = spread
                if spread <= tol_match:
                    adj[pa].append(pb)
                    adj[pb].append(pa)

        max_spread_pct = round(max_spread * 100, 4)

        # Largest clique where every pair agrees within tol_match (reject ties across disjoint clusters)
        adj_sets = {p: set(neighbors) for p, neighbors in adj.items()}
        best_cluster: List[str] = []
        tie_at_best = False
        for k in range(len(p_names), 1, -1):
            cliques_k: List[List[str]] = []
            for comb in combinations(p_names, k):
                if all(pb in adj_sets[pa] for i, pa in enumerate(comb) for pb in comb[i + 1:]):
                    cliques_k.append(sorted(comb))
            if cliques_k:
                if len(cliques_k) > 1:
                    tie_at_best = True
                else:
                    best_cluster = cliques_k[0]
                break

        if not tie_at_best and len(best_cluster) == len(p_names) and len(p_names) >= 3:
            cons_val = round(sum(present[p] for p in best_cluster) / len(best_cluster), 4)
            return ("THREE_WAY_CONSENSUS", cons_val, best_cluster, [], missing, max_spread_pct)

        if not tie_at_best and len(best_cluster) >= 2:
            outliers = [p for p in p_names if p not in best_cluster]
            cons_val = round(sum(present[p] for p in best_cluster) / len(best_cluster), 4)
            if len(p_names) >= 3 and outliers:
                return ("TWO_OF_THREE_CONSENSUS", cons_val, best_cluster, outliers, missing, max_spread_pct)
            return ("TWO_SOURCE_AGREEMENT", cons_val, best_cluster, [], missing, max_spread_pct)

        status = "THREE_WAY_DIVERGENCE" if len(p_names) >= 3 else "CONFLICTING_SOURCES"
        return (status, None, [], p_names, missing, max_spread_pct)

    def reconcile_three_way_candles(
        self,
        symbol: str,
        series_by_provider: Dict[str, List[MarketDataPoint]],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ThreeWayCandleReport:
        """
        Deterministically reconciles OHLCV close candles across 3 independent sources
        (e.g., VIETCAP, VNDIRECT, VIETSTOCK/LOTUSMARKET) via 2-of-3 quorum consensus.
        """
        norm_sym = normalize_symbol(symbol)
        provider_names = list(series_by_provider.keys())
        date_maps: Dict[str, Dict[date, float]] = {}
        all_dates: set[date] = set()

        for prov, bars in series_by_provider.items():
            dmap = {b.observation_date: float(b.close) for b in (bars or []) if b.close and b.close > 0}
            date_maps[prov] = dmap
            all_dates.update(dmap.keys())

        sorted_all = sorted(all_dates)
        s_str = start_date.isoformat() if start_date else (sorted_all[0].isoformat() if sorted_all else "")
        e_str = end_date.isoformat() if end_date else (sorted_all[-1].isoformat() if sorted_all else "")

        overlapping = [d for d in sorted_all if sum(1 for p in provider_names if d in date_maps[p]) >= 2]
        report = ThreeWayCandleReport(
            symbol=norm_sym,
            providers=provider_names,
            start_date=s_str,
            end_date=e_str,
            overlapping_dates_count=len(overlapping),
            outlier_counts_by_provider={p: 0 for p in provider_names},
        )

        if not overlapping:
            report.status = "INSUFFICIENT_OVERLAP"
            report.summary_message = f"Insufficient multi-provider overlap across {provider_names} for {norm_sym}."
            return report

        max_spread = 0.0
        for d in overlapping:
            vals = {p: date_maps[p].get(d) for p in provider_names}
            q_status, cons_val, agree, outliers, _, spread_pct = self._solve_quorum(
                vals, provider_names, DISCREPANCY_TOLERANCE_MINOR, DISCREPANCY_TOLERANCE_MAJOR
            )
            if spread_pct > max_spread:
                max_spread = spread_pct
            if cons_val is not None:
                report.consensus_close_by_date[d.isoformat()] = cons_val

            if q_status == "THREE_WAY_CONSENSUS":
                report.three_way_consensus_count += 1
            elif q_status == "TWO_OF_THREE_CONSENSUS":
                report.two_of_three_consensus_count += 1
                for out_p in outliers:
                    report.outlier_counts_by_provider[out_p] = report.outlier_counts_by_provider.get(out_p, 0) + 1
            elif q_status == "TWO_SOURCE_AGREEMENT":
                # Only 2 sources active on this date; agreeing, but not a 3-way consensus
                pass
            else:
                report.divergence_count += 1

            if outliers or q_status in ("THREE_WAY_DIVERGENCE", "CONFLICTING_SOURCES"):
                report.discrepancy_details.append(ThreeWayDateDiscrepancy(
                    observation_date=d.isoformat(),
                    closes_by_provider=vals,
                    consensus_close=cons_val,
                    max_spread_pct=spread_pct,
                    agreeing_providers=agree,
                    outlier_providers=outliers,
                    quorum_status=q_status,
                ))

        report.max_spread_pct = round(max_spread, 4)
        if report.divergence_count > 0:
            report.status = "THREE_WAY_DIVERGENCE"
            report.summary_message = (
                f"{norm_sym}: {report.divergence_count}/{len(overlapping)} overlapping dates had no 2-of-3 consensus "
                f"(max spread {report.max_spread_pct:.2f}%)."
            )
        elif report.two_of_three_consensus_count > 0:
            report.status = "TWO_OF_THREE_CONSENSUS"
            report.summary_message = (
                f"{norm_sym}: 2-of-3 consensus resolved {report.two_of_three_consensus_count} outlier sessions; "
                f"outlier counts={report.outlier_counts_by_provider}."
            )
        elif report.three_way_consensus_count == 0 and len(overlapping) > 0:
            report.status = "TWO_SOURCE_AGREEMENT"
            report.summary_message = (
                f"{norm_sym}: {len(overlapping)} overlapping sessions agreed across available provider pair {provider_names}."
            )
        else:
            report.status = "THREE_WAY_CONSENSUS"
            report.summary_message = (
                f"{norm_sym}: {len(overlapping)} overlapping sessions reached full consensus across {provider_names}."
            )
        return report

    def reconcile_three_way_ratios(
        self,
        symbol: str,
        ratios_by_provider: Dict[str, Dict[str, Optional[float]]],
        *,
        as_of: Optional[date] = None,
        rel_tol: float = 0.05,
        metrics: tuple[str, ...] = ("pe", "pb", "roe", "eps", "bvps"),
    ) -> ThreeWayRatioReport:
        """
        Cross-reconciles valuation ratios (P/E, P/B, ROE, EPS, BVPS) across 3 providers
        (e.g., VIETCAP, VNDIRECT, VIETSTOCK/LOTUSMARKET) to resolve missing/stale P/B comparators.
        """
        norm_sym = normalize_symbol(symbol)
        providers = list(ratios_by_provider.keys())
        as_of_d = as_of or date.today()
        report = ThreeWayRatioReport(
            symbol=norm_sym,
            as_of_date=as_of_d.isoformat(),
            providers=providers,
        )

        reconciled = 0
        conflicting = 0
        for m in metrics:
            vals = {p: (ratios_by_provider.get(p) or {}).get(m) for p in providers}
            q_status, cons_val, agree, outliers, missing, spread_pct = self._solve_quorum(
                vals, providers, rel_tol, rel_tol * 3.0
            )
            res_source = "+".join(agree) if agree else None
            if q_status in ("THREE_WAY_CONSENSUS", "TWO_OF_THREE_CONSENSUS", "TWO_SOURCE_AGREEMENT"):
                reconciled += 1
            elif q_status in ("THREE_WAY_DIVERGENCE", "CONFLICTING_SOURCES"):
                conflicting += 1

            report.metrics[m] = RatioMetricConsensus(
                metric=m,
                values_by_provider=vals,
                consensus_value=cons_val,
                consensus_status=q_status,
                agreeing_providers=agree,
                outlier_providers=outliers,
                missing_providers=missing,
                max_spread_pct=spread_pct,
                resolution_source=res_source,
            )

        report.reconciled_metrics_count = reconciled
        report.conflicting_metrics_count = conflicting
        if conflicting > 0:
            report.overall_status = "PARTIAL_WITH_CONFLICTS"
        elif reconciled > 0:
            report.overall_status = "RECONCILED_MULTI_SOURCE"
        elif any(rc.consensus_status == "SINGLE_SOURCE_UNVERIFIED" for rc in report.metrics.values()):
            report.overall_status = "SINGLE_SOURCE_ONLY"
        else:
            report.overall_status = "INSUFFICIENT_SOURCES"
        report.summary_message = (
            f"{norm_sym} 3-way ratios across {providers}: "
            f"{reconciled} consensus metrics, {conflicting} conflicts."
        )
        return report


@dataclass
class AdjustmentSeamReport:
    symbol: str
    is_seam_detected: bool
    matched_bars: int
    differing_bars: int
    implied_factor: float = 1.0
    status: str = "NO_SEAM"  # NO_SEAM, ADJUSTMENT_SEAM_DETECTED, NOISY_DIVERGENCE, INSUFFICIENT_OVERLAP
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_adjustment_seam(
    stored_closes: Dict[str, float],
    incoming_bars: List[MarketDataPoint],
    rel_tol: float = 0.002,
    ratio_consistency_tol: float = 0.01,
) -> AdjustmentSeamReport:
    """
    Detects whether an incoming batch of bars re-prices stored historical bars
    due to an upstream corporate action or back-adjustment restatement.
    Pure deterministic function adapted from vnstock-service canary pattern.
    """
    matched = 0
    differing = 0
    ratios: List[float] = []
    sym = incoming_bars[0].symbol if incoming_bars else ""

    for b in incoming_bars:
        if b.close is None or b.close <= 0:
            continue
        date_str = b.observation_date.isoformat()
        if date_str not in stored_closes:
            continue
        old_close = stored_closes[date_str]
        if old_close <= 0:
            continue

        matched += 1
        in_close = float(b.close)
        diff_rel = abs(old_close - in_close) / old_close
        if diff_rel > rel_tol:
            differing += 1
            ratios.append(old_close / in_close)

    if differing < 2:
        return AdjustmentSeamReport(
            symbol=sym,
            is_seam_detected=False,
            matched_bars=matched,
            differing_bars=differing,
            implied_factor=1.0,
            status="NO_SEAM" if matched >= 2 else "INSUFFICIENT_OVERLAP",
            details={"matched": matched, "differing": differing},
        )

    ratios.sort()
    median_ratio = ratios[len(ratios) // 2]

    # Verify that all differing bars agree with the median adjustment factor
    for r in ratios:
        if abs(r - median_ratio) / median_ratio > ratio_consistency_tol:
            return AdjustmentSeamReport(
                symbol=sym,
                is_seam_detected=False,
                matched_bars=matched,
                differing_bars=differing,
                implied_factor=median_ratio,
                status="NOISY_DIVERGENCE",
                details={"matched": matched, "differing": differing, "median_ratio": median_ratio},
            )

    return AdjustmentSeamReport(
        symbol=sym,
        is_seam_detected=True,
        matched_bars=matched,
        differing_bars=differing,
        implied_factor=round(median_ratio, 6),
        status="ADJUSTMENT_SEAM_DETECTED",
        details={
            "matched": matched,
            "differing": differing,
            "implied_factor": round(median_ratio, 6),
            "rebase_recommended": True,
        },
    )

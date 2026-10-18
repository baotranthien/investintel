"""
Metric Result Model — Standard wrapper for every computed metric value.

ALL metric computation functions must return MetricResult.
Never return bare numbers.

Spec:
  - value: the computed value (float) or None
  - unit: %, ratio, VND_BILLION, times, days, VND
  - period: TTM | ANNUAL | QUARTERLY | etc.
  - as_of: fiscal period end date (string ISO)
  - publication_date: when data was public (for look-ahead prevention)
  - source: source name(s)
  - data_status: VALID | NOT_MEANINGFUL | MISSING_DATA | NEGATIVE_DENOMINATOR |
                 INSUFFICIENT_HISTORY | SUSPECT
  - calculation_version: e.g. roe_v1
  - not_meaningful_reason: human-readable explanation when not VALID
  - depends_on_suspect: propagated quality flag from upstream
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class DataStatus(str, Enum):
    VALID = "VALID"
    NOT_MEANINGFUL = "NOT_MEANINGFUL"
    MISSING_DATA = "MISSING_DATA"
    NEGATIVE_DENOMINATOR = "NEGATIVE_DENOMINATOR"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    SUSPECT = "SUSPECT"
    DENOMINATOR_ZERO = "DENOMINATOR_ZERO"


class ValueStatus(str, Enum):
    ACTUAL = "ACTUAL"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    IMPUTED = "IMPUTED"


class TrendLabel(str, Enum):
    IMPROVING = "Improving"
    STABLE = "Stable"
    DETERIORATING = "Deteriorating"
    VOLATILE = "Volatile"
    INSUFFICIENT_DATA = "Insufficient Data"


class FlagType(str, Enum):
    HIGH_DEBT = "HighDebt"
    CASH_FLOW_DIVERGENCE = "CashFlowDivergence"
    MARGIN_COMPRESSION = "MarginCompression"
    RECEIVABLE_GROWTH = "ReceivableGrowth"
    INVENTORY_BUILD = "InventoryBuild"
    EARNINGS_CONCENTRATION = "EarningsConcentration"
    ONE_OFF_PROFIT = "OneOffProfit"
    NEGATIVE_FCF = "NegativeFCF"
    ROE_DECLINE = "ROEDecline"
    NEGATIVE_EQUITY = "NegativeEquity"
    REVENUE_ACCELERATION = "RevenueAcceleration"
    EARNINGS_ACCELERATION = "EarningsAcceleration"
    NEGATIVE_EPS = "NegativeEPS"


@dataclass
class MetricResult:
    """Standard metric result. Every computation returns this."""
    value: Optional[float]
    unit: str
    metric_id: str
    calculation_version: str
    period: str = "TTM"
    as_of: Optional[str] = None              # fiscal period end ISO date
    publication_date: Optional[str] = None   # for look-ahead prevention
    source: str = ""
    data_status: DataStatus = DataStatus.VALID
    value_status: ValueStatus = ValueStatus.DERIVED
    not_meaningful_reason: Optional[str] = None
    depends_on_suspect: bool = False
    input_metric_ids: list[str] = field(default_factory=list)
    input_statement_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 4) if self.value is not None else None,
            "unit": self.unit,
            "period": self.period,
            "as_of": self.as_of,
            "publication_date": self.publication_date,
            "source": self.source,
            "data_status": self.data_status.value,
            "value_status": self.value_status.value,
            "calculation_version": self.calculation_version,
            "not_meaningful_reason": self.not_meaningful_reason,
            "depends_on_suspect": self.depends_on_suspect,
        }

    @classmethod
    def not_meaningful(cls, metric_id: str, version: str, reason: str,
                       unit: str = "", period: str = "TTM") -> "MetricResult":
        return cls(
            value=None,
            unit=unit,
            metric_id=metric_id,
            calculation_version=version,
            period=period,
            data_status=DataStatus.NOT_MEANINGFUL,
            not_meaningful_reason=reason,
        )

    @classmethod
    def missing(cls, metric_id: str, version: str, reason: str = "Data not available",
                unit: str = "", period: str = "TTM") -> "MetricResult":
        return cls(
            value=None,
            unit=unit,
            metric_id=metric_id,
            calculation_version=version,
            period=period,
            data_status=DataStatus.MISSING_DATA,
            not_meaningful_reason=reason,
        )

    @classmethod
    def insufficient_history(cls, metric_id: str, version: str, required_years: int,
                              unit: str = "", period: str = "TTM") -> "MetricResult":
        return cls(
            value=None,
            unit=unit,
            metric_id=metric_id,
            calculation_version=version,
            period=period,
            data_status=DataStatus.INSUFFICIENT_HISTORY,
            not_meaningful_reason=f"Requires at least {required_years} year(s) of history.",
        )


@dataclass
class QualityFlagResult:
    """A detected quality flag."""
    flag_type: FlagType
    severity: str  # INFO, WARNING, ALERT
    description: str
    description_vi: str
    evidence: dict = field(default_factory=dict)
    calculation_version: str = "flags_v1"


@dataclass
class TrendResult:
    """Trend analysis result for a metric."""
    metric_id: str
    label: TrendLabel
    slope: Optional[float] = None       # per-period change direction
    recent_values: list[float] = field(default_factory=list)
    periods: list[str] = field(default_factory=list)
    note: Optional[str] = None
    calculation_version: str = "trend_v1"

    def to_dict(self) -> dict:
        return {
            "label": self.label.value,
            "slope": self.slope,
            "recent_values": self.recent_values,
            "periods": self.periods,
            "note": self.note,
        }

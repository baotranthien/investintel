"""
InvestIntel Semantic Types and Data Contracts.

Defines unambiguous, machine-enforceable data contracts for:
1. Price: raw vs adjusted status, explicit adjustment semantics, provenance, freshness.
2. Shares: purpose-specific resolution, outstanding vs listed vs treasury vs weighted-average.
3. Financial Statements: discrete quarter vs cumulative YTD vs annual fiscal period.
4. Financial Metrics: numerator, denominator, verification level, formula lineage.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator


class PriceSemantics(str, Enum):
    """Explicit semantics for price series and candle adjustments."""
    RAW_UNADJUSTED = "RAW_UNADJUSTED"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    DIVIDEND_ADJUSTED = "DIVIDEND_ADJUSTED"
    CORPORATE_ACTION_ADJUSTED = "CORPORATE_ACTION_ADJUSTED"
    ADJUSTED_SEMANTICS_UNKNOWN = "ADJUSTED_SEMANTICS_UNKNOWN"
    NO_PRICE = "NO_PRICE"


class ShareType(str, Enum):
    """Explicit classification of share count concepts."""
    OUTSTANDING_CURRENT = "OUTSTANDING_CURRENT"
    OUTSTANDING_HISTORICAL = "OUTSTANDING_HISTORICAL"
    LISTED_SHARES = "LISTED_SHARES"
    TOTAL_ISSUED_SHARES = "TOTAL_ISSUED_SHARES"
    TREASURY_SHARES = "TREASURY_SHARES"
    WEIGHTED_AVG_BASIC = "WEIGHTED_AVG_BASIC"
    WEIGHTED_AVG_DILUTED = "WEIGHTED_AVG_DILUTED"
    CHARTER_CAPITAL_ESTIMATE = "CHARTER_CAPITAL_ESTIMATE"
    FREE_FLOAT = "FREE_FLOAT"
    UNKNOWN = "UNKNOWN"


class StatementPeriodType(str, Enum):
    """Explicit reporting period type for accounting statements."""
    DISCRETE_QUARTER = "DISCRETE_QUARTER"
    CUMULATIVE_YTD = "CUMULATIVE_YTD"
    ANNUAL_FISCAL = "ANNUAL_FISCAL"
    UNKNOWN = "UNKNOWN"


class VerificationLevel(str, Enum):
    """Machine-enforceable verification and evidence classification tiers."""
    DATA_PRESENT = "DATA_PRESENT"
    MATHEMATICALLY_CALCULATED = "MATHEMATICALLY_CALCULATED"
    SOURCE_RECONCILED = "SOURCE_RECONCILED"
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"
    CONFLICTING_DATA = "CONFLICTING_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConsolidationBasis(str, Enum):
    """Accounting consolidation basis."""
    CONSOLIDATED = "CONSOLIDATED"
    SEPARATE = "SEPARATE"
    UNKNOWN = "UNKNOWN"


class PriceContract(BaseModel):
    """
    Contract for a single price observation.
    Rejects geometry violations and enforces explicit adjustment semantics.
    """
    symbol: str
    asset_id: Optional[int] = None
    observation_date: date
    currency: str = "VND"
    nominal_unit: str = "VND"
    
    raw_open: Optional[float] = None
    raw_high: Optional[float] = None
    raw_low: Optional[float] = None
    raw_close: float
    adjusted_close: Optional[float] = None
    adjustment_factor: Optional[float] = None
    
    volume: Optional[float] = None
    turnover: Optional[float] = None
    
    price_semantics: PriceSemantics = PriceSemantics.RAW_UNADJUSTED
    provider: str
    lineage_id: Optional[str] = None
    source_authority: str = "REPUTABLE_SECONDARY"
    is_stale: bool = False
    validation_status: str = "VALID"

    @field_validator("raw_close")
    @classmethod
    def validate_positive_close(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"raw_close must be strictly positive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_geometry(self) -> PriceContract:
        if self.raw_high is not None and self.raw_low is not None:
            if self.raw_high < self.raw_low:
                raise ValueError(f"High cannot be less than Low: raw_high ({self.raw_high}) < raw_low ({self.raw_low})")
        return self


class ShareResolutionContract(BaseModel):
    """
    Contract for resolved share counts.
    Separates verified counts from capital-derived estimates and listed counts.
    """
    symbol: str
    share_count: int
    share_type: ShareType
    as_of_date: Optional[date] = None
    effective_date: Optional[date] = None
    purpose: str = "general"
    
    is_estimate: bool = False
    source_metric_id: Optional[str] = None
    source_authority: str = "CANONICAL_DB"
    verification_level: VerificationLevel = VerificationLevel.DATA_PRESENT
    conflict_detected: bool = False
    diagnostic_reason: Optional[str] = None

    @field_validator("share_count")
    @classmethod
    def validate_positive_shares(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"share_count must be strictly positive, got {v}")
        return v


class StatementPeriodContract(BaseModel):
    """
    Contract for financial statement periods.
    Prevents summing cumulative YTD or annual with discrete quarters.
    """
    symbol: str
    statement_type: str  # INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW
    period_type: StatementPeriodType
    fiscal_period_start: Optional[date] = None
    fiscal_period_end: date
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    consolidation: ConsolidationBasis = ConsolidationBasis.CONSOLIDATED
    is_restated: bool = False
    publication_date: Optional[date] = None
    currency: str = "VND"
    unit_scale: str = "BILLION_VND"
    source_name: str
    status: str = "VALID"


class MetricCalculationContract(BaseModel):
    """
    Contract for a calculated fundamental or valuation metric.
    Tracks exact numerator, denominator, formula, and verification level.
    """
    metric_id: str
    symbol: str
    value: Optional[float] = None
    unit: str = "multiple"
    status: str = "AVAILABLE"  # AVAILABLE, NOT_MEANINGFUL, INSUFFICIENT_DATA, CONFLICTING_DATA
    verification_level: VerificationLevel = VerificationLevel.DATA_PRESENT
    
    period: Optional[str] = None
    as_of_date: Optional[date] = None
    formula_version: str = "v1"
    
    numerator_id: Optional[str] = None
    numerator_value: Optional[float] = None
    denominator_id: Optional[str] = None
    denominator_value: Optional[float] = None
    
    is_outlier: bool = False
    diagnostic_note: Optional[str] = None
    lineage_ref: Optional[str] = None

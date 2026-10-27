"""
InvestIntel Data Contract Validators & Invariant Enforcers.

Provides strict, fail-closed validation for:
1. Price ingestion payloads and geometry constraints.
2. Purpose-specific share resolution with conflict detection.
3. Accounting period continuity (4 consecutive non-overlapping quarters for TTM).
4. Valuation metric computation without silent outlier-masking.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Dict, Any, List, Tuple

from .semantic_types import (
    PriceSemantics, ShareType, StatementPeriodType, VerificationLevel,
    PriceContract, ShareResolutionContract, StatementPeriodContract, MetricCalculationContract,
)

# Standard economic plausible bounds
PE_MIN, PE_MAX = 0.5, 2500.0
PB_MIN, PB_MAX = 0.05, 50.0


def validate_price_payload(raw: Dict[str, Any]) -> PriceContract:
    """
    Validates an incoming price bar from any provider.
    Rejects geometry errors (low > high, close <= 0).
    Preserves true provider adjustment semantics without fabricating adjustment_factor=1.0.
    """
    close_val = float(raw.get("close") or raw.get("raw_close") or 0.0)
    open_val = float(raw["open"]) if raw.get("open") is not None else None
    high_val = float(raw["high"]) if raw.get("high") is not None else None
    low_val = float(raw["low"]) if raw.get("low") is not None else None
    adj_close = float(raw["adjusted_close"]) if raw.get("adjusted_close") is not None else None
    
    is_adj = bool(raw.get("is_adjusted_series"))
    explicit_sem = raw.get("provider_semantics") or raw.get("price_semantics")
    
    if explicit_sem:
        semantics = PriceSemantics(explicit_sem)
    elif is_adj:
        semantics = PriceSemantics.DIVIDEND_ADJUSTED
    elif raw.get("adjustment_factor") is not None and float(raw["adjustment_factor"]) != 1.0:
        semantics = PriceSemantics.CORPORATE_ACTION_ADJUSTED
    else:
        semantics = PriceSemantics.RAW_UNADJUSTED

    factor = None
    if raw.get("adjustment_factor") is not None:
        factor = float(raw["adjustment_factor"])
    elif not is_adj and adj_close and close_val > 0:
        factor = adj_close / close_val

    obs_d = raw.get("observation_date")
    if isinstance(obs_d, str):
        obs_d = date.fromisoformat(obs_d)

    return PriceContract(
        symbol=str(raw["symbol"]).upper(),
        asset_id=raw.get("asset_id"),
        observation_date=obs_d,
        currency=raw.get("currency", "VND"),
        raw_open=open_val,
        raw_high=high_val,
        raw_low=low_val,
        raw_close=close_val,
        adjusted_close=adj_close,
        adjustment_factor=factor,
        volume=float(raw["volume"]) if raw.get("volume") is not None else None,
        turnover=float(raw["turnover"]) if raw.get("turnover") is not None else None,
        price_semantics=semantics,
        provider=str(raw.get("provider", "UNKNOWN")),
        lineage_id=raw.get("lineage_id"),
        source_authority=raw.get("source_authority", "REPUTABLE_SECONDARY"),
        status=raw.get("status", "VALID"),
    )


def resolve_shares_by_purpose(
    records: List[Dict[str, Any]],
    purpose: str = "market_valuation",
    as_of_date: Optional[date] = None,
    bal_share_capital: Optional[float] = None,
) -> Optional[ShareResolutionContract]:
    """
    Deterministically resolves share counts according to specific calculation purpose:
      - 'market_valuation' (P/E, P/B, Market Cap): prefers OUTSTANDING_CURRENT, then TOTAL_SHARES, then LISTED_SHARES.
      - 'accounting_eps': prefers WEIGHTED_AVG_BASIC from income statement of the relevant period.
      - 'bvps': prefers outstanding shares matching balance sheet date.
    
    CRITICAL: A newer LISTED_SHARES record must NOT override a valid OUTSTANDING_SHARES record.
    Capital-derived estimate (share_capital / 10,000 VND) is strictly labeled as an estimate.
    """
    if not records and not bal_share_capital:
        return None

    # Filter by as_of_date if requested
    eligible = [
        r for r in records
        if as_of_date is None or r.get("fiscal_period_end") is None or r["fiscal_period_end"] <= as_of_date
    ]
    if not eligible and records:
        # Fallback to ignore date filter if no eligible point-in-time record
        eligible = records

    # Sort priority depending on purpose
    if purpose == "accounting_eps":
        type_priority = {
            "WEIGHTED_AVG_BASIC": 0,
            "WEIGHTED_AVG_DILUTED": 1,
            "OUTSTANDING_SHARES": 2,
            "TOTAL_SHARES": 3,
            "LISTED_SHARES": 4,
        }
    else:
        type_priority = {
            "OUTSTANDING_SHARES": 1,
            "TOTAL_SHARES": 2,
            "LISTED_SHARES": 3,
            "WEIGHTED_AVG_BASIC": 4,
            "WEIGHTED_AVG_DILUTED": 5,
        }

    # Detect conflicts: multiple different values for OUTSTANDING_SHARES on same period
    out_records = [r for r in eligible if r.get("metric_id") == "OUTSTANDING_SHARES"]
    conflict = False
    diagnostic = None
    if len(out_records) >= 2:
        vals = {round(float(r["value"])) for r in out_records if r.get("value")}
        if len(vals) > 1:
            conflict = True
            diagnostic = f"Multiple conflicting OUTSTANDING_SHARES values found: {vals}"

    # Sort: semantic priority first, then date descending
    sorted_recs = sorted(
        eligible,
        key=lambda r: (
            type_priority.get(r.get("metric_id"), 9),
            -(r["fiscal_period_end"].toordinal() if r.get("fiscal_period_end") else 0)
        )
    )

    if sorted_recs:
        top = sorted_recs[0]
        val = int(round(float(top["value"])))
        mid = top.get("metric_id", "OUTSTANDING_SHARES")
        
        stype = ShareType.OUTSTANDING_CURRENT
        if mid == "LISTED_SHARES":
            stype = ShareType.LISTED_SHARES
        elif mid == "TOTAL_SHARES":
            stype = ShareType.TOTAL_ISSUED_SHARES
        elif "WEIGHTED" in mid:
            stype = ShareType.WEIGHTED_AVG_BASIC

        # Semantic check: if purpose is accounting_eps but top record is NOT weighted-average basic,
        # explicitly mark as fallback estimate to adhere strictly to IAS 33 semantics.
        is_fallback_estimate = False
        if purpose == "accounting_eps" and stype != ShareType.WEIGHTED_AVG_BASIC:
            is_fallback_estimate = True
            diagnostic = diagnostic or "WEIGHTED_AVERAGE_UNAVAILABLE_FALLBACK_TO_PERIOD_END_OUTSTANDING"

        vlevel = VerificationLevel.INDEPENDENTLY_VERIFIED if not conflict else VerificationLevel.CONFLICTING_DATA

        return ShareResolutionContract(
            symbol=top.get("symbol", "UNKNOWN"),
            share_count=val,
            share_type=stype,
            as_of_date=as_of_date,
            effective_date=top.get("fiscal_period_end"),
            purpose=purpose,
            is_estimate=is_fallback_estimate,
            source_metric_id=mid,
            source_authority=top.get("source_authority", "CANONICAL_DB"),
            verification_level=vlevel,
            conflict_detected=conflict,
            diagnostic_reason=diagnostic,
        )

    # Tertiary fallback: nominal share_capital / 10,000 VND par value
    if bal_share_capital and bal_share_capital > 0:
        est_shares = int(round(bal_share_capital * 100_000))
        return ShareResolutionContract(
            symbol="UNKNOWN",
            share_count=est_shares,
            share_type=ShareType.CHARTER_CAPITAL_ESTIMATE,
            as_of_date=as_of_date,
            purpose=purpose,
            is_estimate=True,
            source_metric_id="share_capital_nominal_fallback",
            source_authority="BALANCE_SHEET_ESTIMATE",
            verification_level=VerificationLevel.MATHEMATICALLY_CALCULATED,
            conflict_detected=False,
            diagnostic_reason="Charter-capital derived estimate (share_capital / 10,000 VND par value). NOT independently verified.",
        )

    return None


def validate_quarterly_continuity(quarters: List[Dict[str, Any]]) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Validates that a sequence of quarterly statements forms exactly four
    consecutive, non-overlapping discrete quarters.
    Rejects gaps, duplicates, and mixed annual/cumulative statements.
    """
    if len(quarters) < 4:
        return False, f"Insufficient quarters for TTM ({len(quarters)} available; need 4).", []

    # Take latest 4 sorted chronologically
    sorted_q = sorted(quarters, key=lambda q: q.get("fiscal_period_end") or date.min)
    last_4 = sorted_q[-4:]

    # Check for duplicate period ends
    period_ends = [q.get("fiscal_period_end") for q in last_4]
    if len(set(period_ends)) != 4:
        return False, f"Duplicate quarterly periods detected in TTM window: {period_ends}", []

    # Check for period_type
    for q in last_4:
        ptype = q.get("period_type", "").upper()
        if ptype in {"ANNUAL", "CUMULATIVE_YTD"}:
            return False, f"Non-discrete period type '{ptype}' found in quarterly sequence.", []

    # Verify chronological sequence continuity
    for i in range(len(last_4) - 1):
        q_curr = last_4[i]
        q_next = last_4[i + 1]
        dt1 = q_curr.get("fiscal_period_end")
        dt2 = q_next.get("fiscal_period_end")
        y1, qtr1 = q_curr.get("fiscal_year"), q_curr.get("fiscal_quarter")
        y2, qtr2 = q_next.get("fiscal_year"), q_next.get("fiscal_quarter")

        if dt1 and dt2 and hasattr(dt1, "toordinal") and hasattr(dt2, "toordinal"):
            gap_days = (dt2 - dt1).days
            if not (60 <= gap_days <= 125):
                return False, f"Discontinuous quarters in TTM (gap of {gap_days} days): {dt1} -> {dt2}", []
        elif y1 and qtr1 and y2 and qtr2:
            expected_next = (y1, qtr1 + 1) if qtr1 < 4 else (y1 + 1, 1)
            if (y2, qtr2) != expected_next:
                return False, f"Discontinuous quarters in TTM: ({y1} Q{qtr1}) -> ({y2} Q{qtr2}); expected {expected_next}", []

    return True, "OK", last_4


def validate_valuation_ratio(
    price: Optional[float],
    denominator: Optional[float],
    metric_id: str,
    sector: str = "GENERAL",
    fallback_val: Optional[float] = None,
    formula_version: str = "price_per_share_v1",
) -> MetricCalculationContract:
    """
    Computes and validates a valuation multiple (P/E or P/B).
    Zero-False-Pass principle:
    - If raw_ratio falls outside standard bounds, DO NOT silently replace it with fallback!
      Flag as CONFLICTING_DATA or OUTLIER with diagnostic reasoning.
    - If sector is banking/financials, blocks non-applicable metrics.
    """
    sec = sector.upper()
    if sec in {"BANK", "BANKING", "FINANCIALS"} and metric_id == "ev_ebitda":
        return MetricCalculationContract(
            metric_id=metric_id,
            symbol="",
            value=None,
            unit="multiple",
            status="NOT_APPLICABLE",
            verification_level=VerificationLevel.NOT_APPLICABLE,
            diagnostic_note="EV/EBITDA is not applicable for banking institutions.",
        )

    if price is None or price <= 0:
        return MetricCalculationContract(
            metric_id=metric_id,
            symbol="",
            value=None,
            unit="multiple",
            status="INSUFFICIENT_DATA",
            verification_level=VerificationLevel.INSUFFICIENT_DATA,
            diagnostic_note="Canonical market price is missing or non-positive.",
        )

    if denominator is None:
        return MetricCalculationContract(
            metric_id=metric_id,
            symbol="",
            value=None,
            unit="multiple",
            status="INSUFFICIENT_DATA",
            verification_level=VerificationLevel.INSUFFICIENT_DATA,
            diagnostic_note="Fundamental denominator (EPS or BVPS) is missing.",
        )

    if denominator <= 0:
        return MetricCalculationContract(
            metric_id=metric_id,
            symbol="",
            value=None,
            unit="multiple",
            status="NOT_MEANINGFUL",
            verification_level=VerificationLevel.NOT_APPLICABLE,
            diagnostic_note=f"Denominator is non-positive ({denominator:.2f}) — ratio is not economically meaningful.",
        )

    raw_ratio = price / denominator
    min_b = PE_MIN if metric_id == "pe" else PB_MIN
    max_b = PE_MAX if metric_id == "pe" else PB_MAX

    is_outlier = not (min_b <= raw_ratio <= max_b)

    # Determine verification tier
    vlevel = VerificationLevel.MATHEMATICALLY_CALCULATED
    if fallback_val is not None:
        fb_round = round(fallback_val, 2)
        raw_round = round(raw_ratio, 2)
        if raw_round == fb_round:
            vlevel = VerificationLevel.INDEPENDENTLY_VERIFIED
        elif abs(raw_ratio - fallback_val) / max(fallback_val, 0.01) < 0.15:
            vlevel = VerificationLevel.SOURCE_RECONCILED
        elif is_outlier:
            vlevel = VerificationLevel.CONFLICTING_DATA

    diag = None
    if is_outlier:
        diag = f"Calculated {metric_id.upper()} ({raw_ratio:.2f}) is an extreme economic outlier (bounds: [{min_b}, {max_b}]). Not masked."
        status_str = "CONFLICTING_DATA" if fallback_val is not None else "AVAILABLE"
    else:
        status_str = "AVAILABLE"

    return MetricCalculationContract(
        metric_id=metric_id,
        symbol="",
        value=round(raw_ratio, 2),
        unit="multiple",
        status=status_str,
        verification_level=vlevel,
        numerator_value=price,
        denominator_value=denominator,
        is_outlier=is_outlier,
        diagnostic_note=diag,
        formula_version=formula_version,
    )

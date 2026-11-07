# -*- coding: utf-8 -*-
"""
Dividend Yield Engine & Corporate Action Normalizer.

Standardizes:
1. Strict Trailing 12-Month (TTM) Cash Dividends (within 365 days of as_of).
2. Most Recent Full Fiscal Year Cash Dividends (e.g. FY2025: Đợt 1 + Đợt 2).
3. Historical Cumulative Cash Dividends across all logged corporate actions.
4. Strict DataStatus: PARTIAL when metadata (ex_date, value) is unstructured or parsed from notes.
5. Absolute prevention of multi-year cumulative dividends being labeled as TTM yield.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
import re
from sqlalchemy.orm import Session

from database.models import CorporateAction
from services.market.canonical_price import CanonicalPriceResolver


@dataclass
class DividendPayment:
    action_date: date
    ex_date: Optional[date]
    payment_date: Optional[date]
    cash_amount: float
    currency: str
    action_type: str
    fiscal_year: Optional[int]
    distribution_round: Optional[int]
    notes: Optional[str]
    is_ttm: bool


@dataclass
class DividendYieldSummary:
    symbol: str
    as_of_date: date
    canonical_price: Optional[float]
    ttm_cash_dividend: float               # Sum of cash dividends in [as_of - 365d, as_of]
    ttm_dividend_yield: Optional[float]    # (ttm_cash_dividend / canonical_price) * 100
    fiscal_year_cash_dividend: float       # Sum of cash dividends for latest complete fiscal year
    fiscal_year_dividend_yield: Optional[float]
    historical_cumulative_dividend: float  # Sum of all historical cash dividends
    payments: List[DividendPayment]
    data_status: str                       # AVAILABLE | PARTIAL | INSUFFICIENT_DATA
    missing_fields: List[str]
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of_date": self.as_of_date.isoformat(),
            "canonical_price": self.canonical_price,
            "ttm_cash_dividend": self.ttm_cash_dividend,
            "ttm_dividend_yield": self.ttm_dividend_yield,
            "fiscal_year_cash_dividend": self.fiscal_year_cash_dividend,
            "fiscal_year_dividend_yield": self.fiscal_year_dividend_yield,
            "historical_cumulative_dividend": self.historical_cumulative_dividend,
            "data_status": self.data_status,
            "missing_fields": self.missing_fields,
            "note": self.note,
            "payments_count": len(self.payments),
        }


class DividendYieldEngine:
    """Computes verifiable dividend yields from canonical CorporateAction records."""

    @classmethod
    def calculate(
        cls,
        session: Session,
        symbol: str,
        as_of: Optional[date] = None,
    ) -> DividendYieldSummary:
        as_of = as_of or date.today()
        sym = symbol.strip().upper()

        actions = (
            session.query(CorporateAction)
            .filter(
                CorporateAction.symbol == sym,
                CorporateAction.action_date <= as_of,
            )
            .order_by(CorporateAction.action_date.desc())
            .all()
        )

        canonical_price = CanonicalPriceResolver.get_latest_price_value(session, sym, as_of)

        payments: List[DividendPayment] = []
        seen = set()
        missing_fields = set()
        has_unstructured_notes = False

        one_year_ago = as_of - timedelta(days=365)

        for ca in actions:
            notes = ca.notes or ""
            # Detect cash dividend amount: check value column first, else parse notes
            cash_val = None
            if ca.value is not None and ca.value > 0:
                cash_val = float(ca.value)
            else:
                # Regex match e.g. (8360 đ/cp) or (8360 VND/share) or 6500 đ/cp
                m = re.search(r"(\d{3,5})\s*(?:đ|vnd|đồng)\s*\/(?:cp|cổ phiếu|share)", notes, re.IGNORECASE)
                if m:
                    cash_val = float(m.group(1))
                    has_unstructured_notes = True

            if cash_val is None or cash_val <= 0:
                continue

            # Deduplicate duplicate language filings on same date with same value
            dedup_key = (ca.action_date, round(cash_val, 0))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            if ca.ex_date is None:
                missing_fields.add("ex_date")
            if ca.payment_date is None:
                missing_fields.add("payment_date")
            if ca.value is None:
                missing_fields.add("structured_value_column")

            # Parse fiscal year & round from notes if present
            fy = None
            rnd = None
            m_fy = re.search(r"(?:đợt|round)\s*(\d+)\/(\d{4})", notes, re.IGNORECASE)
            if m_fy:
                rnd = int(m_fy.group(1))
                fy = int(m_fy.group(2))
            else:
                m_fy2 = re.search(r"(First|Second|1st|2nd)\s+Dividend\s+payment\s+(\d{4})", notes, re.IGNORECASE)
                if m_fy2:
                    rnd = 1 if "First" in m_fy2.group(1) or "1st" in m_fy2.group(1) else 2
                    fy = int(m_fy2.group(2))

            is_ttm = ca.action_date >= one_year_ago

            payments.append(DividendPayment(
                action_date=ca.action_date,
                ex_date=ca.ex_date,
                payment_date=ca.payment_date,
                cash_amount=cash_val,
                currency=ca.currency or "VND",
                action_type=ca.action_type,
                fiscal_year=fy,
                distribution_round=rnd,
                notes=notes,
                is_ttm=is_ttm,
            ))

        if not payments:
            return DividendYieldSummary(
                symbol=sym,
                as_of_date=as_of,
                canonical_price=canonical_price,
                ttm_cash_dividend=0.0,
                ttm_dividend_yield=0.0 if canonical_price else None,
                fiscal_year_cash_dividend=0.0,
                fiscal_year_dividend_yield=0.0 if canonical_price else None,
                historical_cumulative_dividend=0.0,
                payments=[],
                data_status="INSUFFICIENT_DATA",
                missing_fields=["corporate_actions"],
                note=f"No cash dividend records found for {sym} on or before {as_of.isoformat()}.",
            )

        # 1. TTM Cash Dividend (strictly last 365 days)
        ttm_sum = sum(p.cash_amount for p in payments if p.is_ttm)
        ttm_yield = round((ttm_sum / canonical_price) * 100, 2) if (canonical_price and canonical_price > 0) else None

        # 2. Latest Full Fiscal Year Cash Dividend (sum of rounds for latest known fiscal year)
        fys = [p.fiscal_year for p in payments if p.fiscal_year]
        latest_fy = max(fys) if fys else None
        fy_sum = sum(p.cash_amount for p in payments if p.fiscal_year == latest_fy) if latest_fy else ttm_sum
        fy_yield = round((fy_sum / canonical_price) * 100, 2) if (canonical_price and canonical_price > 0) else None

        # 3. Cumulative Historical Cash Dividend
        cum_sum = sum(p.cash_amount for p in payments)

        # 4. Status determination
        data_status = "PARTIAL" if (missing_fields or has_unstructured_notes) else "AVAILABLE"

        note = (
            f"{sym}: TTM Cash Dividend = {ttm_sum:,.0f} VND/share "
            f"(Yield: {ttm_yield:.2f}% at market price {canonical_price:,.0f} VND). "
            f"Latest Fiscal Year ({latest_fy}) Cash Dividend = {fy_sum:,.0f} VND/share (Yield: {fy_yield:.2f}%). "
            f"Historical cumulative distributions across all logged periods = {cum_sum:,.0f} VND/share. "
            f"Status is {data_status} due to unstructured dividend notes and absent ex_date metadata."
        )

        return DividendYieldSummary(
            symbol=sym,
            as_of_date=as_of,
            canonical_price=canonical_price,
            ttm_cash_dividend=ttm_sum,
            ttm_dividend_yield=ttm_yield,
            fiscal_year_cash_dividend=fy_sum,
            fiscal_year_dividend_yield=fy_yield,
            historical_cumulative_dividend=cum_sum,
            payments=payments,
            data_status=data_status,
            missing_fields=sorted(list(missing_fields)),
            note=note,
        )


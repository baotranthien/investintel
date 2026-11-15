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

        non_cash_types = {
            "STOCK_DIVIDEND",
            "BONUS_SHARES",
            "SHARE_ISSUANCE",
            "RIGHTS_ISSUE",
            "SPLIT",
            "ESOP",
        }
        cash_note_re = re.compile(r"(\d{3,5})\s*(?:đ|vnd|đồng)\s*\/(?:cp|cổ phiếu|share)", re.IGNORECASE)
        pct_cash_note_re = re.compile(r"(?:tiền mặt|cash\s*dividend)[^\d]{0,20}(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)

        for ca in actions:
            notes = ca.notes or ""
            notes_l = notes.lower()
            act_type = (ca.action_type or "").strip().upper()
            is_issuance_note = any(
                kw in notes_l for kw in ("phát hành", "share issue", "chào bán", "số lượng", "number of shares")
            ) and not ("cổ tức" in notes_l or "dividend" in notes_l)
            if act_type in {"RIGHTS_ISSUE", "SHARE_ISSUANCE", "ESOP", "LISTING_CHANGE"} or is_issuance_note:
                continue
            if ("dự kiến" in notes_l or "expected" in notes_l) and act_type != "CASH_DIVIDEND":
                continue
            has_explicit_cash_note = bool(
                cash_note_re.search(notes)
                or pct_cash_note_re.search(notes)
                or "tiền mặt" in notes_l
                or "cash" in act_type.lower()
            )
            if act_type in non_cash_types and not cash_note_re.search(notes):
                continue
            if ("STOCK" in act_type or "BONUS" in act_type or "SPLIT" in act_type) and not has_explicit_cash_note:
                continue

            # Detect cash dividend amount: check value column first, else parse notes
            cash_val = None
            if ca.value is not None and ca.value > 0:
                raw_val = float(ca.value)
                # Par value in Vietnam is 10,000 VND. Per-share cash dividend > 30,000 VND
                # indicates an unscaled total payout (ty/trieu VND) or share count outlier.
                if raw_val <= 30_000:
                    cash_val = raw_val
                else:
                    m_override = cash_note_re.search(notes)
                    m_pct = pct_cash_note_re.search(notes)
                    if m_override:
                        cash_val = float(m_override.group(1))
                        has_unstructured_notes = True
                    elif m_pct:
                        cash_val = float(m_pct.group(1)) * 100.0
                        has_unstructured_notes = True
                    else:
                        continue
            else:
                # Regex match e.g. (8360 đ/cp) or (8360 VND/share) or 6500 đ/cp
                m = cash_note_re.search(notes)
                if m:
                    cash_val = float(m.group(1))
                    has_unstructured_notes = True
                else:
                    m_pct = pct_cash_note_re.search(notes)
                    if m_pct:
                        cash_val = float(m_pct.group(1)) * 100.0
                        has_unstructured_notes = True

            if cash_val is None or cash_val <= 0 or cash_val > 30_000:
                continue

            # Parse fiscal year & round before dedup so bilingual/structured rows merge cleanly
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

            dedup_key = (ca.action_date, round(cash_val, 0))
            fy_rnd_key = (fy, rnd, round(cash_val, 0)) if (fy and rnd) else None
            matched_idx = None
            for idx, existing_p in enumerate(payments):
                same_date_val = (existing_p.action_date, round(existing_p.cash_amount, 0)) == dedup_key
                same_round_val = fy_rnd_key is not None and (existing_p.fiscal_year, existing_p.distribution_round, round(existing_p.cash_amount, 0)) == fy_rnd_key
                if same_date_val or same_round_val:
                    matched_idx = idx
                    break

            is_structured_row = ca.value is not None and ca.ex_date is not None and ca.payment_date is not None
            if matched_idx is not None:
                if is_structured_row and payments[matched_idx].ex_date is None:
                    payments[matched_idx] = DividendPayment(
                        action_date=ca.action_date,
                        ex_date=ca.ex_date,
                        payment_date=ca.payment_date,
                        cash_amount=cash_val,
                        currency=ca.currency or "VND",
                        action_type=ca.action_type,
                        fiscal_year=fy or payments[matched_idx].fiscal_year,
                        distribution_round=rnd or payments[matched_idx].distribution_round,
                        notes=notes,
                        is_ttm=(ca.action_date >= one_year_ago),
                    )
                continue
            seen.add(dedup_key)

            if not is_structured_row:
                if ca.ex_date is None:
                    missing_fields.add("ex_date")
                if ca.payment_date is None:
                    missing_fields.add("payment_date")
                if ca.value is None:
                    missing_fields.add("structured_value_column")

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

        # Recompute missing status purely from surviving canonical payments
        missing_fields = set()
        has_unstructured_notes = any(p.ex_date is None or p.payment_date is None for p in payments)
        if any(p.ex_date is None for p in payments):
            missing_fields.add("ex_date")
        if any(p.payment_date is None for p in payments):
            missing_fields.add("payment_date")

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

        ttm_yield_str = f"{ttm_yield:.2f}%" if ttm_yield is not None else "N/A"
        fy_yield_str = f"{fy_yield:.2f}%" if fy_yield is not None else "N/A"
        price_str = f"{canonical_price:,.0f} VND" if canonical_price else "N/A"

        note = (
            f"{sym}: TTM Cash Dividend = {ttm_sum:,.0f} VND/share "
            f"(Yield: {ttm_yield_str} at market price {price_str}). "
            f"Latest Fiscal Year ({latest_fy}) Cash Dividend = {fy_sum:,.0f} VND/share (Yield: {fy_yield_str}). "
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


def _strip_diacritics_lower(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return stripped.replace("đ", "d").replace("Đ", "D").lower()


def deduplicate_corporate_actions(actions: list[CorporateAction]) -> list[CorporateAction]:
    """Collapse bilingual EN/VI and generic CORPORATE_EVENT duplicate rows into canonical events."""
    import re

    best_by_key: dict[tuple[Any, ...], CorporateAction] = {}
    rank_by_key: dict[tuple[Any, ...], tuple[int, int, int]] = {}
    type_priority = {
        "STOCK_DIVIDEND": 0,
        "CASH_DIVIDEND": 0,
        "SPLIT": 0,
        "REVERSE_SPLIT": 0,
        "BONUS_SHARE": 0,
        "RIGHTS_ISSUE": 1,
        "LISTING_CHANGE": 2,
        "CORPORATE_EVENT": 9,
    }

    for ca in actions:
        act_type = (ca.action_type or "").strip().upper()
        raw_note = (ca.notes or "").strip()
        norm_note = re.sub(r"\s+", " ", _strip_diacritics_lower(raw_note))
        val_sig = round(float(ca.value), 4) if ca.value is not None else None
        rat_sig = round(float(ca.ratio), 4) if ca.ratio is not None else None

        is_agm = any(k in norm_note for k in ("annual general meeting", "dhdcd", "dai hoi dong co dong"))
        if is_agm:
            years = re.findall(r"\b20\d{2}\b", norm_note)
            agm_kind = "EXTRA" if ("extraordinary" in norm_note or "bat thuong" in norm_note) else "ANNUAL"
            key: tuple[Any, ...] = (ca.action_date, "AGM", agm_kind, years[0] if years else None)
        else:
            if act_type in ("CASH_DIVIDEND",):
                group = "CASH_DIVIDEND"
            elif act_type in ("STOCK_DIVIDEND", "BONUS_SHARE", "SPLIT", "REVERSE_SPLIT"):
                group = "EQUITY_DISTRIBUTION"
            elif act_type == "LISTING_CHANGE":
                group = "LISTING_CHANGE"
            elif act_type == "CORPORATE_EVENT":
                if rat_sig is not None or any(
                    k in norm_note
                    for k in ("exercise rate", "ty le", "100:", "co phieu thuong", "stock dividend", "chia tach", "split")
                ):
                    group = "EQUITY_DISTRIBUTION"
                elif val_sig is not None and any(k in norm_note for k in ("dividend", "co tuc")):
                    group = "CASH_DIVIDEND"
                elif val_sig is not None and any(k in norm_note for k in ("number of shares", "so luong", "listing")):
                    group = "LISTING_CHANGE"
                else:
                    group = "CORPORATE_EVENT"
            else:
                group = act_type or "CORPORATE_EVENT"

            if val_sig is not None or rat_sig is not None:
                key = (ca.action_date, group, val_sig, rat_sig)
            else:
                key = (ca.action_date, group, None, None, norm_note)

        has_non_ascii = any(ord(ch) > 127 for ch in raw_note)
        rank = (
            type_priority.get(act_type, 5),
            0 if has_non_ascii else 1,
            -(ca.id or 0),
        )
        if key not in rank_by_key or rank < rank_by_key[key]:
            rank_by_key[key] = rank
            best_by_key[key] = ca

    return sorted(
        best_by_key.values(),
        key=lambda item: (item.action_date, item.id or 0),
        reverse=True,
    )



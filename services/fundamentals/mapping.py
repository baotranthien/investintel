"""
Line Item Mapping Engine.

Converts provider-specific raw labels → canonical metric names.

Rules:
  - Mappings are loaded from a config file (not hard-coded parser logic)
  - Configurable: source, raw_label, canonical_metric, statement_type, version
  - Sign normalization enforced: Revenue positive, Expense negative, etc.
  - Multiple sources can map to same canonical metric (priority: OFFICIAL > SECONDARY)

Sign Conventions:
  Revenue: +
  Cost/Expense: - (stored as negative, negate if source provides positive)
  Tax: -
  Cash outflow: -
  Debt repayment: -
  Dividend paid: -
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MappingEntry:
    source: str
    raw_label: str
    canonical_metric: str
    statement_type: str
    canonical_section: str
    sign_convention: str = "POSITIVE"  # POSITIVE or NEGATE (invert source sign)
    version: str = "v1"


# ─────────────────────────────────────────────────────────
# Default built-in mappings for Vietnamese BCTC
# (Extensible: user can add more via JSON file)
# ─────────────────────────────────────────────────────────
BUILTIN_MAPPINGS: list[dict] = [
    # ── Income Statement / KQKD ──────────────────────────
    {
        "source": "VIETSTOCK",
        "raw_label": "Doanh thu bán hàng và cung cấp dịch vụ",
        "canonical_metric": "revenue",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        "canonical_metric": "revenue",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Giá vốn hàng bán",
        "canonical_metric": "cost_of_goods_sold",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",  # source shows positive, we store negative
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        "canonical_metric": "gross_profit",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Chi phí bán hàng",
        "canonical_metric": "selling_expense",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Chi phí quản lý doanh nghiệp",
        "canonical_metric": "general_admin_expense",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận thuần từ hoạt động kinh doanh",
        "canonical_metric": "operating_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Thu nhập tài chính",
        "canonical_metric": "interest_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Chi phí tài chính",
        "canonical_metric": "interest_expense",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Chi phí lãi vay",
        "canonical_metric": "interest_expense",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận khác",
        "canonical_metric": "other_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tổng lợi nhuận kế toán trước thuế",
        "canonical_metric": "pre_tax_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Chi phí thuế thu nhập doanh nghiệp hiện hành",
        "canonical_metric": "income_tax",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận sau thuế thu nhập doanh nghiệp",
        "canonical_metric": "net_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận sau thuế của cổ đông thiểu số",
        "canonical_metric": "minority_interest",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận sau thuế của cổ đông công ty mẹ",
        "canonical_metric": "net_income_parent",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lãi cơ bản trên cổ phiếu",
        "canonical_metric": "eps_basic",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    # ── Balance Sheet / CĐKT ─────────────────────────────
    {
        "source": "VIETSTOCK",
        "raw_label": "Tiền và các khoản tương đương tiền",
        "canonical_metric": "cash",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Các khoản đầu tư tài chính ngắn hạn",
        "canonical_metric": "short_term_investments",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Các khoản phải thu ngắn hạn",
        "canonical_metric": "accounts_receivable",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Hàng tồn kho, ròng",
        "canonical_metric": "inventory",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tổng tài sản ngắn hạn",
        "canonical_metric": "total_current_assets",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tài sản cố định",
        "canonical_metric": "ppe",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "TỔNG CỘNG TÀI SẢN",
        "canonical_metric": "total_assets",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Vay và thuê tài chính ngắn hạn",
        "canonical_metric": "short_term_debt",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tổng nợ phải trả ngắn hạn",
        "canonical_metric": "total_current_liabilities",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Vay và thuê tài chính dài hạn",
        "canonical_metric": "long_term_debt",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tổng nợ phải trả",
        "canonical_metric": "total_liabilities",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Vốn điều lệ",
        "canonical_metric": "share_capital",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lợi nhuận sau thuế chưa phân phối",
        "canonical_metric": "retained_earnings",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Vốn chủ sở hữu của cổ đông công ty mẹ",
        "canonical_metric": "equity_parent",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "TỔNG CỘNG NGUỒN VỐN",
        "canonical_metric": "total_equity",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    # Bank-specific balance sheet
    {
        "source": "VIETSTOCK",
        "raw_label": "Cho vay khách hàng",
        "canonical_metric": "loans_and_advances",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Tiền gửi của khách hàng",
        "canonical_metric": "customer_deposits",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Dự phòng rủi ro tín dụng",
        "canonical_metric": "provisions",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "NEGATE",
    },
    # ── Cash Flow / LCTTT ────────────────────────────────
    {
        "source": "VIETSTOCK",
        "raw_label": "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
        "canonical_metric": "cash_from_operations",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lưu chuyển tiền thuần từ hoạt động đầu tư",
        "canonical_metric": "cash_from_investing",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Lưu chuyển tiền thuần từ hoạt động tài chính",
        "canonical_metric": "cash_from_financing",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Mua sắm tài sản cố định",
        "canonical_metric": "capex",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "NEGATE",  # capex is stored as negative outflow
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Cổ tức đã trả",
        "canonical_metric": "dividends_paid",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "NEGATE",
    },
    {
        "source": "VIETSTOCK",
        "raw_label": "Khấu hao tài sản cố định",
        "canonical_metric": "depreciation_amortization",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "POSITIVE",
    },
    # ── English / Generic mappings ───────────────────────
    {
        "source": "GENERIC_EN",
        "raw_label": "Revenue",
        "canonical_metric": "revenue",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Net Revenue",
        "canonical_metric": "revenue",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Cost of Goods Sold",
        "canonical_metric": "cost_of_goods_sold",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "NEGATE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Gross Profit",
        "canonical_metric": "gross_profit",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Operating Income",
        "canonical_metric": "operating_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Net Income",
        "canonical_metric": "net_income",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Net Income Attributable to Shareholders",
        "canonical_metric": "net_income_parent",
        "statement_type": "INCOME_STATEMENT",
        "canonical_section": "income",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Cash and Cash Equivalents",
        "canonical_metric": "cash",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Total Assets",
        "canonical_metric": "total_assets",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Total Equity",
        "canonical_metric": "total_equity",
        "statement_type": "BALANCE_SHEET",
        "canonical_section": "balance_sheet",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Operating Cash Flow",
        "canonical_metric": "cash_from_operations",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "POSITIVE",
    },
    {
        "source": "GENERIC_EN",
        "raw_label": "Capital Expenditures",
        "canonical_metric": "capex",
        "statement_type": "CASH_FLOW",
        "canonical_section": "cash_flow",
        "sign_convention": "NEGATE",
    },
]


class LineItemMapper:
    """
    Maps raw financial statement line items to canonical metrics.
    Maintains a versioned, configurable lookup table.
    """

    def __init__(self, extra_mappings: list[dict] | None = None):
        self._mappings: dict[tuple[str, str], MappingEntry] = {}
        for m in BUILTIN_MAPPINGS:
            self._add(m)
        if extra_mappings:
            for m in extra_mappings:
                self._add(m)

    def _add(self, m: dict) -> None:
        key = (m["source"].upper(), m["raw_label"].strip().upper())
        self._mappings[key] = MappingEntry(
            source=m["source"],
            raw_label=m["raw_label"],
            canonical_metric=m["canonical_metric"],
            statement_type=m["statement_type"],
            canonical_section=m["canonical_section"],
            sign_convention=m.get("sign_convention", "POSITIVE"),
            version=m.get("version", "v1"),
        )

    def lookup(self, source: str, raw_label: str) -> Optional[MappingEntry]:
        """Return mapping entry for a given source and raw label."""
        key = (source.upper(), raw_label.strip().upper())
        entry = self._mappings.get(key)
        if not entry:
            # Fuzzy fallback: try GENERIC_EN
            key_generic = ("GENERIC_EN", raw_label.strip().upper())
            entry = self._mappings.get(key_generic)
        return entry

    def apply_sign(self, entry: MappingEntry, raw_value: Optional[float]) -> Optional[float]:
        """Apply sign convention to raw value."""
        if raw_value is None:
            return None
        if entry.sign_convention == "NEGATE":
            return -abs(raw_value)
        return raw_value

    def normalize_value(self, source: str, raw_label: str,
                        raw_value: Optional[float]) -> tuple[Optional[str], Optional[float]]:
        """
        Given source, raw_label, raw_value → (canonical_metric, normalized_value).
        Returns (None, None) if no mapping found.
        """
        entry = self.lookup(source, raw_label)
        if not entry:
            return None, None
        normalized = self.apply_sign(entry, raw_value)
        return entry.canonical_metric, normalized

    def get_all_mappings(self) -> list[MappingEntry]:
        return list(self._mappings.values())

    def load_from_file(self, path: str) -> None:
        """Load additional mappings from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        for m in data:
            self._add(m)


# Global default mapper instance
_default_mapper: LineItemMapper | None = None


def get_mapper() -> LineItemMapper:
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = LineItemMapper()
    return _default_mapper

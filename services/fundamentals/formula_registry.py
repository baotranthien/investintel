"""
Canonical formula registry for the Fundamental Engine.

Every financial metric has:
  - metric_id: unique identifier
  - name / name_vi: English and Vietnamese names
  - formula: human-readable formula
  - version: semver string (bump when formula changes)
  - scope: GENERAL | BANK | RETAIL | TECHNOLOGY | INDUSTRIAL | MATERIALS
  - unit: %, ratio, VND_BILLION, times, days
  - caveats: important notes

Rules:
  - Deterministic calculation only. NO LLM.
  - Negative denominator → NOT_MEANINGFUL
  - Zero denominator → NOT_MEANINGFUL / denominator_zero
  - Missing data → null + data_status
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FormulaSpec:
    metric_id: str
    name: str
    name_vi: str
    formula: str
    description: str
    version: str
    unit: str
    scope: str = "GENERAL"
    sector: Optional[str] = None
    caveats: str = ""
    example: str = ""


FORMULA_REGISTRY: dict[str, FormulaSpec] = {
    # ──────────────────────────────────────────────
    # MARGINS
    # ──────────────────────────────────────────────
    "gross_margin": FormulaSpec(
        metric_id="gross_margin",
        name="Gross Margin",
        name_vi="Biên lợi nhuận gộp",
        formula="Gross Profit / Revenue",
        description="Percentage of revenue remaining after cost of goods sold.",
        version="gross_margin_v1",
        unit="%",
        caveats="Not meaningful for banks; use NIM instead.",
    ),
    "ebit_margin": FormulaSpec(
        metric_id="ebit_margin",
        name="EBIT Margin",
        name_vi="Biên EBIT",
        formula="EBIT / Revenue",
        description="Earnings before interest and tax as % of revenue.",
        version="ebit_margin_v1",
        unit="%",
    ),
    "ebitda_margin": FormulaSpec(
        metric_id="ebitda_margin",
        name="EBITDA Margin",
        name_vi="Biên EBITDA",
        formula="EBITDA / Revenue",
        description="Earnings before interest, tax, depreciation, amortization as % of revenue.",
        version="ebitda_margin_v1",
        unit="%",
    ),
    "net_margin": FormulaSpec(
        metric_id="net_margin",
        name="Net Profit Margin",
        name_vi="Biên lợi nhuận ròng",
        formula="Net Income (Parent) / Revenue",
        description="Net profit attributable to shareholders as % of revenue.",
        version="net_margin_v1",
        unit="%",
    ),
    "cfo_margin": FormulaSpec(
        metric_id="cfo_margin",
        name="CFO Margin",
        name_vi="Biên dòng tiền hoạt động",
        formula="Cash from Operations / Revenue",
        description="Operating cash flow as % of revenue.",
        version="cfo_margin_v1",
        unit="%",
    ),
    # ──────────────────────────────────────────────
    # PROFITABILITY
    # ──────────────────────────────────────────────
    "roe": FormulaSpec(
        metric_id="roe",
        name="Return on Equity",
        name_vi="Tỷ suất sinh lời trên vốn chủ sở hữu",
        formula="Net Income (Parent) / Average Equity (Parent)",
        description="Net income attributable to shareholders divided by average equity over the period.",
        version="roe_v1",
        unit="%",
        caveats="Use average of beginning and ending equity. Banks: use net income / average equity (parent). Not meaningful when equity < 0.",
        example="Net Income = 5,000 Bn; Avg Equity = 25,000 Bn → ROE = 20%",
    ),
    "roa": FormulaSpec(
        metric_id="roa",
        name="Return on Assets",
        name_vi="Tỷ suất sinh lời trên tổng tài sản",
        formula="Net Income / Average Total Assets",
        description="Net income divided by average total assets.",
        version="roa_v1",
        unit="%",
        example="Net Income = 5,000 Bn; Avg Assets = 100,000 Bn → ROA = 5%",
    ),
    "roic": FormulaSpec(
        metric_id="roic",
        name="Return on Invested Capital",
        name_vi="Tỷ suất sinh lời trên vốn đầu tư",
        formula="NOPAT / Average Invested Capital",
        description="NOPAT = Operating Income × (1 - Effective Tax Rate). Invested Capital = Total Equity + Total Debt - Cash.",
        version="roic_v1",
        unit="%",
        caveats="Not applicable for banks (BANK sector). Use ROE/ROA for banks. Negative invested capital yields NOT_MEANINGFUL.",
        scope="GENERAL",
    ),
    "nim": FormulaSpec(
        metric_id="nim",
        name="Net Interest Margin",
        name_vi="Biên lãi thuần",
        formula="Net Interest Income / Average Interest-Earning Assets",
        description="Bank-specific metric. Net interest income as % of average interest-earning assets.",
        version="nim_v1",
        unit="%",
        scope="BANK",
        sector="BANK",
    ),
    # ──────────────────────────────────────────────
    # GROWTH
    # ──────────────────────────────────────────────
    "revenue_yoy": FormulaSpec(
        metric_id="revenue_yoy",
        name="Revenue YoY Growth",
        name_vi="Tăng trưởng doanh thu theo năm",
        formula="(Revenue_current / Revenue_prior_year) - 1",
        description="Year-over-year revenue growth. Same period comparison.",
        version="revenue_yoy_v1",
        unit="%",
        caveats="Returns null if prior year data not available. Not % difference of 0.",
    ),
    "net_income_yoy": FormulaSpec(
        metric_id="net_income_yoy",
        name="Net Income YoY Growth",
        name_vi="Tăng trưởng lợi nhuận theo năm",
        formula="(Net Income_current / Net Income_prior_year) - 1",
        description="Year-over-year net income growth.",
        version="net_income_yoy_v1",
        unit="%",
        caveats="NOT_MEANINGFUL when prior year net income is negative or zero.",
    ),
    "eps_yoy": FormulaSpec(
        metric_id="eps_yoy",
        name="EPS YoY Growth",
        name_vi="Tăng trưởng EPS theo năm",
        formula="(EPS_current / EPS_prior_year) - 1",
        description="Year-over-year earnings per share growth.",
        version="eps_yoy_v1",
        unit="%",
        caveats="NOT_MEANINGFUL when prior EPS ≤ 0.",
    ),
    "revenue_cagr_3y": FormulaSpec(
        metric_id="revenue_cagr_3y",
        name="Revenue 3Y CAGR",
        name_vi="CAGR doanh thu 3 năm",
        formula="(Revenue_latest / Revenue_3y_ago) ^ (1/3) - 1",
        description="Compound annual growth rate of revenue over 3 years.",
        version="revenue_cagr_3y_v1",
        unit="%",
        caveats="NOT_MEANINGFUL when base or current value is negative. Requires minimum 3 years history.",
    ),
    "revenue_cagr_5y": FormulaSpec(
        metric_id="revenue_cagr_5y",
        name="Revenue 5Y CAGR",
        name_vi="CAGR doanh thu 5 năm",
        formula="(Revenue_latest / Revenue_5y_ago) ^ (1/5) - 1",
        description="Compound annual growth rate of revenue over 5 years.",
        version="revenue_cagr_5y_v1",
        unit="%",
        caveats="Requires minimum 5 years history. NOT_MEANINGFUL if base is negative.",
    ),
    "eps_cagr_3y": FormulaSpec(
        metric_id="eps_cagr_3y",
        name="EPS 3Y CAGR",
        name_vi="CAGR EPS 3 năm",
        formula="(EPS_latest / EPS_3y_ago) ^ (1/3) - 1",
        description="Compound annual growth rate of EPS over 3 years.",
        version="eps_cagr_3y_v1",
        unit="%",
        caveats="NOT_MEANINGFUL when base EPS ≤ 0.",
    ),
    "eps_cagr_5y": FormulaSpec(
        metric_id="eps_cagr_5y",
        name="EPS 5Y CAGR",
        name_vi="CAGR EPS 5 năm",
        formula="(EPS_latest / EPS_5y_ago) ^ (1/5) - 1",
        description="Compound annual growth rate of EPS over 5 years.",
        version="eps_cagr_5y_v1",
        unit="%",
        caveats="NOT_MEANINGFUL when base EPS ≤ 0. Requires 5 years.",
    ),
    # ──────────────────────────────────────────────
    # LEVERAGE / DEBT
    # ──────────────────────────────────────────────
    "gross_debt": FormulaSpec(
        metric_id="gross_debt",
        name="Gross Debt",
        name_vi="Nợ vay",
        formula="Short-Term Debt + Long-Term Debt",
        description="Total interest-bearing debt.",
        version="gross_debt_v1",
        unit="VND_BILLION",
    ),
    "net_debt": FormulaSpec(
        metric_id="net_debt",
        name="Net Debt",
        name_vi="Nợ ròng",
        formula="Gross Debt - Cash - Short-Term Investments",
        description="Gross debt less liquid assets. Negative = net cash position.",
        version="net_debt_v1",
        unit="VND_BILLION",
    ),
    "de_ratio": FormulaSpec(
        metric_id="de_ratio",
        name="Debt to Equity",
        name_vi="Tỷ lệ nợ / vốn chủ sở hữu",
        formula="Gross Debt / Total Equity (Parent)",
        description="Financial leverage ratio.",
        version="de_ratio_v1",
        unit="ratio",
        caveats="NOT_MEANINGFUL when equity ≤ 0.",
    ),
    "net_debt_ebitda": FormulaSpec(
        metric_id="net_debt_ebitda",
        name="Net Debt / EBITDA",
        name_vi="Nợ ròng / EBITDA",
        formula="Net Debt / EBITDA (TTM)",
        description="Leverage coverage: years to pay off debt from EBITDA.",
        version="net_debt_ebitda_v1",
        unit="times",
        caveats="NOT_MEANINGFUL when EBITDA ≤ 0. Not applicable to banks.",
    ),
    "debt_to_assets": FormulaSpec(
        metric_id="debt_to_assets",
        name="Debt to Total Assets",
        name_vi="Tỷ lệ nợ / tổng tài sản",
        formula="Total Liabilities / Total Assets",
        description="Proportion of assets financed by debt.",
        version="debt_to_assets_v1",
        unit="ratio",
    ),
    # ──────────────────────────────────────────────
    # LIQUIDITY
    # ──────────────────────────────────────────────
    "current_ratio": FormulaSpec(
        metric_id="current_ratio",
        name="Current Ratio",
        name_vi="Tỷ số thanh toán hiện hành",
        formula="Total Current Assets / Total Current Liabilities",
        description="Ability to pay short-term obligations.",
        version="current_ratio_v1",
        unit="ratio",
        caveats="Not applicable to banks. NOT_MEANINGFUL when current liabilities = 0.",
    ),
    "quick_ratio": FormulaSpec(
        metric_id="quick_ratio",
        name="Quick Ratio",
        name_vi="Tỷ số thanh toán nhanh",
        formula="(Current Assets - Inventory) / Current Liabilities",
        description="Liquidity excluding inventory.",
        version="quick_ratio_v1",
        unit="ratio",
        caveats="Not applicable to banks.",
    ),
    # ──────────────────────────────────────────────
    # COVERAGE
    # ──────────────────────────────────────────────
    "interest_coverage": FormulaSpec(
        metric_id="interest_coverage",
        name="Interest Coverage",
        name_vi="Tỷ số bao phủ lãi vay",
        formula="EBIT / Interest Expense",
        description="Ability to cover interest expense from operating earnings.",
        version="interest_coverage_v1",
        unit="times",
        caveats="NOT_MEANINGFUL when interest expense = 0 or EBIT < 0. Use N/A for zero-debt companies.",
    ),
    # ──────────────────────────────────────────────
    # CASH FLOW
    # ──────────────────────────────────────────────
    "fcf": FormulaSpec(
        metric_id="fcf",
        name="Free Cash Flow",
        name_vi="Dòng tiền tự do",
        formula="Cash from Operations - Capital Expenditure",
        description="Cash available after maintaining/expanding asset base.",
        version="fcf_v1",
        unit="VND_BILLION",
        caveats="Capex is represented as a positive number in formula (CFO minus capex outflow).",
    ),
    "cfo_to_ni": FormulaSpec(
        metric_id="cfo_to_ni",
        name="CFO / Net Income",
        name_vi="Dòng tiền hoạt động / Lợi nhuận ròng",
        formula="Cash from Operations / Net Income",
        description="Cash conversion quality. Ratio > 1 = high quality earnings.",
        version="cfo_to_ni_v1",
        unit="ratio",
        caveats="NOT_MEANINGFUL when net income ≤ 0.",
    ),
    "fcf_to_ni": FormulaSpec(
        metric_id="fcf_to_ni",
        name="FCF / Net Income",
        name_vi="Dòng tiền tự do / Lợi nhuận ròng",
        formula="Free Cash Flow / Net Income",
        description="Quality of earnings in terms of free cash flow conversion.",
        version="fcf_to_ni_v1",
        unit="ratio",
        caveats="NOT_MEANINGFUL when net income ≤ 0.",
    ),
    "capex_to_revenue": FormulaSpec(
        metric_id="capex_to_revenue",
        name="Capex / Revenue",
        name_vi="Chi phí vốn / Doanh thu",
        formula="Capital Expenditure / Revenue",
        description="Capital intensity of the business.",
        version="capex_to_revenue_v1",
        unit="%",
    ),
    # ──────────────────────────────────────────────
    # WORKING CAPITAL
    # ──────────────────────────────────────────────
    "dso": FormulaSpec(
        metric_id="dso",
        name="Days Sales Outstanding",
        name_vi="Số ngày phải thu bình quân",
        formula="Average Accounts Receivable / Revenue × 365",
        description="Average number of days to collect receivables.",
        version="dso_v1",
        unit="days",
    ),
    "dio": FormulaSpec(
        metric_id="dio",
        name="Days Inventory Outstanding",
        name_vi="Số ngày tồn kho bình quân",
        formula="Average Inventory / COGS × 365",
        description="Average number of days inventory is held.",
        version="dio_v1",
        unit="days",
        caveats="NOT_MEANINGFUL when COGS = 0 (service companies).",
    ),
    "dpo": FormulaSpec(
        metric_id="dpo",
        name="Days Payable Outstanding",
        name_vi="Số ngày phải trả bình quân",
        formula="Average Accounts Payable / COGS × 365",
        description="Average number of days to pay suppliers.",
        version="dpo_v1",
        unit="days",
    ),
    "ccc": FormulaSpec(
        metric_id="ccc",
        name="Cash Conversion Cycle",
        name_vi="Chu kỳ chuyển đổi tiền mặt",
        formula="DSO + DIO - DPO",
        description="Days to convert investments in inventory into cash flows from sales.",
        version="ccc_v1",
        unit="days",
    ),
    # ──────────────────────────────────────────────
    # PER SHARE
    # ──────────────────────────────────────────────
    "bvps": FormulaSpec(
        metric_id="bvps",
        name="Book Value Per Share",
        name_vi="Giá trị sổ sách mỗi cổ phiếu",
        formula="Equity (Parent) / Weighted Average Shares Basic",
        description="Shareholders' equity per share.",
        version="bvps_v1",
        unit="VND",
        caveats="Use shares outstanding if weighted average not available.",
    ),
    "eps_ttm": FormulaSpec(
        metric_id="eps_ttm",
        name="EPS TTM",
        name_vi="EPS lũy kế 12 tháng",
        formula="Net Income (Parent) TTM / Weighted Average Shares Basic",
        description="Trailing twelve months earnings per share.",
        version="eps_ttm_v1",
        unit="VND",
    ),
    "fcf_per_share": FormulaSpec(
        metric_id="fcf_per_share",
        name="FCF Per Share",
        name_vi="Dòng tiền tự do mỗi cổ phiếu",
        formula="Free Cash Flow TTM / Shares Outstanding",
        description="Free cash flow on a per-share basis.",
        version="fcf_per_share_v1",
        unit="VND",
    ),
    # ──────────────────────────────────────────────
    # BANK-SPECIFIC
    # ──────────────────────────────────────────────
    "npl_ratio": FormulaSpec(
        metric_id="npl_ratio",
        name="Non-Performing Loan Ratio",
        name_vi="Tỷ lệ nợ xấu",
        formula="NPL Gross / Total Loans",
        description="Proportion of loan book classified as non-performing.",
        version="npl_ratio_v1",
        unit="%",
        scope="BANK",
        sector="BANK",
    ),
    "llr_coverage": FormulaSpec(
        metric_id="llr_coverage",
        name="Loan Loss Reserve Coverage",
        name_vi="Tỷ lệ bao phủ nợ xấu",
        formula="Provisions / NPL Gross",
        description="How much of NPLs are covered by provisions.",
        version="llr_coverage_v1",
        unit="%",
        scope="BANK",
        sector="BANK",
        caveats="Higher is better. < 100% means under-provisioned.",
    ),
    "ldr": FormulaSpec(
        metric_id="ldr",
        name="Loan to Deposit Ratio",
        name_vi="Tỷ lệ dư nợ / huy động vốn",
        formula="Total Loans / Customer Deposits",
        description="Liquidity and leverage ratio for banks.",
        version="ldr_v1",
        unit="%",
        scope="BANK",
        sector="BANK",
    ),
    "cir": FormulaSpec(
        metric_id="cir",
        name="Cost to Income Ratio",
        name_vi="Tỷ lệ chi phí / thu nhập",
        formula="Operating Expenses / Operating Income",
        description="Efficiency ratio for banks. Lower is better.",
        version="cir_v1",
        unit="%",
        scope="BANK",
        sector="BANK",
    ),
    # ──────────────────────────────────────────────
    # ASSET QUALITY / EFFICIENCY
    # ──────────────────────────────────────────────
    "asset_turnover": FormulaSpec(
        metric_id="asset_turnover",
        name="Asset Turnover",
        name_vi="Vòng quay tổng tài sản",
        formula="Revenue / Average Total Assets",
        description="Revenue generated per unit of assets.",
        version="asset_turnover_v1",
        unit="times",
    ),
    "receivables_to_revenue": FormulaSpec(
        metric_id="receivables_to_revenue",
        name="Receivables / Revenue",
        name_vi="Phải thu / Doanh thu",
        formula="Accounts Receivable / Revenue",
        description="Proportion of revenue not yet collected. Rising ratio = warning.",
        version="receivables_to_revenue_v1",
        unit="ratio",
    ),
}


def get_formula(metric_id: str) -> Optional[FormulaSpec]:
    """Return formula spec for a given metric_id."""
    return FORMULA_REGISTRY.get(metric_id)


def list_formulas(scope: str = None, sector: str = None) -> list[FormulaSpec]:
    """List all formulas, optionally filtered by scope or sector."""
    specs = list(FORMULA_REGISTRY.values())
    if scope:
        specs = [s for s in specs if s.scope == scope or s.scope == "GENERAL"]
    if sector:
        specs = [s for s in specs if s.sector is None or s.sector == sector]
    return specs

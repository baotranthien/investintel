"""
Golden test fixtures for the Fundamental Engine.

These are SYNTHETIC datasets used exclusively for testing.
DO NOT use as real company data.

Each fixture tests a specific scenario:
  - fpt_tech: Technology company with normal financials (FPT-style)
  - vcb_bank: Bank company (VCB-style) — tests banking metrics
  - mwg_retail: Retail company (MWG-style) — tests retail/inventory metrics
  - hpg_industrial: Industrial/materials (HPG-style) — tests COGS, margins
  - neg_earnings: Company with negative EPS periods
  - neg_fcf: Company with positive NI but negative FCF (divergence flag)
  - restatement: Company with restated financials
  - missing_data: Sparse data (tests NULL propagation)
  - high_debt: Company with D/E > 3x
"""

from __future__ import annotations
from datetime import date


# ─────────────────────────────────────────────────────────
# FPT-STYLE: Technology company (generic)
# ─────────────────────────────────────────────────────────

FPT_INCOME_QUARTERS = [
    # (fiscal_period_end, revenue, cogs, gross_profit, opex, operating_income,
    #  interest_income, interest_expense, other_income, pre_tax, tax, net_income,
    #  net_income_parent, eps_basic, eps_diluted, shares_basic)
    # All values in Billion VND; EPS in VND per share
    {
        "fiscal_period_end": date(2021, 3, 31), "fiscal_year": 2021, "fiscal_quarter": 1,
        "revenue": 8200.0, "cost_of_goods_sold": -5740.0, "gross_profit": 2460.0,
        "selling_expense": -410.0, "general_admin_expense": -246.0,
        "operating_income": 1804.0, "interest_income": 150.0, "interest_expense": -80.0,
        "other_income": 50.0, "pre_tax_income": 1924.0, "income_tax": -385.0,
        "net_income": 1539.0, "net_income_parent": 1350.0,
        "eps_basic": 3200.0, "eps_diluted": 3150.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2021, 6, 30), "fiscal_year": 2021, "fiscal_quarter": 2,
        "revenue": 8600.0, "cost_of_goods_sold": -6020.0, "gross_profit": 2580.0,
        "selling_expense": -430.0, "general_admin_expense": -258.0,
        "operating_income": 1892.0, "interest_income": 165.0, "interest_expense": -75.0,
        "other_income": 40.0, "pre_tax_income": 2022.0, "income_tax": -405.0,
        "net_income": 1617.0, "net_income_parent": 1420.0,
        "eps_basic": 3366.0, "eps_diluted": 3310.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2021, 9, 30), "fiscal_year": 2021, "fiscal_quarter": 3,
        "revenue": 9100.0, "cost_of_goods_sold": -6370.0, "gross_profit": 2730.0,
        "selling_expense": -455.0, "general_admin_expense": -273.0,
        "operating_income": 2002.0, "interest_income": 180.0, "interest_expense": -70.0,
        "other_income": 30.0, "pre_tax_income": 2142.0, "income_tax": -429.0,
        "net_income": 1713.0, "net_income_parent": 1510.0,
        "eps_basic": 3580.0, "eps_diluted": 3520.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021, "fiscal_quarter": 4,
        "revenue": 9800.0, "cost_of_goods_sold": -6860.0, "gross_profit": 2940.0,
        "selling_expense": -490.0, "general_admin_expense": -294.0,
        "operating_income": 2156.0, "interest_income": 200.0, "interest_expense": -65.0,
        "other_income": 60.0, "pre_tax_income": 2351.0, "income_tax": -471.0,
        "net_income": 1880.0, "net_income_parent": 1660.0,
        "eps_basic": 3935.0, "eps_diluted": 3875.0, "shares_basic": 421875000,
    },
    # 2022
    {
        "fiscal_period_end": date(2022, 3, 31), "fiscal_year": 2022, "fiscal_quarter": 1,
        "revenue": 9500.0, "cost_of_goods_sold": -6650.0, "gross_profit": 2850.0,
        "selling_expense": -475.0, "general_admin_expense": -285.0,
        "operating_income": 2090.0, "interest_income": 200.0, "interest_expense": -70.0,
        "other_income": 40.0, "pre_tax_income": 2260.0, "income_tax": -452.0,
        "net_income": 1808.0, "net_income_parent": 1600.0,
        "eps_basic": 3794.0, "eps_diluted": 3730.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2022, 6, 30), "fiscal_year": 2022, "fiscal_quarter": 2,
        "revenue": 10200.0, "cost_of_goods_sold": -7140.0, "gross_profit": 3060.0,
        "selling_expense": -510.0, "general_admin_expense": -306.0,
        "operating_income": 2244.0, "interest_income": 220.0, "interest_expense": -65.0,
        "other_income": 50.0, "pre_tax_income": 2449.0, "income_tax": -490.0,
        "net_income": 1959.0, "net_income_parent": 1730.0,
        "eps_basic": 4101.0, "eps_diluted": 4040.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2022, 9, 30), "fiscal_year": 2022, "fiscal_quarter": 3,
        "revenue": 11000.0, "cost_of_goods_sold": -7700.0, "gross_profit": 3300.0,
        "selling_expense": -550.0, "general_admin_expense": -330.0,
        "operating_income": 2420.0, "interest_income": 240.0, "interest_expense": -60.0,
        "other_income": 45.0, "pre_tax_income": 2645.0, "income_tax": -529.0,
        "net_income": 2116.0, "net_income_parent": 1870.0,
        "eps_basic": 4432.0, "eps_diluted": 4365.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022, "fiscal_quarter": 4,
        "revenue": 11800.0, "cost_of_goods_sold": -8260.0, "gross_profit": 3540.0,
        "selling_expense": -590.0, "general_admin_expense": -354.0,
        "operating_income": 2596.0, "interest_income": 260.0, "interest_expense": -55.0,
        "other_income": 70.0, "pre_tax_income": 2871.0, "income_tax": -575.0,
        "net_income": 2296.0, "net_income_parent": 2030.0,
        "eps_basic": 4813.0, "eps_diluted": 4740.0, "shares_basic": 421875000,
    },
    # 2023
    {
        "fiscal_period_end": date(2023, 3, 31), "fiscal_year": 2023, "fiscal_quarter": 1,
        "revenue": 11200.0, "cost_of_goods_sold": -7840.0, "gross_profit": 3360.0,
        "selling_expense": -560.0, "general_admin_expense": -336.0,
        "operating_income": 2464.0, "interest_income": 260.0, "interest_expense": -60.0,
        "other_income": 40.0, "pre_tax_income": 2704.0, "income_tax": -541.0,
        "net_income": 2163.0, "net_income_parent": 1910.0,
        "eps_basic": 4529.0, "eps_diluted": 4460.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2023, 6, 30), "fiscal_year": 2023, "fiscal_quarter": 2,
        "revenue": 12500.0, "cost_of_goods_sold": -8750.0, "gross_profit": 3750.0,
        "selling_expense": -625.0, "general_admin_expense": -375.0,
        "operating_income": 2750.0, "interest_income": 280.0, "interest_expense": -55.0,
        "other_income": 50.0, "pre_tax_income": 3025.0, "income_tax": -606.0,
        "net_income": 2419.0, "net_income_parent": 2140.0,
        "eps_basic": 5075.0, "eps_diluted": 5000.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2023, 9, 30), "fiscal_year": 2023, "fiscal_quarter": 3,
        "revenue": 13200.0, "cost_of_goods_sold": -9240.0, "gross_profit": 3960.0,
        "selling_expense": -660.0, "general_admin_expense": -396.0,
        "operating_income": 2904.0, "interest_income": 300.0, "interest_expense": -50.0,
        "other_income": 60.0, "pre_tax_income": 3214.0, "income_tax": -643.0,
        "net_income": 2571.0, "net_income_parent": 2280.0,
        "eps_basic": 5405.0, "eps_diluted": 5325.0, "shares_basic": 421875000,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023, "fiscal_quarter": 4,
        "revenue": 14100.0, "cost_of_goods_sold": -9870.0, "gross_profit": 4230.0,
        "selling_expense": -705.0, "general_admin_expense": -423.0,
        "operating_income": 3102.0, "interest_income": 330.0, "interest_expense": -45.0,
        "other_income": 80.0, "pre_tax_income": 3467.0, "income_tax": -694.0,
        "net_income": 2773.0, "net_income_parent": 2460.0,
        "eps_basic": 5830.0, "eps_diluted": 5745.0, "shares_basic": 421875000,
    },
]

FPT_BALANCE_QUARTERS = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "cash": 4500.0, "short_term_investments": 2000.0, "accounts_receivable": 8200.0,
        "inventory": 1200.0, "total_current_assets": 16500.0,
        "ppe": 5800.0, "intangibles": 1500.0, "total_assets": 28000.0,
        "short_term_debt": 1500.0, "total_current_liabilities": 9000.0,
        "long_term_debt": 2000.0, "total_liabilities": 14000.0,
        "share_capital": 4219.0, "retained_earnings": 6800.0,
        "total_equity": 14000.0, "equity_parent": 12500.0,
        "minority_interest": 1500.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "cash": 5200.0, "short_term_investments": 2500.0, "accounts_receivable": 9100.0,
        "inventory": 1350.0, "total_current_assets": 18800.0,
        "ppe": 6400.0, "intangibles": 1700.0, "total_assets": 32000.0,
        "short_term_debt": 1800.0, "total_current_liabilities": 10200.0,
        "long_term_debt": 2200.0, "total_liabilities": 15800.0,
        "share_capital": 4219.0, "retained_earnings": 8400.0,
        "total_equity": 16200.0, "equity_parent": 14500.0,
        "minority_interest": 1700.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "cash": 6100.0, "short_term_investments": 3000.0, "accounts_receivable": 10200.0,
        "inventory": 1500.0, "total_current_assets": 22000.0,
        "ppe": 7200.0, "intangibles": 1900.0, "total_assets": 37000.0,
        "short_term_debt": 2000.0, "total_current_liabilities": 11500.0,
        "long_term_debt": 2500.0, "total_liabilities": 18000.0,
        "share_capital": 4219.0, "retained_earnings": 10500.0,
        "total_equity": 19000.0, "equity_parent": 17000.0,
        "minority_interest": 2000.0,
    },
]

FPT_CASHFLOW_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "cash_from_operations": 5100.0, "cash_from_investing": -2200.0,
        "cash_from_financing": -1800.0, "capex": -1500.0,
        "dividends_paid": -800.0, "free_cash_flow": 3600.0,
        "depreciation_amortization": 1200.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "cash_from_operations": 6200.0, "cash_from_investing": -2700.0,
        "cash_from_financing": -2100.0, "capex": -1900.0,
        "dividends_paid": -1000.0, "free_cash_flow": 4300.0,
        "depreciation_amortization": 1400.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "cash_from_operations": 7400.0, "cash_from_investing": -3100.0,
        "cash_from_financing": -2500.0, "capex": -2200.0,
        "dividends_paid": -1200.0, "free_cash_flow": 5200.0,
        "depreciation_amortization": 1700.0,
    },
]


# ─────────────────────────────────────────────────────────
# VCB-STYLE: Bank company
# ─────────────────────────────────────────────────────────

VCB_BANK_INCOME_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "revenue": 42000.0, "interest_income": 35000.0, "interest_expense": -18000.0,
        "operating_income": 24000.0, "general_admin_expense": -8400.0,
        "pre_tax_income": 15600.0, "income_tax": -3120.0,
        "net_income": 12480.0, "net_income_parent": 12000.0,
        "eps_basic": 3650.0, "shares_basic": 3287000000,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "revenue": 50000.0, "interest_income": 42000.0, "interest_expense": -22000.0,
        "operating_income": 28000.0, "general_admin_expense": -9800.0,
        "pre_tax_income": 18200.0, "income_tax": -3640.0,
        "net_income": 14560.0, "net_income_parent": 14000.0,
        "eps_basic": 4257.0, "shares_basic": 3287000000,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "revenue": 58000.0, "interest_income": 49000.0, "interest_expense": -26000.0,
        "operating_income": 32000.0, "general_admin_expense": -11200.0,
        "pre_tax_income": 20800.0, "income_tax": -4160.0,
        "net_income": 16640.0, "net_income_parent": 16000.0,
        "eps_basic": 4866.0, "shares_basic": 3287000000,
    },
]

VCB_BANK_BALANCE_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "cash": 180000.0, "total_assets": 1500000.0,
        "loans_and_advances": 1000000.0, "customer_deposits": 1200000.0,
        "provisions": -25000.0, "npl_gross": 12000.0, "npl_ratio": 1.2,
        "total_liabilities": 1380000.0, "total_equity": 120000.0,
        "equity_parent": 115000.0, "share_capital": 37100.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "cash": 200000.0, "total_assets": 1750000.0,
        "loans_and_advances": 1180000.0, "customer_deposits": 1400000.0,
        "provisions": -28000.0, "npl_gross": 14000.0, "npl_ratio": 1.19,
        "total_liabilities": 1610000.0, "total_equity": 140000.0,
        "equity_parent": 135000.0, "share_capital": 37100.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "cash": 230000.0, "total_assets": 2000000.0,
        "loans_and_advances": 1360000.0, "customer_deposits": 1600000.0,
        "provisions": -30000.0, "npl_gross": 16000.0, "npl_ratio": 1.18,
        "total_liabilities": 1840000.0, "total_equity": 160000.0,
        "equity_parent": 155000.0, "share_capital": 37100.0,
    },
]


# ─────────────────────────────────────────────────────────
# MWG-STYLE: Retail company
# ─────────────────────────────────────────────────────────

MWG_RETAIL_INCOME_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "revenue": 108000.0, "cost_of_goods_sold": -86400.0, "gross_profit": 21600.0,
        "selling_expense": -12960.0, "general_admin_expense": -3240.0,
        "operating_income": 5400.0, "interest_expense": -800.0,
        "pre_tax_income": 4600.0, "income_tax": -920.0,
        "net_income": 3680.0, "net_income_parent": 3500.0,
        "eps_basic": 8100.0, "shares_basic": 432000000,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "revenue": 133000.0, "cost_of_goods_sold": -106400.0, "gross_profit": 26600.0,
        "selling_expense": -15960.0, "general_admin_expense": -3990.0,
        "operating_income": 6650.0, "interest_expense": -1200.0,
        "pre_tax_income": 5450.0, "income_tax": -1090.0,
        "net_income": 4360.0, "net_income_parent": 4100.0,
        "eps_basic": 9491.0, "shares_basic": 432000000,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "revenue": 95000.0, "cost_of_goods_sold": -76000.0, "gross_profit": 19000.0,
        "selling_expense": -14250.0, "general_admin_expense": -2850.0,
        "operating_income": 1900.0, "interest_expense": -1800.0,  # margin compression year
        "pre_tax_income": 100.0, "income_tax": -20.0,
        "net_income": 80.0, "net_income_parent": 75.0,
        "eps_basic": 174.0, "shares_basic": 432000000,
    },
]

MWG_RETAIL_BALANCE_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "cash": 8000.0, "accounts_receivable": 4000.0, "inventory": 22000.0,
        "total_current_assets": 36000.0, "total_assets": 52000.0,
        "accounts_payable": 16000.0, "short_term_debt": 8000.0,
        "total_current_liabilities": 28000.0, "long_term_debt": 4000.0,
        "total_liabilities": 35000.0, "total_equity": 17000.0, "equity_parent": 16000.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "cash": 7500.0, "accounts_receivable": 5500.0, "inventory": 30000.0,
        "total_current_assets": 46000.0, "total_assets": 64000.0,
        "accounts_payable": 18000.0, "short_term_debt": 15000.0,
        "total_current_liabilities": 38000.0, "long_term_debt": 8000.0,
        "total_liabilities": 50000.0, "total_equity": 14000.0, "equity_parent": 13200.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "cash": 6000.0, "accounts_receivable": 5000.0, "inventory": 26000.0,
        "total_current_assets": 40000.0, "total_assets": 56000.0,
        "accounts_payable": 14000.0, "short_term_debt": 14000.0,
        "total_current_liabilities": 32000.0, "long_term_debt": 10000.0,
        "total_liabilities": 45000.0, "total_equity": 11000.0, "equity_parent": 10400.0,
    },
]


# ─────────────────────────────────────────────────────────
# HPG-STYLE: Steel / Industrial / Materials
# ─────────────────────────────────────────────────────────

HPG_INDUSTRIAL_INCOME_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "revenue": 142000.0, "cost_of_goods_sold": -102000.0, "gross_profit": 40000.0,
        "selling_expense": -7100.0, "general_admin_expense": -5680.0,
        "operating_income": 27220.0, "interest_expense": -3000.0,
        "pre_tax_income": 24220.0, "income_tax": -3633.0,
        "net_income": 20587.0, "net_income_parent": 20000.0,
        "eps_basic": 3920.0, "shares_basic": 5102000000,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "revenue": 160000.0, "cost_of_goods_sold": -128000.0, "gross_profit": 32000.0,
        "selling_expense": -8000.0, "general_admin_expense": -6400.0,
        "operating_income": 17600.0, "interest_expense": -4500.0,
        "pre_tax_income": 13100.0, "income_tax": -1965.0,
        "net_income": 11135.0, "net_income_parent": 10800.0,
        "eps_basic": 2117.0, "shares_basic": 5102000000,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "revenue": 120000.0, "cost_of_goods_sold": -96000.0, "gross_profit": 24000.0,
        "selling_expense": -6000.0, "general_admin_expense": -4800.0,
        "operating_income": 13200.0, "interest_expense": -5500.0,
        "pre_tax_income": 7700.0, "income_tax": -1155.0,
        "net_income": 6545.0, "net_income_parent": 6300.0,
        "eps_basic": 1235.0, "shares_basic": 5102000000,
    },
]

HPG_INDUSTRIAL_BALANCE_ANNUAL = [
    {
        "fiscal_period_end": date(2021, 12, 31), "fiscal_year": 2021,
        "cash": 18000.0, "accounts_receivable": 12000.0, "inventory": 35000.0,
        "total_current_assets": 75000.0, "ppe": 80000.0, "total_assets": 185000.0,
        "accounts_payable": 20000.0, "short_term_debt": 25000.0,
        "total_current_liabilities": 55000.0, "long_term_debt": 45000.0,
        "total_liabilities": 115000.0, "total_equity": 70000.0, "equity_parent": 68000.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "cash": 15000.0, "accounts_receivable": 14000.0, "inventory": 42000.0,
        "total_current_assets": 82000.0, "ppe": 95000.0, "total_assets": 215000.0,
        "accounts_payable": 18000.0, "short_term_debt": 35000.0,
        "total_current_liabilities": 62000.0, "long_term_debt": 60000.0,
        "total_liabilities": 140000.0, "total_equity": 75000.0, "equity_parent": 73000.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "cash": 12000.0, "accounts_receivable": 13000.0, "inventory": 38000.0,
        "total_current_assets": 72000.0, "ppe": 105000.0, "total_assets": 210000.0,
        "accounts_payable": 16000.0, "short_term_debt": 30000.0,
        "total_current_liabilities": 56000.0, "long_term_debt": 65000.0,
        "total_liabilities": 138000.0, "total_equity": 72000.0, "equity_parent": 70000.0,
    },
]


# ─────────────────────────────────────────────────────────
# EDGE CASE: Negative earnings
# ─────────────────────────────────────────────────────────

NEG_EARNINGS_FIXTURE = [
    {
        "fiscal_period_end": date(2022, 12, 31), "fiscal_year": 2022,
        "revenue": 10000.0, "net_income": -500.0, "net_income_parent": -500.0,
        "eps_basic": -1200.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "fiscal_year": 2023,
        "revenue": 11000.0, "net_income": 200.0, "net_income_parent": 200.0,
        "eps_basic": 480.0,
    },
]


# ─────────────────────────────────────────────────────────
# EDGE CASE: Cash flow divergence (positive NI, negative CFO)
# ─────────────────────────────────────────────────────────

CF_DIVERGENCE_FIXTURE = [
    {
        "fiscal_period_end": date(2021, 12, 31), "net_income": 500.0,
        "cash_from_operations": -200.0, "free_cash_flow": -500.0,
    },
    {
        "fiscal_period_end": date(2022, 12, 31), "net_income": 600.0,
        "cash_from_operations": -300.0, "free_cash_flow": -700.0,
    },
    {
        "fiscal_period_end": date(2023, 12, 31), "net_income": 700.0,
        "cash_from_operations": -400.0, "free_cash_flow": -900.0,
    },
]


# ─────────────────────────────────────────────────────────
# EDGE CASE: Missing data (sparse)
# ─────────────────────────────────────────────────────────

MISSING_DATA_FIXTURE = {
    "revenue": 5000.0,
    "net_income": None,      # missing
    "gross_profit": None,    # missing
    "total_assets": 20000.0,
    "total_equity": None,    # missing
    "cash_from_operations": None,
}


# ─────────────────────────────────────────────────────────
# EDGE CASE: Zero denominator
# ─────────────────────────────────────────────────────────

ZERO_DENOMINATOR_FIXTURE = {
    "revenue": 0.0,      # will cause division by zero in margins
    "total_equity": 0.0,  # will cause D/E not meaningful
    "ebit": 5000.0,
    "interest_expense": 0.0,  # coverage N/A
}


# Fixture registry
FIXTURES = {
    "fpt_tech": {
        "income_quarters": FPT_INCOME_QUARTERS,
        "balance_annual": FPT_BALANCE_QUARTERS,
        "cashflow_annual": FPT_CASHFLOW_ANNUAL,
        "sector": "TECHNOLOGY",
        "symbol": "FIXTURE_FPT",
    },
    "vcb_bank": {
        "income_annual": VCB_BANK_INCOME_ANNUAL,
        "balance_annual": VCB_BANK_BALANCE_ANNUAL,
        "sector": "BANK",
        "symbol": "FIXTURE_VCB",
    },
    "mwg_retail": {
        "income_annual": MWG_RETAIL_INCOME_ANNUAL,
        "balance_annual": MWG_RETAIL_BALANCE_ANNUAL,
        "sector": "RETAIL",
        "symbol": "FIXTURE_MWG",
    },
    "hpg_industrial": {
        "income_annual": HPG_INDUSTRIAL_INCOME_ANNUAL,
        "balance_annual": HPG_INDUSTRIAL_BALANCE_ANNUAL,
        "sector": "MATERIALS",
        "symbol": "FIXTURE_HPG",
    },
    "neg_earnings": {
        "income_annual": NEG_EARNINGS_FIXTURE,
        "sector": "GENERAL",
        "symbol": "FIXTURE_NEG",
    },
    "cf_divergence": {
        "cashflow_annual": CF_DIVERGENCE_FIXTURE,
        "sector": "GENERAL",
        "symbol": "FIXTURE_CFD",
    },
    "missing_data": {
        "snapshot": MISSING_DATA_FIXTURE,
        "sector": "GENERAL",
        "symbol": "FIXTURE_MISSING",
    },
    "zero_denominator": {
        "snapshot": ZERO_DENOMINATOR_FIXTURE,
        "sector": "GENERAL",
        "symbol": "FIXTURE_ZERO",
    },
}

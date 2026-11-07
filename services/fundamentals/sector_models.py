"""
Sector-Specific Fundamental Models.

Each sector has its own model with appropriate metrics and exclusions.
Generic metrics (current ratio, inventory) are not applied to banking.
Banking metrics (NIM, NPL) are not applied to retail/technology.

Protocol: SectorFundamentalModel
Implementations:
  - BankModel
  - SecuritiesModel
  - RetailModel
  - TechnologyModel
  - ConsumerModel
  - IndustrialModel
  - MaterialsModel
  - OilGasModel
  - UtilityModel
  - RealEstateModel
  - TransportationModel
  - GeneralModel (default fallback)
"""

from __future__ import annotations
from typing import Optional, Any, Protocol, runtime_checkable
from dataclasses import dataclass, field

from .models import MetricResult, DataStatus


@dataclass
class SectorMetrics:
    """Sector-specific metrics output."""
    sector: str
    metrics: dict[str, MetricResult]
    applicable_metrics: list[str]       # metrics computed for this sector
    not_applicable: list[str]           # metrics intentionally excluded
    notes: list[str] = field(default_factory=list)


@runtime_checkable
class SectorFundamentalModel(Protocol):
    sector: str

    def calculate_metrics(
        self,
        company_id: int,
        financial_snapshot: dict[str, Any],
    ) -> SectorMetrics:
        ...

    def get_applicable_metrics(self) -> list[str]:
        ...


# ─────────────────────────────────────────────────────────
# BANK MODEL
# ─────────────────────────────────────────────────────────

class BankModel:
    sector = "BANK"

    APPLICABLE = [
        "net_margin", "roe", "roa", "nim", "npl_ratio", "llr_coverage",
        "ldr", "cir", "revenue_yoy", "net_income_yoy", "eps_yoy",
        "revenue_cagr_3y", "eps_cagr_3y", "bvps", "eps_ttm", "de_ratio",
        "gross_debt", "net_debt",
    ]
    NOT_APPLICABLE = [
        "gross_margin",      # N/A for banks (no COGS)
        "current_ratio",     # N/A
        "quick_ratio",       # N/A
        "inventory",         # N/A
        "dio",               # N/A
        "dpo",               # N/A
        "roic",              # N/A
        "ebitda_margin",     # N/A
        "capex_to_revenue",  # N/A
        "interest_coverage", # N/A for banks (deposit cost of funds)
        "cfo_to_ni",         # N/A (deposits/loans skew operating CF)
        "fcf",               # N/A (industrial FCF not applicable)
        "fcf_to_ni",         # N/A
    ]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        metrics = {}
        notes = ["Banking sector: ROIC, inventory, current ratio excluded. Use NIM, NPL, LDR."]

        inc = snapshot.get("income", {})
        bs = snapshot.get("balance_sheet", {})
        cf = snapshot.get("cash_flow", {})
        prev_bs = snapshot.get("prev_balance_sheet", {})

        # NIM
        nii = inc.get("interest_income")  # net interest income for banks
        avg_earning_assets = snapshot.get("avg_earning_assets")
        if nii is not None and avg_earning_assets and avg_earning_assets > 0:
            metrics["nim"] = MetricResult(
                value=(nii / avg_earning_assets) * 100,
                unit="%", metric_id="nim", calculation_version="nim_v1",
                data_status=DataStatus.VALID,
            )
        else:
            metrics["nim"] = MetricResult(
                value=None, unit="%", metric_id="nim", calculation_version="nim_v1",
                data_status=DataStatus.MISSING_DATA,
                not_meaningful_reason="Net interest income or earning assets data not available.",
            )

        # NPL Ratio
        npl = bs.get("npl_gross")
        loans = bs.get("loans_and_advances")
        if npl is not None and loans and loans > 0:
            metrics["npl_ratio"] = MetricResult(
                value=(npl / loans) * 100,
                unit="%", metric_id="npl_ratio", calculation_version="npl_ratio_v1",
                data_status=DataStatus.VALID,
            )
        else:
            metrics["npl_ratio"] = MetricResult(
                value=None, unit="%", metric_id="npl_ratio", calculation_version="npl_ratio_v1",
                data_status=DataStatus.MISSING_DATA,
                not_meaningful_reason="NPL or loan data not available.",
            )

        # LLR Coverage
        prov = bs.get("provisions")
        if prov is not None and npl and abs(npl) > 1e-10:
            metrics["llr_coverage"] = MetricResult(
                value=(abs(prov) / npl) * 100,
                unit="%", metric_id="llr_coverage", calculation_version="llr_coverage_v1",
                data_status=DataStatus.VALID,
            )
        else:
            metrics["llr_coverage"] = MetricResult(
                value=None, unit="%", metric_id="llr_coverage", calculation_version="llr_coverage_v1",
                data_status=DataStatus.MISSING_DATA,
                not_meaningful_reason="Provisions or NPL data not available.",
            )

        # LDR
        deposits = bs.get("customer_deposits")
        if loans and deposits and deposits > 0:
            metrics["ldr"] = MetricResult(
                value=(loans / deposits) * 100,
                unit="%", metric_id="ldr", calculation_version="ldr_v1",
                data_status=DataStatus.VALID,
            )

        # CIR
        opex = inc.get("operating_expense")
        op_income = inc.get("operating_income")
        if opex is not None and op_income and abs(op_income) > 1e-10:
            metrics["cir"] = MetricResult(
                value=(abs(opex) / abs(op_income)) * 100,
                unit="%", metric_id="cir", calculation_version="cir_v1",
                data_status=DataStatus.VALID,
            )

        # BVPS
        equity_parent = bs.get("equity_parent")
        shares = snapshot.get("shares_basic")
        if equity_parent is not None and shares and shares > 0:
            metrics["bvps"] = MetricResult(
                value=equity_parent / shares,
                unit="VND", metric_id="bvps", calculation_version="bvps_v1",
                data_status=DataStatus.VALID,
            )

        return SectorMetrics(
            sector=self.sector,
            metrics=metrics,
            applicable_metrics=self.APPLICABLE,
            not_applicable=self.NOT_APPLICABLE,
            notes=notes,
        )

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# SECURITIES / BROKERAGE MODEL
# ─────────────────────────────────────────────────────────

class SecuritiesModel:
    sector = "SECURITIES"

    APPLICABLE = [
        "revenue_yoy", "net_income_yoy", "roe", "roa", "bvps",
        "de_ratio", "net_margin", "cfo_to_ni",
    ]
    NOT_APPLICABLE = ["gross_margin", "current_ratio", "roic", "inventory", "dio", "dpo"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Securities sector: focus on brokerage revenue, margin lending, ROE.",
            "Market share data available only from official disclosures.",
        ]
        return SectorMetrics(
            sector=self.sector, metrics={},
            applicable_metrics=self.APPLICABLE,
            not_applicable=self.NOT_APPLICABLE,
            notes=notes,
        )

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# RETAIL MODEL
# ─────────────────────────────────────────────────────────

class RetailModel:
    sector = "RETAIL"

    APPLICABLE = [
        "revenue_yoy", "net_income_yoy", "eps_yoy", "gross_margin", "net_margin",
        "roe", "roa", "inventory", "dio", "dso", "dpo", "ccc",
        "current_ratio", "quick_ratio", "de_ratio", "cfo_to_ni", "fcf",
        "capex_to_revenue", "asset_turnover",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "llr_coverage", "ldr", "cir", "roic"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Retail sector: inventory days, cash conversion cycle are key.",
            "Same-store sales growth requires company disclosure.",
        ]
        return SectorMetrics(
            sector=self.sector, metrics={},
            applicable_metrics=self.APPLICABLE,
            not_applicable=self.NOT_APPLICABLE,
            notes=notes,
        )

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# TECHNOLOGY MODEL
# ─────────────────────────────────────────────────────────

class TechnologyModel:
    sector = "TECHNOLOGY"

    APPLICABLE = [
        "revenue_yoy", "revenue_cagr_3y", "revenue_cagr_5y",
        "eps_yoy", "eps_cagr_3y", "gross_margin", "ebit_margin",
        "net_margin", "roe", "roa", "roic", "fcf", "cfo_to_ni",
        "fcf_to_ni", "de_ratio", "capex_to_revenue", "dso",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "dio", "ldr", "cir"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Technology sector: revenue growth and gross margin expansion are priority metrics.",
            "International revenue, recurring revenue require company disclosure.",
            "Backlog/contract data: only if officially published.",
        ]
        return SectorMetrics(
            sector=self.sector, metrics={},
            applicable_metrics=self.APPLICABLE,
            not_applicable=self.NOT_APPLICABLE,
            notes=notes,
        )

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# CONSUMER / FMCG MODEL
# ─────────────────────────────────────────────────────────

class ConsumerModel:
    sector = "CONSUMER"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "net_margin", "roe", "roa",
        "inventory", "dio", "dso", "dpo", "ccc", "cfo_to_ni",
        "de_ratio", "current_ratio", "capex_to_revenue",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "ldr", "cir"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = ["Consumer sector: volume/pricing data requires company disclosure."]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# INDUSTRIAL MODEL
# ─────────────────────────────────────────────────────────

class IndustrialModel:
    sector = "INDUSTRIAL"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "ebit_margin", "net_margin",
        "roe", "roa", "roic", "fcf", "cfo_to_ni", "capex_to_revenue",
        "de_ratio", "net_debt_ebitda", "interest_coverage",
        "inventory", "dio", "asset_turnover",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "ldr", "cir"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Industrial sector: capacity utilization data requires company disclosure.",
            "Energy cost and raw material price tracking requires supplemental data.",
        ]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# MATERIALS MODEL (e.g., Steel, Mining)
# ─────────────────────────────────────────────────────────

class MaterialsModel:
    sector = "MATERIALS"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "ebit_margin", "net_margin",
        "roe", "roa", "de_ratio", "net_debt_ebitda", "interest_coverage",
        "fcf", "cfo_to_ni", "capex_to_revenue", "inventory", "dio",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "ldr"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Materials: commodity price spread (ASP - input cost) requires supplemental data.",
            "Capacity/utilization requires official disclosure.",
        ]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# OIL & GAS MODEL
# ─────────────────────────────────────────────────────────

class OilGasModel:
    sector = "OIL_GAS"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "net_margin", "roe", "roa",
        "fcf", "cfo_to_ni", "de_ratio", "net_debt_ebitda",
        "capex_to_revenue", "interest_coverage",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "dio"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = ["Oil & Gas: commodity realized price, production volume require official disclosure."]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# REAL ESTATE MODEL
# ─────────────────────────────────────────────────────────

class RealEstateModel:
    sector = "REAL_ESTATE"

    APPLICABLE = [
        "revenue_yoy", "net_margin", "roe", "roa",
        "inventory", "accounts_receivable", "gross_debt",
        "net_debt", "de_ratio", "net_debt_ebitda", "interest_coverage",
        "cfo_to_ni", "fcf",
    ]
    NOT_APPLICABLE = ["gross_margin", "dio", "nim", "npl_ratio", "ldr"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Real Estate: revenue recognition ≠ cash collection.",
            "Presales and project pipeline require official disclosure.",
            "Accounting profit and cash received can differ significantly.",
        ]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# TRANSPORTATION / AIRLINES MODEL
# ─────────────────────────────────────────────────────────

class TransportationModel:
    sector = "TRANSPORTATION"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "net_margin", "roe", "roa",
        "de_ratio", "net_debt_ebitda", "interest_coverage",
        "fcf", "cfo_to_ni", "capex_to_revenue",
    ]
    NOT_APPLICABLE = ["inventory", "dio", "nim", "npl_ratio"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = [
            "Transportation: load factor, fuel cost require operational disclosure.",
            "Lease obligations require IFRS 16 data.",
        ]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# UTILITY MODEL (e.g., Power, Water, Renewable Energy)
# ─────────────────────────────────────────────────────────

class UtilityModel:
    sector = "UTILITY"

    APPLICABLE = [
        "revenue_yoy", "gross_margin", "ebit_margin", "net_margin",
        "roe", "roa", "roic", "fcf", "cfo_to_ni", "capex_to_revenue",
        "de_ratio", "net_debt_ebitda", "interest_coverage",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "inventory", "dio", "ldr", "cir"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        notes = ["Utility sector: stable cash flow, regulated tariff, and high dividend payout are key."]
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE, notes=notes)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# GENERAL / DEFAULT MODEL
# ─────────────────────────────────────────────────────────

class GeneralModel:
    sector = "GENERAL"

    APPLICABLE = [
        "revenue_yoy", "revenue_cagr_3y", "revenue_cagr_5y",
        "net_income_yoy", "eps_yoy", "eps_cagr_3y",
        "gross_margin", "ebit_margin", "net_margin", "cfo_margin",
        "roe", "roa", "roic", "de_ratio", "net_debt_ebitda",
        "current_ratio", "quick_ratio", "interest_coverage",
        "fcf", "cfo_to_ni", "fcf_to_ni", "capex_to_revenue",
        "dso", "dio", "dpo", "ccc", "asset_turnover",
        "bvps", "eps_ttm", "gross_debt", "net_debt",
    ]
    NOT_APPLICABLE = ["nim", "npl_ratio", "llr_coverage", "ldr", "cir"]

    def calculate_metrics(self, company_id: int, snapshot: dict[str, Any]) -> SectorMetrics:
        return SectorMetrics(sector=self.sector, metrics={},
                             applicable_metrics=self.APPLICABLE,
                             not_applicable=self.NOT_APPLICABLE)

    def get_applicable_metrics(self) -> list[str]:
        return self.APPLICABLE


# ─────────────────────────────────────────────────────────
# SECTOR MODEL REGISTRY / FACTORY
# ─────────────────────────────────────────────────────────

SECTOR_MODELS: dict[str, type] = {
    "BANK": BankModel,
    "SECURITIES": SecuritiesModel,
    "RETAIL": RetailModel,
    "TECHNOLOGY": TechnologyModel,
    "CONSUMER": ConsumerModel,
    "INDUSTRIAL": IndustrialModel,
    "MATERIALS": MaterialsModel,
    "OIL_GAS": OilGasModel,
    "UTILITY": UtilityModel,
    "REAL_ESTATE": RealEstateModel,
    "TRANSPORTATION": TransportationModel,
    "GENERAL": GeneralModel,
}


def normalize_sector_name(sector: Optional[str]) -> Optional[str]:
    """
    Standardize inconsistent sector names from DB into canonical sector identifiers.
    """
    if not sector:
        return None
    s = str(sector).strip().upper()
    mapping = {
        "BANK": "BANK",
        "BANKING": "BANK",
        "BANKS": "BANK",
        "SECURITIES": "SECURITIES",
        "FINANCIALS": "SECURITIES",
        "FINANCIAL SERVICES": "SECURITIES",
        "FINANCIAL_SERVICES": "SECURITIES",
        "INSURANCE": "SECURITIES",
        "REAL ESTATE": "REAL_ESTATE",
        "REAL_ESTATE": "REAL_ESTATE",
        "CONSUMER GOODS": "CONSUMER",
        "CONSUMER_GOODS": "CONSUMER",
        "CONSUMER": "CONSUMER",
        "RETAIL": "RETAIL",
        "TECHNOLOGY": "TECHNOLOGY",
        "IT": "TECHNOLOGY",
        "MATERIALS": "MATERIALS",
        "BASIC MATERIALS": "MATERIALS",
        "BASIC_MATERIALS": "MATERIALS",
        "ENERGY": "OIL_GAS",
        "OIL_GAS": "OIL_GAS",
        "OIL & GAS": "OIL_GAS",
        "OIL_AND_GAS": "OIL_GAS",
        "UTILITIES": "UTILITY",
        "UTILITY": "UTILITY",
        "INDUSTRIALS": "INDUSTRIAL",
        "INDUSTRIAL": "INDUSTRIAL",
        "MANUFACTURING": "INDUSTRIAL",
        "CONSTRUCTION": "INDUSTRIAL",
        "TRANSPORTATION": "TRANSPORTATION",
        "LOGISTICS": "TRANSPORTATION",
    }
    return mapping.get(s, s)


# Canonical sector assignments for 100 HOSE universe stocks
COMPANY_SECTOR_MAP: dict[str, str] = {
    # BANK (17)
    "ACB": "BANK", "BID": "BANK", "CTG": "BANK", "EIB": "BANK", "HDB": "BANK",
    "LPB": "BANK", "MBB": "BANK", "MSB": "BANK", "NAB": "BANK", "OCB": "BANK",
    "SHB": "BANK", "SSB": "BANK", "STB": "BANK", "TCB": "BANK", "TPB": "BANK",
    "VCB": "BANK", "VPB": "BANK",
    # SECURITIES (14)
    "BSI": "SECURITIES", "BVH": "SECURITIES", "CTS": "SECURITIES", "DSE": "SECURITIES",
    "EVF": "SECURITIES", "FTS": "SECURITIES", "HCM": "SECURITIES", "SSI": "SECURITIES",
    "TCX": "SECURITIES", "VCI": "SECURITIES", "VCK": "SECURITIES", "VIX": "SECURITIES",
    "VND": "SECURITIES", "VPX": "SECURITIES",
    # REAL_ESTATE (19)
    "BCM": "REAL_ESTATE", "DIG": "REAL_ESTATE", "DXG": "REAL_ESTATE", "HDG": "REAL_ESTATE",
    "KBC": "REAL_ESTATE", "KDH": "REAL_ESTATE", "KOS": "REAL_ESTATE", "NLG": "REAL_ESTATE",
    "NVL": "REAL_ESTATE", "PDR": "REAL_ESTATE", "SIP": "REAL_ESTATE", "SJS": "REAL_ESTATE",
    "TAL": "REAL_ESTATE", "TCH": "REAL_ESTATE", "VGC": "REAL_ESTATE", "VHM": "REAL_ESTATE",
    "VIC": "REAL_ESTATE", "VPI": "REAL_ESTATE", "VRE": "REAL_ESTATE",
    # RETAIL (4)
    "DGW": "RETAIL", "FRT": "RETAIL", "MWG": "RETAIL", "PNJ": "RETAIL",
    # TECHNOLOGY (3)
    "CMG": "TECHNOLOGY", "FPT": "TECHNOLOGY", "ELC": "TECHNOLOGY",
    # MATERIALS (9)
    "BMP": "MATERIALS", "DCM": "MATERIALS", "DPM": "MATERIALS", "GVR": "MATERIALS",
    "HPG": "MATERIALS", "HSG": "MATERIALS", "HT1": "MATERIALS", "NKG": "MATERIALS",
    "PHR": "MATERIALS",
    # CONSUMER (13)
    "ANV": "CONSUMER", "BAF": "CONSUMER", "DBC": "CONSUMER", "HAG": "CONSUMER",
    "KDC": "CONSUMER", "MCH": "CONSUMER", "MSN": "CONSUMER", "PAN": "CONSUMER",
    "SAB": "CONSUMER", "SBT": "CONSUMER", "VHC": "CONSUMER", "VNM": "CONSUMER",
    "VPL": "CONSUMER",
    # OIL_GAS (4)
    "BSR": "OIL_GAS", "GAS": "OIL_GAS", "PLX": "OIL_GAS", "PVD": "OIL_GAS",
    # UTILITY (4)
    "BWE": "UTILITY", "NT2": "UTILITY", "POW": "UTILITY", "REE": "UTILITY",
    # INDUSTRIAL (8)
    "CII": "INDUSTRIAL", "CTD": "INDUSTRIAL", "CTR": "INDUSTRIAL", "GEE": "INDUSTRIAL",
    "GEX": "INDUSTRIAL", "HHV": "INDUSTRIAL", "PC1": "INDUSTRIAL", "VCG": "INDUSTRIAL",
    # TRANSPORTATION (6)
    "GMD": "TRANSPORTATION", "HVN": "TRANSPORTATION", "PVT": "TRANSPORTATION",
    "VJC": "TRANSPORTATION", "VSC": "TRANSPORTATION", "VTP": "TRANSPORTATION",
}


def get_sector_for_symbol(symbol: str, db_sector: Optional[str] = None) -> str:
    """
    Return the sector string for a symbol.
    Priority: COMPANY_SECTOR_MAP -> normalize_sector_name(db_sector) -> "GENERAL"
    """
    if symbol:
        mapped = COMPANY_SECTOR_MAP.get(symbol.upper())
        if mapped:
            return mapped
    normalized = normalize_sector_name(db_sector)
    if normalized:
        return normalized
    return "GENERAL"


def get_sector_model(symbol: str, sector: Optional[str] = None) -> SectorFundamentalModel:
    """
    Return the appropriate sector model for a given company.
    Checks COMPANY_SECTOR_MAP first, then falls back to normalized sector, then GENERAL.
    """
    resolved_sector = get_sector_for_symbol(symbol, sector)
    model_class = SECTOR_MODELS.get(resolved_sector, GeneralModel)
    return model_class()

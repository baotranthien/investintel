"""
Unified Provider Capability Registry.
Defines supported datasets, asset types, exchanges, rate limits, authentication requirements,
and semantic fallback ordering for all market data and macro providers in InvestIntel.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class DatasetType(str, Enum):
    PRICES = "PRICES"
    STATEMENTS_INCOME = "STATEMENTS_INCOME"
    STATEMENTS_BALANCE = "STATEMENTS_BALANCE"
    STATEMENTS_CASHFLOW = "STATEMENTS_CASHFLOW"
    RATIOS = "RATIOS"
    COMPANY_PROFILE = "COMPANY_PROFILE"
    EVENTS_INSIDER = "EVENTS_INSIDER"
    EVENTS_CORPORATE = "EVENTS_CORPORATE"
    NEWS_RSS = "NEWS_RSS"
    MACRO_SERIES = "MACRO_SERIES"
    UNIVERSE_DISCOVERY = "UNIVERSE_DISCOVERY"


class AssetType(str, Enum):
    STOCK = "STOCK"
    INDEX = "INDEX"
    ETF = "ETF"


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    datasets: Set[DatasetType]
    asset_types: Set[AssetType]
    exchanges: Set[str]
    requires_auth: bool = False
    rate_limit_interval: float = 0.5  # minimum seconds between requests
    authority_level: str = "REPUTABLE_SECONDARY"  # OFFICIAL_EXCHANGE, OFFICIAL_GOV, REPUTABLE_SECONDARY, SCRAPED_SECONDARY
    license_type: str = "PUBLIC_UNAUTHENTICATED"  # COMMERCIAL_LICENSED, PUBLIC_UNAUTHENTICATED, BYOK_AUTH
    priority: int = 100  # lower number = higher priority in failover chain
    description: str = ""
    known_limitations: List[str] = field(default_factory=list)


# Central Registry of Provider Capabilities
PROVIDER_CAPABILITIES: Dict[str, ProviderCapability] = {
    "VIETCAP": ProviderCapability(
        name="VIETCAP",
        datasets={
            DatasetType.STATEMENTS_INCOME,
            DatasetType.STATEMENTS_BALANCE,
            DatasetType.STATEMENTS_CASHFLOW,
            DatasetType.RATIOS,
            DatasetType.COMPANY_PROFILE,
            DatasetType.EVENTS_CORPORATE,
            DatasetType.PRICES,
            DatasetType.UNIVERSE_DISCOVERY,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX, AssetType.ETF},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.25,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=10,
        description="Vietcap IQ Insight Service & Trading API — 34+ quarters audited financials with publicDate, ICB sectors, corporate actions, and OHLCV.",
        known_limitations=[
            "Unauthenticated public endpoint for personal/research use",
            "Rate limits should be respected to prevent IP bans",
        ],
    ),
    "VNDIRECT": ProviderCapability(
        name="VNDIRECT",
        datasets={
            DatasetType.PRICES,
            DatasetType.STATEMENTS_INCOME,
            DatasetType.STATEMENTS_BALANCE,
            DatasetType.STATEMENTS_CASHFLOW,
            DatasetType.RATIOS,
            DatasetType.COMPANY_PROFILE,
            DatasetType.EVENTS_CORPORATE,
        },
        asset_types={AssetType.STOCK},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.2,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=20,
        description="VNDIRECT Finfo & dChart API — Deep financial statement history and equity OHLCV.",
        known_limitations=[
            "Does not support benchmark index candles (^VNINDEX, VN30)",
            "Unadjusted vs back-adjusted price divergence during corporate actions",
        ],
    ),
    "LOTUSMARKET": ProviderCapability(
        name="LOTUSMARKET",
        datasets={
            DatasetType.PRICES,
            DatasetType.EVENTS_INSIDER,
            DatasetType.COMPANY_PROFILE,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX, AssetType.ETF},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.1,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=15,
        description="VPS DataFeed (real-time quotes, foreign flow, index candles) & CafeF insider transactions.",
        known_limitations=[
            "Requires corporate action adjustment reconciliation against raw VNDIRECT feeds",
        ],
    ),
    "DNSE": ProviderCapability(
        name="DNSE",
        datasets={
            DatasetType.PRICES,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.1,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=30,
        description="DNSE Entrade chart API — Fast unauthenticated equity and index OHLCV candles.",
        known_limitations=[
            "Does not provide financial statements or corporate actions",
        ],
    ),
    "CAFEF": ProviderCapability(
        name="CAFEF",
        datasets={
            DatasetType.STATEMENTS_INCOME,
            DatasetType.STATEMENTS_BALANCE,
            DatasetType.RATIOS,
            DatasetType.EVENTS_INSIDER,
        },
        asset_types={AssetType.STOCK},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.5,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=40,
        description="CafeF FinanceReport and GetDataChiSoTaiChinh AJAX endpoints for statements and ratios.",
        known_limitations=[
            "Reports statement numbers in thousand VND (requires x1,000 scaling to raw VND)",
            "Cash flow summary handler does not serve full rows (returns empty)",
        ],
    ),
    "SSI_IBOARD": ProviderCapability(
        name="SSI_IBOARD",
        datasets={
            DatasetType.UNIVERSE_DISCOVERY,
            DatasetType.COMPANY_PROFILE,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX, AssetType.ETF},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=0.5,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=10,
        description="SSI iBoard query API — Stock group constituents and legal security names across HOSE, HNX, and UPCOM.",
        known_limitations=[
            "Board lists are addressed by index group tokens (VNINDEX, VN30, HnxIndex, HNXUpcomIndex)",
        ],
    ),
    "FINANCIAL_NEWS": ProviderCapability(
        name="FINANCIAL_NEWS",
        datasets={
            DatasetType.NEWS_RSS,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX},
        exchanges={"HOSE", "HNX", "UPCOM"},
        requires_auth=False,
        rate_limit_interval=1.0,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=50,
        description="CafeF and VnEconomy RSS news feeds with transparent article deduplication.",
        known_limitations=[
            "RSS feeds provide recent articles (last 24-48 hours)",
        ],
    ),
    "VIETSTOCK": ProviderCapability(
        name="VIETSTOCK",
        datasets={
            DatasetType.NEWS_RSS,
        },
        asset_types={AssetType.STOCK},
        exchanges={"HOSE"},
        requires_auth=False,
        rate_limit_interval=1.0,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=60,
        description="Vietstock public daily news API.",
        known_limitations=[
            "Daily rolling news endpoint without historical search",
        ],
    ),
    "WORLD_BANK": ProviderCapability(
        name="WORLD_BANK",
        datasets={
            DatasetType.MACRO_SERIES,
        },
        asset_types={AssetType.INDEX},
        exchanges={"GLOBAL"},
        requires_auth=False,
        rate_limit_interval=0.5,
        authority_level="OFFICIAL_GOV",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=10,
        description="World Bank Indicators API for Vietnam macroeconomic statistics.",
        known_limitations=[
            "Annual indicators updated with official national publication lag",
        ],
    ),
    "OPEN_EXCHANGE_RATES": ProviderCapability(
        name="OPEN_EXCHANGE_RATES",
        datasets={
            DatasetType.MACRO_SERIES,
        },
        asset_types={AssetType.INDEX},
        exchanges={"GLOBAL"},
        requires_auth=False,
        rate_limit_interval=1.0,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=15,
        description="Open.er-api / Frankfurter unauthenticated daily USD/VND exchange rates.",
        known_limitations=[],
    ),
    "BLS": ProviderCapability(
        name="BLS",
        datasets={
            DatasetType.MACRO_SERIES,
        },
        asset_types={AssetType.INDEX},
        exchanges={"GLOBAL"},
        requires_auth=False,
        rate_limit_interval=0.5,
        authority_level="OFFICIAL_GOV",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=10,
        description="U.S. Bureau of Labor Statistics API v1/v2 for global macro benchmarks.",
        known_limitations=[
            "BLS v1 unauthenticated mode clamped to 10-year observation window",
        ],
    ),
    "FRED": ProviderCapability(
        name="FRED",
        datasets={
            DatasetType.MACRO_SERIES,
        },
        asset_types={AssetType.INDEX},
        exchanges={"GLOBAL"},
        requires_auth=True,
        rate_limit_interval=0.5,
        authority_level="OFFICIAL_GOV",
        license_type="BYOK_AUTH",
        priority=20,
        description="Federal Reserve Economic Data API (supports public CSV fallback when enabled).",
        known_limitations=[
            "Requires FRED_API_KEY for official API; reports BLOCKED when key is absent",
        ],
    ),
    "DATACORE": ProviderCapability(
        name="DATACORE",
        datasets={
            DatasetType.PRICES,
            DatasetType.MACRO_SERIES,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX},
        exchanges={"HOSE", "HNX", "UPCOM", "GLOBAL"},
        requires_auth=True,
        rate_limit_interval=0.5,
        authority_level="REPUTABLE_SECONDARY",
        license_type="BYOK_AUTH",
        priority=70,
        description="DataCore Vietnam REST API (gateway.datacore.vn) — Preview datasets unauthenticated; full queries require X_API_KEY.",
        known_limitations=[
            "Unauthenticated preview mode is limited to fixed 10-row sample without symbol filtering",
            "Full access requires paid subscription with X_API_KEY",
        ],
    ),
    "HOSE_CSV": ProviderCapability(
        name="HOSE_CSV",
        datasets={
            DatasetType.PRICES,
        },
        asset_types={AssetType.STOCK, AssetType.INDEX},
        exchanges={"HOSE"},
        requires_auth=False,
        rate_limit_interval=0.0,
        authority_level="REPUTABLE_SECONDARY",
        license_type="PUBLIC_UNAUTHENTICATED",
        priority=999,
        description="Local static CSV seed files for offline development and testing.",
        known_limitations=[
            "Static historical records; not a live feed",
        ],
    ),
}


class ProviderRegistry:
    """Query service for provider capabilities, compatibility checks, and failover chains."""

    @classmethod
    def get_capability(cls, provider: str) -> Optional[ProviderCapability]:
        return PROVIDER_CAPABILITIES.get(provider.upper())

    @classmethod
    def get_providers_for_dataset(
        cls,
        dataset: DatasetType,
        asset_type: AssetType = AssetType.STOCK,
        exchange: Optional[str] = None,
    ) -> List[ProviderCapability]:
        """Returns sorted list of compatible providers for a dataset (ordered by priority)."""
        compatible = []
        for prov in PROVIDER_CAPABILITIES.values():
            if dataset in prov.datasets and asset_type in prov.asset_types:
                if exchange is None or exchange.upper() in prov.exchanges or "GLOBAL" in prov.exchanges:
                    compatible.append(prov)
        compatible.sort(key=lambda p: p.priority)
        return compatible

    @classmethod
    def is_supported(
        cls,
        provider: str,
        dataset: DatasetType,
        asset_type: AssetType = AssetType.STOCK,
        exchange: Optional[str] = None,
    ) -> bool:
        """Determines if a provider can legally and technically handle the given combination."""
        cap = cls.get_capability(provider)
        if not cap:
            return False
        if dataset not in cap.datasets:
            return False
        if asset_type not in cap.asset_types:
            return False
        if exchange and exchange.upper() not in cap.exchanges and "GLOBAL" not in cap.exchanges:
            return False
        return True

    @classmethod
    def get_fallback_chain(cls, dataset: DatasetType) -> List[str]:
        """Returns ordered provider names for a given dataset."""
        return [p.name for p in cls.get_providers_for_dataset(dataset)]

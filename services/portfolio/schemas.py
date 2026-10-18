from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PortfolioRole = Literal["CORE", "SATELLITE", "UNASSIGNED"]
Horizon = Literal["MEDIUM_TERM", "LONG_TERM"]
TransactionType = Literal["BUY", "SELL", "DIVIDEND", "FEE"]


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol or len(symbol) > 20 or not all(char.isalnum() or char in "._-" for char in symbol):
        raise ValueError("Symbol must contain 1-20 ASCII letters, digits, dot, dash, or underscore.")
    return symbol


class HoldingCreate(BaseModel):
    symbol: str
    quantity: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    average_cost: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    acquisition_date: date
    role: PortfolioRole = "UNASSIGNED"
    horizon: Optional[Horizon] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class HoldingPatch(BaseModel):
    quantity: Optional[Decimal] = Field(None, gt=0, max_digits=28, decimal_places=8)
    average_cost: Optional[Decimal] = Field(None, gt=0, max_digits=20, decimal_places=6)
    acquisition_date: Optional[date] = None
    role: Optional[PortfolioRole] = None
    horizon: Optional[Horizon] = None
    notes: Optional[str] = Field(None, max_length=2000)


class ManualTransactionCreate(BaseModel):
    symbol: str
    transaction_type: TransactionType
    quantity: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    unit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    transaction_date: date
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class TargetItem(BaseModel):
    symbol: str
    target_weight: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class TargetAllocationUpdate(BaseModel):
    targets: list[TargetItem] = Field(max_length=100)

    @model_validator(mode="after")
    def check_targets(self):
        symbols = [item.symbol for item in self.targets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate symbols are not allowed in target allocation.")
        if sum((item.target_weight for item in self.targets), Decimal("0")) > Decimal("1"):
            raise ValueError("Target allocation weights must not sum above 100%.")
        return self


class PortfolioSettingsPatch(BaseModel):
    single_name_limit: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)
    sector_limit: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)
    material_change_threshold: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)
    core_target: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)
    satellite_target: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)

    @model_validator(mode="after")
    def check_roles_total(self):
        if self.core_target is not None and self.satellite_target is not None:
            if self.core_target + self.satellite_target > 1:
                raise ValueError("Core and satellite targets must leave a nonnegative reserve.")
        return self


class DcaPlanUpdate(BaseModel):
    monthly_amount: int = Field(ge=300_000, le=400_000)
    core_pct: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)
    satellite_pct: Decimal = Field(ge=0, le=1, max_digits=8, decimal_places=6)

    @model_validator(mode="after")
    def check_split(self):
        if self.core_pct + self.satellite_pct > 1:
            raise ValueError("Core and satellite portions must sum to 100% or less.")
        return self


class WatchlistCreate(BaseModel):
    symbol: str
    thesis: Optional[str] = Field(None, max_length=4000)
    horizon: Optional[Horizon] = None
    invalidation: Optional[str] = Field(None, max_length=4000)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        return normalize_symbol(value)


class WatchlistPatch(BaseModel):
    thesis: Optional[str] = Field(None, max_length=4000)
    horizon: Optional[Horizon] = None
    invalidation: Optional[str] = Field(None, max_length=4000)
    last_reviewed_at: Optional[date] = None
    change_reason: Optional[str] = Field(None, max_length=2000)


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    name: str
    quantity: Decimal
    average_cost: Decimal
    acquisition_date: date
    role: str
    horizon: Optional[str]
    notes: Optional[str]


class PortfolioSettingsResponse(BaseModel):
    portfolio_id: str
    name: str
    base_currency: str
    single_name_limit: Optional[Decimal]
    sector_limit: Optional[Decimal]
    core_target: Optional[Decimal]
    satellite_target: Optional[Decimal]
    material_change_threshold: Optional[Decimal] = None


class PortfolioHoldingView(BaseModel):
    id: int
    symbol: str
    name: str
    sector: Optional[str]
    asset_type: str
    quantity: float
    average_cost: float
    acquisition_date: date
    role: str
    horizon: Optional[str]
    notes: Optional[str]
    current_price: Optional[float]
    price_as_of: Optional[date]
    price_source: Optional[str]
    price_status: str
    cost_basis: float
    market_value: Optional[float]
    unrealized_pnl: Optional[float]
    target_weight: Optional[float]
    current_weight: Optional[float]


class PortfolioDashboardResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    status: Literal["EMPTY", "AVAILABLE", "PARTIAL"]
    summary: dict[str, Any]
    holdings: list[PortfolioHoldingView]
    allocation: dict[str, Any]
    concentration: dict[str, Any]
    risk_exposure: dict[str, Any]
    factor_exposure: dict[str, Any]


class PortfolioFitResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    status: str
    items: list[dict[str, Any]]


class WatchlistItemView(BaseModel):
    id: int
    symbol: str
    name: str
    sector: Optional[str]
    thesis: Optional[str]
    horizon: Optional[str]
    invalidation: Optional[str]
    last_reviewed_at: Optional[str]
    last_changed_at: str
    opportunity: Optional[float]
    confidence: str
    risk: Optional[float]
    valuation: Optional[dict[str, Any]]
    why_now: list[dict[str, Any]]
    why_not_now: list[dict[str, Any]]
    data_status: str
    data_freshness: dict[str, Any]
    changes: list[dict[str, Any]]

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import date
from pydantic import BaseModel

class MacroDataPoint(BaseModel):
    series_id: str
    observation_date: date
    release_date: date | None = None
    value: float
    unit: str
    frequency: str

class MarketDataPoint(BaseModel):
    symbol: str
    observation_date: date
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None

class BaseProvider(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        """Fetch macroeconomic series"""
        pass

    @abstractmethod
    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        """Fetch market data"""
        pass

    def validate_macro_data(self, data: List[MacroDataPoint]) -> List[MacroDataPoint]:
        """Run validation rules on macro data"""
        validated = []
        for point in data:
            if point.value is None:
                continue # Skip nulls
            validated.append(point)
        return validated

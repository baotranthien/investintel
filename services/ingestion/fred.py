import os
import csv
from datetime import datetime
from typing import List, Any
from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .http_client import shared_http_client, ProviderUnavailableError

class FredProvider(BaseProvider):
    def __init__(self):
        super().__init__("FRED")
        self.api_key = os.getenv("FRED_API_KEY")
        self.base_url = "https://api.stlouisfed.org/fred"

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        if not self.api_key:
            if os.getenv("ENABLE_FRED_CSV_FALLBACK", "false").lower() in ("true", "1", "yes") or kwargs.get("use_fallback", False):
                return await self.fetch_macro_series_csv(series_id, **kwargs)
            raise ProviderUnavailableError("FRED_API_KEY is required but not set.")
            
        url = f"{self.base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": kwargs.get("start_date", "2000-01-01"),
        }
        
        response = await shared_http_client.get(url, params=params)
        data = response.json()
        if data.get("error_code"):
            raise ProviderUnavailableError(data.get("error_message", "FRED returned an API error"))
        
        results = []
        for obs in data.get("observations", []):
            try:
                val = float(obs["value"])
                date_obj = datetime.strptime(obs["date"], "%Y-%m-%d").date()
                results.append(MacroDataPoint(
                    series_id=series_id,
                    observation_date=date_obj,
                    release_date=datetime.strptime(obs["realtime_start"], "%Y-%m-%d").date(),
                    value=val,
                    unit="PERCENT" if "DGS" in series_id else "unknown",
                    frequency="DAILY"
                ))
            except ValueError:
                continue
                
        return self.validate_macro_data(results)

    async def fetch_macro_series_csv(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        """
        Public unauthenticated fallback fetching series CSV directly from FRED graph endpoint:
        https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}
        Does not require FRED_API_KEY.
        """
        import httpx
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InvestmentIntel/1.0"
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
        except Exception as exc:
            raise ProviderUnavailableError(f"FRED public CSV connection failed: {exc}")

        if response.status_code != 200:
            raise ProviderUnavailableError(f"FRED public CSV returned HTTP {response.status_code}")

        lines = response.text.strip().splitlines()
        if not lines or len(lines) < 2:
            return []

        reader = csv.reader(lines)
        header = next(reader)
        results = []
        start_date_str = kwargs.get("start_date")
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        for row in reader:
            if len(row) < 2:
                continue
            date_str, val_str = row[0].strip(), row[1].strip()
            if not date_str or val_str == "." or not val_str:
                continue
            try:
                val = float(val_str)
                d_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if start_date and d_obj < start_date:
                    continue
                results.append(MacroDataPoint(
                    series_id=series_id,
                    observation_date=d_obj,
                    release_date=d_obj,
                    value=val,
                    unit="PERCENT" if "DGS" in series_id else "unknown",
                    frequency="DAILY"
                ))
            except ValueError:
                continue

        return self.validate_macro_data(results)

    async def fetch_market_data(self, symbol: str, start_date, end_date) -> List[MarketDataPoint]:
        raise NotImplementedError("FRED is not used for specific market data in this platform.")

import os
import json
from datetime import datetime, date
from typing import List, Any
from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .http_client import shared_http_client

class BlsProvider(BaseProvider):
    def __init__(self):
        super().__init__("BLS")
        self.api_key = os.getenv("BLS_API_KEY") or os.getenv("BLS_REGISTRATION_KEY")
        # If API key is present, use v2 registered access; otherwise use unauthenticated v1 access
        if self.api_key:
            self.base_url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
            self.mode = "V2_REGISTERED"
        else:
            self.base_url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
            self.mode = "V1_UNAUTHENTICATED"

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        url = self.base_url
        headers = {'Content-type': 'application/json'}
        current_year = datetime.now().year
        end_year = int(kwargs.get("end_year", str(current_year)))
        start_year = int(kwargs.get("start_year", "2010"))

        # BLS v1 unauthenticated mode enforces maximum 10-year query window
        if not self.api_key and (end_year - start_year >= 10):
            start_year = end_year - 9

        payload = {
            "seriesid": [series_id],
            "startyear": str(start_year),
            "endyear": str(end_year)
        }
        if self.api_key:
            payload["registrationkey"] = self.api_key
        
        response = await shared_http_client.post_json(url, payload, headers=headers)
        data = response.json()
        
        if data.get("status") != "REQUEST_SUCCEEDED":
            raise Exception(f"BLS API Error ({self.mode}): {data.get('message')}")
            
        results = []
        for series in data["Results"]["series"]:
            if series["seriesID"] != series_id:
                continue
            for item in series["data"]:
                try:
                    val = float(item["value"])
                    # BLS provides period like 'M01', 'Q01', etc. Convert to date roughly.
                    year = int(item["year"])
                    period = item["period"]
                    month = 1
                    if period.startswith("M") and period[1:].isdigit():
                        month = int(period[1:])
                    elif period.startswith("Q") and period[1:].isdigit():
                        month = (int(period[1:]) - 1) * 3 + 1
                        
                    # Handle M13 (Annual Average)
                    if month > 12: month = 12
                        
                    date_obj = datetime(year, month, 1).date()
                    
                    results.append(MacroDataPoint(
                        series_id=series_id,
                        observation_date=date_obj,
                        value=val,
                        unit="index", 
                        frequency="monthly" if period.startswith("M") else "quarterly"
                    ))
                except ValueError:
                    continue
                    
        return self.validate_macro_data(results)

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError()

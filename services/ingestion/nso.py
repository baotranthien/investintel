"""
NSO Vietnam (General Statistics Office - GSO) Public Macro Provider.
Fetches official macroeconomic indicators from the National Summary Data Page (NSDP):
- CPI (Consumer Price Index): https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO/CPIVNM.xml
- GDP (Gross Domestic Product): https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO/GDPVNM.xml

Standard: IMF e-GDDS / SDMX-ML 2.1 StructureSpecificData.
Authentication: NOT required (Public Official National Summary Data Page).
Authority: PRIMARY_OFFICIAL.

Publication timestamp is extracted directly from the SDMX header (<message:Prepared>)
to ensure strict Point-In-Time provenance without fabrication.

Note on SBV (State Bank of Vietnam):
SBV does not currently expose an unauthenticated public REST/JSON or SDMX API.
Requests to sbv.gov.vn redirect with HTTP 302 to WebCenter Portal login sessions.
SBV remains BLOCKED_UNSUPPORTED_PUBLIC_INTERFACE until an official API is documented.
"""
import hashlib
import logging
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_NSDP_BASE_URL = "https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO"
_CPI_URL = f"{_NSDP_BASE_URL}/CPIVNM.xml"
_GDP_URL = f"{_NSDP_BASE_URL}/GDPVNM.xml"

_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MiB cap

_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App; Macro Pipeline)",
    "Accept": "application/xml, text/xml, */*"
}


def _coerce_float(val: Any) -> Optional[float]:
    """Coerces string/numeric to float, handling nulls safely."""
    try:
        x = float(val)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


class NsoProvider(BaseProvider):
    """
    Official Vietnam National Statistics Office (GSO) Provider.
    Parses SDMX-ML XML feeds from the National Summary Data Page.
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("NSO_VIETNAM")
        self.timeout = timeout

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError("NSO Vietnam does not provide equity market data.")

    async def _fetch_xml(self, url: str) -> str:
        """Fetches raw XML payload from NSDP endpoint."""
        max_attempts = 3
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                # verify=False is needed if government portal certificate is self-signed/internal CA
                async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                    response = await client.get(url, headers=_HEADERS)
                    if response.status_code == 429:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("NSO Vietnam rate limit exceeded")

                    if response.status_code >= 500:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"NSO Vietnam server error: HTTP {response.status_code}")

                    if response.status_code != 200:
                        raise ProviderUnavailableError(f"NSO Vietnam returned HTTP {response.status_code}")

                    if len(response.content) > _MAX_RESPONSE_BYTES:
                        raise ProviderUnavailableError(f"NSO Vietnam payload exceeded {_MAX_RESPONSE_BYTES} bytes")

                    return response.text
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"NSO Vietnam endpoint unreachable: {exc}") from exc
        raise ProviderUnavailableError("NSO Vietnam request failed after retries")

    def parse_sdmx_observations(self, xml_content: str, series_id: str) -> tuple[List[MacroDataPoint], Optional[datetime]]:
        """
        Parses SDMX-ML StructureSpecificData XML from NSDP.
        Extracts observation points and the header <Prepared> timestamp.
        """
        if not xml_content:
            return [], None

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            logger.error("XML parse error on NSO feed: %s", exc)
            return [], None

        # 1. Extract publication timestamp from header <Prepared>
        pub_dt = None
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Prepared" and elem.text:
                try:
                    # e.g. 2026-10-12T02:33:09Z
                    prep_str = elem.text.strip().replace("Z", "+00:00")
                    pub_dt = datetime.fromisoformat(prep_str)
                except ValueError:
                    pass
                break

        # 2. Extract observations from <Obs TIME_PERIOD="..." OBS_VALUE="..."/>
        points: List[MacroDataPoint] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Obs":
                time_period = elem.get("TIME_PERIOD") or ""
                obs_val_str = elem.get("OBS_VALUE") or ""
                val = _coerce_float(obs_val_str)
                if val is None or not time_period:
                    continue

                # Parse date from time_period: YYYY-MM or YYYY-Q# or YYYY
                obs_date = None
                time_period = time_period.strip()
                if re.match(r"^\d{4}-\d{2}$", time_period):
                    # Monthly: end of month
                    year, month = map(int, time_period.split("-"))
                    # Determine last day of month
                    next_month = month + 1 if month < 12 else 1
                    next_year = year if month < 12 else year + 1
                    obs_date = date(next_year, next_month, 1) - date.resolution
                elif re.match(r"^\d{4}-Q[1-4]$", time_period, re.IGNORECASE):
                    # Quarterly: end of quarter
                    year = int(time_period[:4])
                    q = int(time_period[-1])
                    q_end_month = q * 3
                    next_m = q_end_month + 1 if q_end_month < 12 else 1
                    next_y = year if q_end_month < 12 else year + 1
                    obs_date = date(next_y, next_m, 1) - date.resolution
                elif re.match(r"^\d{4}$", time_period):
                    obs_date = date(int(time_period), 12, 31)

                if obs_date:
                    points.append(MacroDataPoint(
                        series_id=series_id,
                        observation_date=obs_date,
                        value=val,
                        unit="INDEX_2019_100" if "cpi" in series_id.lower() else "BILLION_VND",
                        frequency="MONTHLY" if "cpi" in series_id.lower() else "QUARTERLY",
                        release_date=pub_dt.date() if pub_dt else None
                    ))

        return points, pub_dt

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        """
        Fetches macro series from NSO Vietnam NSDP.
        Supported series_ids:
        - 'vnm_cpi_gso' or containing 'cpi' -> CPI (Consumer Price Index)
        - 'vnm_gdp_gso' or containing 'gdp' -> GDP (Gross Domestic Product)
        """
        lower_id = series_id.lower()
        if "cpi" in lower_id:
            url = _CPI_URL
        elif "gdp" in lower_id:
            url = _GDP_URL
        else:
            raise ValueError(f"Unsupported NSO series_id '{series_id}'. Available: 'vnm_cpi_gso', 'vnm_gdp_gso'")

        xml_content = await self._fetch_xml(url)
        points, _ = self.parse_sdmx_observations(xml_content, series_id)
        return points

    async def ingest_series_to_database(
        self,
        session: Session,
        series_id: str,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetches official macro observations from NSDP and runs canonical IngestionPipeline.
        Records lineage with header publication timestamp.
        """
        lower_id = series_id.lower()
        url = _CPI_URL if "cpi" in lower_id else _GDP_URL
        xml_content = await self._fetch_xml(url)
        points, pub_dt = self.parse_sdmx_observations(xml_content, series_id)

        records = points
        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_macro_series(
            provider="NSO_VIETNAM",
            series_id=series_id,
            records=records,
            source_url=url,
            source_id=source_id
        )
        return result

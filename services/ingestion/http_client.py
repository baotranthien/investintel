import httpx
import logging
import asyncio
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class RateLimitedError(Exception):
    pass

class ProviderUnavailableError(Exception):
    pass

class InvalidResponseError(Exception):
    pass

class SharedHttpClient:
    """
    A shared HTTP client for data ingestion.
    Handles rate-limits, retries, and generic HTTP errors.
    """
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.min_interval_seconds = 0.5
        self._rate_limit_lock: asyncio.Lock | None = None
        self._last_request_at = 0.0
        self.headers = {
            "User-Agent": "InvestmentIntel/1.0 (Personal Research App)"
        }

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    @property
    def lock(self) -> asyncio.Lock:
        if self._rate_limit_lock is None:
            self._rate_limit_lock = asyncio.Lock()
        return self._rate_limit_lock

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, RateLimitedError, ProviderUnavailableError))
    )
    async def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        return await self.request("GET", url, params=params, headers=headers)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, RateLimitedError, ProviderUnavailableError))
    )
    async def post_json(self, url: str, payload: dict, headers: dict | None = None) -> httpx.Response:
        return await self.request("POST", url, json=payload, headers=headers)

    async def request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        req_headers = {**self.headers, **(headers or {})}
        try:
            async with self.lock:
                wait_seconds = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                response = await self.client.request(
                    method, url, params=params, json=json, headers=req_headers
                )
                self._last_request_at = time.monotonic()
            
            if response.status_code == 429:
                logger.warning(f"Rate limited on {url}. Retrying...")
                raise RateLimitedError("Rate limit exceeded")
                
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ProviderUnavailableError(f"Provider error: {e}")
            raise InvalidResponseError(f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise

    async def close(self):
        await self.client.aclose()

shared_http_client = SharedHttpClient()

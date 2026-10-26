"""
LotusMarket Data Provider for InvestIntel.

Integrates data-fetching capabilities from:
https://github.com/ducnhd/lotusmarket (MIT License, Copyright (c) 2025-2026 Dat Duc Nguyen Huu).

Provides:
1. VPS DataFeed API: real-time quotes, intraday OHLC, bid/ask, and foreign flow volumes (VND).
2. Entrade API: historical daily OHLCV candles (VND).
3. CafeF AJAX API: corporate insider trading transactions (promoted to EventRecord).
4. KBS API: fundamental ratios and metrics (with bounded error handling).

Integrates fully with InvestIntel's IngestionPipeline:
Raw -> Staging -> Validation -> Canonical Promotion -> Lineage Tracking.
Preserves Point-In-Time guards and does not overwrite existing canonical records.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import httpx

from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

# Constants
_VPS_BASE_URL = "https://bgapidatafeed.vps.com.vn/getliststockdata"
_ENTRADE_BASE_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
_CAFEF_URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx?Symbol={ticker}&PageIndex=1&PageSize=50"
_KBS_BASE_URL = "https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestIntel-LotusMarket/1.0)",
    "Accept": "application/json",
}
_PRICE_SCALE = 1000.0  # VPS and Entrade report stock prices in thousands of VND
_VN_TZ = timezone(timedelta(hours=7))  # Vietnam Asia/Ho_Chi_Minh (UTC+7)
_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB response buffer cap


def normalize_symbol(symbol: str) -> str:
    """Uppercase, strips whitespace and non-alphanumeric characters."""
    if not symbol:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", symbol.strip()).upper()


def _parse_pipe_vol(s: str) -> int:
    """Parses 'price|volume' pipe-separated string from VPS quote feed."""
    if not s or "|" not in s:
        return 0
    parts = s.split("|")
    if len(parts) >= 2:
        try:
            return int(float(parts[1]))
        except (ValueError, TypeError):
            return 0
    return 0


def _parse_cafef_date(s: str) -> Optional[datetime]:
    """Parse CafeF's '/Date(ms)/' format to datetime in Vietnam timezone (UTC+7)."""
    if not s:
        return None
    s = s.replace("/Date(", "").replace(")/", "").strip()
    if not s:
        return None
    try:
        ms = int(s)
        return datetime.fromtimestamp(ms / 1000, tz=_VN_TZ)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _clean_html_anchor(s: str) -> str:
    """Strips HTML anchor tags sometimes present in CafeF text fields."""
    if not s:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", s)
    return cleaned.strip()


class LotusMarketProvider(BaseProvider):
    """
    Data provider wrapping verified LotusMarket fetcher endpoints:
    - VPS (Real-time quotes, foreign flow, bid/ask)
    - Entrade (Historical OHLCV with VPS fallback)
    - CafeF (Insider trading events)
    - KBS (Fundamentals)
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("LOTUSMARKET")
        self.timeout = timeout

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("LotusMarket does not provide macroeconomic series.")

    # --------------------------------------------------------------------------
    # 1. VPS Real-Time Quotes & Intraday Snapshots
    # --------------------------------------------------------------------------
    def fetch_quotes(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch real-time quotes for multiple tickers from VPS DataFeed API.
        Scaled to VND. Retries up to 3 times with exponential backoff.
        """
        norm_tickers = [normalize_symbol(t) for t in tickers if normalize_symbol(t)]
        if not norm_tickers:
            return []

        url = f"{_VPS_BASE_URL}/{','.join(norm_tickers)}"
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url, headers=_HEADERS)
                    if resp.status_code == 429:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("VPS DataFeed rate limit exceeded")

                    if resp.status_code >= 500:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"VPS server error HTTP {resp.status_code}")

                    if resp.status_code != 200:
                        logger.warning("VPS non-200 response: HTTP %d", resp.status_code)
                        return []

                    raw = resp.json()
                    if not isinstance(raw, list):
                        return []

                    results: List[Dict[str, Any]] = []
                    today_str = datetime.now(tz=_VN_TZ).date().isoformat()

                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        sym = normalize_symbol(str(item.get("sym", "")))
                        if not sym:
                            continue

                        ref_price = float(item.get("r", 0)) * _PRICE_SCALE
                        last_price = float(item.get("lastPrice", 0)) * _PRICE_SCALE
                        open_price = float(item.get("openPrice", 0)) * _PRICE_SCALE
                        high_price = float(item.get("highPrice", 0)) * _PRICE_SCALE
                        low_price = float(item.get("lowPrice", 0)) * _PRICE_SCALE

                        # If market hasn't traded yet today, last_price defaults to ref_price
                        if last_price == 0 and ref_price > 0:
                            last_price = ref_price
                        if open_price == 0 and last_price > 0:
                            open_price = last_price
                        if high_price == 0 and last_price > 0:
                            high_price = max(open_price, last_price)
                        if low_price == 0 and last_price > 0:
                            low_price = min(open_price, last_price)

                        change_val = last_price - ref_price if ref_price > 0 else 0.0
                        change_pct = (change_val / ref_price * 100) if ref_price > 0 else 0.0

                        f_buy = int(float(item.get("fBVol", 0)))
                        f_sell = int(float(item.get("fSVolume", 0)))

                        g1 = str(item.get("g1", ""))
                        g2 = str(item.get("g2", ""))
                        bid_p = float(g1.split("|")[0]) * _PRICE_SCALE if "|" in g1 else 0.0
                        ask_p = float(g2.split("|")[0]) * _PRICE_SCALE if "|" in g2 else 0.0

                        results.append({
                            "symbol": sym,
                            "observation_date": today_str,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": last_price,
                            "adjusted_close": last_price,
                            "volume": float(item.get("lot", 0)),
                            "ref_price": ref_price,
                            "ceiling": float(item.get("c", 0)) * _PRICE_SCALE,
                            "floor": float(item.get("f", 0)) * _PRICE_SCALE,
                            "change_percent": change_pct,
                            "change_value": change_val,
                            "foreign_buy_vol": f_buy,
                            "foreign_sell_vol": f_sell,
                            "foreign_net_vol": f_buy - f_sell,
                            "bid": bid_p,
                            "ask": ask_p,
                            "bid_vol": _parse_pipe_vol(g1),
                            "ask_vol": _parse_pipe_vol(g2),
                        })

                    return results

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"VPS connection failed: {exc}") from exc

        return []

    def fetch_single_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch quote for a single ticker."""
        quotes = self.fetch_quotes([ticker])
        return quotes[0] if quotes else None

    # --------------------------------------------------------------------------
    # 2. Historical OHLCV Data (Entrade with VPS Fallback)
    # --------------------------------------------------------------------------
    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical daily OHLCV candles from Entrade.
        Normalizes timestamps to Vietnam timezone (UTC+7) and scales prices to VND.
        Appends today's VPS real-time quote if not yet in EOD history and within date range.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        is_index = norm_sym in {"VN100", "VN30", "VNINDEX", "VNX50"}
        base_url = "https://services.entrade.com.vn/chart-api/v2/ohlcs/index" if is_index else _ENTRADE_BASE_URL
        scale = 1.0 if is_index else _PRICE_SCALE

        from_ts = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        to_ts = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp())

        url = f"{base_url}?from={from_ts}&to={to_ts}&symbol={norm_sym}&resolution=1D"
        records: List[Dict[str, Any]] = []

        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url, headers=_HEADERS)
                    if resp.status_code == 429:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("Entrade rate limit exceeded")

                    if resp.status_code >= 500:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"Entrade server error HTTP {resp.status_code}")

                    if resp.status_code != 200:
                        logger.warning("Entrade non-200 response: HTTP %d", resp.status_code)
                        break

                    data = resp.json()
                    if not isinstance(data, dict):
                        break

                    t_arr = data.get("t", [])
                    o_arr = data.get("o", [])
                    h_arr = data.get("h", [])
                    l_arr = data.get("l", [])
                    c_arr = data.get("c", [])
                    v_arr = data.get("v", [])

                    n = min(len(t_arr), len(c_arr))
                    for i in range(n):
                        try:
                            bar_dt = datetime.fromtimestamp(t_arr[i], tz=_VN_TZ).date()
                        except (TypeError, ValueError, OverflowError, OSError):
                            continue

                        if bar_dt < start_date or bar_dt > end_date:
                            continue

                        close_vnd = float(c_arr[i]) * scale
                        open_vnd = float(o_arr[i]) * scale if i < len(o_arr) and o_arr[i] is not None else close_vnd
                        high_vnd = float(h_arr[i]) * scale if i < len(h_arr) and h_arr[i] is not None else max(open_vnd, close_vnd)
                        low_vnd = float(l_arr[i]) * scale if i < len(l_arr) and l_arr[i] is not None else min(open_vnd, close_vnd)
                        vol = float(v_arr[i]) if i < len(v_arr) and v_arr[i] is not None else 0.0

                        # Ensure valid OHLC
                        if high_vnd < low_vnd or close_vnd <= 0:
                            continue

                        records.append({
                            "symbol": norm_sym,
                            "observation_date": bar_dt,
                            "open": open_vnd,
                            "high": high_vnd,
                            "low": low_vnd,
                            "close": close_vnd,
                            "adjusted_close": close_vnd,
                            "is_adjusted_series": True,
                            "provider_semantics": "DIVIDEND_ADJUSTED_CANDLE",
                            "volume": max(0.0, vol),
                        })
                    break

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.warning("Entrade historical fetch failed: %s", exc)
                    break

        records.sort(key=lambda r: r["observation_date"])

        # Fallback check: if today's date is within range and missing from history, fetch VPS (stocks only)
        today = datetime.now(tz=_VN_TZ).date()
        if not is_index and start_date <= today <= end_date:
            dates_in_history = {r["observation_date"] for r in records}
            if today not in dates_in_history:
                try:
                    quote = self.fetch_single_quote(norm_sym)
                    if quote and quote["close"] > 0:
                        records.append({
                            "symbol": norm_sym,
                            "observation_date": today,
                            "open": quote["open"],
                            "high": quote["high"],
                            "low": quote["low"],
                            "close": quote["close"],
                            "adjusted_close": quote["close"],
                            "volume": quote["volume"],
                        })
                        records.sort(key=lambda r: r["observation_date"])
                except Exception as exc:
                    logger.debug("VPS fallback for today's bar skipped: %s", exc)

        return records

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[MarketDataPoint]:
        """
        Async implementation matching BaseProvider interface.
        """
        raw_rows = self.fetch_ohlcv(symbol, start_date, end_date)
        return [
            MarketDataPoint(
                symbol=row["symbol"],
                observation_date=row["observation_date"],
                close=row["close"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                volume=row["volume"],
            )
            for row in raw_rows
        ]

    # --------------------------------------------------------------------------
    # 3. CafeF Insider Shareholder Transactions
    # --------------------------------------------------------------------------
    def fetch_insider_transactions(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch corporate insider transactions from CafeF AJAX API.
        Returns list of standardized event dictionaries ready for IngestionPipeline.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        url = _CAFEF_URL.format(ticker=norm_sym)
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url, headers=_HEADERS)
                    if resp.status_code != 200:
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        return []

                    data = resp.json()
                    if not isinstance(data, dict) or not data.get("Success"):
                        return []

                    items = data.get("Data", {}).get("Data", [])
                    if not isinstance(items, list):
                        return []

                    events: List[Dict[str, Any]] = []
                    cutoff = datetime.now(tz=_VN_TZ) - timedelta(days=180)

                    for item in items:
                        if not isinstance(item, dict):
                            continue

                        insider_name = _clean_html_anchor(str(item.get("TransactionMan") or "")).strip()
                        if not insider_name:
                            continue

                        position = str(item.get("TransactionManPosition") or "").strip()
                        plan_buy = int(float(item.get("PlanBuyVolume") or 0))
                        plan_sell = int(float(item.get("PlanSellVolume") or 0))
                        real_buy = int(float(item.get("RealBuyVolume") or 0))
                        real_sell = int(float(item.get("RealSellVolume") or 0))

                        action = "BUY" if (plan_buy > 0 or real_buy > 0) else "SELL" if (plan_sell > 0 or real_sell > 0) else "TRADE"
                        vol_exec = real_buy if action == "BUY" else real_sell if action == "SELL" else 0
                        vol_plan = plan_buy if action == "BUY" else plan_sell

                        start_dt = _parse_cafef_date(str(item.get("PlanBeginDate") or ""))
                        pub_dt = _parse_cafef_date(str(item.get("PublishedDate") or "")) or start_dt
                        if not pub_dt or pub_dt < cutoff:
                            continue

                        shares_after = int(float(item.get("VolumeAfterTransaction") or 0))
                        ownership = float(item.get("TyLeSoHuu") or 0.0)

                        title = f"[{norm_sym}] Giao dịch cổ đông nội bộ: {insider_name} ({position}) - {action} {vol_exec:,} CP (Đăng ký: {vol_plan:,} CP)"
                        summary = (
                            f"Cổ đông nội bộ {insider_name} ({position}) thực hiện giao dịch cổ phiếu {norm_sym}. "
                            f"Khối lượng đăng ký: {vol_plan:,} CP, khối lượng khớp: {vol_exec:,} CP. "
                            f"Số lượng sở hữu sau giao dịch: {shares_after:,} CP ({ownership:.2f}%)."
                        )

                        # Unique deterministic key based on ticker, insider, action, and date
                        date_str = pub_dt.strftime("%Y%m%d")
                        tx_hash = f"{norm_sym}_{insider_name}_{action}_{date_str}_{vol_exec}".replace(" ", "_")

                        events.append({
                            "id": f"cafef-{tx_hash}",
                            "title": title,
                            "snippet": summary,
                            "url": f"https://cafef.vn/du-lieu/{norm_sym}.chn",
                            "sourceName": "LotusMarket / CafeF",
                            "published_at": pub_dt.isoformat(),
                            "event_type": "CorporateAction",
                            "materiality": "MATERIAL" if vol_exec >= 1000000 else "RELEVANT" if vol_exec >= 100000 else "INFORMATIONAL",
                            "sentiment": "POSITIVE" if action == "BUY" else "NEGATIVE" if action == "SELL" else "NEUTRAL",
                            "affected_sectors": ["ALL"],
                            "impacts": [{
                                "entity_name": norm_sym,
                                "entity_type": "COMPANY",
                                "direction": "POSITIVE" if action == "BUY" else "NEGATIVE" if action == "SELL" else "NO_MATERIAL_EVIDENCE",
                                "magnitude": "HIGH" if vol_exec >= 1000000 else "MEDIUM" if vol_exec >= 100000 else "LOW",
                                "confidence": "HIGH",
                                "evidence": f"CafeF Shareholder Ledger {date_str}"
                            }],
                        })

                    return events

            except Exception as exc:
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.warning("CafeF insider transaction fetch failed for %s: %s", norm_sym, exc)
                    return []

        return []

    # --------------------------------------------------------------------------
    # 4. KBS Fundamentals (with Graceful Degradation)
    # --------------------------------------------------------------------------
    def fetch_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to fetch fundamental valuation metrics (P/E, P/B, EPS, Beta) from KBS.
        Handles provider deprecation or 400/404 errors safely by returning None without crashing.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return None

        to_date = datetime.now(tz=_VN_TZ).strftime("%Y-%m-%d")
        from_date = (datetime.now(tz=_VN_TZ) - timedelta(days=14)).strftime("%Y-%m-%d")
        url = f"{_KBS_BASE_URL}/{norm_sym}/historical-quotes?from={from_date}&to={to_date}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=_HEADERS)
                if resp.status_code != 200:
                    logger.info("KBS fundamentals currently unavailable for %s (HTTP %d)", norm_sym, resp.status_code)
                    return None

                quotes = resp.json()
                if not isinstance(quotes, list) or not quotes:
                    return None

                q = quotes[0]
                return {
                    "symbol": norm_sym,
                    "date": q.get("TradingDate", ""),
                    "market_cap": float(q.get("MarketCapital", 0)),
                    "pe": float(q.get("PE", 0)),
                    "pb": float(q.get("PB", 0)),
                    "eps": float(q.get("EPS", 0)),
                    "bvps": float(q.get("BVPS", 0)),
                    "beta": float(q.get("Beta", 0)),
                    "dividend_yield": float(q.get("Yield", 0)),
                }
        except Exception as exc:
            logger.info("KBS fundamentals request failed for %s: %s", norm_sym, exc)
            return None

    # --------------------------------------------------------------------------
    # 5. Database Ingestion Pipeline Integration
    # --------------------------------------------------------------------------
    def ingest_to_database(
        self,
        session: Session,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: str = "HOSE",
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs full IngestionPipeline: Raw -> Staging -> Validation -> Canonical -> Lineage.
        """
        norm_sym = normalize_symbol(symbol)
        raw_records = self.fetch_ohlcv(norm_sym, start_date, end_date)
        is_index = norm_sym in {"VN100", "VN30", "VNINDEX", "VNX50"}
        kind = "index" if is_index else "stock"
        source_url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/{kind}?symbol={norm_sym}"

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_market_data(
            provider=self.name,
            symbol=norm_sym,
            exchange=exchange,
            records=raw_records,
            source_url_or_path=source_url,
            source_id=source_id,
        )
        return result

    def ingest_insider_events(
        self,
        session: Session,
        symbol: str,
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetches and ingests insider trading transactions into canonical EventRecord table.
        """
        norm_sym = normalize_symbol(symbol)
        events = self.fetch_insider_transactions(norm_sym)
        source_url = _CAFEF_URL.format(ticker=norm_sym)

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_news_events(
            provider=f"{self.name}_CAFEF",
            articles=events,
            source_url=source_url,
            source_id=source_id,
            dataset=f"insider_events_{norm_sym}",
        )
        return result

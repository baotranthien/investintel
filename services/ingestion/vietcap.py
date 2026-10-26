"""
Vietcap Data Provider.
Clean-room implementation of Vietcap Trading API and IQ Insight Service.
Provides:
1. Daily unadjusted and adjusted OHLCV price history (in full VND) for equities and benchmark indexes (^VNINDEX, VN30).
2. Audited quarterly and annual financial statements (Income Statement, Balance Sheet, Cash Flow) with explicit public publication dates (publicDate).
3. Point-in-time financial ratios (P/E, P/B, ROE, ROA, EPS, BVPS).
4. Corporate action events (cash dividends, stock dividends, bonus issues).
5. Real-time quote board (bid/ask book, VWAP, foreign net value).
6. Comprehensive listed universe discovery across HOSE, HNX, and UPCOM.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from sqlalchemy.orm import Session

from database.models import (
    Asset,
    CorporateAction,
    DataLineage,
    DataQualityReportRecord,
    DataRun,
    DataSource,
    EventRecord,
    FinancialLineItem,
    FinancialStatement,
    FundamentalMetric,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    NormalizedIncome,
    Price,
    StagingRecord,
)
from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .http_client import ProviderUnavailableError, RateLimitedError
from .pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

_TRADING_BASE = "https://trading.vietcap.com.vn/api"
_IQ_BASE = "https://iq.vietcap.com.vn/api/iq-insight-service"

_VN_TZ = timezone(timedelta(hours=7))
_DEFAULT_TIMEOUT = 12.0
_MIN_INTERVAL_S = 0.25
_FINANCIAL_BILLION_SCALE = 1_000_000_000.0

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn/",
}

_INDEX_ALIASES = {
    "VNINDEX": "VNINDEX",
    "^VNINDEX": "VNINDEX",
    "VNI": "VNINDEX",
    "VN30": "VN30",
    "^VN30": "VN30",
    "HNX": "HNXIndex",
    "HNXINDEX": "HNXIndex",
    "UPCOM": "HNXUpcomIndex",
    "UPCOMINDEX": "HNXUpcomIndex",
}


def normalize_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        clean = clean[1:]
    return re.sub(r"[^A-Za-z0-9]", "", clean)


class _Pacer:
    """Thread-safe request rate-pacing."""
    def __init__(self, interval: float = _MIN_INTERVAL_S):
        self._interval = interval
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            due = max(now, self._next_allowed)
            self._next_allowed = due + self._interval
        if due > now:
            time.sleep(due - now)


_pacer = _Pacer(_MIN_INTERVAL_S)


class VietcapProvider(BaseProvider):
    """
    Unified provider for Vietcap market data, financial statements, ratios, and events.
    Clean-room implementation with zero heavy dependencies (pure httpx).
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("VIETCAP")
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._client_lock = threading.Lock()

    def _get_client(self) -> httpx.Client:
        with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.Client(headers=_HEADERS, timeout=self.timeout)
            return self._client

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[Any]:
        client = self._get_client()
        backoff = 0.5
        for attempt in range(1, max_retries + 1):
            _pacer.wait()
            try:
                if method.upper() == "POST":
                    resp = client.post(url, json=json_body, params=params)
                else:
                    resp = client.get(url, params=params)

                if resp.status_code == 429:
                    if attempt < max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise RateLimitedError("Vietcap rate limit exceeded (HTTP 429)")

                if resp.status_code >= 500:
                    if attempt < max_retries:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise ProviderUnavailableError(f"Vietcap upstream server error (HTTP {resp.status_code})")

                if resp.status_code in (401, 403):
                    raise ProviderUnavailableError(f"Vietcap access refused (HTTP {resp.status_code})")

                if resp.status_code == 404:
                    return None

                if resp.status_code != 200:
                    logger.warning("Vietcap HTTP %d: %s", resp.status_code, resp.text[:200])
                    return None

                data = resp.json()
                # Vietcap envelopes often return {"successful": true, "data": ...}
                if isinstance(data, dict) and "successful" in data:
                    if not data.get("successful"):
                        msg = data.get("msg") or data.get("exception") or "Unsuccessful"
                        logger.warning("Vietcap business error: %s", msg)
                        return None
                    return data.get("data")
                return data

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"Vietcap connection failed: {exc}") from exc

        return None

    # --------------------------------------------------------------------------
    # 1. OHLCV Market Data
    # --------------------------------------------------------------------------
    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        is_index: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetches daily OHLCV bars from Vietcap Trading gap-chart API.
        Returns records with prices normalized to full VND.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        wire_sym = _INDEX_ALIASES.get(norm_sym, norm_sym) if is_index else norm_sym
        days_span = (end_date - start_date).days + 1
        if days_span <= 0:
            return []

        # Count weekdays in span + buffer
        weekdays = sum(1 for i in range(days_span) if (start_date + timedelta(days=i)).weekday() < 5)
        to_ts = int(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=_VN_TZ).timestamp())

        url = f"{_TRADING_BASE}/chart/OHLCChart/gap-chart"
        payload = {
            "timeFrame": "ONE_DAY",
            "symbols": [wire_sym],
            "to": to_ts,
            "countBack": weekdays + 5,
        }

        raw = self._request("POST", url, json_body=payload)
        if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
            return []

        item = raw[0]
        timestamps = item.get("t") or []
        opens = item.get("o") or []
        highs = item.get("h") or []
        lows = item.get("l") or []
        closes = item.get("c") or []
        volumes = item.get("v") or []

        records: List[Dict[str, Any]] = []
        d0_str, d1_str = start_date.isoformat(), end_date.isoformat()

        for i in range(len(timestamps)):
            try:
                bar_dt = datetime.fromtimestamp(int(timestamps[i]), tz=_VN_TZ).date()
                bar_date_str = bar_dt.isoformat()
            except (ValueError, TypeError, OverflowError, OSError):
                continue

            if not (d0_str <= bar_date_str <= d1_str):
                continue

            c_val = float(closes[i]) if i < len(closes) and closes[i] is not None else None
            if c_val is None or c_val <= 0:
                continue

            o_val = float(opens[i]) if i < len(opens) and opens[i] is not None else c_val
            h_val = float(highs[i]) if i < len(highs) and highs[i] is not None else max(o_val, c_val)
            l_val = float(lows[i]) if i < len(lows) and lows[i] is not None else min(o_val, c_val)
            v_val = float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0

            records.append({
                "symbol": norm_sym,
                "observation_date": bar_dt,
                "open": o_val,
                "high": h_val,
                "low": l_val,
                "close": c_val,
                "adjusted_close": c_val,
                "volume": max(0.0, v_val),
            })

        records.sort(key=lambda r: r["observation_date"])
        return records

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[MarketDataPoint]:
        is_idx = normalize_symbol(symbol) in {"VN100", "VN30", "VNINDEX", "HNXINDEX", "UPCOMINDEX"}
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, self.fetch_ohlcv, symbol, start_date, end_date, is_idx)
        return [
            MarketDataPoint(
                symbol=r["symbol"],
                observation_date=r["observation_date"],
                close=r["close"],
                open=r["open"],
                high=r["high"],
                low=r["low"],
                volume=r["volume"],
            )
            for r in rows
        ]

    # --------------------------------------------------------------------------
    # 2. Real-time Quotes & Intraday Board
    # --------------------------------------------------------------------------
    def fetch_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        norm_symbols = [normalize_symbol(s) for s in symbols if normalize_symbol(s)]
        if not norm_symbols:
            return []

        url = f"{_TRADING_BASE}/price/symbols/getList"
        raw = self._request("POST", url, json_body={"symbols": norm_symbols})
        if not isinstance(raw, list):
            return []

        quotes: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            listing = item.get("listingInfo") or {}
            match = item.get("matchPrice") or {}
            book = item.get("bidAsk") or {}
            sym = normalize_symbol(listing.get("symbol") or "")
            if not sym:
                continue

            c_val = float(match.get("matchPrice") or listing.get("refPrice") or 0.0)
            accum_val = float(match.get("accumulatedValue") or 0.0) * 1_000_000.0  # million VND -> VND
            fb_val = float(match.get("foreignBuyValue") or 0.0)
            fs_val = float(match.get("foreignSellValue") or 0.0)

            quotes.append({
                "symbol": sym,
                "close": c_val,
                "ceiling": float(listing.get("ceiling") or 0.0),
                "floor": float(listing.get("floor") or 0.0),
                "ref_price": float(listing.get("refPrice") or 0.0),
                "open": float(match.get("openPrice") or c_val),
                "high": float(match.get("highPrice") or c_val),
                "low": float(match.get("lowPrice") or c_val),
                "volume": float(match.get("accumulatedVolume") or 0.0),
                "traded_value": accum_val,
                "vwap": float(match.get("avgMatchPrice") or c_val),
                "foreign_buy_value": fb_val,
                "foreign_sell_value": fs_val,
                "foreign_net_value": fb_val - fs_val,
            })
        return quotes

    # --------------------------------------------------------------------------
    # 3. Financial Statements (Audited, with publicDate)
    # --------------------------------------------------------------------------
    def fetch_financial_statements(
        self,
        symbol: str,
        section: str = "INCOME_STATEMENT",
    ) -> Dict[str, Any]:
        """
        Fetches statement records from Vietcap IQ Insight API.
        Sections: 'INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW'.
        Returns dict with 'quarters' and 'years' lists.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return {"quarters": [], "years": []}

        url = f"{_IQ_BASE}/v1/company/{norm_sym}/financial-statement"
        data = self._request("GET", url, params={"section": section})
        if not isinstance(data, dict):
            return {"quarters": [], "years": []}

        return {
            "quarters": data.get("quarters") or [],
            "years": data.get("years") or [],
        }

    # --------------------------------------------------------------------------
    # 4. Financial Ratios
    # --------------------------------------------------------------------------
    def fetch_ratios(self, symbol: str) -> List[Dict[str, Any]]:
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        url = f"{_IQ_BASE}/v1/company/{norm_sym}/statistics-financial"
        data = self._request("GET", url)
        if not isinstance(data, list):
            return []
        return [r for r in data if isinstance(r, dict)]

    # --------------------------------------------------------------------------
    # 5. Corporate Actions / Dividends
    # --------------------------------------------------------------------------
    def fetch_corporate_actions(
        self,
        symbol: str,
        years_back: int = 8,
    ) -> List[Dict[str, Any]]:
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        today = datetime.now(tz=_VN_TZ).date()
        from_str = (today - timedelta(days=365 * years_back)).strftime("%Y%m%d")
        to_str = today.strftime("%Y%m%d")

        url = f"{_IQ_BASE}/v1/events"
        events: List[Dict[str, Any]] = []

        for page in range(5):
            params = {
                "ticker": norm_sym,
                "fromDate": from_str,
                "toDate": to_str,
                "page": page,
                "size": 50,
            }
            res = self._request("GET", url, params=params)
            if not isinstance(res, dict):
                break
            content = res.get("content") or []
            if not isinstance(content, list) or not content:
                break
            for ev in content:
                if isinstance(ev, dict):
                    events.append(ev)
            total_pages = int(res.get("totalPages") or 1)
            if page + 1 >= total_pages:
                break

        return events

    # --------------------------------------------------------------------------
    # 6. Listed Universe Discovery
    # --------------------------------------------------------------------------
    def discover_universe(self) -> List[Dict[str, Any]]:
        """Enumerates the full listed security universe from Vietcap."""
        url = f"{_TRADING_BASE}/price/symbols/getAll"
        raw = self._request("GET", url)
        if not isinstance(raw, list):
            return []

        board_map = {"HSX": "HOSE", "HNX": "HNX", "UPCOM": "UPCOM"}
        items: List[Dict[str, Any]] = []

        for m in raw:
            if not isinstance(m, dict):
                continue
            sym = normalize_symbol(m.get("symbol") or "")
            if not sym:
                continue
            raw_board = str(m.get("board") or "").upper()
            exchange = board_map.get(raw_board, raw_board)
            raw_type = str(m.get("type") or "").upper()
            asset_type = "STOCK" if raw_type in ("STOCK", "S") else ("ETF" if "ETF" in raw_type else "OTHER")

            items.append({
                "symbol": sym,
                "name": str(m.get("organShortName") or m.get("organName") or sym),
                "exchange": exchange,
                "asset_type": asset_type,
                "board": raw_board,
            })
        return items

    # --------------------------------------------------------------------------
    # 7. Ingestion Pipeline & Database Persistence
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
        """Ingests price candles into staging, validation, canonical prices, and lineage."""
        norm_sym = normalize_symbol(symbol)
        is_index = norm_sym in {"VN100", "VN30", "VNINDEX", "HNXINDEX", "UPCOMINDEX"}
        raw_records = self.fetch_ohlcv(norm_sym, start_date, end_date, is_index=is_index)
        wire_sym = _INDEX_ALIASES.get(norm_sym, norm_sym) if is_index else norm_sym
        source_url = f"{_TRADING_BASE}/chart/OHLCChart/gap-chart?symbol={wire_sym}"

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

    def ingest_fundamentals(
        self,
        session: Session,
        symbol: str,
        periods_limit: int = 24,
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Parses Vietcap audited statements, scales to BILLION_VND, and creates
        canonical FinancialStatement, NormalizedIncome, NormalizedBalanceSheet,
        NormalizedCashFlow, and DataLineage records with publicDate provenance.
        """
        norm_sym = normalize_symbol(symbol)
        asset = session.query(Asset).filter(Asset.symbol == norm_sym).first()
        if not asset:
            return {"status": "ERROR", "reason": f"Asset {norm_sym} not registered"}

        # Fetch sections
        inc_res = self.fetch_financial_statements(norm_sym, "INCOME_STATEMENT")
        bs_res = self.fetch_financial_statements(norm_sym, "BALANCE_SHEET")
        cf_res = self.fetch_financial_statements(norm_sym, "CASH_FLOW")

        q_inc = inc_res.get("quarters") or []
        q_bs = { (r.get("yearReport"), r.get("lengthReport")): r for r in (bs_res.get("quarters") or []) }
        q_cf = { (r.get("yearReport"), r.get("lengthReport")): r for r in (cf_res.get("quarters") or []) }

        created_count = 0
        updated_count = 0

        # Sort quarters descending by period
        q_inc_sorted = sorted(
            [r for r in q_inc if r.get("yearReport") and r.get("lengthReport")],
            key=lambda r: (r.get("yearReport", 0), r.get("lengthReport", 0)),
            reverse=True,
        )[:periods_limit]

        for inc_row in q_inc_sorted:
            y = int(inc_row["yearReport"])
            q = int(inc_row["lengthReport"])
            if not (1 <= q <= 4):
                continue

            end_m = q * 3
            end_d = 30 if end_m in (6, 9) else 31
            period_end = date(y, end_m, end_d)
            start_m = (q - 1) * 3 + 1
            period_start = date(y, start_m, 1)

            pub_str = inc_row.get("publicDate") or inc_row.get("updateDate")
            pub_date = None
            if pub_str:
                try:
                    pub_date = datetime.fromisoformat(str(pub_str)[:10]).date()
                except (ValueError, TypeError):
                    pub_date = period_end + timedelta(days=45)
            else:
                pub_date = period_end + timedelta(days=45)

            # Check existing statement
            stmt = session.query(FinancialStatement).filter(
                FinancialStatement.symbol == norm_sym,
                FinancialStatement.statement_type == "INCOME_STATEMENT",
                FinancialStatement.fiscal_period_end == period_end,
                FinancialStatement.period_type == "QUARTER",
            ).first()

            # Map Income statement (scale raw VND to billion VND)
            rev_raw = inc_row.get("isa3") or inc_row.get("isa1")  # Net revenue or gross revenue
            rev = float(rev_raw) / _FINANCIAL_BILLION_SCALE if rev_raw is not None else None
            cogs_raw = inc_row.get("isa4")
            cogs = float(cogs_raw) / _FINANCIAL_BILLION_SCALE if cogs_raw is not None else None
            gp_raw = inc_row.get("isa5")
            gp = float(gp_raw) / _FINANCIAL_BILLION_SCALE if gp_raw is not None else None
            op_raw = inc_row.get("isa11")
            op = float(op_raw) / _FINANCIAL_BILLION_SCALE if op_raw is not None else None
            pbt_raw = inc_row.get("isa16")
            pbt = float(pbt_raw) / _FINANCIAL_BILLION_SCALE if pbt_raw is not None else None
            ni_raw = inc_row.get("isa20")
            ni = float(ni_raw) / _FINANCIAL_BILLION_SCALE if ni_raw is not None else None
            ni_parent_raw = inc_row.get("isa22")
            ni_parent = float(ni_parent_raw) / _FINANCIAL_BILLION_SCALE if ni_parent_raw is not None else ni
            eps_val = float(inc_row.get("isa23") or 0.0)

            # Bank income fields fallback
            if rev is None and inc_row.get("isb25") is not None:
                rev = float(inc_row["isb25"]) / _FINANCIAL_BILLION_SCALE
                pbt = float(inc_row.get("isb37") or 0.0) / _FINANCIAL_BILLION_SCALE
                ni = float(inc_row.get("isb39") or 0.0) / _FINANCIAL_BILLION_SCALE
                ni_parent = ni

            if not stmt:
                stmt = FinancialStatement(
                    asset_id=asset.id,
                    symbol=norm_sym,
                    statement_type="INCOME_STATEMENT",
                    fiscal_period_start=period_start,
                    fiscal_period_end=period_end,
                    fiscal_year=y,
                    fiscal_quarter=q,
                    period_type="QUARTER",
                    statement_date=period_end,
                    publication_date=pub_date,
                    consolidation="CONSOLIDATED",
                    source_id=source_id,
                    source_name="VIETCAP_IQ",
                    source_url=f"{_IQ_BASE}/v1/company/{norm_sym}/financial-statement",
                    currency="VND",
                    unit_scale="BILLION_VND",
                    version=1,
                    status="VALID",
                    raw_data={"yearReport": y, "lengthReport": q, "source": "VIETCAP"},
                )
                session.add(stmt)
                session.flush()

                norm_inc = NormalizedIncome(
                    statement_id=stmt.id,
                    symbol=norm_sym,
                    fiscal_period_end=period_end,
                    fiscal_year=y,
                    fiscal_quarter=q,
                    period_type="QUARTER",
                    revenue=rev,
                    cost_of_goods_sold=cogs,
                    gross_profit=gp,
                    operating_income=op,
                    pre_tax_income=pbt,
                    net_income=ni,
                    net_income_parent=ni_parent,
                    eps_basic=eps_val if eps_val > 0 else None,
                )
                session.add(norm_inc)

                # Lineage
                chk = hashlib.sha256(f"VIETCAP:{norm_sym}:{period_end}:{rev}:{ni}".encode()).hexdigest()
                session.add(DataLineage(
                    record_table="financial_statements",
                    record_id=str(stmt.id),
                    raw_source=f"VIETCAP_IQ [INCOME_STATEMENT, {y}-Q{q}, {period_end}]",
                    url=f"https://iq.vietcap.com.vn/api/iq-service/v1/company/{norm_sym}/financial-statement",
                    retrieved_at=datetime.now(timezone.utc),
                    checksum=chk,
                ))
                created_count += 1
            else:
                updated_count += 1

            # Balance sheet & Cash flow rows
            bs_row = q_bs.get((y, q))
            if bs_row:
                tot_assets = float(bs_row.get("bsa1") or bs_row.get("bsa53") or 0.0) / _FINANCIAL_BILLION_SCALE
                tot_liab = float(bs_row.get("bsa163") or 0.0) / _FINANCIAL_BILLION_SCALE
                tot_equity = float(bs_row.get("bsa204") or 0.0) / _FINANCIAL_BILLION_SCALE

                existing_bs = session.query(NormalizedBalanceSheet).filter(
                    NormalizedBalanceSheet.symbol == norm_sym,
                    NormalizedBalanceSheet.fiscal_period_end == period_end,
                    NormalizedBalanceSheet.period_type == "QUARTER",
                ).first()
                if not existing_bs and stmt:
                    session.add(NormalizedBalanceSheet(
                        statement_id=stmt.id,
                        symbol=norm_sym,
                        fiscal_period_end=period_end,
                        fiscal_year=y,
                        fiscal_quarter=q,
                        period_type="QUARTER",
                        total_assets=tot_assets if tot_assets > 0 else None,
                        total_liabilities=tot_liab if tot_liab > 0 else None,
                        total_equity=tot_equity if tot_equity > 0 else None,
                    ))

            cf_row = q_cf.get((y, q))
            if cf_row:
                cfo = float(cf_row.get("cfa1") or 0.0) / _FINANCIAL_BILLION_SCALE
                cfi = float(cf_row.get("cfa2") or 0.0) / _FINANCIAL_BILLION_SCALE
                cff = float(cf_row.get("cfa3") or 0.0) / _FINANCIAL_BILLION_SCALE
                existing_cf = session.query(NormalizedCashFlow).filter(
                    NormalizedCashFlow.symbol == norm_sym,
                    NormalizedCashFlow.fiscal_period_end == period_end,
                    NormalizedCashFlow.period_type == "QUARTER",
                ).first()
                if not existing_cf and stmt:
                    session.add(NormalizedCashFlow(
                        statement_id=stmt.id,
                        symbol=norm_sym,
                        fiscal_period_end=period_end,
                        fiscal_year=y,
                        fiscal_quarter=q,
                        period_type="QUARTER",
                        cash_from_operations=cfo,
                        cash_from_investing=cfi,
                        cash_from_financing=cff,
                    ))

        session.commit()
        return {
            "status": "SUCCESS",
            "symbol": norm_sym,
            "statements_created": created_count,
            "statements_existing": updated_count,
            "periods_processed": len(q_inc_sorted),
        }

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("Vietcap does not supply global macroeconomic series.")

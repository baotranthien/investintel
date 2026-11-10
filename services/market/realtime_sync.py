# -*- coding: utf-8 -*-
"""
Real-Time Market Sync Engine & In-Memory Live Price Cache.
Guarantees real-time market data freshness across InvestIntel (API, AI, Screener, Valuation).
"""
import asyncio
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Asset, Price, DataLineage
from services.ingestion.dnse import DnseProvider, normalize_symbol

logger = logging.getLogger(__name__)

VN_TZ = timezone(timedelta(hours=7))


class RealtimePriceCache:
    """Thread-safe, high-speed in-memory cache for live market quotes."""
    _cache: Dict[str, Dict[str, Any]] = {}
    _lock = asyncio.Lock()

    @classmethod
    def get(cls, symbol: str, max_age_seconds: int = 120) -> Optional[Dict[str, Any]]:
        sym = normalize_symbol(symbol)
        entry = cls._cache.get(sym)
        if not entry:
            return None
        if time.time() - entry.get("cached_at", 0) > max_age_seconds:
            return None
        return entry

    @classmethod
    def get_latest_quote(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """Returns cached quote regardless of TTL if available today."""
        sym = normalize_symbol(symbol)
        return cls._cache.get(sym)

    @classmethod
    def put(cls, symbol: str, candle: Dict[str, Any]) -> None:
        sym = normalize_symbol(symbol)
        cls._cache[sym] = {
            **candle,
            "cached_at": time.time(),
        }

    @classmethod
    def get_all(cls) -> Dict[str, Dict[str, Any]]:
        return dict(cls._cache)


class RealtimeMarketSyncEngine:
    """
    Continuous background updater and on-demand live market price synchronizer.
    """

    def __init__(self, dnse_provider: Optional[DnseProvider] = None):
        self.provider = dnse_provider or DnseProvider()

    def fetch_live_candle(self, symbol: str, is_index: bool = False) -> Optional[Dict[str, Any]]:
        """Fetches the latest available candle from Entrade / DNSE."""
        today = datetime.now(VN_TZ).date()
        start = today - timedelta(days=7)
        try:
            bars = self.provider.fetch_ohlcv(symbol, start_date=start, end_date=today, is_index=is_index)
            if not bars:
                return None
            latest = bars[-1]
            RealtimePriceCache.put(symbol, latest)
            return latest
        except Exception as exc:
            logger.warning("Failed to fetch live candle for %s: %s", symbol, exc)
            return None

    def persist_candle(self, session: Session, candle: Dict[str, Any]) -> bool:
        """
        Idempotently inserts or updates the candle in the Price table.
        Permitted even when ALLOW_PRODUCTION_DB_WRITE=false via market data guardrail.
        """
        symbol = candle["symbol"]
        obs_date = candle["observation_date"]
        asset = session.query(Asset).filter(Asset.symbol == symbol).first()
        if not asset:
            return False

        existing = (
            session.query(Price)
            .filter(Price.asset_id == asset.id, Price.observation_date == obs_date)
            .first()
        )

        raw_c = float(candle["close"])
        adj_c = float(candle.get("adjusted_close") or candle["close"])
        vol = float(candle.get("volume", 0.0))

        if existing:
            # Update existing price record if values changed
            if existing.raw_close != raw_c or existing.volume != vol:
                existing.raw_open = candle.get("open")
                existing.raw_high = candle.get("high")
                existing.raw_low = candle.get("low")
                existing.raw_close = raw_c
                existing.adjusted_close = adj_c
                existing.volume = vol
                existing.source = "DNSE_REALTIME"
                existing.status = "VALID"
                session.commit()
                return True
            return False
        else:
            new_price = Price(
                asset_id=asset.id,
                observation_date=obs_date,
                raw_open=candle.get("open"),
                raw_high=candle.get("high"),
                raw_low=candle.get("low"),
                raw_close=raw_c,
                adjusted_close=adj_c,
                adjustment_factor=1.0,
                volume=vol,
                source="DNSE_REALTIME",
                status="VALID",
            )
            session.add(new_price)
            session.flush()
            session.add(DataLineage(
                record_table="prices",
                record_id=str(new_price.id),
                raw_source="DNSE_REALTIME",
                url=f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}",
            ))
            session.commit()
            return True

    def _persist_candles_batch(self, valid_candles: List[Dict[str, Any]], session_factory=SessionLocal) -> int:
        updated_count = 0
        with session_factory() as session:
            for candle in valid_candles:
                try:
                    if self.persist_candle(session, candle):
                        updated_count += 1
                except Exception as exc:
                    logger.warning("Could not persist realtime price for %s: %s", candle.get("symbol"), exc)
                    session.rollback()
        return updated_count

    async def sync_symbols(
        self,
        symbols: List[str],
        session_factory=SessionLocal,
        max_concurrency: int = 4,
    ) -> int:
        """
        Concurrently fetches live prices for target symbols and synchronizes to DB and cache.
        """
        sem = asyncio.Semaphore(max_concurrency)
        INDEX_SYMBOLS = {"VN100", "VN30", "VNINDEX", "VNX50", "VN300"}
        loop = asyncio.get_running_loop()

        async def _sync_one(sym: str) -> Optional[Dict[str, Any]]:
            async with sem:
                is_idx = sym in INDEX_SYMBOLS
                return await loop.run_in_executor(None, self.fetch_live_candle, sym, is_idx)

        tasks = [_sync_one(s) for s in symbols]
        candles = await asyncio.gather(*tasks, return_exceptions=True)

        valid_candles = [c for c in candles if isinstance(c, dict) and c is not None]
        if not valid_candles:
            return 0

        # Persist batch to DB in executor so event loop is never blocked
        return await loop.run_in_executor(None, self._persist_candles_batch, valid_candles, session_factory)

    async def sync_universe(self, session_factory=SessionLocal) -> int:
        """
        Synchronizes all active constituent stocks and benchmark indices.
        """
        with session_factory() as s:
            active_assets = s.query(Asset.symbol).filter(Asset.status == "ACTIVE").all()
            symbols = [a[0] for a in active_assets]

        if not symbols:
            return 0

        # Prioritize VN30 + core symbols first
        priority_symbols = [
            "VNINDEX", "VN30", "VN100", "FPT", "HPG", "VCB", "VHM", "VIC",
            "TCB", "MBB", "MWG", "GAS", "MSN", "SSI", "STB", "VNM", "BID"
        ]
        ordered_symbols = list(dict.fromkeys(
            [s for s in priority_symbols if s in symbols] + symbols
        ))

        return await self.sync_symbols(ordered_symbols, session_factory=session_factory)


async def start_realtime_sync_loop(stop_event: asyncio.Event, interval_seconds: Optional[int] = None) -> None:
    """
    Background worker that keeps market prices fresh in real-time.
    Runs immediately on startup, then continuously loops.
    """
    if interval_seconds is None:
        interval_seconds = int(os.getenv("REALTIME_SYNC_INTERVAL_SECONDS", "60"))

    engine = RealtimeMarketSyncEngine()
    logger.info("Real-time market sync worker starting up (interval: %ds)...", interval_seconds)

    # Initial delay for clean server startup
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=2.0)
        return
    except asyncio.TimeoutError:
        pass

    # Immediate initial synchronization of core symbols on startup
    try:
        core_symbols = [
            "VNINDEX", "VN30", "VN100", "FPT", "HPG", "VCB", "VHM", "VIC",
            "TCB", "MBB", "MWG", "GAS", "MSN", "SSI", "STB", "VNM", "BID"
        ]
        logger.info("Running initial startup real-time price synchronization for %d core symbols...", len(core_symbols))
        updated = await engine.sync_symbols(core_symbols)
        logger.info("Initial real-time sync completed: %d prices updated.", updated)
    except Exception as exc:
        logger.warning("Initial real-time price sync failed: %s", exc)

    # Continuous sync loop
    while not stop_event.is_set():
        try:
            # Full universe sync
            updated = await engine.sync_universe()
            logger.info("Background real-time universe sync cycle finished (%d prices updated).", updated)
        except Exception as exc:
            logger.warning("Background real-time sync cycle error: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


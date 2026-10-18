import csv
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .pipeline import IngestionPipeline

class MarketDataCsvProvider(BaseProvider):
    def __init__(self):
        super().__init__("MarketDataCSV")
        
    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("MarketDataCSV does not provide macroeconomic series.")

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        file_path: Optional[str] = None
    ) -> List[MarketDataPoint]:
        """
        Parses CSV records within a given date range.
        """
        if not file_path:
            # Check default market data path
            default_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "market", f"{symbol.lower()}_historical.csv"
            )
            if os.path.exists(default_path):
                file_path = default_path
            else:
                raise ValueError(f"CSV file_path is required for MarketDataCsvProvider (default {default_path} not found)")
            
        results = []
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_str = row.get('Date', row.get('Ngày'))
                    close_str = row.get('Close', row.get('Đóng cửa'))
                    
                    if not date_str or not close_str:
                        continue
                        
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    
                    if date_obj < start_date or date_obj > end_date:
                        continue
                        
                    results.append(MarketDataPoint(
                        symbol=symbol.upper(),
                        observation_date=date_obj,
                        close=float(close_str),
                        open=float(row.get('Open', row.get('Mở cửa', 0))),
                        high=float(row.get('High', row.get('Cao nhất', 0))),
                        low=float(row.get('Low', row.get('Thấp nhất', 0))),
                        volume=float(row.get('Volume', row.get('Khối lượng', 0)))
                    ))
                except ValueError:
                    continue
                    
        return results

    def ingest_to_database(
        self,
        session: Session,
        file_path: str,
        symbol: str,
        exchange: str = "HOSE",
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs the full Raw -> Staging -> Validation -> Canonical pipeline into the database.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Market CSV file not found: {file_path}")

        raw_records = []
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('Date', row.get('Ngày'))
                close_val = row.get('Close', row.get('Đóng cửa'))
                if not date_str:
                    continue
                try:
                    d_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    raw_records.append({
                        "symbol": symbol.upper(),
                        "observation_date": d_obj,
                        "close": float(close_val) if close_val is not None else None,
                        "open": float(row.get('Open', row.get('Mở cửa', 0))),
                        "high": float(row.get('High', row.get('Cao nhất', 0))),
                        "low": float(row.get('Low', row.get('Thấp nhất', 0))),
                        "volume": float(row.get('Volume', row.get('Khối lượng', 0))),
                        "adjusted_close": float(row.get('Adjusted_Close', row.get('Close', 0)))
                    })
                except (ValueError, TypeError):
                    raw_records.append({
                        "symbol": symbol.upper(),
                        "observation_date": date_str,
                        "close": close_val,
                        "open": row.get('Open'),
                        "high": row.get('High'),
                        "low": row.get('Low'),
                        "volume": row.get('Volume')
                    })

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_market_data(
            provider=self.name,
            symbol=symbol,
            exchange=exchange,
            records=raw_records,
            source_url_or_path=file_path,
            source_id=source_id
        )
        return result


class FallbackMarketDataProvider(BaseProvider):
    """
    Tiered Multi-Provider Price Ingestion Engine with Automatic Fallback:
    1. Primary Tier: DNSE Entrade Public Chart API
    2. Secondary Tier: VNDirect Finfo Public REST API
    3. Resilient Offline Tier: Canonical Local EOD CSV (data/market/<symbol>_historical.csv)

    Adheres strictly to Point-In-Time integrity, non-destructive same-date conflict protection,
    and automatic EOD CSV sync.
    """
    def __init__(self, dnse_timeout: float = 15.0, vndirect_timeout: float = 15.0):
        super().__init__("PRICE_FALLBACK_ENGINE")
        self.dnse_timeout = dnse_timeout
        self.vndirect_timeout = vndirect_timeout

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("FallbackMarketDataProvider only provides market data.")

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        is_index: bool = False
    ) -> List[MarketDataPoint]:
        """
        Attempts to fetch market data sequentially:
        DNSE -> VNDIRECT -> Local CSV.
        Returns the first non-empty dataset.
        """
        sym = symbol.upper().strip()
        # 1. Tier 1: DNSE
        try:
            from .dnse import DnseProvider
            dnse = DnseProvider(timeout=self.dnse_timeout)
            points = await dnse.fetch_market_data(sym, start_date, end_date, is_index=is_index)
            if points:
                return points
        except Exception as exc:
            pass

        # 2. Tier 2: VNDIRECT
        try:
            from .vndirect import VndirectProvider
            vnd = VndirectProvider(timeout=self.vndirect_timeout)
            points = await vnd.fetch_market_data(sym, start_date, end_date)
            if points:
                return points
        except Exception as exc:
            pass

        # 3. Tier 3: Local CSV Fallback
        csv_prov = MarketDataCsvProvider()
        return await csv_prov.fetch_market_data(sym, start_date, end_date)

    async def ingest_to_database(
        self,
        session: Session,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: str = "HOSE",
        source_ids: Optional[Dict[str, int]] = None,
        save_eod_csv: bool = True
    ) -> Dict[str, Any]:
        """
        Ingests market data with transparent fallback:
        Tier 1: DNSE -> Tier 2: VNDIRECT -> Tier 3: Local CSV.
        Preserves existing canonical bars (no conflict overwriting).
        """
        sym = symbol.upper().strip()
        source_ids = source_ids or {}

        # 1. Try DNSE
        try:
            from .dnse import DnseProvider
            dnse = DnseProvider(timeout=self.dnse_timeout)
            res = dnse.ingest_to_database(
                session=session,
                symbol=sym,
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
                source_id=source_ids.get("DNSE")
            )
            if res.get("status") in ("SUCCESS", "IDEMPOTENT_UNCHANGED", "PARTIAL") and res.get("records_valid", 0) > 0:
                res["provider_used"] = "DNSE"
                res["fallback_triggered"] = False
                if save_eod_csv:
                    self._sync_eod_csv(session, sym)
                return res
        except Exception as exc:
            pass

        # 2. Try VNDIRECT
        try:
            from .vndirect import VndirectProvider
            vnd = VndirectProvider(timeout=self.vndirect_timeout)
            res = await vnd.ingest_to_database(
                session=session,
                symbol=sym,
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
                source_id=source_ids.get("VNDIRECT")
            )
            if res.get("status") in ("SUCCESS", "IDEMPOTENT_UNCHANGED", "PARTIAL") and res.get("records_valid", 0) > 0:
                res["provider_used"] = "VNDIRECT"
                res["fallback_triggered"] = True
                res["fallback_tier"] = 2
                if save_eod_csv:
                    self._sync_eod_csv(session, sym)
                return res
        except Exception as exc:
            pass

        # 3. Fallback to Local CSV
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "market", f"{sym.lower()}_historical.csv"
        )
        if os.path.exists(csv_path):
            csv_prov = MarketDataCsvProvider()
            res = csv_prov.ingest_to_database(
                session=session,
                file_path=csv_path,
                symbol=sym,
                exchange=exchange,
                source_id=source_ids.get("HOSE_CSV")
            )
            res["provider_used"] = "HOSE_CSV"
            res["fallback_triggered"] = True
            res["fallback_tier"] = 3
            return res

        return {
            "status": "INSUFFICIENT_DATA",
            "symbol": sym,
            "provider_used": None,
            "fallback_triggered": True,
            "records_valid": 0,
            "reason": "All tiers (DNSE, VNDIRECT, Local CSV) exhausted or returned no data."
        }

    def _sync_eod_csv(self, session: Session, symbol: str) -> None:
        """Helper to safely sync latest canonical database bars to local EOD CSV backup."""
        from database.models import Price, Asset
        sym = symbol.upper().strip()
        csv_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "market"))
        os.makedirs(csv_dir, exist_ok=True)
        csv_path = os.path.join(csv_dir, f"{sym.lower()}_historical.csv")

        # Load all canonical prices from DB ordered by date
        bars = session.query(Price).join(Asset, Price.asset_id == Asset.id).filter(Asset.symbol == sym).order_by(Price.observation_date.asc()).all()
        if not bars:
            return

        # Write safely without corrupting format
        with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Open", "High", "Low", "Close", "Adjusted_Close", "Volume"])
            for b in bars:
                writer.writerow([
                    b.observation_date.isoformat(),
                    f"{float(b.raw_open or b.raw_close):.2f}",
                    f"{float(b.raw_high or b.raw_close):.2f}",
                    f"{float(b.raw_low or b.raw_close):.2f}",
                    f"{float(b.raw_close):.2f}",
                    f"{float(b.adjusted_close or b.raw_close):.2f}",
                    f"{float(b.volume or 0.0):.0f}"
                ])


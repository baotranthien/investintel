"""
VNDirect Public Market Data & Fundamentals Provider.
Fetches public OHLCV candles, company profiles, financial statements,
financial ratios, and corporate events from VNDirect Finfo API:
- Stock Prices: https://api-finfo.vndirect.com.vn/v4/stock_prices
- Company Profiles: https://api-finfo.vndirect.com.vn/v4/company_profiles
- Financial Statements: https://api-finfo.vndirect.com.vn/v4/financial_statements
- Financial Ratios: https://api-finfo.vndirect.com.vn/v4/ratios
- Corporate Events: https://api-finfo.vndirect.com.vn/v4/events

Authentication is NOT required.
Authority: REPUTABLE_SECONDARY.
Provides independent second-source verification alongside DNSE.
Prices in Finfo API are quoted in thousands of VND; scaled by 1,000 to canonical VND.
Financial statement figures in VND; scaled by 1,000,000,000 to BILLION_VND.
Publication date is preserved from `createdDate` (or disclosureDate) for strict Point-In-Time integrity.
"""
import hashlib
import json
import logging
import math
import re
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import httpx

from database.models import (
    Asset,
    FinancialStatement,
    NormalizedIncome,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    FinancialLineItem,
    FundamentalMetric,
    CorporateAction,
    EventRecord,
    DataLineage,
    DataRun,
    DataSource,
)
from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_FINFO_STOCK_PRICES_URL = "https://api-finfo.vndirect.com.vn/v4/stock_prices"
_FINFO_COMPANY_PROFILE_URL = "https://api-finfo.vndirect.com.vn/v4/company_profiles"
_FINFO_FINANCIAL_STATEMENTS_URL = "https://api-finfo.vndirect.com.vn/v4/financial_statements"
_FINFO_RATIOS_URL = "https://api-finfo.vndirect.com.vn/v4/ratios"
_FINFO_EVENTS_URL = "https://api-finfo.vndirect.com.vn/v4/events"

_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB cap
_PRICE_SCALE = 1000.0  # Finfo prices are quoted in kVND
_FINANCIAL_BILLION_SCALE = 1e9  # Raw VND to BILLION_VND

_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App; Multi-Provider)",
    "Accept": "application/json"
}

# Standard mapping: VNDirect itemCode -> Normalized field
INCOME_ITEM_MAP = {
    21001.0: "revenue",                  # Doanh thu thuần
    21000.0: "revenue",                  # Tổng doanh thu
    421701.0: "revenue",                 # Tổng thu nhập hoạt động (TOI - Ngân hàng)
    421900.0: "interest_income",         # Thu nhập lãi thuần (NII - Ngân hàng)
    422100.0: "interest_expense",        # Chi phí lãi và các chi phí tương tự (Ngân hàng)
    88888.0: "operating_income",         # Lợi nhuận thuần trước trích lập DPRR (Ngân hàng)
    22100.0: "cost_of_goods_sold",       # Giá vốn hàng bán
    23100.0: "gross_profit",             # Lợi nhuận gộp
    22110.0: "selling_expense",          # Chi phí bán hàng
    22200.0: "general_admin_expense",    # Chi phí quản lý DN
    23110.0: "operating_income",         # Lợi nhuận thuần từ HĐKD
    21500.0: "interest_income",          # Doanh thu tài chính
    22510.0: "interest_expense",         # Chi phí lãi vay
    21900.0: "other_income",             # Thu nhập khác
    22900.0: "other_expense",            # Chi phí khác
    23800.0: "pre_tax_income",           # Lợi nhuận trước thuế
    22070.0: "income_tax",               # Chi phí thuế TNDN
    23003.0: "net_income",               # Lợi nhuận sau thuế TNDN
    23000.0: "net_income_parent",        # Lợi nhuận sau thuế của công ty mẹ
    23500.0: "minority_interest",        # Lợi ích của cổ đông thiểu số
    23001.0: "eps_basic",                # Lãi cơ bản trên cổ phiếu (VND/share)
    700087.0: "eps_diluted",             # Lãi suy giảm trên cổ phiếu (VND/share)
}

BALANCE_ITEM_MAP = {
    11000.0: "total_current_assets",     # Tài sản ngắn hạn
    11100.0: "cash",                     # Tiền và tương đương tiền
    11200.0: "short_term_investments",   # Đầu tư tài chính ngắn hạn
    11300.0: "accounts_receivable",      # Phải thu ngắn hạn
    11400.0: "inventory",                # Hàng tồn kho
    11500.0: "other_current_assets",     # Tài sản ngắn hạn khác
    12200.0: "ppe",                      # Tài sản cố định
    12270.0: "intangibles",              # TSCĐ vô hình
    12500.0: "long_term_investments",    # Đầu tư tài chính dài hạn
    12600.0: "other_non_current_assets", # Tài sản dài hạn khác
    12700.0: "total_assets",             # Tổng cộng tài sản
    13000.0: "total_liabilities",        # Nợ phải trả
    13100.0: "total_current_liabilities",# Nợ ngắn hạn
    13110.0: "short_term_debt",          # Vay và nợ ngắn hạn
    13120.0: "accounts_payable",         # Phải trả người bán
    13340.0: "long_term_debt",           # Vay và nợ dài hạn
    14000.0: "total_equity",             # Vốn chủ sở hữu
    14110.0: "share_capital",            # Vốn góp
    14200.0: "retained_earnings",        # LN sau thuế chưa phân phối
    14240.0: "minority_interest",        # Lợi ích CĐ không kiểm soát
    # Banking specific items
    412100.0: "loans_and_advances",      # Cho vay khách hàng (Ngân hàng)
    412200.0: "provisions",              # Dự phòng rủi ro cho vay khách hàng (Ngân hàng)
    413300.0: "customer_deposits",       # Tiền gửi của khách hàng (Ngân hàng)
}

CASHFLOW_ITEM_MAP = {
    32000.0: "cash_from_operations",     # Lưu chuyển tiền thuần từ HĐKD
    932000.0: "cash_from_operations",    # LCTT từ HĐKD (gián tiếp)
    932001.0: "cash_from_operations",    # LCTT từ HĐKD (trực tiếp)
    32100.0: "capex",                    # Mua sắm TSCĐ (capex)
    33000.0: "cash_from_investing",      # Lưu chuyển tiền thuần từ HĐĐT
    933000.0: "cash_from_investing",     # LCTT từ HĐĐT
    34000.0: "cash_from_financing",      # Lưu chuyển tiền thuần từ HĐTC
    934000.0: "cash_from_financing",     # LCTT từ HĐTC
    33100.0: "share_issuance",           # Tiền thu từ phát hành CP
    33200.0: "share_buyback",            # Mua lại cổ phiếu
    33300.0: "debt_issued",              # Tiền vay nhận được
    33400.0: "debt_repaid",              # Tiền trả nợ gốc vay
    33600.0: "dividends_paid",           # Cổ tức đã trả
    22230.0: "depreciation_amortization",# Khấu hao TSCĐ
}


def normalize_symbol(symbol: str) -> str:
    """Uppercase, strips whitespace and non-alphanumeric characters."""
    if not symbol:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', symbol.strip()).upper()


def _coerce_float(val: Any) -> Optional[float]:
    """Coerces numeric values to float, handling nulls and NaNs safely."""
    try:
        x = float(val)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


class VndirectProvider(BaseProvider):
    """
    Public stock and fundamentals provider using VNDirect's unauthenticated finfo REST API.
    Provides:
    - OHLCV historical bars
    - Company profile
    - Financial statements (quarterly/annual)
    - Financial ratios
    - Corporate events
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("VNDIRECT")
        self.timeout = timeout
        self.endpoint_url = _FINFO_STOCK_PRICES_URL

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("VNDirect does not provide macroeconomic time series.")

    async def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Internal helper for robust GET requests with retries and rate limiting."""
        max_attempts = 3
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params, headers=_HEADERS)
                    if response.status_code == 429:
                        logger.warning("VNDirect rate limited (HTTP 429). Attempt %d/%d", attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("VNDirect rate limit exceeded")

                    if response.status_code >= 500:
                        logger.warning("VNDirect server error HTTP %d. Attempt %d/%d", response.status_code, attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"VNDirect server error: HTTP {response.status_code}")

                    if response.status_code == 404:
                        logger.info("VNDirect resource not found (HTTP 404) for %s", url)
                        return None

                    if response.status_code != 200:
                        logger.warning("VNDirect returned non-200 HTTP %d for %s", response.status_code, url)
                        return None

                    if len(response.content) > _MAX_RESPONSE_BYTES:
                        raise ProviderUnavailableError(f"VNDirect payload exceeded {_MAX_RESPONSE_BYTES} bytes")

                    return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning("VNDirect network error on attempt %d/%d: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"VNDirect endpoint unreachable: {exc}") from exc
        return None

    # ─────────────────────────────────────────────────────────────
    # MARKET DATA (OHLCV)
    # ─────────────────────────────────────────────────────────────

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[MarketDataPoint]:
        """Fetches OHLCV market candles from VNDirect Finfo API."""
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        q_filter = f"code:{norm_sym}~date:gte:{start_date.isoformat()}~date:lte:{end_date.isoformat()}"
        params = {
            "q": q_filter,
            "sort": "date:asc",
            "size": 500
        }

        data = await self._get_json(self.endpoint_url, params=params)
        if not data:
            return []

        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            return []

        candles: List[MarketDataPoint] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            close_raw = _coerce_float(item.get("close") or item.get("basicPrice"))
            if close_raw is None or close_raw <= 0:
                continue

            date_str = str(item.get("date") or "").strip()
            if not date_str:
                continue

            try:
                obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            open_raw = _coerce_float(item.get("open"))
            high_raw = _coerce_float(item.get("high"))
            low_raw = _coerce_float(item.get("low"))
            vol_raw = _coerce_float(item.get("nmVolume"))

            candles.append(MarketDataPoint(
                symbol=norm_sym,
                observation_date=obs_date,
                close=close_raw * _PRICE_SCALE,
                open=open_raw * _PRICE_SCALE if open_raw is not None else None,
                high=high_raw * _PRICE_SCALE if high_raw is not None else None,
                low=low_raw * _PRICE_SCALE if low_raw is not None else None,
                volume=vol_raw if vol_raw is not None and vol_raw >= 0 else None,
            ))

        return candles

    async def ingest_to_database(
        self,
        session: Session,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: str = "HOSE",
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Runs the canonical IngestionPipeline for VNDirect market bars."""
        points = await self.fetch_market_data(symbol, start_date, end_date)
        records = [p.model_dump() for p in points]
        pipeline = IngestionPipeline(session)
        norm_sym = normalize_symbol(symbol)
        source_url = f"{self.endpoint_url}?q=code:{norm_sym}"
        result = pipeline.ingest_market_data(
            provider=self.name,
            symbol=norm_sym,
            exchange=exchange,
            records=records,
            source_url_or_path=source_url,
            source_id=source_id
        )
        return result

    # ─────────────────────────────────────────────────────────────
    # COMPANY PROFILE
    # ─────────────────────────────────────────────────────────────

    async def fetch_company_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetches company profile from VNDirect finfo."""
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return None
        params = {"q": f"code:{norm_sym}"}
        data = await self._get_json(_FINFO_COMPANY_PROFILE_URL, params=params)
        if not data:
            return None
        items = data.get("data") or []
        if isinstance(items, list) and items:
            return items[0]
        return None

    async def ingest_company_profile(
        self,
        session: Session,
        symbol: str,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Updates Asset record with verified company profile data and creates lineage."""
        norm_sym = normalize_symbol(symbol)
        profile = await self.fetch_company_profile(norm_sym)
        if not profile:
            return {"status": "INSUFFICIENT_DATA", "symbol": norm_sym}

        asset = session.query(Asset).filter(Asset.symbol == norm_sym).first()
        if not asset:
            asset = Asset(
                symbol=norm_sym,
                name=profile.get("vnName") or norm_sym,
                asset_type="STOCK",
                exchange=profile.get("floor") or "HOSE",
                currency="VND",
                status="ACTIVE"
            )
            session.add(asset)
            session.flush()
        else:
            if profile.get("vnName"):
                asset.name = profile.get("vnName")
            if profile.get("floor"):
                asset.exchange = profile.get("floor")

        # Record lineage
        source_url = f"{_FINFO_COMPANY_PROFILE_URL}?q=code:{norm_sym}"
        payload_bytes = json.dumps(profile, sort_keys=True).encode("utf-8")
        lineage = DataLineage(
            record_table="assets",
            record_id=str(asset.id),
            raw_source=f"VNDIRECT_PROFILE [symbol={norm_sym}]",
            url=source_url,
            retrieved_at=datetime.now(timezone.utc),
            checksum=hashlib.sha256(payload_bytes).hexdigest()
        )
        session.add(lineage)
        session.commit()
        return {"status": "SUCCESS", "symbol": norm_sym, "asset_id": asset.id}

    # ─────────────────────────────────────────────────────────────
    # FINANCIAL STATEMENTS (QUARTERLY & ANNUAL)
    # ─────────────────────────────────────────────────────────────

    async def fetch_financial_statements(
        self,
        symbol: str,
        report_type: str = "QUARTER",
        size: int = 500,
        max_pages: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetches line items from VNDirect finfo financial_statements with automatic pagination support.
        report_type: 'QUARTER' or 'YEAR'.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        all_items: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            params = {
                "q": f"code:{norm_sym}~reportType:{report_type}",
                "sort": "fiscalDate:desc",
                "size": size,
                "page": page
            }
            data = await self._get_json(_FINFO_FINANCIAL_STATEMENTS_URL, params=params)
            if not data:
                break
            items = data.get("data") or []
            if not isinstance(items, list) or not items:
                break
            all_items.extend(items)
            if len(items) < size:
                break
        return all_items

    async def ingest_fundamentals(
        self,
        session: Session,
        symbol: str,
        report_type: str = "QUARTER",
        periods_limit: int = 8,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ingests financial statements from VNDirect into canonical tables:
        FinancialStatement, NormalizedIncome, NormalizedBalanceSheet, NormalizedCashFlow, FinancialLineItem.
        Preserves createdDate as publication_date for Point-In-Time integrity.
        """
        norm_sym = normalize_symbol(symbol)
        needed_pages = max(1, min(10, math.ceil((periods_limit * 210) / 1000)))
        raw_items = await self.fetch_financial_statements(norm_sym, report_type=report_type, size=1000, max_pages=needed_pages)
        if not raw_items:
            return {"status": "INSUFFICIENT_DATA", "symbol": norm_sym, "statements_ingested": 0}

        asset = session.query(Asset).filter(Asset.symbol == norm_sym).first()
        if not asset:
            asset = Asset(symbol=norm_sym, name=norm_sym, asset_type="STOCK", exchange="HOSE")
            session.add(asset)
            session.flush()

        # Group items by fiscalDate
        by_fiscal_date: Dict[str, List[Dict[str, Any]]] = {}
        for it in raw_items:
            fdate = it.get("fiscalDate")
            if fdate:
                by_fiscal_date.setdefault(fdate, []).append(it)

        # Sort dates descending and take up to periods_limit
        sorted_dates = sorted(by_fiscal_date.keys(), reverse=True)[:periods_limit]
        statements_created = 0

        for fdate_str in sorted_dates:
            period_items = by_fiscal_date[fdate_str]
            try:
                fiscal_end = datetime.strptime(fdate_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            fiscal_year = fiscal_end.year
            # Determine quarter
            quarter = (fiscal_end.month - 1) // 3 + 1 if report_type == "QUARTER" else None
            period_type_val = "QUARTERLY" if report_type == "QUARTER" else "ANNUAL"

            # Parse earliest createdDate as real publication date
            pub_date = None
            for it in period_items:
                cdate_str = str(it.get("createdDate") or "")[:10]
                if cdate_str:
                    try:
                        cd = datetime.strptime(cdate_str, "%Y-%m-%d").date()
                        if pub_date is None or cd < pub_date:
                            pub_date = cd
                    except ValueError:
                        pass
            if pub_date is None:
                pub_date = fiscal_end

            # Map raw item codes by modelType
            inc_data: Dict[str, float] = {}
            bs_data: Dict[str, float] = {}
            cf_data: Dict[str, float] = {}

            for it in period_items:
                icode = _coerce_float(it.get("itemCode"))
                nval = _coerce_float(it.get("numericValue"))
                mtype = _coerce_float(it.get("modelType"))
                if icode is None or nval is None:
                    continue

                if mtype in (2.0, 102.0, 202.0, 302.0) or icode in INCOME_ITEM_MAP:
                    field = INCOME_ITEM_MAP.get(icode)
                    if field:
                        # EPS is VND/share; revenue/totals are scaled to BILLION_VND
                        if field in ("eps_basic", "eps_diluted"):
                            inc_data[field] = nval
                        else:
                            inc_data[field] = nval / _FINANCIAL_BILLION_SCALE

                if mtype in (1.0, 101.0, 201.0, 301.0) or icode in BALANCE_ITEM_MAP:
                    field = BALANCE_ITEM_MAP.get(icode)
                    if field:
                        bs_data[field] = nval / _FINANCIAL_BILLION_SCALE

                if mtype in (3.0, 103.0, 203.0, 303.0) or icode in CASHFLOW_ITEM_MAP:
                    field = CASHFLOW_ITEM_MAP.get(icode)
                    if field:
                        cf_data[field] = nval / _FINANCIAL_BILLION_SCALE

            # 1. Promote Income Statement
            if inc_data.get("revenue") is not None or inc_data.get("net_income") is not None:
                existing_inc = session.query(FinancialStatement).filter(
                    FinancialStatement.symbol == norm_sym,
                    FinancialStatement.statement_type == "INCOME_STATEMENT",
                    FinancialStatement.fiscal_period_end == fiscal_end,
                    FinancialStatement.period_type == period_type_val,
                    FinancialStatement.version == 1
                ).first()

                if not existing_inc:
                    stmt_inc = FinancialStatement(
                        asset_id=asset.id,
                        symbol=norm_sym,
                        statement_type="INCOME_STATEMENT",
                        fiscal_period_start=date(fiscal_year, 1, 1) if period_type_val == "ANNUAL" else date(fiscal_year, (quarter - 1) * 3 + 1, 1),
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        statement_date=fiscal_end,
                        publication_date=pub_date,
                        consolidation="CONSOLIDATED",
                        source_id=source_id,
                        source_name="VNDIRECT_FINFO",
                        source_url=_FINFO_FINANCIAL_STATEMENTS_URL,
                        currency="VND",
                        unit_scale="BILLION_VND",
                        version=1,
                        status="VALID",
                        raw_data={"item_count": len(period_items), "fiscal_date": fdate_str}
                    )
                    session.add(stmt_inc)
                    session.flush()

                    norm_inc = NormalizedIncome(
                        statement_id=stmt_inc.id,
                        symbol=norm_sym,
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        revenue=inc_data.get("revenue"),
                        cost_of_goods_sold=inc_data.get("cost_of_goods_sold"),
                        gross_profit=inc_data.get("gross_profit"),
                        selling_expense=inc_data.get("selling_expense"),
                        general_admin_expense=inc_data.get("general_admin_expense"),
                        operating_income=inc_data.get("operating_income"),
                        interest_income=inc_data.get("interest_income"),
                        interest_expense=inc_data.get("interest_expense"),
                        other_income=inc_data.get("other_income"),
                        other_expense=inc_data.get("other_expense"),
                        pre_tax_income=inc_data.get("pre_tax_income"),
                        income_tax=inc_data.get("income_tax"),
                        net_income=inc_data.get("net_income"),
                        net_income_parent=inc_data.get("net_income_parent"),
                        minority_interest=inc_data.get("minority_interest"),
                        eps_basic=inc_data.get("eps_basic"),
                        eps_diluted=inc_data.get("eps_diluted"),
                    )
                    session.add(norm_inc)

                    # Add sample canonical line item
                    if inc_data.get("revenue") is not None:
                        session.add(FinancialLineItem(
                            statement_id=stmt_inc.id,
                            raw_label="21001.0_REVENUE",
                            canonical_metric="revenue",
                            canonical_section="income",
                            raw_value=Decimal(str(round(inc_data["revenue"], 4))),
                            currency="VND",
                            unit_scale="BILLION_VND",
                            data_quality="VALID",
                            mapping_version="vndirect_v1"
                        ))

                    # Lineage
                    session.add(DataLineage(
                        record_table="financial_statements",
                        record_id=str(stmt_inc.id),
                        raw_source=f"VNDIRECT_FS [INCOME_STATEMENT, {period_type_val}, {fiscal_end}]",
                        url=f"{_FINFO_FINANCIAL_STATEMENTS_URL}?q=code:{norm_sym}~fiscalDate:{fdate_str}",
                        retrieved_at=datetime.now(timezone.utc),
                        checksum=hashlib.sha256(f"{norm_sym}_{fdate_str}_inc".encode()).hexdigest()
                    ))
                    statements_created += 1

            # 2. Promote Balance Sheet
            if (bs_data.get("total_assets") is not None or bs_data.get("total_equity") is not None 
                    or bs_data.get("total_liabilities") is not None or bs_data.get("loans_and_advances") is not None):
                existing_bs = session.query(FinancialStatement).filter(
                    FinancialStatement.symbol == norm_sym,
                    FinancialStatement.statement_type == "BALANCE_SHEET",
                    FinancialStatement.fiscal_period_end == fiscal_end,
                    FinancialStatement.period_type == period_type_val,
                    FinancialStatement.version == 1
                ).first()

                if not existing_bs:
                    stmt_bs = FinancialStatement(
                        asset_id=asset.id,
                        symbol=norm_sym,
                        statement_type="BALANCE_SHEET",
                        fiscal_period_start=date(fiscal_year, 1, 1),
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        statement_date=fiscal_end,
                        publication_date=pub_date,
                        consolidation="CONSOLIDATED",
                        source_id=source_id,
                        source_name="VNDIRECT_FINFO",
                        source_url=_FINFO_FINANCIAL_STATEMENTS_URL,
                        currency="VND",
                        unit_scale="BILLION_VND",
                        version=1,
                        status="VALID",
                        raw_data={"item_count": len(period_items), "fiscal_date": fdate_str}
                    )
                    session.add(stmt_bs)
                    session.flush()

                    norm_bs = NormalizedBalanceSheet(
                        statement_id=stmt_bs.id,
                        symbol=norm_sym,
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        cash=bs_data.get("cash"),
                        short_term_investments=bs_data.get("short_term_investments"),
                        accounts_receivable=bs_data.get("accounts_receivable"),
                        inventory=bs_data.get("inventory"),
                        other_current_assets=bs_data.get("other_current_assets"),
                        total_current_assets=bs_data.get("total_current_assets"),
                        ppe=bs_data.get("ppe"),
                        intangibles=bs_data.get("intangibles"),
                        long_term_investments=bs_data.get("long_term_investments"),
                        other_non_current_assets=bs_data.get("other_non_current_assets"),
                        total_assets=bs_data.get("total_assets"),
                        short_term_debt=bs_data.get("short_term_debt"),
                        accounts_payable=bs_data.get("accounts_payable"),
                        total_current_liabilities=bs_data.get("total_current_liabilities"),
                        long_term_debt=bs_data.get("long_term_debt"),
                        total_liabilities=bs_data.get("total_liabilities"),
                        share_capital=bs_data.get("share_capital"),
                        retained_earnings=bs_data.get("retained_earnings"),
                        minority_interest=bs_data.get("minority_interest"),
                        total_equity=bs_data.get("total_equity"),
                        equity_parent=bs_data.get("total_equity"),
                        loans_and_advances=bs_data.get("loans_and_advances"),
                        customer_deposits=bs_data.get("customer_deposits"),
                        provisions=bs_data.get("provisions")
                    )
                    session.add(norm_bs)

                    session.add(DataLineage(
                        record_table="financial_statements",
                        record_id=str(stmt_bs.id),
                        raw_source=f"VNDIRECT_FS [BALANCE_SHEET, {period_type_val}, {fiscal_end}]",
                        url=f"{_FINFO_FINANCIAL_STATEMENTS_URL}?q=code:{norm_sym}~fiscalDate:{fdate_str}",
                        retrieved_at=datetime.now(timezone.utc),
                        checksum=hashlib.sha256(f"{norm_sym}_{fdate_str}_bs".encode()).hexdigest()
                    ))
                    statements_created += 1

            # 3. Promote Cash Flow
            if (cf_data.get("cash_from_operations") is not None 
                    or cf_data.get("cash_from_investing") is not None 
                    or cf_data.get("cash_from_financing") is not None):
                existing_cf = session.query(FinancialStatement).filter(
                    FinancialStatement.symbol == norm_sym,
                    FinancialStatement.statement_type == "CASH_FLOW",
                    FinancialStatement.fiscal_period_end == fiscal_end,
                    FinancialStatement.period_type == period_type_val,
                    FinancialStatement.version == 1
                ).first()

                if not existing_cf:
                    stmt_cf = FinancialStatement(
                        asset_id=asset.id,
                        symbol=norm_sym,
                        statement_type="CASH_FLOW",
                        fiscal_period_start=date(fiscal_year, 1, 1),
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        statement_date=fiscal_end,
                        publication_date=pub_date,
                        consolidation="CONSOLIDATED",
                        source_id=source_id,
                        source_name="VNDIRECT_FINFO",
                        source_url=_FINFO_FINANCIAL_STATEMENTS_URL,
                        currency="VND",
                        unit_scale="BILLION_VND",
                        version=1,
                        status="VALID",
                        raw_data={"item_count": len(period_items), "fiscal_date": fdate_str}
                    )
                    session.add(stmt_cf)
                    session.flush()

                    cfo = cf_data.get("cash_from_operations")
                    capex = cf_data.get("capex")
                    fcf = (cfo + capex) if (cfo is not None and capex is not None) else cfo

                    norm_cf = NormalizedCashFlow(
                        statement_id=stmt_cf.id,
                        symbol=norm_sym,
                        fiscal_period_end=fiscal_end,
                        fiscal_year=fiscal_year,
                        fiscal_quarter=quarter,
                        period_type=period_type_val,
                        cash_from_operations=cfo,
                        cash_from_investing=cf_data.get("cash_from_investing"),
                        cash_from_financing=cf_data.get("cash_from_financing"),
                        capex=capex,
                        dividends_paid=cf_data.get("dividends_paid"),
                        debt_issued=cf_data.get("debt_issued"),
                        debt_repaid=cf_data.get("debt_repaid"),
                        share_issuance=cf_data.get("share_issuance"),
                        share_buyback=cf_data.get("share_buyback"),
                        depreciation_amortization=cf_data.get("depreciation_amortization"),
                        free_cash_flow=fcf
                    )
                    session.add(norm_cf)

                    session.add(DataLineage(
                        record_table="financial_statements",
                        record_id=str(stmt_cf.id),
                        raw_source=f"VNDIRECT_FS [CASH_FLOW, {period_type_val}, {fiscal_end}]",
                        url=f"{_FINFO_FINANCIAL_STATEMENTS_URL}?q=code:{norm_sym}~fiscalDate:{fdate_str}",
                        retrieved_at=datetime.now(timezone.utc),
                        checksum=hashlib.sha256(f"{norm_sym}_{fdate_str}_cf".encode()).hexdigest()
                    ))
                    statements_created += 1

        session.commit()
        return {
            "status": "SUCCESS" if statements_created > 0 else "IDEMPOTENT_UNCHANGED",
            "symbol": norm_sym,
            "statements_created": statements_created,
            "periods_processed": len(sorted_dates)
        }

    # ─────────────────────────────────────────────────────────────
    # FINANCIAL RATIOS
    # ─────────────────────────────────────────────────────────────

    async def fetch_ratios(self, symbol: str, size: int = 100) -> List[Dict[str, Any]]:
        """Fetches financial ratios from VNDirect finfo."""
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []
        params = {
            "q": f"code:{norm_sym}",
            "sort": "reportDate:desc",
            "size": size
        }
        data = await self._get_json(_FINFO_RATIOS_URL, params=params)
        if not data:
            return []
        items = data.get("data") or []
        return items if isinstance(items, list) else []

    async def ingest_ratios(
        self,
        session: Session,
        symbol: str,
        size: int = 50,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Ingests VNDirect ratios into FundamentalMetric table with reportDate provenance."""
        norm_sym = normalize_symbol(symbol)
        ratios_raw = await self.fetch_ratios(norm_sym, size=size)
        if not ratios_raw:
            return {"status": "INSUFFICIENT_DATA", "symbol": norm_sym, "ratios_ingested": 0}

        metrics_created = 0
        for it in ratios_raw:
            ratio_code = str(it.get("ratioCode") or "").strip()
            val = _coerce_float(it.get("value"))
            rdate_str = str(it.get("reportDate") or "").strip()
            item_name = str(it.get("itemName") or "").strip()

            if not ratio_code or val is None or not rdate_str:
                continue

            try:
                rdate = datetime.strptime(rdate_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Check existing metric
            existing = session.query(FundamentalMetric).filter(
                FundamentalMetric.symbol == norm_sym,
                FundamentalMetric.fiscal_period_end == rdate,
                FundamentalMetric.period_type == "POINT_IN_TIME",
                FundamentalMetric.metric_id == ratio_code,
                FundamentalMetric.calculation_version == "vndirect_ratio_v1"
            ).first()

            if not existing:
                metric = FundamentalMetric(
                    symbol=norm_sym,
                    fiscal_period_end=rdate,
                    period_type="POINT_IN_TIME",
                    metric_id=ratio_code,
                    metric_category="FINANCIAL_RATIO",
                    metric_name=item_name or ratio_code,
                    calculation_version="vndirect_ratio_v1",
                    value=Decimal(str(round(val, 8))),
                    unit="RATIO",
                    value_status="VALID",
                    as_of_publication_date=rdate,
                    data_status="VALID"
                )
                session.add(metric)
                metrics_created += 1

        session.commit()
        return {
            "status": "SUCCESS" if metrics_created > 0 else "IDEMPOTENT_UNCHANGED",
            "symbol": norm_sym,
            "metrics_created": metrics_created
        }

    # ─────────────────────────────────────────────────────────────
    # CORPORATE EVENTS & ACTIONS
    # ─────────────────────────────────────────────────────────────

    async def fetch_events(self, symbol: str, size: int = 50) -> List[Dict[str, Any]]:
        """Fetches corporate events from VNDirect finfo."""
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []
        params = {
            "q": f"code:{norm_sym}",
            "sort": "disclosureDate:desc",
            "size": size
        }
        data = await self._get_json(_FINFO_EVENTS_URL, params=params)
        if not data:
            return []
        items = data.get("data") or []
        return items if isinstance(items, list) else []

    async def ingest_events(
        self,
        session: Session,
        symbol: str,
        size: int = 30,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ingests corporate events into CorporateAction and EventRecord canonical tables.
        Preserves disclosureDate as published_at.
        """
        norm_sym = normalize_symbol(symbol)
        events_raw = await self.fetch_events(norm_sym, size=size)
        if not events_raw:
            return {"status": "INSUFFICIENT_DATA", "symbol": norm_sym, "events_ingested": 0}

        actions_created = 0
        event_records_created = 0

        for it in events_raw:
            ev_id = str(it.get("id") or "")
            ev_type = str(it.get("type") or "CORPORATE_EVENT")
            type_desc = str(it.get("typeDesc") or "")
            note = str(it.get("note") or "")
            disc_date_str = str(it.get("disclosureDate") or "").strip()
            shares = _coerce_float(it.get("numberOfShares"))

            if not disc_date_str:
                continue

            try:
                disc_date = datetime.strptime(disc_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # 1. Promote to CorporateAction if dividend, split, rights or listing change
            action_type = "CORPORATE_EVENT"
            ev_type_lower = ev_type.lower()
            if "dividend" in ev_type_lower:
                action_type = "CASH_DIVIDEND" if "cash" in ev_type_lower else "STOCK_DIVIDEND"
            elif "split" in ev_type_lower:
                action_type = "STOCK_SPLIT"
            elif "right" in ev_type_lower:
                action_type = "RIGHTS_ISSUE"
            elif "listed" in ev_type_lower:
                action_type = "LISTING_CHANGE"

            existing_action = session.query(CorporateAction).filter(
                CorporateAction.symbol == norm_sym,
                CorporateAction.action_date == disc_date,
                CorporateAction.action_type == action_type,
                CorporateAction.notes == (note or type_desc)
            ).first()

            if not existing_action:
                ca = CorporateAction(
                    symbol=norm_sym,
                    action_date=disc_date,
                    action_type=action_type,
                    value=Decimal(str(shares)) if shares is not None else None,
                    currency="VND",
                    record_date=disc_date,
                    source="VNDIRECT_EVENTS",
                    notes=note or type_desc
                )
                session.add(ca)
                actions_created += 1

            # 2. Promote to canonical EventRecord
            canonical_ev_id = f"vnd-{norm_sym}-{ev_id}" if ev_id else f"vnd-{norm_sym}-{disc_date_str}-{actions_created}"
            existing_event = session.query(EventRecord).filter(EventRecord.id == canonical_ev_id).first()
            if not existing_event:
                pub_dt = datetime.combine(disc_date, datetime.min.time(), tzinfo=timezone.utc)
                er = EventRecord(
                    id=canonical_ev_id,
                    title=f"{norm_sym}: {type_desc or action_type}",
                    description=note or type_desc or f"Corporate action for {norm_sym}",
                    event_type="Earnings" if "dividend" in ev_type_lower else "Corporate",
                    materiality="MATERIAL" if ("dividend" in ev_type_lower or "split" in ev_type_lower or "right" in ev_type_lower) else "INFORMATIONAL",
                    severity=50.0,
                    sentiment="POSITIVE" if "dividend" in ev_type_lower else "NEUTRAL",
                    countries=["VN"],
                    affected_sectors=[],
                    sources=[f"https://api-finfo.vndirect.com.vn/v4/events?q=code:{norm_sym}"],
                    source_id=source_id,
                    published_at=pub_dt,
                    retrieved_at=datetime.now(timezone.utc),
                    as_of_date=disc_date
                )
                session.add(er)
                event_records_created += 1

        session.commit()
        return {
            "status": "SUCCESS" if (actions_created > 0 or event_records_created > 0) else "IDEMPOTENT_UNCHANGED",
            "symbol": norm_sym,
            "corporate_actions_created": actions_created,
            "event_records_created": event_records_created
        }

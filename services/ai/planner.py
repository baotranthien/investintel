"""
Deterministic Query Planner for InvestIntel AI Analyst.
Analyzes user financial queries to determine entity types, symbols, intent, 
requested metric categories, and routing requirements before data retrieval or LLM execution.
"""
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import re
from typing import Any, Optional
from sqlalchemy.orm import Session

from services.universe.registry import UniverseRegistry


class EntityType(str, Enum):
    TICKER = "TICKER"
    MULTI_TICKER = "MULTI_TICKER"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"
    UNIVERSE = "UNIVERSE"
    GENERAL = "GENERAL"


class QueryIntent(str, Enum):
    FUNDAMENTAL = "FUNDAMENTAL"
    VALUATION_DCF = "VALUATION_DCF"
    PEER_COMPARISON = "PEER_COMPARISON"
    TIME_SERIES_CORRELATION = "TIME_SERIES_CORRELATION"
    MARKET_REGIME = "MARKET_REGIME"
    SCREENER = "SCREENER"
    DIVIDEND = "DIVIDEND"
    PORTFOLIO = "PORTFOLIO"
    UNKNOWN = "UNKNOWN"


@dataclass
class ScreenerFilterSpec:
    universe: str = "ALL"
    pe_min: Optional[float] = None
    pe_max: Optional[float] = None
    pb_min: Optional[float] = None
    pb_max: Optional[float] = None
    roe_min: Optional[float] = None
    gross_margin_min: Optional[float] = None
    net_margin_min: Optional[float] = None
    de_ratio_max: Optional[float] = None


@dataclass
class QueryPlan:
    raw_query: str
    entity_type: EntityType
    symbols: list[str]
    intent: QueryIntent
    requested_metric_groups: dict[str, set[str]]
    screener_spec: Optional[ScreenerFilterSpec] = None
    special_routing: dict[str, Any] = field(default_factory=dict)
    asks_intraday: bool = False
    asks_horizon: bool = False


class QueryPlanner:
    """Deterministic, rules-based query parser and planner."""

    @staticmethod
    def plan_query(
        query: str,
        session: Session,
        explicit_symbol: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> QueryPlan:
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # 1. Symbol resolution
        symbols: list[str] = []
        if explicit_symbol:
            resolved = UniverseRegistry.resolve_instrument(session, explicit_symbol)
            sym = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(explicit_symbol) or explicit_symbol.upper())
            symbols = [sym]
            if session is not None and hasattr(session, "query"):
                text_symbols = UniverseRegistry.extract_all_symbols_from_text(q_clean, session)
                for extra in text_symbols:
                    if extra in symbols:
                        continue
                    extra_res = UniverseRegistry.resolve_instrument(session, extra)
                    if extra_res and extra_res.source in {
                        "DATABASE_ASSET",
                        "VN100_CONSTITUENTS_JSON",
                        "VN30_CONSTITUENTS_JSON",
                        "CANONICAL_DATABASE",
                    }:
                        symbols.append(extra_res.symbol)
        else:
            symbols = UniverseRegistry.extract_all_symbols_from_text(q_clean, session)

        # 2. Check for broad universe screener queries (e.g. Q19: P/E < 15, ROE > 15)
        is_screener_query = bool(
            re.search(r"\b(tìm\s*các\s*cổ\s*phiếu|lọc\s*cổ\s*phiếu|thỏa\s*mãn\s*tiêu\s*chí|bộ\s*lọc|định\s*giá\s*rẻ\s*p\/e|chọn\s*lọc\s*cổ\s*phiếu)\b", q_lower)
            or (not symbols and re.search(r"\b(những\s*cổ\s*phiếu\s*nào|cổ\s*phiếu\s*nào\s*đang\s*có|cơ\s*hội\s*đầu\s*tư\s*hấp\s*dẫn)\b", q_lower))
            or (re.search(r"\bp\/e\b.*?\b(?:dưới|<|thấp\s*hơn|nhỏ\s*hơn)\b", q_lower) and re.search(r"\broe\b.*?\b(?:trên|>|cao\s*hơn|lớn\s*hơn)\b", q_lower))
            or (re.search(r"\b(toàn\s*bộ\s*vũ\s*trụ|toàn\s*thị\s*trường|vũ\s*trụ\s*đầu\s*tư)\b", q_lower) and ("p/e" in q_lower or "roe" in q_lower))
        )

        screener_spec: Optional[ScreenerFilterSpec] = None
        if is_screener_query:
            screener_spec = ScreenerFilterSpec()
            # Extract P/E thresholds
            pe_match = re.search(r"\bp\/e\s*(?:dưới|<|thấp\s*hơn|nhỏ\s*hơn|<=|≤)\s*(\d+(?:[.,]\d+)?)\b", q_lower)
            if pe_match:
                screener_spec.pe_max = float(pe_match.group(1).replace(",", "."))
            # Extract ROE thresholds
            roe_match = re.search(r"\broe\s*(?:trên|>|cao\s*hơn|lớn\s*hơn|>=|≥)\s*(\d+(?:[.,]\d+)?)\b", q_lower)
            if roe_match:
                screener_spec.roe_min = float(roe_match.group(1).replace(",", "."))

        # 3. Check for Market Regime queries (Q8: VNINDEX / VN100 / Market Regime / Breadth)
        is_market_regime_query = bool(
            re.search(r"\b(chế\s*độ\s*thị\s*trường|market\s*regime|độ\s*rộng(?:\s*thị\s*trường)?|breadth|xu\s*hướng\s*thị\s*trường|thị\s*trường\s*chứng\s*khoán\s*việt\s*nam)\b", q_lower)
            or ("vnindex" in q_lower or "vn-index" in q_lower or "vn100" in q_lower) and any(w in q_lower for w in ("chế độ", "regime", "độ rộng", "tổng quan", "xu hướng"))
        )

        # 4. Check for Portfolio Allocation query
        portfolio_terms = (
            "danh mục", "danh muc", "phân bổ", "phan bo", "portfolio", "allocation",
            "tài sản", "tai san", "100 triệu", "đa dạng hóa", "da dang hoa", "chiến lược",
        )
        is_portfolio_query = any(term in q_lower for term in portfolio_terms) and not symbols

        # 5. Check for Peer Comparison (Q6, Q17: trung vị ngành, so với ngành, peers)
        is_peer_comparison_query = bool(
            re.search(r"\b(trung\s*vị\s*ngành|peer\s*median|bình\s*quân\s*ngành|so\s*với\s*ngành|so\s*với\s*các\s*doanh\s*nghiệp\s*cùng\s*ngành|materials\s*peers|cùng\s*ngành)\b", q_lower)
        )

        # 6. Check for DCF / Intrinsic Valuation (Q11: DCF, Base Case, kịch bản cơ sở, fair value)
        is_dcf_query = bool(
            re.search(r"\b(dcf|chiết\s*khấu\s*dòng\s*tiền|kịch\s*bản\s*cơ\s*sở|base\s*case|fair\s*value|giá\s*trị\s*hợp\s*lý)\b", q_lower)
        )

        # 7. Check for Commodity / Time Series Correlation (Q7: PLX vs Brent, tương quan doanh thu/giá)
        is_correlation_query = bool(
            re.search(r"\b(tương\s*quan|correlation|pearson)\b", q_lower)
            and any(w in q_lower for w in ("dầu", "oil", "brent", "wti", "hàng hóa", "commodity"))
        )

        # 8. Check for Dividend queries (Q15: cổ tức, dividend yield)
        is_dividend_query = bool(
            re.search(r"\b(cổ\s*tức|dividend|dividend\s*yield|tỷ\s*suất\s*cổ\s*tức|chi\s*trả\s*cổ\s*tức)\b", q_lower)
        )

        # 9. Determine Entity Type
        if is_screener_query:
            entity_type = EntityType.UNIVERSE
            if not symbols:
                symbols = ["ALL"]
        elif is_market_regime_query and not [s for s in symbols if s not in ("VNINDEX", "VN100")]:
            entity_type = EntityType.INDEX
            if not symbols:
                symbols = ["VN100"]
        elif len(symbols) > 1:
            entity_type = EntityType.MULTI_TICKER
        elif len(symbols) == 1:
            sym0 = symbols[0].upper()
            if sym0 in ("VNINDEX", "VN100", "VN30"):
                entity_type = EntityType.INDEX
            elif sym0 in ("BRENT", "WTI", "GOLD"):
                entity_type = EntityType.COMMODITY
            else:
                entity_type = EntityType.TICKER
        elif is_portfolio_query:
            entity_type = EntityType.UNIVERSE
            symbols = ["VN100"]
        else:
            entity_type = EntityType.GENERAL

        # 10. Determine Intent
        if is_screener_query:
            intent = QueryIntent.SCREENER
        elif is_dcf_query:
            intent = QueryIntent.VALUATION_DCF
        elif is_peer_comparison_query:
            intent = QueryIntent.PEER_COMPARISON
        elif is_correlation_query:
            intent = QueryIntent.TIME_SERIES_CORRELATION
        elif is_market_regime_query:
            intent = QueryIntent.MARKET_REGIME
        elif is_dividend_query:
            intent = QueryIntent.DIVIDEND
        elif is_portfolio_query:
            intent = QueryIntent.PORTFOLIO
        else:
            intent = QueryIntent.FUNDAMENTAL

        # 11. Extract requested metric groups from registry
        from services.ai.prompt_registry import extract_requested_metric_groups
        requested_metric_groups = extract_requested_metric_groups(q_clean)

        # Special overrides based on intent
        if intent == QueryIntent.VALUATION_DCF:
            requested_metric_groups.setdefault("dcf", {"dcf_fair_value", "dcf_base", "composite_fair_value"})
        elif intent == QueryIntent.PEER_COMPARISON:
            requested_metric_groups.setdefault("peer_medians", {"peer_median_pe", "peer_median_pb", "peer_median_roe"})
        elif intent == QueryIntent.SCREENER:
            requested_metric_groups.setdefault("screener", {"screened_count", "matched_count", "matching_symbols"})
        elif intent == QueryIntent.MARKET_REGIME:
            requested_metric_groups.setdefault("market_regime", {"market_regime", "breadth_advancing", "breadth_declining", "market_breadth_pct"})

        # Intraday and Horizon flags
        asks_intraday = bool(re.search(r"\b(?:1[0-9]|2[0-3]|0?[0-9]):[0-5][0-9]\b", q_clean))
        asks_horizon = any(term in q_lower for term in (
            "horizon", "investment period", "time horizon", "thời hạn", "kỳ hạn", "đầu tư bao lâu",
        ))

        # Special routing flags
        special_routing: dict[str, Any] = {
            "is_screener": is_screener_query,
            "is_dcf": is_dcf_query,
            "is_peer_comparison": is_peer_comparison_query,
            "is_market_regime": is_market_regime_query,
            "is_correlation": is_correlation_query,
        }

        return QueryPlan(
            raw_query=q_clean,
            entity_type=entity_type,
            symbols=symbols,
            intent=intent,
            requested_metric_groups=requested_metric_groups,
            screener_spec=screener_spec,
            special_routing=special_routing,
            asks_intraday=asks_intraday,
            asks_horizon=asks_horizon,
        )


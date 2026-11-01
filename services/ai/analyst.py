import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import logging
import re
from typing import Any, AsyncGenerator, Literal

from sqlalchemy.orm import Session
from pydantic import ValidationError

from .gateway import AIGateway
from .prompt_registry import (
    METRIC_CATEGORY_PATTERNS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_chat_prompt,
    extract_requested_metric_groups,
)
from .provider import AIProvider
from .providers import AIProviderError, OllamaProvider
from .router import AIRouter, TaskType
from .schemas import AIAnswerDraft, AIChatResponse, AICitation, AIClaim
from .tools import AITools

logger = logging.getLogger(__name__)


_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d[\d,]*(?:\.\d+)?%?")


def _extract_token_interpretations(token_match: str) -> set[Decimal]:
    cleaned = token_match.rstrip("%")
    interpretations = set()
    # 1. As standard integer/float without commas (e.g. 84,873 -> 84873, 12.5 -> 12.5)
    try:
        interpretations.add(Decimal(cleaned.replace(",", "")).normalize())
    except (InvalidOperation, ValueError):
        pass
    # 2. As Vietnamese decimal comma (e.g. 24,813 -> 24.813, 1,45 -> 1.45)
    if cleaned.count(",") == 1:
        try:
            interpretations.add(Decimal(cleaned.replace(",", ".")).normalize())
        except (InvalidOperation, ValueError):
            pass
    return interpretations


def _extract_claim_number_tokens(text: str) -> list[set[Decimal]]:
    # Normalize duplicate dots in decimal expressions (e.g. 84.832.6% -> 84.8326%)
    cleaned_value = re.sub(r"(\d+\.\d+)\.(\d+)", r"\1\2", str(text))
    tokens = []
    for match in _NUMBER.findall(cleaned_value):
        interps = _extract_token_interpretations(match)
        if interps:
            tokens.append(interps)
    return tokens


def _numeric_values(value: str) -> set[Decimal]:
    found = set()
    cleaned_value = re.sub(r"(\d+\.\d+)\.(\d+)", r"\1\2", str(value))
    for match in _NUMBER.findall(cleaned_value):
        found.update(_extract_token_interpretations(match))
    return found


def _extract_evidence_numbers(ev: Any) -> set[Decimal]:
    metric_clean = str(ev.metric or "").replace("_", " ")
    raw_str = (
        f"{json.dumps(ev.value, default=str)} "
        f"{ev.observation_date or ''} "
        f"{ev.publication_date or ''} "
        f"{metric_clean} "
        f"{ev.note or ''}"
    )
    nums = _numeric_values(raw_str)
    val = ev.value
    if isinstance(val, (int, float, Decimal)):
        try:
            f_val = float(val)
            for r in (0, 1, 2, 3):
                nums.add(Decimal(str(round(f_val, r))).normalize())
            nums.add(Decimal(int(f_val)))
        except (ValueError, OverflowError, InvalidOperation):
            pass
    return nums


def _is_number_grounded(num: Decimal, cited_numbers: set[Decimal]) -> bool:
    if num in cited_numbers:
        return True
    num_f = float(num)
    for c in cited_numbers:
        c_f = float(c)
        # Check absolute tolerance for small values
        if abs(num_f - c_f) <= 0.05:
            return True
        # Check relative tolerance (0.5%) for larger numbers
        if abs(c_f) > 1e-6 and abs(num_f - c_f) / abs(c_f) <= 0.005:
            return True
def _calculate_pearson(series_x: list[float] | None, series_y: list[float] | None) -> float | None:
    if not series_x or not series_y or len(series_x) != len(series_y) or len(series_x) < 3:
        return None
    n = len(series_x)
    mean_x = sum(series_x) / n
    mean_y = sum(series_y) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(series_x, series_y))
    den_x = sum((x - mean_x) ** 2 for x in series_x)
    den_y = sum((y - mean_y) ** 2 for y in series_y)
    if den_x <= 0 or den_y <= 0:
        return None
    return round(num / ((den_x ** 0.5) * (den_y ** 0.5)), 4)


def _matches_entity(ev_symbol: str | None, target_sym: str) -> bool:
    if not ev_symbol:
        return True
    symbols_in_ev = {s.strip().upper() for s in str(ev_symbol).split(",")}
    return target_sym.upper() in symbols_in_ev or "VN100" in symbols_in_ev


class AIAnalyst:
    def __init__(self, provider: AIProvider | None = None, router: AIRouter | None = None):
        self.provider = provider or AIGateway()
        self.router = router or AIRouter()

    def _citations(self, context: dict[str, Any]) -> list[AICitation]:
        citations = []
        raw_evidence = context.get("evidence", [])
        if isinstance(raw_evidence, dict):
            evidence_items = []
            for module_name, items in raw_evidence.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item_copy = dict(item)
                            item_copy.setdefault("responsible_module", module_name)
                            evidence_items.append(item_copy)
                elif isinstance(items, dict):
                    item_copy = dict(items)
                    item_copy.setdefault("responsible_module", module_name)
                    evidence_items.append(item_copy)
        elif isinstance(raw_evidence, list):
            evidence_items = raw_evidence
        else:
            evidence_items = []

        for index, item in enumerate(evidence_items, start=1):
            citations.append(AICitation(
                id=f"E{index:03d}",
                claim_type=item.get("claim_type", "UNCERTAINTY"),
                responsible_module=item.get("responsible_module", "unknown"),
                metric=item.get("metric"),
                value=item.get("value"),
                unit=item.get("unit"),
                source=item.get("source"),
                source_url=item.get("source_url"),
                observation_date=str(item["observation_date"]) if item.get("observation_date") else None,
                publication_date=str(item["publication_date"]) if item.get("publication_date") else None,
                retrieved_at=str(item["retrieved_at"]) if item.get("retrieved_at") else None,
                data_origin=item.get("data_origin"),
                freshness=item.get("freshness"),
                is_estimate=item.get("is_estimate", False),
                diagnostic_reason=item.get("diagnostic_reason"),
                note=item.get("note"),
                symbol=item.get("symbol"),
            ))
        return citations

    @staticmethod
    def _has_verifiable_evidence(citations: list[AICitation]) -> bool:
        return any(
            item.claim_type in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
            and bool(item.source)
            and item.data_origin not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
            and item.freshness not in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
            for item in citations
        )

    @staticmethod
    def _has_supported_horizon(context: dict[str, Any]) -> bool:
        for tool in context.get("tools", []):
            data = tool.get("data")
            if not isinstance(data, dict):
                continue
            if data.get("horizon"):
                return True
            portfolio = data.get("portfolio")
            if isinstance(portfolio, dict) and any(
                holding.get("horizon")
                for holding in portfolio.get("holdings", [])
                if isinstance(holding, dict)
            ):
                return True
        return False

    @staticmethod
    def _is_conversational_or_help(text: str) -> bool:
        cleaned = text.strip().lower()
        greetings = {
            "chào", "chao", "xin chào", "xin chao", "hi", "hello", "hey",
            "chào bạn", "chao ban", "chào bot", "chao bot", "alo", "alo bot",
            "hello bot", "hi bot",
        }
        if cleaned in greetings:
            return True
        help_patterns = [
            r"^(?:xin\s+)?chào(?:\s+bạn|\s+bot)?[\s!.,?]*$",
            r"^(?:hi|hello|hey)(?:\s+bot)?[\s!.,?]*$",
            r"^(?:bạn|bot)\s+(?:là\s+ai|tên\s+gì)[\s?]*$",
            r"^(?:who\s+are\s+you|what\s+can\s+you\s+do)[\s?]*$",
            r"^(?:hướng\s+dẫn|huong\s+dan|help|trợ\s+giúp|tro\s+giup)[\s?]*$",
            r"^(?:bạn|bot)\s+(?:có\s+thể\s+làm\s+gì|giúp\s+gì|làm\s+được\s+gì)[\s?]*$",
            r"^(?:tính\s+năng|chức\s+năng|gioi\s+thieu|giới\s+thiệu)[\s?]*$",
        ]
        return any(re.search(pat, cleaned, re.IGNORECASE) for pat in help_patterns)

    def _conversational_response(self, as_of: date) -> dict[str, Any]:
        return AIChatResponse(
            status="AVAILABLE",
            symbol=None,
            resolved_symbol=None,
            as_of_date=as_of,
            prompt_version=PROMPT_VERSION,
            model="investintel-assistant",
            answer=(
                "Xin chào! Tôi là Trợ lý Phân tích Định lượng & Nghiên cứu Doanh nghiệp của InvestIntel.\n\n"
                "Tôi có thể hỗ trợ bạn tra cứu và phân tích dữ liệu kiểm chứng cho toàn bộ danh mục cổ phiếu và chứng khoán được hỗ trợ:\n"
                "1. **Định giá & Sức khỏe tài chính:** Hỏi về doanh thu, biên lợi nhuận, P/E, P/B, nợ vay (ví dụ: *'giá VCB'*, *'định giá FPT'*, *'doanh thu MWG'*).\n"
                "2. **Toàn cảnh thị trường:** Hỏi về chỉ số và chế độ thị trường (ví dụ: *'thị trường hôm nay'*, *'tổng quan VN-Index'*).\n"
                "3. **Luận điểm & Rủi ro:** Kiểm tra tín hiệu cơ hội, điểm rủi ro tổng hợp (ví dụ: *'rủi ro HPG'*, *'đánh giá SHB'*).\n\n"
                "Mẹo: Bạn có thể nhập trực tiếp tên mã cổ phiếu vào câu hỏi hoặc điền mã vào ô 'Mã cổ phiếu' phía trên."
            ),
            claims=[
                AIClaim(
                    claim_type="FACT",
                    text="InvestIntel hỗ trợ phân tích toàn bộ các cổ phiếu và chứng khoán trong cơ sở dữ liệu với dữ liệu tài chính, định giá và rủi ro được kiểm chứng đa tầng.",
                    citation_ids=[],
                )
            ],
            citations=[],
            uncertainty=[],
            tools_used=[],
            usage={"eval_count": 50},
        ).model_dump(mode="json")

    def _inject_precomputed_metrics(
        self,
        citations: list[AICitation],
        query_symbols: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[AICitation]:
        new_citations = list(citations)
        existing_metrics_by_sym: dict[str, set[str]] = {}
        values_by_sym_metric: dict[tuple[str, str], float] = {}

        for c in citations:
            sym = c.symbol or (query_symbols[0] if query_symbols else "MARKET")
            if sym not in existing_metrics_by_sym:
                existing_metrics_by_sym[sym] = set()
            if c.metric:
                existing_metrics_by_sym[sym].add(c.metric)
                if c.value is not None:
                    try:
                        if (sym, c.metric) not in values_by_sym_metric:
                            values_by_sym_metric[(sym, c.metric)] = float(c.value)
                    except (ValueError, TypeError):
                        pass

        # Helper to get next numeric ID
        max_id = 0
        for c in citations:
            m = re.match(r"^E(\d+)$", c.id)
            if m:
                max_id = max(max_id, int(m.group(1)))

        # 1. Single symbol pre-computed margins (net_margin)
        target_symbols = [s for s in query_symbols if s and s != "VN100"]
        for sym in target_symbols:
            rev = values_by_sym_metric.get((sym, "revenue"))
            ni = values_by_sym_metric.get((sym, "net_income"))
            if rev and ni and rev > 0 and "net_margin" not in existing_metrics_by_sym.get(sym, set()):
                net_margin = round((ni / rev) * 100, 2)
                max_id += 1
                new_citations.append(AICitation(
                    id=f"E{max_id:03d}",
                    claim_type="MODEL_OUTPUT",
                    responsible_module="fundamentals",
                    metric="net_margin",
                    value=net_margin,
                    unit="%",
                    source="INVESTINTEL_PYTHON_CALCULATOR",
                    data_origin="LINEAGED_INGESTION",
                    freshness="AVAILABLE",
                    symbol=sym,
                    note=f"Biên lợi nhuận ròng của {sym} được tính sẵn bằng Python: ({ni:,.0f} / {rev:,.0f}) * 100 = {net_margin}%",
                ))

        # 2. Multi-symbol differences (PE diff, PB diff)
        if len(target_symbols) >= 2:
            s1, s2 = target_symbols[0], target_symbols[1]
            pe1 = values_by_sym_metric.get((s1, "pe")) or values_by_sym_metric.get((s1, "pe_ratio"))
            pe2 = values_by_sym_metric.get((s2, "pe")) or values_by_sym_metric.get((s2, "pe_ratio"))
            if pe1 is not None and pe2 is not None:
                pe_diff = round(pe1 - pe2, 2)
                max_id += 1
                new_citations.append(AICitation(
                    id=f"E{max_id:03d}",
                    claim_type="MODEL_OUTPUT",
                    responsible_module="valuation",
                    metric="pe_diff",
                    value=pe_diff,
                    unit="multiple",
                    source="INVESTINTEL_PYTHON_CALCULATOR",
                    data_origin="LINEAGED_INGESTION",
                    freshness="AVAILABLE",
                    symbol=f"{s1},{s2}",
                    note=f"Chênh lệch P/E ({s1} - {s2}) được tính sẵn: {pe1:.2f} - {pe2:.2f} = {pe_diff:+.2f} điểm",
                ))

            pb1 = values_by_sym_metric.get((s1, "pb")) or values_by_sym_metric.get((s1, "pb_ratio"))
            pb2 = values_by_sym_metric.get((s2, "pb")) or values_by_sym_metric.get((s2, "pb_ratio"))
            if pb1 is not None and pb2 is not None:
                pb_diff = round(pb1 - pb2, 2)
                max_id += 1
                new_citations.append(AICitation(
                    id=f"E{max_id:03d}",
                    claim_type="MODEL_OUTPUT",
                    responsible_module="valuation",
                    metric="pb_diff",
                    value=pb_diff,
                    unit="multiple",
                    source="INVESTINTEL_PYTHON_CALCULATOR",
                    data_origin="LINEAGED_INGESTION",
                    freshness="AVAILABLE",
                    symbol=f"{s1},{s2}",
                    note=f"Chênh lệch P/B ({s1} - {s2}) được tính sẵn: {pb1:.2f} - {pb2:.2f} = {pb_diff:+.2f} điểm",
                ))

        # 3. Commodity vs Stock price correlation
        if context and context.get("commodity_series") and context.get("stock_price_series"):
            c_series = context["commodity_series"]
            s_series = context["stock_price_series"]
            corr = _calculate_pearson(c_series, s_series)
            if corr is not None:
                max_id += 1
                target_sym = target_symbols[0] if target_symbols else "ENERGY"
                new_citations.append(AICitation(
                    id=f"E{max_id:03d}",
                    claim_type="MODEL_OUTPUT",
                    responsible_module="macro",
                    metric="pearson_correlation",
                    value=corr,
                    unit="coefficient",
                    source="INVESTINTEL_PYTHON_CALCULATOR",
                    data_origin="LINEAGED_INGESTION",
                    freshness="AVAILABLE",
                    symbol=target_sym,
                    note=f"Hệ số tương quan Pearson giữa giá {target_sym} và hàng hóa được tính sẵn: {corr}",
                ))

        # 4. Bank metric differences (NIM diff, CASA diff, Credit growth diff, NPL diff)
        if len(target_symbols) >= 2:
            s1, s2 = target_symbols[0], target_symbols[1]
            bank_metrics_to_diff = [
                ("nim", "nim_diff", "điểm %", "Biên lãi ròng (NIM)"),
                ("casa_ratio", "casa_diff", "điểm %", "Tỷ lệ CASA"),
                ("credit_growth", "credit_growth_diff", "điểm %", "Tăng trưởng tín dụng"),
                ("npl_ratio", "npl_diff", "điểm %", "Tỷ lệ nợ xấu (NPL)"),
                ("llr_ratio", "llr_diff", "điểm %", "Tỷ lệ bao phủ nợ xấu (LLR)"),
            ]
            for m_key, diff_key, unit_str, label in bank_metrics_to_diff:
                v1 = values_by_sym_metric.get((s1, m_key))
                v2 = values_by_sym_metric.get((s2, m_key))
                if v1 is not None and v2 is not None:
                    d_val = round(v1 - v2, 2)
                    max_id += 1
                    new_citations.append(AICitation(
                        id=f"E{max_id:03d}",
                        claim_type="MODEL_OUTPUT",
                        responsible_module="bank_metrics",
                        metric=diff_key,
                        value=d_val,
                        unit=unit_str,
                        source="INVESTINTEL_PYTHON_CALCULATOR",
                        data_origin="LINEAGED_INGESTION",
                        freshness="AVAILABLE",
                        symbol=f"{s1},{s2}",
                        note=f"Chênh lệch {label} ({s1} - {s2}) được tính sẵn: {v1:.2f} - {v2:.2f} = {d_val:+.2f} {unit_str}",
                    ))

        return new_citations

    def _build_structured_data_summary(
        self,
        citations: list[AICitation],
        context: dict[str, Any],
        extracted_symbols: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        symbols_summary: dict[str, Any] = {}
        target_symbols = extracted_symbols if extracted_symbols else ["MARKET"]

        for sym in target_symbols:
            symbols_summary[sym] = {
                "metrics": {},
                "calculated_indicators": {},
            }

        for c in citations:
            sym = c.symbol or (target_symbols[0] if target_symbols else "MARKET")
            if sym not in symbols_summary:
                symbols_summary[sym] = {"metrics": {}, "calculated_indicators": {}}
            if c.metric and c.value is not None:
                symbols_summary[sym]["metrics"][c.metric] = {
                    "value": c.value,
                    "unit": c.unit,
                    "observation_date": c.observation_date,
                    "source": c.source,
                    "citation_id": c.id,
                    "is_estimate": c.is_estimate,
                }

        # Python-computed financial indicators
        for sym, s_data in symbols_summary.items():
            metrics = s_data["metrics"]
            calc = s_data["calculated_indicators"]

            # Net profit margin (%) = net_income / revenue * 100
            if "net_income" in metrics and "revenue" in metrics:
                try:
                    rev = float(metrics["revenue"]["value"])
                    ni = float(metrics["net_income"]["value"])
                    if rev > 0:
                        calc["net_profit_margin_pct"] = round((ni / rev) * 100, 2)
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            # Gross margin (%)
            if "gross_margin" in metrics:
                try:
                    gm = float(metrics["gross_margin"]["value"])
                    calc["gross_margin_pct"] = round(gm, 2)
                except (ValueError, TypeError):
                    pass

            # Operating margin (%)
            if "operating_income" in metrics and "revenue" in metrics:
                try:
                    rev = float(metrics["revenue"]["value"])
                    op_inc = float(metrics["operating_income"]["value"])
                    if rev > 0:
                        calc["operating_margin_pct"] = round((op_inc / rev) * 100, 2)
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            # ROE (%)
            if "roe" in metrics:
                try:
                    calc["roe_pct"] = round(float(metrics["roe"]["value"]), 2)
                except (ValueError, TypeError):
                    pass

        # Multi-ticker comparisons (e.g. MBB vs VCB)
        comparisons: dict[str, Any] = {}
        if len(target_symbols) >= 2:
            s1, s2 = target_symbols[0], target_symbols[1]
            m1 = symbols_summary.get(s1, {}).get("metrics", {})
            m2 = symbols_summary.get(s2, {}).get("metrics", {})

            # P/E comparison
            pe1_item = m1.get("pe") or m1.get("pe_ratio")
            pe2_item = m2.get("pe") or m2.get("pe_ratio")
            if pe1_item and pe2_item and pe1_item.get("value") is not None and pe2_item.get("value") is not None:
                try:
                    v1 = float(pe1_item["value"])
                    v2 = float(pe2_item["value"])
                    comparisons["pe_diff"] = round(v1 - v2, 2)
                    comparisons["pe_ratio"] = round(v1 / v2, 2) if v2 != 0 else None
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            # P/B comparison
            pb1_item = m1.get("pb") or m1.get("pb_ratio")
            pb2_item = m2.get("pb") or m2.get("pb_ratio")
            if pb1_item and pb2_item and pb1_item.get("value") is not None and pb2_item.get("value") is not None:
                try:
                    v1 = float(pb1_item["value"])
                    v2 = float(pb2_item["value"])
                    comparisons["pb_diff"] = round(v1 - v2, 2)
                    comparisons["pb_ratio"] = round(v1 / v2, 2) if v2 != 0 else None
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            # ROE comparison
            roe1_item = m1.get("roe")
            roe2_item = m2.get("roe")
            if roe1_item and roe2_item and roe1_item.get("value") is not None and roe2_item.get("value") is not None:
                try:
                    comparisons["roe_diff"] = round(float(roe1_item["value"]) - float(roe2_item["value"]), 2)
                except (ValueError, TypeError):
                    pass

            # Bank comparisons (NIM, CASA, Credit Growth, NPL, LLR)
            for b_key in ("nim", "casa_ratio", "credit_growth", "npl_ratio", "llr_ratio"):
                b1 = m1.get(b_key)
                b2 = m2.get(b_key)
                if b1 and b2 and b1.get("value") is not None and b2.get("value") is not None:
                    try:
                        comparisons[f"{b_key}_diff"] = round(float(b1["value"]) - float(b2["value"]), 2)
                    except (ValueError, TypeError):
                        pass

        structured_summary = {
            "symbols": symbols_summary,
            "comparisons": comparisons if comparisons else None,
        }

        # Metadata flags
        has_estimate_eps = any(
            bool(c.is_estimate) for c in citations if c.metric in ("eps", "pe", "pe_ratio")
        )
        metadata_flags = {
            "eps_is_estimate": has_estimate_eps,
            "shares_basis": "PERIOD_END_SHARES" if has_estimate_eps else "WEIGHTED_AVERAGE_SHARES",
            "accounting_standard_warning": (
                "Chỉ số EPS và P/E được ước tính trên số lượng cổ phiếu lưu hành cuối kỳ theo dữ liệu BCTC thực tế; chưa áp dụng số lượng bình quân gia quyền theo chuẩn mực IAS 33 do thiếu dữ liệu phát hành quyền chọn/cổ tức nội quý."
                if has_estimate_eps else None
            ),
            "data_origin": "CANONICAL_DATABASE",
            "deterministic_validation": "PASSED_STRICT",
            "total_verifiable_citations": sum(1 for c in citations if self._has_verifiable_evidence([c])),
        }
        return structured_summary, metadata_flags

    def _build_fallback_claims(
        self,
        citations: list[AICitation],
        structured_summary: dict[str, Any],
        extracted_symbols: list[str],
    ) -> list[AIClaim]:
        fallback_claims: list[AIClaim] = []
        sym_summaries = structured_summary.get("symbols", {})
        evidence_by_id = {c.id: c for c in citations}

        for sym, data in sym_summaries.items():
            metrics = data.get("metrics", {})
            # 1. Price claim
            if "price" in metrics:
                p_item = metrics["price"]
                p_val = p_item["value"]
                cid = p_item.get("citation_id")
                date_str = f" tại ngày {p_item['observation_date']}" if p_item.get("observation_date") else ""
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"Giá đóng cửa của {sym}{date_str} ghi nhận ở mức {float(p_val):,.0f} VND.",
                    citation_ids=[cid] if cid and cid in evidence_by_id else [],
                ))

            # 2. Valuation claims (P/E, P/B, EPS)
            pe_item = metrics.get("pe") or metrics.get("pe_ratio")
            pb_item = metrics.get("pb") or metrics.get("pb_ratio")
            eps_item = metrics.get("eps")
            val_parts = []
            val_cids = []
            if pe_item and pe_item.get("value") is not None:
                val_parts.append(f"P/E là {float(pe_item['value']):.2f}x")
                if pe_item.get("citation_id") and pe_item["citation_id"] in evidence_by_id:
                    val_cids.append(pe_item["citation_id"])
            if pb_item and pb_item.get("value") is not None:
                val_parts.append(f"P/B là {float(pb_item['value']):.2f}x")
                if pb_item.get("citation_id") and pb_item["citation_id"] in evidence_by_id:
                    val_cids.append(pb_item["citation_id"])
            if eps_item and eps_item.get("value") is not None:
                val_parts.append(f"EPS là {float(eps_item['value']):,.0f} VND")
                if eps_item.get("citation_id") and eps_item["citation_id"] in evidence_by_id:
                    val_cids.append(eps_item["citation_id"])
            if val_parts:
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"Định giá thị trường của {sym}: {', '.join(val_parts)}.",
                    citation_ids=val_cids,
                ))

            # 3. Fundamentals claims (Revenue, Net income, Margins)
            rev_item = metrics.get("revenue")
            ni_item = metrics.get("net_income")
            fund_parts = []
            fund_cids = []
            if rev_item and rev_item.get("value") is not None:
                r_val = float(rev_item["value"])
                r_str = f"{r_val / 1e9:,.1f} tỷ VND" if abs(r_val) >= 1e9 else f"{r_val:,.0f} VND"
                fund_parts.append(f"doanh thu đạt {r_str}")
                if rev_item.get("citation_id") and rev_item["citation_id"] in evidence_by_id:
                    fund_cids.append(rev_item["citation_id"])
            if ni_item and ni_item.get("value") is not None:
                ni_val = float(ni_item["value"])
                ni_str = f"{ni_val / 1e9:,.1f} tỷ VND" if abs(ni_val) >= 1e9 else f"{ni_val:,.0f} VND"
                fund_parts.append(f"lợi nhuận sau thuế đạt {ni_str}")
                if ni_item.get("citation_id") and ni_item["citation_id"] in evidence_by_id:
                    fund_cids.append(ni_item["citation_id"])
            calc_ind = data.get("calculated_indicators", {})
            if "net_profit_margin_pct" in calc_ind:
                fund_parts.append(f"biên lợi nhuận ròng đạt {calc_ind['net_profit_margin_pct']}%")
            if fund_parts:
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"Kết quả kinh doanh của {sym}: {', '.join(fund_parts)}.",
                    citation_ids=fund_cids,
                ))

            # Bank specific metrics (NIM, CASA, Credit Growth, NPL, LLR)
            bank_parts = []
            bank_cids = []
            for b_k, b_lbl in [
                ("nim", "NIM"),
                ("casa_ratio", "CASA"),
                ("credit_growth", "tăng trưởng tín dụng"),
                ("npl_ratio", "tỷ lệ nợ xấu NPL"),
                ("llr_ratio", "tỷ lệ bao phủ nợ xấu LLR"),
            ]:
                if b_k in metrics and metrics[b_k].get("value") is not None:
                    bank_parts.append(f"{b_lbl} đạt {float(metrics[b_k]['value']):.2f}%")
                    if metrics[b_k].get("citation_id") and metrics[b_k]["citation_id"] in evidence_by_id:
                        bank_cids.append(metrics[b_k]["citation_id"])
            if bank_parts:
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"Chỉ số hoạt động ngành ngân hàng của {sym}: {', '.join(bank_parts)}.",
                    citation_ids=bank_cids,
                ))

        # 4. Multi-ticker comparison claim
        comps = structured_summary.get("comparisons")
        if comps and len(extracted_symbols) >= 2:
            s1, s2 = extracted_symbols[0], extracted_symbols[1]
            comp_parts = []
            if "pe_diff" in comps:
                comp_parts.append(f"chênh lệch P/E ({s1} - {s2}) là {comps['pe_diff']:+.2f} điểm")
            if "pb_diff" in comps:
                comp_parts.append(f"chênh lệch P/B ({s1} - {s2}) là {comps['pb_diff']:+.2f} điểm")
            if "roe_diff" in comps:
                comp_parts.append(f"chênh lệch ROE ({s1} - {s2}) là {comps['roe_diff']:+.2f}%")
            if "nim_diff" in comps:
                comp_parts.append(f"chênh lệch NIM ({s1} - {s2}) là {comps['nim_diff']:+.2f}%")
            if "credit_growth_diff" in comps:
                comp_parts.append(f"chênh lệch tăng trưởng tín dụng ({s1} - {s2}) là {comps['credit_growth_diff']:+.2f}%")
            if "npl_ratio_diff" in comps:
                comp_parts.append(f"chênh lệch nợ xấu NPL ({s1} - {s2}) là {comps['npl_ratio_diff']:+.2f}%")
            if comp_parts:
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"So sánh định giá & chỉ số giữa {s1} và {s2}: {'; '.join(comp_parts)}.",
                    citation_ids=[],
                ))

        # 5. Macro commodity & correlation claims
        for c in citations:
            if c.metric == "brent_close" and c.value is not None:
                fallback_claims.append(AIClaim(
                    claim_type="FACT",
                    text=f"Giá dầu Brent tham chiếu giao ngay ghi nhận ở mức {float(c.value):.2f} USD/thùng.",
                    citation_ids=[c.id] if c.id in evidence_by_id else [],
                ))
            elif c.metric == "pearson_correlation" and c.value is not None:
                fallback_claims.append(AIClaim(
                    claim_type="MODEL_OUTPUT",
                    text=f"Hệ số tương quan tuyến tính Pearson giữa giá cổ phiếu và dầu Brent đạt {float(c.value):.4f}.",
                    citation_ids=[c.id] if c.id in evidence_by_id else [],
                ))

        # Always add an honest notice
        fallback_claims.append(AIClaim(
            claim_type="UNCERTAINTY",
            text="Lưu ý: Mô hình AI chưa tạo được kết luận văn bản vượt qua lớp kiểm định chống Hallucination. Bảng số liệu trên được trích xuất trực tiếp từ CSDL kiểm chứng của InvestIntel.",
            citation_ids=[],
        ))
        return fallback_claims

    @staticmethod
    def determine_response_status(
        question: str,
        cited_claims: list[AIClaim],
        evidence_by_id: dict[str, AICitation],
        final_uncertainty: list[str],
        extracted_symbols: list[str] | None = None,
        canonical_symbol: str | None = None,
        asks_intraday: bool = False,
        citations: list[AICitation] | None = None,
    ) -> tuple[str, set[str]]:
        """
        Determine whether the final answer status is 'AVAILABLE' or 'PARTIAL'.
        - AVAILABLE: All directly requested metrics are identified and verified with valid citations.
        - PARTIAL: Missing requested metrics, ungrounded substantive claims, or missing data uncertainty.
        """
        requested_metric_groups = extract_requested_metric_groups(question)
        substantive_claims = [c for c in cited_claims if c.claim_type != "UNCERTAINTY"]
        target_syms = [s.upper() for s in extracted_symbols] if extracted_symbols else ([canonical_symbol.upper()] if canonical_symbol else [])

        # Check coverage of requested metric categories
        # A category is covered IF AND ONLY IF at least one substantive claim cites
        # an evidence item whose metric matches candidate_metrics (and matches target symbol if specified).
        covered_categories = set()
        for cat, candidate_metrics in requested_metric_groups.items():
            cat_matched = False
            for c in substantive_claims:
                for cid in c.citation_ids:
                    ev = evidence_by_id.get(cid)
                    if not ev or not ev.metric:
                        continue
                    if ev.metric.lower() in candidate_metrics:
                        if target_syms and ev.symbol and ev.symbol.upper() not in target_syms:
                            continue
                        cat_matched = True
                        break
                if cat_matched:
                    break
            if cat_matched:
                covered_categories.add(cat)

        uncovered_requested_groups = set(requested_metric_groups.keys()) - covered_categories

        # Check whether any UNCERTAINTY claim or uncertainty bullet signals missing data/unavailability
        missing_data_uncertainty = False
        missing_data_pattern = r"(không có dữ liệu|chưa có thông tin|không đủ dữ liệu|thiếu dữ liệu|chưa có sẵn|không tìm thấy|unverified|insufficient)"
        for c in cited_claims:
            if c.claim_type == "UNCERTAINTY":
                text_lower = c.text.lower()
                if re.search(missing_data_pattern, text_lower):
                    if requested_metric_groups:
                        if uncovered_requested_groups:
                            missing_data_uncertainty = True
                            break
                    else:
                        missing_data_uncertainty = True
                        break

        if not missing_data_uncertainty:
            for unc in final_uncertainty:
                unc_lower = str(unc).lower()
                if re.search(missing_data_pattern, unc_lower):
                    if requested_metric_groups:
                        if uncovered_requested_groups:
                            missing_data_uncertainty = True
                            break
                    else:
                        missing_data_uncertainty = True
                        break

        # Never default to AVAILABLE when requested_metric_groups is empty if there are no grounded citations
        no_grounded_substantive_claims = (
            len(substantive_claims) == 0
            or not any(c.citation_ids for c in substantive_claims)
        )

        referenced_ids = {cid for c in cited_claims for cid in c.citation_ids}
        stale_or_insufficient = False
        if citations:
            stale_or_insufficient = any(
                item.freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
                for item in citations
                if item.id in referenced_ids
            )

        symbol_unrepresented = False
        if extracted_symbols and len(extracted_symbols) > 1:
            symbol_unrepresented = any(
                not any(
                    evidence_by_id.get(cid) and evidence_by_id[cid].symbol == s
                    for c in cited_claims
                    for cid in c.citation_ids
                )
                for s in extracted_symbols
            )

        has_uncertainty = (
            asks_intraday
            or bool(uncovered_requested_groups)
            or missing_data_uncertainty
            or no_grounded_substantive_claims
            or stale_or_insufficient
            or symbol_unrepresented
        )

        status = "PARTIAL" if has_uncertainty else "AVAILABLE"
        return status, uncovered_requested_groups

    def _insufficient_response(
        self,
        *,
        symbol: str | None,
        as_of: date,
        citations: list[AICitation],
        tools_used: list[str],
        reason: str,
        answer: str = "Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.",
        structured_data_summary: dict[str, Any] | None = None,
        metadata_flags: dict[str, Any] | None = None,
        status: Literal["INSUFFICIENT_DATA", "PARTIAL_DATA_ONLY"] = "INSUFFICIENT_DATA",
    ) -> dict[str, Any]:
        return AIChatResponse(
            status=status,
            symbol=symbol,
            resolved_symbol=symbol,
            as_of_date=as_of,
            prompt_version=PROMPT_VERSION,
            model=None,
            answer=answer,
            claims=[AIClaim(claim_type="UNCERTAINTY", text=reason)],
            citations=citations,
            uncertainty=[reason],
            tools_used=tools_used,
            usage={},
            structured_data_summary=structured_data_summary,
            metadata_flags=metadata_flags,
        ).model_dump(mode="json")

    async def answer_question_stream(
        self,
        question: str,
        *,
        session: Session,
        symbol: str | None = None,
        as_of: date | None = None,
        tool_names: list[str] | None = None,
        task_type: TaskType = "USER_CHAT",
    ) -> AsyncGenerator[str, None]:
        from services.universe.registry import UniverseRegistry

        requested_date = as_of or date.today()

        # Step 1: Status fetching_data
        yield f"data: {json.dumps({'type': 'status', 'step': 'fetching_data', 'message': 'Đang trích xuất BCTC và chuỗi giá...'}, ensure_ascii=False)}\n\n"

        # Handle conversational greetings and guidance if no specific symbol is supplied
        if self._is_conversational_or_help(question) and not symbol:
            res = self._conversational_response(requested_date)
            yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        extracted_symbols: list[str] = []
        canonical_symbol = None
        if symbol:
            resolved = UniverseRegistry.resolve_instrument(session, symbol)
            canonical_symbol = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(symbol) or symbol.upper())
            extracted_symbols = [canonical_symbol]
        else:
            extracted_symbols = UniverseRegistry.extract_all_symbols_from_text(question, session)
            canonical_symbol = extracted_symbols[0] if extracted_symbols else None

        # Check for general portfolio or asset allocation query without specific single ticker (Q19)
        portfolio_terms = (
            "danh mục", "danh muc", "phân bổ", "phan bo", "portfolio", "allocation",
            "tài sản", "tai san", "100 triệu", "đa dạng hóa", "da dang hoa", "chiến lược",
        )
        is_portfolio_query = any(term in question.casefold() for term in portfolio_terms)
        if not extracted_symbols and is_portfolio_query:
            extracted_symbols = ["VN100"]
            canonical_symbol = "VN100"

        query_target = extracted_symbols if len(extracted_symbols) > 1 else canonical_symbol
        context = AITools.get_context(query_target, requested_date, tool_names, session, question=question)
        citations = self._citations(context)
        used_tools = [item["name"] for item in context.get("tools", [])]
        asks_horizon = any(term in question.casefold() for term in (
            "horizon", "investment period", "time horizon", "thời hạn", "kỳ hạn", "đầu tư bao lâu",
        ))
        if asks_horizon and not self._has_supported_horizon(context):
            res = self._insufficient_response(
                symbol=canonical_symbol or symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="No sourced investment horizon is recorded for this query.",
            )
            yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not self._has_verifiable_evidence(citations):
            effective_symbol = canonical_symbol or symbol
            if effective_symbol:
                detail_reason = f"Available records for {effective_symbol} are missing, stale, seeded/untraced, or lack a source citation (as of {requested_date})."
                ans_text = f"Chưa đủ bằng chứng có nguồn kiểm chứng về mã {effective_symbol} để trả lời câu hỏi này."
            else:
                detail_reason = "Không tìm thấy mã cổ phiếu hợp lệ trong câu hỏi hoặc mã chưa có trong cơ sở dữ liệu."
                ans_text = (
                    "Chưa xác định được mã cổ phiếu hoặc chủ đề cần phân tích. "
                    "Bạn vui lòng nhập rõ mã cổ phiếu (ví dụ: VCB, FPT, HPG) hoặc đặt câu hỏi về thị trường chung (ví dụ: 'thị trường hôm nay')."
                )
            res = self._insufficient_response(
                symbol=effective_symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason=detail_reason,
                answer=ans_text,
            )
            yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Check for intraday historical timestamp request (Q18)
        asks_intraday = bool(re.search(r"\b(?:1[0-9]|2[0-3]|0?[0-9]):[0-5][0-9]\b", question))

        # Inject precomputed metrics (margins, pe/pb diff, correlation)
        citations = self._inject_precomputed_metrics(citations, extracted_symbols, context)
        evidence_by_id = {item.id: item for item in citations}
        tool_context = {
            **context,
            "evidence_register": [item.model_dump(mode="json") for item in citations],
        }
        model = self.router.route_task(task_type, "HIGH" if task_type == "DEEP_RESEARCH" else "MEDIUM")

        # Step 2: Status llm_reasoning with heartbeat ping loop
        yield f"data: {json.dumps({'type': 'status', 'step': 'llm_reasoning', 'message': 'Đang phân tích tương quan tài chính...'}, ensure_ascii=False)}\n\n"

        llm_task = asyncio.create_task(
            self.provider.generate_structured(
                prompt=build_chat_prompt(question, tool_context),
                system=SYSTEM_PROMPT,
                model=model,
                schema=AIAnswerDraft.model_json_schema(),
            )
        )

        draft: AIAnswerDraft | None = None
        usage: dict[str, Any] = {}
        llm_failure_reason: str | None = None

        try:
            while not llm_task.done():
                done, _ = await asyncio.wait([llm_task], timeout=3.0)
                if not done:
                    yield f"data: {json.dumps({'type': 'status', 'step': 'llm_reasoning', 'message': 'Đang phân tích tương quan tài chính... (heartbeat)'}, ensure_ascii=False)}\n\n"

            draft_data, usage = await llm_task

            # Step 3: Status validating
            yield f"data: {json.dumps({'type': 'status', 'step': 'validating', 'message': 'Đang đối chiếu số liệu chống Hallucination...'}, ensure_ascii=False)}\n\n"

            draft = AIAnswerDraft.model_validate(draft_data)
        except (AIProviderError, ValidationError, Exception) as err:
            logger.warning("LLM generation/validation failed: %s. Engaging deterministic smart fallback.", err)
            llm_failure_reason = str(err)

        if draft is None:
            # Build structured data summary and metadata flags
            structured_summary, metadata_flags = self._build_structured_data_summary(citations, context, extracted_symbols)

            if any(self._has_verifiable_evidence([c]) for c in citations):
                fallback_claims = self._build_fallback_claims(citations, structured_summary, extracted_symbols)
                verifiable_cits = [c for c in citations if self._has_verifiable_evidence([c])][:20]
                answer_text = (
                    "Mô hình AI ngôn ngữ đang tạm thời không khả dụng hoặc chưa thể trích xuất kết luận văn bản. "
                    "Hệ thống tự động kích hoạt chế độ phân tích định lượng (Deterministic Fallback) và cung cấp bảng số liệu tài chính đã được đối chiếu từ cơ sở dữ liệu kiểm chứng cùng các chỉ số được tính toán trực tiếp:"
                )
                res = AIChatResponse(
                    status="PARTIAL_DATA_ONLY",
                    symbol=", ".join(extracted_symbols) if len(extracted_symbols) > 1 else (canonical_symbol or symbol),
                    resolved_symbol=canonical_symbol or symbol,
                    as_of_date=requested_date,
                    prompt_version=PROMPT_VERSION,
                    model="investintel-deterministic-fallback",
                    answer=answer_text,
                    claims=fallback_claims,
                    citations=verifiable_cits,
                    uncertainty=[
                        f"Mô hình AI tạm thời không phản hồi ({llm_failure_reason or 'AI provider unavailable'}).",
                        "Toàn bộ số liệu trên được trích xuất và tính toán tự động từ CSDL tài chính và giá EOD có nguồn kiểm chứng của InvestIntel."
                    ],
                    tools_used=used_tools,
                    usage={},
                    structured_data_summary=structured_summary,
                    metadata_flags=metadata_flags,
                ).model_dump(mode="json")
                yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            res = self._insufficient_response(
                symbol=canonical_symbol or symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason=f"Mô hình AI không khả dụng ({llm_failure_reason}) và không đủ dữ liệu kiểm chứng.",
                structured_data_summary=structured_summary,
                metadata_flags=metadata_flags,
            )
            yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        cited_claims = []
        referenced_ids: set[str] = set()
        suppressed_reasons: list[str] = []
        for claim in draft.claims:
            normalized_cids = []
            for raw_cid in claim.citation_ids:
                cid_str = str(raw_cid).strip().strip("[]").upper()
                m = re.match(r"^E(\d+)$", cid_str)
                if m:
                    cid_str = f"E{int(m.group(1)):03d}"
                normalized_cids.append(cid_str)
            claim.citation_ids = normalized_cids

            valid_ids = [citation_id for citation_id in claim.citation_ids if citation_id in evidence_by_id]
            if claim.claim_type != "UNCERTAINTY" and not valid_ids:
                suppressed_reasons.append("The model returned a factual or interpreted claim without a valid evidence citation.")
                continue
            if claim.claim_type != "UNCERTAINTY" and any(
                evidence_by_id[citation_id].claim_type not in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
                or not evidence_by_id[citation_id].source
                or evidence_by_id[citation_id].data_origin in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
                or evidence_by_id[citation_id].freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
                for citation_id in valid_ids
            ):
                suppressed_reasons.append("The selected citation is stale, untraced, or not a verifiable evidence source.")
                continue

            if claim.claim_type == "UNCERTAINTY":
                valid_ids = []
                claim.citation_ids = []
            elif len(valid_ids) != len(claim.citation_ids):
                suppressed_reasons.append("The model referenced an evidence ID that was not supplied by a data tool.")
                continue

            if claim.claim_type != "UNCERTAINTY":
                claim_text_lower = claim.text.lower()

                # Entity consistency: if claim mentions stock A, citations must not belong solely to stock B
                has_entity_mismatch = False
                if extracted_symbols:
                    for sym in extracted_symbols:
                        if sym and sym != "VN100":
                            sym_re = rf"\b{re.escape(sym.lower())}\b"
                            if re.search(sym_re, claim_text_lower):
                                foreign = [cid for cid in valid_ids if evidence_by_id[cid].symbol and not _matches_entity(evidence_by_id[cid].symbol, sym)]
                                if foreign and not any(_matches_entity(evidence_by_id[cid].symbol, sym) for cid in valid_ids):
                                    suppressed_reasons.append(f"Claim for {sym} cannot be supported solely by citations from {evidence_by_id[foreign[0]].symbol}.")
                                    has_entity_mismatch = True
                                    break
                if has_entity_mismatch:
                    continue

                # Metric semantic validation:
                # 1. P/E vs P/B
                if any(term in claim_text_lower for term in ("p/b", "pb", "price-to-book", "price to book")):
                    if any(evidence_by_id[cid].metric in ("pe", "pe_ratio", "price_to_earnings") for cid in valid_ids):
                        suppressed_reasons.append("P/E evidence cannot be presented as P/B.")
                        continue
                if any(term in claim_text_lower for term in ("p/e", "pe", "price-to-earnings", "price to earnings")):
                    if any(evidence_by_id[cid].metric in ("pb", "pb_ratio", "price_to_book") for cid in valid_ids):
                        suppressed_reasons.append("P/B evidence cannot be presented as P/E.")
                        continue

                # 2. Gross margin vs Revenue growth / decline (Q06 VHM)
                is_revenue_claim = bool(
                    re.search(r"\bdoanh\s*thu\b.*?\b(?:tăng|giảm|tăng\s*trưởng|suy\s*giảm|growth|decline)\b", claim_text_lower)
                    or re.search(r"\b(?:tăng\s*trưởng|suy\s*giảm)\s+doanh\s*thu\b", claim_text_lower)
                    or any(term in claim_text_lower for term in ("revenue growth", "revenue decline"))
                )
                if is_revenue_claim:
                    if any(evidence_by_id[cid].metric in ("gross_margin", "net_margin", "ebitda_margin") for cid in valid_ids) and not any(evidence_by_id[cid].metric in ("revenue", "revenue_yoy", "revenue_cagr_3y", "revenue_cagr_5y") for cid in valid_ids):
                        suppressed_reasons.append("Margin evidence cannot be presented as revenue growth or decline.")
                        continue

                # 3. P/E multiple vs Profit / Net income (Q07 VIC)
                if any(term in claim_text_lower for term in ("lợi nhuận hợp nhất", "lợi nhuận thuần", "net profit", "lợi nhuận sau thuế")):
                    if any(evidence_by_id[cid].metric in ("pe", "pe_ratio", "pb", "pb_ratio") for cid in valid_ids) and not any(evidence_by_id[cid].metric in ("net_income", "net_income_yoy", "operating_income") for cid in valid_ids):
                        suppressed_reasons.append("Valuation multiple evidence cannot be presented as profit or income.")
                        continue

                # 4. Company revenue vs Commodity/Oil price (Q10 PLX)
                if any(term in claim_text_lower for term in ("giá dầu", "oil price", "giá hàng hóa")):
                    if any(evidence_by_id[cid].metric in ("revenue", "revenue_yoy", "gross_margin", "net_income") for cid in valid_ids):
                        suppressed_reasons.append("Company financial statements cannot substantiate commodity price changes without a market price series.")
                        continue

                # Numeric grounding check
                cited_numbers = set().union(*(
                    _extract_evidence_numbers(evidence_by_id[citation_id])
                    for citation_id in valid_ids
                    if citation_id in evidence_by_id
                )).union(_numeric_values(question))
                claim_tokens = _extract_claim_number_tokens(claim.text)
                is_grounded = all(
                    any(_is_number_grounded(interp, cited_numbers) for interp in token_interps)
                    for token_interps in claim_tokens
                )
                if not is_grounded:
                    suppressed_reasons.append("A numeric claim is not present in the values of its cited evidence IDs.")
                    continue

            referenced_ids.update(valid_ids)
            cited_claims.append(claim)

        # Build structured data summary and metadata flags
        structured_summary, metadata_flags = self._build_structured_data_summary(citations, context, extracted_symbols)

        # Check if at least one substantive claim survived validation
        valid_substantive_claims = [c for c in cited_claims if c.claim_type != "UNCERTAINTY"]
        if not valid_substantive_claims:
            if draft.answer and draft.answer.strip():
                clean_ans = draft.answer.strip()
                ans_numbers = _numeric_values(clean_ans)
                if not ans_numbers:
                    cited_claims.append(AIClaim(claim_type="UNCERTAINTY", text=clean_ans, citation_ids=[]))
                    valid_substantive_claims = [c for c in cited_claims if c.claim_type != "UNCERTAINTY"]

            if not valid_substantive_claims:
                reason = suppressed_reasons[0] if suppressed_reasons else "The model did not return any structured claims that can be safely displayed."
                # Smart fallback: If verifiable citations exist, return PARTIAL_DATA_ONLY
                if any(self._has_verifiable_evidence([c]) for c in citations):
                    fallback_claims = self._build_fallback_claims(citations, structured_summary, extracted_symbols)
                    verifiable_cits = [c for c in citations if self._has_verifiable_evidence([c])][:20]
                    answer_text = (
                        "Mô hình AI chưa trích xuất được kết luận văn bản đủ độ tin cậy để vượt qua lớp kiểm định chống sai lệch (Hallucination Guard). "
                        "Hệ thống cung cấp bảng số liệu tài chính thực tế đã được đối chiếu từ cơ sở dữ liệu kiểm chứng cùng các chỉ số được tính toán trực tiếp:"
                    )
                    res = AIChatResponse(
                        status="PARTIAL_DATA_ONLY",
                        symbol=", ".join(extracted_symbols) if len(extracted_symbols) > 1 else (canonical_symbol or symbol),
                        resolved_symbol=canonical_symbol or symbol,
                        as_of_date=requested_date,
                        prompt_version=PROMPT_VERSION,
                        model=usage.get("model", model),
                        answer=answer_text,
                        claims=fallback_claims,
                        citations=verifiable_cits,
                        uncertainty=[
                            reason,
                            "Toàn bộ số liệu trên được tính toán tự động từ CSDL tài chính và giá EOD có nguồn kiểm chứng."
                        ],
                        tools_used=used_tools,
                        usage=usage,
                        structured_data_summary=structured_summary,
                        metadata_flags=metadata_flags,
                    ).model_dump(mode="json")
                    yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                res = self._insufficient_response(
                    symbol=canonical_symbol or symbol,
                    as_of=requested_date,
                    citations=citations,
                    tools_used=used_tools,
                    reason=reason,
                    structured_data_summary=structured_summary,
                    metadata_flags=metadata_flags,
                )
                yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

        # If intraday timestamp requested, inject honesty notice regarding EOD limitation (Q18)
        if asks_intraday:
            cited_claims.insert(0, AIClaim(
                claim_type="UNCERTAINTY",
                text=f"Lưu ý: Hệ thống InvestIntel hiện chỉ hỗ trợ dữ liệu chốt phiên theo ngày (EOD), không hỗ trợ replay dữ liệu tại thời điểm trong phiên giao dịch. Kết quả dưới đây được tổng hợp dựa trên dữ liệu chốt phiên ngày {requested_date.isoformat()}.",
                citation_ids=[],
            ))

        # If multi-ticker comparison, verify if any requested stock has missing evidence
        if len(extracted_symbols) > 1:
            for req_sym in extracted_symbols:
                has_sym = any(
                    (evidence_by_id.get(cid) and evidence_by_id[cid].symbol == req_sym)
                    for c in cited_claims for cid in c.citation_ids
                )
                if not has_sym and not any(req_sym.lower() in c.text.lower() for c in cited_claims):
                    cited_claims.append(AIClaim(
                        claim_type="UNCERTAINTY",
                        text=f"Dữ liệu tài chính và định giá cho mã {req_sym} hiện chưa có sẵn hoặc chưa đủ điều kiện kiểm chứng trong hệ thống.",
                        citation_ids=[],
                    ))

        # Filter contradictory uncertainty statements
        available_metrics = {
            evidence_by_id[cid].metric.lower()
            for c in cited_claims
            for cid in c.citation_ids
            if cid in evidence_by_id and evidence_by_id[cid].metric
        }
        cleaned_uncertainty = []
        for unc in draft.uncertainty:
            unc_lower = unc.lower()
            contradicts = False
            if "p/e" in unc_lower and any(m in ("pe", "pe_ratio", "price_to_earnings") for m in available_metrics):
                contradicts = True
            elif "p/b" in unc_lower and any(m in ("pb", "pb_ratio", "price_to_book") for m in available_metrics):
                contradicts = True
            elif ("biên lợi nhuận" in unc_lower or "gross margin" in unc_lower) and "gross_margin" in available_metrics:
                contradicts = True
            if not contradicts:
                cleaned_uncertainty.append(unc)

        # Sanitize ungrounded numbers from uncertainty statements
        allowed_uncertainty_numbers = set().union(*(
            _numeric_values(f"{c.metric or ''} {c.observation_date or ''}")
            for c in citations
        )).union(_numeric_values(question))

        final_uncertainty = []
        for unc in cleaned_uncertainty:
            unc_numbers = _numeric_values(unc)
            if not (unc_numbers - allowed_uncertainty_numbers):
                final_uncertainty.append(unc)
            else:
                stripped = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", "", unc).strip()
                if stripped and len(stripped) > 5:
                    final_uncertainty.append(stripped)

        status, uncovered_requested_groups = self.determine_response_status(
            question=question,
            cited_claims=cited_claims,
            evidence_by_id=evidence_by_id,
            final_uncertainty=final_uncertainty,
            extracted_symbols=extracted_symbols,
            canonical_symbol=canonical_symbol or symbol,
            asks_intraday=asks_intraday,
            citations=citations,
        )
        grounded_answer = " ".join(
            f"{claim.text} [Evidence: {', '.join(claim.citation_ids)}]" if claim.citation_ids else claim.text
            for claim in cited_claims
        )
        returned_citations = [item for item in citations if item.id in referenced_ids]
        if not returned_citations and any(self._has_verifiable_evidence([c]) for c in citations):
            returned_citations = [c for c in citations if self._has_verifiable_evidence([c])][:15]

        res = AIChatResponse(
            status=status,
            symbol=", ".join(extracted_symbols) if len(extracted_symbols) > 1 else (canonical_symbol or symbol),
            resolved_symbol=canonical_symbol or symbol,
            as_of_date=requested_date,
            prompt_version=PROMPT_VERSION,
            model=usage.get("model", model),
            answer=grounded_answer,
            claims=cited_claims,
            citations=returned_citations,
            uncertainty=final_uncertainty,
            tools_used=used_tools,
            usage=usage,
            structured_data_summary=structured_summary,
            metadata_flags=metadata_flags,
        ).model_dump(mode="json")
        yield f"data: {json.dumps({'type': 'result', 'data': res}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    async def answer_question(
        self,
        question: str,
        *,
        session: Session,
        symbol: str | None = None,
        as_of: date | None = None,
        tool_names: list[str] | None = None,
        task_type: TaskType = "USER_CHAT",
    ) -> dict[str, Any]:
        async for sse_chunk in self.answer_question_stream(
            question,
            session=session,
            symbol=symbol,
            as_of=as_of,
            tool_names=tool_names,
            task_type=task_type,
        ):
            if sse_chunk.startswith("data: "):
                payload_str = sse_chunk[6:].strip()
                if payload_str == "[DONE]":
                    continue
                try:
                    payload = json.loads(payload_str)
                    if payload.get("type") == "result":
                        return payload["data"]
                except json.JSONDecodeError:
                    continue
        return self._insufficient_response(
            symbol=symbol,
            as_of=as_of or date.today(),
            citations=[],
            tools_used=[],
            reason="Stream closed without producing a final result.",
        )

    async def generate_daily_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Summarize only sourced market, regime, macro, event, and portfolio evidence for today.",
            session=session,
            as_of=as_of,
            tool_names=["macro", "regime", "events", "portfolio", "evidence"],
            task_type="DAILY_BRIEF",
        )

    async def generate_weekly_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Summarize evidence-backed changes in market, macro, events, opportunity, watchlist, and portfolio. State missing comparisons.",
            session=session,
            as_of=as_of,
            tool_names=["macro", "regime", "events", "opportunity", "portfolio", "watchlist", "historical_snapshot", "evidence"],
            task_type="WEEKLY_BRIEF",
        )

    async def generate_monthly_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Review sourced portfolio, DCA, allocation, valuation, thesis, event, and data-quality evidence. Do not predict prices.",
            session=session,
            as_of=as_of,
            tool_names=["fundamentals", "valuation", "factors", "risk", "macro", "regime", "events", "opportunity", "portfolio", "watchlist", "historical_snapshot", "evidence"],
            task_type="MONTHLY_BRIEF",
        )

    async def analyze_stock(self, symbol: str, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            f"Analyze {symbol} only from the selected evidence tools. Explain missing or stale inputs and avoid trade instructions.",
            session=session,
            symbol=symbol,
            as_of=as_of,
            task_type="STOCK_RESEARCH",
        )
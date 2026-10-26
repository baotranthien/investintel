"""Prompt registry and prompt engineering for local InvestIntel AI Analyst."""
from typing import Any
import re

PROMPT_VERSION = "investment_analyst_v2"

SYSTEM_PROMPT = """Bạn là trợ lý phân tích nghiên cứu đầu tư chuyên nghiệp của InvestIntel.
Nhiệm vụ: Phân tích và trả lời câu hỏi của nhà đầu tư bằng tiếng Việt một cách khách quan, chính xác dựa trên dữ liệu bằng chứng được cung cấp.

Quy tắc cốt lõi:
1. Ngôn ngữ: Luôn trả lời 100% bằng tiếng Việt tự nhiên, gãy gọn, đúng văn phong tài chính.
2. Căn cứ dữ liệu & trích dẫn:
   - Mọi nhận định có số liệu tài chính hoặc dữ kiện từ 'verifiable_evidence' PHẢI đặt claim_type='FACT' hoặc 'MODEL_OUTPUT' và gắn đúng citation_ids=['mã_bằng_chứng'] (ví dụ ['E001']). Số liệu nêu trong câu phải khớp chính xác với giá trị trong bằng chứng đó.
   - Nhận định định tính về ngành nghề, rủi ro tổng quát hoặc thông tin dữ liệu còn thiếu từ 'unverified_or_missing_metrics': đặt claim_type='UNCERTAINTY', citation_ids=[]. Không đưa số liệu chưa được trích dẫn vào claim UNCERTAINTY.
3. Tuyệt đối KHÔNG tự sáng tác số liệu tài chính không có trong verifiable_evidence.
4. Cấu trúc JSON trả về (AIAnswerDraft):
   - "answer": Bài phân tích tổng hợp trả lời trực tiếp câu hỏi của nhà đầu tư.
   - "claims": Danh sách các mệnh đề phân tích (mỗi claim độc lập, có claim_type và citation_ids phù hợp).
   - "uncertainty": Danh sách các chỉ số định giá hoặc dữ liệu còn thiếu/chưa kiểm chứng."""


def build_chat_prompt(question: str, context: dict[str, Any]) -> str:
    import json

    compact_context: dict[str, Any] = {}
    if "symbol" in context:
        compact_context["symbol"] = context["symbol"]
    if "as_of" in context or "as_of_date" in context:
        compact_context["as_of_date"] = str(context.get("as_of_date") or context.get("as_of"))

    # Asset profile without rogue un-indexed numeric tables
    for t in context.get("tools", []):
        if isinstance(t, dict) and t.get("name") == "asset" and isinstance(t.get("data"), dict):
            asset_data = t["data"]
            compact_context["asset_profile"] = {
                "symbol": asset_data.get("symbol"),
                "name": asset_data.get("name"),
                "sector": asset_data.get("sector"),
                "exchange": asset_data.get("exchange"),
                "asset_type": asset_data.get("asset_type"),
            }
            break

    # Extract ONLY verifiable evidence for citation
    raw_evidence = context.get("evidence_register") or context.get("evidence") or []
    verifiable_evidence = []
    missing_indicators = []

    for idx, item in enumerate(raw_evidence, start=1):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id") or f"E{idx:03d}"
        val = item.get("value")
        metric = item.get("metric")
        claim_type = item.get("claim_type")
        origin = item.get("data_origin")
        freshness = item.get("freshness")
        source = item.get("source")

        is_verifiable = (
            claim_type in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
            and bool(source)
            and origin not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
            and freshness not in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
            and val is not None
        )
        if is_verifiable:
            verifiable_evidence.append({
                "id": item_id,
                "metric": metric,
                "value": val,
                "unit": item.get("unit"),
                "source": source,
            })
        elif metric and freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            missing_indicators.append(metric)

    if verifiable_evidence:
        q_lower = question.lower()
        asks_pb = bool(re.search(r"\b(p/b|pb)\b", q_lower))
        asks_pe = bool(re.search(r"\b(p/e|pe)\b", q_lower))

        def _score(ev: dict[str, Any]) -> int:
            m = str(ev.get("metric") or "").lower()
            s = 0
            if ("giá" in q_lower or "price" in q_lower) and m == "price":
                s += 100
            if ("doanh thu" in q_lower or "revenue" in q_lower) and m in {"revenue", "revenue_yoy", "gross_margin"}:
                s += 100
            if ("lợi nhuận" in q_lower or "income" in q_lower or "profit" in q_lower) and m in {"net_income", "net_income_yoy", "net_margin"}:
                s += 90
            if "roe" in q_lower and m == "roe":
                s += 120
            if "roa" in q_lower and m == "roa":
                s += 120
            if asks_pb and m in {"pb", "pb_ratio", "price_to_book"}:
                s += 150
            if asks_pe and m in {"pe", "pe_ratio", "price_to_earnings"}:
                s += 150
            if asks_pb and not asks_pe and m in {"pe", "pe_ratio", "price_to_earnings"}:
                s -= 500  # Explicitly exclude PE when PB is specifically asked
            if asks_pe and not asks_pb and m in {"pb", "pb_ratio", "price_to_book"}:
                s -= 500  # Explicitly exclude PB when PE is specifically asked
            if ("định giá" in q_lower or "valuation" in q_lower) and not asks_pb and not asks_pe and m in {"pe", "pb"}:
                s += 50
            if "eps" in q_lower and m in {"eps_ttm", "eps_yoy"}:
                s += 100
            if "bvps" in q_lower and m == "bvps":
                s += 100
            return s

        verifiable_evidence.sort(key=_score, reverse=True)
        selected_evidence = []
        for item in verifiable_evidence[:8]:
            val = item.get("value")
            if isinstance(val, float):
                clean_val = round(val, 2)
            else:
                clean_val = val
            selected_evidence.append({
                "id": item.get("id"),
                "metric": item.get("metric"),
                "value": clean_val,
                "unit": item.get("unit"),
                "source": item.get("source"),
            })
        compact_context["verifiable_evidence"] = selected_evidence
    if missing_indicators:
        compact_context["unverified_or_missing_metrics"] = list(dict.fromkeys(missing_indicators))[:15]

    return (
        f"Câu hỏi của nhà đầu tư:\n{question}\n\n"
        "Dữ liệu bằng chứng được cung cấp (JSON):\n"
        f"{json.dumps(compact_context, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
        "Yêu cầu trả lời bằng tiếng Việt (JSON) tuân thủ cấu trúc AIAnswerDraft:\n"
        "- 'answer': Bài phân tích tổng hợp trả lời trực tiếp câu hỏi của nhà đầu tư.\n"
        "- 'claims': Danh sách các mệnh đề logic độc lập:\n"
        "  + BẮT BUỘC: Mỗi mệnh đề chứa số liệu phải trích dẫn ĐÚNG mã 'id' tương ứng của chỉ số đó trong danh sách verifiable_evidence (ví dụ: số liệu định giá P/B trích dẫn đúng ID có metric='pb', số liệu P/E trích dẫn đúng ID có metric='pe', số liệu ROE trích dẫn đúng ID có metric='roe'). Tuyệt đối không gán ID của 'pe' cho 'pb' hay ngược lại.\n"
        "  + Nếu câu hỏi yêu cầu cả P/B và ROE: BẮT BUỘC trả lời đầy đủ CẢ HAI chỉ số trong claims độc lập.\n"
        "  + Nếu trích dẫn số liệu/dữ kiện từ verifiable_evidence: claim_type='FACT' hoặc 'MODEL_OUTPUT' và citation_ids=['mã_bằng_chứng'].\n"
        "  + Nếu là nhận định định tính, rủi ro, hoặc dữ liệu thiếu từ unverified_or_missing_metrics: claim_type='UNCERTAINTY' và citation_ids=[].\n"
        "- 'uncertainty': Danh sách các yếu tố hoặc chỉ số còn thiếu/chưa được kiểm chứng."
    )
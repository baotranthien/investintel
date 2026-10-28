"""Prompt registry and prompt engineering for local InvestIntel AI Analyst."""
from typing import Any
import re

PROMPT_VERSION = "investment_analyst_v2"

SYSTEM_PROMPT = """Bạn là trợ lý phân tích nghiên cứu đầu tư chuyên nghiệp của InvestIntel.
Nhiệm vụ: Phân tích và trả lời câu hỏi của nhà đầu tư bằng tiếng Việt một cách khách quan, chính xác dựa trên dữ liệu bằng chứng được cung cấp.

Quy tắc cốt lõi:
1. Ngôn ngữ & Thuật ngữ:
   - Luôn trả lời 100% bằng tiếng Việt tự nhiên, gãy gọn, đúng văn phong tài chính.
   - Đơn vị 'VND/share' dịch chuẩn là 'VND/cổ phiếu', tuyệt đối không dịch là 'VND/thành viên'.
   - Chỉ số P/E là hệ số định giá (lần), không bao giờ được gọi là lợi nhuận hoặc doanh thu.
   - Biên lợi nhuận (gross_margin) là tỷ suất sinh lời, không được nhầm lẫn với tăng trưởng hay suy giảm doanh thu.
2. Căn cứ dữ liệu & trích dẫn:
   - Mọi nhận định có số liệu tài chính hoặc dữ kiện từ 'verifiable_evidence' PHẢI đặt claim_type='FACT' hoặc 'MODEL_OUTPUT' và gắn đúng citation_ids=['mã_bằng_chứng'] (ví dụ ['E001']).
   - Phân biệt rõ từng mã cổ phiếu: Chỉ số của công ty nào (xem trường 'symbol' trong bằng chứng) PHẢI gán đúng cho công ty đó. Tuyệt đối không dùng số liệu của mã này để gán cho mã khác trong câu so sánh.
   - Nếu bằng chứng có 'is_estimate': true hoặc có 'note' ghi nhận việc sử dụng số cổ phiếu cuối kỳ (period-end shares fallback), BẮT BUỘC phải nêu rõ đây là số liệu ước tính dựa trên số cổ phiếu cuối kỳ, không gọi là số liệu chính xác tuyệt đối.
3. Nhất quán và Dữ liệu chưa chắc chắn:
   - Nếu một chỉ số đã được cung cấp trong verifiable_evidence và đưa vào claims, TUYỆT ĐỐI KHÔNG ghi trong 'uncertainty' rằng chỉ số đó bị thiếu hay chưa cung cấp.
   - Với các mã cổ phiếu hoặc chỉ tiêu không có dữ liệu, nêu rõ trong claims (claim_type='UNCERTAINTY', citation_ids=[]) hoặc trong 'uncertainty'.
4. Cấu trúc JSON trả về (AIAnswerDraft):
   - "answer": Bài phân tích tổng hợp trả lời trực tiếp câu hỏi của nhà đầu tư.
   - "claims": Danh sách các mệnh đề phân tích (mỗi claim độc lập, có claim_type và citation_ids phù hợp).
   - "uncertainty": Danh sách các chỉ số hoặc yếu tố thực sự còn thiếu/chưa kiểm chứng."""


def build_chat_prompt(question: str, context: dict[str, Any]) -> str:
    import json

    compact_context: dict[str, Any] = {}
    if "symbol" in context:
        compact_context["symbol"] = context["symbol"]
    if "symbols" in context:
        compact_context["symbols"] = context["symbols"]
    if "as_of" in context or "as_of_date" in context:
        compact_context["as_of_date"] = str(context.get("as_of_date") or context.get("as_of"))

    # Asset profile without rogue un-indexed numeric tables
    for t in context.get("tools", []):
        if isinstance(t, dict) and t.get("name") == "asset" and isinstance(t.get("data"), (dict, list)):
            compact_context["asset_profile"] = t["data"]
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
            entry = {
                "id": item_id,
                "metric": metric,
                "value": val,
                "unit": item.get("unit"),
                "source": source,
            }
            if item.get("symbol"):
                entry["symbol"] = item.get("symbol")
            if item.get("is_estimate"):
                entry["is_estimate"] = True
            if item.get("diagnostic_reason"):
                entry["diagnostic_reason"] = item.get("diagnostic_reason")
            if item.get("note"):
                entry["note"] = item.get("note")
            verifiable_evidence.append(entry)
        elif metric and freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            missing_indicators.append(metric)

    if verifiable_evidence:
        q_lower = question.lower()
        asks_pb = bool(re.search(r"\b(p/b|pb)\b", q_lower))
        asks_pe = bool(re.search(r"\b(p/e|pe)\b", q_lower))
        query_symbols = [str(s).lower() for s in (context.get("symbols") or ([context.get("symbol")] if context.get("symbol") else []))]

        def _score(ev: dict[str, Any]) -> int:
            m = str(ev.get("metric") or "").lower()
            sym = str(ev.get("symbol") or "").lower()
            s = 0
            if sym and sym in query_symbols:
                s += 200
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
        max_evidence_items = 20 if len(query_symbols) > 1 else 10
        selected_evidence = []
        for item in verifiable_evidence[:max_evidence_items]:
            val = item.get("value")
            if isinstance(val, float):
                clean_val = round(val, 2)
            else:
                clean_val = val
            ev_entry = {
                "id": item.get("id"),
                "metric": item.get("metric"),
                "value": clean_val,
                "unit": item.get("unit"),
                "source": item.get("source"),
            }
            if item.get("symbol"):
                ev_entry["symbol"] = item.get("symbol")
            if item.get("is_estimate"):
                ev_entry["is_estimate"] = True
            if item.get("diagnostic_reason"):
                ev_entry["diagnostic_reason"] = item.get("diagnostic_reason")
            if item.get("note"):
                ev_entry["note"] = item.get("note")
            selected_evidence.append(ev_entry)
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
        "  + BẮT BUỘC: Mỗi mệnh đề chứa số liệu phải trích dẫn ĐÚNG mã 'id' tương ứng của chỉ số đó trong danh sách verifiable_evidence.\n"
        "  + Nếu phân tích nhiều mã cổ phiếu: ghi rõ mã cổ phiếu trong câu và chỉ trích dẫn đúng ID thuộc về mã đó.\n"
        "  + Nếu chỉ số có 'is_estimate': true hoặc dùng số cổ phiếu cuối kỳ (fallback shares), BẮT BUỘC nêu rõ đây là ước tính.\n"
        "  + Nếu trích dẫn số liệu/dữ kiện từ verifiable_evidence: claim_type='FACT' hoặc 'MODEL_OUTPUT' và citation_ids=['mã_bằng_chứng'].\n"
        "  + Nếu là nhận định định tính, rủi ro, hoặc dữ liệu thiếu từ unverified_or_missing_metrics: claim_type='UNCERTAINTY' và citation_ids=[].\n"
        "- 'uncertainty': Danh sách các yếu tố hoặc chỉ số còn thiếu/chưa được kiểm chứng (không lặp lại các chỉ số đã có bằng chứng)."
    )
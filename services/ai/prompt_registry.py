"""Prompt registry and prompt engineering for local InvestIntel AI Analyst."""
from typing import Any

PROMPT_VERSION = "investment_analyst_v2"

SYSTEM_PROMPT = """Bạn là trợ lý phân tích nghiên cứu đầu tư chuyên nghiệp của InvestIntel.
Nhiệm vụ: Phân tích và trả lời đầy đủ câu hỏi của nhà đầu tư bằng tiếng Việt, dựa trên dữ liệu được cung cấp.

Quy tắc cốt lõi:
1. Ngôn ngữ: Luôn trả lời 100% bằng tiếng Việt tự nhiên, gãy gọn, đúng văn phong tài chính. Tuyệt đối không sao chép quy tắc tiếng Anh vào nội dung.
2. Trả lời đầy đủ từng phần trong câu hỏi bằng cách phân rã thành các claims riêng biệt trong 'claims':
   - Claim về lĩnh vực hoạt động: Nêu rõ lĩnh vực, ngành nghề kinh doanh dựa vào 'asset_profile' (claim_type='UNCERTAINTY', citation_ids=[]).
   - Các claims về rủi ro đầu tư: Trình bày các rủi ro đầu tư chính (ví dụ rủi ro cạnh tranh công nghệ toàn cầu, rủi ro biến động tỷ giá ngoại tệ, rủi ro nhân lực hoặc chu kỳ kinh tế) (claim_type='UNCERTAINTY', citation_ids=[]).
   - Claim về dữ liệu định giá còn thiếu: Nêu rõ các chỉ số định giá còn thiếu trong 'unverified_or_missing_metrics' (như P/E, P/B, EV/EBITDA, CAGR 3 năm/5 năm) khiến hệ thống chưa thể kết luận định giá (claim_type='UNCERTAINTY', citation_ids=[]).
   - Các claims số liệu tài chính (nếu có trích dẫn số từ 'verifiable_evidence'): claim_type='FACT' hoặc 'MODEL_OUTPUT' và citation_ids=["mã_bằng_chứng"]. Số liệu trong câu phải khớp chính xác với value của mã đó.
3. Tuyệt đối KHÔNG tự sáng tác số liệu tài chính không có trong verifiable_evidence.
4. Cấu trúc JSON trả về:
   - "answer": Bài phân tích tổng hợp hoàn chỉnh bằng tiếng Việt bao gồm giới thiệu ngành, các rủi ro chính, và kết luận về dữ liệu định giá.
   - "claims": Danh sách các mệnh đề phân tích (ít nhất 3-5 claims tương ứng với từng nội dung: ngành nghề, các rủi ro, và dữ liệu định giá còn thiếu).
   - "uncertainty": Danh sách các chỉ số định giá còn thiếu trong InvestIntel."""


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
        compact_context["verifiable_evidence"] = verifiable_evidence[:30]
    if missing_indicators:
        compact_context["unverified_or_missing_metrics"] = list(dict.fromkeys(missing_indicators))[:15]

    return (
        f"Câu hỏi của nhà đầu tư:\n{question}\n\n"
        "Dữ liệu bằng chứng được cung cấp (JSON):\n"
        f"{json.dumps(compact_context, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
        "Yêu cầu trả lời bằng tiếng Việt (JSON): Trả lời đầy đủ 3 ý theo yêu cầu của câu hỏi trong mảng 'claims':\n"
        "1. Lĩnh vực hoạt động: Nêu tên công ty và lĩnh vực/ngành kinh doanh dựa trên asset_profile (claim_type='UNCERTAINTY', citation_ids=[]).\n"
        "2. Rủi ro đầu tư: Nêu 3 rủi ro chính (claim_type='UNCERTAINTY', citation_ids=[]).\n"
        "3. Dữ liệu thiếu để định giá: Nêu các chỉ số thiếu từ unverified_or_missing_metrics (claim_type='UNCERTAINTY', citation_ids=[]).\n"
        "Nếu trích dẫn số liệu cụ thể từ verifiable_evidence, đặt claim_type='FACT' và gắn đúng citation_ids."
    )
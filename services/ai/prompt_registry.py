"""Prompt registry and prompt engineering for local InvestIntel AI Analyst."""
from typing import Any
import re

PROMPT_VERSION = "investment_analyst_v2"

METRIC_CATEGORY_PATTERNS: dict[str, tuple[list[str], set[str]]] = {
    # Valuation & Multiples
    "pe": (
        [r"\b(p\/e|pe|price[-\s]to[-\s]earnings|hệ\s*số\s*p\/e)\b"],
        {"pe", "pe_ratio", "price_to_earnings"},
    ),
    "pb": (
        [r"\b(p\/b|pb|price[-\s]to[-\s]book|hệ\s*số\s*p\/b)\b"],
        {"pb", "pb_ratio", "price_to_book"},
    ),
    "roe": (
        [r"\b(roe|lợi\s*nhuận\s*trên\s*vốn\s*chủ|sinh\s*lời\s*trên\s*vốn)\b"],
        {"roe"},
    ),
    "roa": (
        [r"\b(roa|sinh\s*lời\s*trên\s*tài\s*sản)\b"],
        {"roa"},
    ),
    # Profitability Margins (atomic)
    "gross_margin": (
        [r"\b(biên\s*gộp|biên\s*lợi\s*nhuận\s*gộp|gross\s*margin)\b"],
        {"gross_margin"},
    ),
    "net_margin": (
        [r"\b(biên\s*ròng|biên\s*lợi\s*nhuận\s*ròng|net\s*margin)\b"],
        {"net_margin"},
    ),
    "operating_margin": (
        [r"\b(biên\s*hoạt\s*động|biên\s*ebit|operating\s*margin)\b"],
        {"operating_margin", "ebit_margin"},
    ),
    "margins_generic": (
        [r"\b(biên\s*lợi\s*nhuận|margins?)\b"],
        {"gross_margin", "net_margin", "ebit_margin"},
    ),
    # Revenue & Income
    "revenue": (
        [r"\b(doanh\s*thu(?!\s*(?:tăng\s*trưởng|yoy|cagr))|revenue(?!\s*(?:growth|yoy)))\b"],
        {"revenue"},
    ),
    "revenue_yoy": (
        [r"\b(tăng\s*trưởng\s*doanh\s*thu|doanh\s*thu\s*tăng\s*trưởng|doanh\s*thu\s*yoy|revenue\s*(?:growth|yoy))\b"],
        {"revenue_yoy"},
    ),
    "net_income": (
        [r"\b(lợi\s*nhuận\s*sau\s*thuế|lợi\s*nhuận\s*ròng|lãi\s*ròng|net\s*income|lnst)\b"],
        {"net_income", "net_income_yoy"},
    ),
    "eps": (
        [r"\b(eps|thu\s*nhập\s*mỗi\s*cổ\s*phiếu|thu\s*nhập\s*trên\s*mỗi\s*cổ\s*phiếu|lãi\s*cơ\s*bản)\b"],
        {"eps_ttm", "eps_yoy"},
    ),
    "price": (
        [r"\b(giá\s*cổ\s*phiếu|giá\s*đóng\s*cửa|thị\s*giá|price)\b"],
        {"price"},
    ),
    # Debt & Capital Structure (atomic)
    "debt_to_assets": (
        [r"\b(nợ\s*(?:phải\s*trả)?\s*[\/\:]\s*(?:tổng\s*)?tài\s*sản|nợ\s*(?:phải\s*trả)?\s*trên\s*(?:tổng\s*)?tài\s*sản|debt\s*(?:to|[\/])\s*assets?)\b"],
        {"debt_to_assets"},
    ),
    "debt_to_equity": (
        [r"\b(nợ\s*(?:vay|phải\s*trả)?\s*[\/\:]\s*vốn\s*chủ(?:\s*sở\s*hữu)?|nợ\s*(?:vay)?\s*trên\s*vốn(?:\s*chủ(?:\s*sở\s*hữu)?)?|d\/e|de\s*ratio|debt\s*(?:to|[\/])\s*equity)\b"],
        {"de_ratio"},
    ),
    "net_debt_ebitda": (
        [r"\b(nợ\s*ròng\s*[\/\:]\s*ebitda|nợ\s*ròng\s*trên\s*ebitda|net\s*debt\s*(?:to|[\/])\s*ebitda)\b"],
        {"net_debt_ebitda"},
    ),
    "total_debt": (
        [r"\b(tổng\s*nợ(?:\s*vay)?|vay\s*nợ|total\s*debt)\b"],
        {"total_debt", "short_term_debt", "long_term_debt"},
    ),
    "debt_generic": (
        [r"\b(tỷ\s*lệ\s*nợ|đòn\s*bẩy(?:\s*tài\s*chính)?|leverage)\b"],
        {"debt_to_assets", "de_ratio", "net_debt_ebitda"},
    ),
    # Cash & Cash Flow (atomic)
    "cash_balance": (
        [r"\b(tiền\s*và\s*tương\s*đương\s*tiền|tiền\s*mặt(?:\s*hiện\s*tại)?|lượng\s*tiền(?:\s*mặt)?|số\s*dư\s*tiền|tiền\s*hiện\s*tại|tiền\s*hiện\s*có|cash\s*balance)\b"],
        {"cash"},
    ),
    "operating_cash_flow": (
        [r"\b(lưu\s*chuyển\s*tiền\s*thuần\s*từ\s*(?:hđkd|hoạt\s*động\s*kinh\s*doanh)|dòng\s*tiền\s*(?:từ\s*)?(?:hoạt\s*động(?:\s*kinh\s*doanh)?|hđkd)|operating\s*cash\s*flow|cfo)\b"],
        {"cfo"},
    ),
    "cash_flow_generic": (
        [r"\b(dòng\s*tiền|lưu\s*chuyển\s*tiền|cash\s*flow|fcf)\b"],
        {"cfo", "fcf", "cfo_to_ni", "fcf_to_ni"},
    ),
    # Solvency & Liquidity
    "solvency_liquidity": (
        [r"\b(thanh\s*khoản|khả\s*năng\s*thanh\s*toán|current\s*ratio|quick\s*ratio)\b"],
        {"current_ratio", "quick_ratio", "interest_coverage"},
    ),
    "valuation_multiples": (
        [r"\b(định\s*giá|valuation|bội\s*số)\b"],
        {"pe", "pb", "ev_ebitda"},
    ),
    "comparison": (
        [r"\b(so\s*sánh|chênh\s*lệch|compare|difference)\b"],
        {"pe_diff", "pb_diff", "roe_diff"},
    ),
    "bank_metrics": (
        [r"\b(nim|casa|tín\s*dụng|credit\s*growth|nợ\s*xấu|npl|llr)\b"],
        {"nim", "casa_ratio", "credit_growth", "npl_ratio", "llr_ratio"},
    ),
    "macro_commodity": (
        [r"\b(giá\s*dầu|oil|brent|wti|tương\s*quan|correlation|lạm\s*phát|cpi|tỷ\s*giá|usd\/vnd)\b"],
        {"pearson_correlation", "brent", "wti", "commodity_close", "commodity_change_pct", "FX_USDVND", "VNM_CPI_YOY"},
    ),
    "operating_expense": (
        [r"\b(chi\s*phí\s*hoạt\s*động|chi\s*phí\s*bán\s*hàng|chi\s*phí\s*quản\s*lý|opex|sga)\b"],
        {"operating_expense", "sga", "operating_cost"},
    ),
}


def extract_requested_metric_groups(question: str) -> dict[str, set[str]]:
    """Extract financial metric groups explicitly mentioned in a Vietnamese question with strict disambiguation."""
    q_lower = question.lower()
    requested: dict[str, set[str]] = {}
    for cat, (patterns, metrics) in METRIC_CATEGORY_PATTERNS.items():
        if any(re.search(pat, q_lower) for pat in patterns):
            requested[cat] = set(metrics)

    # 1. Disambiguate generic margins vs specific margins
    if ("gross_margin" in requested or "net_margin" in requested or "operating_margin" in requested) and "margins_generic" in requested:
        del requested["margins_generic"]

    # 2. Disambiguate generic debt vs specific debt ratios
    if ("debt_to_assets" in requested or "debt_to_equity" in requested or "net_debt_ebitda" in requested or "total_debt" in requested) and "debt_generic" in requested:
        del requested["debt_generic"]

    # 3. Disambiguate generic cash flow vs specific cash flow / cash balance
    if "operating_cash_flow" in requested and "cash_flow_generic" in requested:
        del requested["cash_flow_generic"]

    # 4. Disambiguate cash balance vs cash flow when only cash balance is meant
    # E.g. "tiền mặt hiện tại" should not trigger cash flow if no flow keyword was used
    if "cash_balance" in requested and "cash_flow_generic" in requested:
        if not re.search(r"\b(dòng\s*tiền|lưu\s*chuyển\s*tiền|cash\s*flow|fcf)\b", q_lower):
            del requested["cash_flow_generic"]

    # 5. Disambiguate margin phrasing (e.g. 'biên lợi nhuận gộp') from standalone net income requests
    if "net_income" in requested:
        q_no_margin = re.sub(r"\bbiên\s+(?:lợi\s+nhuận|gộp|ròng|hoạt\s*động|ebit)\b", "", q_lower)
        if not any(re.search(pat, q_no_margin) for pat in [
            r"\b(lợi\s*nhuận\s*sau\s*thuế|lợi\s*nhuận\s*ròng|lãi\s*ròng|net\s*income|lnst)\b"
        ]):
            del requested["net_income"]

    # 6. Disambiguate revenue growth vs revenue
    if "revenue_yoy" in requested and "revenue" in requested:
        q_no_growth = re.sub(r"\b(?:tăng\s*trưởng\s*doanh\s*thu|doanh\s*thu\s*tăng\s*trưởng|doanh\s*thu\s*yoy|revenue\s*(?:growth|yoy))\b", "", q_lower)
        if not re.search(r"\b(doanh\s*thu|revenue)\b", q_no_growth):
            del requested["revenue"]

    # 7. Disambiguate valuation ("định giá cổ phiếu") from stock price ("giá cổ phiếu")
    if "price" in requested and "valuation_multiples" in requested:
        q_no_val = re.sub(r"\bđịnh\s*giá(?:\s*cổ\s*phiếu)?\b", "", q_lower)
        if not re.search(r"\b(giá\s*cổ\s*phiếu|giá\s*đóng\s*cửa|thị\s*giá|price)\b", q_no_val):
            del requested["price"]

    return requested


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
3. Chỉ số tính toán sẵn (Pre-computed Metrics):
   - Các chỉ số: biên lợi nhuận ròng ('net_margin'), chênh lệch P/E và P/B giữa các mã ('pe_diff', 'pb_diff'), hệ số tương quan Pearson ('pearson_correlation'), chỉ số ngân hàng ('nim', 'casa_ratio', 'credit_growth', 'npl_ratio') ĐÃ ĐƯỢC TÍNH SẴN bằng Python trong danh sách verifiable_evidence.
   - Hãy trích dẫn trực tiếp các con số có sẵn này kèm mã ID bằng chứng tương ứng. Tuyệt đối không tự làm toán hay tính nhẩm trong đầu.
4. Nhất quán và Dữ liệu chưa chắc chắn:
   - Nếu một chỉ số đã được cung cấp trong verifiable_evidence và đưa vào claims, TUYỆT ĐỐI KHÔNG ghi trong 'uncertainty' rằng chỉ số đó bị thiếu hay chưa cung cấp.
   - Với các mã cổ phiếu hoặc chỉ tiêu không có dữ liệu, nêu rõ trong claims (claim_type='UNCERTAINTY', citation_ids=[]) hoặc trong 'uncertainty'.
5. Cấu trúc JSON trả về (AIAnswerDraft):
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

    missing_requested_metrics: list[str] = []
    if verifiable_evidence:
        q_lower = question.lower()
        asks_pb = bool(re.search(r"\b(p/b|pb)\b", q_lower))
        asks_pe = bool(re.search(r"\b(p/e|pe)\b", q_lower))
        query_symbols = [str(s).lower() for s in (context.get("symbols") or ([context.get("symbol")] if context.get("symbol") else []))]
        requested_groups = extract_requested_metric_groups(question)

        # 1. Scoring helper for fallback ranking and general context
        def _score(ev: dict[str, Any]) -> int:
            m = str(ev.get("metric") or "").lower()
            sym = str(ev.get("symbol") or "").lower()
            s = 0
            if sym and sym in query_symbols:
                s += 200
            # Direct boost for metrics belonging to explicitly requested groups
            for cat_name, cands in requested_groups.items():
                if m in cands:
                    s += 250
                    break
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
            if ("so sánh" in q_lower or "compare" in q_lower) and m in {"pe_diff", "pb_diff"}:
                s += 250
            if m in {"pe_diff", "pb_diff"} and len(query_symbols) > 1:
                s += 200
            if ("tương quan" in q_lower or "correlation" in q_lower or "giá dầu" in q_lower or "dầu" in q_lower) and m in {"pearson_correlation", "brent", "wti", "commodity_close", "commodity_change_pct"}:
                s += 280
            if any(term in q_lower for term in ("tín dụng", "nim", "casa", "nợ xấu", "ngân hàng", "npl")) and m in {"credit_growth", "nim", "casa_ratio", "npl_ratio", "llr_ratio"}:
                s += 250
            if "eps" in q_lower and m in {"eps_ttm", "eps_yoy"}:
                s += 100
            if "bvps" in q_lower and m == "bvps":
                s += 100
            if "nợ" in q_lower and m in {"debt_to_assets", "de_ratio", "net_debt_ebitda"}:
                s += 130
            if ("dòng tiền" in q_lower or "tiền" in q_lower) and m in {"cfo", "fcf", "cash", "cfo_to_ni", "fcf_to_ni"}:
                s += 110
            return s

        # 2. Dynamic context budget based on requested metric complexity
        num_requested = len(requested_groups)
        if num_requested <= 2:
            max_evidence_items = 10 if len(query_symbols) > 1 else 6
        else:
            # Scale budget to ensure each requested category gets representation
            if len(query_symbols) > 1:
                max_evidence_items = min(22, max(12, num_requested * 2))
            else:
                max_evidence_items = min(16, max(8, num_requested + 3))

        selected_evidence = []
        selected_ids: set[str] = set()

        # 3. Intent-first selection: satisfy each requested metric group
        for cat_name, candidate_metrics in requested_groups.items():
            # Find matching items in verifiable_evidence
            cat_items = [ev for ev in verifiable_evidence if str(ev.get("metric") or "").lower() in candidate_metrics]
            if query_symbols:
                target_sym_items = [ev for ev in cat_items if str(ev.get("symbol") or "").lower() in query_symbols]
                if target_sym_items:
                    cat_items = target_sym_items

            if cat_items:
                # Sort category items by preference (_score descending)
                cat_items.sort(key=_score, reverse=True)
                # Take up to 2 items for composite groups (like margins, revenue+growth), 1 for single metrics
                take_count = 2 if cat_name in {"margins_generic", "revenue", "net_income"} else 1
                for item in cat_items[:take_count]:
                    if item.get("id") not in selected_ids and len(selected_evidence) < max_evidence_items:
                        selected_ids.add(item.get("id"))
                        val = item.get("value")
                        clean_val = round(val, 2) if isinstance(val, float) else val
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
            else:
                # Requested metric was not found in verifiable evidence
                # Check if it was in missing_indicators (e.g. de_ratio, net_debt_ebitda)
                for cand in candidate_metrics:
                    if cand in missing_indicators:
                        missing_requested_metrics.append(cand)
                    elif not any(cand == str(ev.get("metric") or "").lower() for ev in verifiable_evidence):
                        missing_requested_metrics.append(cand)

        # 4. Fill remaining slots from globally scored verifiable evidence
        verifiable_evidence.sort(key=_score, reverse=True)
        for item in verifiable_evidence:
            if len(selected_evidence) >= max_evidence_items:
                break
            if item.get("id") in selected_ids:
                continue
            selected_ids.add(item.get("id"))
            val = item.get("value")
            clean_val = round(val, 2) if isinstance(val, float) else val
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

        # Add diagnostic evidence telemetry into context
        telemetry_info = {
            "total_candidates": len(raw_evidence),
            "total_verifiable": len(verifiable_evidence),
            "selected_count": len(selected_evidence),
            "requested_categories": list(requested_groups.keys()),
            "missing_requested_metrics": list(dict.fromkeys(missing_requested_metrics)),
            "context_budget": max_evidence_items,
        }
        compact_context["evidence_telemetry"] = telemetry_info
        if isinstance(context, dict):
            context["evidence_telemetry"] = telemetry_info

    # Assemble unverified or missing metrics, placing requested missing metrics first
    all_missing = list(dict.fromkeys(missing_requested_metrics + missing_indicators))
    if all_missing:
        compact_context["unverified_or_missing_metrics"] = all_missing[:6]

    return (
        f"Câu hỏi của nhà đầu tư:\n{question}\n\n"
        "Dữ liệu bằng chứng được cung cấp (JSON):\n"
        f"{json.dumps(compact_context, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
        "Yêu cầu trả lời bằng tiếng Việt (JSON) tuân thủ cấu trúc AIAnswerDraft:\n"
        "- Trả lời ngắn gọn, súc tích trong 150-200 từ.\n"
        "- 'answer': Bài phân tích súc tích (1-2 đoạn ngắn) trả lời trực tiếp câu hỏi.\n"
        "- 'claims': Danh sách từ 3 đến 5 mệnh đề logic cốt lõi (ngắn gọn, mỗi mệnh đề 1 câu):\n"
        "  + BẮT BUỘC: Mỗi mệnh đề chứa số liệu phải trích dẫn ĐÚNG mã 'id' tương ứng của chỉ số đó trong danh sách verifiable_evidence.\n"
        "  + Nếu phân tích nhiều mã cổ phiếu: ghi rõ mã cổ phiếu trong câu và chỉ trích dẫn đúng ID thuộc về mã đó.\n"
        "  + Nếu chỉ số có 'is_estimate': true hoặc dùng số cổ phiếu cuối kỳ (fallback shares), BẮT BUỘC nêu rõ đây là ước tính.\n"
        "  + Nếu trích dẫn số liệu/dữ kiện từ verifiable_evidence: claim_type='FACT' hoặc 'MODEL_OUTPUT' và citation_ids=['mã_bằng_chứng'].\n"
        "  + Nếu là nhận định định tính, rủi ro, hoặc dữ liệu thiếu từ unverified_or_missing_metrics: claim_type='UNCERTAINTY' và citation_ids=[].\n"
        "- 'uncertainty': Tối đa 2-3 gạch đầu dòng ngắn gọn về các chỉ số còn thiếu (không lặp lại các chỉ số đã có bằng chứng).\n\n"
        "QUY ĐỊNH BẮT BUỘC VỀ ĐỘ DÀI: Xuất tối đa 2 đến 3 claims ngắn gọn (mỗi câu dưới 20 từ). "
        "Phần 'answer' gồm 1 đến 2 câu súc tích. Hoàn thành toàn bộ JSON trong dưới 200 từ."
    )
"""Prompt registry and prompt engineering for local InvestIntel AI Analyst."""
from typing import Any
import re

def _strip_vietnamese_accents(text: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.replace("đ", "d").replace("Đ", "D")


def _has_match(pattern: str, text: str) -> bool:
    if re.search(pattern, text):
        return True
    return bool(re.search(_strip_vietnamese_accents(pattern), _strip_vietnamese_accents(text)))


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
        [r"\b(roe|lợi\s*nhuận\s*trên\s*vốn\s*chủ|sinh\s*lời\s*trên\s*vốn(?!\s*(?:đầu\s*tư|hoạt\s*động|hóa|hoá)))\b"],
        {"roe"},
    ),
    "roic": (
        [r"\b(roic|return\s*on\s*invested\s*capital|lợi\s*nhuận\s*trên\s*vốn\s*(?:đầu\s*tư|hoạt\s*động))\b"],
        {"roic"},
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
        [
            r"\b(giá\s*(?:cổ\s*phiếu|đóng\s*cửa|hôm\s*qua|hôm\s*nay|hiện\s*tại|phiên\s*gần\s*nhất|bao\s*nhiêu)?|thị\s*giá|price|closing\s*price)\b",
            r"\b(gia\s*(?:co\s*phieu|dong\s*cua|hom\s*qua|hom\s*nay|hien\s*tai|phien\s*gan\s*nhat|bao\s*nhieu)?|thi\s*gia)\b",
        ],
        {"price"},
    ),
    "price_change": (
        [
            r"\b(tăng\s*hay\s*giảm|biến\s*động\s*giá|thay\s*đổi\s*giá|so\s*với\s*hôm\s*qua|so\s*với\s*phiên\s*trước|giá.*?(?:tăng|giảm).*?(?:hôm\s*qua|phiên\s*trước))\b",
            r"\b(tang\s*hay\s*giam|bien\s*dong\s*gia|thay\s*doi\s*gia|so\s*voi\s*hom\s*qua|so\s*voi\s*phien\s*truoc|gia.*?(?:tang|giam).*?(?:hom\s*qua|phien\s*truoc))\b",
        ],
        {"previous_close", "price_change_pct"},
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
    "interest_coverage": (
        [r"\b(khả\s*năng\s*(?:chi\s*trả\s*)?lãi\s*vay|chi\s*trả\s*lãi\s*vay|bao\s*phủ\s*lãi\s*vay|interest\s*coverage)\b"],
        {"interest_coverage"},
    ),
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
    "revenue_commodity_correlation": (
        [r"\b(tương\s*quan\s*doanh\s*thu|doanh\s*thu\s*và\s*(?:giá\s*)?dầu|doanh\s*thu\s*plx|revenue\s*(?:and|to|vs)\s*oil)\b"],
        {"revenue_commodity_correlation"},
    ),
    "macro_commodity": (
        [r"\b(giá\s*dầu|oil|brent|wti|tương\s*quan|correlation|lạm\s*phát|cpi|tỷ\s*giá|usd\/vnd)\b"],
        {"revenue_commodity_correlation", "pearson_correlation", "brent", "wti", "commodity_close", "commodity_change_pct", "FX_USDVND", "VNM_CPI_YOY"},
    ),
    "operating_expense": (
        [r"\b(chi\s*phí\s*hoạt\s*động|chi\s*phí\s*bán\s*hàng|chi\s*phí\s*quản\s*lý|opex|sga)\b"],
        {"operating_expense", "sga", "operating_cost"},
    ),
    "total_equity": (
        [r"\b(vốn\s*chủ(?:\s*sở\s*hữu)?|quy\s*mô\s*vốn(?:\s*chủ)?|total\s*equity|equity\s*size)\b"],
        {"total_equity", "equity", "bvps"},
    ),
    "dcf": (
        [r"\b(dcf|chiết\s*khấu\s*dòng\s*tiền|kịch\s*bản\s*cơ\s*sở|base\s*case|fair\s*value|giá\s*trị\s*hợp\s*lý)\b"],
        {"dcf_fair_value", "dcf_base", "composite_fair_value_base", "margin_of_safety", "wacc", "terminal_growth"},
    ),
    "peer_medians": (
        [r"\b(trung\s*vị\s*ngành|peer\s*median|bình\s*quân\s*ngành|so\s*với\s*ngành|so\s*với\s*các\s*doanh\s*nghiệp\s*cùng\s*ngành|materials\s*peers)\b"],
        {"peer_median_pe", "peer_median_pb", "peer_median_roe"},
    ),
    "dividends": (
        [r"\b(cổ\s*tức|dividend|dividend\s*yield|tỷ\s*suất\s*cổ\s*tức|chính\s*sách\s*cổ\s*tức|chi\s*trả\s*cổ\s*tức)\b"],
        {"dividend_yield", "cash_dividend", "dividend_payout_ratio"},
    ),
    "working_capital_cycle": (
        [r"\b(ccc|chu\s*kỳ\s*tiền|dio|dso|dpo|vòng\s*quay\s*tồn\s*kho|vòng\s*quay\s*phải\s*thu|quản\s*lý\s*hàng\s*tồn\s*kho|quản\s*lý\s*vốn\s*lưu\s*động)\b"],
        {"ccc", "dio", "dso", "dpo"},
    ),
    "market_regime": (
        [r"\b(chế\s*độ\s*thị\s*trường|market\s*regime|độ\s*rộng(?:\s*thị\s*trường)?|breadth|số\s*mã\s*tăng|số\s*mã\s*giảm)\b"],
        {"market_regime", "breadth_advancing", "breadth_declining", "market_breadth_pct"},
    ),
    "screener": (
        [r"\b(tìm\s*các\s*cổ\s*phiếu|lọc\s*cổ\s*phiếu|screener|screen|thỏa\s*mãn\s*tiêu\s*chí|bộ\s*lọc)\b"],
        {"screened_count", "matched_count", "matching_symbols"},
    ),
    "capex": (
        [r"\b(chi\s*phí\s*vốn|tiến\s*độ\s*mở\s*rộng|capex|chi\s*tiêu\s*vốn|mở\s*rộng\s*nhà\s*máy|dự\s*án\s*mở\s*rộng)\b"],
        {"capex", "capital_expenditure"},
    ),
}


def extract_requested_metric_groups(question: str) -> dict[str, set[str]]:
    """Extract financial metric groups explicitly mentioned in a Vietnamese question with strict disambiguation."""
    q_lower = question.lower()
    q_stripped = _strip_vietnamese_accents(q_lower)
    requested: dict[str, set[str]] = {}
    for cat, (patterns, metrics) in METRIC_CATEGORY_PATTERNS.items():
        matched = False
        for pat in patterns:
            if re.search(pat, q_lower) or re.search(_strip_vietnamese_accents(pat), q_stripped):
                matched = True
                break
        if matched:
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
        if not _has_match(r"\b(dòng\s*tiền|lưu\s*chuyển\s*tiền|cash\s*flow|fcf)\b", q_lower):
            del requested["cash_flow_generic"]

    # 5. Disambiguate margin phrasing (e.g. 'biên lợi nhuận gộp') from standalone net income requests
    if "net_income" in requested:
        q_no_margin = re.sub(r"\b(?:biên|bien)\s+(?:lợi\s+nhuận|loi\s+nhuan|gộp|gop|ròng|rong|hoạt\s*động|hoat\s*dong|ebit)\b", "", q_lower)
        if not any(_has_match(pat, q_no_margin) for pat in [
            r"\b(lợi\s*nhuận\s*sau\s*thuế|lợi\s*nhuận\s*ròng|lãi\s*ròng|net\s*income|lnst)\b"
        ]):
            del requested["net_income"]

    # 6. Disambiguate revenue growth vs revenue
    if "revenue_yoy" in requested and "revenue" in requested:
        q_no_growth = re.sub(r"\b(?:tăng\s*trưởng\s*doanh\s*thu|tang\s*truong\s*doanh\s*thu|doanh\s*thu\s*tăng\s*trưởng|doanh\s*thu\s*tang\s*truong|doanh\s*thu\s*yoy|revenue\s*(?:growth|yoy))\b", "", q_lower)
        if not _has_match(r"\b(doanh\s*thu|revenue)\b", q_no_growth):
            del requested["revenue"]

    # 7. Disambiguate valuation ("định giá cổ phiếu") from stock price ("giá cổ phiếu")
    if "price" in requested and "valuation_multiples" in requested:
        q_no_val = re.sub(r"\b(?:định|dinh)\s*giá(?:\s*cổ\s*phiếu|\s*co\s*phieu)?\b", "", q_lower)
        if not _has_match(r"\b(giá\s*cổ\s*phiếu|giá\s*đóng\s*cửa|thị\s*giá|price)\b", q_no_val):
            del requested["price"]

    # 8. Disambiguate total equity from debt-to-equity
    if "total_equity" in requested and "debt_to_equity" in requested:
        q_no_de = re.sub(
            r"\b(?:nợ\s*(?:vay|phải\s*trả)?\s*[\/\:]\s*vốn\s*chủ(?:\s*sở\s*hữu)?|no\s*(?:vay|phai\s*tra)?\s*[\/\:]\s*von\s*chu(?:\s*so\s*huu)?|nợ\s*(?:vay)?\s*trên\s*vốn(?:\s*chủ(?:\s*sở\s*hữu)?)?|d\/e|de\s*ratio|debt\s*(?:to|[\/])\s*equity)\b",
            "",
            q_lower,
        )
        if not _has_match(r"\b(vốn\s*chủ(?:\s*sở\s*hữu)?|quy\s*mô\s*vốn(?:\s*chủ)?|total\s*equity|equity\s*size)\b", q_no_de):
            del requested["total_equity"]
        elif not _has_match(r"\b(nợ|vay|d\/e|de\s*ratio|debt)\b", q_lower):
            del requested["debt_to_equity"]

    # 9. Disambiguate DCF valuation from generic valuation multiples
    if "dcf" in requested and "valuation_multiples" in requested:
        if not _has_match(r"\b(bội\s*số|p\/e|p\/b|ev\/ebitda)\b", q_lower):
            del requested["valuation_multiples"]

    # 10. Disambiguate generic valuation multiples when specific multiples (pe/pb) or screener or peer_medians are present
    if ("pe" in requested or "pb" in requested or "screener" in requested or "peer_medians" in requested) and "valuation_multiples" in requested:
        if not _has_match(r"\b(ev[\/\s]ebitda|bội\s*số)\b", q_lower):
            del requested["valuation_multiples"]

    # 11. Disambiguate cash balance vs working capital cash conversion cycle ("chu kỳ chuyển đổi tiền mặt")
    if "cash_balance" in requested and "working_capital_cycle" in requested:
        q_no_ccc = re.sub(r"\b(?:chu\s*kỳ\s*(?:chuyển\s*đổi\s*)?tiền(?:\s*mặt)?|chu\s*ky\s*tien|ccc)\b", "", q_lower)
        if not _has_match(r"\b(tiền\s*và\s*tương\s*đương\s*tiền|tiền\s*mặt(?:\s*hiện\s*tại)?|lượng\s*tiền(?:\s*mặt)?|số\s*dư\s*tiền|tiền\s*hiện\s*tại|tiền\s*hiện\s*có|cash\s*balance)\b", q_no_ccc):
            del requested["cash_balance"]

    # 12. In a universe screener query, the requested metric is the screener result, not standalone single-stock criteria
    if "screener" in requested:
        for crit in ("pe", "pb", "roe", "roa", "roic", "valuation_multiples", "margins_generic"):
            if crit in requested:
                del requested[crit]

    # 13. Disambiguate standalone revenue from revenue commodity correlation
    if "revenue_commodity_correlation" in requested and "revenue" in requested:
        q_no_corr = re.sub(r"\b(?:tương\s*quan\s*(?:giữa\s*)?doanh\s*thu|doanh\s*thu\s*(?:và|vs|to)\s*(?:giá\s*)?dầu|doanh\s*thu\s*plx)\b", "", q_lower)
        if not _has_match(r"\b(doanh\s*thu\s*(?:thuần|năm|quý)?|doanh\s*số|net\s*revenue)\b", q_no_corr):
            del requested["revenue"]

    # 14. Disambiguate ROE vs ROIC when only ROIC is requested
    if "roic" in requested and "roe" in requested:
        q_no_roic = re.sub(r"\b(?:roic|return\s*on\s*invested\s*capital)\b", "", q_lower)
        if not _has_match(r"\b(?:roe|lợi\s*nhuận\s*trên\s*vốn\s*chủ|sinh\s*lời\s*trên\s*vốn(?!\s*(?:đầu\s*tư|hoạt\s*động|hóa|hoá)))\b", q_no_roic):
            del requested["roe"]

    # 15. Disambiguate interest_coverage vs solvency_liquidity
    if "interest_coverage" in requested and "solvency_liquidity" in requested:
        if not _has_match(r"\b(thanh\s*khoản|khả\s*năng\s*thanh\s*toán|current\s*ratio|quick\s*ratio)\b", q_lower):
            del requested["solvency_liquidity"]

    # 16. Disambiguate revenue_commodity_correlation vs generic macro_commodity
    if "revenue_commodity_correlation" in requested and "macro_commodity" in requested:
        del requested["macro_commodity"]

    # 14. When peer_medians is in requested and the question does NOT compare an individual stock to peers
    # (e.g. asking purely for sector medians like "Định giá P/E và P/B trung vị của nhóm cổ phiếu ngành vật liệu"),
    # the requested metrics are the peer medians (peer_median_pe, peer_median_pb), not single-stock pe/pb/roe.
    if "peer_medians" in requested:
        if not re.search(r"\b(?:so\s*với|so\s*sánh|vs|chênh\s*lệch)\b", q_lower):
            for m in ("pe", "pb", "roe", "roic", "valuation_multiples"):
                if m in requested:
                    del requested[m]

    return requested


SYSTEM_PROMPT = """Bạn là trợ lý phân tích nghiên cứu đầu tư của InvestIntel. Trả lời 100% bằng tiếng Việt tự nhiên, khách quan dựa trên verifiable_evidence.
Quy tắc bắt buộc:
1. Thuật ngữ & Tên mã cổ phiếu:
- 'VND/share' dịch là 'VND/cổ phiếu' (không dịch là thành viên); P/E là hệ số định giá (lần), không gọi là lợi nhuận/doanh thu; biên lợi nhuận (gross_margin) không nhầm với tăng trưởng doanh thu.
- Tên mã cổ phiếu: Luôn viết HOA chính xác mã cổ phiếu (ví dụ: HDB, FPT, MWG, VCB, HPG...). Tuyệt đối không viết sai ký tự (như 'I IDB', '||DB', 'H DB').
- Đối với nhóm Ngân hàng (như HDB, VCB, MBB, TCB, ACB, BID, CTG...): Thu nhập từ hoạt động kinh doanh là 'Tổng thu nhập hoạt động (TOI)' và 'Thu nhập lãi thuần (NII)', không dùng từ 'Doanh thu thuần' cho ngân hàng.
- Biên an toàn (Margin of Safety): Là mức chiết khấu định giá (ví dụ: +57.26%), TUYỆT ĐỐI KHÔNG gắn hậu tố 'YoY' vào biên an toàn.
2. Trích dẫn & thực thể:
- Mọi mệnh đề chứa số liệu từ verifiable_evidence PHẢI đặt claim_type='FACT' hoặc 'MODEL_OUTPUT' và gắn đúng citation_ids=['E...'].
- Gán đúng chỉ số theo trường 'symbol' của từng mã cổ phiếu; không gộp nhầm số liệu mã này sang mã khác.
- Tương quan doanh thu PLX & giá dầu Brent: BẮT BUỘC trích dẫn 'revenue_commodity_correlation' (trên doanh thu quý), không dùng tương quan giá cổ phiếu thay cho doanh thu.
- VNINDEX vs VN100: Nêu rõ chuỗi giá trực tiếp VNINDEX (toàn sàn HOSE) chưa có sẵn và trình bày VN100 làm bối cảnh đại diện (Proxy Context).
- Nợ & khả năng trả nợ (như HPG): Cung cấp cả 'net_debt_ebitda' và 'interest_coverage'.
- Trung vị ngành ('peer_median_pe', 'peer_median_pb', 'peer_median_roe' của *_PEERS): Không dùng chỉ số riêng của mã cổ phiếu thay cho trung vị ngành.
- Định giá DCF ('dcf_base', 'composite_fair_value_base', 'margin_of_safety'), vốn chủ sở hữu ('total_equity' tỷ VND và 'pb'), bộ lọc ('screened_count', 'matched_count', 'matching_symbols'): Trích dẫn trực tiếp con số đã tính sẵn trong verifiable_evidence, tuyệt đối không tự tính nhẩm.
- Nếu bằng chứng có 'is_estimate': true hoặc dùng số cổ phiếu cuối kỳ (period-end shares fallback), BẮT BUỘC nêu rõ đây là số liệu ước tính.
3. Không ghi vào 'uncertainty' các chỉ số đã có trong verifiable_evidence.
4. Đối với câu hỏi về giá cổ phiếu (ví dụ 'Giá cổ phiếu X hôm nay', 'giá đóng cửa phiên hôm nay'):
- Trả lời trực tiếp và rõ ràng giá đóng cửa và ngày quan sát tương ứng (ví dụ: 'Giá đóng cửa cổ phiếu FPT ngày DD/MM/YYYY là XX.XXX VND/cổ phiếu [Evidence: EXXX].').
- Nếu thời điểm hiện tại là trước giờ mở cửa (trước 09:00 sáng) hoặc ngày nghỉ cuối tuần/lễ, nêu rõ: 'Giá đóng cửa phiên gần nhất (ngày DD/MM/YYYY) là...'. Tuyệt đối không khẳng định giá của phiên chưa diễn ra."""


def build_chat_prompt(question: str, context: dict[str, Any]) -> str:
    import json

    compact_context: dict[str, Any] = {}
    try:
        from services.market.trading_hours import get_market_session_summary
        sess_summary = get_market_session_summary()
        compact_context["market_session"] = sess_summary.get("session_code")
        compact_context["market_session_status"] = sess_summary.get("label")
        compact_context["effective_trading_date"] = sess_summary.get("effective_date_iso")
    except Exception:
        pass
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
                "unit": item.get("unit") or ("VND/cổ phiếu" if metric == "price" else None),
                "source": source,
            }
            if item.get("symbol"):
                entry["symbol"] = item.get("symbol")
            if item.get("observation_date"):
                entry["observation_date"] = str(item.get("observation_date"))
            if item.get("is_estimate"):
                entry["is_estimate"] = True
            if item.get("diagnostic_reason"):
                entry["diagnostic_reason"] = item.get("diagnostic_reason")
            if item.get("note"):
                entry["note"] = item.get("note")
            verifiable_evidence.append(entry)
        elif metric and freshness == "NOT_MEANINGFUL":
            note_txt = item.get("note") or "Không áp dụng cho đặc thù ngành (ví dụ: Ngân hàng không dùng Biên lợi nhuận gộp, Vòng quay tồn kho hay Hệ số thanh toán hiện hành)."
            missing_indicators.append(f"{metric}: NOT_APPLICABLE_FOR_SECTOR ({note_txt})")
        elif metric and freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}:
            missing_indicators.append(metric)

    missing_requested_metrics: list[str] = []
    if verifiable_evidence:
        q_lower = question.lower()
        q_stripped = _strip_vietnamese_accents(q_lower)
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
            if ("giá" in q_lower or "gia" in q_stripped or "price" in q_lower) and m == "price":
                s += 100
            if ("doanh thu" in q_stripped or "revenue" in q_lower) and m in {"revenue", "revenue_yoy", "gross_margin"}:
                s += 100
            if ("loi nhuan" in q_stripped or "lợi nhuận" in q_lower or "income" in q_lower or "profit" in q_lower) and m in {"net_income", "net_income_yoy", "net_margin"}:
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
            if ("dinh gia" in q_stripped or "valuation" in q_lower) and not asks_pb and not asks_pe and m in {"pe", "pb"}:
                s += 50
            if ("so sanh" in q_stripped or "compare" in q_lower) and m in {"pe_diff", "pb_diff"}:
                s += 250
            if m in {"pe_diff", "pb_diff"} and len(query_symbols) > 1:
                s += 200
            if ("tuong quan" in q_stripped or "correlation" in q_lower or "gia dau" in q_stripped or "dau" in q_stripped) and m in {"pearson_correlation", "brent", "wti", "commodity_close", "commodity_change_pct"}:
                s += 280
            if any(term in q_stripped for term in ("tin dung", "nim", "casa", "no xau", "ngan hang", "npl")) and m in {"credit_growth", "nim", "casa_ratio", "npl_ratio", "llr_ratio"}:
                s += 250
            if "eps" in q_lower and m in {"eps_ttm", "eps_yoy"}:
                s += 100
            if "bvps" in q_lower and m == "bvps":
                s += 100
            if "no" in q_stripped and m in {"debt_to_assets", "de_ratio", "net_debt_ebitda"}:
                s += 130
            if ("dong tien" in q_stripped or "tien" in q_stripped) and m in {"cfo", "fcf", "cash", "cfo_to_ni", "fcf_to_ni"}:
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
                # Take up to 2 items for composite groups (like margins, revenue+growth, price_change), 1 for single metrics
                take_count = 2 if cat_name in {"margins_generic", "revenue", "net_income", "price_change"} else 1
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
                        if item.get("observation_date"):
                            ev_entry["observation_date"] = str(item.get("observation_date"))
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
            if item.get("observation_date"):
                ev_entry["observation_date"] = str(item.get("observation_date"))
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
        if isinstance(context, dict):
            context["evidence_telemetry"] = telemetry_info

    # Assemble unverified or missing metrics, placing requested missing metrics first
    all_missing = list(dict.fromkeys(missing_requested_metrics + missing_indicators))
    if all_missing:
        compact_context["unverified_or_missing_metrics"] = all_missing[:6]

    return (
        f"Câu hỏi:\n{question}\n\n"
        "Bằng chứng (JSON):\n"
        f"{json.dumps(compact_context, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
        "Trả lời tiếng Việt theo JSON AIAnswerDraft (ngắn gọn dưới 160 từ):\n"
        "- 'answer': 1-2 câu súc tích trả lời trực tiếp câu hỏi.\n"
        "- 'claims': 2-4 mệnh đề ngắn (mỗi câu < 25 từ). Mệnh đề có số liệu từ verifiable_evidence PHẢI đặt claim_type='FACT' hoặc 'MODEL_OUTPUT' và gắn đúng citation_ids=['id']. Nếu chỉ số có is_estimate=true, nêu rõ là ước tính. Mệnh đề về dữ liệu thiếu đặt claim_type='UNCERTAINTY', citation_ids=[].\n"
        "- 'uncertainty': Tối đa 2 mục ngắn gọn về dữ liệu còn thiếu (không lặp lại chỉ số đã có)."
    )
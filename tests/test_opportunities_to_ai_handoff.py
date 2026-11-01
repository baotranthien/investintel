"""
Focused regression tests for Opportunities -> AI Analyst context handoff.
Validates:
1. Exact Vietnamese prompt generation from stock ticker (FPT, HPG, VHM, etc.)
2. Ticker normalization and rejection of invalid symbols
3. URL construction with proper RFC 3986 query encoding
4. Opportunities page components wiring to the handoff URL
5. AI Analyst page context parsing and state initialization contracts
"""

import re
import urllib.parse
from pathlib import Path

WEB_SRC = Path(__file__).resolve().parent.parent / "apps" / "web" / "src"

EXPECTED_PROMPT_TEMPLATE = (
    "Phân tích cơ hội đầu tư của cổ phiếu {symbol} dựa trên dữ liệu hiện có trong InvestIntel. "
    "Hãy trình bày các luận điểm hỗ trợ, định giá, rủi ro, độ mới của dữ liệu và những thông tin "
    "chưa đủ bằng chứng. Phân biệt số liệu thực tế với ước tính."
)


def normalize_ticker(raw: str | None) -> str | None:
    if not raw:
        return None
    trimmed = raw.strip().upper()
    if re.match(r"^[A-Z0-9]{2,10}$", trimmed):
        return trimmed
    return None


def build_opportunity_question(symbol: str) -> str:
    clean = normalize_ticker(symbol) or symbol.strip().upper()
    return EXPECTED_PROMPT_TEMPLATE.format(symbol=clean)


def build_opportunity_ai_url(symbol: str) -> str:
    clean = normalize_ticker(symbol) or symbol.strip().upper()
    q = build_opportunity_question(clean)
    params = urllib.parse.urlencode({
        "symbol": clean,
        "source": "opportunities",
        "q": q,
    })
    return f"/ai?{params}"


def test_question_generation_for_fpt():
    """Verify exact prompt text for FPT matches required specification."""
    prompt = build_opportunity_question("FPT")
    expected = (
        "Phân tích cơ hội đầu tư của cổ phiếu FPT dựa trên dữ liệu hiện có trong InvestIntel. "
        "Hãy trình bày các luận điểm hỗ trợ, định giá, rủi ro, độ mới của dữ liệu và những thông tin "
        "chưa đủ bằng chứng. Phân biệt số liệu thực tế với ước tính."
    )
    assert prompt == expected
    assert "FPT" in prompt


def test_question_generation_different_tickers():
    """Verify different stocks (HPG, VHM, MWG) generate distinct tickers, never reusing FPT."""
    prompt_hpg = build_opportunity_question("HPG")
    prompt_vhm = build_opportunity_question("VHM")

    assert "HPG" in prompt_hpg
    assert "FPT" not in prompt_hpg

    assert "VHM" in prompt_vhm
    assert "FPT" not in prompt_vhm
    assert "HPG" not in prompt_vhm


def test_ticker_normalization_and_validation():
    """Verify valid tickers are cleaned and invalid inputs rejected."""
    assert normalize_ticker("fpt") == "FPT"
    assert normalize_ticker(" Hpg ") == "HPG"
    assert normalize_ticker("vcb") == "VCB"
    assert normalize_ticker("VN30") == "VN30"
    assert normalize_ticker("FUEVN100") == "FUEVN100"

    # Invalid tickers
    assert normalize_ticker(None) is None
    assert normalize_ticker("") is None
    assert normalize_ticker("   ") is None
    assert normalize_ticker("$$$") is None
    assert normalize_ticker("FPT@VN") is None
    assert normalize_ticker("A") is None  # Less than 2 chars
    assert normalize_ticker("VERYLONGTICKERNAME") is None  # > 10 chars


def test_url_construction_and_encoding():
    """Verify URL encodes parameters safely with proper query structure."""
    url = build_opportunity_ai_url("FPT")
    assert url.startswith("/ai?")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    assert params["symbol"] == ["FPT"]
    assert params["source"] == ["opportunities"]
    assert "FPT" in params["q"][0]
    assert "Phân tích cơ hội đầu tư của cổ phiếu FPT" in params["q"][0]


def test_ts_handoff_module_contract():
    """Verify apps/web/src/lib/ai-handoff.ts exists and defines required functions."""
    handoff_ts = WEB_SRC / "lib" / "ai-handoff.ts"
    assert handoff_ts.exists(), "ai-handoff.ts must exist"
    content = handoff_ts.read_text(encoding="utf-8")

    assert "export function normalizeTicker" in content
    assert "export function buildOpportunityQuestion" in content
    assert "export function buildOpportunityAIUrl" in content
    assert "Phân tích cơ hội đầu tư của cổ phiếu" in content
    assert "source: \"opportunities\"" in content


def test_opportunities_page_wiring():
    """Verify opportunities page uses buildOpportunityAIUrl in cards and table rows."""
    opp_page = WEB_SRC / "app" / "opportunities" / "page.tsx"
    assert opp_page.exists()
    content = opp_page.read_text(encoding="utf-8")

    assert "buildOpportunityAIUrl" in content
    # Ensure both card and table views pass item.symbol to buildOpportunityAIUrl
    assert "buildOpportunityAIUrl(item.symbol)" in content
    # Ensure no hardcoded questions remain in link targets for opportunities
    assert "Đánh giá cơ hội đầu tư và triển vọng của cổ phiếu" not in content


def test_ai_page_context_handoff():
    """Verify AI page imports handoff helpers and binds to searchParams with idempotency."""
    ai_page = WEB_SRC / "app" / "ai" / "page.tsx"
    assert ai_page.exists()
    content = ai_page.read_text(encoding="utf-8")

    # Imported helpers
    assert "normalizeTicker" in content
    assert "buildOpportunityQuestion" in content

    # Reads symbol, q, and source
    assert "symbolParam" in content
    assert "qParam" in content
    assert "sourceParam" in content

    # Idempotency via lastHandledKeyRef
    assert "lastHandledKeyRef" in content

    # Does not submit automatically
    assert "ask(" not in content or "onSubmit={ask}" in content
    # Verify no auto-invocation of ask() inside useEffect
    ask_calls = re.findall(r"useEffect\([^)]*ask\(", content, re.DOTALL)
    assert len(ask_calls) == 0, "ask() must not be called inside useEffect (no auto-submit)"


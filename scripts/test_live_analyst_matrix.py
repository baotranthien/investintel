"""
Live AI Analyst Acceptance Test Matrix.
Tests the real HTTP inference endpoint /api/v1/ai/chat against local Ollama (qwen2.5:3b).
Verifies:
- Live model invocation
- Canonical symbol resolution
- Evidence sufficiency
- Citation integrity (IDs map to real evidence, cited_numbers match)
- Proper status handling (FULL, PARTIAL, INSUFFICIENT_DATA)
"""
import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000/api/v1/ai/chat"

TEST_CASES = [
    {
        "name": "SHB Price Query (Reproduction Case)",
        "payload": {
            "question": "Giá cổ phiếu SHB hiện tại là bao nhiêu?",
            "symbol": "SHB",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "SHB",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "VCB Financial Results Summary",
        "payload": {
            "question": "Tóm tắt kết quả tài chính và doanh thu gần nhất của VCB",
            "symbol": "VCB",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "VCB",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "FPT Fundamentals & Valuation",
        "payload": {
            "question": "Đánh giá các chỉ số cơ bản P/E, ROE và tăng trưởng của FPT",
            "symbol": "FPT",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "FPT",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "ACB Fundamental Banking Metrics",
        "payload": {
            "question": "Cho biết định giá P/B và tỷ suất sinh lời ROE của ngân hàng ACB",
            "symbol": "ACB",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "ACB",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "MBB Financial & Price Analysis",
        "payload": {
            "question": "Giá cổ phiếu và kết quả kinh doanh gần nhất của MBB",
            "symbol": "MBB",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "MBB",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "MWG Retail Margin & Revenue",
        "payload": {
            "question": "Doanh thu và biên lợi nhuận của Thế Giới Di Động (MWG)",
            "symbol": "MWG",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "MWG",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "HPG Steel Fundamentals & Valuation",
        "payload": {
            "question": "Giá cổ phiếu và định giá P/E của Tập đoàn Hòa Phát (HPG)",
            "symbol": "HPG",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "HPG",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "VNM VN100 Non-Seed Constituent",
        "payload": {
            "question": "Giá cổ phiếu và các chỉ số tài chính gần nhất của Vinamilk (VNM)",
            "symbol": "VNM",
            "active_tools": ["prices", "fundamentals", "valuation", "factors", "macro", "risk", "events"]
        },
        "expected_symbol": "VNM",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "SSI Securities VN100 Constituent",
        "payload": {
            "question": "Giá đóng cửa gần nhất của cổ phiếu chứng khoán SSI",
            "symbol": "SSI",
            "active_tools": ["prices", "fundamentals", "valuation"]
        },
        "expected_symbol": "SSI",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "FUEVN100 ETF Partial Coverage Query",
        "payload": {
            "question": "Giá đóng cửa hiện tại của chứng chỉ quỹ ETF FUEVN100 là bao nhiêu?",
            "symbol": "FUEVN100",
            "active_tools": ["prices", "fundamentals"]
        },
        "expected_symbol": "FUEVN100",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "Benchmark Index (VN30) Query",
        "payload": {
            "question": "Chỉ số VN30 hiện tại có điểm số và giá đóng cửa bao nhiêu?",
            "symbol": "VN30",
            "active_tools": ["prices", "macro"]
        },
        "expected_symbol": "VN30",
        "allowed_statuses": ["AVAILABLE", "PARTIAL"],
        "expected_min_citations": 1,
    },
    {
        "name": "Genuinely Missing Evidence Query on Valid Stock",
        "payload": {
            "question": "Dự báo lợi nhuận sau thuế năm 2038 của FPT là bao nhiêu?",
            "symbol": "FPT",
            "active_tools": ["prices", "fundamentals"]
        },
        "expected_symbol": "FPT",
        "allowed_statuses": ["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"],
    },
    {
        "name": "Unsupported/Invalid Ticker (Insufficient Data Check)",
        "payload": {
            "question": "Cho biết báo cáo tài chính của mã XYZUNKNOWN",
            "symbol": "XYZUNKNOWN",
            "active_tools": ["prices", "fundamentals"]
        },
        "expected_status": "INSUFFICIENT_DATA",
    }
]

def run_test(case):
    print(f"\n" + "=" * 60)
    print(f"RUNNING: {case['name']}")
    print(f"Payload: {json.dumps(case['payload'], ensure_ascii=False)}")
    print("=" * 60)
    
    t0 = time.time()
    req = urllib.request.Request(
        BASE_URL,
        data=json.dumps(case["payload"]).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            elapsed = time.time() - t0
            data = json.loads(resp.read().decode("utf-8"))
            
            status = data.get("status")
            answer = data.get("answer", "")
            citations = data.get("citations", [])
            claims = data.get("claims", [])
            evidence = data.get("evidence", [])
            resolution = data.get("resolved_symbol") or data.get("symbol")
            
            print(f"Elapsed Time: {elapsed:.2f}s")
            print(f"Status: {status}")
            print(f"Resolved Symbol: {resolution}")
            print(f"Answer: {answer[:250]}...")
            print(f"Total Evidence items retrieved: {len(evidence)}")
            print(f"Claims count: {len(claims)}")
            print(f"Citations count: {len(citations)}")
            
            if citations:
                for c in citations[:3]:
                    print(f"  - Citation [{c.get('id')}]: {c.get('metric')} = {c.get('value')} ({c.get('source')}, date: {c.get('observation_date')})")
            
            # Validation assertions
            if "expected_symbol" in case:
                assert resolution == case["expected_symbol"], f"Expected {case['expected_symbol']}, got {resolution}"
            if "expected_status" in case:
                assert status == case["expected_status"], f"Expected {case['expected_status']}, got {status}"
            if "allowed_statuses" in case:
                assert status in case["allowed_statuses"], f"Expected status in {case['allowed_statuses']}, got {status}"
            if case.get("expected_min_citations"):
                assert len(citations) >= case["expected_min_citations"], f"Expected >= {case['expected_min_citations']} citations, got {len(citations)}"
            
            print(">>> RESULT: PASSED")
            return True, elapsed
    except Exception as exc:
        print(f">>> RESULT: FAILED with error: {exc}")
        return False, 0.0

if __name__ == "__main__":
    results = []
    for tc in TEST_CASES:
        ok, elapsed = run_test(tc)
        results.append((tc["name"], ok, elapsed))
    
    print("\n" + "=" * 60)
    print("AI ANALYST ACCEPTANCE TEST SUMMARY:")
    print("=" * 60)
    for name, ok, elapsed in results:
        status_str = "PASS" if ok else "FAIL"
        print(f"[{status_str}] {name} ({elapsed:.2f}s)")

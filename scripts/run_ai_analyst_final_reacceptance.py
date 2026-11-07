"""
InvestIntel — Final Product Acceptance: Actual Local Qwen 9B UI Acceptance Runner
Driven with Playwright directly through Chrome against live Next.js (port 3000) & FastAPI (port 8000).

Execution guarantees:
- Sequential execution with isolated browser tabs (1 tab per question).
- Full live UI interaction (navigates to /ai, fills inputs, clicks submit / Enter).
- Real resident Qwen 3.5 9B Ollama streaming through SSE.
- Direct DOM extraction of rendered badges, prose, claims, citations, uncertainty, and fallback tables.
- High-res full-page screenshots into docs/audits/evidence/ai_analyst_final_reacceptance_2026-11-02/.
- Generates exhaustive markdown acceptance report final_qwen_ui_results.md.
"""
import json
import os
import sys
import time
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WEB_URL = "http://localhost:3000/ai"
OUT_DIR = r"C:\Users\baotr\Downloads\trading\docs\audits\evidence\ai_analyst_final_reacceptance_2026-11-02"
os.makedirs(OUT_DIR, exist_ok=True)

AUDIT_QUESTIONS = [
    {
        "id": "Q05_HPG_DE_Capex",
        "symbol": "HPG",
        "question": "Chi phí vốn, hệ số đòn bẩy tài chính D/E và tiến độ mở rộng của Tập đoàn Hòa Phát (HPG)?",
        "title": "HPG: Đòn bẩy tài chính D/E & Chi phí vốn / Mở rộng",
        "expected_status": "PARTIAL",
        "key_metrics": ["debt_to_equity"],
        "notes": "D/E grounded (0.70x), capex progress reported as unverified uncertainty -> PARTIAL status",
    },
    {
        "id": "Q06_BMP_Peers_ROE",
        "symbol": "BMP",
        "question": "Định giá P/E và tỷ suất sinh lời ROE của Nhựa Bình Minh (BMP) so với trung vị ngành vật liệu?",
        "title": "BMP vs Materials Peers: P/E & ROE so với trung vị ngành",
        "expected_status": "AVAILABLE",
        "key_metrics": ["pe", "roe", "peer_median_pe", "peer_median_roe"],
        "notes": "BMP P/E 8.99x - 9.10x, ROE 41.57% vs Peer Medians (P/E ~13.35x, ROE ~5.62%) -> AVAILABLE status",
    },
    {
        "id": "Q07_PLX_Brent_Correlation",
        "symbol": "PLX",
        "question": "Mối tương quan giữa doanh thu PLX và biến động giá dầu thế giới (Brent/WTI)?",
        "title": "PLX: Tương quan doanh thu thuần 24 quý vs Giá dầu Brent",
        "expected_status": "AVAILABLE",
        "key_metrics": ["revenue_commodity_correlation", "brent_close"],
        "notes": "Quarterly revenue vs Brent price Pearson correlation (-0.8031 raw levels, 24 quarters) -> AVAILABLE status",
    },
    {
        "id": "Q08_VNINDEX_Regime_Breadth",
        "symbol": "VNINDEX",
        "question": "Đánh giá trạng thái chế độ thị trường (Market Regime) và độ rộng thị trường chứng khoán Việt Nam?",
        "title": "VNINDEX: Chế độ thị trường & Độ rộng (VN100 Proxy Context)",
        "expected_status": "PARTIAL",
        "key_metrics": ["market_regime_vnindex", "market_regime", "market_breadth_pct"],
        "notes": "Direct VNINDEX index absent disclosure, VN100 large-cap proxy context (NEUTRAL, 11% breadth) -> PARTIAL status",
    },
    {
        "id": "Q09_FPT_NetMargin_ROIC",
        "symbol": "FPT",
        "question": "Biên lợi nhuận ròng và hiệu quả sử dụng vốn ROIC của FPT trong các kỳ gần nhất?",
        "title": "FPT: Biên lợi nhuận ròng & Hiệu quả sử dụng vốn ROIC",
        "expected_status": "AVAILABLE",
        "key_metrics": ["net_margin", "roic"],
        "notes": "Net Margin 15.68%, ROIC 21.51% (roic_v1), strict disambiguation (no ROE substitution) -> AVAILABLE status",
    },
    {
        "id": "Q10_VCB_Equity_PB",
        "symbol": "VCB",
        "question": "Quy mô vốn chủ sở hữu và định giá P/B của Vietcombank (VCB) hiện tại?",
        "title": "VCB: Quy mô vốn chủ sở hữu & Định giá P/B",
        "expected_status": "AVAILABLE",
        "key_metrics": ["total_equity", "pb"],
        "notes": "Total Equity 248,490.51 tỷ VND, P/B 1.89x, strict disambiguation (no D/E substitution) -> AVAILABLE status",
    },
    {
        "id": "Q11_BMP_DCF_BaseCase",
        "symbol": "BMP",
        "question": "Mô hình định giá DCF và kịch bản cơ sở (Base Case) đối với cổ phiếu BMP đưa ra kết quả gì?",
        "title": "BMP: Mô hình định giá DCF Kịch bản cơ sở (Base Case)",
        "expected_status": "AVAILABLE",
        "key_metrics": ["dcf_base", "composite_fair_value_base"],
        "notes": "DCF Base Case 179,638 VND, Authoritative Composite Fair Value 174,462 VND -> AVAILABLE status",
    },
    {
        "id": "Q16_HPG_NetDebtEBITDA_Coverage",
        "symbol": "HPG",
        "question": "Tỷ lệ nợ ròng trên EBITDA và khả năng chi trả lãi vay của HPG?",
        "title": "HPG: Nợ ròng / EBITDA & Hệ số chi trả lãi vay (Interest Coverage)",
        "expected_status": "AVAILABLE",
        "key_metrics": ["net_debt_ebitda", "interest_coverage"],
        "notes": "Net Debt/EBITDA 2.05x, Interest Coverage 5.51x, both grounded -> AVAILABLE status",
    },
    {
        "id": "Q17_Materials_Peer_Medians",
        "symbol": "BMP",
        "question": "Định giá P/E và P/B trung vị của nhóm cổ phiếu ngành vật liệu (Materials Peers) tại Việt Nam?",
        "title": "Materials Peers: P/E, P/B và ROE trung vị nhóm ngành vật liệu",
        "expected_status": "AVAILABLE",
        "key_metrics": ["peer_median_pe", "peer_median_pb", "peer_median_roe"],
        "notes": "Median P/E ~13.35x, P/B ~0.77x, ROE ~5.62% -> AVAILABLE status",
    },
    {
        "id": "Q18_MWG_CCC_WorkingCapital",
        "symbol": "MWG",
        "question": "Chu kỳ chuyển đổi tiền mặt (Cash Conversion Cycle - CCC) và hiệu quả quản lý hàng tồn kho của MWG?",
        "title": "MWG: Chu kỳ tiền mặt CCC & Quản trị vốn lưu động",
        "expected_status": "AVAILABLE",
        "key_metrics": ["ccc", "dio", "dso", "dpo"],
        "notes": "CCC 46.93 ngày, DIO 68.1 ngày, DSO 4.2 ngày, DPO 25.4 ngày -> AVAILABLE status",
    },
    {
        "id": "Q19_ALL_Universe_Screener",
        "symbol": "ALL",
        "question": "Các cổ phiếu thỏa mãn tiêu chí định giá rẻ P/E dưới 15 và sinh lời ROE trên 15%?",
        "title": "Vũ trụ ALL: Bộ lọc cổ phiếu P/E < 15 và ROE > 15%",
        "expected_status": "AVAILABLE",
        "key_metrics": ["screened_count", "matched_count"],
        "notes": "Screened 106, Matched 35 qualifying tickers (VCB, FPT, MBB, MWG, HPG, BMP...) -> AVAILABLE status",
    },
]


def run_acceptance():
    print(f"================================================================================", flush=True)
    print(f"STARTING INVESTINTEL FINAL QWEN 9B UI ACCEPTANCE SUITE ({len(AUDIT_QUESTIONS)} QUESTIONS)", flush=True)
    print(f"Target Frontend: {WEB_URL}", flush=True)
    print(f"Evidence Directory: {OUT_DIR}", flush=True)
    print(f"Mode: Tab Isolation Per Question (100% Live Browser Automation)", flush=True)
    print(f"================================================================================\n", flush=True)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--window-size=1440,1100", "--disable-gpu", "--hide-scrollbars"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1100})

    results = []
    total = len(AUDIT_QUESTIONS)

    try:
        for idx, item in enumerate(AUDIT_QUESTIONS, 1):
            qid = item["id"]
            sym = item["symbol"]
            q = item["question"]
            title = item["title"]

            print(f"\n--------------------------------------------------------------------------------", flush=True)
            print(f"[{idx}/{total}] RUNNING LIVE TEST: {qid}", flush=True)
            print(f"  Title: {title}", flush=True)
            print(f"  Symbol: {sym} | Query: {q[:75]}...", flush=True)

            page = context.new_page()
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            t0 = time.time()
            try:
                # 1. Navigate fresh tab to /ai
                page.goto(WEB_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("textarea", timeout=10000)
                time.sleep(0.5)

                # 2. Fill symbol input (leave empty for market-wide ALL queries)
                if sym and sym != "ALL":
                    sym_input = page.locator('input[placeholder="MÃ CP"]')
                    sym_input.click()
                    sym_input.fill(sym)
                    sym_input.dispatch_event("input")
                    time.sleep(0.3)

                # 3. Fill query in textarea
                textarea = page.locator("textarea")
                textarea.click()
                textarea.fill(q)
                textarea.dispatch_event("input")
                time.sleep(0.5)

                # 4. Submit form
                submit_btn = page.locator('button[type="submit"]')
                if submit_btn.is_disabled():
                    page.evaluate("""(text) => {
                        const ta = document.querySelector('textarea');
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(ta, text);
                        ta.dispatchEvent(new Event('input', { bubbles: true }));
                        ta.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", q)
                    time.sleep(0.5)

                submit_btn.click()

                print("  Submit triggered. Waiting for live Ollama inference & UI render (max 160s)...", flush=True)

                # 5. Wait for <article> containing final answer
                art = page.wait_for_selector("article", timeout=160000)
                dur = round(time.time() - t0, 2)
                time.sleep(1.5)  # Let smooth animations and citation pills settle

                # 6. Extract rendered data from DOM
                badges = [b.inner_text().strip() for b in page.locator("article header span").all()]

                actual_status = "UNKNOWN"
                for b in badges:
                    b_upper = b.upper()
                    if b_upper in {"AVAILABLE", "PARTIAL", "UNAVAILABLE", "WRONG_SCOPE", "PARTIAL_DATA_ONLY"}:
                        actual_status = b_upper
                        break
                if actual_status == "UNKNOWN" and any("HOÀN TẤT" in b for b in badges):
                    actual_status = "AVAILABLE"

                # Extract model
                model_name = "qwen3.5:9b-q4_K_M"
                for b in badges:
                    if "qwen" in b.lower():
                        model_name = b

                # Extract prose
                prose = ""
                prose_loc = page.locator('article div[class*="answerProse"]')
                if prose_loc.count() > 0:
                    prose = prose_loc.inner_text().strip()

                # Extract claims
                claims = [c.inner_text().strip() for c in page.locator('article div[class*="claimRow"]').all()]

                # Extract citations
                citations_text = [c.inner_text().strip() for c in page.locator('article span[class*="citationPill"], article a[class*="citationPill"]').all()]

                # Extract uncertainty notes
                uncertainties = [u.inner_text().strip() for u in page.locator('article li[class*="uncertaintyItem"]').all()]

                # Check proxy badge
                has_proxy_badge = any("BỐI CẢNH ĐẠI DIỆN" in b or "PROXY CONTEXT" in b for b in badges)

                # 7. Capture full-page screenshot
                screenshot_filename = f"{qid}.png"
                screenshot_path = os.path.join(OUT_DIR, screenshot_filename)
                page.screenshot(path=screenshot_path, full_page=True)

                status_match = (actual_status == item["expected_status"])
                m_icon = "✅ PASS" if status_match else "❌ FAIL"
                print(f"  {m_icon} Rendered in {dur}s | Status: {actual_status} (Expected: {item['expected_status']})", flush=True)
                print(f"  Claims: {len(claims)} | Citations: {len(citations_text)} | Uncertainty: {len(uncertainties)} | Proxy Badge: {has_proxy_badge}", flush=True)
                print(f"  Screenshot -> {screenshot_filename}", flush=True)

                results.append({
                    "id": qid,
                    "title": title,
                    "symbol": sym,
                    "question": q,
                    "expected_status": item["expected_status"],
                    "actual_status": actual_status,
                    "status_match": status_match,
                    "duration_s": dur,
                    "badges": badges,
                    "has_proxy_badge": has_proxy_badge,
                    "model": model_name,
                    "prose": prose,
                    "claims": claims,
                    "citations_text": citations_text,
                    "uncertainties": uncertainties,
                    "screenshot_filename": screenshot_filename,
                    "screenshot_path": screenshot_path,
                    "console_errors": console_errors,
                })

            except Exception as e:
                print(f"  ❌ ERROR: {e}", flush=True)
                err_screenshot = f"{qid}_error.png"
                page.screenshot(path=os.path.join(OUT_DIR, err_screenshot), full_page=True)
                results.append({
                    "id": qid,
                    "title": title,
                    "symbol": sym,
                    "question": q,
                    "expected_status": item["expected_status"],
                    "actual_status": "TIMEOUT_OR_ERROR",
                    "status_match": False,
                    "duration_s": round(time.time() - t0, 2),
                    "badges": [],
                    "has_proxy_badge": False,
                    "model": "qwen3.5:9b-q4_K_M",
                    "prose": f"Execution failed: {e}",
                    "claims": [],
                    "citations_text": [],
                    "uncertainties": [str(e)],
                    "screenshot_filename": err_screenshot,
                    "screenshot_path": os.path.join(OUT_DIR, err_screenshot),
                    "console_errors": console_errors,
                })
            finally:
                page.close()

            # Small 5s cooldown between inferences for Ollama stability
            time.sleep(5.0)

        # 8. Generate markdown acceptance report
        md_path = os.path.join(OUT_DIR, "final_qwen_ui_results.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# INVESTINTEL — FINAL QWEN 9B UI ACCEPTANCE RESULTS\n\n")
            f.write(f"**Date:** 2026-11-02  \n")
            f.write(f"**Local AI Model:** `qwen3.5:9b-q4_K_M` via Ollama  \n")
            f.write(f"**Frontend:** `{WEB_URL}`  \n")
            f.write(f"**Inference Mode:** 100% Live End-to-End Chrome Browser Automation  \n")
            f.write(f"**Artifact Directory:** `{OUT_DIR}`  \n\n")
            f.write("---\n\n")

            f.write("## 1. Executive Summary Table\n\n")
            f.write("| # | Question ID | Symbol | Question Title | Expected Status | Actual Status | Conformance | Duration | Claims | Citations | Screenshot |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")

            total_passed = sum(1 for r in results if r["status_match"])
            for idx, r in enumerate(results, 1):
                icon = "✅ PASS" if r["status_match"] else "❌ FAIL"
                f.write(f"| {idx:02d} | `{r['id']}` | **{r['symbol']}** | {r['title']} | `{r['expected_status']}` | `{r['actual_status']}` | {icon} | {r['duration_s']}s | {len(r['claims'])} | {len(r['citations_text'])} | [`{r['screenshot_filename']}`](./{r['screenshot_filename']}) |\n")

            f.write(f"\n**Total Conformance:** {total_passed}/{len(results)} ({total_passed/len(results)*100:.1f}%)\n\n")
            f.write("---\n\n")

            f.write("## 2. Detailed Per-Question Verifications\n\n")
            for r in results:
                f.write(f"### {r['id']} — {r['title']}\n\n")
                f.write(f"- **User Query:** \"{r['question']}\"\n")
                f.write(f"- **Target Entity:** `{r['symbol']}`\n")
                f.write(f"- **Inference Model:** `{r['model']}`\n")
                f.write(f"- **Total E2E Duration:** `{r['duration_s']}s`\n")
                f.write(f"- **Decision Status:** `{r['actual_status']}` (Expected: `{r['expected_status']}`)\n")
                if r["has_proxy_badge"]:
                    f.write("- **Proxy Indicator:** `⚠️ BỐI CẢNH ĐẠI DIỆN / PROXY CONTEXT (VN100)` badge active\n")
                f.write(f"- **Screenshot:** ![{r['id']}](./{r['screenshot_filename']})\n\n")

                f.write("#### Rendered Prose Snippet\n")
                lead = r["prose"][:400].replace("\n", " ") if r["prose"] else "*No prose text.*"
                f.write(f"> {lead}...\n\n")

                f.write("#### Grounded Claims from DOM\n")
                if r["claims"]:
                    for c in r["claims"]:
                        f.write(f"- {c}\n")
                else:
                    f.write("- *No atomic claims recorded.*\n")
                f.write("\n")

                f.write("#### Uncertainty & Data Limitations from DOM\n")
                if r["uncertainties"]:
                    for u in r["uncertainties"]:
                        f.write(f"- ⚠️ {u}\n")
                else:
                    f.write("- *No ungrounded claims or uncertainties reported.*\n")
                f.write("\n---\n\n")

        print(f"\n================================================================================", flush=True)
        print(f"ACCEPTANCE EXECUTION FINISHED: {total_passed}/{len(results)} ({total_passed/len(results)*100:.1f}%) PASSED", flush=True)
        print(f"Report written to: {md_path}", flush=True)
        print(f"================================================================================\n", flush=True)

    finally:
        context.close()
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    run_acceptance()

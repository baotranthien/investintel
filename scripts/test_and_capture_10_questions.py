import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import httpx
import websockets

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222
OUT_DIR = r"C:\Users\baotr\Downloads\trading\docs\audits\evidence\ai_analyst_fix_2026-10-28"

TEST_QUESTIONS = [
    {
        "id": "q01_fpt",
        "symbol": "FPT",
        "question": "Triển vọng tăng trưởng doanh thu và định giá P/E hiện tại của FPT?",
        "title": "FPT: Tăng trưởng doanh thu & Định giá P/E"
    },
    {
        "id": "q02_mbb_tcb",
        "symbol": "MBB",
        "question": "So sánh NIM, CASA và tỷ lệ nợ xấu NPL giữa MBB và TCB?",
        "title": "MBB vs TCB: So sánh NIM, CASA & Nợ xấu"
    },
    {
        "id": "q03_plx",
        "symbol": "PLX",
        "question": "Tương quan giữa giá cổ phiếu PLX và giá dầu thô Brent tham chiếu?",
        "title": "PLX: Tương quan cổ phiếu dầu khí & Brent"
    },
    {
        "id": "q04_vcb",
        "symbol": "VCB",
        "question": "Tỷ lệ bao phủ nợ xấu LLR và chất lượng tài sản của Vietcombank VCB?",
        "title": "VCB: Bao phủ nợ xấu LLR & Chất lượng tài sản"
    },
    {
        "id": "q05_mwg",
        "symbol": "MWG",
        "question": "Biên lợi nhuận ròng, doanh thu và định giá P/S của Thế Giới Di Động MWG?",
        "title": "MWG: Biên lợi nhuận & Định giá bán lẻ"
    },
    {
        "id": "q06_hpg",
        "symbol": "HPG",
        "question": "Đánh giá biên lợi nhuận gộp và tỷ suất sinh lời ROE của Tập đoàn Hòa Phát HPG?",
        "title": "HPG: Biên lợi nhuận gộp & Tỷ suất ROE"
    },
    {
        "id": "q07_vnm",
        "symbol": "VNM",
        "question": "Dòng tiền kinh doanh CFO và tỷ suất cổ tức tiền mặt của Vinamilk VNM?",
        "title": "VNM: Dòng tiền kinh doanh & Cổ tức tiền mặt"
    },
    {
        "id": "q08_bsr",
        "symbol": "BSR",
        "question": "Biên lọc dầu crack spread, lượng tiền mặt và tỷ lệ nợ vay của Lọc hóa dầu Bình Sơn BSR?",
        "title": "BSR: Crack spread & Dự trữ tiền mặt"
    },
    {
        "id": "q09_vnindex",
        "symbol": "VNINDEX",
        "question": "Tổng quan định giá thị trường VNINDEX, lãi suất điều hành và tăng trưởng tín dụng NHNN?",
        "title": "VNINDEX: Định giá vĩ mô & Chính sách tiền tệ"
    },
    {
        "id": "q10_portfolio",
        "symbol": "VN100",
        "question": "Chiến lược phân bổ danh mục tài sản phòng thủ kết hợp tăng trưởng cho quy mô 100 triệu VND?",
        "title": "Phân bổ danh mục: Phòng thủ kết hợp tăng trưởng"
    }
]

async def send_cdp(ws, method, params=None, msg_id=[1]):
    mid = msg_id[0]
    msg_id[0] += 1
    req = {"id": mid, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp_text = await ws.recv()
        resp = json.loads(resp_text)
        if resp.get("id") == mid:
            return resp.get("result", {})

async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    temp_profile = os.path.join(tempfile.gettempdir(), f"chrome_investintel_profile_{int(time.time())}")
    os.makedirs(temp_profile, exist_ok=True)

    # Launch Chrome headless with clean isolated user-data-dir
    chrome_proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={temp_profile}",
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1440,1080",
        "about:blank"
    ])

    print(f"Launched Chrome PID {chrome_proc.pid} with profile: {temp_profile}", flush=True)
    time.sleep(2)

    try:
        # Find WebSocket URL for page
        ws_url = None
        for _ in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://127.0.0.1:{DEBUG_PORT}/json")
                    pages = resp.json()
                    page_targets = [p for p in pages if p.get("type") == "page"]
                    if page_targets:
                        ws_url = page_targets[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                time.sleep(0.5)

        if not ws_url:
            raise RuntimeError("Could not find Chrome page target WebSocketDebuggerUrl")

        print(f"Connected to CDP Page target: {ws_url}", flush=True)

        results = []

        async with websockets.connect(ws_url, max_size=35_000_000) as ws:
            msg_id = [1]
            await send_cdp(ws, "Page.enable", msg_id=msg_id)
            await send_cdp(ws, "Runtime.enable", msg_id=msg_id)

            for i, item in enumerate(TEST_QUESTIONS, 1):
                qid = item["id"]
                sym = item["symbol"]
                q = item["question"]
                title = item["title"]
                print(f"\n[{i}/10] Testing: {title} ({sym})", flush=True)

                # Build URL with autoSubmit=1
                query_enc = urllib.parse.quote(q)
                target_url = f"http://localhost:3000/ai?symbol={sym}&q={query_enc}&autoSubmit=1"
                
                await send_cdp(ws, "Page.navigate", {"url": target_url}, msg_id=msg_id)

                # Wait for response to render (poll for .answerContent or .claimsHeading)
                poll_start = time.time()
                rendered = False
                answer_info = {}

                while time.time() - poll_start < 20.0:
                    await asyncio.sleep(0.6)
                    eval_res = await send_cdp(ws, "Runtime.evaluate", {
                        "expression": """
                        (() => {
                            const ansEl = document.querySelector('[class*="answerContent"]');
                            const errEl = document.querySelector('[class*="errorState"]');
                            const claims = document.querySelectorAll('[class*="claimCard"]');
                            const pills = document.querySelectorAll('[class*="citationPill"]');
                            const fallback = document.querySelector('[class*="fallbackCard"]');
                            const table = document.querySelector('[class*="summaryTable"]');
                            const empty = document.querySelector('[class*="emptyState"]');
                            const lead = document.querySelector('[class*="answerLeadText"]');
                            const busy = document.querySelector('[class*="streamingState"]');
                            
                            return {
                                hasAnswer: !!ansEl,
                                hasError: !!errEl,
                                isBusy: !!busy,
                                errorText: errEl ? errEl.innerText : null,
                                claimsCount: claims.length,
                                pillsCount: pills.length,
                                hasFallback: !!fallback,
                                hasTable: !!table,
                                hasEmpty: !!empty,
                                leadText: lead ? lead.innerText.slice(0, 150) : null
                            };
                        })()
                        """,
                        "returnByValue": True
                    }, msg_id=msg_id)

                    val = eval_res.get("result", {}).get("value", {})
                    if val.get("hasAnswer"):
                        rendered = True
                        answer_info = val
                        break
                    elif val.get("hasError"):
                        answer_info = val
                        break

                elapsed = round(time.time() - poll_start, 2)
                print(f"    Status: {'SUCCESS' if rendered else 'FAILED'} | Elapsed: {elapsed}s | Claims: {answer_info.get('claimsCount', 0)} | Pills: {answer_info.get('pillsCount', 0)}", flush=True)

                # Wait 500ms for smooth fonts and animations to settle
                await asyncio.sleep(0.5)

                # Capture full screenshot
                shot_data = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_id)
                img_bytes = base64.b64decode(shot_data["data"])
                out_path = os.path.join(OUT_DIR, f"{qid}.png")
                with open(out_path, "wb") as img_f:
                    img_f.write(img_bytes)

                print(f"    Saved screenshot -> {out_path} ({len(img_bytes):,} bytes)", flush=True)

                results.append({
                    "id": qid,
                    "title": title,
                    "symbol": sym,
                    "question": q,
                    "rendered": rendered,
                    "elapsed_s": elapsed,
                    "claims_count": answer_info.get("claimsCount", 0),
                    "citations_count": answer_info.get("pillsCount", 0),
                    "has_fallback": answer_info.get("hasFallback", False),
                    "has_table": answer_info.get("hasTable", False),
                    "screenshot_path": out_path,
                    "lead_text": answer_info.get("leadText", ""),
                })

        summary_path = os.path.join(OUT_DIR, "test_results_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n==========================================", flush=True)
        print(f"All 10 questions tested and captured!", flush=True)
        total_rendered = sum(1 for r in results if r["rendered"])
        print(f"Results successfully rendered: {total_rendered}/10", flush=True)
        print(f"Summary JSON: {summary_path}", flush=True)
        print(f"==========================================", flush=True)

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            chrome_proc.kill()
        try:
            shutil.rmtree(temp_profile, ignore_errors=True)
        except Exception:
            pass
        print("Chrome closed.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

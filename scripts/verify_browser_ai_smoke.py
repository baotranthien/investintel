import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import httpx
import websockets

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
OUT_DIR = r"C:\Users\baotr\Downloads\trading\docs\audits\evidence"
os.makedirs(OUT_DIR, exist_ok=True)

QUESTION = "Phân tích FPT dựa trên dữ liệu hiện có. Nêu giá và ngày dữ liệu, EPS, P/E và P/B nếu có. Phân biệt dữ liệu thực tế với số liệu ước tính và ghi rõ các chỉ tiêu còn thiếu."

class ChromeBrowser:
    def __init__(self):
        self.proc = None
        self.ws = None
        self.msg_id = 0

    async def start(self):
        profile_dir = r"C:\Users\baotr\Downloads\trading\scratch\chrome_ai_smoke_profile"
        os.makedirs(profile_dir, exist_ok=True)
        cmd = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={CDP_PORT}",
            "--window-size=1440,1100",
            "about:blank",
        ]
        self.proc = subprocess.Popen(cmd)
        
        for _ in range(30):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{CDP_URL}/json/version")
                    if resp.status_code == 200:
                        break
            except Exception:
                await asyncio.sleep(0.5)

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CDP_URL}/json")
            tabs = resp.json()
            ws_url = tabs[0]["webSocketDebuggerUrl"]

        self.ws = await websockets.connect(ws_url, max_size=20 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("DOM.enable")
        await self.send("Runtime.enable")

    async def send(self, method: str, params: dict | None = None):
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self.msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error']}")
                return data.get("result", {})

    async def eval_js(self, expression: str):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = res.get("result", {})
        return val.get("value")

    async def navigate(self, url: str):
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(2.0)

    async def screenshot(self, filepath: str):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(res["data"])
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"Captured screenshot: {filepath} ({len(data)} bytes)")

    async def close(self):
        try:
            if self.ws:
                await self.ws.close()
        except Exception:
            pass
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()

async def run_smoke_test():
    browser = ChromeBrowser()
    try:
        print("Starting headless Chrome for AI Analyst smoke test...")
        await browser.start()

        # Navigate with query params to prefill FPT and question natively via React URL state
        target_url = f"http://localhost:3000/ai?symbol=FPT&q={urllib.parse.quote(QUESTION)}"
        print(f"Navigating to {target_url}...")
        await browser.navigate(target_url)
        
        # Wait for textarea and input to appear and be populated
        print("Waiting for page inputs to load and prefill...")
        for i in range(30):
            ready = await browser.eval_js("""
                Boolean(
                    document.querySelector('textarea')?.value && 
                    document.querySelector('input[type=\"text\"]')?.value === 'FPT'
                )
            """)
            if ready:
                print(f"Page inputs prefilled and ready after {i * 0.5:.1f}s")
                break
            await asyncio.sleep(0.5)

        # Check badge text
        badge_text = await browser.eval_js("""
            (() => {
                const el = document.querySelector('[class*=\"heroBadge\"], [class*=\"badge\"]');
                return el ? el.innerText : '';
            })()
        """)
        print(f"Hero badge text: {badge_text}")

        # Verify values entered
        entered_sym = await browser.eval_js("document.querySelector('input[type=\"text\"]')?.value")
        entered_q = await browser.eval_js("document.querySelector('textarea')?.value")
        print(f"Verified prefilled values -> Symbol: '{entered_sym}', Question length: {len(entered_q or '')}")

        # Click Submit Button
        print("Submitting the question through the form...")
        t_start = time.time()
        await browser.eval_js("""
            (() => {
                const form = document.querySelector('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                } else {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const submitBtn = btns.find(b => b.innerText.includes('Gửi') || b.innerText.includes('Phân tích') || b.type === 'submit');
                    if (submitBtn) submitBtn.click();
                }
            })()
        """)

        # Poll for completion up to 210s
        print("Waiting for streaming answer completion (timeout=210s)...", flush=True)
        answer_found = False
        
        for poll_i in range(105):  # 105 * 2s = 210s
            await asyncio.sleep(2.0)
            elapsed = time.time() - t_start
            
            # Check if answer container is rendered
            has_answer = await browser.eval_js("""
                (() => {
                    const text = document.body.innerText;
                    return text.includes('KẾT QUẢ ĐỐI SOÁT') || text.includes('Evidence:') || text.includes('E038') || text.includes('10,18') || text.includes('10.18');
                })()
            """)
            
            # Check for progress status
            status_text = await browser.eval_js("""
                (() => {
                    const el = document.querySelector('[class*=\"progress\"], [class*=\"status\"], [class*=\"pulse\"]');
                    return el ? el.innerText : '';
                })()
            """)
            if poll_i % 5 == 0 or has_answer:
                print(f"[{elapsed:.1f}s] Polling UI status: {status_text[:60] if status_text else 'processing...'}")
            
            if has_answer:
                answer_found = True
                print(f"\nSUCCESS: AI Analyst response rendered in UI after {elapsed:.2f}s!")
                break

        # Let the UI render settled state
        await asyncio.sleep(2.0)

        # Capture full screenshot
        screenshot_path = os.path.join(OUT_DIR, "qwen35_9b_smoke_test.png")
        await browser.screenshot(screenshot_path)

        # Extract answer container text
        page_content = await browser.eval_js("document.body.innerText")
        
        print("\n=== BROWSER SMOKE TEST RESULT SUMMARY ===")
        print(f"Answer rendered: {answer_found}")
        print(f"Total UI duration: {time.time() - t_start:.2f}s")
        print(f"Screenshot saved to: {screenshot_path}")
        
        contains_model = "qwen3.5:9b-q4_K_M" in page_content
        contains_pe = "P/E" in page_content or "p/e" in page_content
        contains_evidence = "Evidence" in page_content or "E038" in page_content or "E0" in page_content
        print(f"Contains configured model (qwen3.5:9b-q4_K_M): {contains_model}")
        print(f"Contains P/E metrics: {contains_pe}")
        print(f"Contains Evidence citations: {contains_evidence}")

        return answer_found and contains_model

    finally:
        await browser.close()

if __name__ == "__main__":
    success = asyncio.run(run_smoke_test())
    sys.exit(0 if success else 1)

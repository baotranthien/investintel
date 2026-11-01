"""
Live browser verification script for Opportunities -> AI Analyst context handoff.
Connects to headless Chrome via Chrome DevTools Protocol (CDP) to verify:
1. "Hỏi AI" link generation on Opportunities page
2. Context handoff navigation to /ai for FPT
3. Ticker input selection and visible question textarea prefill
4. No automatic submission (user must click submit)
5. Idempotent state: user-edited text is preserved across re-renders
6. Navigation for a second opportunity (e.g. HPG/MWG) carries its own ticker without reusing FPT
7. Direct navigation to /ai without params remains un-prefilled
"""

import asyncio
import json
import os
import subprocess
import sys
import time
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


class ChromeBrowser:
    def __init__(self):
        self.proc = None
        self.ws = None
        self.msg_id = 0

    async def start(self):
        profile_dir = r"C:\Users\baotr\Downloads\trading\scratch\chrome_verify_profile"
        os.makedirs(profile_dir, exist_ok=True)
        cmd = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={CDP_PORT}",
            "--window-size=1440,900",
            "about:blank",
        ]
        self.proc = subprocess.Popen(cmd)
        
        # Wait for CDP endpoint to become ready
        for _ in range(30):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{CDP_URL}/json/version", timeout=1.0)
                    if resp.status_code == 200:
                        break
            except Exception:
                await asyncio.sleep(0.3)
        else:
            raise RuntimeError("Chrome CDP did not become ready in time")

        # Get WebSocket debugger URL for the page target (not background extensions)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CDP_URL}/json", timeout=2.0)
            targets = resp.json()
            page_target = next((t for t in targets if t.get("type") == "page"), targets[0])
            ws_url = page_target["webSocketDebuggerUrl"]

        self.ws = await websockets.connect(ws_url, max_size=20 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        await self.send("DOM.enable")

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

    async def navigate(self, url: str):
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(1.5)

    async def eval_js(self, expression: str):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = res.get("result", {})
        return val.get("value")

    async def screenshot(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        import base64
        data = base64.b64decode(res["data"])
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"  [Artifact] Saved screenshot to {filepath} ({len(data)} bytes)")

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()


async def main():
    print("=== LIVE BROWSER VERIFICATION: Opportunities -> AI Analyst Handoff ===")
    browser = ChromeBrowser()
    try:
        await browser.start()
        print("1. Headless Chrome started with CDP on port", CDP_PORT)

        # ---------------------------------------------------------------------
        # TEST 1: Opportunities page inspection
        # ---------------------------------------------------------------------
        print("\n2. Navigating to http://localhost:3000/opportunities ...")
        await browser.navigate("http://localhost:3000/opportunities")
        
        # Wait for data to fetch and cards to render (up to 60s for initial calculation)
        print("  Waiting for opportunity cards to calculate and render...")
        for i in range(120):
            has_cards = await browser.eval_js("Boolean(document.querySelector('article'))")
            if has_cards:
                print(f"  Opportunity cards rendered after ~{i * 0.5:.1f}s")
                break
            await asyncio.sleep(0.5)

        # Inspect the "Hỏi AI" links on the Opportunities page
        links_info = await browser.eval_js("""
            (() => {
                const links = Array.from(document.querySelectorAll('a'))
                    .filter(a => a.textContent.includes('Hỏi AI') || a.href.includes('/ai?'));
                return links.map(a => ({
                    text: a.textContent.trim(),
                    href: a.getAttribute('href')
                }));
            })()
        """)
        print(f"  Found {len(links_info)} 'Hỏi AI' links on Opportunities page.")
        assert len(links_info) > 0, "Expected at least one 'Hỏi AI' link on Opportunities page"
        
        # Verify FPT link formatting
        fpt_link = next((item for item in links_info if "symbol=FPT" in item["href"]), None)
        assert fpt_link is not None, "Expected an opportunity link for FPT"
        print("  FPT Link Target:", fpt_link["href"])
        assert "source=opportunities" in fpt_link["href"]
        assert "symbol=FPT" in fpt_link["href"]
        assert "q=" in fpt_link["href"]

        # ---------------------------------------------------------------------
        # TEST 2: Click/Navigate to AI Analyst with FPT opportunity context
        # ---------------------------------------------------------------------
        fpt_target_url = "http://localhost:3000" + fpt_link["href"]
        print(f"\n3. Navigating to AI Analyst via FPT link: {fpt_target_url} ...")
        await browser.navigate(fpt_target_url)
        await asyncio.sleep(2.0)

        # Check ticker input value
        ticker_val = await browser.eval_js("document.querySelector('input[placeholder=\"MÃ CP\"]')?.value")
        print(f"  [AI Page] Ticker Input value: '{ticker_val}'")
        assert ticker_val == "FPT", f"Expected ticker 'FPT', got '{ticker_val}'"

        # Check visible question textarea value
        question_val = await browser.eval_js("document.querySelector('textarea')?.value")
        print(f"  [AI Page] Textarea value preview: '{question_val[:90]}...'")
        assert "Phân tích cơ hội đầu tư của cổ phiếu FPT" in question_val
        assert "độ mới của dữ liệu" in question_val
        assert "Phân biệt số liệu thực tế với ước tính" in question_val

        # Check that it did NOT auto-submit
        is_busy = await browser.eval_js("document.querySelector('button[type=\"submit\"]')?.textContent")
        has_answer = await browser.eval_js("Boolean(document.querySelector('article'))")
        print(f"  [AI Page] Submit button text: '{is_busy}', Has answer card rendered: {has_answer}")
        assert "Đang xử lý" not in is_busy, "Question must not be submitted automatically"
        assert not has_answer, "No answer card should be rendered before user explicitly submits"

        # Check top suggestion pill selection
        is_pill_active = await browser.eval_js("""
            (() => {
                const pills = Array.from(document.querySelectorAll('button'))
                    .filter(b => b.textContent.trim() === 'FPT');
                if (pills.length === 0) return false;
                const style = window.getComputedStyle(pills[0]);
                return style.backgroundColor.includes('29, 29, 31') || style.backgroundColor.includes('rgb(29, 29, 31)');
            })()
        """)
        print(f"  [AI Page] FPT top selector pill is active: {is_pill_active}")

        await browser.screenshot(os.path.join(OUT_DIR, "browser_handoff_fpt.png"))

        # ---------------------------------------------------------------------
        # TEST 3: User edit preservation & idempotency
        # ---------------------------------------------------------------------
        print("\n4. Testing user edit preservation across re-renders ...")
        # Append user-specific custom inquiry text
        await browser.eval_js("""
            (() => {
                const ta = document.querySelector('textarea');
                const newText = ta.value + " [GHI CHÚ RIÊNG CỦA NHÀ ĐẦU TƯ: Ưu tiên phân tích dòng tiền]";
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, newText);
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            })()
        """)
        edited_val = await browser.eval_js("document.querySelector('textarea')?.value")
        assert "[GHI CHÚ RIÊNG CỦA NHÀ ĐẦU TƯ: Ưu tiên phân tích dòng tiền]" in edited_val

        # Toggle a tool checkbox to trigger React re-render
        await browser.eval_js("""
            (() => {
                const cb = document.querySelector('input[type=\"checkbox\"]');
                if (cb) { cb.click(); }
            })()
        """)
        await asyncio.sleep(0.5)

        # Check that edited text was NOT wiped out by searchParams
        post_rerender_val = await browser.eval_js("document.querySelector('textarea')?.value")
        print("  [AI Page] Textarea value after re-render preserved user edit:",
              "[GHI CHÚ RIÊNG CỦA NHÀ ĐẦU TƯ: Ưu tiên phân tích dòng tiền]" in post_rerender_val)
        assert "[GHI CHÚ RIÊNG CỦA NHÀ ĐẦU TƯ: Ưu tiên phân tích dòng tiền]" in post_rerender_val, \
            "User edits must not be overwritten by searchParams on re-render"

        # ---------------------------------------------------------------------
        # TEST 4: Navigation for a second opportunity (e.g. HPG)
        # ---------------------------------------------------------------------
        hpg_link = next((item for item in links_info if "symbol=HPG" in item["href"]), None)
        hpg_target = hpg_link["href"] if hpg_link else "/ai?symbol=HPG&source=opportunities&q=" + urllib.parse.quote("Phân tích cơ hội đầu tư của cổ phiếu HPG dựa trên dữ liệu hiện có trong InvestIntel. Hãy trình bày các luận điểm hỗ trợ, định giá, rủi ro, độ mới của dữ liệu và những thông tin chưa đủ bằng chứng. Phân biệt số liệu thực tế với ước tính.")
        
        print(f"\n5. Navigating to AI Analyst via HPG opportunity link: {hpg_target} ...")
        await browser.navigate("http://localhost:3000" + hpg_target)
        await asyncio.sleep(2.0)

        ticker_val_hpg = await browser.eval_js("document.querySelector('input[placeholder=\"MÃ CP\"]')?.value")
        question_val_hpg = await browser.eval_js("document.querySelector('textarea')?.value")
        print(f"  [AI Page] Second stock ticker: '{ticker_val_hpg}'")
        print(f"  [AI Page] Second stock question preview: '{question_val_hpg[:90]}...'")

        assert ticker_val_hpg == "HPG", f"Expected 'HPG', got '{ticker_val_hpg}'"
        assert "Phân tích cơ hội đầu tư của cổ phiếu HPG" in question_val_hpg
        assert "FPT" not in question_val_hpg, "Second opportunity must NOT reuse FPT ticker or question"

        await browser.screenshot(os.path.join(OUT_DIR, "browser_handoff_second_stock.png"))

        # ---------------------------------------------------------------------
        # TEST 5: Direct navigation to /ai without parameters
        # ---------------------------------------------------------------------
        print("\n6. Direct navigation to http://localhost:3000/ai (without parameters) ...")
        await browser.navigate("http://localhost:3000/ai")
        await asyncio.sleep(2.0)

        ticker_direct = await browser.eval_js("document.querySelector('input[placeholder=\"MÃ CP\"]')?.value")
        question_direct = await browser.eval_js("document.querySelector('textarea')?.value")
        print(f"  [AI Page Direct] Ticker: '{ticker_direct}', Question: '{question_direct}'")
        assert ticker_direct == "", f"Direct navigation should have blank ticker, got '{ticker_direct}'"
        assert question_direct == "", f"Direct navigation should have empty question, got '{question_direct}'"

        await browser.screenshot(os.path.join(OUT_DIR, "browser_handoff_direct.png"))

        print("\n>>> ALL 5 LIVE BROWSER VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

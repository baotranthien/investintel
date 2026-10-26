import sys
import httpx
import re

sys.stdout.reconfigure(encoding='utf-8')

print("1. PROBING RENDER BACKEND...")
try:
    r = httpx.get("https://investintel-api.onrender.com/health", timeout=30)
    print("Render /health:", r.status_code, r.text)
    print("Render rndr-id:", r.headers.get("rndr-id"))
    print("Render server:", r.headers.get("server"))
    print("Render x-render-origin-server:", r.headers.get("x-render-origin-server"))
except Exception as e:
    print("Render health failed:", e)

print("\n2. PROBING VERCEL FRONTEND...")
try:
    r = httpx.get("https://investintel-nine.vercel.app/login", timeout=30)
    print("Vercel /login:", r.status_code)
    print("Vercel etag:", r.headers.get("etag"))
    print("Vercel x-vercel-id:", r.headers.get("x-vercel-id"))
    print("Vercel x-vercel-cache:", r.headers.get("x-vercel-cache"))
    
    # Extract Next.js script chunks
    chunks = re.findall(r'/_next/static/chunks/[^"\']+', r.text)
    print("Vercel chunks found:", len(chunks))
    for c in chunks[:5]:
        print("  chunk:", c)
except Exception as e:
    print("Vercel probe failed:", e)

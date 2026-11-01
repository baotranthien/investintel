import asyncio
import json
import os
import sys
import time
import httpx

sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

QUESTION = "Phân tích FPT dựa trên dữ liệu hiện có. Nêu giá và ngày dữ liệu, EPS, P/E và P/B nếu có. Phân biệt dữ liệu thực tế với số liệu ước tính và ghi rõ các chỉ tiêu còn thiếu."

async def test_stream():
    url = "http://127.0.0.1:8000/api/v1/ai/chat/stream"
    payload = {
        "question": QUESTION,
        "symbol": "FPT",
        "tool_names": [
            "asset", "fundamentals", "valuation", "factors", "risk", "macro", "regime",
            "events", "opportunity", "portfolio", "watchlist", "historical_snapshot",
            "evidence", "document_retrieval"
        ]
    }
    
    print(f"Submitting AI Analyst question for FPT (Timeout=120s)...")
    print(f"Question: {QUESTION}")
    
    t0 = time.time()
    events = []
    final_response = None
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            print(f"Stream connected with status {resp.status_code}")
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)
                    for line in event_text.splitlines():
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                print(f"[{time.time()-t0:.1f}s] STREAM [DONE]")
                                continue
                            try:
                                data = json.loads(raw_data)
                                events.append(data)
                                event_type = data.get("type")
                                if event_type == "status":
                                    step = data.get("step")
                                    msg = data.get("message")
                                    print(f"[{time.time()-t0:.1f}s] STATUS: step={step} msg={msg}")
                                elif event_type == "result":
                                    final_response = data.get("data", data)
                                    print(f"[{time.time()-t0:.1f}s] FINAL RESULT EVENT RECEIVED!")
                            except json.JSONDecodeError:
                                pass

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.2f}s")
    
    if final_response:
        print("\n=== AI ANALYST FINAL RESULT ===")
        print("Status:", final_response.get("status"))
        print("Model used:", final_response.get("model"))
        print("Symbol:", final_response.get("symbol"))
        print("Answer length:", len(final_response.get("answer", "")))
        print("Answer:\n", final_response.get("answer"))
        print("\nClaims count:", len(final_response.get("claims", [])))
        for idx, c in enumerate(final_response.get("claims", []), 1):
            print(f"  Claim {idx} [{c.get('claim_type')}]: {c.get('text')} (citations: {c.get('citation_ids')})")
        print("\nCitations count:", len(final_response.get("citations", [])))
        print("Uncertainty notes count:", len(final_response.get("uncertainty", [])))
        for idx, u in enumerate(final_response.get("uncertainty", []), 1):
            print(f"  Uncertainty {idx}: {u}")
        print("Metadata flags:", final_response.get("metadata_flags"))
        print("Usage:", final_response.get("usage"))
        
        # Save output to json for verification artifact
        with open("docs/audits/evidence/qwen35_9b_analyst_response.json", "w", encoding="utf-8") as f:
            json.dump({
                "duration_seconds": elapsed,
                "events_count": len(events),
                "final_response": final_response,
            }, f, ensure_ascii=False, indent=2)
        print("\nSaved result to docs/audits/evidence/qwen35_9b_analyst_response.json")
        return True
    else:
        print("FAILED: No final response received!")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_stream())
    sys.exit(0 if success else 1)

import asyncio
import json
import os
import sys
import time
import httpx

sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from services.ai.schemas import AIAnswerDraft

SCHEMA = AIAnswerDraft.model_json_schema()

PROMPT = (
    "Định nghĩa ngắn gọn chỉ số P/E trong 1 câu và liệt kê 1 luận điểm xác nhận (FACT).\n"
    "Dữ liệu: P/E của FPT là 22.5.\n"
    "Xuất JSON theo schema yêu cầu."
)
SYSTEM = "Bạn là trợ lý tài chính. Trả lời bằng tiếng Việt và tuân thủ tuyệt đối schema JSON."

async def test_config(name: str, payload_extra: dict, timeout_sec: float = 120.0):
    print(f"\n==========================================")
    print(f"TESTING CONFIG: {name}")
    print(f"Payload extra: {payload_extra}")
    print(f"Timeout: {timeout_sec}s")
    print(f"==========================================")
    
    payload = {
        "model": "qwen3.5:9b-q4_K_M",
        "prompt": PROMPT,
        "system": SYSTEM,
        "stream": False,
        "format": SCHEMA,
        "options": {
            "num_ctx": 4096,
            "num_predict": 512,
        },
        **payload_extra
    }
    
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
            elapsed = time.time() - t0
            status_code = resp.status_code
            data = resp.json()
            
        response_text = data.get("response", "")
        thinking_text = data.get("thinking", "")
        eval_count = data.get("eval_count", 0)
        done_reason = data.get("done_reason")
        
        print(f"HTTP Status: {status_code} in {elapsed:.2f}s")
        print(f"Eval count: {eval_count} tokens")
        print(f"Thinking length: {len(thinking_text)} chars")
        print(f"Response length: {len(response_text)} chars")
        print(f"Done reason: {done_reason}")
        
        is_nonempty = bool(response_text and response_text.strip())
        print(f"Response nonempty: {is_nonempty}")
        
        if not is_nonempty:
            print("FAILURE: Ollama returned empty response content.")
            return {
                "name": name,
                "finished": True,
                "nonempty": False,
                "json_parsed": False,
                "schema_satisfied": False,
                "timeout": False,
                "error": "Empty response content",
                "duration": elapsed,
                "eval_count": eval_count,
            }
            
        # JSON parsing
        try:
            parsed = json.loads(response_text)
            print("JSON parsing: SUCCESS")
        except json.JSONDecodeError as je:
            print(f"FAILURE: JSON decode error: {je}")
            return {
                "name": name,
                "finished": True,
                "nonempty": True,
                "json_parsed": False,
                "schema_satisfied": False,
                "timeout": False,
                "error": f"JSONDecodeError: {je}",
                "duration": elapsed,
                "eval_count": eval_count,
            }
            
        # Schema satisfaction
        try:
            validated = AIAnswerDraft.model_validate(parsed)
            print("Schema validation: SUCCESS")
            print("Validated Answer:", validated.answer[:150])
            print("Validated Claims count:", len(validated.claims))
            return {
                "name": name,
                "finished": True,
                "nonempty": True,
                "json_parsed": True,
                "schema_satisfied": True,
                "timeout": False,
                "error": None,
                "duration": elapsed,
                "eval_count": eval_count,
            }
        except Exception as ve:
            print(f"FAILURE: Schema validation error: {ve}")
            return {
                "name": name,
                "finished": True,
                "nonempty": True,
                "json_parsed": True,
                "schema_satisfied": False,
                "timeout": False,
                "error": f"ValidationError: {ve}",
                "duration": elapsed,
                "eval_count": eval_count,
            }

    except httpx.TimeoutException:
        elapsed = time.time() - t0
        print(f"FAILURE: Request TIMED OUT after {elapsed:.2f}s")
        return {
            "name": name,
            "finished": False,
            "nonempty": False,
            "json_parsed": False,
            "schema_satisfied": False,
            "timeout": True,
            "error": f"TimeoutException after {elapsed:.2f}s",
            "duration": elapsed,
            "eval_count": 0,
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILURE: Runtime error: {type(e).__name__}: {e}")
        return {
            "name": name,
            "finished": False,
            "nonempty": False,
            "json_parsed": False,
            "schema_satisfied": False,
            "timeout": False,
            "error": f"{type(e).__name__}: {e}",
            "duration": elapsed,
            "eval_count": 0,
        }

async def main():
    results = []
    
    # Config 1: Production baseline (no think parameter)
    res1 = await test_config("Config 1: Current Production (no think parameter)", {}, timeout_sec=120.0)
    results.append(res1)
    
    # Config 2: think=False
    res2 = await test_config("Config 2: think=False", {"think": False}, timeout_sec=120.0)
    results.append(res2)
    
    print("\n\n================ SUMMARY OF DIAGNOSTIC ================")
    for r in results:
        print(f"[{r['name']}]")
        print(f"  Finished: {r['finished']}")
        print(f"  Nonempty: {r['nonempty']}")
        print(f"  JSON Parsed: {r['json_parsed']}")
        print(f"  Schema Satisfied: {r['schema_satisfied']}")
        print(f"  Timeout: {r['timeout']}")
        print(f"  Duration: {r['duration']:.2f}s")
        print(f"  Tokens: {r['eval_count']}")
        print(f"  Error: {r['error']}")

if __name__ == "__main__":
    asyncio.run(main())


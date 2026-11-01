import urllib.request
import json
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

payload = {
    "model": "qwen3.5:9b-q4_K_M",
    "prompt": "Giải thích ngắn gọn chỉ số P/E trong không quá 3 câu bằng tiếng Việt.",
    "stream": False,
    "think": False,
    "options": {
        "num_ctx": 4096,
        "num_predict": 256
    }
}

req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

start = time.time()
print("Starting bounded simple generation test (timeout=60s)...", flush=True)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    print("=== SIMPLE GENERATION SUCCESS ===")
    print("Model:", data.get("model"))
    print("Response text:", data.get("response"))
    print(f"Eval count: {data.get('eval_count')} tokens")
    print(f"Prompt eval duration: {data.get('prompt_eval_duration', 0) / 1e9:.2f}s")
    print(f"Eval duration: {data.get('eval_duration', 0) / 1e9:.2f}s")
    print(f"Total time (wall): {elapsed:.2f}s")
    speed = data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9)
    print(f"Inference speed: {speed:.2f} tokens/s")
    print("Done reason:", data.get("done_reason"))
except Exception as e:
    elapsed = time.time() - start
    print(f"=== SIMPLE GENERATION FAILED after {elapsed:.2f}s: {type(e).__name__}: {e} ===")
    sys.exit(1)


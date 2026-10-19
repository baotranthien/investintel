import sys
sys.path.insert(0, '.')
import httpx
import time
from scripts.verify_live_prod import BASE_URL, CRON_SECRET

headers = {
    "Content-Type": "application/json",
    "X-Cron-Secret": CRON_SECRET
}

def ingest_fundamentals(symbols: list[str]):
    print(f"\n>>> Ingesting Fundamentals for {symbols}...")
    payload = {
        "providers": ["VNDIRECT"],
        "datasets": ["FUNDAMENTALS"],
        "symbols": symbols,
        "force": True
    }
    with httpx.Client(timeout=300.0) as client:
        t0 = time.time()
        res = client.post(f"{BASE_URL}/api/v1/system/cron/run-ingestion", headers=headers, json=payload)
        elapsed = time.time() - t0
        print(f"[{res.status_code}] elapsed: {elapsed:.1f}s")
        if res.status_code == 200:
            data = res.json()
            print("Status:", data.get("status"))
            for r in data.get("results", []):
                print("Result:", r.get("provider"), r.get("dataset"), r.get("status"), "records:", r.get("records_inserted"))
        else:
            print("Error:", res.text[:300])

if __name__ == "__main__":
    # Ingest for VCB and MBB first
    ingest_fundamentals(["VCB", "MBB"])
    # Ingest for MWG and HPG
    ingest_fundamentals(["MWG", "HPG"])

import sys
sys.path.insert(0, '.')
import httpx
import json
import time
from scripts.verify_live_prod import BASE_URL, CRON_SECRET

headers = {
    "Content-Type": "application/json",
    "X-Cron-Secret": CRON_SECRET
}

def run_batch(name: str, symbols: list[str], datasets: list[str] = ["PRICES"]):
    print(f"\n>>> Running {name} ({len(symbols)} symbols: {symbols[:4]}...)...")
    payload = {
        "providers": ["VNDIRECT"],
        "datasets": datasets,
        "symbols": symbols,
        "force": True
    }
    with httpx.Client(timeout=180.0) as client:
        start_t = time.time()
        res = client.post(f"{BASE_URL}/api/v1/system/cron/run-ingestion", headers=headers, json=payload)
        elapsed = time.time() - start_t
        print(f"[{res.status_code}] elapsed: {elapsed:.1f}s")
        if res.status_code == 200:
            data = res.json()
            print("Status:", data.get("status"))
            summary = data.get("summary", {})
            print("Summary:", summary)
            failed = [r for r in data.get("results", []) if r.get("status") == "FAILURE"]
            if failed:
                print(f"Failed ({len(failed)}):", [f.get("symbol") for f in failed])
        else:
            print("Error:", res.text[:200])

if __name__ == "__main__":
    # Batch 4: VN100 midcaps part 1
    run_batch("VN100_Batch_1", ["ANV", "BAF", "BMP", "BSI", "CII", "CTD", "CTR", "CTS", "DBC", "DCM", "DGC", "DGW", "DIG"])
    # Batch 5: VN100 midcaps part 2
    run_batch("VN100_Batch_2", ["DPM", "DXG", "EIB", "EVF", "FRT", "GEX", "HDG", "HHV", "HSG", "KBC", "KDC", "KDH"])

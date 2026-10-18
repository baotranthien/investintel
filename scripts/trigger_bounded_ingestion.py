"""
Trigger bounded LotusMarket ingestion on Render for FPT, VCB, MBB, MWG, HPG.
"""
import json
from pathlib import Path
import httpx

authsecr_path = Path(__file__).resolve().parent.parent / "authsecr.txt"
with open(authsecr_path, "r", encoding="utf-8") as f:
    secret = [l.strip() for l in f if l.strip()][1]

payload = {
    "force": True,
    "providers": ["LOTUSMARKET"],
    "symbols": ["FPT", "VCB", "MBB", "MWG", "HPG"],
}

print("Executing bounded LotusMarket ingestion on Render...")
with httpx.Client(timeout=180.0) as client:
    r = client.post(
        "https://investintel-api.onrender.com/api/v1/system/cron/run-ingestion",
        headers={"X-Cron-Secret": secret},
        json=payload,
    )
    print(f"HTTP Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Job Status: {data.get('status')}")
        print(f"Idempotency Key: {data.get('idempotency_key')}")
        print(f"Results Count: {data.get('results_count')}")
        for res in data.get("results", []):
            prov = res.get("provider")
            sym = res.get("symbol", "")
            dset = res.get("dataset", "prices")
            st = res.get("status")
            prom = res.get("records_promoted", res.get("events_ingested", 0))
            rej = res.get("records_rejected", 0)
            reason = res.get("reason", "")
            print(f"  [{prov}] {sym} ({dset}): status={st}, promoted={prom}, rejected={rej} {reason}")
    else:
        print(f"Error Response: {r.text}")

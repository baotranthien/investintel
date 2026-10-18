"""
Phase B — Read-only live verification of LotusMarket data sources for FPT, ACB, HPG.
Tests live availability, response schemas, price units, date formats, and OHLC consistency.
"""

import sys
import json
import time
from datetime import datetime, timedelta
import httpx

sys.stdout.reconfigure(encoding="utf-8")

SAMPLE_TICKERS = ["FPT", "ACB", "HPG"]

def test_vps():
    print("=" * 60)
    print("1. TESTING VPS QUOTES (https://bgapidatafeed.vps.com.vn)")
    print("=" * 60)
    url = f"https://bgapidatafeed.vps.com.vn/getliststockdata/{','.join(SAMPLE_TICKERS)}"
    try:
        resp = httpx.get(url, timeout=15)
        print(f"VPS HTTP Status: {resp.status_code}, Length: {len(resp.content)} bytes")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Received {len(data)} items from VPS:")
            for item in data:
                sym = item.get("sym")
                last = float(item.get("lastPrice", 0)) * 1000
                ref = float(item.get("r", 0)) * 1000
                high = float(item.get("highPrice", 0)) * 1000
                low = float(item.get("lowPrice", 0)) * 1000
                open_p = float(item.get("openPrice", 0)) * 1000
                lot = int(float(item.get("lot", 0)))
                f_buy = int(float(item.get("fBVol", 0)))
                f_sell = int(float(item.get("fSVolume", 0)))
                print(f"  [{sym}] Close: {last:,.0f} VND (Ref: {ref:,.0f}, Open: {open_p:,.0f}, High: {high:,.0f}, Low: {low:,.0f}) | Vol: {lot:,} | Foreign Buy: {f_buy:,}, Sell: {f_sell:,}, Net: {f_buy - f_sell:,}")
                # Validate OHLC
                if high > 0 and low > 0:
                    assert high >= low, f"High {high} < Low {low}"
                    if open_p > 0:
                        assert high >= open_p and low <= open_p, f"High/Low invalid vs Open: H={high}, L={low}, O={open_p}"
    except Exception as e:
        print(f"VPS Test Error: {type(e).__name__}: {e}")

def test_entrade_history():
    print("\n" + "=" * 60)
    print("2. TESTING ENTRADE HISTORICAL OHLCV (https://services.entrade.com.vn)")
    print("=" * 60)
    now_ts = int(time.time())
    from_ts = int((datetime.now() - timedelta(days=365)).timestamp())
    for ticker in SAMPLE_TICKERS:
        url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={from_ts}&to={now_ts}&symbol={ticker}&resolution=1D"
        try:
            resp = httpx.get(url, timeout=15)
            print(f"Entrade [{ticker}] Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                t = data.get("t", [])
                o = data.get("o", [])
                h = data.get("h", [])
                l = data.get("l", [])
                c = data.get("c", [])
                v = data.get("v", [])
                print(f"  Bars received: {len(t)}")
                if t:
                    first_dt = datetime.fromtimestamp(t[0]).strftime("%Y-%m-%d")
                    last_dt = datetime.fromtimestamp(t[-1]).strftime("%Y-%m-%d")
                    first_c = c[0] * 1000
                    last_c = c[-1] * 1000
                    print(f"  Range: {first_dt} -> {last_dt} | First Close: {first_c:,.0f} VND, Latest Close: {last_c:,.0f} VND")
                    # Check OHLC consistency for last 5 bars
                    for idx in range(max(0, len(t)-5), len(t)):
                        bar_dt = datetime.fromtimestamp(t[idx]).strftime("%Y-%m-%d")
                        op, hp, lp, cp, vol = o[idx]*1000, h[idx]*1000, l[idx]*1000, c[idx]*1000, v[idx]
                        assert hp >= lp, f"Inconsistent bar {bar_dt}: H={hp} < L={lp}"
                        assert hp >= max(op, cp), f"Inconsistent bar {bar_dt}: H={hp} < max(O,C)"
                        assert lp <= min(op, cp), f"Inconsistent bar {bar_dt}: L={lp} > min(O,C)"
                        assert vol >= 0, f"Negative volume in bar {bar_dt}"
                    print(f"  Consistency check passed for [{ticker}] (all OHLC rules valid).")
        except Exception as e:
            print(f"Entrade [{ticker}] Error: {type(e).__name__}: {e}")

def test_kbs_fundamentals():
    print("\n" + "=" * 60)
    print("3. TESTING KBS FUNDAMENTALS (https://kbbuddywts.kbsec.com.vn)")
    print("=" * 60)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    for ticker in SAMPLE_TICKERS:
        url = f"https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock/{ticker}/historical-quotes?from={from_date}&to={to_date}"
        try:
            resp = httpx.get(url, timeout=15)
            print(f"KBS [{ticker}] Status: {resp.status_code}")
            if resp.status_code == 200:
                quotes = resp.json()
                print(f"  Records returned: {len(quotes)}")
                if quotes:
                    q = quotes[0]
                    trade_date = q.get("TradingDate")
                    pe = q.get("PE")
                    pb = q.get("PB")
                    eps = q.get("EPS")
                    bvps = q.get("BVPS")
                    beta = q.get("Beta")
                    mkt_cap = q.get("MarketCapital")
                    div_yield = q.get("Yield")
                    print(f"  [{ticker}] Date: {trade_date} | P/E: {pe} | P/B: {pb} | EPS: {eps:,.0f} VND | BVPS: {bvps:,.0f} VND | Beta: {beta} | Yield: {div_yield}% | MarketCap: {mkt_cap:,.0f} VND")
        except Exception as e:
            print(f"KBS [{ticker}] Error: {type(e).__name__}: {e}")

def test_cafef_insider():
    print("\n" + "=" * 60)
    print("4. TESTING CAFEF INSIDER TRANSACTIONS (https://cafef.vn)")
    print("=" * 60)
    for ticker in SAMPLE_TICKERS:
        url = f"https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx?Symbol={ticker}&PageIndex=1&PageSize=10"
        try:
            resp = httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            print(f"CafeF [{ticker}] Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("Data", [])
                print(f"  Transactions returned: {len(items)}")
                if items:
                    for item in items[:2]:
                        name = item.get("NguoiThucHien")
                        pos = item.get("ChucVu")
                        vol_reg = item.get("SoLuongDK")
                        vol_done = item.get("SoLuongKhop")
                        dt_start = item.get("NgayBatDau")
                        print(f"    - {name} ({pos}): Registered {vol_reg}, Done {vol_done}, Start: {dt_start}")
        except Exception as e:
            print(f"CafeF [{ticker}] Error: {type(e).__name__}: {e}")

def test_edge_cases():
    print("\n" + "=" * 60)
    print("5. TESTING EDGE CASES & MALFORMED INPUTS")
    print("=" * 60)
    # Non-existent ticker
    invalid_url = "https://bgapidatafeed.vps.com.vn/getliststockdata/INVALID999"
    try:
        r = httpx.get(invalid_url, timeout=10)
        print("VPS Invalid Ticker Status:", r.status_code, "Body:", r.text[:100])
    except Exception as e:
        print("VPS Invalid Ticker Error:", e)

    kbs_invalid = "https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock/INVALID999/historical-quotes?from=2026-01-01&to=2026-01-10"
    try:
        r = httpx.get(kbs_invalid, timeout=10)
        print("KBS Invalid Ticker Status:", r.status_code, "Body:", r.text[:100])
    except Exception as e:
        print("KBS Invalid Ticker Error:", e)

if __name__ == "__main__":
    test_vps()
    test_entrade_history()
    test_kbs_fundamentals()
    test_cafef_insider()
    test_edge_cases()

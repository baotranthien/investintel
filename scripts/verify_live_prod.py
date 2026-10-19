import sys
import io
import httpx
import json
import os

sys.path.insert(0, '.')
from services.auth.security import create_session_token

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = os.getenv('API_BASE_URL', 'https://investintel-api.onrender.com')
app_secret = os.getenv('APP_AUTH_SECRET', '')
cron_secret = os.getenv('CRON_SECRET', '')
if os.path.exists('authsecr.txt'):
    with open('authsecr.txt') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
        if len(lines) >= 2:
            app_secret = lines[0]
            cron_secret = lines[1]

APP_SECRET = app_secret
CRON_SECRET = cron_secret

def get_client():
    return httpx.Client(base_url=BASE_URL, timeout=30)

def get_auth_headers():
    token = create_session_token(secret=APP_SECRET)
    return {'Authorization': f'Bearer {token}'}

def main():
    client = get_client()
    auth_headers = get_auth_headers()

    # 1. Health & Ready
    health = client.get('/health').json()
    ready = client.get('/ready').json()
    print('Health:', health.get('status'), '| Ready:', ready.get('status'))

    # 2. Observability
    obs_res = client.get('/api/v1/system/observability')
    print('\n=== OBSERVABILITY (HTTP', obs_res.status_code, ') ===')
    if obs_res.status_code == 200:
        obs = obs_res.json()
        print('Overall status:', obs.get('status'))
        print('Database status:', obs.get('components', {}).get('database', {}).get('status'), '| Backend:', obs.get('components', {}).get('database', {}).get('backend'))
        print('AI status:', obs.get('components', {}).get('ai_provider', {}).get('status'), '| Provider:', obs.get('components', {}).get('ai_provider', {}).get('provider'))
        freshness = obs.get('data_freshness', {})
        print('Total prices:', freshness.get('total_price_records'))
        print('Duplicate prices count:', freshness.get('duplicate_prices_count'))
        print('Unique assets with prices:', freshness.get('assets_with_prices_count'))
        print('Price counts by symbol:', freshness.get('price_counts_by_symbol'))
        print('Price date range:', freshness.get('latest_price_date'))

    # 3. Market Dashboard
    market_res = client.get('/api/v1/market/dashboard', headers=auth_headers)
    print('\n=== MARKET DASHBOARD (HTTP', market_res.status_code, ') ===')
    if market_res.status_code == 200:
        market = market_res.json()
        print('Overall status:', market.get('status'))
        print('Breadth status:', market.get('breadth', {}).get('status'))
        print('Breadth note:', market.get('breadth', {}).get('note'))
        print('Breadth details:', json.dumps(market.get('breadth', {}).get('details'), ensure_ascii=False))
        print('Momentum status:', market.get('momentum', {}).get('status'), '| Value:', market.get('momentum', {}).get('value'))
        for idx in market.get('indexes', []):
            print(f"Index {idx.get('symbol')}: status={idx.get('metric', {}).get('status')}, value={idx.get('metric', {}).get('value')}")
    else:
        print('Market Dashboard Error:', market_res.text)

    # 4. Valuation Endpoints for Key Tickers
    print('\n=== VALUATION ===')
    for sym in ['FPT', 'VCB', 'MBB', 'MWG', 'HPG']:
        val_res = client.get(f'/api/v1/valuation/{sym}', headers=auth_headers)
        if val_res.status_code == 200:
            v = val_res.json()
            print(f"[{sym}] Fair Value: {v.get('composite_fair_value')}, Status: {v.get('status', 'OK')}")
            for m in v.get('methods', []):
                print(f"   - {m.get('method')}: Base={m.get('fair_value', {}).get('base')}, Weight={m.get('weight')}")
                if m.get('assumptions_used'):
                    for a in m.get('assumptions_used'):
                        print(f"       * {a.get('name')}: {a.get('value')} {a.get('unit')} ({a.get('type')})")
        else:
            print(f"[{sym}] HTTP {val_res.status_code}: {val_res.text[:100]}")

    # 5. Research Workspace for Key Tickers
    print('\n=== RESEARCH WORKSPACE ===')
    for sym in ['FPT', 'VCB']:
        res_res = client.get(f'/api/v1/research/{sym}', headers=auth_headers)
        if res_res.status_code == 200:
            r = res_res.json()
            val_m = r.get('valuation', {}).get('metrics', {})
            print(f"[{sym}] Valuation Metrics:")
            for k in ['pe', 'pb', 'ev_ebitda', 'dcf', 'residual_income']:
                item = val_m.get(k, {})
                print(f"   - {k}: status={item.get('status')}, value={item.get('value')}, unit={item.get('unit')}")
        else:
            print(f"[{sym}] HTTP {res_res.status_code}: {res_res.text[:100]}")

    # 6. Cron History
    print('\n=== CRON HISTORY ===')
    hist_res = client.get('/api/v1/system/cron/history', headers={'X-Cron-Secret': CRON_SECRET})
    print('Cron History HTTP:', hist_res.status_code)
    if hist_res.status_code == 200:
        h = hist_res.json()
        print('Summary:', json.dumps(h.get('summary'), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()

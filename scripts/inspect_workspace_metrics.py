import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import date
from database.connection import SessionLocal
from services.research.workspace import build_research_workspace

session = SessionLocal()
try:
    for sym in ['HPG', 'FPT', 'ACB', 'VCB', 'MBB', 'MWG', 'VNM', 'SSI']:
        w = build_research_workspace(session, sym, as_of=date(2026, 10, 26))
        if not w:
            print(f"{sym}: No workspace")
            continue
        wd = w.model_dump()
        price = wd.get('price', {})
        val = wd.get('valuation', {}).get('metrics', {})
        fund = wd.get('fundamentals', {}).get('metrics', {})
        print(f"=== {sym} ===")
        print(f"  Price: value={price.get('value')} as_of={price.get('as_of_date')} status={price.get('status')}")
        pe_val = val.get('pe', {})
        pb_val = val.get('pb', {})
        print(f"  Valuation: PE={pe_val.get('value')} ({pe_val.get('status')}) | PB={pb_val.get('value')} ({pb_val.get('status')})")
        eps_ttm = fund.get('eps_ttm', {})
        bvps = fund.get('bvps', {})
        roe = fund.get('roe', {})
        roa = fund.get('roa', {})
        print(f"  Fundamentals: EPS_TTM={eps_ttm.get('value')} | BVPS={bvps.get('value')} | ROE={roe.get('value')}% | ROA={roa.get('value')}%")
finally:
    session.close()

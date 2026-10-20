import asyncio
import sys
from database.connection import SessionLocal
from services.ai.analyst import AIAnalyst

async def main():
    db = SessionLocal()
    analyst = AIAnalyst()
    
    queries = [
        ("giá VCB", None),
        ("VCB thế nào?", None),
        ("vcb", None),
        ("FPT", None),
        ("thị trường hôm nay", None),
        ("chào bạn", None),
        ("bạn là ai", None),
        ("XYZUNKNOWN", None),
    ]
    
    for q, sym in queries:
        try:
            res = await analyst.answer_question(q, session=db, symbol=sym)
            status = res.get('status')
            resolved_sym = res.get('symbol')
            claims_count = len(res.get('claims', []))
            citations_count = len(res.get('citations', []))
            answer_snip = (res.get('answer') or '')[:100].replace('\n', ' ')
            out = f"Query: '{q}' (sym={sym}) -> Status: {status} | Sym: {resolved_sym} | Claims: {claims_count} | Citations: {citations_count}\n   Ans: {answer_snip}...\n"
            sys.stdout.buffer.write(out.encode('utf-8'))
            sys.stdout.buffer.flush()
        except Exception as e:
            out = f"Query: '{q}' (sym={sym}) -> ERROR: {type(e).__name__}: {e}\n"
            sys.stdout.buffer.write(out.encode('utf-8'))
            sys.stdout.buffer.flush()
            
    db.close()

if __name__ == "__main__":
    asyncio.run(main())

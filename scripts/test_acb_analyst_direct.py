import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.connection import SessionLocal
from services.ai.analyst import AIAnalyst

async def main():
    s = SessionLocal()
    try:
        analyst = AIAnalyst()
        ans = await analyst.answer_question(
            "Cho biết định giá P/B và tỷ suất sinh lời ROE của ngân hàng ACB",
            session=s,
            symbol="ACB"
        )
        print("Status:", ans.get("status"))
        print("\nAnswer:\n", ans.get("answer"))
        print("\nClaims:")
        for c in ans.get("claims", []):
            print(f"  [{c.get('claim_type')}] {c.get('text')} -> cites: {c.get('citation_ids')}")
        print("\nTarget Citations:")
        for ci in ans.get("citations", []):
            if ci.get("metric") in ("pb", "roe", "pe"):
                print(f"  [{ci.get('id')}]: {ci.get('metric')} = {ci.get('value')} ({ci.get('source')})")
    finally:
        s.close()

if __name__ == "__main__":
    asyncio.run(main())

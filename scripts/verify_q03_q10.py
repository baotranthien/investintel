import sys
import asyncio
import json
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal
from services.ai.analyst import AIAnalyst
from tests.test_bank_and_commodity_expansion import MockDraftProvider

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    db = SessionLocal()
    try:
        analyst = AIAnalyst(provider=MockDraftProvider())

        print("=" * 80)
        print("DEMONSTRATION: Q03 (MBB vs VCB Banking Comparison)")
        print("=" * 80)
        q03 = "So sánh tăng trưởng tín dụng, NIM và tỷ lệ nợ xấu của MBB và VCB trong 2 quý gần nhất?"
        res_q03 = asyncio.run(analyst.answer_question(q03, session=db, as_of=date(2026, 10, 27)))
        print(f"Status: {res_q03['status']}")
        print(f"Answer:\n{res_q03['answer']}\n")
        print("Structured Data Comparisons:")
        print(json.dumps(res_q03.get("structured_data_summary", {}).get("comparisons", {}), indent=2, ensure_ascii=False))

        print("\n" + "=" * 80)
        print("DEMONSTRATION: Q10 (PLX vs Brent Oil Correlation)")
        print("=" * 80)
        q10 = "PLX có mối tương quan như thế nào với giá dầu Brent thế giới trong quý gần nhất?"
        res_q10 = asyncio.run(analyst.answer_question(q10, session=db, as_of=date(2026, 10, 27)))
        print(f"Status: {res_q10['status']}")
        print(f"Answer:\n{res_q10['answer']}\n")
        print("Substantive Grounded Claims:")
        for c in res_q10["claims"]:
            print(f" - [{c['claim_type']}]: {c['text']} (Citations: {c['citation_ids']})")
        print("\nStructured Data Summary Metrics for PLX & BRENT:")
        symbols_sum = res_q10.get("structured_data_summary", {}).get("symbols", {})
        plx_metrics = symbols_sum.get("PLX", {}).get("metrics", {})
        brent_metrics = symbols_sum.get("BRENT", {}).get("metrics", {})
        print(f" - PLX Close Price: {plx_metrics.get('price', {}).get('value')} VND")
        if "brent_close" in brent_metrics:
            print(f" - Brent Close Price: {brent_metrics['brent_close']['value']} {brent_metrics['brent_close']['unit']}")
        if "pearson_correlation" in plx_metrics:
            print(f" - Python-Calculated Pearson Correlation: {plx_metrics['pearson_correlation']['value']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

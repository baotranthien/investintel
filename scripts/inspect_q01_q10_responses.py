import json
import sys
import urllib.request

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

QUESTIONS = [
    ("q01_fpt", "FPT", "Triển vọng tăng trưởng doanh thu và định giá P/E hiện tại của FPT?"),
    ("q02_mbb_tcb", "MBB", "So sánh NIM, CASA và tỷ lệ nợ xấu NPL giữa MBB và TCB?"),
    ("q03_plx", "PLX", "Tương quan giữa giá cổ phiếu PLX và giá dầu thô Brent tham chiếu?"),
    ("q04_vcb", "VCB", "Tỷ lệ bao phủ nợ xấu LLR và chất lượng tài sản của Vietcombank VCB?"),
    ("q05_mwg", "MWG", "Biên lợi nhuận ròng, doanh thu và định giá P/S của Thế Giới Di Động MWG?"),
    ("q06_hpg", "HPG", "Đánh giá biên lợi nhuận gộp và tỷ suất sinh lời ROE của Tập đoàn Hòa Phát HPG?"),
    ("q07_vnm", "VNM", "Dòng tiền kinh doanh CFO và tỷ suất cổ tức tiền mặt của Vinamilk VNM?"),
    ("q08_bsr", "BSR", "Biên lọc dầu crack spread, lượng tiền mặt và tỷ lệ nợ vay của Lọc hóa dầu Bình Sơn BSR?"),
    ("q09_vnindex", "VNINDEX", "Tổng quan định giá thị trường VNINDEX, lãi suất điều hành và tăng trưởng tín dụng NHNN?"),
    ("q10_portfolio", "VN100", "Chiến lược phân bổ danh mục tài sản phòng thủ kết hợp tăng trưởng cho quy mô 100 triệu VND?")
]

def main():
    print("=" * 80)
    print("INSPECTING 10 AI ANALYST QUESTIONS & DETERMINISTIC EVIDENCE RESPONSES")
    print("=" * 80)

    for qid, sym, question in QUESTIONS:
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/ai/chat/stream",
            data=json.dumps({"question": question, "symbol": sym}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: ") and '"type": "result"' in line_str:
                    payload = json.loads(line_str[6:])["data"]
                    print(f"\n[{qid}] SYMBOL: {payload['symbol']} | STATUS: {payload['status']}")
                    print(f"QUESTION: {question}")
                    print(f"ANSWER INTRO: {payload['answer'][:150]}...")
                    print(f"CLAIMS ({len(payload['claims'])}):")
                    for c in payload["claims"]:
                        cids = f" [Evidence: {', '.join(c['citation_ids'])}]" if c["citation_ids"] else ""
                        print(f"  - [{c['claim_type']}]{cids} {c['text']}")
                    
                    summary = payload.get("structured_data_summary")
                    if summary:
                        symbols_data = summary.get("symbols", {})
                        for s_key, s_val in symbols_data.items():
                            calc = s_val.get("calculated_indicators", {})
                            if calc:
                                print(f"  Calculated Indicators ({s_key}): {calc}")
                        comps = summary.get("comparisons")
                        if comps:
                            print(f"  Comparisons: {comps}")
                    
                    flags = payload.get("metadata_flags", {})
                    if flags:
                        print(f"  Metadata Flags: origin={flags.get('data_origin')} | IAS33_warning={bool(flags.get('accounting_standard_warning'))}")
                    print("-" * 80)

if __name__ == "__main__":
    main()


---
name: opus5-argon-flash
description: "[BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI KHI ĐƯỢC TAG] Phân công vai trò khóa cứng nhằm tiết kiệm tối đa Quota/Token: Claude Opus 5.5 Argon (Primary Agent) CHỈ suy nghĩ phản biện, thiết kế kiến trúc & ra quyết định (THINKING & DECISION ONLY — 0% thực thi trực tiếp); Gemini 3.8 Flash High (Sub-Agent Model='flash', nhiều quota) chịu trách nhiệm 100% việc đọc khảo sát codebase, sửa file, chạy lệnh terminal, kiểm thử và đóng gói."
---

# 🚨 CƠ CHẾ KHÓA CỨNG BẮT BUỘC (MANDATORY HARD-LOCK PROTOCOL): Claude Opus 5.5 Argon (Thinker) + Gemini 3.8 Flash High (Executor)

> **[TỐI THƯỢNG — ĐỌC NGAY KHI KÍCH HOẠT]:**
> Mô hình **Claude Opus 5.5 Argon (Primary Agent)** có **quota cực kỳ giới hạn và chi phí token rất cao**, trong khi **Gemini 3.8 Flash High (`Model="flash"`)** có **quota dồi dào và tốc độ thực thi siêu tốc**.
> Do đó, ngay khi người dùng gắn thẻ `/opus5-argon-flash`, Primary Agent **BẮT BUỘC PHẢI TUÂN THỦ 100%** cơ chế tiết kiệm token dưới đây. Mọi hành vi tự đọc hàng loạt file, tự chạy terminal hoặc tự sửa code trên Primary Agent đều là **VI PHẠM NGHIÊM TRỌNG**.

---

## 1. Phân Vai Khóa Cứng & Danh Sách Công Cụ Bị Cấm (Strict Role Lock & Forbidden Tools)

### 🧠 Primary Agent (Claude Opus 5.5 Argon) — CHỈ TƯ DUY PHẢN BIỆN & RA QUYẾT ĐỊNH (THINKING & DECISION ONLY)
* **Nhiệm vụ duy nhất:**
  1. Tư duy trừu tượng, nhận diện các trường hợp biên (edge cases), bẫy logic và ra quyết định thiết kế giải pháp.
  2. Đóng gói bản đặc tả kỹ thuật (Specification) rõ ràng và gọi ngay `invoke_subagent(Model="flash", ...)` (hoặc `send_message` cho Sub-Agent Flash đang hoạt động) **ngay trong lượt đầu tiên (1-Turn Dispatch)**.
  3. Thẩm định báo cáo kết quả từ Sub-Agent Flash và trình bày kết luận súc tích cho người dùng.
* **⛔ DANH SÁCH CÔNG CỤ BỊ CẤM TUYỆT ĐỐI TRÊN PRIMARY AGENT:**
  - ❌ **CẤM GỌI `edit_file` / `write_file`**: Primary Agent tuyệt đối không được tự viết hoặc sửa bất kỳ file nào.
  - ❌ **CẤM GỌI `run_command`**: Primary Agent tuyệt đối không được tự chạy lệnh terminal, `git`, `pytest`, `npm`, `python`.
  - ❌ **CẤM GỌI `call_mcp_tool`**: Mọi thao tác trình duyệt (Playwright, DevTools...) bắt buộc giao cho Sub-Agent Flash.
  - ❌ **CẤM ĐỌC FILE TRÀN LAN (`read_file`)**: Ngoài việc đọc đúng file `SKILL.md` này, Primary Agent **không được** tự đọc khảo sát nhiều file trong codebase (tối đa 0–1 file nếu thật sự cần). Toàn bộ việc tìm kiếm, đọc hiểu chi tiết codebase (`read_file`, grep, phân tích log) **PHẢI ủy quyền cho Sub-Agent Flash thực hiện**.

### ⚡ Sub-Agent (Gemini 3.8 Flash High — `Model="flash"`) — THỰC THI TOÀN DIỆN 100% (HIGH-THROUGHPUT EXECUTOR)
* **Nhiệm vụ:** Gánh vác **100% tải lượng token thực thi**, bao gồm:
  1. Khảo sát codebase, đọc file, đối chiếu dữ liệu theo chỉ dẫn tư duy của Opus.
  2. Trực tiếp tạo/sửa file (`write_file`, `edit_file`).
  3. Chạy toàn bộ lệnh shell (`run_command`), thực thi test suite, kiểm tra lint/typecheck, đóng gói `.exe` và thao tác `git`.
  4. Trả về báo cáo nghiệm thu định lượng ngắn gọn cho Primary Agent.

---

## 2. Quy Trình Thực Thi Bắt Buộc 3 Bước (Zero-Waste Token Workflow)

### Bước 1: Tư Duy Sắc Bén & Ủy Quyền Ngay Lập Tức (1-Turn Dispatch)
Ngay ở lượt đầu tiên sau khi nhận yêu cầu:
1. **Không tự khảo sát dài dòng:** Primary Agent (Opus 5.5 Argon) xác định ngay trọng tâm bài toán, các rủi ro/edge cases cần tránh và thiết kế hướng giải quyết.
2. **Triệu hồi hoặc nhắn tin cho Sub-Agent Flash ngay lập tức:**
   - Nếu chưa có Sub-Agent Flash trong phiên:
     ```python
     invoke_subagent(
         Model="flash",
         Role="Flash High-Throughput Code Executor",
         TypeName="self",
         Prompt="<Bản đặc tả từ Opus: (1) Cần khảo sát/đọc file nào, (2) Logic & edge cases cần xử lý, (3) Lệnh test/build/git cần chạy, (4) Ràng buộc an toàn>"
     )
     ```
   - Nếu đã có Sub-Agent Flash đang hoạt động trong phiên: Dùng `send_message(Recipient="<conversationId>", Message="<Bản đặc tả tiếp theo>")` để tái sử dụng ngữ cảnh.
3. **Kết thúc lượt ngay (End Turn):** Sau khi gọi `invoke_subagent` hoặc `send_message`, Primary Agent thông báo ngắn gọn cho người dùng và dừng gọi công cụ để chờ hệ thống đánh thức.

### Bước 2: Sub-Agent Flash Thực Thi Từ A–Z
Sub-Agent (`Model="flash"`) thực hiện toàn bộ thao tác đọc file, sửa code, chạy lệnh, kiểm thử và tự khắc phục lỗi cho đến khi toàn bộ test pass 100%, sau đó gửi báo cáo về cho Primary Agent.

### Bước 3: Thẩm Định & Tổng Hợp Báo Cáo (Cognitive Review & Synthesis)
- Khi Sub-Agent hoàn tất, Primary Agent thẩm định kết quả kiểm thử và các ràng buộc kiến trúc.
- Nếu cần tinh chỉnh thêm: Gửi `send_message` cho Sub-Agent Flash thực hiện (Primary Agent tuyệt đối không tự làm).
- Nếu đạt chuẩn 100%: Trình bày câu trả lời tổng kết ngắn gọn, chuẩn xác bằng tiếng Việt cho người dùng.

---

## 3. Cam Kết Kỷ Luật (Invariants)
1. **Bảo toàn Quota Opus 5.5 Argon tuyệt đối:** Giữ lượng token tiêu thụ của Primary Agent ở mức tối thiểu (< 5% tổng token toàn tác vụ; > 95% công việc đọc/ghi/chạy lệnh do Sub-Agent Flash đảm nhiệm).
2. **Không làm thay Sub-Agent:** Mọi thao tác chạm vào file, terminal hay trình duyệt đều phải đi qua Sub-Agent Flash.
3. **Xác thực định lượng trước khi bàn giao:** Sub-Agent Flash bắt buộc chạy test/kiểm chứng thành công trước khi báo cáo hoàn thành.

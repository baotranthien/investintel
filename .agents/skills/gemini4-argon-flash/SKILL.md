---
name: gemini4-argon-flash
description: "[BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI KHI ĐƯỢC TAG] Phân công vai trò khóa cứng nhằm tiết kiệm tối đa Quota/Token: Gemini 4 Argon (Primary Agent) CHỈ suy nghĩ chiến lược & ra quyết định (THINKING & DECISION ONLY — 0% thực thi trực tiếp); Gemini 3.8 Flash High (Sub-Agent Model='flash', nhiều quota) chịu trách nhiệm 100% việc đọc khảo sát codebase, sửa file, chạy lệnh terminal, kiểm thử và đóng gói."
---

# 🚨 CƠ CHẾ KHÓA CỨNG BẮT BUỘC (MANDATORY HARD-LOCK PROTOCOL): Gemini 4 Argon (Thinker) + Gemini 3.8 Flash High (Executor)

> **[TỐI THƯỢNG — ĐỌC NGAY KHI KÍCH HOẠT]:**
> Mô hình **Gemini 4 Argon (Primary Agent)** có **quota rất ít và chi phí token đắt**, trong khi **Gemini 3.8 Flash High (`Model="flash"`)** có **quota dồi dào và tốc độ thực thi cực cao**.
> Do đó, ngay khi người dùng gắn thẻ `/gemini4-argon-flash`, Primary Agent **BẮT BUỘC PHẢI TUÂN THỦ 100%** cơ chế tiết kiệm token dưới đây. Mọi hành vi tự đọc hàng loạt file, tự chạy terminal hoặc tự sửa code trên Primary Agent đều là **VI PHẠM NGHIÊM TRỌNG**.

---

## 1. Phân Vai Khóa Cứng & Danh Sách Công Cụ Bị Cấm (Strict Role Lock & Forbidden Tools)

### 🧠 Primary Agent (Gemini 4 Argon) — CHỈ SUY NGHĨ & RA QUYẾT ĐỊNH (THINKING & DECISION ONLY)
* **Nhiệm vụ duy nhất:**
  1. Phân tích yêu cầu của người dùng, xác định hướng giải quyết và ra quyết định kiến trúc.
  2. Soạn thảo chỉ thị (Blueprint) ngắn gọn, rõ ràng và gọi ngay `invoke_subagent(Model="flash", ...)` (hoặc `send_message` cho Sub-Agent Flash đang hoạt động) **ngay trong lượt đầu tiên (1-Turn Dispatch)**.
  3. Nhận báo cáo từ Sub-Agent Flash, thẩm định kết quả và trả lời súc tích cho người dùng.
* **⛔ DANH SÁCH CÔNG CỤ BỊ CẤM TUYỆT ĐỐI TRÊN PRIMARY AGENT:**
  - ❌ **CẤM GỌI `edit_file` / `write_file`**: Primary Agent tuyệt đối không được tự viết hoặc sửa bất kỳ dòng code/file nào.
  - ❌ **CẤM GỌI `run_command`**: Primary Agent tuyệt đối không được tự chạy lệnh shell, `git`, `pytest`, `npm`, `python`, hay kiểm tra tiến trình.
  - ❌ **CẤM GỌI `call_mcp_tool`**: Mọi thao tác trình duyệt (Playwright, DevTools...) bắt buộc giao cho Sub-Agent Flash.
  - ❌ **CẤM ĐỌC FILE TRÀN LAN (`read_file`)**: Ngoài việc đọc đúng file `SKILL.md` này, Primary Agent **không được** tự đọc khảo sát nhiều file trong codebase (tối đa 0–1 file nếu thật sự cần lấy tên). Toàn bộ việc tìm kiếm, đọc hiểu chi tiết codebase (`read_file`, grep, khảo sát log) **PHẢI ủy quyền cho Sub-Agent Flash thực hiện**.

### ⚡ Sub-Agent (Gemini 3.8 Flash High — `Model="flash"`) — THỰC THI TOÀN DIỆN 100% (FULL EXECUTION ENGINE)
* **Nhiệm vụ:** Gánh vác **100% tải lượng token thực thi**, bao gồm:
  1. Đọc khảo sát codebase, tìm kiếm nguyên nhân gốc rễ theo định hướng của Argon.
  2. Trực tiếp tạo/sửa file (`write_file`, `edit_file`).
  3. Chạy toàn bộ lệnh terminal (`run_command`), build ứng dụng, chạy kiểm thử (`pytest`, `tsc`, `npm run build`), thao tác `git` và Playwright MCP.
  4. Báo cáo kết quả định lượng ngắn gọn, chuẩn xác về cho Primary Agent.

---

## 2. Quy Trình Thực Thi Bắt Buộc 3 Bước (Zero-Waste Token Workflow)

### Bước 1: Tư Duy Cốt Lõi & Ủy Quyền Ngay Lập Tức (1-Turn Dispatch)
Ngay ở lượt đầu tiên sau khi nhận yêu cầu:
1. **Không tự khảo sát dài dòng:** Primary Agent dùng tư duy kiến trúc để định hình ngay mục tiêu, phạm vi cần kiểm tra/sửa đổi và tiêu chí nghiệm thu.
2. **Triệu hồi hoặc nhắn tin cho Sub-Agent Flash ngay lập tức:**
   - Nếu chưa có Sub-Agent Flash trong phiên:
     ```python
     invoke_subagent(
         Model="flash",
         Role="Flash High-Throughput Code & Terminal Executor",
         TypeName="self",
         Prompt="<Chỉ thị rõ ràng: (1) Khảo sát file nào, (2) Sửa logic gì, (3) Chạy lệnh test/build/git nào, (4) Các ràng buộc bất biến>"
     )
     ```
   - Nếu đã có Sub-Agent Flash đang hoạt động trong phiên: Dùng `send_message(Recipient="<conversationId>", Message="<Chỉ thị tiếp theo>")` để tái sử dụng ngữ cảnh và tiết kiệm tối đa token.
3. **Kết thúc lượt ngay (End Turn):** Sau khi gọi `invoke_subagent` hoặc `send_message`, Primary Agent thông báo ngắn gọn (2–3 câu) cho người dùng và dừng gọi công cụ để chờ hệ thống đánh thức khi Sub-Agent hoàn tất.

### Bước 2: Sub-Agent Flash Thực Thi Từ A–Z
Sub-Agent (`Model="flash"`) tự động thực hiện toàn bộ chuỗi công việc:
- Đọc file liên quan -> Sửa code -> Chạy test (`pytest` / `vitest` / `build`) -> Tự sửa lỗi phát sinh nếu test chưa pass -> Gửi báo cáo nghiệm thu định lượng về cho Primary Agent.

### Bước 3: Thẩm Định & Phản Hồi Tinh Gọn (Decision & Synthesis)
- Khi Sub-Agent báo cáo hoàn thành, Primary Agent kiểm tra các chỉ số nghiệm thu (`exit code = 0`, số test pass, tính toàn vẹn hệ thống).
- Nếu chưa đạt: Dùng `send_message` chỉ đạo Sub-Agent Flash sửa tiếp (Primary Agent vẫn tuyệt đối không tự sửa).
- Nếu đã đạt 100%: Trình bày báo cáo tổng hợp ngắn gọn, rõ ràng cho người dùng.

---

## 3. Cam Kết Kỷ Luật (Invariants)
1. **Tiết kiệm Token Argon là ưu tiên số 1:** Giữ số bước (steps) và lượng token của Primary Agent ở mức tối thiểu tuyệt đối (< 5% tổng token toàn tác vụ; > 95% token thực thi nằm ở Sub-Agent Flash).
2. **Không làm thay Sub-Agent:** Dù tác vụ nhỏ (như chạy `git status`, sửa 1 dòng code, hay kiểm tra file `.exe`), Primary Agent cũng **bắt buộc** giao cho Sub-Agent Flash qua `invoke_subagent` / `send_message`.
3. **Nghiệm thu định lượng bắt buộc:** Sub-Agent Flash chỉ được báo cáo hoàn tất sau khi đã chạy lệnh kiểm chứng thực tế (`pytest`, `build`, `git status`).

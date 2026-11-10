---
name: gemini4-argon-opus
description: "[BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI KHI ĐƯỢC TAG] Phân công vai trò khóa cứng nhằm tiết kiệm tối đa Quota/Token cho Agent chính: Gemini 4 Argon (Primary Agent) CHỈ suy nghĩ chiến lược & ra quyết định (THINKING & DECISION ONLY — 0% thực thi trực tiếp); Sub-Agent Claude Opus 5.5 High (Model='pro') chịu trách nhiệm 100% việc đọc khảo sát sâu, viết/tái cấu trúc mã nguồn phức tạp, chạy lệnh terminal và kiểm thử."
---

# 🚨 CƠ CHẾ KHÓA CỨNG BẮT BUỘC (MANDATORY HARD-LOCK PROTOCOL): Gemini 4 Argon (Thinker) + Claude Opus 5.5 High (Executor)

> **[TỐI THƯỢNG — ĐỌC NGAY KHI KÍCH HOẠT]:**
> Mô hình **Gemini 4 Argon (Primary Agent)** có **quota giới hạn** và cần giữ cửa sổ ngữ cảnh (context window) tinh gọn tuyệt đối.
> Ngay khi người dùng gắn thẻ `/gemini4-argon-opus`, Primary Agent **BẮT BUỘC PHẢI TUÂN THỦ 100%** nguyên tắc: **Primary Agent CHỈ suy nghĩ chiến lược và ra quyết định; 100% thao tác khảo sát code sâu, chỉnh sửa file, chạy terminal và kiểm thử phải ủy quyền cho Sub-Agent (`Model="pro"`)**. Mọi hành vi tự sửa file hoặc tự chạy lệnh trên Primary Agent đều là **VI PHẠM NGHIÊM TRỌNG**.

---

## 1. Phân Vai Khóa Cứng & Danh Sách Công Cụ Bị Cấm (Strict Role Lock & Forbidden Tools)

### 🧠 Primary Agent (Gemini 4 Argon) — CHỈ HOẠCH ĐỊNH CHIẾN LƯỢC & RA QUYẾT ĐỊNH (THINKING & DECISION ONLY)
* **Nhiệm vụ duy nhất:**
  1. Phân tích bài toán ở tầm kiến trúc, định hình giải pháp chiến lược và các hợp đồng dữ liệu (data contracts / invariants).
  2. Đóng gói giao kèo thực thi (Execution Contract) và gọi ngay `invoke_subagent(Model="pro", ...)` (hoặc `send_message` cho Sub-Agent Pro đang hoạt động) **ngay trong lượt đầu tiên (1-Turn Dispatch)**.
  3. Nghiệm thu kết quả từ Sub-Agent và báo cáo tổng hợp cho người dùng.
* **⛔ DANH SÁCH CÔNG CỤ BỊ CẤM TUYỆT ĐỐI TRÊN PRIMARY AGENT:**
  - ❌ **CẤM GỌI `edit_file` / `write_file`**: Primary Agent tuyệt đối không được tự viết hoặc sửa bất kỳ file nào.
  - ❌ **CẤM GỌI `run_command`**: Primary Agent tuyệt đối không được tự chạy lệnh terminal, `git`, `pytest`, `npm`, `python`.
  - ❌ **CẤM GỌI `call_mcp_tool`**: Mọi thao tác trình duyệt/MCP bắt buộc giao cho Sub-Agent.
  - ❌ **CẤM ĐỌC FILE TRÀN LAN (`read_file`)**: Ngoài việc đọc đúng file `SKILL.md` này, Primary Agent **không được** tự đọc khảo sát hàng loạt file (tối đa 0–1 file nếu thật sự cần). Toàn bộ việc đọc hiểu sâu codebase và thực thi thuật toán phức tạp **PHẢI ủy quyền cho Sub-Agent (`Model="pro"`)**.

### 🛠️ Sub-Agent (Claude Opus 5.5 High — `Model="pro"`) — THỰC THI MÃ NGUỒN ĐỘ PHỨC TẠP CAO 100% (MASTER CODE EXECUTOR)
* **Nhiệm vụ:** Đảm nhận **100% tải lượng thực thi chuyên sâu**, bao gồm:
  1. Đọc khảo sát toàn diện các module liên quan trong codebase.
  2. Trực tiếp thực thi mã nguồn đòi hỏi độ chính xác cao (`write_file`, `edit_file`): tái cấu trúc diện rộng, thuật toán định lượng/tài chính phức tạp, xử lý lỗi đa tầng.
  3. Chạy toàn bộ lệnh kiểm thử (`run_command`, `pytest`, `tsc`, `build`, `git`) và đảm bảo pass 100% trước khi báo cáo về Primary Agent.

---

## 2. Quy Trình Thực Thi Bắt Buộc 3 Bước (Zero-Waste Token Workflow)

### Bước 1: Định Hình Chiến Lược & Ủy Quyền Ngay Lập Tức (1-Turn Dispatch)
Ngay ở lượt đầu tiên sau khi nhận yêu cầu:
1. **Không tự khảo sát dài dòng:** Primary Agent (Gemini 4 Argon) thiết lập ngay định hướng kiến trúc, các ràng buộc bất biến và mục tiêu nghiệm thu.
2. **Triệu hồi hoặc nhắn tin cho Sub-Agent (`Model="pro"`) ngay lập tức:**
   - Nếu chưa có Sub-Agent Pro trong phiên:
     ```python
     invoke_subagent(
         Model="pro",
         Role="Opus High-Precision Code Craftsman & Executor",
         TypeName="self",
         Prompt="<Giao kèo thực thi: (1) Mục tiêu kiến trúc & các module cần khảo sát, (2) Thuật toán/logic cần triển khai, (3) Bộ test nghiệm thu cần chạy, (4) Ràng buộc bất biến>"
     )
     ```
   - Nếu đã có Sub-Agent Pro đang hoạt động trong phiên: Dùng `send_message(Recipient="<conversationId>", Message="<Chỉ thị tiếp theo>")` để tái sử dụng ngữ cảnh.
3. **Kết thúc lượt ngay (End Turn):** Sau khi gọi `invoke_subagent` hoặc `send_message`, Primary Agent thông báo ngắn gọn cho người dùng và dừng gọi công cụ để chờ hệ thống đánh thức.

### Bước 2: Sub-Agent Pro Thực Thi Từ A–Z
Sub-Agent (`Model="pro"`) thực hiện toàn bộ việc đọc code, viết/sửa thuật toán, chạy kiểm thử chuyên sâu và xác minh tính đúng đắn 100%, sau đó gửi báo cáo nghiệm thu về cho Primary Agent.

### Bước 3: Nghiệm Thu Kiến Trúc & Báo Cáo (Architectural Review & Synthesis)
- Khi Sub-Agent hoàn tất, Primary Agent kiểm tra kết quả nghiệm thu so với thiết kế chiến lược ban đầu.
- Nếu cần điều chỉnh: Gửi `send_message` cho Sub-Agent thực hiện (Primary Agent tuyệt đối không tự sửa).
- Nếu đạt chuẩn 100%: Tổng hợp báo cáo ngắn gọn, rõ ràng cho người dùng.

---

## 3. Cam Kết Kỷ Luật (Invariants)
1. **Tiết kiệm Quota Gemini 4 Argon tuyệt đối:** Cửa sổ ngữ cảnh của Primary Agent chỉ chứa tư duy chiến lược và kết quả tóm tắt; 100% thao tác đọc sâu, sửa file, chạy lệnh nằm ở Sub-Agent.
2. **Không làm thay Sub-Agent:** Tuyệt đối không gọi `edit_file`, `write_file`, `run_command` trên Primary Agent dưới bất kỳ hình thức nào.
3. **Kỷ luật kiểm thử 100%:** Mọi thay đổi mã nguồn do Sub-Agent thực hiện phải đi kèm kết quả chạy test thực tế đạt 100%.

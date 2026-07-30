---
id: SPEC-homekeeper-agent
companions:
  - glossary.md
sources:
  - ../../planning-artifacts/prds/prd-Vibe-2026-06-23/prd.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in `sources:` are for traceability only.

# HomeKeeper Agent

## Why

Chủ nhà tại Việt Nam không thể nhớ hết lịch bảo trì thiết bị và deadline thanh toán hóa đơn định kỳ. Hậu quả là tiền phạt trễ hạn, thiết bị xuống cấp vì thiếu bảo dưỡng, và mất thời gian tìm thợ gấp khi sự cố xảy ra. Không có công cụ nào đủ đơn giản và đủ chủ động để giải quyết vấn đề này qua kênh mà người dùng đã dùng hàng ngày (Telegram). HomeKeeper Agent giải quyết đúng khoảng trống này: nhắc nhở đúng lúc, không cần nhớ.

## Capabilities

- **CAP-1**
  - **intent:** Admin có thể tạo, xem, sửa, và xóa Task bảo trì hoặc hóa đơn định kỳ qua hội thoại Telegram.
  - **success:** Admin tạo một Task mới; Task xuất hiện trong danh sách với ngày Reminder tiếp theo chính xác (due date − 1 ngày). Task bị xóa không còn sinh Reminder.

- **CAP-2**
  - **intent:** Bot tự động gửi Reminder đến Admin và tất cả Member 1 ngày trước hạn (D-1) và đúng ngày hạn (D-0); nếu Task vẫn chưa được xác nhận sau D-0, bot nhắc lại mỗi 1 giờ cho đến khi Admin xử lý. Member nhận Reminder nhưng không thấy nút xác nhận hoặc quản lý.
  - **success:** Mọi Task đến hạn đều nhận được Reminder D-1 và D-0 (verifiable bằng time-mock trong test). Task quá hạn nhận ít nhất một tin nhắn ⚠️ mỗi giờ; chuỗi nhắc lại dừng ngay khi Admin xác nhận hoặc bỏ qua.

- **CAP-3**
  - **intent:** Admin xác nhận hoàn thành hoặc bỏ qua một Task; bot lưu log (chỉ khi hoàn thành) và tự đặt ngày hạn tiếp theo dựa trên ngày hạn gốc, không phải ngày thao tác.
  - **success:** Sau khi Admin xác nhận hoàn thành, Task tiếp theo xuất hiện trong danh sách với ngày hạn chính xác và log có timestamp. Sau khi Admin bỏ qua, Task tiếp theo được lên lịch nhưng không có log hoàn thành.

- **CAP-4**
  - **intent:** Admin hoặc Member báo cáo Incident đột xuất bằng mô tả tự do; bot trả về danh sách Repairman phù hợp theo loại dịch vụ từ directory đã lưu.
  - **success:** Sau khi người dùng xác nhận muốn tìm thợ, bot trả về ít nhất một Repairman phù hợp (nếu có trong directory) trong vòng 30 giây. Nếu không có Repairman phù hợp, bot thông báo rõ.

- **CAP-5**
  - **intent:** Admin có thể thêm, sửa, xóa Repairman trong directory và quản lý danh sách Member bằng Telegram user ID.
  - **success:** Repairman được thêm xuất hiện trong gợi ý khi Incident khớp loại dịch vụ. Member được thêm nhận Reminder từ thời điểm đó trở đi; Member bị xóa không còn nhận Reminder.

## Constraints

- **HITL tuyệt đối:** Bot không được liên hệ bất kỳ bên ngoài nào hoặc thực hiện hành động ngoài hội thoại mà không có xác nhận tường minh từ người dùng. Đây là nguyên tắc thiết kế, không phải giới hạn kỹ thuật.
- **Telegram only:** Toàn bộ tương tác diễn ra qua Telegram. Không có web dashboard, không có mobile app riêng.
- **Single Admin:** Mỗi bot instance có đúng một Admin, xác định bằng Telegram user ID. Repairman directory chỉ do Admin quản lý — không tích hợp tìm kiếm bên ngoài.
- **SDD:** Mỗi behavior flow phải có acceptance criteria viết sẵn trước khi implement. Hành vi chưa có spec không được deploy.
- **Giới hạn tần suất nhắc:** Hourly overdue Reminder áp dụng khi quá hạn — không tối ưu tổng số tin nhắn; mục tiêu là không bỏ lỡ, không phải tối đa hóa notifications.

## Non-goals

- Tích hợp smart home device (IoT, Google Home, Apple HomeKit)
- Tự động đặt lịch hoặc liên hệ Repairman thay người dùng
- Tự động thanh toán hóa đơn
- Web dashboard hoặc mobile app riêng
- Quản lý nhiều bất động sản (v2+)
- AI chẩn đoán sự cố hoặc gợi ý Repairman từ internet

## Success signal

Admin sử dụng bot ít nhất 4 tuần liên tiếp mà không có Task nào bị bỏ lỡ trong danh sách đã nhập. Khi có Incident, gợi ý Repairman xuất hiện trong vòng 30 giây. Không có lần nào bot thực hiện hành động bên ngoài mà không có xác nhận của Admin.

## Assumptions

- SQLite cho local persistence; không cần cloud DB trong v1 (đã xác nhận với user).
- Reminder gửi lúc 08:00 giờ Việt Nam (UTC+7); tùy chỉnh per-Task defer sang v1.1 (đã xác nhận).
- Member enrollment: Admin đăng ký Telegram user ID của thành viên gia đình qua lệnh bot (chưa xác nhận flow cụ thể).
- Repairman service-type matching dùng keyword match trên trường text tự do; không dùng LLM, không có enum validation.
- Admin ID được cấu hình qua biến môi trường hoặc hardcode khi deploy (chưa xác nhận cơ chế cụ thể).

## Open Questions

- **OQ-A1:** Admin ID setup — hardcode, env var, hay first-run setup wizard qua Telegram?
- **OQ-A3:** Member enrollment flow — Admin nhập Telegram user ID bằng lệnh gì? Có confirmation step không?

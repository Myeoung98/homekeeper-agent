# Glossary — HomeKeeper Agent

Downstream skills và implementers dùng đúng các thuật ngữ dưới đây. Không dùng từ đồng nghĩa ở bất kỳ đâu trong codebase, tests, hoặc tài liệu.

| Term | Definition |
|------|------------|
| **Admin** | Người dùng Telegram duy nhất có toàn quyền quản lý: tạo/sửa/xóa Task, quản lý Repairman directory, và kiểm soát danh sách Member. Xác thực bằng Telegram user ID. |
| **Member** | Thành viên gia đình được Admin thêm vào bot. Nhận Reminder và có thể báo Incident; không thể quản lý Task, Repairman, hoặc Member khác. |
| **Task** | Một hạng mục bảo trì hoặc thanh toán định kỳ. Gồm: tên, Cycle, ngày đến hạn tiếp theo. |
| **Cycle** | Chu kỳ lặp lại của một Task. Ví dụ: 1 tháng, 3 tháng, 6 tháng. Dùng để tính ngày hạn tiếp theo sau khi xác nhận hoàn thành. |
| **Reminder** | Tin nhắn Telegram bot gửi tự động khi Task sắp đến hạn hoặc đã quá hạn. Ba loại: D-1 (trước 1 ngày), D-0 (đúng ngày hạn), Overdue (mỗi 1 giờ sau D-0 cho đến khi xác nhận). |
| **Incident** | Sự cố đột xuất ngoài lịch Task định kỳ. Do Admin hoặc Member báo cáo qua bot bằng mô tả tự do. |
| **Repairman** | Liên lạc dịch vụ sửa chữa do Admin nhập tay vào directory. Gồm: tên, số điện thoại, loại dịch vụ (text tự do). |
| **HITL** | Human-in-the-Loop: nguyên tắc thiết kế cốt lõi — bot không thực hiện hành động quan trọng nào mà không có xác nhận tường minh từ người dùng. |
| **SDD** | Spec-Driven Development: acceptance criteria cho mỗi behavior flow được viết trước khi implement. |

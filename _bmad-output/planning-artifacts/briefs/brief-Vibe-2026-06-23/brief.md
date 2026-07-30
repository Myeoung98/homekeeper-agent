---
title: "HomeKeeper Agent — Smart Home Maintenance & Reminder Bot"
status: draft
created: 2026-06-23
updated: 2026-06-23
---

# Product Brief: HomeKeeper Agent

## Executive Summary

HomeKeeper là một Telegram bot được hỗ trợ bởi AI agent, giúp chủ nhà không bao giờ bỏ lỡ lịch bảo trì định kỳ và hóa đơn dịch vụ định kỳ. Thay vì dựa vào trí nhớ hay ghi chú rải rác, người dùng chỉ cần nhập lịch một lần — agent lo phần còn lại, nhắc nhở đúng ngày qua Telegram.

Vấn đề không phải là thiếu thông tin mà là thiếu nhắc nhở đúng lúc. Chủ nhà biết lọc nước cần thay mỗi 6 tháng, biết tiền điện đóng ngày 15 — nhưng giữa bao nhiêu việc, những thứ đó trôi qua. HomeKeeper giải quyết đúng một vấn đề này: tự động nhắc, không cần nhớ.

Phiên bản đầu phục vụ chủ nhà và gia đình trong cùng một mái nhà. Điểm mạnh: được xây bởi chính người dùng, cho nhu cầu thực — không có giả định.

## Vấn đề

Chủ nhà phải theo dõi nhiều lịch định kỳ cùng lúc: bảo trì thiết bị (lọc nước, điều hòa), thanh toán hóa đơn (điện, nước, internet, phí chung cư), và xử lý sự cố đột xuất khi thiết bị hỏng. Không có công cụ nào đủ đơn giản và đủ chủ động để nhắc nhở những việc này.

Giải pháp hiện tại thường là: ghi chú điện thoại (bị bỏ qua), calendar (phải tự tạo từng event), nhắn tin nhóm gia đình (không hệ thống). Hậu quả là tiền phạt trễ hạn, thiết bị xuống cấp vì không bảo dưỡng đúng hạn, hoặc phải mất thời gian tìm thợ gấp khi sự cố xảy ra.

## Giải Pháp

HomeKeeper là Telegram bot nhận lịch từ người dùng một lần, sau đó tự động nhắc đúng ngày qua tin nhắn. Không cần mở app, không cần nhớ — bot tìm đến người dùng, không phải ngược lại.

Hai luồng chính:

**Nhắc nhở định kỳ:** Người dùng nhập danh sách (tên việc, chu kỳ, ngày bắt đầu). Bot tính toán ngày tiếp theo và gửi nhắc nhở khi đến hạn. Ví dụ: "Đã đến lịch thay lõi lọc nước (6 tháng). Đánh dấu đã xong không?" Sau khi người dùng xác nhận, bot tự cập nhật lịch cho chu kỳ tiếp theo.

**Xử lý sự cố đột xuất:** Người dùng báo cáo qua bot ("điều hòa phòng ngủ bị hỏng"). Bot hỏi thêm thông tin cần thiết, sau đó gợi ý danh sách thợ từ danh bạ người dùng đã nhập sẵn. Quyết định liên hệ ai luôn thuộc về người dùng — bot không tự đặt lịch.

## Người Dùng

**Người dùng chính:** Chủ nhà cá nhân tại Việt Nam, tự quản lý nhà, không có trợ lý hay property manager. Quen dùng Telegram hàng ngày. Không muốn học app mới. Vấn đề không phải thiếu kỷ luật — mà là quá nhiều thứ cần nhớ.

**Người dùng phụ (v1):** Các thành viên gia đình cùng nhà — dùng chung bot, cùng thấy lịch và nhận nhắc nhở.

## Điểm Khác Biệt

Sự khác biệt không nằm ở tính năng mà ở thiết kế hành vi:

- **HITL từ gốc rễ:** Agent không bao giờ hành động thay người dùng mà không có xác nhận. Đây không phải giới hạn — đây là nguyên tắc thiết kế.
- **Spec-Driven Development:** Hành vi agent được viết thành kịch bản (specs) trước khi code. Mỗi flow có acceptance criteria rõ ràng, tránh agent tự ý làm những việc ngoài ý muốn.
- **Đủ đơn giản để thực sự dùng:** Không tích hợp IoT, không dashboard phức tạp. Telegram là giao diện duy nhất — người dùng đã ở đó rồi.
- **Khoảng trống thị trường:** Tại Việt Nam chưa có giải pháp tương tự nhắm vào chủ nhà cá nhân qua Telegram.

## Tiêu Chí Thành Công

- Bot gửi nhắc nhở đúng ngày, không cần người dùng làm gì
- Người dùng không bỏ lỡ bất kỳ lịch nào đã nhập trong 3 tháng đầu dùng
- Khi có sự cố, người dùng nhận được gợi ý thợ trong vòng 1-2 phút sau khi báo cáo
- Không xảy ra trường hợp agent thực hiện hành động quan trọng mà không có xác nhận của người dùng

## Phạm Vi V1

**Trong phạm vi:**
- Nhập và lưu lịch định kỳ qua hội thoại Telegram
- Gửi nhắc nhở tự động đúng ngày/giờ
- Xác nhận hoàn thành và tự động tính chu kỳ tiếp theo
- Nhận báo cáo sự cố đột xuất và gợi ý thợ
- Quản lý danh sách thợ do người dùng nhập tay
- Chia sẻ bot cho nhiều thành viên trong gia đình

**Ngoài phạm vi:**
- Tích hợp thiết bị smart home (IoT sensors, Google Home, HomeKit)
- Tự động đặt lịch hoặc liên hệ thợ thay người dùng
- Dashboard web hoặc mobile app riêng
- Thanh toán hóa đơn tự động

## Vision

Nếu v1 hoạt động tốt, bước mở rộng tự nhiên là hỗ trợ chủ nhà quản lý nhiều bất động sản cho thuê. Về dài hạn, HomeKeeper có thể thành "trợ lý quản lý tài sản cá nhân" — theo dõi chi phí, lịch sử sửa chữa, và thông tin bảo hành thiết bị.

Nhưng v1 không cố gắng làm tất cả. Nó làm đúng một việc: nhắc nhở đúng lúc.

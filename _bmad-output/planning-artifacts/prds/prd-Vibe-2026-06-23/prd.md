---
title: "HomeKeeper Agent — PRD v1"
status: final
created: 2026-06-23
updated: 2026-06-23
---

# PRD: HomeKeeper Agent

## 0. Mục Đích Tài Liệu

PRD này phục vụ người xây dựng (Admin), làm tài liệu định hướng phát triển v1 của HomeKeeper Agent — một Telegram bot nhắc nhở bảo trì nhà và hóa đơn định kỳ. Từ vựng được chuẩn hóa tại §3 Glossary; FRs đánh số toàn cục (FR-1..N); các giả định được gắn tag `[ASSUMPTION]` và lập chỉ mục tại §9.

Brief nguồn: `_bmad-output/planning-artifacts/briefs/brief-Vibe-2026-06-23/brief.md`

---

## 1. Vision

HomeKeeper Agent là một Telegram bot chạy nền, nhắc nhở chủ nhà và các thành viên gia đình về lịch bảo trì định kỳ và hóa đơn dịch vụ — mà không đòi hỏi người dùng phải nhớ bất cứ điều gì sau khi đã thiết lập ban đầu.

Nguyên tắc thiết kế cốt lõi: **bot đề xuất, người dùng quyết định**. Mọi hành động có ảnh hưởng ra bên ngoài (liên hệ thợ, đặt lịch) đều thuộc về người dùng. Bot không bao giờ hành động thay khi chưa có xác nhận — đây không phải giới hạn kỹ thuật mà là lựa chọn thiết kế chủ đích (HITL).

Hành vi bot được định nghĩa bằng SDD (Spec-Driven Development): mỗi flow có acceptance criteria tường minh trước khi code, tránh bot tự ý làm ngoài ý muốn.

---

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional:** Không bỏ lỡ lịch bảo trì thiết bị hoặc deadline thanh toán hóa đơn mà không cần chủ động nhớ
- **Functional:** Biết ngay cần gọi thợ nào khi có sự cố, không mất thời gian tìm kiếm
- **Emotional:** Cảm giác "có người lo" cho ngôi nhà — bớt lo âu nền về việc bỏ sót
- **Contextual:** Dùng được ngay trong Telegram mà không cần học app mới

### 2.2 Non-Users (v1)

- Người thuê nhà (không quản lý thiết bị)
- Người quản lý nhiều bất động sản (scope v2+)
- Người không dùng Telegram

### 2.3 Key User Journeys

**UJ-1. Ton thiết lập lịch bảo trì lần đầu.**
Ton nhắn `/add` cho bot, bot hỏi lần lượt: tên việc, chu kỳ, ngày đến hạn tiếp theo. Ton nhập "Thay lõi lọc nước / 6 tháng / 15/07/2026". Bot xác nhận và lưu. Từ đây Ton không cần làm gì thêm.

**UJ-2. Bot nhắc Ton thay lõi lọc nước.**
Ngày 14/07 (trước 1 ngày), bot gửi: "Ngày mai (15/07) đến lịch **Thay lõi lọc nước**. Bạn đã chuẩn bị chưa?" Ngày 15/07, bot nhắc lại: "Hôm nay đến lịch **Thay lõi lọc nước**. Đánh dấu hoàn thành không?" Ton bấm "✅ Xong" — bot lưu log và tự lên lịch Reminder tiếp theo vào 15/01/2027.

**UJ-3. Điều hòa hỏng đột xuất.**
Ton nhắn "Điều hòa phòng ngủ bị hỏng". Bot hỏi: "Bạn cần tìm thợ điện lạnh không?" Ton bấm "Có". Bot trả về danh sách thợ đã lưu theo loại "Điện lạnh" với tên và số điện thoại. Ton tự gọi. Bot không liên hệ thợ thay Ton.

---

## 3. Glossary

- **Admin** — Người dùng Telegram duy nhất có quyền tạo/sửa/xóa Task, Cycle, và danh sách Repairman. Xác thực bằng Telegram user ID.
- **Member** — Thành viên gia đình được Admin thêm vào bot. Nhận Reminder và có thể báo Incident; không thể quản lý Task.
- **Task** — Một hạng mục bảo trì hoặc thanh toán định kỳ, gồm: tên, Cycle, ngày đến hạn tiếp theo.
- **Cycle** — Chu kỳ lặp lại của một Task (ví dụ: hàng tháng, 3 tháng, 6 tháng).
- **Reminder** — Tin nhắn Telegram bot gửi tự động khi Task sắp đến hạn.
- **Incident** — Sự cố đột xuất ngoài lịch định kỳ, do Admin hoặc Member báo cáo qua bot.
- **Repairman** — Liên lạc dịch vụ sửa chữa do Admin nhập tay, gồm: tên, số điện thoại, loại dịch vụ.
- **HITL** — Human-in-the-Loop: nguyên tắc bot không thực hiện hành động quan trọng nếu chưa có xác nhận tường minh từ người dùng.
- **SDD** — Spec-Driven Development: viết acceptance criteria cho từng behavior trước khi implement.

---

## 4. Features

### 4.1 Quản Lý Task (Admin)

**Description:** Admin tạo, xem, sửa, xóa Task qua hội thoại Telegram. Bot dẫn dắt qua từng bước thu thập thông tin. Realizes UJ-1.

**Functional Requirements:**

#### FR-1: Tạo Task mới
Admin có thể tạo Task mới bằng cách cung cấp tên, Cycle, và ngày đến hạn tiếp theo qua hội thoại bot.

**Consequences:**
- Task được lưu và xuất hiện trong danh sách khi Admin xem (`/list`)
- Bot xác nhận Task đã tạo và hiển thị ngày Reminder tiếp theo (hạn − 1 ngày)
- Task chưa có tên hoặc Cycle → bot từ chối lưu và yêu cầu bổ sung

#### FR-2: Xem danh sách Task
Admin có thể xem toàn bộ Task hiện có, bao gồm tên, ngày đến hạn tiếp theo, và trạng thái (chờ / quá hạn).

**Consequences:**
- Danh sách được sort theo ngày đến hạn tăng dần
- Task quá hạn được đánh dấu rõ ràng

#### FR-3: Sửa và xóa Task
Admin có thể sửa thông tin Task hoặc xóa Task.

**Consequences:**
- Sửa Cycle → bot tính lại ngày Reminder tiếp theo dựa trên ngày hạn đã lưu
- Xóa Task → Task không còn xuất hiện trong danh sách và không sinh Reminder

#### FR-4: Quản lý danh sách Repairman
Admin có thể thêm, sửa, xóa Repairman với tên, số điện thoại, và loại dịch vụ.

**Consequences:**
- Repairman xuất hiện trong gợi ý khi xử lý Incident cùng loại dịch vụ
- [ASSUMPTION: A-5] Loại dịch vụ là text tự do (ví dụ: "Điện lạnh", "Nước"), không có danh sách cố định

---

### 4.2 Reminder Engine

**Description:** Bot tự động gửi Reminder 1 ngày trước hạn và đúng ngày hạn. Sau khi Admin xác nhận hoàn thành, bot tự tính chu kỳ tiếp theo. Realizes UJ-2.

**Functional Requirements:**

#### FR-5: Gửi advance Reminder (D-1)
Bot gửi Reminder đến Admin và tất cả Member 1 ngày trước ngày đến hạn của Task.

**Consequences:**
- Reminder bao gồm: tên Task, ngày đến hạn, và nút "✅ Xác nhận đã chuẩn bị"
- [ASSUMPTION: A-4] Reminder gửi lúc 8:00 sáng giờ Việt Nam

#### FR-6: Gửi Reminder đúng ngày hạn (D-0)
Bot gửi Reminder lần hai vào đúng ngày đến hạn.

**Consequences:**
- Reminder bao gồm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
- Nếu Admin đã xác nhận ở D-1, bot vẫn gửi D-0 nhưng hiển thị trạng thái đã chuẩn bị

#### FR-7: Xác nhận hoàn thành và tự động reschedule
Admin xác nhận Task hoàn thành → bot lưu log và tính ngày đến hạn tiếp theo theo Cycle.

**Consequences:**
- Log hoàn thành lưu kèm timestamp
- Ngày hạn mới = ngày hạn cũ + Cycle (không phải ngày xác nhận + Cycle)
- Nếu chọn "Bỏ qua lần này", bot reschedule nhưng không ghi log hoàn thành

#### FR-7b: Nhắc lại Task quá hạn
Task đã đến hạn nhưng chưa được xác nhận hoàn thành → bot gửi Reminder nhắc lại mỗi 1 tiếng cho đến khi Admin xác nhận.

**Consequences:**
- Nhắc lại gửi đến Admin và tất cả Member
- Tin nhắn nhắc lại đánh dấu rõ "⚠️ Quá hạn" kèm số giờ đã trễ
- Dừng nhắc lại ngay khi Admin xác nhận hoàn thành hoặc bỏ qua

#### FR-8: Gửi Reminder đến Member
Member nhận Reminder của tất cả Task, không có quyền xác nhận hoàn thành hoặc quản lý Task.

**Consequences:**
- [ASSUMPTION: A-3] Member được thêm bằng cách Admin đăng ký Telegram user ID của họ
- Member không thấy các nút quản lý trong tin nhắn Reminder

---

### 4.3 Incident Reporting & Repairman Suggestion

**Description:** Admin hoặc Member báo cáo Incident đột xuất. Bot hỏi loại dịch vụ cần và gợi ý Repairman phù hợp từ danh sách đã lưu. Realizes UJ-3. **HITL tuyệt đối:** bot không liên hệ thợ thay người dùng.

**Functional Requirements:**

#### FR-9: Báo cáo Incident
Admin và Member đều có thể báo cáo Incident bằng mô tả tự do qua bot.

**Consequences:**
- Bot ghi nhận Incident và hỏi xác nhận: "Bạn cần tìm thợ sửa không?"
- Incident được lưu log với timestamp và mô tả

#### FR-10: Gợi ý Repairman theo loại dịch vụ
Bot gợi ý Repairman phù hợp từ danh sách đã lưu dựa trên loại dịch vụ của Incident.

**Consequences:**
- Bot trả về tên, số điện thoại, và loại dịch vụ của Repairman phù hợp
- Nếu không có Repairman nào phù hợp, bot thông báo rõ và gợi ý Admin thêm vào danh sách
- [ASSUMPTION: A-6] Bot match loại dịch vụ bằng keyword đơn giản, không dùng LLM cho bước này

#### FR-11: HITL — Không tự liên hệ thợ
Bot không được tự gọi điện, nhắn tin, hoặc đặt lịch với bất kỳ Repairman nào dưới bất kỳ hình thức nào.

**Consequences:**
- Bot chỉ hiển thị thông tin liên lạc để người dùng tự liên hệ
- Không có tính năng "gọi ngay" hay "nhắn tin qua bot"

---

### 4.4 Access Control

**Description:** Hai vai trò: Admin (toàn quyền) và Member (chỉ nhận và báo cáo). Xác thực bằng Telegram user ID.

**Functional Requirements:**

#### FR-12: Phân quyền Admin
Chỉ Admin (xác định bằng Telegram user ID cấu hình lúc khởi tạo) mới có thể tạo/sửa/xóa Task và Repairman.

**Consequences:**
- Mọi lệnh quản lý từ user ID không phải Admin → bot từ chối và không thực hiện
- [ASSUMPTION: A-1] Admin ID được hardcode hoặc cấu hình qua biến môi trường lúc deploy

#### FR-13: Thêm Member
Admin có thể thêm Telegram user ID của thành viên gia đình để họ nhận Reminder.

**Consequences:**
- Member được thêm → nhận tất cả Reminder từ thời điểm đó trở đi
- Admin có thể xóa Member khỏi danh sách bất cứ lúc nào

---

## 5. Non-Goals (Explicit)

- Tích hợp smart home device (IoT sensors, Google Home, Apple HomeKit)
- Tự động đặt lịch hoặc liên hệ Repairman thay người dùng
- Web dashboard hoặc mobile app riêng
- Tự động thanh toán hóa đơn
- Quản lý nhiều bất động sản (v2+)
- Gợi ý Repairman từ internet / Google Maps (danh sách hoàn toàn do Admin nhập)
- AI tự phân tích mô tả Incident để chẩn đoán sự cố

---

## 6. MVP Scope

### 6.1 In Scope

- Tạo, xem, sửa, xóa Task qua hội thoại Telegram
- Reminder tự động D-1 và D-0
- Xác nhận hoàn thành + auto-reschedule
- Incident reporting + Repairman suggestion
- Quản lý danh sách Repairman (nhập tay)
- Phân quyền Admin / Member theo Telegram user ID
- Multi-member: Admin thêm thành viên gia đình nhận Reminder

### 6.2 Out of Scope for MVP

- Thống kê / lịch sử bảo trì chi tiết (v2)
- Xuất báo cáo PDF/Excel (v2)
- Nhắc nhở theo giờ tùy chỉnh per-Task (hiện tại: fixed 8:00 sáng) `[NOTE FOR PM: có thể là quick win ở v1.1]`
- Member xác nhận hoàn thành Task (hiện tại: Admin only)
- Bot tự động đề xuất Cycle dựa trên loại thiết bị

---

## 7. Success Metrics

**Primary**
- **SM-1:** Zero missed Reminder cho mọi Task đã nhập trong 90 ngày đầu. Validates FR-5, FR-6.
- **SM-2:** Admin vẫn dùng bot sau 4 tuần (retention). Validates tổng thể v1.

**Secondary**
- **SM-3:** Khi có Incident, Admin nhận gợi ý Repairman trong ≤ 30 giây. Validates FR-10.
- **SM-4:** Không có lần nào bot thực hiện hành động bên ngoài mà không có xác nhận. Validates FR-11, FR-12.

**Counter-metrics (không tối ưu)**
- **SM-C1:** Tổng số tin nhắn bot gửi — không tối ưu số lượng; quá nhiều = spam gây tắt bot. Counterbalances SM-1.

---

## 8. Assumptions Index

**Đã xác nhận:**
- **[A-2]** Data lưu trong SQLite; không cần cloud DB cho v1 (§4.2)
- **[A-4]** Reminder gửi lúc 8:00 sáng giờ Việt Nam (UTC+7); tùy chỉnh per-Task defer v1.1 (§FR-5)

**Còn là giả định — cần xác nhận khi implement:**
- **[A-1]** Admin Telegram user ID được hardcode hoặc cấu hình qua biến môi trường khi deploy (§FR-12)
- **[A-3]** Member được thêm bằng cách Admin đăng ký Telegram user ID của họ qua lệnh bot (§FR-8, FR-13)
- **[A-5]** Loại dịch vụ Repairman là text tự do, không có danh sách enum cố định (§FR-4)
- **[A-6]** Bot match Repairman bằng keyword đơn giản trên trường loại dịch vụ, không dùng LLM (§FR-10)

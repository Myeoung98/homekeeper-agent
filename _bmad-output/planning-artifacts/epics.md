---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - planning-artifacts/prds/prd-Vibe-2026-06-23/prd.md
  - planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md
  - specs/spec-homekeeper-agent/SPEC.md
---

# HomeKeeper Agent - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for HomeKeeper Agent, decomposing the requirements from the PRD, Architecture, and SPEC into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: Admin có thể tạo Task mới bằng cách cung cấp tên, Cycle, và ngày đến hạn tiếp theo qua hội thoại bot. Task được lưu và bot xác nhận ngày Reminder tiếp theo (hạn − 1 ngày). Task thiếu tên hoặc Cycle → bot từ chối lưu.
FR-2: Admin có thể xem toàn bộ Task hiện có, bao gồm tên, ngày đến hạn, trạng thái (chờ / quá hạn). Danh sách sort theo ngày đến hạn tăng dần; Task quá hạn được đánh dấu rõ.
FR-3: Admin có thể sửa thông tin Task hoặc xóa Task. Sửa Cycle → bot tính lại ngày Reminder. Xóa Task → không còn sinh Reminder.
FR-4: Admin có thể thêm, sửa, xóa Repairman với tên, số điện thoại, và loại dịch vụ (text tự do).
FR-5: Bot gửi Reminder đến Admin và tất cả Member 1 ngày trước ngày đến hạn của Task lúc 8:00 sáng giờ Việt Nam (UTC+7).
FR-6: Bot gửi Reminder lần hai vào đúng ngày đến hạn lúc 8:00 sáng. Reminder bao gồm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này".
FR-7: Admin xác nhận Task hoàn thành → bot lưu log kèm timestamp và tính ngày hạn tiếp theo = ngày hạn cũ + Cycle.
FR-7b: Task đã đến hạn nhưng chưa xác nhận → bot gửi Reminder nhắc lại mỗi 1 giờ với dấu ⚠️ Quá hạn. Dừng khi Admin xác nhận hoặc bỏ qua.
FR-8: Member nhận Reminder của tất cả Task nhưng không thấy nút xác nhận hoặc nút quản lý.
FR-9: Admin và Member đều có thể báo cáo Incident bằng mô tả tự do. Bot ghi nhận và hỏi: "Bạn cần tìm thợ sửa không?" Incident được lưu log với timestamp.
FR-10: Bot gợi ý Repairman phù hợp từ danh sách đã lưu dựa trên loại dịch vụ (keyword match). Nếu không có Repairman phù hợp, bot thông báo rõ.
FR-11: Bot không được tự gọi điện, nhắn tin, hoặc đặt lịch với bất kỳ Repairman nào. Chỉ hiển thị thông tin liên lạc.
FR-12: Chỉ Admin (xác định bằng Telegram user ID từ env var) mới có thể tạo/sửa/xóa Task và Repairman. Lệnh từ user ID không phải Admin → bot từ chối.
FR-13: Admin có thể thêm Telegram user ID của thành viên gia đình để họ nhận Reminder. Admin có thể xóa Member.

### NonFunctional Requirements

NFR-1: Khi có Incident, người dùng nhận được gợi ý Repairman trong ≤ 30 giây sau khi xác nhận muốn tìm thợ.
NFR-2: Không bỏ lỡ bất kỳ Reminder nào cho Task đã nhập trong 90 ngày đầu sử dụng.
NFR-3: Không có lần nào bot thực hiện hành động bên ngoài mà không có xác nhận tường minh từ người dùng (HITL absolute).
NFR-4: Bot tiếp tục hoạt động bình thường sau khi khởi động lại; các Reminder bị bỏ lỡ khi máy tắt được gửi bù khi khởi động lại.
NFR-5: Admin và Member ID được đọc từ environment variables, không hardcode trong code.

### Additional Requirements

- **Stack:** Python ≥ 3.12, python-telegram-bot (PTB) ≥ 21.0, SQLite (bundled)
- **Module structure:** `bot/` | `scheduler/` | `db/` | `domain/` — downward-only imports (AD-1)
- **Threading:** PTB event loop và scheduler loop chạy trong hai thread riêng; giao tiếp chỉ qua SQLite, không share in-memory state (AD-2)
- **SQLite WAL mode:** `PRAGMA journal_mode=WAL` khi khởi động; mỗi thread giữ một connection riêng (AD-5)
- **Polling mode:** không cần public server; bot chạy bằng polling trên máy cá nhân
- **Catch-up on restart:** khi khởi động, `scheduler/catchup.py` query `REMINDER_LOG` để tìm Task quá hạn chưa được nhắc, gửi bù ngay (AD-6)
- **No outbound integration:** codebase không có HTTP client hay external API call — HITL được enforce bằng cấu trúc (AD-4)
- **Single writer rule:** chỉ `bot/reminder_callbacks.py` được ghi `TASK.next_due_date`; scheduler là read-only trên TASK (AD-8)
- **Config via env vars:** `ADMIN_USER_ID`, `DB_PATH` đọc từ `.env` khi khởi động
- **Schema:** 5 bảng: TASK, MEMBER, REPAIRMAN, REMINDER_LOG, INCIDENT

### UX Design Requirements

N/A — HomeKeeper Agent là Telegram bot, toàn bộ UI là Telegram messages và inline keyboards. Không có web/mobile UI riêng.

### FR Coverage Map

FR-1: Epic 1 — Tạo Task mới qua hội thoại bot
FR-2: Epic 1 — Xem danh sách Task
FR-3: Epic 1 — Sửa và xóa Task
FR-4: Epic 3 — Quản lý Repairman directory
FR-5: Epic 2 — Gửi D-1 Reminder lúc 8:00am
FR-6: Epic 2 — Gửi D-0 Reminder lúc 8:00am
FR-7: Epic 2 — Xác nhận hoàn thành + auto-reschedule
FR-7b: Epic 2 — Overdue hourly re-notification
FR-8: Epic 4 — Member nhận Reminder không có nút quản lý
FR-9: Epic 3 — Báo cáo Incident bằng mô tả tự do
FR-10: Epic 3 — Gợi ý Repairman theo loại dịch vụ
FR-11: Epic 3 — HITL: không tự liên hệ thợ
FR-12: Epic 1 — Admin auth bằng Telegram user ID
FR-13: Epic 4 — Admin thêm/xóa Member

## Epic List

### Epic 1: Task Management & Bot Foundation
Admin có thể khởi động bot an toàn và quản lý toàn bộ danh sách công việc bảo trì định kỳ.
**FRs covered:** FR-1, FR-2, FR-3, FR-12

### Epic 2: Automatic Reminder Engine
Bot tự động nhắc Admin đúng giờ, xử lý xác nhận hoàn thành, nhắc lại khi quá hạn, và gửi bù khi khởi động lại.
**FRs covered:** FR-5, FR-6, FR-7, FR-7b

### Epic 3: Incident Reporting & Repairman Finder
Admin và Member có thể báo cáo sự cố và nhận gợi ý thợ sửa từ danh bạ đã lưu, với HITL tuyệt đối.
**FRs covered:** FR-4, FR-9, FR-10, FR-11

### Epic 4: Family Sharing
Admin có thể thêm thành viên gia đình vào bot để họ cùng nhận nhắc nhở.
**FRs covered:** FR-8, FR-13

---

## Epic 1: Task Management & Bot Foundation

Admin có thể khởi động bot an toàn và quản lý toàn bộ danh sách công việc bảo trì định kỳ.

### Story 1.1: Bot Foundation & Admin Auth

As a Admin,
I want a running Telegram bot that recognizes me as the authorized admin,
So that I can securely manage my home maintenance tasks without others interfering.

**Acceptance Criteria:**

**Given** `ADMIN_USER_ID` và `DB_PATH` được set trong file `.env`
**When** Admin chạy `python main.py`
**Then** Bot khởi động, kết nối Telegram thành công, `db/schema.sql` được chạy để tạo tất cả 5 bảng (TASK, MEMBER, REPAIRMAN, REMINDER_LOG, INCIDENT) nếu chưa tồn tại, `PRAGMA journal_mode=WAL` được bật
**And** Bot log "HomeKeeper Agent started" ra console

**Given** Admin gửi bất kỳ tin nhắn hoặc lệnh nào cho bot
**When** Telegram user ID của Admin khớp với `ADMIN_USER_ID`
**Then** Bot xử lý lệnh bình thường và phản hồi

**Given** Một user khác (không phải Admin) gửi lệnh cho bot
**When** Telegram user ID không khớp với `ADMIN_USER_ID`
**Then** Bot trả về: "Bạn không có quyền sử dụng bot này." và không thực hiện lệnh

**Given** `ADMIN_USER_ID` không được set trong `.env`
**When** Bot khởi động
**Then** Bot log lỗi rõ ràng và dừng lại, không chạy với config thiếu

---

### Story 1.2: Add Maintenance Task

As a Admin,
I want to add a recurring maintenance task through a step-by-step conversation,
So that the bot knows what to remind me about and when.

**Acceptance Criteria:**

**Given** Admin gửi `/add`
**When** Bot nhận lệnh
**Then** Bot hỏi: "Tên công việc là gì? (ví dụ: Thay lõi lọc nước)"

**Given** Admin nhập tên công việc
**When** Bot nhận tên (không rỗng)
**Then** Bot hỏi: "Chu kỳ lặp lại? (ví dụ: 30 ngày, 90 ngày, 180 ngày)"

**Given** Admin nhập chu kỳ hợp lệ (số nguyên dương + đơn vị ngày)
**When** Bot nhận Cycle
**Then** Bot hỏi: "Ngày đến hạn tiếp theo? (định dạng DD/MM/YYYY)"

**Given** Admin nhập ngày hợp lệ
**When** Bot nhận ngày đến hạn
**Then** Bot lưu Task vào SQLite và xác nhận: "✅ Đã thêm: **[tên]** — đến hạn [ngày], nhắc trước 1 ngày vào [ngày−1]."

**Given** Admin bỏ trống tên hoặc nhập Cycle = 0
**When** Bot validate
**Then** Bot báo lỗi cụ thể và yêu cầu nhập lại, không lưu Task

**Given** Admin gửi `/cancel` trong bất kỳ bước nào của conversation
**When** Bot nhận `/cancel`
**Then** Bot hủy flow và trả về: "Đã hủy. Task không được lưu."

---

### Story 1.3: View Task List

As a Admin,
I want to see all my scheduled tasks sorted by due date,
So that I know what's coming up and what's overdue.

**Acceptance Criteria:**

**Given** Admin gửi `/list`
**When** Có ít nhất một Task trong database
**Then** Bot trả về danh sách tất cả Task, sort theo `next_due_date` tăng dần, mỗi Task hiển thị: tên, ngày đến hạn, số ngày còn lại (hoặc số ngày đã trễ)

**Given** Có Task với `next_due_date` < ngày hôm nay
**When** Admin xem `/list`
**Then** Task đó được đánh dấu ⚠️ Quá hạn và hiển thị số ngày đã trễ

**Given** Admin gửi `/list`
**When** Không có Task nào trong database
**Then** Bot trả về: "Chưa có công việc nào. Dùng /add để thêm."

---

### Story 1.4: Edit & Delete Task

As a Admin,
I want to edit or delete an existing task,
So that I can keep my schedule accurate when things change.

**Acceptance Criteria:**

**Given** Admin gửi `/edit`
**When** Có Task trong database
**Then** Bot hiển thị danh sách Task có đánh số và hỏi: "Chọn số thứ tự Task muốn sửa:"

**Given** Admin chọn một Task hợp lệ
**When** Bot hiển thị form sửa
**Then** Admin có thể sửa tên, Cycle, hoặc ngày đến hạn. Trường nào bỏ trống = giữ nguyên giá trị cũ.

**Given** Admin thay đổi Cycle của Task
**When** Lưu thay đổi
**Then** Bot tính lại ngày Reminder tiếp theo = ngày hạn hiện tại − 1 ngày (không tính lại từ Cycle mới)

**Given** Admin gửi `/delete`
**When** Admin chọn Task và xác nhận "Có"
**Then** Task bị xóa khỏi database và không còn sinh Reminder
**And** Bot xác nhận: "✅ Đã xóa: **[tên Task]**"

**Given** Admin chọn `/delete` nhưng trả lời "Không" khi được hỏi xác nhận
**When** Bot nhận "Không"
**Then** Task không bị xóa và Bot thông báo: "Đã hủy xóa."

---

## Epic 2: Automatic Reminder Engine

Bot tự động nhắc Admin đúng giờ, xử lý xác nhận hoàn thành, nhắc lại khi quá hạn, và gửi bù khi khởi động lại.

### Story 2.1: Scheduler Infrastructure

As a Admin,
I want the bot to continuously check for upcoming tasks in the background,
So that reminders fire automatically without me doing anything after initial setup.

**Acceptance Criteria:**

**Given** Admin chạy `python main.py`
**When** Bot khởi động
**Then** Scheduler thread được khởi động song song với PTB event loop; hai thread không chia sẻ biến in-memory nào — giao tiếp chỉ qua SQLite (AD-2)

**Given** Scheduler thread đang chạy
**When** Mỗi 60 giây
**Then** Scheduler query tất cả Task từ DB, kiểm tra xem Task nào đến hạn cần gửi Reminder, và ghi log tick ở level DEBUG

**Given** Scheduler đọc một Task để gửi Reminder
**When** Scheduler chuẩn bị ghi vào REMINDER_LOG
**Then** Scheduler re-reads row Task từ DB để xác nhận `next_due_date` chưa thay đổi kể từ khi nó quyết định gửi; nếu đã thay đổi, bỏ qua tick này cho Task đó (AD-8)

**Given** Bot đang chạy và SQLite được mở
**When** Cả PTB thread và Scheduler thread đều ghi DB đồng thời
**Then** Không xảy ra lỗi `SQLITE_BUSY`; mỗi thread giữ connection riêng, WAL mode đã bật (AD-5)

---

### Story 2.2: D-1 Reminder Delivery

As a Admin,
I want to receive a reminder message the day before a task is due,
So that I have time to prepare or arrange for the maintenance.

**Acceptance Criteria:**

**Given** Có Task với `next_due_date = T` và chưa có REMINDER_LOG row với `type='D-1'` cho due date này
**When** Scheduler chạy vào buổi sáng ngày T−1 sau 08:00 Vietnam time (UTC+7)
**Then** Bot gửi Reminder đến Admin: "🔔 Nhắc nhở: **[tên Task]** đến hạn vào ngày mai ([ngày T])."
**And** Scheduler ghi một row vào REMINDER_LOG: `task_id, type='D-1', sent_at=now`

**Given** Bot đã gửi D-1 Reminder cho Task trong ngày hôm nay
**When** Scheduler chạy các tick tiếp theo trong ngày
**Then** Scheduler không gửi lại D-1 Reminder cho cùng Task và cùng `next_due_date` (idempotent — dựa trên REMINDER_LOG)

**Given** Có ít nhất một Member được đăng ký
**When** D-1 Reminder được gửi
**Then** Cùng nội dung Reminder được gửi đến tất cả Member đang active; không có nút inline keyboard trong tin nhắn gửi cho Member

---

### Story 2.3: D-0 Reminder with Action Buttons

As a Admin,
I want to receive a reminder on the due date with action buttons,
So that I can confirm completion or skip with one tap.

**Acceptance Criteria:**

**Given** Có Task với `next_due_date = T` và chưa có REMINDER_LOG row với `type='D-0'` cho due date này
**When** Scheduler chạy vào buổi sáng ngày T sau 08:00 Vietnam time (UTC+7)
**Then** Bot gửi Reminder đến Admin: "📅 Đến hạn hôm nay: **[tên Task]**" kèm inline keyboard gồm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
**And** Scheduler ghi row vào REMINDER_LOG: `task_id, type='D-0', sent_at=now`

**Given** D-0 Reminder đã được gửi cho Admin
**When** Cùng Task này được gửi D-0 Reminder đến Member
**Then** Tin nhắn gửi cho Member KHÔNG có inline keyboard (FR-8); chỉ Admin thấy nút hành động

**Given** Bot đã gửi D-0 Reminder cho Task trong ngày T
**When** Scheduler chạy các tick tiếp theo trong ngày T (Task chưa được xác nhận)
**Then** Scheduler không gửi thêm D-0 Reminder — chỉ chuyển sang overdue hourly logic nếu đã qua 08:00 ngày T và Task chưa done

---

### Story 2.4: Task Completion & Auto-Reschedule

As a Admin,
I want to confirm a task as done with one tap,
So that the bot automatically schedules the next occurrence without me having to calculate anything.

**Acceptance Criteria:**

**Given** Admin nhận D-0 Reminder với nút "✅ Hoàn thành"
**When** Admin tap nút "✅ Hoàn thành"
**Then** `bot/reminder_callbacks.py` cập nhật REMINDER_LOG row hiện tại với `confirmed_at=now` (AD-8)
**And** `bot/reminder_callbacks.py` ghi `TASK.next_due_date = next_due_date_cũ + cycle_days` (đây là writer duy nhất được phép — AD-8)
**And** Bot reply: "✅ Đã ghi nhận: **[tên Task]** hoàn thành. Hạn tiếp theo: [ngày mới]."

**Given** Admin nhận D-0 Reminder với nút "⏭ Bỏ qua lần này"
**When** Admin tap nút "⏭ Bỏ qua lần này"
**Then** REMINDER_LOG row được đánh dấu `confirmed_at=now` với flag skip
**And** `TASK.next_due_date` được tính lại = `next_due_date_cũ + cycle_days` (bỏ qua lần này, không reset về hôm nay)
**And** Bot reply: "⏭ Đã bỏ qua. Hạn tiếp theo: [ngày mới]."

**Given** Reminder message đã cũ (bot đã restart và gửi lại catch-up)
**When** Admin tap vào nút cũ trên một message cũ
**Then** Bot reply bằng alert hoặc tin nhắn: "Reminder này đã hết hiệu lực. Xem /list để biết trạng thái hiện tại." — không update DB sai

---

### Story 2.5: Overdue Hourly Re-notification & Catch-up on Restart

As a Admin,
I want to be reminded every hour when a task is overdue and receive missed reminders after a restart,
So that nothing falls through the cracks even if I miss the initial reminder or the bot was offline.

**Acceptance Criteria:**

**Given** Task có `next_due_date < hôm nay` và Admin chưa xác nhận (không có `confirmed_at` trong REMINDER_LOG)
**When** Scheduler chạy và đã qua mốc 1 giờ kể từ lần Overdue Reminder gần nhất
**Then** Bot gửi Reminder cho Admin: "⚠️ Quá hạn: **[tên Task]** đã trễ [N] ngày. Bạn đã xử lý chưa?" kèm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
**And** Scheduler ghi row vào REMINDER_LOG: `type='overdue', sent_at=now`

**Given** Admin xác nhận hoặc bỏ qua Task đang overdue
**When** `confirmed_at` được ghi vào REMINDER_LOG
**Then** Scheduler dừng gửi Overdue Reminder cho Task đó

**Given** Bot vừa khởi động lại (sau khi máy tắt)
**When** `scheduler/catchup.py` chạy ngay khi startup
**Then** catchup.py query REMINDER_LOG để tìm Task có `next_due_date ≤ hôm nay` và chưa có Reminder row cho due date đó
**And** Với mỗi Task bị bỏ lỡ, bot gửi ngay một catch-up Reminder với label "⚡ Gửi bù (bot vừa khởi động lại)"
**And** Ghi row vào REMINDER_LOG để đánh dấu đã gửi — các tick tiếp theo không gửi lại

**Given** Task đã được catch-up Reminder gửi trong cùng ngày đến hạn
**When** Scheduler bình thường poll sau đó
**Then** Scheduler không gửi thêm D-1 hoặc D-0 Reminder cho cùng `next_due_date` đó (REMINDER_LOG đã có row)

---

## Epic 3: Incident Reporting & Repairman Finder

Admin và Member có thể báo cáo sự cố và nhận gợi ý thợ sửa từ danh bạ đã lưu, với HITL tuyệt đối.

### Story 3.1: Repairman Directory Management

As a Admin,
I want to maintain a directory of repairmen with their contact details and service types,
So that the bot can suggest the right person when something breaks.

**Acceptance Criteria:**

**Given** Admin gửi `/repairman add`
**When** Bot nhận lệnh
**Then** Bot hỏi tên thợ, sau đó số điện thoại, sau đó loại dịch vụ (text tự do, ví dụ: "điều hòa, điện lạnh")

**Given** Admin hoàn thành nhập 3 trường
**When** Bot lưu Repairman
**Then** Repairman được lưu vào bảng REPAIRMAN và bot xác nhận: "✅ Đã thêm thợ: **[tên]** — [phone] — [service_type]."

**Given** Admin gửi `/repairman list`
**When** Có Repairman trong database
**Then** Bot trả về danh sách tất cả Repairman với tên, số điện thoại, và loại dịch vụ

**Given** Admin gửi `/repairman list`
**When** Không có Repairman nào
**Then** Bot trả về: "Chưa có thợ nào trong danh bạ. Dùng /repairman add để thêm."

**Given** Admin gửi `/repairman edit` hoặc `/repairman delete`
**When** Admin chọn Repairman và sửa/xóa
**Then** Thay đổi được lưu vào DB và bot xác nhận; xóa yêu cầu confirm "Có/Không" trước khi thực hiện

**Given** Một Member (không phải Admin) gửi bất kỳ lệnh `/repairman` nào
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền quản lý danh bạ thợ." (FR-12)

---

### Story 3.2: Incident Reporting

As a Admin or Member,
I want to report a home incident with a free-text description,
So that the issue is logged and I can get help finding a repairman.

**Acceptance Criteria:**

**Given** Admin hoặc Member gửi `/incident`
**When** Bot nhận lệnh từ bất kỳ user đã xác thực (Admin hoặc Member đăng ký)
**Then** Bot hỏi: "Mô tả sự cố: (ví dụ: điều hòa phòng ngủ không mát)"

**Given** User nhập mô tả sự cố
**When** Bot nhận mô tả (không rỗng)
**Then** Bot lưu Incident vào bảng INCIDENT với `reported_by` = Telegram user ID, `description`, `created_at = now`
**And** Bot hỏi: "Bạn có cần tìm thợ sửa không?" với nút inline "Có" và "Không"

**Given** User trả lời "Không"
**When** Bot nhận "Không"
**Then** Bot reply: "✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ." — flow kết thúc

**Given** User nhập mô tả rỗng
**When** Bot validate
**Then** Bot yêu cầu nhập lại, không lưu Incident

**Given** Một Telegram user không phải Admin và không có trong bảng MEMBER gửi `/incident`
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền sử dụng bot này."

---

### Story 3.3: Repairman Suggestion (HITL)

As a Admin or Member,
I want the bot to suggest matching repairmen based on the incident description,
So that I have contact info ready to call — and the bot never contacts anyone on my behalf.

**Acceptance Criteria:**

**Given** User trả lời "Có" khi được hỏi có cần tìm thợ sau khi báo Incident
**When** Bot thực hiện keyword match giữa mô tả sự cố và trường `service_type` của tất cả Repairman trong DB
**Then** Bot trả về danh sách Repairman có service_type khớp (tối thiểu 1 từ khóa chung), hiển thị: tên, số điện thoại, loại dịch vụ
**And** Kết quả xuất hiện trong ≤ 30 giây kể từ khi user xác nhận "Có" (NFR-1)

**Given** Kết quả được trả về
**When** Bot hiển thị danh sách Repairman gợi ý
**Then** Bot KHÔNG có nút "Gọi ngay", KHÔNG tự gọi điện, KHÔNG gửi tin nhắn đến thợ — chỉ hiển thị số điện thoại để user tự liên hệ (FR-11, AD-4)
**And** Bot thêm chú thích: "Liên hệ trực tiếp với thợ theo số điện thoại trên."

**Given** Không có Repairman nào trong DB có service_type khớp với từ khóa trong mô tả
**When** Keyword match trả về rỗng
**Then** Bot trả về: "Không tìm thấy thợ phù hợp trong danh bạ. Bạn có thể thêm thợ bằng /repairman add."

**Given** Danh bạ Repairman hoàn toàn rỗng (chưa nhập thợ nào)
**When** User yêu cầu tìm thợ
**Then** Bot trả về: "Danh bạ thợ đang trống. Admin có thể thêm thợ bằng /repairman add." — không crash, không trả về danh sách rỗng im lặng

---

## Epic 4: Family Sharing

Admin có thể thêm thành viên gia đình vào bot để họ cùng nhận nhắc nhở.

### Story 4.1: Member Management

As a Admin,
I want to add and remove family members by their Telegram user ID,
So that they receive the same reminders and can report incidents without needing separate setup.

**Acceptance Criteria:**

**Given** Admin gửi `/member add`
**When** Bot nhận lệnh
**Then** Bot hỏi: "Nhập Telegram user ID của thành viên: (họ cần nhắn tin cho bot trước để lấy ID)"

**Given** Admin nhập một Telegram user ID hợp lệ (số nguyên)
**When** Bot validate
**Then** Bot hỏi tên hiển thị của Member (tùy chọn, dùng để nhận diện)
**And** Bot lưu Member vào bảng MEMBER với `telegram_user_id` và `name`
**And** Bot xác nhận: "✅ Đã thêm thành viên: **[tên]** (ID: [id])."

**Given** Admin nhập một Telegram user ID đã tồn tại trong bảng MEMBER
**When** Bot kiểm tra DB
**Then** Bot báo: "Thành viên này đã có trong danh sách." và không tạo bản ghi trùng

**Given** Admin gửi `/member list`
**When** Có Member trong database
**Then** Bot trả về danh sách tất cả Member với tên và Telegram user ID

**Given** Admin gửi `/member list`
**When** Không có Member nào
**Then** Bot trả về: "Chưa có thành viên nào. Dùng /member add để thêm."

**Given** Admin gửi `/member remove` và chọn một Member
**When** Admin xác nhận "Có"
**Then** Member bị xóa khỏi bảng MEMBER và không còn nhận Reminder
**And** Bot xác nhận: "✅ Đã xóa thành viên: **[tên]**."

**Given** Một Telegram user không phải Admin gửi bất kỳ lệnh `/member` nào
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền quản lý thành viên." (FR-12)

---

### Story 4.2: Member-Aware Reminder Delivery

As a Member,
I want to receive the same reminders as the admin without seeing management controls,
So that I stay informed about home maintenance without accidentally triggering admin actions.

**Acceptance Criteria:**

**Given** Scheduler gửi D-1 Reminder cho một Task
**When** Có ít nhất một Member trong bảng MEMBER
**Then** Bot gửi cùng nội dung Reminder đến mỗi Member trong danh sách
**And** Tin nhắn gửi cho Member KHÔNG có inline keyboard (không có nút "✅ Hoàn thành" hoặc "⏭ Bỏ qua") (FR-8)

**Given** Scheduler gửi D-0 Reminder cho một Task
**When** Bot gửi đến Admin và các Member
**Then** Admin nhận Reminder kèm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
**And** Mỗi Member nhận cùng nội dung text nhưng không có nút inline keyboard

**Given** Scheduler gửi Overdue Reminder cho một Task
**When** Bot gửi đến Admin và các Member
**Then** Admin nhận ⚠️ Overdue Reminder kèm nút hành động
**And** Mỗi Member nhận thông báo overdue dạng text thuần, không có nút

**Given** Admin xóa một Member khỏi bảng MEMBER
**When** Scheduler gửi Reminder tiếp theo
**Then** Member đã xóa không nhận được Reminder — bot query danh sách Member mỗi lần gửi, không cache

**Given** Bot gửi Reminder đến một Member nhưng Telegram trả về lỗi (ví dụ: user đã block bot)
**When** Lỗi xảy ra
**Then** Bot log lỗi ở level WARNING, tiếp tục gửi đến các Member còn lại và Admin — không crash toàn bộ Reminder batch

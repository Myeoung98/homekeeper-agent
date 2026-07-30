# AI Collaboration Log — HomeKeeper Agent

> Nhật ký làm việc với AI trong quá trình xây dựng HomeKeeper Agent.
> Ghi lại vai trò của AI ở từng giai đoạn: thiết kế, kiến trúc, implementation, debug, và UX.

---

## Tổng quan

| Mục | Giá trị |
|---|---|
| Dự án | HomeKeeper Agent |
| Mô hình AI trong sản phẩm | Groq `llama-3.3-70b-versatile` (NLP) + OpenRouter Vision (phân tích ảnh) |
| AI dùng để build | Claude Sonnet (Claude Code CLI) |
| Phương pháp | Vibe Coding — AI lead, developer steer |
| Tổng commits | 15 commits, từ `58ac64f` đến `dcee60f` |

---

## Giai đoạn 1 — Khởi tạo ý tưởng & kiến trúc

### Prompt dùng để thiết kế hệ thống ban đầu

```
Tôi muốn xây một Telegram bot giúp gia đình quản lý bảo trì nhà —
nhắc nhở vệ sinh máy lạnh, lọc nước, kiểm tra điện. Thiết kế kiến trúc
cho hệ thống này dùng Python, Telegram Bot API, và SQLite.
```

**AI đề xuất:**
- Architecture pattern: single-process với PTB (python-telegram-bot) + scheduler thread
- DB schema: TASK, MEMBER, REPAIRMAN, INCIDENT với household_id để multi-tenant
- Conversation state machine cho `/add`, `/edit`, `/delete` flows
- Separation of concerns: handlers / db / scheduler tách biệt

**Quyết định developer:** Chấp nhận toàn bộ kiến trúc. Thêm requirement: mỗi Telegram group = 1 household độc lập.

---

## Giai đoạn 2 — Thêm AI vào sản phẩm (AI-Native layer)

### 2a. Natural Language Processing

**Vấn đề:** Users không muốn dùng command `/add`, họ muốn nhắn tự nhiên như "nhắc tôi thay lọc nước tháng sau".

**Prompt gửi AI:**
```
Thiết kế intent detection cho Telegram bot quản lý nhà. User có thể nhắn
tự nhiên bằng tiếng Việt. Cần detect: tạo task, hỏi thợ, báo sự cố,
xem danh sách. Dùng LLM để parse intent + extract entities.
```

**AI sinh ra:**
- `homekeeper/bot/ai_handlers.py` — catch-all text handler với Groq
- System prompt với household context injection
- Intent routing: CREATE_TASK / FIND_REPAIRMAN / REPORT_INCIDENT / QUERY_TASKS / GENERAL
- Structured JSON response parsing

**Commit:** `67df192` — *Add Claude AI natural-language features to HomeKeeper bot*

**Adjustment:** AI ban đầu đề xuất dùng Anthropic Claude API. Developer yêu cầu đổi sang Groq vì latency thấp hơn và free tier.

**Commit:** `ebeef0f` — *Switch AI backend from Anthropic to Groq (llama-3.3-70b-versatile)*

---

### 2b. Photo Analysis (Vision AI)

**Vấn đề:** Users muốn chụp ảnh thiết bị hỏng gửi lên, bot tự nhận diện vấn đề.

**Prompt gửi AI:**
```
Xây photo handler cho Telegram bot. User gửi ảnh thiết bị nhà bị hỏng.
Dùng Vision LLM để: nhận diện vấn đề, đánh giá mức độ (thấp/trung/cao),
gợi ý loại thợ cần gọi, suggest task bảo trì liên quan.
```

**AI sinh ra:**
- `homekeeper/bot/photo_handlers.py` — xử lý `Update.message.photo`
- OpenRouter API call với model `qwen/qwen2-vl-72b-instruct`
- Response schema: `{issue, severity, repairman_type, suggested_task}`
- Fallback model list khi primary model fail

**Debug session với AI:**
```
Lỗi: openrouter trả 404 cho model qwen2-vl
AI: model ID đã thay đổi, cần query /api/v1/models để lấy ID thật
```

**AI tự generate script kiểm tra model IDs live từ OpenRouter API, tìm ra model ID đúng.**

**Commit:** `911f752` — *Use correct free vision model IDs from OpenRouter live API*

---

## Giai đoạn 3 — Multi-tenant & Onboarding

**Vấn đề:** Bot đang hardcode 1 household. Cần scale ra nhiều gia đình.

**Prompt:**
```
Thêm multi-tenant support. Mỗi Telegram group chat = 1 household riêng
với dữ liệu hoàn toàn tách biệt. Khi bot được add vào group mới, tự
setup onboarding message.
```

**AI thiết kế:**
- Migration strategy: `ALTER TABLE ... ADD COLUMN household_id` (idempotent)
- `build_onboarding_handler()` — lắng nghe `ChatMemberUpdated` event
- `household_id = update.effective_chat.id` — dùng Telegram chat ID làm tenant ID
- Tất cả queries filter theo `household_id`

**Insight từ AI:** "Dùng chat ID làm tenant key là zero-config — không cần registration flow, không cần database tenant table."

**Commit:** `368fa09` — *Add multi-tenant support, AI photo analysis, and group onboarding*

---

## Giai đoạn 4 — Dashboard & Demo preparation

**Prompt:**
```
Xây web dashboard để demo cho investor. Cần show: health score tổng,
danh sách tasks theo trạng thái, incidents, repairmen. FastAPI + HTML.
Auto-refresh mỗi 30 giây.
```

**AI sinh ra:**
- `homekeeper/dashboard/app.py` — FastAPI app mount vào main process
- `dashboard.html` với inline JavaScript, auto-poll `/api/summary`
- Health score formula: `100 - overdue*8 - incidents*3`
- Color coding: xanh/vàng/đỏ theo score

**Commit:** `911f752` → `eee2fd4` — *Add web dashboard for investor demo*

---

### Demo data seeding

**Prompt:**
```
Tạo auto-seed script cho Railway deploy: khi DB trống, tự tạo 3 households
demo với tasks thật, repairmen thật, incidents có ngày realistic (một số
quá hạn, một số sắp tới, một số tương lai xa).
```

**AI tính toán offset ngày:** tasks quá hạn -5, -12 ngày; tasks hôm nay; tasks +2, +3, +45, +120 ngày — tạo ra dashboard "interesting" thay vì tất cả đều clean.

**Commit:** `95f98e1` — *Auto-seed demo data on fresh deploy when DB is empty*

---

### /demo command

**Prompt:**
```
Tạo /demo command cho investor pitch trong Telegram. Chạy scripted walkthrough
tự động: show platform stats thật, simulate AI photo analysis response,
show NLP demo, multi-tenant pitch, kết thúc bằng CTA.
```

**AI viết toàn bộ `demo_handlers.py`** với animated typing delays, real data từ DB, repairman lookup từ seed data.

**Commit:** `dcee60f` — *Add /demo command for investor demo walkthrough*

---

## AI trong sản phẩm — tóm tắt kỹ thuật

```
User Input (text)
    │
    ▼
Groq llama-3.3-70b-versatile
    │  system prompt: household context + task list + repairmen
    │  → intent: CREATE_TASK / FIND_REPAIRMAN / REPORT_INCIDENT / QUERY
    │  → entities: task_name, cycle_days, service_type, etc.
    ▼
Intent Router → DB write / query / Telegram reply

User Input (photo)
    │
    ▼
OpenRouter Vision (qwen2-vl-72b)
    │  → issue description, severity, repairman_type
    ▼
Match với REPAIRMAN table → suggest thợ phù hợp
```

**AI không phải tính năng thêm vào — AI là interface chính của sản phẩm.** Không có NLP và Vision, bot chỉ là command-line wrapper. Với AI, bot hiểu ý người dùng và kết nối với dữ liệu nhà.

---

## Lessons learned từ vibe coding

| Vấn đề | Cách AI giúp giải quyết |
|---|---|
| PTB conversation state phức tạp | AI generate state machine + handler pattern đúng từ đầu |
| SQLite WAL mode + multi-thread safety | AI nhắc dùng `check_same_thread=True` và connection-per-thread |
| OpenRouter model IDs thay đổi | AI write script tự query live API thay vì hardcode |
| Railway deploy không có `.env` | AI đề xuất `python-dotenv` optional pattern với `load_dotenv()` |
| Telegram group vs private chat routing | AI phát hiện `effective_chat.id` works cho cả hai case |
| Dashboard chạy cùng process với bot | AI đề xuất daemon thread + uvicorn pattern |

---

## Thời gian & effort

Toàn bộ project từ ý tưởng đến deployed trên Railway: **~2 tuần làm việc**.

Ước tính nếu không dùng AI: 6–8 tuần (PTB boilerplate, DB schema, NLP integration, Vision API, dashboard).

**Vibe Coding tăng tốc ~4x** trên project này — không phải vì AI thay thế developer, mà vì AI eliminate toàn bộ boilerplate research và syntax lookup, để developer focus vào business logic và product decisions.

import os
import sqlite3
from datetime import date, datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def _db_path() -> str:
    return os.environ.get("DB_PATH", "homekeeper.db")


def _fetch(query: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _scalar(query: str, params: tuple = (), default=0):
    conn = sqlite3.connect(_db_path())
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else default


def _stats() -> dict:
    today = date.today().isoformat()
    month_start = datetime.now().strftime("%Y-%m")
    return {
        "households": _scalar("SELECT COUNT(DISTINCT household_id) FROM TASK WHERE household_id != 0"),
        "total_tasks": _scalar("SELECT COUNT(*) FROM TASK"),
        "overdue_tasks": _scalar("SELECT COUNT(*) FROM TASK WHERE next_due_date < ?", (today,)),
        "due_today": _scalar("SELECT COUNT(*) FROM TASK WHERE next_due_date = ?", (today,)),
        "repairmen": _scalar("SELECT COUNT(*) FROM REPAIRMAN"),
        "members": _scalar("SELECT COUNT(*) FROM MEMBER"),
        "incidents": _scalar("SELECT COUNT(*) FROM INCIDENT"),
        "incidents_this_month": _scalar("SELECT COUNT(*) FROM INCIDENT WHERE created_at >= ?", (month_start,)),
    }


def _health_score(stats: dict) -> int:
    total = stats["total_tasks"]
    if total == 0:
        return 100
    overdue = stats["overdue_tasks"]
    incidents_month = stats["incidents_this_month"]
    score = 100 - min(overdue * 8, 40) - min(incidents_month * 3, 20)
    return max(0, score)


def _task_chart() -> tuple[int, int, int]:
    today = date.today().isoformat()
    overdue = _scalar("SELECT COUNT(*) FROM TASK WHERE next_due_date < ?", (today,))
    due_soon = _scalar(
        "SELECT COUNT(*) FROM TASK WHERE next_due_date BETWEEN ? AND date(?, '+7 days')",
        (today, today),
    )
    healthy = max(0, _scalar("SELECT COUNT(*) FROM TASK") - overdue - due_soon)
    return overdue, due_soon, healthy


def _household_breakdown() -> list[dict]:
    today = date.today().isoformat()
    hids = _fetch("SELECT DISTINCT household_id FROM TASK WHERE household_id != 0 ORDER BY household_id")
    result = []
    names = {1001: "Gia đình Nguyễn", 1002: "Gia đình Trần", 1003: "Văn phòng Demo"}
    icons = {1001: "🏠", 1002: "🏡", 1003: "🏢"}
    for row in hids:
        hid = row["household_id"]
        tasks = _scalar("SELECT COUNT(*) FROM TASK WHERE household_id=?", (hid,))
        overdue = _scalar("SELECT COUNT(*) FROM TASK WHERE household_id=? AND next_due_date < ?", (hid, today))
        incidents = _scalar("SELECT COUNT(*) FROM INCIDENT WHERE household_id=?", (hid,))
        repairmen = _scalar("SELECT COUNT(*) FROM REPAIRMAN WHERE household_id=?", (hid,))
        score = max(0, 100 - overdue * 8 - incidents * 3)
        result.append({
            "id": hid,
            "name": names.get(hid, f"Hộ #{hid}"),
            "icon": icons.get(hid, "🏠"),
            "tasks": tasks, "overdue": overdue,
            "incidents": incidents, "repairmen": repairmen,
            "score": score,
        })
    return result


def _recent_tasks(limit: int = 8) -> list[dict]:
    return _fetch("SELECT * FROM TASK ORDER BY next_due_date ASC LIMIT ?", (limit,))


def _recent_incidents(limit: int = 5) -> list[dict]:
    return _fetch("SELECT * FROM INCIDENT ORDER BY created_at DESC LIMIT ?", (limit,))


def _repairmen(limit: int = 8) -> list[dict]:
    return _fetch("SELECT * FROM REPAIRMAN ORDER BY service_type, id LIMIT ?", (limit,))


def _due_badge(due_date_str: str) -> str:
    try:
        due = date.fromisoformat(due_date_str)
        diff = (due - date.today()).days
        if diff < 0:
            return f'<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30">Quá hạn {-diff}n</span>'
        if diff == 0:
            return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">Hôm nay</span>'
        if diff <= 7:
            return f'<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">{diff} ngày</span>'
        return f'<span class="px-2 py-0.5 rounded-full text-xs bg-slate-700 text-slate-400">{diff} ngày</span>'
    except (ValueError, TypeError):
        return ""


def _score_color(score: int) -> str:
    if score >= 80: return "#22c55e"
    if score >= 60: return "#eab308"
    if score >= 40: return "#f97316"
    return "#ef4444"


def _score_label(score: int) -> str:
    if score >= 80: return "Tốt"
    if score >= 60: return "Trung bình"
    if score >= 40: return "Cần chú ý"
    return "Nguy hiểm"


def _render_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return '<p class="text-slate-500 text-sm text-center py-6">Chưa có công việc nào</p>'
    rows = []
    for t in tasks:
        badge = _due_badge(t.get("next_due_date", ""))
        rows.append(
            f'<div class="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-slate-700/50 transition-colors">'
            f'<div class="flex items-center gap-2 flex-1 min-w-0">'
            f'<span class="text-slate-500 text-xs">🔧</span>'
            f'<span class="text-sm text-slate-200 truncate">{t["name"]}</span>'
            f'</div>'
            f'<div class="shrink-0 ml-2">{badge}</div>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_incidents(incidents: list[dict]) -> str:
    if not incidents:
        return '<p class="text-slate-500 text-sm text-center py-6">Không có sự cố</p>'
    rows = []
    icons = ["🚨", "⚡", "💧", "🌡️", "🔑"]
    for i, inc in enumerate(incidents):
        ts = (inc.get("created_at") or "")[:10]
        desc = (inc.get("description") or "")[:55]
        icon = icons[i % len(icons)]
        rows.append(
            f'<div class="flex gap-3 py-2.5 px-3 rounded-lg hover:bg-slate-700/50 transition-colors">'
            f'<span class="text-lg shrink-0 mt-0.5">{icon}</span>'
            f'<div class="flex-1 min-w-0">'
            f'<p class="text-sm text-slate-200 truncate">{desc}{"…" if len(inc.get("description",""))>55 else ""}</p>'
            f'<p class="text-xs text-slate-500 mt-0.5">{ts}</p>'
            f'</div>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_repairmen(repairmen: list[dict]) -> str:
    if not repairmen:
        return '<p class="text-slate-500 text-sm text-center py-6">Chưa có thợ</p>'
    service_icons = {"điện": "⚡", "nước": "💧", "máy lạnh": "❄️", "sơn": "🎨", "mộc": "🪚", "khóa": "🔑"}
    rows = []
    for r in repairmen:
        icon = service_icons.get(r["service_type"].lower(), "🔧")
        rows.append(
            f'<div class="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-slate-700/50 transition-colors">'
            f'<div class="flex items-center gap-2">'
            f'<span class="text-lg">{icon}</span>'
            f'<div>'
            f'<p class="text-sm font-medium text-slate-200">{r["name"]}</p>'
            f'<p class="text-xs text-slate-500">{r["service_type"]}</p>'
            f'</div>'
            f'</div>'
            f'<span class="text-sky-400 text-xs font-mono">{r["phone"]}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_households(households: list[dict]) -> str:
    if not households:
        return ""
    cards = []
    for h in households:
        sc = h["score"]
        col = _score_color(sc)
        lbl = _score_label(sc)
        overdue_badge = (
            f'<span class="text-xs text-red-400">{h["overdue"]} quá hạn</span>'
            if h["overdue"] > 0 else
            '<span class="text-xs text-emerald-400">Tất cả đúng hạn</span>'
        )
        cards.append(
            f'<div class="card p-4 flex flex-col gap-3">'
            f'<div class="flex items-center justify-between">'
            f'<div class="flex items-center gap-2">'
            f'<span class="text-2xl">{h["icon"]}</span>'
            f'<div>'
            f'<p class="font-semibold text-white text-sm">{h["name"]}</p>'
            f'<p class="text-xs text-slate-500">ID #{h["id"]}</p>'
            f'</div>'
            f'</div>'
            f'<div class="text-right">'
            f'<p class="text-2xl font-bold" style="color:{col}">{sc}</p>'
            f'<p class="text-xs" style="color:{col}">{lbl}</p>'
            f'</div>'
            f'</div>'
            f'<div class="grid grid-cols-3 gap-2 text-center">'
            f'<div class="bg-slate-800 rounded-lg py-2">'
            f'<p class="text-lg font-bold text-sky-400">{h["tasks"]}</p>'
            f'<p class="text-xs text-slate-500">Tasks</p>'
            f'</div>'
            f'<div class="bg-slate-800 rounded-lg py-2">'
            f'<p class="text-lg font-bold text-amber-400">{h["incidents"]}</p>'
            f'<p class="text-xs text-slate-500">Sự cố</p>'
            f'</div>'
            f'<div class="bg-slate-800 rounded-lg py-2">'
            f'<p class="text-lg font-bold text-emerald-400">{h["repairmen"]}</p>'
            f'<p class="text-xs text-slate-500">Thợ</p>'
            f'</div>'
            f'</div>'
            f'<div class="flex items-center justify-between">'
            f'<div class="flex-1 bg-slate-800 rounded-full h-1.5 mr-3">'
            f'<div class="h-1.5 rounded-full transition-all" style="width:{sc}%;background:{col}"></div>'
            f'</div>'
            f'{overdue_badge}'
            f'</div>'
            f'</div>'
        )
    return "\n".join(cards)


_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>HomeKeeper Agent — Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  body {{ background:#0a0f1e; color:#e2e8f0; font-family:'Inter',sans-serif; }}
  .card {{ background:#111827; border:1px solid #1f2937; border-radius:16px; }}
  .card-glow {{ background:#111827; border:1px solid #1f2937; border-radius:16px;
                box-shadow:0 0 0 1px rgba(99,102,241,0.1), 0 4px 24px rgba(0,0,0,0.4); }}
  .gradient-border {{ background:linear-gradient(#111827,#111827) padding-box,
                      linear-gradient(135deg,#6366f1,#06b6d4) border-box;
                      border:1px solid transparent; border-radius:16px; }}
  .kpi-card {{ background:linear-gradient(135deg,#111827 0%,#0f172a 100%);
               border:1px solid #1f2937; border-radius:16px;
               transition:transform .2s,box-shadow .2s; }}
  .kpi-card:hover {{ transform:translateY(-2px); box-shadow:0 8px 32px rgba(0,0,0,0.4); }}
  .score-ring {{ transform:rotate(-90deg); transform-origin:center; }}
  .ai-badge {{ background:linear-gradient(135deg,#4f46e5,#0ea5e9);
               padding:2px 10px; border-radius:999px; font-size:11px;
               font-weight:600; letter-spacing:.5px; }}
  ::-webkit-scrollbar {{ width:4px; }}
  ::-webkit-scrollbar-thumb {{ background:#374151; border-radius:4px; }}
  .scrollable {{ max-height:280px; overflow-y:auto; }}
  @keyframes countUp {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .count-up {{ animation:countUp .6s ease forwards; }}
  @keyframes pulse-dot {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.4; }} }}
  .pulse-dot {{ animation:pulse-dot 2s infinite; }}
</style>
<meta http-equiv="refresh" content="30"/>
</head>
<body class="min-h-screen p-5">

<!-- Header -->
<div class="flex items-center justify-between mb-6">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-xl">🏠</div>
    <div>
      <h1 class="text-xl font-bold text-white leading-tight">HomeKeeper Agent</h1>
      <p class="text-slate-500 text-xs">AI-Powered Home Maintenance Platform</p>
    </div>
  </div>
  <div class="flex items-center gap-3">
    <span class="ai-badge text-white">✨ AI-Powered</span>
    <div class="flex items-center gap-2 px-3 py-1.5 card text-xs text-slate-400">
      <span class="pulse-dot w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
      Live · 30s refresh
    </div>
  </div>
</div>

<!-- Health Score + KPI row -->
<div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">

  <!-- Health Score -->
  <div class="gradient-border p-4 flex items-center gap-4 md:col-span-1">
    <div class="relative w-16 h-16 shrink-0">
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="26" fill="none" stroke="#1f2937" stroke-width="6"/>
        <circle cx="32" cy="32" r="26" fill="none" stroke="{score_color}" stroke-width="6"
          stroke-dasharray="{score_dash} 163.4" stroke-linecap="round" class="score-ring"
          style="transition:stroke-dasharray 1s ease"/>
      </svg>
      <div class="absolute inset-0 flex items-center justify-center">
        <span class="text-sm font-bold" style="color:{score_color}">{score}</span>
      </div>
    </div>
    <div>
      <p class="text-xs text-slate-500 uppercase tracking-wider">Health Score</p>
      <p class="font-bold text-white">{score_label}</p>
      <p class="text-xs text-slate-500 mt-0.5">Toàn bộ hệ thống</p>
    </div>
  </div>

  <!-- KPI cards -->
  <div class="kpi-card p-4">
    <p class="text-slate-500 text-xs uppercase tracking-wider mb-1">Hộ gia đình</p>
    <p class="text-3xl font-bold text-white count-up">{households}</p>
    <p class="text-slate-600 text-xs mt-1">Multi-tenant ↑</p>
  </div>
  <div class="kpi-card p-4">
    <p class="text-slate-500 text-xs uppercase tracking-wider mb-1">Công việc</p>
    <p class="text-3xl font-bold text-sky-400 count-up">{total_tasks}</p>
    <p class="text-{overdue_color}-400 text-xs mt-1">{overdue_tasks} quá hạn · {due_today} hôm nay</p>
  </div>
  <div class="kpi-card p-4">
    <p class="text-slate-500 text-xs uppercase tracking-wider mb-1">Thợ sửa chữa</p>
    <p class="text-3xl font-bold text-emerald-400 count-up">{repairmen}</p>
    <p class="text-slate-500 text-xs mt-1">{members} thành viên</p>
  </div>
  <div class="kpi-card p-4">
    <p class="text-slate-500 text-xs uppercase tracking-wider mb-1">Sự cố tháng này</p>
    <p class="text-3xl font-bold text-amber-400 count-up">{incidents_this_month}</p>
    <p class="text-slate-500 text-xs mt-1">{incidents} tổng · AI phân tích 📸</p>
  </div>
</div>

<!-- Household Cards -->
<div class="mb-5">
  <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
    <span>🏘️</span> Breakdown theo hộ gia đình
  </h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    {household_cards}
  </div>
</div>

<!-- Middle row: chart + tasks -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">

  <div class="card p-5">
    <h2 class="text-sm font-semibold text-white mb-4 flex items-center gap-2">
      <span>📊</span> Tình trạng bảo trì
    </h2>
    <div class="flex justify-center mb-3">
      <canvas id="taskChart" width="160" height="160"></canvas>
    </div>
    <div class="grid grid-cols-3 gap-2 text-center text-xs">
      <div><span class="text-red-400 font-bold text-base">{overdue}</span><br/><span class="text-slate-500">Quá hạn</span></div>
      <div><span class="text-yellow-400 font-bold text-base">{due_soon}</span><br/><span class="text-slate-500">Sắp đến</span></div>
      <div><span class="text-emerald-400 font-bold text-base">{healthy}</span><br/><span class="text-slate-500">Ổn định</span></div>
    </div>
  </div>

  <div class="card p-5 md:col-span-2">
    <h2 class="text-sm font-semibold text-white mb-3 flex items-center gap-2">
      <span>📋</span> Lịch bảo trì sắp tới
      <span class="ml-auto text-xs text-slate-500 font-normal">Sắp xếp theo ngày</span>
    </h2>
    <div class="scrollable">
      {task_rows}
    </div>
  </div>

</div>

<!-- Bottom row: incidents + repairmen -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">

  <div class="card p-5">
    <h2 class="text-sm font-semibold text-white mb-3 flex items-center gap-2">
      <span>🚨</span> Sự cố gần đây
      <span class="ml-auto ai-badge text-white">AI nhận dạng 📸</span>
    </h2>
    <div class="scrollable">
      {incident_rows}
    </div>
  </div>

  <div class="card p-5">
    <h2 class="text-sm font-semibold text-white mb-3 flex items-center gap-2">
      <span>🔧</span> Danh bạ thợ
      <span class="ml-auto text-xs text-slate-500 font-normal">AI gợi ý tự động</span>
    </h2>
    <div class="scrollable">
      {repairman_rows}
    </div>
  </div>

</div>

<!-- AI Features Banner -->
<div class="card-glow p-5 mb-5">
  <h2 class="text-sm font-semibold text-white mb-4 flex items-center gap-2">
    <span>🤖</span> Tính năng AI
  </h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <div class="bg-slate-800/50 rounded-xl p-4 border border-indigo-500/20">
      <div class="text-2xl mb-2">📸</div>
      <p class="font-semibold text-white text-sm">Phân tích ảnh AI</p>
      <p class="text-slate-400 text-xs mt-1">Gửi ảnh hỏng hóc → AI nhận diện vấn đề, mức độ, gợi ý thợ phù hợp trong vài giây</p>
      <div class="mt-3 flex items-center gap-1.5 text-xs text-indigo-400">
        <span>✦</span> OpenRouter Vision
      </div>
    </div>
    <div class="bg-slate-800/50 rounded-xl p-4 border border-cyan-500/20">
      <div class="text-2xl mb-2">💬</div>
      <p class="font-semibold text-white text-sm">Ngôn ngữ tự nhiên</p>
      <p class="text-slate-400 text-xs mt-1">"Nhắc tôi vệ sinh máy lạnh sau 30 ngày" → tự tạo task, set reminder tự động</p>
      <div class="mt-3 flex items-center gap-1.5 text-xs text-cyan-400">
        <span>✦</span> Groq llama-3.3-70b
      </div>
    </div>
    <div class="bg-slate-800/50 rounded-xl p-4 border border-emerald-500/20">
      <div class="text-2xl mb-2">👥</div>
      <p class="font-semibold text-white text-sm">Multi-tenant</p>
      <p class="text-slate-400 text-xs mt-1">Mỗi group Telegram = 1 hộ gia đình riêng biệt. Scale không giới hạn, không cài app</p>
      <div class="mt-3 flex items-center gap-1.5 text-xs text-emerald-400">
        <span>✦</span> Telegram Bot API
      </div>
    </div>
  </div>
</div>

<!-- Footer -->
<div class="text-center text-slate-700 text-xs">
  HomeKeeper Agent &middot; Built with Python · FastAPI · Telegram Bot API · Groq · OpenRouter &middot; Deployed on Railway
</div>

<script>
new Chart(document.getElementById('taskChart').getContext('2d'), {{
  type: 'doughnut',
  data: {{
    datasets: [{{
      data: [{overdue}, {due_soon}, {healthy}],
      backgroundColor: ['#ef4444','#eab308','#22c55e'],
      borderWidth: 0, hoverOffset: 4,
      borderRadius: 4,
    }}]
  }},
  options: {{
    cutout: '72%',
    plugins: {{ legend: {{ display: false }} }},
    animation: {{ animateRotate: true, duration: 800 }}
  }}
}});
</script>
</body>
</html>"""


def create_app() -> FastAPI:
    app = FastAPI(title="HomeKeeper Dashboard", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        stats = _stats()
        overdue, due_soon, healthy = _task_chart()
        score = _health_score(stats)
        score_color = _score_color(score)
        score_label = _score_label(score)
        score_dash = round(score / 100 * 163.4, 1)
        households = _household_breakdown()
        tasks = _recent_tasks()
        incidents = _recent_incidents()
        repairmen = _repairmen()
        overdue_color = "red" if stats["overdue_tasks"] > 0 else "slate"

        html = _HTML.format(
            score=score, score_color=score_color,
            score_label=score_label, score_dash=score_dash,
            households=stats["households"],
            total_tasks=stats["total_tasks"],
            overdue_tasks=stats["overdue_tasks"],
            overdue_color=overdue_color,
            due_today=stats["due_today"],
            repairmen=stats["repairmen"],
            members=stats["members"],
            incidents=stats["incidents"],
            incidents_this_month=stats["incidents_this_month"],
            overdue=overdue, due_soon=due_soon, healthy=healthy,
            household_cards=_render_households(households),
            task_rows=_render_tasks(tasks),
            incident_rows=_render_incidents(incidents),
            repairman_rows=_render_repairmen(repairmen),
        )
        return HTMLResponse(content=html)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "HomeKeeper Dashboard"}

    return app

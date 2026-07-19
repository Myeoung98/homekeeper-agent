import os
import sqlite3
from datetime import date, datetime
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
    return {
        "households": _scalar(
            "SELECT COUNT(DISTINCT household_id) FROM TASK WHERE household_id != 0"
        ),
        "total_tasks": _scalar("SELECT COUNT(*) FROM TASK"),
        "overdue_tasks": _scalar(
            "SELECT COUNT(*) FROM TASK WHERE next_due_date < ?", (today,)
        ),
        "due_today": _scalar(
            "SELECT COUNT(*) FROM TASK WHERE next_due_date = ?", (today,)
        ),
        "repairmen": _scalar("SELECT COUNT(*) FROM REPAIRMAN"),
        "members": _scalar("SELECT COUNT(*) FROM MEMBER"),
        "incidents": _scalar("SELECT COUNT(*) FROM INCIDENT"),
        "incidents_this_month": _scalar(
            "SELECT COUNT(*) FROM INCIDENT WHERE created_at >= ?",
            (datetime.now().strftime("%Y-%m"),),
        ),
    }


def _recent_tasks(limit: int = 8) -> list[dict]:
    return _fetch(
        "SELECT * FROM TASK ORDER BY next_due_date ASC LIMIT ?", (limit,)
    )


def _recent_incidents(limit: int = 6) -> list[dict]:
    return _fetch(
        "SELECT * FROM INCIDENT ORDER BY created_at DESC LIMIT ?", (limit,)
    )


def _repairmen(limit: int = 10) -> list[dict]:
    return _fetch(
        "SELECT * FROM REPAIRMAN ORDER BY id DESC LIMIT ?", (limit,)
    )


def _task_status_chart() -> tuple[int, int, int]:
    today = date.today().isoformat()
    overdue = _scalar("SELECT COUNT(*) FROM TASK WHERE next_due_date < ?", (today,))
    due_soon = _scalar(
        "SELECT COUNT(*) FROM TASK WHERE next_due_date BETWEEN ? AND date(?, '+7 days')",
        (today, today),
    )
    healthy = max(0, _scalar("SELECT COUNT(*) FROM TASK") - overdue - due_soon)
    return overdue, due_soon, healthy


_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>HomeKeeper Agent — Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; }}
  .stat-card {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border: 1px solid #334155; border-radius: 12px; }}
  .badge-ok  {{ background: #14532d; color: #86efac; }}
  .badge-warn{{ background: #78350f; color: #fde68a; }}
  .badge-err {{ background: #7f1d1d; color: #fca5a5; }}
  .dot-green {{ background: #22c55e; width:8px; height:8px; border-radius:50%; display:inline-block; }}
  .dot-red   {{ background: #ef4444; width:8px; height:8px; border-radius:50%; display:inline-block; }}
  .dot-yellow{{ background: #eab308; width:8px; height:8px; border-radius:50%; display:inline-block; }}
  .scrollable {{ max-height: 320px; overflow-y: auto; }}
  ::-webkit-scrollbar {{ width:4px; }} ::-webkit-scrollbar-thumb {{ background:#475569; border-radius:4px; }}
</style>
<meta http-equiv="refresh" content="30"/>
</head>
<body class="min-h-screen p-6">

<!-- Header -->
<div class="flex items-center justify-between mb-8">
  <div class="flex items-center gap-3">
    <div class="text-3xl">🏠</div>
    <div>
      <h1 class="text-2xl font-bold text-white">HomeKeeper Agent</h1>
      <p class="text-slate-400 text-sm">AI-Powered Home Maintenance Platform</p>
    </div>
  </div>
  <div class="flex items-center gap-2 px-4 py-2 card text-sm">
    <span class="dot-green animate-pulse"></span>
    <span class="text-slate-300">Live · auto-refresh 30s</span>
  </div>
</div>

<!-- KPI Cards -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="stat-card p-5">
    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Hộ gia đình</p>
    <p class="text-4xl font-bold text-white">{households}</p>
    <p class="text-slate-500 text-xs mt-1">Multi-tenant</p>
  </div>
  <div class="stat-card p-5">
    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Công việc</p>
    <p class="text-4xl font-bold text-sky-400">{total_tasks}</p>
    <p class="text-{overdue_color}-400 text-xs mt-1">{overdue_tasks} quá hạn</p>
  </div>
  <div class="stat-card p-5">
    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Thợ sửa chữa</p>
    <p class="text-4xl font-bold text-emerald-400">{repairmen}</p>
    <p class="text-slate-500 text-xs mt-1">{members} thành viên</p>
  </div>
  <div class="stat-card p-5">
    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Sự cố tháng này</p>
    <p class="text-4xl font-bold text-amber-400">{incidents_this_month}</p>
    <p class="text-slate-500 text-xs mt-1">{incidents} tổng cộng</p>
  </div>
</div>

<!-- Middle Row -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">

  <!-- Task Health Chart -->
  <div class="card p-5">
    <h2 class="font-semibold text-white mb-4 flex items-center gap-2">
      <span>📊</span> Tình trạng bảo trì
    </h2>
    <div class="flex justify-center">
      <canvas id="taskChart" width="180" height="180"></canvas>
    </div>
    <div class="flex justify-center gap-4 mt-3 text-xs text-slate-400">
      <span><span class="dot-red mr-1" style="display:inline-block"></span>Quá hạn ({overdue})</span>
      <span><span class="dot-yellow mr-1" style="display:inline-block"></span>Sắp đến ({due_soon})</span>
      <span><span class="dot-green mr-1" style="display:inline-block"></span>Ổn ({healthy})</span>
    </div>
  </div>

  <!-- Upcoming Tasks -->
  <div class="card p-5 md:col-span-2">
    <h2 class="font-semibold text-white mb-4 flex items-center gap-2">
      <span>📋</span> Lịch bảo trì sắp tới
    </h2>
    <div class="scrollable space-y-2">
      {task_rows}
    </div>
  </div>

</div>

<!-- Bottom Row -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-4">

  <!-- Recent Incidents -->
  <div class="card p-5">
    <h2 class="font-semibold text-white mb-4 flex items-center gap-2">
      <span>🚨</span> Sự cố gần đây
    </h2>
    <div class="scrollable space-y-2">
      {incident_rows}
    </div>
  </div>

  <!-- Repairman Directory -->
  <div class="card p-5">
    <h2 class="font-semibold text-white mb-4 flex items-center gap-2">
      <span>🔧</span> Danh bạ thợ
    </h2>
    <div class="scrollable space-y-2">
      {repairman_rows}
    </div>
  </div>

</div>

<!-- Footer -->
<div class="mt-8 text-center text-slate-600 text-xs">
  HomeKeeper Agent · AI-powered by Groq + OpenRouter · Multi-tenant Telegram Bot
</div>

<script>
const ctx = document.getElementById('taskChart').getContext('2d');
new Chart(ctx, {{
  type: 'doughnut',
  data: {{
    datasets: [{{
      data: [{overdue}, {due_soon}, {healthy}],
      backgroundColor: ['#ef4444','#eab308','#22c55e'],
      borderWidth: 0,
      hoverOffset: 4
    }}]
  }},
  options: {{
    cutout: '70%',
    plugins: {{ legend: {{ display: false }} }},
    animation: {{ animateRotate: true }}
  }}
}});
</script>
</body>
</html>"""


def _due_badge(due_date_str: str) -> str:
    try:
        due = date.fromisoformat(due_date_str)
        today = date.today()
        diff = (due - today).days
        if diff < 0:
            return f'<span class="badge-err text-xs px-2 py-0.5 rounded-full">Quá hạn {-diff}n</span>'
        if diff == 0:
            return '<span class="badge-warn text-xs px-2 py-0.5 rounded-full">Hôm nay</span>'
        if diff <= 7:
            return f'<span class="badge-warn text-xs px-2 py-0.5 rounded-full">{diff} ngày</span>'
        return f'<span class="text-slate-500 text-xs">{diff} ngày</span>'
    except (ValueError, TypeError):
        return ""


def _render_task_rows(tasks: list[dict]) -> str:
    if not tasks:
        return '<p class="text-slate-500 text-sm text-center py-4">Chưa có công việc nào</p>'
    rows = []
    for t in tasks:
        badge = _due_badge(t.get("next_due_date", ""))
        rows.append(
            f'<div class="flex items-center justify-between bg-slate-800 rounded-lg px-3 py-2">'
            f'<span class="text-sm text-slate-200 truncate flex-1">{t["name"]}</span>'
            f'<span class="ml-2 shrink-0">{badge}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_incident_rows(incidents: list[dict]) -> str:
    if not incidents:
        return '<p class="text-slate-500 text-sm text-center py-4">Không có sự cố nào</p>'
    rows = []
    for inc in incidents:
        ts = (inc.get("created_at") or "")[:10]
        desc = (inc.get("description") or "")[:60]
        rows.append(
            f'<div class="bg-slate-800 rounded-lg px-3 py-2">'
            f'<p class="text-sm text-slate-200">{desc}{"…" if len(inc.get("description",""))>60 else ""}</p>'
            f'<p class="text-xs text-slate-500 mt-0.5">{ts}</p>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_repairman_rows(repairmen: list[dict]) -> str:
    if not repairmen:
        return '<p class="text-slate-500 text-sm text-center py-4">Chưa có thợ nào</p>'
    rows = []
    for r in repairmen:
        rows.append(
            f'<div class="flex items-center justify-between bg-slate-800 rounded-lg px-3 py-2">'
            f'<div>'
            f'<p class="text-sm text-slate-200 font-medium">{r["name"]}</p>'
            f'<p class="text-xs text-slate-500">{r["service_type"]}</p>'
            f'</div>'
            f'<a href="tel:{r["phone"]}" class="text-sky-400 text-xs hover:underline">{r["phone"]}</a>'
            f'</div>'
        )
    return "\n".join(rows)


def create_app() -> FastAPI:
    app = FastAPI(title="HomeKeeper Dashboard", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        stats = _stats()
        overdue, due_soon, healthy = _task_status_chart()
        tasks = _recent_tasks()
        incidents = _recent_incidents()
        repairmen = _repairmen()

        overdue_color = "red" if stats["overdue_tasks"] > 0 else "slate"

        html = _HTML.format(
            households=stats["households"],
            total_tasks=stats["total_tasks"],
            overdue_tasks=stats["overdue_tasks"],
            overdue_color=overdue_color,
            repairmen=stats["repairmen"],
            members=stats["members"],
            incidents=stats["incidents"],
            incidents_this_month=stats["incidents_this_month"],
            overdue=overdue,
            due_soon=due_soon,
            healthy=healthy,
            task_rows=_render_task_rows(tasks),
            incident_rows=_render_incident_rows(incidents),
            repairman_rows=_render_repairman_rows(repairmen),
        )
        return HTMLResponse(content=html)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "HomeKeeper Dashboard"}

    return app

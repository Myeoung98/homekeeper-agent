"""
Demo data seed script for HomeKeeper Agent investor demo.
Run once: python seed_demo.py
Idempotent: safe to run multiple times (skips existing records).
"""
from dotenv import load_dotenv
load_dotenv()

import sqlite3
import os
from datetime import date, timedelta
from homekeeper.db.connection import open_db

conn = open_db()

today = date.today()

def d(offset: int) -> str:
    return (today + timedelta(days=offset)).isoformat()

def now_str(offset_days: int = 0) -> str:
    from datetime import datetime
    return (datetime.now() + timedelta(days=-offset_days)).strftime("%Y-%m-%dT%H:%M:%S")

# ---------------------------------------------------------------------------
# Households (household_id = Telegram chat ID, we use fake IDs for demo)
# ---------------------------------------------------------------------------
# HH1 = Gia đình Nguyễn (1 căn hộ)
# HH2 = Gia đình Trần   (1 nhà phố)
# HH3 = VP Demo          (văn phòng)
HH1, HH2, HH3 = 1001, 1002, 1003

# ---------------------------------------------------------------------------
# REPAIRMEN
# ---------------------------------------------------------------------------
repairmen = [
    (HH1, "Nguyễn Văn An",  "0901234567", "điện"),
    (HH1, "Trần Thị Bình",  "0912345678", "nước"),
    (HH1, "Lê Quốc Cường",  "0923456789", "máy lạnh"),
    (HH2, "Phạm Minh Đức",  "0934567890", "máy lạnh"),
    (HH2, "Hoàng Thị Lan",  "0945678901", "sơn"),
    (HH2, "Vũ Thanh Nam",   "0956789012", "mộc"),
    (HH3, "Đinh Văn Phúc",  "0967890123", "điện"),
    (HH3, "Bùi Thị Quỳnh",  "0978901234", "nước"),
]
for hid, name, phone, stype in repairmen:
    exists = conn.execute(
        "SELECT 1 FROM REPAIRMAN WHERE name=? AND household_id=?", (name, hid)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO REPAIRMAN (name, phone, service_type, household_id) VALUES (?,?,?,?)",
            (name, phone, stype, hid),
        )

# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------
tasks = [
    # HH1 — căn hộ Nguyễn
    (HH1, "Vệ sinh máy lạnh phòng khách",   90,  d(-5)),   # overdue
    (HH1, "Thay bộ lọc nước",                60,  d(0)),    # due today
    (HH1, "Kiểm tra điện định kỳ",           180, d(3)),    # due soon
    (HH1, "Bảo dưỡng bình nóng lạnh",        365, d(45)),   # healthy
    (HH1, "Sơn lại tường ban công",          730, d(120)),  # healthy
    # HH2 — nhà phố Trần
    (HH2, "Thông cống thoát nước",            30,  d(-12)),  # overdue
    (HH2, "Vệ sinh máy lạnh phòng ngủ",       90,  d(2)),    # due soon
    (HH2, "Kiểm tra mái nhà trước mùa mưa",  365, d(5)),    # due soon
    (HH2, "Sơn cổng sắt chống gỉ",           365, d(90)),   # healthy
    # HH3 — văn phòng
    (HH3, "Bảo trì hệ thống điện văn phòng", 180, d(-3)),   # overdue
    (HH3, "Vệ sinh máy lạnh tầng 1",          60,  d(1)),    # due soon
    (HH3, "Kiểm tra PCCC",                   180, d(60)),   # healthy
]
for hid, name, cycle, due in tasks:
    exists = conn.execute(
        "SELECT 1 FROM TASK WHERE name=? AND household_id=?", (name, hid)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO TASK (name, cycle_days, next_due_date, created_at, household_id) "
            "VALUES (?,?,?,?,?)",
            (name, cycle, due, now_str(30), hid),
        )

# ---------------------------------------------------------------------------
# INCIDENTS
# ---------------------------------------------------------------------------
incidents = [
    (HH1, 6121314171, "Máy lạnh phòng khách chảy nước, không mát", now_str(15)),
    (HH1, 6121314171, "Bóng đèn hành lang bị chập, cần thay gấp",  now_str(8)),
    (HH2, 6121314172, "Bồn cầu bị tắc, nước tràn ra ngoài",        now_str(20)),
    (HH2, 6121314172, "Vòi nước bếp bị rỉ, chảy liên tục",         now_str(5)),
    (HH2, 6121314172, "Cửa gỗ phòng ngủ bị phồng do ẩm",           now_str(2)),
    (HH3, 6121314173, "Cầu dao tổng bị nhảy vào buổi tối",         now_str(10)),
    (HH3, 6121314173, "Máy lạnh phòng họp không đủ lạnh",           now_str(1)),
]
for hid, uid, desc, ts in incidents:
    exists = conn.execute(
        "SELECT 1 FROM INCIDENT WHERE description=? AND household_id=?", (desc, hid)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO INCIDENT (reported_by, description, created_at, household_id) "
            "VALUES (?,?,?,?)",
            (uid, desc, ts, hid),
        )

# ---------------------------------------------------------------------------
# MEMBERS
# ---------------------------------------------------------------------------
members = [
    (HH1, 6121314171, "Nguyễn Văn A (chủ nhà)"),
    (HH1, 6121314174, "Nguyễn Thị B"),
    (HH2, 6121314172, "Trần Văn C (chủ nhà)"),
    (HH3, 6121314173, "Admin VP"),
]
for hid, uid, name in members:
    exists = conn.execute(
        "SELECT 1 FROM MEMBER WHERE telegram_user_id=?", (uid,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO MEMBER (telegram_user_id, name, household_id) VALUES (?,?,?)",
            (uid, name, hid),
        )

conn.commit()
conn.close()

print("✅ Demo data seeded successfully!")
print(f"   • {len(repairmen)} repairmen across 3 households")
print(f"   • {len(tasks)} maintenance tasks (3 overdue, 4 due soon, 5 healthy)")
print(f"   • {len(incidents)} incidents")
print(f"   • {len(members)} members")

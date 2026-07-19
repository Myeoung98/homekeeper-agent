"""Auto-seed demo data when the database is empty (first run / fresh deploy)."""
import sqlite3
from datetime import date, datetime, timedelta


def _d(conn: sqlite3.Connection, offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _ts(conn: sqlite3.Connection, offset_days: int = 0) -> str:
    return (datetime.now() - timedelta(days=offset_days)).strftime("%Y-%m-%dT%H:%M:%S")


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Insert demo data only when TASK table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM TASK").fetchone()[0]
    if count > 0:
        return  # already has data — skip

    HH1, HH2, HH3 = 1001, 1002, 1003

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
    conn.executemany(
        "INSERT INTO REPAIRMAN (name, phone, service_type, household_id) VALUES (?,?,?,?)",
        repairmen,
    )

    today = date.today()
    tasks = [
        (HH1, "Vệ sinh máy lạnh phòng khách",  90,  (today + timedelta(-5)).isoformat()),
        (HH1, "Thay bộ lọc nước",               60,  today.isoformat()),
        (HH1, "Kiểm tra điện định kỳ",          180, (today + timedelta(3)).isoformat()),
        (HH1, "Bảo dưỡng bình nóng lạnh",       365, (today + timedelta(45)).isoformat()),
        (HH1, "Sơn lại tường ban công",         730, (today + timedelta(120)).isoformat()),
        (HH2, "Thông cống thoát nước",           30,  (today + timedelta(-12)).isoformat()),
        (HH2, "Vệ sinh máy lạnh phòng ngủ",      90,  (today + timedelta(2)).isoformat()),
        (HH2, "Kiểm tra mái nhà trước mùa mưa", 365, (today + timedelta(5)).isoformat()),
        (HH2, "Sơn cổng sắt chống gỉ",          365, (today + timedelta(90)).isoformat()),
        (HH3, "Bảo trì hệ thống điện văn phòng",180, (today + timedelta(-3)).isoformat()),
        (HH3, "Vệ sinh máy lạnh tầng 1",         60,  (today + timedelta(1)).isoformat()),
        (HH3, "Kiểm tra PCCC",                  180, (today + timedelta(60)).isoformat()),
    ]
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    conn.executemany(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at, household_id) VALUES (?,?,?,?,?)",
        [(hid, name, cycle, due, now) for hid, name, cycle, due in tasks],
    )

    incidents = [
        (HH1, 6121314171, "Máy lạnh phòng khách chảy nước, không mát",
         (datetime.now() - timedelta(15)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH1, 6121314171, "Bóng đèn hành lang bị chập, cần thay gấp",
         (datetime.now() - timedelta(8)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH2, 6121314172, "Bồn cầu bị tắc, nước tràn ra ngoài",
         (datetime.now() - timedelta(20)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH2, 6121314172, "Vòi nước bếp bị rỉ, chảy liên tục",
         (datetime.now() - timedelta(5)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH2, 6121314172, "Cửa gỗ phòng ngủ bị phồng do ẩm",
         (datetime.now() - timedelta(2)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH3, 6121314173, "Cầu dao tổng bị nhảy vào buổi tối",
         (datetime.now() - timedelta(10)).strftime("%Y-%m-%dT%H:%M:%S")),
        (HH3, 6121314173, "Máy lạnh phòng họp không đủ lạnh",
         (datetime.now() - timedelta(1)).strftime("%Y-%m-%dT%H:%M:%S")),
    ]
    conn.executemany(
        "INSERT INTO INCIDENT (reported_by, description, created_at, household_id) VALUES (?,?,?,?)",
        incidents,
    )

    members = [
        (HH1, 6121314171, "Nguyễn Văn A (chủ nhà)"),
        (HH1, 6121314174, "Nguyễn Thị B"),
        (HH2, 6121314172, "Trần Văn C (chủ nhà)"),
        (HH3, 6121314173, "Admin VP"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO MEMBER (telegram_user_id, name, household_id) VALUES (?,?,?)",
        members,
    )

    conn.commit()

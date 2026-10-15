from datetime import datetime, timezone, timedelta
import sqlite3
from database import get_db, get_setting

JAKARTA_TZ = timezone(timedelta(hours=7))


def jakarta_now():
    return datetime.now(JAKARTA_TZ)


def jakarta_today_str():
    return jakarta_now().strftime("%Y-%m-%d")


def jakarta_time_str(dt=None):
    if dt is None:
        dt = jakarta_now()
    return dt.strftime("%H:%M:%S")


def determine_status(check_in_time_str):
    late_threshold = get_setting("late_threshold", "08:30")
    if check_in_time_str <= late_threshold:
        return "Hadir"
    return "Terlambat"


def record_check_in(user_id):
    conn = get_db()
    today = jakarta_today_str()
    now_str = jakarta_time_str()
    try:
        existing = conn.execute(
            "SELECT id, check_in FROM attendance WHERE user_id=? AND attendance_date=?",
            (user_id, today),
        ).fetchone()
        if existing and existing["check_in"]:
            return {"ok": False, "error": "Already checked in today",
                    "existing": dict(existing)}
        status = determine_status(now_str)
        if existing:
            conn.execute(
                "UPDATE attendance SET check_in=?, status=? WHERE id=?",
                (now_str, status, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO attendance (user_id, attendance_date, check_in, status) "
                "VALUES (?,?,?,?)",
                (user_id, today, now_str, status),
            )
        conn.commit()
        return {"ok": True, "date": today, "check_in": now_str, "status": status}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "Duplicate attendance record"}
    finally:
        conn.close()


def record_check_out(user_id):
    conn = get_db()
    today = jakarta_today_str()
    now_str = jakarta_time_str()
    try:
        row = conn.execute(
            "SELECT id, check_in, check_out FROM attendance "
            "WHERE user_id=? AND attendance_date=?",
            (user_id, today),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "No check-in record found for today"}
        if not row["check_in"]:
            return {"ok": False, "error": "Must check in first"}
        if row["check_out"]:
            return {"ok": False, "error": "Already checked out today"}
        conn.execute(
            "UPDATE attendance SET check_out=? WHERE id=?",
            (now_str, row["id"]),
        )
        conn.commit()
        return {"ok": True, "date": today, "check_out": now_str}
    finally:
        conn.close()


def get_today_attendance(user_id=None):
    conn = get_db()
    today = jakarta_today_str()
    if user_id is None:
        rows = conn.execute("""
            SELECT a.*, u.full_name, u.employee_code
            FROM attendance a JOIN users u ON a.user_id = u.id
            WHERE a.attendance_date = ?
            ORDER BY a.check_in DESC
        """, (today,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT a.*, u.full_name, u.employee_code
            FROM attendance a JOIN users u ON a.user_id = u.id
            WHERE a.attendance_date = ? AND a.user_id = ?
            ORDER BY a.check_in DESC
        """, (today, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_db()
    today = jakarta_today_str()
    total_users = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_active=1"
    ).fetchone()[0]
    checked_in = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND check_in IS NOT NULL",
        (today,),
    ).fetchone()[0]
    late = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Terlambat'",
        (today,),
    ).fetchone()[0]
    not_checked_in = max(0, total_users - checked_in)
    conn.close()
    return {
        "total_users": total_users,
        "checked_in": checked_in,
        "late": late,
        "not_checked_in": not_checked_in,
        "date": today,
    }


def record_kiosk_attendance(user_id, min_checkout_minutes=60):
    conn = get_db()
    today = jakarta_today_str()
    now = jakarta_now()
    now_str = jakarta_time_str(now)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, check_in, check_out FROM attendance "
            "WHERE user_id=? AND attendance_date=?",
            (user_id, today),
        ).fetchone()

        if row is None or not row["check_in"]:
            status = determine_status(now.strftime("%H:%M:%S"))
            if row:
                conn.execute(
                    "UPDATE attendance SET check_in=?, status=?, "
                    "verification_method='face' WHERE id=?",
                    (now_str, status, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO attendance "
                    "(user_id, attendance_date, check_in, status, verification_method) "
                    "VALUES (?,?,?,?,?)",
                    (user_id, today, now_str, status, "face"),
                )
            conn.commit()
            return {"ok": True, "action": "check-in", "date": today,
                    "time": now_str, "status": status}

        if row["check_out"]:
            conn.commit()
            return {"ok": True, "action": "already-complete", "date": today,
                    "time": now_str, "status": "Selesai"}

        try:
            checkin = datetime.strptime(row["check_in"], "%H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day, tzinfo=JAKARTA_TZ
            )
        except (TypeError, ValueError):
            conn.rollback()
            return {"ok": False, "error": "Waktu check-in tersimpan tidak valid"}

        elapsed = (now - checkin).total_seconds() / 60
        if elapsed < max(1, int(min_checkout_minutes)):
            conn.commit()
            remaining = max(1, int(min_checkout_minutes - elapsed))
            return {
                "ok": True,
                "action": "waiting-checkout",
                "date": today,
                "time": now_str,
                "status": "Hadir",
                "remaining_minutes": remaining,
            }

        cursor = conn.execute(
            "UPDATE attendance SET check_out=?, verification_method='face' "
            "WHERE id=? AND check_out IS NULL",
            (now_str, row["id"]),
        )
        if cursor.rowcount < 1:
            conn.rollback()
            return {"ok": False, "error": "Check-out gagal, silakan coba lagi"}
        conn.commit()
        return {"ok": True, "action": "check-out", "date": today,
                "time": now_str, "status": "Hadir"}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"ok": False, "error": "Catatan absensi sudah ada"}
    finally:
        conn.close()
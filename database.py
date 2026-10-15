import sqlite3
from config import Config

def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin','employee')),
            face_embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'Hadir'
                CHECK(status IN ('Hadir','Terlambat','Izin','Sakit','Tidak Hadir')),
            verification_method TEXT DEFAULT 'face',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, attendance_date)
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
        CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance(user_id);
    """)
    # Seed default settings
    defaults = {
        "check_in_time": Config.DEFAULT_CHECK_IN,
        "late_threshold": Config.DEFAULT_LATE_THRESHOLD,
        "face_match_threshold": str(Config.FACE_MATCH_THRESHOLD),
        "camera_facing_mode": "user",
        "processing_fps": "4",
        "retention_days": "90",
        "kiosk_min_checkout_minutes": str(Config.KIOSK_MIN_CHECKOUT_MINUTES),
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)",
            (k, v),
        )
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute(
        "SELECT setting_value FROM settings WHERE setting_key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["setting_value"] if row else default

def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?) "
        "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env BEFORE importing app
os.environ["LUMA_SECRET_KEY"] = "test-secret"


@pytest.fixture(scope="function")
def temp_db(tmp_path, monkeypatch):
    """Isolated temp database per test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("LUMA_DB_PATH", str(db_file))
    # Reload config so it picks up new path
    import importlib
    import config
    importlib.reload(config)
    config.Config.DATABASE = str(db_file)
    yield str(db_file)


@pytest.fixture
def client(temp_db):
    """Flask test client with isolated DB."""
    # Import fresh each time to pick up new DB path
    for mod in list(sys.modules.keys()):
        if mod in ("app", "database", "config",
                   "services", "services.attendance_service",
                   "routes", "routes.auth", "routes.admin",
                   "routes.attendance", "routes.kiosk"):
            del sys.modules[mod]

    import config
    config.Config.DATABASE = temp_db

    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_login_invalid(client):
    r = client.post("/api/auth/login", json={"username": "nope", "password": "bad"})
    assert r.status_code == 401


def test_login_missing_fields(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 400


def test_protected_endpoint_requires_auth(client):
    """Unauthenticated requests should be rejected."""
    r = client.get("/api/dashboard/stats")
    assert r.status_code in (401, 403), f"Unexpected {r.status_code}"


def test_create_user_and_login(client):
    from database import get_db
    from werkzeug.security import generate_password_hash

    conn = get_db()
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
        "VALUES ('T001','Test Admin','testadmin',?,'admin')",
        (generate_password_hash("test123"),),
    )
    conn.commit()
    conn.close()

    r = client.post("/api/auth/login", json={"username": "testadmin", "password": "test123"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_attendance_rules_no_double_checkin(client):
    from services.attendance_service import record_check_in, record_check_out
    from database import get_db
    from werkzeug.security import generate_password_hash

    conn = get_db()
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
        "VALUES ('T002','Test Emp','testemp',?,'employee')",
        (generate_password_hash("x"),),
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE username='testemp'").fetchone()[0]
    conn.close()

    r1 = record_check_in(uid)
    assert r1["ok"] is True, f"First check-in should succeed, got: {r1}"

    r2 = record_check_in(uid)
    assert r2["ok"] is False, "Second check-in same day should be rejected"

    r3 = record_check_out(uid)
    assert r3["ok"] is True, f"Check-out should succeed, got: {r3}"

    r4 = record_check_out(uid)
    assert r4["ok"] is False, "Second check-out should be rejected"


def test_checkout_without_checkin(client):
    from services.attendance_service import record_check_out
    from database import get_db
    from werkzeug.security import generate_password_hash

    conn = get_db()
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
        "VALUES ('T003','Test Emp2','testemp2',?,'employee')",
        (generate_password_hash("x"),),
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE username='testemp2'").fetchone()[0]
    conn.close()

    r = record_check_out(uid)
    assert r["ok"] is False, "Check-out without check-in should fail"


def test_csrf_blocks_state_change_without_token(client):
    """POST without CSRF token should be rejected for logged-in user."""
    from database import get_db
    from werkzeug.security import generate_password_hash

    conn = get_db()
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
        "VALUES ('T004','Test CSRF','testcsrf',?,'admin')",
        (generate_password_hash("pass"),),
    )
    conn.commit()
    conn.close()

    # Login to establish session
    r = client.post("/api/auth/login", json={"username": "testcsrf", "password": "pass"})
    assert r.status_code == 200

    # POST without CSRF header
    r = client.post("/api/users", json={
        "employee_code": "X", "full_name": "X",
        "username": "x", "password": "x",
    })
    assert r.status_code == 403
    assert "CSRF" in r.get_json().get("error", "")


def test_api_kiosk_disabled_by_default(client):
    """Kiosk should be off unless LUMA_KIOSK_MODE=1."""
    r = client.get("/api/kiosk/status")
    assert r.status_code == 403


def test_attendance_history_requires_auth(client):
    r = client.get("/api/attendance/history")
    assert r.status_code == 401

def test_attendance_mutations_require_login(client):
    r = client.post("/api/attendance/check-in", json={"image": "not-a-real-image"})
    assert r.status_code == 401
    r = client.post("/api/attendance/check-out", json={"image": "not-a-real-image"})
    assert r.status_code == 401


def test_kiosk_attendance_cannot_check_out_immediately(client):
    from database import get_db
    from services.attendance_service import record_kiosk_attendance
    from werkzeug.security import generate_password_hash

    conn = get_db()
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) VALUES (?,?,?,?,?)",
        ("K001", "Kiosk Test", "kiosktest", generate_password_hash("long-test-password"), "employee"),
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE username='kiosktest'").fetchone()[0]
    conn.close()

    first = record_kiosk_attendance(uid, min_checkout_minutes=60)
    second = record_kiosk_attendance(uid, min_checkout_minutes=60)
    assert first["ok"] is True and first["action"] == "check-in"
    assert second["ok"] is True and second["action"] == "waiting-checkout"


def test_face_verify_requires_login(client):
    r = client.post("/api/face/verify", json={"image": "not-a-real-image"})
    assert r.status_code == 401

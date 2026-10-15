from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from functools import wraps
from database import get_db
from services.face_engine import get_embedding, embedding_to_json, decode_image

admin_bp = Blueprint("admin", __name__, url_prefix="/api")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        conn = get_db()
        try:
            account = conn.execute(
                "SELECT role, is_active FROM users WHERE id=?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
        if not account or not account["is_active"]:
            session.clear()
            return jsonify({"error": "Account is inactive or no longer exists"}), 401
        if account["role"] != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/dashboard/stats", methods=["GET"])
@admin_required
def dashboard_stats():
    from services.attendance_service import get_stats, get_today_attendance
    stats = get_stats()
    today = get_today_attendance()
    return jsonify({"stats": stats, "today": today})

@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "GET":
        search = request.args.get("q", "").strip()
        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT id, employee_code, full_name, username, role, is_active, created_at, "
                "(face_embedding IS NOT NULL) as has_face FROM users "
                "WHERE full_name LIKE ? OR username LIKE ? OR employee_code LIKE ?",
                (f"%{search}%", f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, employee_code, full_name, username, role, is_active, created_at, "
                "(face_embedding IS NOT NULL) as has_face FROM users ORDER BY id DESC"
            ).fetchall()
        conn.close()
        return jsonify({"users": [dict(r) for r in rows]})

    data = request.get_json(silent=True) or {}
    required = ["employee_code", "full_name", "username", "password"]
    for f in required:
        if not isinstance(data.get(f), str) or not data[f].strip():
            return jsonify({"error": f"{f} required"}), 400
    if len(data["password"]) < 8:
        return jsonify({"error": "Password minimal 8 karakter"}), 400
    role = data.get("role", "employee")
    if role not in ("admin", "employee"):
        return jsonify({"error": "Role tidak valid"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (employee_code, full_name, username, password_hash, role) VALUES (?,?,?,?,?)",
            (
                data["employee_code"].strip(),
                data["full_name"].strip(),
                data["username"].strip(),
                generate_password_hash(data["password"]),
                role,
            ),
        )
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({"ok": True, "id": uid}), 201
    except Exception:
        return jsonify({"error": "Gagal membuat pengguna. Pastikan username dan kode pegawai unik."}), 400
    finally:
        conn.close()

@admin_bp.route("/users/<int:uid>", methods=["GET", "PUT", "DELETE"])
@admin_required
def user_detail(uid):
    conn = get_db()
    if request.method == "GET":
        row = conn.execute(
            "SELECT id, employee_code, full_name, username, role, is_active, created_at, "
            "(face_embedding IS NOT NULL) as has_face FROM users WHERE id=?", (uid,)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": dict(row)})

    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        fields = []
        vals = []
        for f in ["employee_code", "full_name", "username", "role", "is_active"]:
            if f in data:
                value = data[f]
                if f == "role" and value not in ("admin", "employee"):
                    conn.close()
                    return jsonify({"error": "Role tidak valid"}), 400
                if f == "is_active":
                    if value not in (0, 1, False, True):
                        conn.close()
                        return jsonify({"error": "is_active harus boolean"}), 400
                    value = int(bool(value))
                if f in ("employee_code", "full_name", "username"):
                    if not isinstance(value, str) or not value.strip():
                        conn.close()
                        return jsonify({"error": f"{f} tidak boleh kosong"}), 400
                    value = value.strip()
                fields.append(f"{f}=?")
                vals.append(value)
        if data.get("password"):
            if not isinstance(data["password"], str) or len(data["password"]) < 8:
                conn.close()
                return jsonify({"error": "Password minimal 8 karakter"}), 400
            fields.append("password_hash=?")
            vals.append(generate_password_hash(data["password"]))
        if not fields:
            return jsonify({"error": "Nothing to update"}), 400
        vals.append(uid)
        conn.execute(f"UPDATE users SET {','.join(fields)} WHERE id=?", vals)
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    # DELETE removes the biometric template; the account itself is retained.
    row = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    conn.execute("UPDATE users SET face_embedding=NULL WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Face template deleted"})

@admin_bp.route("/face/register", methods=["POST"])
@admin_required
def face_register():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    image_b64 = data.get("image")
    if not uid or not image_b64:
        return jsonify({"error": "user_id and image required"}), 400
    img = decode_image(image_b64)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    emb, err = get_embedding(img)
    if emb is None:
        return jsonify({"error": err}), 400
    conn = get_db()
    try:
        user = conn.execute("SELECT id, is_active FROM users WHERE id=?", (uid,)).fetchone()
        if not user or not user["is_active"]:
            return jsonify({"error": "Pengguna tidak ditemukan atau nonaktif"}), 404
        conn.execute("UPDATE users SET face_embedding=? WHERE id=?",
                     (embedding_to_json(emb), uid))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "message": "Face registered"})

@admin_bp.route("/face/verify", methods=["POST"])
def face_verify():
    """Verify a face for an authenticated attendance session only."""
    if not session.get("user_id"):
        return jsonify({"error": "Not authenticated"}), 401
    from services.face_engine import identify_face
    from config import Config
    from services.attendance_service import jakarta_today_str
    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "image required"}), 400
    img = decode_image(image_b64)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
    conn = get_db()
    rows = conn.execute(
        "SELECT id, face_embedding FROM users WHERE id=? AND is_active=1 AND face_embedding IS NOT NULL",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    candidates = [(r["id"], r["face_embedding"]) for r in rows]
    if not candidates:
        return jsonify({"error": "No registered faces in system"}), 400
    from database import get_setting
    try:
        threshold = float(get_setting("face_match_threshold", str(Config.FACE_MATCH_THRESHOLD)))
        if not 0.05 <= threshold <= 0.99:
            threshold = Config.FACE_MATCH_THRESHOLD
    except (TypeError, ValueError):
        threshold = Config.FACE_MATCH_THRESHOLD
    uid, sim, msg = identify_face(img, candidates, threshold)
    if uid is None:
        return jsonify({"matched": False, "similarity": round(sim, 4), "message": msg})
    conn = get_db()
    user = conn.execute(
        "SELECT id, full_name, employee_code FROM users WHERE id=?", (uid,)
    ).fetchone()
    conn.close()
    return jsonify({
        "matched": True,
        "user": dict(user),
        "similarity": round(sim, 4),
        "message": "Identified",
    })

@admin_bp.route("/settings", methods=["GET", "PUT"])
@admin_required
def settings():
    from database import get_setting, set_setting
    if request.method == "GET":
        conn = get_db()
        rows = conn.execute("SELECT setting_key, setting_value FROM settings").fetchall()
        conn.close()
        return jsonify({"settings": {r["setting_key"]: r["setting_value"] for r in rows}})
    data = request.get_json(silent=True) or {}
    allowed = {"check_in_time", "late_threshold", "face_match_threshold", "camera_facing_mode", "processing_fps", "retention_days", "kiosk_min_checkout_minutes"}
    for k, v in data.items():
        if k not in allowed:
            return jsonify({"error": f"Setting tidak dikenal: {k}"}), 400
        value = str(v).strip()
        if k == "face_match_threshold":
            try:
                number = float(value)
                if not 0.05 <= number <= 0.99:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "Threshold harus antara 0.05 dan 0.99"}), 400
        elif k == "kiosk_min_checkout_minutes":
            try:
                number = int(value)
                if not 1 <= number <= 1440:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "Interval check-out harus 1–1440 menit"}), 400
        elif k in ("check_in_time", "late_threshold"):
            import re
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                return jsonify({"error": f"Format {k} harus HH:MM"}), 400
        elif k == "processing_fps":
            try:
                number = int(value)
                if not 1 <= number <= 10:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "Processing FPS harus 1–10"}), 400
        elif k == "retention_days":
            try:
                number = int(value)
                if not 7 <= number <= 3650:
                    raise ValueError
            except ValueError:
                return jsonify({"error": "Retensi harus 7–3650 hari"}), 400
        elif k == "camera_facing_mode" and value not in ("user", "environment"):
            return jsonify({"error": "Mode kamera tidak valid"}), 400
        set_setting(k, value)
    return jsonify({"ok": True})
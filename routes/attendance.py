from flask import Blueprint, request, jsonify, session
from database import get_db
from services.face_engine import decode_image, identify_face
from services.attendance_service import record_check_in, record_check_out, get_today_attendance, jakarta_today_str
from config import Config
import time

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")

_cooldowns = {}

def _check_cooldown(user_id):
    now = time.time()
    last = _cooldowns.get(user_id, 0)
    if now - last < Config.ATTENDANCE_COOLDOWN_SECONDS:
        return False
    return True

def _set_cooldown(user_id):
    _cooldowns[user_id] = time.time()

def _verify_identity(image_b64, expected_user_id=None):
    """Returns (user_dict, error); optionally restrict matching to session user."""
    img = decode_image(image_b64)
    if img is None:
        return None, "Invalid image"
    conn = get_db()
    if expected_user_id is None:
        rows = conn.execute(
            "SELECT id, face_embedding FROM users WHERE is_active=1 AND face_embedding IS NOT NULL"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, face_embedding FROM users WHERE id=? AND is_active=1 AND face_embedding IS NOT NULL",
            (expected_user_id,),
        ).fetchall()
    conn.close()
    candidates = [(r["id"], r["face_embedding"]) for r in rows]
    if not candidates:
        return None, "No registered faces"
    from database import get_setting
    try:
        threshold = float(get_setting("face_match_threshold", str(Config.FACE_MATCH_THRESHOLD)))
        if not 0.05 <= threshold <= 0.99:
            threshold = Config.FACE_MATCH_THRESHOLD
    except (TypeError, ValueError):
        threshold = Config.FACE_MATCH_THRESHOLD
    uid, sim, msg = identify_face(img, candidates, threshold)
    if uid is None:
        return None, f"Face not recognized ({msg})"
    conn = get_db()
    user = conn.execute(
        "SELECT id, full_name, employee_code FROM users WHERE id=?", (uid,)
    ).fetchone()
    conn.close()
    if not user:
        return None, "User not found"
    return dict(user), None

@attendance_bp.route("/check-in", methods=["POST"])
def check_in():
    if not session.get("user_id"):
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "image required"}), 400
    user, err = _verify_identity(image_b64, session.get("user_id"))
    if err:
        return jsonify({"error": err, "matched": False}), 400
    if user["id"] != session.get("user_id"):
        return jsonify({"error": "Wajah tidak cocok dengan akun yang sedang login", "matched": False}), 403
    if not _check_cooldown(user["id"]):
        return jsonify({"error": "Please wait before trying again"}), 429
    result = record_check_in(user["id"])
    if not result.get("ok"):
        return jsonify(result), 400
    _set_cooldown(user["id"])
    return jsonify({
        "ok": True,
        "user": user,
        "attendance": result,
        "message": f"Check-in recorded for {user['full_name']}",
    })

@attendance_bp.route("/check-out", methods=["POST"])
def check_out():
    if not session.get("user_id"):
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "image required"}), 400
    user, err = _verify_identity(image_b64, session.get("user_id"))
    if err:
        return jsonify({"error": err, "matched": False}), 400
    if user["id"] != session.get("user_id"):
        return jsonify({"error": "Wajah tidak cocok dengan akun yang sedang login", "matched": False}), 403
    if not _check_cooldown(user["id"]):
        return jsonify({"error": "Please wait before trying again"}), 429
    result = record_check_out(user["id"])
    if not result.get("ok"):
        return jsonify(result), 400
    _set_cooldown(user["id"])
    return jsonify({
        "ok": True,
        "user": user,
        "attendance": result,
        "message": f"Check-out recorded for {user['full_name']}",
    })

@attendance_bp.route("/today", methods=["GET"])
def today():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    rows = get_today_attendance(None if session.get("role") == "admin" else session.get("user_id"))
    return jsonify({"today": rows, "date": jakarta_today_str()})

@attendance_bp.route("/history", methods=["GET"])
def history():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    status_f = request.args.get("status", "")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    conn = get_db()
    where = []
    params = []
    if date_from:
        where.append("a.attendance_date >= ?"); params.append(date_from)
    if date_to:
        where.append("a.attendance_date <= ?"); params.append(date_to)
    if status_f:
        where.append("a.status = ?"); params.append(status_f)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM attendance a JOIN users u ON a.user_id=u.id {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(f"""
        SELECT a.*, u.full_name, u.employee_code
        FROM attendance a JOIN users u ON a.user_id=u.id
        {where_sql}
        ORDER BY a.attendance_date DESC, a.check_in DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, (page - 1) * per_page]).fetchall()
    conn.close()
    return jsonify({
        "history": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    })

@attendance_bp.route("/export.csv", methods=["GET"])
def export_csv():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    import csv
    import io
    conn = get_db()
    rows = conn.execute("""
        SELECT a.attendance_date, u.employee_code, u.full_name,
               a.check_in, a.check_out, a.status
        FROM attendance a JOIN users u ON a.user_id = u.id
        ORDER BY a.attendance_date DESC
    """).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Employee Code", "Name", "Check In", "Check Out", "Status"])
    for r in rows:
        writer.writerow([r["attendance_date"], r["employee_code"], r["full_name"],
                         r["check_in"] or "", r["check_out"] or "", r["status"]])
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )
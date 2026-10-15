"""
Kiosk mode API — public endpoint for one-device attendance.
Only active when KIOSK_MODE=1 in .env.
"""

from flask import Blueprint, request, jsonify, current_app
from database import get_db, get_setting
from services.face_engine import decode_image, identify_face
from services.attendance_service import (
    record_kiosk_attendance, jakarta_today_str, jakarta_time_str,
)
from config import Config
import time
import threading

kiosk_bp = Blueprint("kiosk", __name__, url_prefix="/api/kiosk")

_rate_buckets = {}
_user_last_scan = {}
_rate_lock = threading.Lock()
RATE_WINDOW = 5.0
RATE_MAX = 25


def _rate_ok(ip):
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets.setdefault(ip, [])
        bucket[:] = [t for t in bucket if now - t < RATE_WINDOW]
        if len(bucket) >= RATE_MAX:
            return False
        bucket.append(now)
    return True


@kiosk_bp.route("/scan", methods=["POST"])
def scan():
    if not current_app.config.get("KIOSK_MODE"):
        return jsonify({"error": "Kiosk mode disabled"}), 403

    ip = request.remote_addr or "unknown"
    if not _rate_ok(ip):
        return jsonify({"error": "Rate limited"}), 429

    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "image required"}), 400

    img = decode_image(image_b64)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, face_embedding FROM users "
            "WHERE is_active=1 AND face_embedding IS NOT NULL"
        ).fetchall()
        candidates = [(r["id"], r["face_embedding"]) for r in rows]

        if not candidates:
            return jsonify({
                "matched": False,
                "message": "Belum ada wajah terdaftar",
            })

        threshold_raw = get_setting(
            "face_match_threshold", str(Config.FACE_MATCH_THRESHOLD)
        )
        try:
            threshold = float(threshold_raw)
            if not 0.05 <= threshold <= 0.99:
                threshold = Config.FACE_MATCH_THRESHOLD
        except (TypeError, ValueError):
            threshold = Config.FACE_MATCH_THRESHOLD

        uid, sim, msg = identify_face(img, candidates, threshold)

        if uid is None:
            return jsonify({
                "matched": False,
                "similarity": round(sim, 4),
                "message": msg,
            })

        user = conn.execute(
            "SELECT id, full_name, employee_code FROM users WHERE id=?",
            (uid,),
        ).fetchone()
        if not user:
            return jsonify({"matched": False, "message": "User tidak ditemukan"})

    finally:
        conn.close()

    # Per-process scan cooldown reduces repeated recognition while a person
    # remains in frame. The persisted minimum interval below is the real guard.
    now_epoch = time.time()
    with _rate_lock:
        last_scan = _user_last_scan.get(uid, 0)
        if now_epoch - last_scan < Config.KIOSK_SCAN_COOLDOWN_SECONDS:
            return jsonify({"matched": False, "cooldown": True,
                            "message": "Tunggu sebentar sebelum scan berikutnya"})
        _user_last_scan[uid] = now_epoch

    try:
        min_checkout = int(get_setting(
            "kiosk_min_checkout_minutes", str(Config.KIOSK_MIN_CHECKOUT_MINUTES)
        ))
    except (TypeError, ValueError):
        min_checkout = Config.KIOSK_MIN_CHECKOUT_MINUTES
    result = record_kiosk_attendance(uid, min_checkout)
    if not result.get("ok"):
        return jsonify({"matched": False, "message": result.get("error", "Absensi gagal")}), 400

    action = result.get("action")
    if action == "waiting-checkout":
        message = f"Check-in sudah tercatat. Check-out tersedia sekitar {result.get('remaining_minutes', 1)} menit lagi."
    elif action == "already-complete":
        message = "Absensi hari ini sudah lengkap"
    elif action == "check-in":
        message = "Check-in berhasil"
    else:
        message = "Check-out berhasil"

    return jsonify({
        "matched": True, "user": dict(user), "action": action,
        "similarity": round(sim, 4), "time": result.get("time", jakarta_time_str()),
        "status": result.get("status", "Hadir"),
        "remaining_minutes": result.get("remaining_minutes"), "message": message,
    })


@kiosk_bp.route("/status", methods=["GET"])
def status():
    """Health check for kiosk page."""
    if not current_app.config.get("KIOSK_MODE"):
        return jsonify({"kiosk": False, "error": "disabled"}), 403
    conn = get_db()
    try:
        n_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_active=1 AND face_embedding IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    return jsonify({
        "kiosk": True,
        "registered_faces": n_users,
        "time": jakarta_time_str(),
        "date": jakarta_today_str(),
    })
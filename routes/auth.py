from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db
from config import Config
import time
from collections import defaultdict

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_login_attempts = defaultdict(list)

def _check_rate_limit(ip):
    now = time.time()
    attempts = _login_attempts[ip]
    _login_attempts[ip] = [t for t in attempts if now - t < Config.LOGIN_WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= Config.MAX_LOGIN_ATTEMPTS:
        return False
    return True

def _record_attempt(ip):
    _login_attempts[ip].append(time.time())

@auth_bp.route("/login", methods=["POST"])
def login():
    ip = request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        return jsonify({"error": "Too many attempts. Try again later."}), 429
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    conn = get_db()
    user = conn.execute(
        "SELECT id, username, password_hash, role, full_name FROM users WHERE username=? AND is_active=1",
        (username,),
    ).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password_hash"], password):
        _record_attempt(ip)
        return jsonify({"error": "Invalid credentials"}), 401
    # Rotate session contents on successful authentication to reduce fixation risk.
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["username"] = user["username"]
    session.permanent = True
    return jsonify({
        "ok": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
        },
    })

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@auth_bp.route("/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_db()
    user = conn.execute(
        "SELECT id, username, role, full_name, employee_code FROM users WHERE id=?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 401
    return jsonify({"user": dict(user)})
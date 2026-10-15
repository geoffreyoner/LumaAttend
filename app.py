import os
from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from config import Config
from database import init_db
from routes import auth_bp, admin_bp, attendance_bp, kiosk_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB max
    app.config["KIOSK_MODE"] = Config.KIOSK_MODE
    app.secret_key = Config.SECRET_KEY
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # localhost HTTP; enable only behind HTTPS
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
    )

    # Init DB
    init_db()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(kiosk_bp)

    # --- Page routes ---
    @app.route("/")
    def index():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        if session.get("role") == "admin":
            return redirect(url_for("dashboard_page"))
        return redirect(url_for("attendance_page"))

    @app.route("/login")
    def login_page():
        if "user_id" in session:
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard_page():
        if session.get("role") != "admin":
            return redirect(url_for("login_page"))
        return render_template("dashboard.html")

    @app.route("/attendance")
    def attendance_page():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("attendance.html")

    @app.route("/users")
    def users_page():
        if session.get("role") != "admin":
            return redirect(url_for("login_page"))
        return render_template("users.html")

    @app.route("/history")
    def history_page():
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return render_template("history.html")

    @app.route("/settings")
    def settings_page():
        if session.get("role") != "admin":
            return redirect(url_for("login_page"))
        return render_template("settings.html")

    @app.route("/kiosk")
    def kiosk_page():
        if not app.config.get("KIOSK_MODE"):
            return (
                "<h1>Kiosk mode disabled</h1>"
                "<p>Set <code>LUMA_KIOSK_MODE=1</code> in .env and restart.</p>",
                403,
            )
        return render_template("kiosk.html")

    # --- CSRF for session-based mutations ---
    CSRF_EXEMPT = {
        "/api/auth/login",
    }

    @app.before_request
    def csrf_protect():
        if request.method not in ("POST", "PUT", "DELETE"):
            return
        if request.path in CSRF_EXEMPT:
            return
        if request.path.startswith("/static/"):
            return
        # Kiosk endpoints are public — skip CSRF check
        if request.path.startswith("/api/kiosk/"):
            return
        if not session.get("user_id"):
            # Not logged in — let route handler return 401/403
            return
        token = session.get("_csrf_token")
        req_token = (
            request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token")
        )
        if not token or token != req_token:
            return jsonify({"error": "CSRF token missing or invalid"}), 403

    @app.after_request
    def set_csrf(response):
        import secrets
        if "user_id" in session and "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(32)
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        return response

    @app.context_processor
    def inject_csrf():
        import secrets
        if "user_id" in session:
            if "_csrf_token" not in session:
                session["_csrf_token"] = secrets.token_hex(32)
            return {"csrf_token": session["_csrf_token"]}
        return {"csrf_token": ""}

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "Request too large"}), 413

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("login.html"), 404

    return app


if __name__ == "__main__":
    app = create_app()
    print("=" * 50)
    print("  LumaAttend - Face Recognition Attendance")
    print("  http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

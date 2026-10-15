from .auth import auth_bp
from .admin import admin_bp
from .attendance import attendance_bp
from .kiosk import kiosk_bp

__all__ = ["auth_bp", "admin_bp", "attendance_bp", "kiosk_bp"]
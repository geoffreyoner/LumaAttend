import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("LUMA_SECRET_KEY") or secrets.token_hex(32)
    DATABASE = os.environ.get(
        "LUMA_DB_PATH", str(BASE_DIR / "instance" / "lumaattend.db")
    )
    TIMEZONE = os.environ.get("LUMA_TIMEZONE", "Asia/Jakarta")
    FACE_MATCH_THRESHOLD = float(
        os.environ.get("LUMA_FACE_THRESHOLD", "0.363")
    )
    FACE_DETECTION_CONFIDENCE = float(
        os.environ.get("LUMA_FACE_DET_CONF", "0.7")
    )
    MAX_LOGIN_ATTEMPTS = int(
        os.environ.get("LUMA_MAX_LOGIN_ATTEMPTS", "5")
    )
    LOGIN_WINDOW_SECONDS = int(
        os.environ.get("LUMA_LOGIN_WINDOW", "300")
    )
    ATTENDANCE_COOLDOWN_SECONDS = int(
        os.environ.get("LUMA_ATT_COOLDOWN", "60")
    )
    KIOSK_SCAN_COOLDOWN_SECONDS = int(os.environ.get("LUMA_KIOSK_SCAN_COOLDOWN", "15"))
    KIOSK_MIN_CHECKOUT_MINUTES = int(os.environ.get("LUMA_KIOSK_MIN_CHECKOUT_MINUTES", "60"))
    MODEL_DIR = BASE_DIR / "models"
    YUNET_MODEL_URL = (
        "https://github.com/opencv/opencv_zoo/raw/main/"
        "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    )
    SFACE_MODEL_URL = (
        "https://github.com/opencv/opencv_zoo/raw/main/"
        "models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
    )
    DEFAULT_CHECK_IN = "08:00"
    DEFAULT_LATE_THRESHOLD = "08:30"

    # Kiosk mode: enable public /kiosk page + /api/kiosk/* endpoints
    KIOSK_MODE = os.environ.get("LUMA_KIOSK_MODE", "0") == "1"

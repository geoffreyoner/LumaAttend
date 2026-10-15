#!/usr/bin/env bash
set -e

echo "=== LumaAttend Installer (Linux / macOS) ==="

# Deteksi distro & install dependency
if command -v apt >/dev/null 2>&1; then
  echo "[apt] Installing system packages..."
  sudo apt update
  sudo apt install -y python3 python3-pip python3-venv git python3-opencv python3-numpy
elif command -v dnf >/dev/null 2>&1; then
  echo "[dnf] Installing system packages..."
  sudo dnf install -y python3 python3-pip git python3-opencv python3-numpy
elif command -v pacman >/dev/null 2>&1; then
  echo "[pacman] Installing system packages..."
  sudo pacman -S --noconfirm python python-pip git python-opencv python-numpy
elif command -v zypper >/dev/null 2>&1; then
  echo "[zypper] Installing system packages..."
  sudo zypper install -y python3 python3-pip git python3-opencv python3-numpy
elif command -v brew >/dev/null 2>&1; then
  echo "[brew] Installing system packages..."
  brew install python@3.12 opencv numpy
else
  echo "WARNING: Package manager tidak dikenali."
  echo "Install manual: python3, python3-pip, python3-venv, opencv, numpy."
fi

# Pilih python binary
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: Python tidak ditemukan."
  exit 1
fi

echo ""
echo "Python yang dipakai: $($PY --version)"

# Rebuild venv kalau ada tapi tidak bisa import cv2/numpy
if [ -d "$HOME/lumaenv" ] && ! "$HOME/lumaenv/bin/python" -c 'import cv2, numpy' >/dev/null 2>&1; then
  echo "Venv lama tidak bisa import cv2/numpy, rebuilding..."
  rm -rf "$HOME/lumaenv"
fi

if [ ! -d "$HOME/lumaenv" ]; then
  $PY -m venv "$HOME/lumaenv" --system-site-packages
  echo "Venv dibuat di $HOME/lumaenv"
fi

source "$HOME/lumaenv/bin/activate"

echo ""
echo "=== Verifikasi OpenCV/NumPy dari venv ==="
python -c "import cv2, numpy; print('OpenCV:', cv2.__version__, '| NumPy:', numpy.__version__)" || {
  echo "ERROR: OpenCV atau NumPy tidak dapat diimpor dari venv."
  echo "Coba hapus venv lama lalu jalankan ulang installer."
  exit 1
}

pip install Flask Werkzeug

mkdir -p instance models static/assets static/css static/js services routes templates
touch instance/.gitkeep models/.gitkeep
touch services/__init__.py routes/__init__.py

if [ ! -f .env ]; then
  SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<EOF
LUMA_SECRET_KEY=${SECRET}
LUMA_DB_PATH=instance/lumaattend.db
LUMA_TIMEZONE=Asia/Jakarta
LUMA_FACE_THRESHOLD=0.363
LUMA_KIOSK_MODE=0
LUMA_KIOSK_SCAN_COOLDOWN=15
LUMA_KIOSK_MIN_CHECKOUT_MINUTES=60
EOF
  echo "Created .env"
fi

echo ""
echo "=== Buat akun admin pertama ==="
echo "Kosongkan (tekan Enter) untuk pakai nilai default."
echo ""

cat > .admin_setup.py <<'PYADMIN'
import sys
sys.path.insert(0, ".")
from app import create_app
from database import get_db
from werkzeug.security import generate_password_hash
import getpass

app = create_app()
conn = get_db()

existing = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
if existing > 0:
    print("Admin sudah ada, dilewati.")
    conn.close()
    raise SystemExit(0)

code = input("Employee code [ADMIN001]: ").strip() or "ADMIN001"
name = input("Full name [Administrator]: ").strip() or "Administrator"
user = input("Username [admin]: ").strip() or "admin"

try:
    pwd = getpass.getpass("Password (min 6 karakter): ")
except (EOFError, KeyboardInterrupt):
    print("\nDibatalkan.")
    conn.close()
    raise SystemExit(1)

if len(pwd) < 6:
    print("ERROR: Password minimal 6 karakter.")
    conn.close()
    raise SystemExit(1)

try:
    conn.execute(
        "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
        "VALUES (?,?,?,?,?)",
        (code, name, user, generate_password_hash(pwd), "admin"),
    )
    conn.commit()
    print("")
    print(f"Admin '{user}' berhasil dibuat.")
    print("Ganti password setelah login pertama lewat halaman Users.")
except Exception as e:
    print(f"ERROR: {e}")
    conn.close()
    raise SystemExit(1)

conn.close()
PYADMIN

python .admin_setup.py
rm -f .admin_setup.py

echo ""
echo "=== Install selesai ==="
echo "Jalankan: bash run-linux.sh"
echo "Buka   : http://127.0.0.1:5000"
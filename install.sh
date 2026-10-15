#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== LumaAttend Installer ==="

pkg update -y
pkg upgrade -y
pkg install -y python python-pip git
pkg install -y opencv-python python-numpy

if [ -d "$HOME/lumaenv" ] && ! "$HOME/lumaenv/bin/python" -c 'import cv2, numpy' >/dev/null 2>&1; then
  echo "Existing venv cannot see Termux OpenCV/NumPy; rebuilding it..."
  rm -rf "$HOME/lumaenv"
fi

if [ ! -d "$HOME/lumaenv" ]; then
  python -m venv "$HOME/lumaenv" --system-site-packages
  echo "Venv created at $HOME/lumaenv"
fi

source "$HOME/lumaenv/bin/activate"

echo ""
echo "=== Verifying OpenCV/NumPy from venv ==="
python -c "import cv2, numpy; print('OpenCV:', cv2.__version__, '| NumPy:', numpy.__version__)" || {
  echo "ERROR: OpenCV atau NumPy tidak dapat diimpor dari venv."
  echo "Coba: rm -rf ~/lumaenv && bash install.sh"
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
echo "Jalankan: bash run.sh"
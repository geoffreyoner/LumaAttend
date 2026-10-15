#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"

# Aktifkan venv
if [ -f "$HOME/lumaenv/bin/activate" ]; then
  source "$HOME/lumaenv/bin/activate"
else
  echo "ERROR: venv not found. Run: bash install.sh"
  exit 1
fi

# Load .env
if [ -f .env ]; then
  set -a; source .env; set +a
fi

python app.py
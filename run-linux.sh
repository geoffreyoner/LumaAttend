#!/usr/bin/env bash
cd "$(dirname "$0")"

if [ -f "$HOME/lumaenv/bin/activate" ]; then
  source "$HOME/lumaenv/bin/activate"
else
  echo "ERROR: venv tidak ditemukan di $HOME/lumaenv"
  echo "Jalankan dulu: bash install-linux.sh"
  exit 1
fi

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

python app.py
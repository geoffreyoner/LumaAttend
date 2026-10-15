# LumaAttend

Sistem absensi berbasis pengenalan wajah realtime yang berjalan **sepenuhnya lokal**. Tidak butuh VPS, cloud, atau internet setelah setup awal. UI bergaya Liquid Glass.

Dua mode:

- **Admin mode** — dashboard, kelola user, register wajah, lihat history, export CSV
- **Kiosk mode** — satu device di depan pintu, user cukup lihat kamera, absen otomatis

---

## Daftar Isi

- [Fitur](#fitur)
- [Requirements](#requirements)
- [Struktur Project](#struktur-project)
- [Instalasi](#instalasi)
  - [Android](#android-terminal-android)
  - [Linux](#linux)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Docker](#docker-opsional)
- [Buat Admin Pertama](#buat-admin-pertama)
- [Cara Pakai — Mode Admin](#cara-pakai--mode-admin)
- [Cara Pakai — Mode Kiosk](#cara-pakai--mode-kiosk)
- [Setup Kiosk Lapangan](#setup-kiosk-lapangan)
- [Konfigurasi](#konfigurasi)
- [API Endpoints](#api-endpoints)
- [Arsitektur](#arsitektur)
- [Privacy & Keamanan](#privacy--keamanan)
- [Troubleshooting](#troubleshooting)
- [Backup & Restore](#backup--restore)
- [Batasan & Catatan Jujur](#batasan--catatan-jujur)
- [Testing](#testing)
- [Lisensi](#lisensi)

---

## Fitur

**Face recognition**
- Pengenalan wajah nyata pakai **YuNet** (deteksi) + **SFace** (embedding) via OpenCV DNN — bukan Haar cascade, bukan pixel matching
- Embedding 128-dimensi, cosine similarity threshold dapat di-tuning
- Model auto-download dari OpenCV Zoo saat first run (timeout + size limit + atomic replace)
- Registrasi wajah via kamera browser, deteksi tepat 1 wajah (tolak 0 atau >1)

**Absensi**
- Check-in / check-out berdasarkan verifikasi wajah backend
- Aturan satu record per user per hari (unique constraint)
- Status otomatis: Hadir / Terlambat (configurable threshold)
- Cooldown per user anti dobel-absensi
- Zona waktu Asia/Jakarta

**Kiosk mode**
- Halaman publik tanpa login untuk satu device
- Auto-scan loop (~3 FPS), auto-detect wajah, auto-record
- Aksi otomatis: check-in / check-out / waiting-checkout / already-complete
- **Minimum interval check-out** (default 60 menit) mencegah wajah sama tercatat in→out dalam beberapa detik
- Per-user scan cooldown untuk mengurangi spam backend
- Screen Wake Lock API agar layar tidak mati
- Kartu sukses animasi + beep sound

**Admin**
- Dashboard statistik harian (total user, hadir, terlambat, belum hadir)
- Grafik trend 7 hari (canvas sederhana)
- Manajemen user (CRUD) + register wajah + hapus template
- Riwayat absensi + filter tanggal/status + pagination
- Export CSV
- Pengaturan: jam kerja, batas keterlambatan, threshold wajah, FPS, retensi

**Keamanan**
- Password hashing Werkzeug (pbkdf2-sha256)
- Session cookie HttpOnly + SameSite=Lax + rotation saat login
- CSRF protection untuk semua endpoint state-changing yang butuh session
- Rate limiting login per IP + kiosk scan per IP
- Admin role revalidate ke DB tiap request
- Validasi input ketat, error tidak expose SQL detail
- Escaping HTML untuk semua data dinamis
- Security headers API (Cache-Control no-store, X-Frame-Options, Referrer-Policy, Permissions-Policy)

**UI**
- Liquid Glass design (backdrop blur, layered glass, ambient lighting)
- Mobile-first, responsif untuk HP dan tablet
- Reduced-motion support
- Fallback untuk browser tanpa `backdrop-filter`
- Toast notification, skeleton loading, modal backdrop blur

**Infrastruktur**
- Flask + SQLite (WAL mode, foreign key ON)
- Virtual environment dengan `--system-site-packages` agar kompatibel dengan package manager sistem
- Model ONNX di folder `models/`, auto-download saat first run
- Test suite 9 kasus (auth, CSRF, aturan absensi, kiosk guard)

---

## Requirements

- **OS**: Android 8+, Linux (Ubuntu/Fedora/Arch/openSUSE), Windows 10+, atau macOS 11+
- **Python**: 3.10 atau lebih baru
- **OpenCV**: 4.8 atau lebih baru (untuk YuNet + SFace API)
- **NumPy**: 1.24 atau lebih baru
- **Ruang**: ~250 MB (termasuk model ONNX)
- **Internet**: hanya saat pertama kali (untuk download model)
- **Browser**: Chrome / Edge / Firefox modern
- **Kamera**: depan atau belakang

---

## Struktur Project

```
LumaAttend/
├── app.py                        # Flask app factory + halaman
├── config.py                     # Konfigurasi env-driven
├── database.py                   # SQLite init + helper setting
├── requirements.txt
├── install.sh                    # Installer Android (pkg)
├── install-linux.sh              # Installer Linux (apt/dnf/pacman)
├── run.sh                        # Runner Android / Linux
├── run-linux.sh                  # Runner Linux (eksplisit)
├── run.bat                       # Runner Windows
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile
├── instance/
│   └── .gitkeep
├── models/
│   └── .gitkeep
├── services/
│   ├── __init__.py
│   ├── face_engine.py
│   ├── attendance_service.py
│   └── liveness_service.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── admin.py
│   ├── attendance.py
│   └── kiosk.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── attendance.html
│   ├── users.html
│   ├── history.html
│   ├── settings.html
│   └── kiosk.html
├── static/
│   ├── css/
│   │   ├── style.css
│   │   └── kiosk.css
│   ├── js/
│   │   ├── app.js
│   │   ├── camera.js
│   │   ├── face-recognition.js
│   │   ├── attendance.js
│   │   ├── users.js
│   │   ├── dashboard.js
│   │   ├── history.js
│   │   └── kiosk.js
│   └── assets/
│       └── logo.svg
└── tests/
    ├── __init__.py
    └── test_app.py
```

---

## Instalasi

Pilih sesuai platform. Kode aplikasi portabel — yang berbeda hanya cara install dependency.

### Android (Terminal Android)

Aplikasi terminal Linux untuk Android. Install dari F-Droid.

#### 1. Persiapan

Buka aplikasi terminal Android, lalu jalankan:

```bash
pkg update && pkg upgrade -y
pkg install -y python python-pip git
pkg install -y opencv-python python-numpy
```

> **Penting:** `opencv-python` dan `python-numpy` **harus** di-install lewat package manager sistem, bukan pip. Tidak ada wheel Android untuk paket itu — pip akan coba compile dari source dan hampir pasti gagal.

#### 2. Copy Project

```bash
cd /storage/emulated/0/CODE
git clone <repo-url> Luma
cd Luma
```

#### 3. Installer

```bash
bash install.sh
```

Script ini:
1. Install paket sistem (python, opencv, numpy)
2. Buat venv di `~/lumaenv` dengan `--system-site-packages`
3. Install Flask + Werkzeug
4. Buat `.env` dengan `LUMA_SECRET_KEY` acak
5. Prompt untuk buat admin pertama

#### 4. Start

```bash
bash run.sh
```

Buka Chrome Android → `http://127.0.0.1:5000`

---

### Linux

Bisa di Ubuntu, Debian, Fedora, Arch, openSUSE, dan turunannya.

#### 1. Install Dependency Sistem

Pilih sesuai distro:

**Ubuntu / Debian / Linux Mint / Pop!_OS:**

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git python3-opencv python3-numpy
```

**Fedora / RHEL / CentOS Stream:**

```bash
sudo dnf install -y python3 python3-pip git python3-opencv python3-numpy
```

**Arch / Manjaro / EndeavourOS:**

```bash
sudo pacman -S --noconfirm python python-pip git python-opencv python-numpy
```

**openSUSE:**

```bash
sudo zypper install -y python3 python3-pip git python3-opencv python3-numpy
```

#### 2. Installer Otomatis

```bash
cd ~/Projects
git clone <repo-url> Luma
cd Luma

bash install-linux.sh
```

Script ini akan deteksi distro, install dependency yang kurang, buat venv, install Flask, generate `.env`, dan prompt untuk buat admin.

#### 3. Start

```bash
bash run-linux.sh
```

Buka browser → `http://127.0.0.1:5000`

#### 4. Install Manual (kalau installer gagal)

```bash
cd ~/Projects/Luma

python3 -m venv ~/lumaenv --system-site-packages
source ~/lumaenv/bin/activate
pip install Flask Werkzeug

mkdir -p instance models

if [ ! -f .env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<EOF
LUMA_SECRET_KEY=${SECRET}
LUMA_DB_PATH=instance/lumaattend.db
LUMA_TIMEZONE=Asia/Jakarta
LUMA_FACE_THRESHOLD=0.363
LUMA_KIOSK_MODE=0
LUMA_KIOSK_SCAN_COOLDOWN=15
LUMA_KIOSK_MIN_CHECKOUT_MINUTES=60
EOF
fi

python app.py
```

---

### Windows

Tiga cara. Pilih yang paling nyaman.

#### Cara A — WSL2 (Recommended)

WSL2 = Linux asli di Windows. Kamera tetap diakses dari browser Windows, jadi tidak ada masalah dengan driver.

1. Install WSL2 dari Microsoft Store → pilih **Ubuntu**
2. Buka Ubuntu, install dependency:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git python3-opencv python3-numpy
```

3. Copy project ke folder WSL (misal `~/Luma`), lalu:

```bash
cd ~/Luma
bash install-linux.sh
bash run-linux.sh
```

4. Buka browser Windows → `http://127.0.0.1:5000`

#### Cara B — Python Native

**1. Install Python**

Download [Python 3.10+](https://www.python.org/downloads/windows/) — centang **"Add Python to PATH"** saat install.

**2. Install dependency**

Buka **PowerShell**:

```powershell
cd C:\path\ke\LumaAttend

python -m venv $env:USERPROFILE\lumaenv
& "$env:USERPROFILE\lumaenv\Scripts\Activate.ps1"

pip install Flask Werkzeug opencv-python numpy
```

> Di Windows, `pip install opencv-python` **memang jalan** — ada wheel resmi. Berbeda dengan Android yang tidak punya wheel.

**3. Generate `.env`**

```powershell
$secret = python -c "import secrets; print(secrets.token_hex(32))"

@"
LUMA_SECRET_KEY=$secret
LUMA_DB_PATH=instance/lumaattend.db
LUMA_TIMEZONE=Asia/Jakarta
LUMA_FACE_THRESHOLD=0.363
LUMA_KIOSK_MODE=0
LUMA_KIOSK_SCAN_COOLDOWN=15
LUMA_KIOSK_MIN_CHECKOUT_MINUTES=60
"@ | Out-File -Encoding ASCII .env

New-Item -ItemType Directory -Force -Path instance, models | Out-Null
```

**4. Jalankan**

```powershell
run.bat
```

Buka browser → `http://127.0.0.1:5000`

#### Cara C — Git Bash

Install [Git for Windows](https://git-scm.com/download/win) → buka Git Bash → ikuti langkah Linux dengan `python` (bukan `python3`).

---

### macOS

#### 1. Install Homebrew (kalau belum ada)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Install Python + OpenCV

```bash
brew install python@3.12 opencv numpy
```

#### 3. Setup Project

```bash
cd ~/Projects
git clone <repo-url> Luma
cd Luma

python3.12 -m venv ~/lumaenv --system-site-packages
source ~/lumaenv/bin/activate
pip install Flask Werkzeug

mkdir -p instance models

if [ ! -f .env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<EOF
LUMA_SECRET_KEY=${SECRET}
LUMA_DB_PATH=instance/lumaattend.db
LUMA_TIMEZONE=Asia/Jakarta
LUMA_FACE_THRESHOLD=0.363
LUMA_KIOSK_MODE=0
LUMA_KIOSK_SCAN_COOLDOWN=15
LUMA_KIOSK_MIN_CHECKOUT_MINUTES=60
EOF
fi
```

#### 4. Start

```bash
python app.py
```

Buka browser → `http://127.0.0.1:5000`

---

### Docker (Opsional)

Cara paling portabel. Backend jalan di container, kamera tetap diakses dari browser host.

Buat `Dockerfile` di root project:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir Flask Werkzeug opencv-python-headless numpy

RUN mkdir -p instance models

EXPOSE 5000

CMD ["python", "app.py"]
```

Build & jalankan:

```bash
docker build -t lumaattend .
docker run --rm -p 5000:5000 \
  -v "$PWD/instance:/app/instance" \
  -v "$PWD/models:/app/models" \
  -v "$PWD/.env:/app/.env:ro" \
  lumaattend
```

Buka browser → `http://localhost:5000`

> **Kamera di Docker:** `getUserMedia` tetap butuh browser di host (bukan di dalam container). Docker hanya menjalankan backend.

---

### Perbandingan Platform

| Platform | Install OpenCV | Waktu | Catatan |
|---|---|---|---|
| Android terminal | `pkg install opencv-python` | ~5 menit | Wajib `--system-site-packages` |
| Ubuntu / Debian | `apt install python3-opencv` | ~3 menit | Paling mudah |
| Fedora | `dnf install python3-opencv` | ~3 menit | — |
| Arch | `pacman -S python-opencv` | ~2 menit | — |
| openSUSE | `zypper install python3-opencv` | ~3 menit | — |
| Windows (WSL2) | Sama seperti Ubuntu | ~10 menit | Install WSL dulu |
| Windows (native) | `pip install opencv-python` | ~5 menit | Ada wheel resmi |
| macOS | `brew install opencv` | ~5 menit | — |
| Docker | Built-in image | ~5 menit | Kamera dari browser host |

---

### Setelah Instalasi

1. **Buat admin pertama** — lihat [Buat Admin Pertama](#buat-admin-pertama)
2. **Buka browser** → `http://127.0.0.1:5000`
3. **Login** → `admin` / password yang kamu isi
4. **Register wajah** → `/users` → Register Face
5. **Mulai absen** → `/attendance` atau aktifkan kiosk mode

Kalau ada error, lihat [Troubleshooting](#troubleshooting).

---

### Catatan Portabilitas

**Yang portabel tanpa perubahan:**

- Semua file `.py` (backend + services + routes)
- Semua file `.html`, `.css`, `.js` (frontend)
- Model ONNX (YuNet + SFace) — file binary yang sama di semua OS
- SQLite database — format file yang sama

**Yang berbeda per platform:**

| Perintah | Android | Linux | Windows |
|---|---|---|---|
| Install paket | `pkg install X` | `apt/dnf/pacman install X` | `pip install X` |
| Aktivasi venv | `source ~/lumaenv/bin/activate` | Sama | `%USERPROFILE%\lumaenv\Scripts\activate` |
| Installer | `install.sh` | `install-linux.sh` | Manual atau `run.bat` |
| Runner | `run.sh` | `run-linux.sh` | `run.bat` |

---

## Buat Admin Pertama

Installer (`install.sh` / `install-linux.sh`) sudah otomatis prompt pembuatan admin. Kalau ingin buat manual:

```bash
cd /path/ke/LumaAttend
source ~/lumaenv/bin/activate

cat > /tmp/luma_admin.py << 'PYEOF'
from app import create_app
from database import get_db
from werkzeug.security import generate_password_hash

app = create_app()
conn = get_db()
conn.execute(
    "INSERT INTO users (employee_code, full_name, username, password_hash, role) "
    "VALUES (?,?,?,?,?)",
    ("ADMIN001", "Administrator", "admin",
     generate_password_hash("admin123"), "admin"),
)
conn.commit()
print("Admin dibuat: admin / admin123")
conn.close()
PYEOF

python /tmp/luma_admin.py
rm -f /tmp/luma_admin.py
```

**Login pertama:** `admin` / `admin123`. Segera ganti password lewat `/users`.

---

## Cara Pakai — Mode Admin

### 1. Login

Buka `http://127.0.0.1:5000`, login dengan kredensial admin.

### 2. Tambah User

`/users` → **+ Add User**:

| Field | Contoh | Aturan |
|---|---|---|
| Employee Code | `EMP001` | unik, wajib |
| Full Name | `Budi Santoso` | wajib |
| Username | `budi` | unik, wajib |
| Password | `budi1234` | minimal **8 karakter** |
| Role | `employee` | employee / admin |

### 3. Register Wajah

- Klik **Register Face** di card user
- Modal terbuka, kamera aktif otomatis
- Posisikan wajah di oval: **1 orang**, cahaya cukup, jarak ~40 cm
- Klik **Capture**
- Backend deteksi tepat 1 wajah → tolak jika 0 atau >1
- Badge user berubah jadi **Face ✓**

### 4. Absensi Manual (user login)

- Buka `/attendance`
- Klik **Start Camera**
- Tunggu status jadi **Recognized: [Nama]**
- Klik **Check In** atau **Check Out**

Backend re-verify dari frame baru. Wajah harus cocok dengan akun yang sedang login.

### 5. History

`/history` → filter tanggal/status → **Export CSV**.

Hanya admin yang bisa akses history lengkap. Employee hanya lihat absensinya sendiri.

---

## Cara Pakai — Mode Kiosk

Kiosk = satu device di depan pintu. User cukup lihat kamera, absen otomatis.

### 1. Aktifkan Kiosk Mode

Edit `.env`:

```bash
sed -i 's/LUMA_KIOSK_MODE=0/LUMA_KIOSK_MODE=1/' .env
grep LUMA_KIOSK_MODE .env
```

Restart server.

### 2. Buka Halaman Kiosk

```
http://127.0.0.1:5000/kiosk
```

Kamera auto-start. Setiap orang yang hadapkan wajah akan mendapat salah satu aksi:

| Aksi | Kapan terjadi | UI |
|---|---|---|
| `check-in` | Belum ada record hari ini | Kartu hijau "Check-in berhasil" |
| `waiting-checkout` | Sudah check-in, belum lewat 60 menit | Kartu "Check-out tersedia X menit lagi" |
| `check-out` | Sudah check-in, sudah lewat minimum interval | Kartu hijau "Check-out berhasil" |
| `already-complete` | Sudah check-in dan check-out hari ini | Kartu info "Absensi hari ini sudah lengkap" |

Kartu sukses muncul 4–4.5 detik, lalu reset.

### 3. Fullscreen

Chrome → **⋮** → **Add to Home screen** → buka dari ikon.

### 4. Wake Lock

`kiosk.js` otomatis pakai **Screen Wake Lock API** supaya layar tidak mati. Kalau browser tidak support, aktifkan manual di sistem: **Settings** → **Display** → **Screen timeout** → **Never** (saat charger tercolok).

### 5. Auto-Start Server (Opsional)

Di Android, gunakan aplikasi boot-runner untuk menjalankan `run.sh` saat HP menyala. Di Linux, gunakan `systemd` service atau `crontab @reboot`.

---

## Setup Kiosk Lapangan

### Hardware

- HP Android bekas, RAM ≥ 2 GB, kamera depan ≥ 5 MP
- Holder / tripod tinggi ~150 cm, layar sejajar mata
- Charger permanen + kabel panjang
- Cahaya cukup (hindari backlight)

### Posisi

- Layar menghadap pintu masuk, jarak user ~40–60 cm
- Background polos
- Antrean: 1 orang per 4 detik

### Optimasi

- Chrome: matikan auto-update tab, matikan sinkronisasi
- Android: aktifkan **Stay awake** (Developer Options) saat charger
- Aktifkan wake lock agar server tidak di-kill

### Maintenance

- Backup DB mingguan
- Bersihkan cache Chrome bulanan
- Update template wajah saat ada user baru

---

## Konfigurasi

Semua via `.env` (dibuat otomatis oleh installer):

| Variabel | Default | Keterangan |
|---|---|---|
| `LUMA_SECRET_KEY` | auto random | Kunci Flask session — **jangan diganti setelah dipakai** |
| `LUMA_DB_PATH` | `instance/lumaattend.db` | Path SQLite |
| `LUMA_TIMEZONE` | `Asia/Jakarta` | Zona waktu absensi |
| `LUMA_FACE_THRESHOLD` | `0.363` | Threshold cosine similarity. Naikkan untuk lebih ketat (0.40+), turunkan kalau user sering ditolak (0.30) |
| `LUMA_FACE_DET_CONF` | `0.7` | Confidence minimum deteksi wajah |
| `LUMA_MAX_LOGIN_ATTEMPTS` | `5` | Limit login sebelum rate limited |
| `LUMA_LOGIN_WINDOW` | `300` | Window rate limit login (detik) |
| `LUMA_ATT_COOLDOWN` | `60` | Cooldown absensi per user (detik) |
| `LUMA_KIOSK_MODE` | `0` | `1` untuk aktifkan kiosk |
| `LUMA_KIOSK_SCAN_COOLDOWN` | `15` | Cooldown scan per user di kiosk (detik) |
| `LUMA_KIOSK_MIN_CHECKOUT_MINUTES` | `60` | Minimum interval check-in → check-out di kiosk |

Setting juga bisa diubah runtime via **`/settings`**.

---

## API Endpoints

### Auth (session)

| Method | Path | Auth | Body |
|---|---|---|---|
| POST | `/api/auth/login` | — | `{username, password}` |
| POST | `/api/auth/logout` | session | — |
| GET | `/api/auth/me` | session | — |

### Admin (session + role admin)

| Method | Path | Body |
|---|---|---|
| GET | `/api/dashboard/stats` | — |
| GET | `/api/users?q=` | — |
| POST | `/api/users` | `{employee_code, full_name, username, password (≥8), role}` |
| GET | `/api/users/<id>` | — |
| PUT | `/api/users/<id>` | `{employee_code?, full_name?, username?, password?, role?, is_active?}` |
| DELETE | `/api/users/<id>` | — (hapus template wajah) |
| POST | `/api/face/register` | `{user_id, image}` |
| POST | `/api/face/verify` | `{image}` (session) |
| GET | `/api/settings` | — |
| PUT | `/api/settings` | key-value setting |

### Attendance (session)

| Method | Path | Body |
|---|---|---|
| POST | `/api/attendance/check-in` | `{image}` |
| POST | `/api/attendance/check-out` | `{image}` |
| GET | `/api/attendance/today` | — |
| GET | `/api/attendance/history?from=&to=&status=&page=` | — (admin only) |
| GET | `/api/attendance/export.csv` | — (admin only) |

### Kiosk (public, hanya jika `LUMA_KIOSK_MODE=1`)

| Method | Path | Body |
|---|---|---|
| POST | `/api/kiosk/scan` | `{image}` |
| GET | `/api/kiosk/status` | — |

### Contoh Error JSON

```json
{"error": "CSRF token missing or invalid"}
{"error": "Not authenticated"}
{"error": "Admin access required"}
{"error": "Password minimal 8 karakter"}
{"error": "No face detected"}
{"error": "Multiple faces (2)"}
{"error": "Wajah tidak cocok dengan akun yang sedang login"}
{"matched": false, "similarity": 0.21, "message": "No match above threshold"}
{"matched": true, "action": "waiting-checkout", "remaining_minutes": 42}
```

---

## Arsitektur

```
┌──────────────────────────────────────────────┐
│  Browser (Chrome / Edge / Firefox)           │
│  ┌────────────────────────────────────────┐  │
│  │  getUserMedia → <video>                │  │
│  │  Canvas frame capture (~3-4 FPS)       │  │
│  │  POST base64 JPEG via apiFetch         │  │
│  └──────────────────┬─────────────────────┘  │
└─────────────────────┼────────────────────────┘
                      │ HTTP (127.0.0.1)
┌─────────────────────▼────────────────────────┐
│  Flask                                       │
│  ┌────────────────────────────────────────┐  │
│  │  before_request: CSRF check            │  │
│  │  after_request: security headers       │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │  routes/attendance.py  (session)       │  │
│  │  routes/kiosk.py       (public)        │  │
│  │  routes/admin.py       (admin + DB)    │  │
│  └──────────────────┬─────────────────────┘  │
│                     ▼                        │
│  ┌────────────────────────────────────────┐  │
│  │  services/face_engine.py               │  │
│  │   ├─ YuNet ONNX (deteksi)              │  │
│  │   ├─ SFace ONNX (embedding 128-d)      │  │
│  │   └─ cosine similarity + threshold     │  │
│  └──────────────────┬─────────────────────┘  │
│                     ▼                        │
│  ┌────────────────────────────────────────┐  │
│  │  services/attendance_service.py        │  │
│  │   ├─ aturan absensi, timezone          │  │
│  │   ├─ BEGIN IMMEDIATE untuk kiosk       │  │
│  │   └─ minimum interval check-out        │  │
│  └──────────────────┬─────────────────────┘  │
│                     ▼                        │
│  ┌────────────────────────────────────────┐  │
│  │  SQLite — instance/lumaattend.db       │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

Face recognition berjalan **sepenuhnya di backend Python**, bukan di browser. Browser hanya kirim frame JPEG.

---

## Privacy & Keamanan

- **Tidak ada upload ke cloud** — semua data lokal di SQLite
- **Foto mentah tidak disimpan** — hanya embedding (array 128 float) sebagai JSON string
- **Embedding tidak terenkripsi** di SQLite — jaga akses file `.db`
- **Session cookie** Flask signed + HttpOnly + SameSite=Lax; rotation saat login
- **CSRF** untuk semua endpoint state-changing yang butuh session
- **Rate limit** login per IP + kiosk scan per IP
- **Password** hashing Werkzeug (pbkdf2-sha256)
- **Admin role** direvalidate ke DB tiap request
- **Validasi input** ketat; error tidak expose SQL detail
- **Escaping HTML** untuk semua data user
- **Wajah user bisa dihapus** — Users → Delete Face

**Data biometrik adalah data pribadi sensitif.** Dapatkan persetujuan eksplisit dari setiap user sebelum registrasi wajah. Sediakan mekanisme penghapusan (sudah ada) dan retensi.

---

## Troubleshooting

### pip error saat install

| Error | Fix |
|---|---|
| `Installing pip is forbidden` | Jangan `pip install --upgrade pip` |
| `Failed building wheel for opencv` | Pakai package manager sistem, bukan pip |
| `No module named 'numpy'` | Rebuild venv: `rm -rf ~/lumaenv && bash install.sh` (atau `install-linux.sh`) |

### Kamera hitam / tidak muncul

- Chrome Settings → Site settings → `127.0.0.1` → Camera → Allow
- Tutup tab `/attendance` sebelum buka modal register (kamera hanya bisa 1 tab)
- Force-stop app kamera lain
- Hard reload halaman

### CSRF token missing atau invalid

- Hard reload halaman
- Cek `.env` — `LUMA_SECRET_KEY` harus ada dan tetap
- Clear cookies browser untuk `127.0.0.1`

### "No registered faces in system"

Buka `/users` → **Register Face** minimal satu user.

### "No face detected" terus

- Cahaya cukup, hindari backlight
- 1 orang saja di frame
- Jarak 30–50 cm, wajah mengisi ~60% oval

### 500 pada `/api/face/register`

Cek traceback. Error umum: `sqlite3.ProgrammingError: type 'list' is not supported` — artinya `embedding_to_json` return list bukan string JSON. Harus `json.dumps(emb.tolist())`.

### `IndentationError` atau `TabError`

Ada tab nyasar di file `.py`. Cek:

```bash
cd /path/ke/LumaAttend
find . -name "*.py" -not -path "./__pycache__/*" -exec grep -lP '\t' {} \;
```

Fix otomatis:

```bash
python - << 'PYEOF'
from pathlib import Path
for p in Path(".").rglob("*.py"):
    if "__pycache__" in str(p): continue
    src = p.read_text()
    fixed = src.replace("\t", "    ")
    if fixed != src:
        p.write_text(fixed)
        print("fixed:", p)
PYEOF
```

### Address already in use

```bash
# Linux / macOS
pkill -f "python app.py"

# Windows
taskkill /F /IM python.exe
```

### Kiosk: kamera jalan tapi tidak auto-absen

- Cek `/api/kiosk/status` — apakah `kiosk: true`?
- Cek `.env` — `LUMA_KIOSK_MODE=1`
- Restart server setelah ubah `.env`

### Kiosk: user sama langsung in→out

Sudah dicegah dengan `min_checkout_minutes`. Kalau masih terjadi:
- Cek `kiosk_min_checkout_minutes` di `/settings`
- Restart server

### Wajah tidak dikenali padahal sudah register

- Turunkan threshold di `/settings` (coba `0.30`)
- Register ulang dengan cahaya lebih baik

---

## Backup & Restore

### Backup manual

```bash
mkdir -p ~/backups
cp /path/ke/LumaAttend/instance/lumaattend.db \
   ~/backups/lumaattend_$(date +%Y%m%d_%H%M%S).db
```

### Restore

```bash
cp ~/backups/lumaattend_20261015_120000.db \
   /path/ke/LumaAttend/instance/lumaattend.db
```

### Backup otomatis (Linux / macOS)

```bash
crontab -e
# Tambahkan:
# 0 3 * * * cp /path/ke/LumaAttend/instance/lumaattend.db ~/backups/lumaattend_$(date +\%Y\%m\%d).db
```

### Backup otomatis (Windows Task Scheduler)

Buat `backup.bat`:

```bat
@echo off
set SRC=C:\path\ke\LumaAttend\instance\lumaattend.db
set DST=%USERPROFILE%\backups\lumaattend_%date:~-4%%date:~3,2%%date:~0,2%.db
copy "%SRC%" "%DST%"
```

Daftarkan di **Task Scheduler** → daily.

---

## Batasan & Catatan Jujur

Aplikasi ini **fungsional dan akurat** untuk skenario low-risk small-scale, tapi **bukan** enterprise-grade:

- **Anti-spoofing tidak aktif** — file `liveness_service.py` ada, tapi belum di-wire ke endpoint. Foto wajah orang bisa dipakai untuk nipu sistem.
- **HTTP only** — kamera hanya jalan di `127.0.0.1` / localhost / HTTPS. Akses dari IP LAN lewat HTTP akan diblokir browser.
- **SQLite** — tidak ideal untuk > 10 concurrent writer. Untuk skala lebih besar, migrasi ke PostgreSQL.
- **Server di HP** — baterai terkuras, sistem bisa kill process background. Butuh wake lock.
- **Embedding tidak terenkripsi** — jaga akses file `.db`. Backup berisi data biometrik.
- **Belum ada audit log** — siapa edit user / hapus wajah tidak terlacak.
- **Belum diuji multi-device** — dirancang untuk 1 device kiosk.

Untuk skenario low-risk (kantor kecil ≤ 30 user, satu pintu masuk, tim jujur), aplikasi ini layak pakai. Untuk audit hukum atau skala > 50 user, perlu hardening tambahan.

---

## Testing

```bash
cd /path/ke/LumaAttend
source ~/lumaenv/bin/activate   # Windows: %USERPROFILE%\lumaenv\Scripts\activate

pip install pytest
pytest tests/ -v
```

Test suite cover:

- Login invalid ditolak
- Login missing fields ditolak
- Endpoint admin butuh auth
- Create user + login sukses
- Aturan anti double check-in
- Check-out tanpa check-in ditolak
- CSRF protection aktif
- Kiosk disabled by default
- History butuh auth

**Manual test:**

1. Buka `/users` → Add User → cek validation error (password < 8 char, username duplikat)
2. Register wajah dengan 0 wajah → tolak "No face detected"
3. Register wajah dengan 2 wajah → tolak "Multiple faces"
4. Buka `/attendance` → Start Camera → wajah lain → "Looking for face..."
5. Login sebagai employee → buka `/history` → 403
6. Kiosk: scan wajah sama 2x dalam 10 detik → yang kedua balas `waiting-checkout`
7. Export CSV → cek format buka di spreadsheet

---

## Lisensi

MIT — bebas dipakai dan dimodifikasi.

Model wajah (YuNet, SFace) berasal dari [OpenCV Zoo](https://github.com/opencv/opencv_zoo) dengan lisensi Apache 2.0.

---

## Referensi

- [YuNet face detector](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [SFace face recognition](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
- [OpenCV FaceDetectorYN docs](https://docs.opencv.org/4.x/df/d20/classcv_1_1FaceDetectorYN.html)
- [Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API)
- [getUserMedia secure context](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
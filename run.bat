@echo off
cd /d "%~dp0"

set VENV=%USERPROFILE%\lumaenv

if not exist "%VENV%\Scripts\activate.bat" (
    echo ERROR: venv tidak ditemukan di %VENV%
    echo Buat dulu venv manual:
    echo   python -m venv %VENV%
    echo   %VENV%\Scripts\activate.bat
    echo   pip install Flask Werkzeug opencv-python numpy
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"

if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "%%a=%%b"
    )
)

python app.py

pause
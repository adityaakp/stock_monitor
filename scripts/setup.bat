@echo off
REM Setup script: bikin venv dan install dependencies
cd /d "%~dp0\.."

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist config\settings.yaml (
    echo Copying settings.example.yaml to settings.yaml...
    copy config\settings.example.yaml config\settings.yaml
    echo.
    echo === PENTING ===
    echo Edit config\settings.yaml dan isi bot_token + chat_id Telegram.
    echo Lihat instruksi di bagian atas file tersebut.
)

echo.
echo Setup selesai. Jalankan: scripts\run.bat

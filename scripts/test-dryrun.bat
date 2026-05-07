@echo off
REM Test analisis tanpa kirim Telegram (cek dulu sebelum setup bot)
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m src.main --dry-run

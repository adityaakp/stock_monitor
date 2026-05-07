@echo off
REM Jalankan bot Telegram interaktif (terima command /list, /scan, dst.)
REM Mode hybrid: kalau schedule.run_mode=interval di settings.yaml,
REM auto-scan periodik tetap jalan di background.
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m src.main --bot %*

@echo off
title NewsPulse Horizon Setup
echo =====================================
echo          NewsPulse Horizon Setup
echo =====================================
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Setup failed. Check your internet connection and Python installation.
  pause
  exit /b 1
)
echo.
echo Setup completed successfully.
pause

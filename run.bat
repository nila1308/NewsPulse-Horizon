@echo off
title NewsPulse Horizon
if not exist .venv\Scripts\activate.bat (
  echo Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate
python app.py
pause

@echo off
cd /d "%~dp0"
title ComplainSense server
if not exist venv\Scripts\python.exe (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
echo Starting ComplainSense at http://127.0.0.1:5000  ^(close this window to stop^)
start "" http://127.0.0.1:5000
venv\Scripts\python.exe app.py
pause

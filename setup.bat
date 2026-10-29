@echo off
setlocal
cd /d "%~dp0"
title ComplainSense setup
echo ============================================
echo  ComplainSense - one-time setup
echo ============================================
echo.
set PY=python
where python >/dev/null 2>nul
if errorlevel 1 set PY=py
%PY% --version
if errorlevel 1 (
  echo.
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and TICK "Add python.exe to PATH" on the first screen of the installer.
  pause
  exit /b 1
)
echo.
echo [1/4] Creating a private Python environment ^(venv^)...
%PY% -m venv venv
if errorlevel 1 ( echo Could not create venv. & pause & exit /b 1 )
echo.
echo [2/4] Installing Flask, Pandas, Matplotlib and pytest ^(needs internet, takes a few minutes^)...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo Package install failed. Check your internet and run setup.bat again. & pause & exit /b 1 )
echo.
echo [3/4] Creating the database, admin account and SAMPLE data...
venv\Scripts\python.exe seed.py --sample
if errorlevel 1 ( echo Database setup failed. & pause & exit /b 1 )
echo.
echo [4/4] Running the automated tests...
venv\Scripts\python.exe -m pytest -q
echo.
echo ============================================
echo  Setup finished. Double-click run.bat to start ComplainSense.
echo  Your admin password is in ADMIN_LOGIN.txt
echo ============================================
pause

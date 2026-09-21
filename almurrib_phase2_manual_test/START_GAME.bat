@echo off
REM Station 7 test harness launcher (ASCII-only on purpose).
REM Prefers Python's server, else the built-in Windows server - nothing to install.
REM The game opens only after a server is confirmed running.
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
  set PY=python
  goto :serve_py
)
where py >nul 2>nul
if errorlevel 1 goto :serve_ps
py -3 --version >nul 2>nul
if errorlevel 1 goto :serve_ps
set PY=py -3
:serve_py
start "Station7 server - KEEP THIS WINDOW OPEN" %PY% -m http.server 8123
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8123/browser/"
exit /b 0
:serve_ps
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SERVE_GAME.ps1"

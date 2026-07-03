@echo off
cd /d "%~dp0"
if not exist "%~dp0python\pythonw.exe" (
  echo [ERROR] Extract the whole zip first.
  pause
  exit /b
)
start "" "%~dp0python\pythonw.exe" "%~dp0app\app_launcher.py"
exit

@echo off
echo ============================================
echo   TW Stock System  -  starting...
echo   First launch takes 20-40 seconds.
echo   A browser tab opens automatically.
echo   Keep this window open  (close it = stop).
echo ============================================
echo.
if not exist "%~dp0python\python.exe" (
  echo [ERROR] python folder missing.
  echo Did you EXTRACT the whole zip first? Run from the extracted folder, not inside the zip.
  echo.
  pause
  exit /b
)
rem 重要：切到 app 目錄當工作目錄，程式才找得到 data\（否則 data 會被找成上一層）
cd /d "%~dp0app"
rem open browser after streamlit is up (15s)
start "" cmd /c "timeout /t 15 >nul & start "" http://localhost:8501"
"%~dp0python\python.exe" -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
echo.
echo Stopped. If it failed above, screenshot the message. Press any key to close.
pause >nul

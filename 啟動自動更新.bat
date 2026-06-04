@echo off
echo 台股自動更新守護程式
echo 每日 14:30 後自動更新股價、籌碼、掃描訊號
echo 請保持此視窗開啟...
echo.
cd /d "G:\Stock\tw_backtest\tw_backtest"
G:\python\python.exe auto_update.py
pause

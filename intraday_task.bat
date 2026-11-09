@echo off
rem tw_backtest intraday engine - weekdays 08:58, exits itself ~13:33
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
G:\python\python.exe intraday_engine.py >> logs\intraday_task.log 2>&1
exit /b 0

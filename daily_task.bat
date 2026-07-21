@echo off
rem tw_backtest daily auto-update (Windows Task Scheduler, weekdays 17:30)
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
G:\python\python.exe run_daily.py >> logs\daily_task.log 2>&1

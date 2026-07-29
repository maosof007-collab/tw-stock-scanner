@echo off
rem tw_backtest daily auto-update - runs 19:30/21:30/23:30 weekdays (retry until fresh)
rem Yahoo TW daily bars appear unreliably between evening and late night,
rem so we retry; the guard below skips the run when data is already current.
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
G:\python\python.exe check_data_current.py && (
  echo %date% %time% data already current, skip >> logs\daily_task.log
  exit /b 0
)
G:\python\python.exe run_daily.py >> logs\daily_task.log 2>&1

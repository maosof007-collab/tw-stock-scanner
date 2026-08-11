@echo off
rem tw_backtest morning brief - 07:15 weekdays, retry every 30min until 09:15
rem script itself skips if today's brief already generated
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
G:\python\python.exe morning_brief.py >> logs\morning_brief.log 2>&1
exit /b 0

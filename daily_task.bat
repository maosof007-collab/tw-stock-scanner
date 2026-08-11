@echo off
rem tw_backtest daily pipeline - slots 15:10/17:10/19:10/21:10/23:10 weekdays
rem 1) official TWSE/TPEX daily append (fast, available ~14:00)
rem 2) if prices fresh and today's scan not done yet -> full run_daily once
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
G:\python\python.exe fetch_daily_official.py >> logs\daily_task.log 2>&1
G:\python\python.exe check_run_needed.py >> logs\daily_task.log 2>&1
if errorlevel 1 (
  G:\python\python.exe run_daily.py >> logs\daily_task.log 2>&1
)
rem margin/short data publishes ~21:00, institutional ~16:00 - keep chips fresh
rem in every evening slot even after run_daily already completed (gap-aware, cheap)
G:\python\python.exe fetch_institutional.py --mode update >> logs\daily_task.log 2>&1
G:\python\python.exe fetch_margin.py --mode update >> logs\daily_task.log 2>&1
rem sync locally-generated Claude artifacts (sentiment/confidence) to git so
rem the cloud app can display them without any API key
git add data/news/sentiment_*.csv scan_results/confidence_*.csv >> logs\daily_task.log 2>&1
git commit -m "data: daily sentiment/confidence sync" >> logs\daily_task.log 2>&1
git pull --rebase origin main >> logs\daily_task.log 2>&1
git push origin main >> logs\daily_task.log 2>&1
exit /b 0

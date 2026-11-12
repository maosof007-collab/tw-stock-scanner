@echo off
rem tw_backtest evening light slot - weekdays 21:25 / 22:25 (task: tw_backtest_evening)
rem Watchdog + notifications ONLY, independent of the heavy daily_task pipeline.
rem Why (2026-11-12): margin data publishes at 21:00; on full-scan days the
rem 15:10 pipeline run killed the 21:10/23:10 repetitions and margin pages
rem stayed a day behind. data_doctor re-fetches whatever is past due and stale.
rem ASCII only - Chinese in .bat breaks on cp950
cd /d G:\Stock\tw_backtest\tw_backtest
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
G:\python\python.exe ssl_trust.py >> logs\daily_task.log 2>&1
set SSL_CERT_FILE=G:\Stock\tw_backtest\tw_backtest\_ca_bundle.pem
set REQUESTS_CA_BUNDLE=G:\Stock\tw_backtest\tw_backtest\_ca_bundle.pem
G:\python\python.exe data_doctor.py >> logs\daily_task.log 2>&1
G:\python\python.exe notify_push.py >> logs\daily_task.log 2>&1
exit /b 0

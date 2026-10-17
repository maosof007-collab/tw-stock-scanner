@echo off
cd /d "G:\Stock\tw_backtest\tw_backtest"
python sentinel_morning.py >> logs\sentinel.log 2>&1

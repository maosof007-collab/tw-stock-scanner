# -*- coding: utf-8 -*-
"""
sentinel_morning.py — 盤前哨兵(輕量):抓隔夜數據→重算風險燈→變化才推 LINE
=================================================================
為什麼需要:run_daily 跑 19:00,但台幣/費半/KOSPI/NVDA 的新數據在半夜才落地
——10/15 教案裡的「提前兩天」訊號,若只靠晚上跑,你早盤前看不到最新燈況。
排程(一次性,系統管理員 PowerShell 執行):
  schtasks /Create /TN tw_sentinel /TR "G:\\Stock\\tw_backtest\\tw_backtest\\sentinel_morning.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:00
耗時 <30 秒;只抓 4 個標的,不動其他資料管線。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    from pathlib import Path as P
    import pandas as pd
    import yfinance as yf
    US = P(__file__).parent / "data" / "us"
    for sym, fn in [("TWD=X", "TWD"), ("^SOX", "SOX"), ("^KS11", "KS11"),
                    ("NVDA", "NVDA")]:
        try:
            d = yf.Ticker(sym).history(period="3mo").reset_index()
            cols = ["Date", "Close"] + (["Volume"] if fn == "NVDA" else [])
            d = d[cols]
            d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
            d.to_csv(US / f"{fn}.csv", index=False)
            print(f"  {fn} → {d['Date'].iloc[-1]}")
        except Exception as e:
            print(f"  {fn} 抓取失敗:{type(e).__name__}")
    from market_risk import assess
    r = assess()
    print(f"  風險燈 {r['lamp']}({r['score']}分)")
    from alert_watch import check_and_push
    print(" ", check_and_push())


if __name__ == "__main__":
    main()

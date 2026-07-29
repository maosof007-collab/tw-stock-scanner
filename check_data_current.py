"""
check_data_current.py — 每日排程守門員
本機資料已是「最近應收盤交易日」→ exit 0（排程跳過重跑）
否則 exit 1（該跑更新）。
"""
import sys
from pathlib import Path

import pandas as pd

from twtime import now_tw


def latest_expected_trading_day():
    """最近一個『已收盤』的交易日（14:00 前不算今天；忽略國定假日，多跑一次無害）"""
    t = now_tw()
    d = pd.Timestamp(t.date())
    if t.weekday() >= 5 or t.hour < 14:
        d -= pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d.date()


def main() -> int:
    p = Path(__file__).parent / "data" / "2330.TW.csv"
    if not p.exists():
        return 1
    try:
        last = pd.to_datetime(pd.read_csv(p, usecols=[0]).iloc[-1, 0]).date()
    except Exception:
        return 1
    expect = latest_expected_trading_day()
    print(f"local={last} expect={expect}")
    return 0 if last >= expect else 1


if __name__ == "__main__":
    sys.exit(main())

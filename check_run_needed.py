"""
check_run_needed.py — 每日完整管線(run_daily)守門員
exit 1 = 該跑 run_daily；exit 0 = 跳過（已跑過 / 價格未到位再等下一槍）
規則：
  今天的訊號檔已存在「且內容是最新價算的」  → 跳過（今天跑過了）
    （2026-11-09 教案：15:41 有程序在價格停在 11/6 時先跑了掃描，
      訊號檔裡日期=11/6，晚間各槍看檔案存在就跳過 → 整晚舊訊號。
      檔案存在不夠，要驗內容日期 = 最新價格日期。）
  價格已是最新交易日                      → 該跑
  價格未到位但已 21 點後（最後保險槍）    → 該跑（讓 yfinance 兜底）
  其餘（價格未到位、時間還早）            → 跳過，等下一槍
"""
import sys
from pathlib import Path

import pandas as pd

from twtime import now_tw
from check_data_current import main as data_current   # 0=最新, 1=落後

ROOT = Path(__file__).parent


def _sig_fresh(sig: Path) -> bool:
    """訊號檔內容是否以最新價格算出（日期欄 max ≥ benchmark max）。"""
    try:
        sd = str(pd.read_csv(sig, usecols=["日期"])["日期"].max())[:10]
        bd = str(pd.read_csv(ROOT / "data" / "benchmark_TWII.csv",
                             usecols=["Date"])["Date"].max())[:10]
        return sd >= bd
    except Exception:
        return True  # 驗不出來就當新鮮，避免無限重跑


def main() -> int:
    t = now_tw()
    sig = ROOT / "scan_results" / f"signals_{t:%Y%m%d}.csv"
    if sig.exists():
        if _sig_fresh(sig):
            print("今日已完整跑過（訊號檔存在且為最新價）→ 跳過")
            return 0
        print("訊號檔存在但內容是舊價算的 → 重跑")
        return 1
    if data_current() == 0:
        print("價格已最新、今日尚未掃描 → 該跑")
        return 1
    if t.hour >= 21:
        print("價格未到位但已過 21:00 → 保險槍，強制跑")
        return 1
    print("價格未到位、時間還早 → 等下一槍")
    return 0


if __name__ == "__main__":
    sys.exit(main())

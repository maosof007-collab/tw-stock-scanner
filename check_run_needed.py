"""
check_run_needed.py — 每日完整管線(run_daily)守門員
exit 1 = 該跑 run_daily；exit 0 = 跳過（已跑過 / 價格未到位再等下一槍）
規則：
  今天的訊號檔已存在                      → 跳過（今天跑過了）
  價格已是最新交易日                      → 該跑
  價格未到位但已 21 點後（最後保險槍）    → 該跑（讓 yfinance 兜底）
  其餘（價格未到位、時間還早）            → 跳過，等下一槍
"""
import sys
from pathlib import Path

from twtime import now_tw
from check_data_current import main as data_current   # 0=最新, 1=落後


def main() -> int:
    t = now_tw()
    sig = Path(__file__).parent / "scan_results" / f"signals_{t:%Y%m%d}.csv"
    if sig.exists():
        print("今日已完整跑過（訊號檔存在）→ 跳過")
        return 0
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

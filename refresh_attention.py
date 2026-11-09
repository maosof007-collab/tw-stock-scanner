# -*- coding: utf-8 -*-
"""
refresh_attention.py — 榜單過期自動重掃(自我防護)
=================================================================
教案(2026-11-06 崩盤日):TWSE 出檔慢,15:11 只有 26 檔有新價,run_daily 照跑,
_attention.csv 的榜停在 11-05;signals 檔已存在 → 之後各槍都跳過,整晚沒人重掃。
後果:short_watch 隔天(11-09)拿舊榜當空方候選。
這支每個晚間槍都跑(daily_task.bat),自我防護:
  _attention.csv 的日期 < benchmark 最新日期 → 重跑 attention_scan.scan() 刷新榜單。
只刷榜,不重推 LINE(分層鐵律:日誌全收、推播濃縮,Flex 已推過就不吵)。
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", usecols=["Date"])
    px_date = str(bm["Date"].max())[:10]
    att = ROOT / "data" / "_attention.csv"
    try:
        cur = str(pd.read_csv(att, usecols=["日期"])["日期"].iloc[0])[:10]
    except Exception:
        cur = ""
    if cur >= px_date:
        print(f"榜單已最新({cur})")
        return 0
    print(f"榜單過期({cur} < 價格 {px_date})→ 重掃")
    import attention_scan
    res = attention_scan.scan()
    new = str(res["meta"]["date"])[:10]
    print(f"重掃完成:榜日 {new}、{res['meta']['n']} 檔")
    try:  # 回放歷史同步補
        import attention_replay
        attention_replay.update()
    except Exception as e:
        print("hist 更新失敗(不致命):", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())

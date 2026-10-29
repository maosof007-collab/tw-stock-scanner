# -*- coding: utf-8 -*-
"""
notify_push.py — 通知獨立跑者(與 run_daily 脫鉤;每個排程時段都執行)
=================================================================
起因(2026-10-28):run_daily 是 90 分鐘的單體,兩天內兩次中途陣亡
(10/27 tpex ReadTimeout、10/28 月營收回補 ChunkedEncodingError),
而訊號鎖開跑即寫 → 後續時段全跳過 → 排在隊尾的 LINE 步驟連續陪葬。
修法:通知不再搭管線便車。本腳本每個時段獨立執行,四步各自 try/except:
  ① 風險燈重算(便宜,每次都算)   ② 哨兵(變化驅動,無變化不推)
  ③ 日報 LINE(17:00 後;一天一次)  ④ 強勢資金 Flex(17:00 後;一天一次)
各步內建防重複標記,多跑無害——寧可空轉,不可沉默。
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from twtime import now_tw


def _step(name: str, fn) -> None:
    try:
        print(f"[notify] {name}:{fn()}")
    except Exception as e:
        print(f"[notify] {name} 失敗:{type(e).__name__}: {e}")
        traceback.print_exc()


def main() -> None:
    print(f"[notify] ---- {now_tw():%Y-%m-%d %H:%M} ----")

    def lamp():
        from market_risk import assess
        r = assess()
        return f"{r['lamp']}({r['score']}分)"
    _step("風險燈", lamp)

    def sentinel():
        from alert_watch import check_and_push
        return check_and_push()
    _step("哨兵", sentinel)

    # 日報與 Flex 要等法人/融資資料(16:00/21:00 後較齊);17:00 前的時段只顧燈
    if now_tw().hour >= 17:
        def digest():
            from daily_line import push
            return push()
        _step("日報LINE", digest)

        def flex():
            from attention_scan import push_flex_daily
            return push_flex_daily()
        _step("強勢Flex", flex)

        def faces():
            from new_faces import push
            return push()
        _step("新面孔雷達", faces)
    else:
        print("[notify] 17:00 前時段:日報/Flex 留給晚間時段")


if __name__ == "__main__":
    main()

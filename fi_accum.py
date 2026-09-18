"""
fi_accum.py — 外資悄悄買榜(小型股外資連續累積掃描)
=================================================================
起源:使用者用 WantGoo 一張張對「外資持股爬升+投信0+融資高」的小型股
(東捷8064/久元6261/天品6199 同指紋)→ 量化成姐妹榜(權證佈局榜的外資版)。
定義:週淨買超(5交易日一桶)連續 ≥N 週為正 + 小型股流動性帶。
資料:data/institutional/(日買賣超累積,非持股存量——誠實標註)。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent


def fi_accum_scan(min_weeks: int = 4, lot_lo: int = 200, lot_hi: int = 8000) -> pd.DataFrame:
    """外資連續累積 ≥min_weeks 週的小型股(20日均量 lot_lo~lot_hi 張)。
    回傳:連續週數/12週累積張數/吸籌強度(累積÷日均量)/價格位置/交叉儀表。"""
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))
    try:
        pan = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv")
    except Exception:
        pan = pd.DataFrame()
    rows = []
    for f in glob.glob(str(ROOT / "data" / "institutional" / "*_inst.csv")):
        code = os.path.basename(f).split("_")[0]
        pf = None
        for suf in (".TW", ".TWO"):
            p = ROOT / "data" / f"{code}{suf}.csv"
            if p.exists():
                pf = p
                break
        if pf is None:
            continue
        try:
            d = pd.read_csv(pf, usecols=["Date", "Close", "Volume"]).dropna().sort_values("Date")
            if len(d) < 130:
                continue
            v = pd.to_numeric(d["Volume"], errors="coerce")
            mv20 = float(v.tail(20).mean()) / 1000
            if not (lot_lo <= mv20 <= lot_hi):
                continue                          # 小型股流動性帶
            i = pd.read_csv(f, usecols=lambda x: x in
                            ("date", "外陸資買賣超股數(不含外資自營商)", "it_net"))
            i = i.dropna(subset=["date"]).sort_values("date")
            fi = pd.to_numeric(i["外陸資買賣超股數(不含外資自營商)"], errors="coerce").fillna(0) / 1000
            if len(fi) < 60:
                continue
            # 5交易日一桶 → 週淨買超序列(近12桶)
            tail = fi.tail(60).reset_index(drop=True)
            weeks = [float(tail.iloc[k:k + 5].sum()) for k in range(0, 60, 5)]
            streak = 0
            for w in reversed(weeks):
                if w > 0:
                    streak += 1
                else:
                    break
            if streak < min_weeks:
                continue
            cum12 = float(sum(weeks))
            strength = cum12 / max(mv20, 1)       # 吸籌強度:12週累積=幾天的日均量
            it10 = float(pd.to_numeric(i["it_net"], errors="coerce").fillna(0)
                         .tail(10).sum()) / 1000
            c = pd.to_numeric(d["Close"], errors="coerce")
            close = float(c.iloc[-1])
            hi252 = float(c.tail(252).max())
            big_d = None
            if not pan.empty and code in pan.columns:
                s = pan[code].dropna().tail(4)
                if len(s) >= 2:
                    big_d = round(float(s.iloc[-1] - s.iloc[0]), 2)
            rows.append({"代號": code, "名稱": nm.get(code, ""),
                         "連續週數": streak,
                         "12週累積(張)": round(cum12),
                         "吸籌強度(日均量倍)": round(strength, 1),
                         "現價": round(close, 1),
                         "距年高%": round((close / hi252 - 1) * 100, 1),
                         "20日均量(張)": round(mv20),
                         "投信10日(張)": round(it10),
                         "大戶4週Δpp": big_d})
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["連續週數", "吸籌強度(日均量倍)"], ascending=False)
    return df


if __name__ == "__main__":
    df = fi_accum_scan()
    print(len(df), "檔")
    print(df.head(20).to_string(index=False))

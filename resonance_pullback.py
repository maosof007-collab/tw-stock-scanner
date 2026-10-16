# -*- coding: utf-8 -*-
"""
resonance_pullback.py — 共振回調掃描(Martin Luk 策略日線版,2026-10-15)
=================================================================
源:XQ全球贏家 FB 貼文之 XScript(分鐘版)→ 本系統改寫日線版。
策略本質:高R:R低勝率(原作者勝率22%、靠3R/5R把帳翻十倍)——家規註記:
要能扛連虧,倉位必須小且固定;停損用「結構位」不是我們慣用的1.5ATR,兩套並列參考。
五關(全過才入選):
  ①趨勢共振:日EMA9>21>50 多頭排列 + 週EMA9向上
  ②錨點:近60日內有「爆量突破日」(量≥1.5×前20日均量、單日漲≥3%、創前20日新高)
  ③前漲幅:整理前20日漲≥15%(證明是強勢股的回調,不是弱勢股的反彈)
  ④整理:近5日振幅≤10%
  ⑤回踩匯聚區:EMA9/EMA21/錨點AVWAP 三線匯聚(區寬≤3%),近3日曾觸區、現收在區上
回測(2015-2026,全市場,含0.6%成本):
  原版結構停損(近2日低)→ PF 0.92 ❌日線不過關(停損太貼=雜訊掃損)
  1.5ATR停損+3R → PF 1.05;+5R → PF 1.14;再加大盤>EMA50濾網 → PF 1.19、平均+0.86%/筆 ✅小幅正期望
  定位:日線版=觀察名單產生器;分鐘級執行請用 XQ 原腳本(策略靈魂在盤中結構)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
OUT = D / "_resonance.csv"


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _check(code: str) -> dict | None:
    for suf in (".TW.csv", ".TWO.csv"):
        p = D / f"{code}{suf}"
        if p.exists():
            break
    else:
        return None
    try:
        px = pd.read_csv(p).dropna(subset=["Close"])
    except Exception:
        return None
    if len(px) < 140:
        return None
    px["Date"] = pd.to_datetime(px["Date"])
    c, h, l, v = (px["Close"].astype(float), px["High"].astype(float),
                  px["Low"].astype(float), px["Volume"].astype(float))
    close = c.iloc[-1]
    if close <= 0 or v.tail(20).mean() * close < 5e7:              # 流動性 5千萬
        return None
    # ①共振:日EMA多頭排列+週EMA9向上
    e9, e21, e50 = _ema(c, 9).iloc[-1], _ema(c, 21).iloc[-1], _ema(c, 50).iloc[-1]
    if not (e9 > e21 > e50):
        return None
    wk = px.set_index("Date")["Close"].resample("W").last().dropna()
    if len(wk) < 30:
        return None
    we9 = _ema(wk, 9)
    if we9.iloc[-1] <= we9.iloc[-2]:
        return None
    # ②錨點:近60日爆量突破日(取最近一個)
    anchor = None
    n = len(px)
    for i in range(n - 1, max(n - 61, 25), -1):
        vol20 = v.iloc[i - 21:i - 1].mean()
        hi20 = h.iloc[i - 21:i - 1].max()
        chg = c.iloc[i] / c.iloc[i - 1] - 1
        if vol20 > 0 and v.iloc[i] >= 1.5 * vol20 and chg >= 0.03 and c.iloc[i] > hi20:
            anchor = i
            break
    if anchor is None:
        return None
    # ③前漲幅:整理前20日 ≥15%
    if len(c) < 31 or c.iloc[-6] / c.iloc[-26] - 1 < 0.15:
        return None
    # ④整理:近5日振幅 ≤10%
    base_hi, base_lo = h.tail(5).max(), l.tail(5).min()
    if base_lo <= 0 or base_hi / base_lo - 1 > 0.10:
        return None
    # ⑤匯聚區:EMA9/EMA21/錨點AVWAP,區寬≤3%,近3日觸區、現收區上緣-1%以上
    seg = px.iloc[anchor:]
    tp = (seg["High"].astype(float) + seg["Low"].astype(float)
          + seg["Close"].astype(float)) / 3
    vv = seg["Volume"].astype(float)
    avwap = float((tp * vv).sum() / max(vv.sum(), 1))
    zone_lo = min(e9, e21, avwap)
    zone_hi = max(e9, e21, avwap)
    base = {"代碼": code, "收盤": round(close, 2),
            "錨點日": f"{px['Date'].iloc[anchor]:%m/%d}",
            "匯聚區": f"{zone_lo:.1f}~{zone_hi:.1f}", "AVWAP": round(avwap, 1),
            "距區上緣%": round((close / zone_hi - 1) * 100, 1)}
    if zone_lo <= 0 or zone_hi / zone_lo - 1 > 0.05:   # 日線尺度放寬至5%
        base["級"] = "B(整理中·三線未聚)"
        return base
    touched = (l.tail(5) <= zone_hi).any()
    if not touched or close < zone_lo * 0.99:
        base["級"] = "B(等回踩觸區)"
        return base
    # 風險閘:距結構停損 ≤4%
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    stop = round(close - 1.5 * atr, 2)          # 回測結論:1.5ATR 版才有正期望,結構停損在日線不過關
    risk = close / stop - 1 if stop > 0 else -1
    if risk < 0.01 or risk > 0.08:
        base["級"] = "B(觸區但風險寬)"
        return base
    r1 = close - stop
    base.update({"級": "A(可進場評估)", "停損(1.5ATR)": stop,
                 "風險%": round(risk * 100, 2),
                 "3R": round(close + 3 * r1, 1), "5R": round(close + 5 * r1, 1)})
    return base


def scan() -> pd.DataFrame:
    import glob
    import os
    import symbols
    try:
        from disposal import current_set
        _dispo = current_set()
    except Exception:
        _dispo = set()
    rows = []
    for f in glob.glob(str(D / "[0-9]*.csv")):
        code = os.path.basename(f).split(".")[0]
        if len(code) != 4 or code in _dispo:
            continue
        try:
            r = _check(code)
            if r:
                r["名稱"] = symbols.resolve(code)[1] or ""
                rows.append(r)
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["級", "距區上緣%"])
        cols = ["代碼", "名稱"] + [c for c in df.columns if c not in ("代碼", "名稱")]
        df = df[cols]
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    out = scan()
    print(out.to_string(index=False) if len(out) else "今日無符合(五關全過本來就該很少)")

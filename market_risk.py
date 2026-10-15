# -*- coding: utf-8 -*-
"""
market_risk.py — 大盤風險燈(2026-10-15,-3.4% 大跌教案)
=================================================================
起因:個股級風控(停損紅點/爆量禁入/體檢卡)一直都有;但大盤級訊號
(融資高檔、外資期貨急空、廣度惡化)只是「儀表」沒有「警報」——10/13 外資
加空 8,138 口、融資 919 萬張高檔,沒有任何紅點。本模組把六個大盤訊號
匯總成一顆燈:🟢(0-1分)/🟡(2-3分)/🔴(≥4分),駕駛艙頂端顯示+待辦紅點。
倉位對接家規:🟡=新倉減半;🔴=禁開新倉、只出不進。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
OUT = D / "_market_risk.json"


def assess() -> dict:
    score, reasons = 0, []
    # ① 大盤位置與單日跌幅
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
        c = bm["Close"].astype(float)
        chg = c.iloc[-1] / c.iloc[-2] - 1
        ema20 = c.ewm(span=20, adjust=False).mean().iloc[-1]
        if chg <= -0.02:
            score += 2
            reasons.append(f"大盤單日 {chg*100:.1f}%(≤-2%)")
        if c.iloc[-1] < ema20:
            score += 1
            reasons.append("大盤跌破 20 日 EMA")
    except Exception:
        pass
    # ② 外資期貨:淨空擴大或單日急變
    try:
        tf = pd.read_csv(D / "_taifex_fi.csv")
        d1 = float(tf["日增減"].iloc[-1]) if len(tf) else 0
        oi = float(tf["淨未平倉口數"].iloc[-1]) if len(tf) else 0
        if d1 <= -5000:
            score += 2
            reasons.append(f"外資期貨單日加空 {abs(d1):,.0f} 口(淨OI {oi:,.0f})")
        elif oi <= -60000:
            score += 1
            reasons.append(f"外資期貨淨空部位沉重({oi:,.0f} 口)")
    except Exception:
        pass
    # ③ 融資:高檔(>900萬張)且維持率走低
    try:
        m = pd.read_csv(D / "_market_margin.csv").dropna()
        lots = float(m["margin_lots"].iloc[-1])
        ratio = float(m["ratio"].iloc[-1])
        d_ratio = ratio - float(m["ratio"].iloc[-2]) if len(m) > 1 else 0
        if lots > 9e6 and d_ratio < -2:
            score += 2
            reasons.append(f"融資 {lots/1e6:.0f}百萬張高檔+維持率單日 {d_ratio:+.1f}pp(減壓賣壓)")
        elif ratio < 150:
            score += 2
            reasons.append(f"融資維持率 {ratio:.0f}%(接近斷頭區)")
        elif lots > 9e6:
            score += 1
            reasons.append(f"融資餘額 {lots/1e6:.1f} 百萬張高檔未退")
    except Exception:
        pass
    # ④ 廣度:跌家數占比與重挫家數
    try:
        import glob
        import os
        up = dn = big = tot = 0
        for f in glob.glob(str(D / "[0-9]*.csv")):
            if len(os.path.basename(f).split(".")[0]) != 4:
                continue
            try:
                px = pd.read_csv(f, usecols=["Close"]).dropna().tail(2)
                if len(px) < 2:
                    continue
                r = px["Close"].iloc[-1] / px["Close"].iloc[-2] - 1
                tot += 1
                if r > 0:
                    up += 1
                else:
                    dn += 1
                    if r < -0.07:
                        big += 1
            except Exception:
                continue
        if tot > 300 and dn / tot > 0.8:
            score += 1
            reasons.append(f"廣度惡化:跌家數佔 {dn/tot*100:.0f}%(重挫>7%:{big} 檔)")
    except Exception:
        pass
    # ⑤ 迴轉率過熱(前日警戒家數)
    try:
        tv = pd.read_csv(D / "_turnover.csv", dtype=str)
        nw = int(tv["隔日沖指紋"].astype(str).str.contains("警戒").sum())
        if nw >= 6:
            score += 1
            reasons.append(f"短線過熱:迴轉率警戒 {nw} 檔")
    except Exception:
        pass
    lamp = "🔴" if score >= 4 else ("🟡" if score >= 2 else "🟢")
    rule = {"🔴": "禁開新倉、只出不進;持倉逐檔對停損", "🟡": "新倉減半、避開高迴轉標的",
            "🟢": "正常紀律"}[lamp]
    out = {"lamp": lamp, "score": score, "reasons": reasons, "rule": rule}
    import json
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = assess()
    print(r["lamp"], f"{r['score']}分|{r['rule']}")
    for x in r["reasons"]:
        print(" -", x)

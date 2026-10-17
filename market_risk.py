# -*- coding: utf-8 -*-
"""
market_risk.py — 大盤風險燈(2026-10-15,-3.4% 大跌教案)
=================================================================
起因:個股級風控(停損紅點/爆量禁入/體檢卡)一直都有;但大盤級訊號
(融資高檔、外資期貨急空、廣度惡化)只是「儀表」沒有「警報」——10/13 外資
加空 8,138 口、融資 919 萬張高檔,沒有任何紅點。本模組把九個大盤訊號(本土槓桿/期貨/廣度/過熱+亞鄰傳染/美股前夜/事件日)
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
    # ⑥ 亞鄰傳染:韓-台價差極端 或 KOSPI 20日重挫(10/15教案:z=-3.2、KOSPI -19.6% 無人升警報)
    try:
        import asia_watch
        snap = asia_watch.asia_snapshot()
        for m in snap.get("markets", []):
            if m["name"] == "韓國" and m.get("chg20") is not None and m["chg20"] <= -15:
                score += 2
                reasons.append(f"亞鄰傳染:KOSPI 20日 {m['chg20']:+.1f}%(風暴中)")
        for s in snap.get("spreads", []):
            if s["pair"].startswith("韓國") and abs(s.get("z", 0)) >= 2.5:
                score += 1
                reasons.append(f"韓-台價差 z={s['z']:+.1f}(歷史極端,補跌/傳染風險)")
    except Exception:
        pass
    # ⑦ 美股前夜:NVDA(半導體風向)單日 ≤-3%
    try:
        nv = pd.read_csv(D / "us" / "NVDA.csv").dropna()
        r = nv["Close"].iloc[-1] / nv["Close"].iloc[-2] - 1
        if r <= -0.03:
            score += 1
            reasons.append(f"美股前夜:NVDA {r*100:+.1f}%")
    except Exception:
        pass
    # ⑩ 資金前哨·台幣:5日貶≥1%=外資匯出收據(10/15教案:崩前台幣連貶2%系統沒在看。
    #    「盤感很奇特,但資金不會騙人」——匯率是最誠實的資金流向表)
    try:
        tw = pd.read_csv(D / "us" / "TWD.csv").dropna()
        r5 = tw["Close"].iloc[-1] / tw["Close"].iloc[-6] - 1
        if r5 >= 0.01:
            score += 1
            reasons.append(f"資金前哨:台幣5日貶 {r5*100:.1f}%(外資匯出跡象)")
    except Exception:
        pass
    # ⑪ 資金前哨·亞美背離:費半/KOSPI 5日重挫而台股未跟=補跌風險
    #    (10/15教案:10/13 當晚 KOSPI 5日-11%、費半-6.6%、台股才-2.9%——提前兩天)
    try:
        bm5 = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Close"]).dropna()
        tw5 = bm5["Close"].iloc[-1] / bm5["Close"].iloc[-6] - 1
        hits = []
        for fn, nm in (("SOX", "費半"), ("KS11", "KOSPI")):
            x = pd.read_csv(D / "us" / f"{fn}.csv").dropna()
            x5 = x["Close"].iloc[-1] / x["Close"].iloc[-6] - 1
            if x5 <= -0.06 and (tw5 - x5) >= 0.04:
                hits.append(f"{nm} 5日 {x5*100:+.1f}% vs 台股 {tw5*100:+.1f}%")
        if hits:
            score += 1
            reasons.append("資金前哨:亞美先殺、台股未跟(補跌風險)——" + ";".join(hits))
    except Exception:
        pass
    # ⑧ 總經事件日:macro_events.csv 今日/明晨高重要度事件
    try:
        ev = pd.read_csv(D / "macro_events.csv", dtype=str)
        from twtime import now_tw
        today_s = f"{now_tw():%Y-%m-%d}"
        hit = ev[(ev["date"] == today_s) & (ev["importance"] == "高")]
        for _, e in hit.iterrows():
            score += 1
            reasons.append(f"事件日:{e['event']}({e.get('time','')})——數據落地前倉位從輕")
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

"""
lines_check.py — 線型十問(M哥檢核卡的機械化,能算的全自動答)
=================================================================
①長多型態 ②240日扣抵價 ③120日扣抵價 ④20日扣抵量 ⑤吸籌樣態(出量外資買/縮量不賣)
⑥外資韌性(大盤跌照買) ⑧心理黑洞(近似) ⑨拉回守全均線 ⑩已在系統排行?
誠實標註:⑤⑧為規則近似,原版靠讀圖;答案是檢核不是買訊。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


def _px(code: str) -> pd.DataFrame | None:
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            d = pd.read_csv(p).dropna(subset=["Close"])
            if len(d) >= 250:
                return d.reset_index(drop=True)
    return None


def _fi(code: str) -> pd.Series | None:
    p = ROOT / "data" / "institutional" / f"{code}_inst.csv"
    if not p.exists():
        return None
    m = pd.read_csv(p)
    a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
    b = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
    s = a.fillna(b)
    s.index = m["date"].astype(str) if "date" in m.columns else m.index
    return s.dropna() / 1000          # 張


def ten_questions(code: str) -> list[dict]:
    d = _px(code)
    if d is None:
        return [{"問": "資料", "答": "價格史不足 250 日", "燈": "⚪"}]
    c, v = d["Close"], d["Volume"]
    out = []
    ma = {n: c.rolling(n).mean() for n in (20, 60, 120, 240)}

    # ① 長多型態
    bull = (c.iloc[-1] > ma[20].iloc[-1] > ma[60].iloc[-1] > ma[120].iloc[-1] > ma[240].iloc[-1]
            and ma[240].iloc[-1] > ma[240].iloc[-11])
    out.append({"問": "① 長多型態(價>20>60>120>240 且年線翻揚)",
                "答": "是" if bull else "否", "燈": "🟢" if bull else "🔴"})
    # ②③ 扣抵價
    for n, tag in ((240, "②"), (120, "③")):
        kd = float(c.iloc[-n])
        low = kd < c.iloc[-1]
        out.append({"問": f"{tag} {n}日扣抵價(低於現價=均線將續揚,助漲)",
                    "答": f"{kd:.1f} vs 現價 {c.iloc[-1]:.1f} → {'低(助漲)' if low else '高(壓力)'}",
                    "燈": "🟢" if low else "🟡"})
    # ④ 20日扣抵量
    kv, nv = float(v.iloc[-20]), float(v.tail(5).mean())
    out.append({"問": "④ 20日扣抵量(扣大量=均量將降,量縮也能維持量增假象消退)",
                "答": f"扣抵日量 {kv/1000:.0f} 張 vs 近5日均 {nv/1000:.0f} 張 → "
                      + ("扣大量(均量將降)" if kv > nv else "扣小量(均量易增)"),
                "燈": "🟢" if kv > nv else "🟡"})
    # ⑤ 吸籌樣態(近60日:爆量日外資買 / 縮量跌日外資不賣)——近似
    fi = _fi(code)
    if fi is not None and len(fi) >= 40:
        n60 = min(60, len(fi), len(d))
        vv, cc_, ff = v.tail(n60).reset_index(drop=True), c.tail(n60).reset_index(drop=True), fi.tail(n60).reset_index(drop=True)
        mv20 = v.rolling(20).mean().tail(n60).reset_index(drop=True)
        burst_buy = shrink_holds = burst_n = shrink_n = 0
        for i in range(1, n60):
            if vv[i] >= 1.5 * (mv20[i] or 1):
                burst_n += 1
                burst_buy += ff[i] > 0
            elif cc_[i] < cc_[i - 1] and vv[i] < 0.8 * (mv20[i] or 1):
                shrink_n += 1
                shrink_holds += ff[i] >= -50
        p1 = burst_buy / burst_n * 100 if burst_n else 0
        p2 = shrink_holds / shrink_n * 100 if shrink_n else 0
        good = p1 >= 60 and p2 >= 60
        out.append({"問": "⑤ 吸籌樣態(出量日外資買/縮量跌日不倒貨,近60日)",
                    "答": f"出量日買超率 {p1:.0f}%({burst_n}次)|縮量跌不賣率 {p2:.0f}%({shrink_n}次)",
                    "燈": "🟢" if good else ("🟡" if p1 >= 50 else "🔴")})
        # ⑥ 外資韌性
        d20 = ff.tail(20)
        buy_days = (d20 > 0).mean() * 100
        out.append({"問": "⑥ 外資韌性(近20日買超天數比;不管環境不斷進場)",
                    "答": f"{buy_days:.0f}% 天數買超,累計 {d20.sum():+,.0f} 張",
                    "燈": "🟢" if buy_days >= 60 else ("🟡" if buy_days >= 45 else "🔴")})
    else:
        out.append({"問": "⑤⑥ 吸籌/外資韌性", "答": "無外資日資料", "燈": "⚪"})
    # ⑧ 心理黑洞(近似:120日內曾單日跌>5%且20日內收復)
    ret = c.pct_change()
    hole = False
    for i in range(max(1, len(d) - 120), len(d) - 1):
        if ret.iloc[i] < -0.05:
            j = min(i + 20, len(d) - 1)
            if c.iloc[i:j + 1].max() >= c.iloc[i - 1]:
                hole = True
    out.append({"問": "⑧ 心理黑洞(近120日曾急殺>5%後20日內收復——洗盤後易拉,近似)",
                "答": "出現過" if hole else "未見", "燈": "🟢" if hole else "⚪"})
    # ⑨ 拉回守全均線
    above = (c.tail(60) > ma[240].tail(60)).mean() * 100
    out.append({"問": "⑨ 近60日收在年線上的比率(拉回被拉回全均線之上)",
                "答": f"{above:.0f}%", "燈": "🟢" if above >= 90 else ("🟡" if above >= 70 else "🔴")})
    # ⑩ 已在系統排行?
    tags = []
    try:
        pool = pd.read_csv(ROOT / "data" / "_mmap_pool.csv", dtype=str)
        pcol = next((cn for cn in pool.columns if cn in ("代碼", "code")), None)
        if pcol is not None and (pool[pcol].astype(str) == str(code)).any():
            tags.append("籌碼地圖池")
    except Exception:
        pass
    try:
        import warrant_flow as wf
        sf = wf.sustained_flow(code)
        if sf and "🔵" in str(sf.get("verdict", "")):
            tags.append("權證佈局榜")
    except Exception:
        pass
    out.append({"問": "⑩ 已在系統排行出現?(地圖池/權證佈局)",
                "答": "、".join(tags) or "未上榜", "燈": "🟢" if tags else "⚪"})
    return out

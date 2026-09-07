"""
warrant_tools.py — 權證專區工具(BS理論價/希臘值/實質槓桿/歷史波動率)
=================================================================
定位:權證是「放大既有訊號」的執行工具,不是選股工具。
本模組只做數學;挑選紀律與體檢卡對接在頁21。
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call_put(S: float, K: float, days: int, iv: float, r: float = 0.017,
                kind: str = "call") -> dict:
    """Black-Scholes(無股利)。iv 年化小數(0.45=45%)。回傳每單位標的的價值與希臘值。"""
    T = max(days, 0.0001) / 365.0
    sig = max(iv, 1e-6)
    d1 = (math.log(S / K) + (r + sig * sig / 2) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    if kind == "call":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
    pdf_d1 = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    theta_y = (-S * pdf_d1 * sig / (2 * math.sqrt(T))
               - (1 if kind == "call" else -1) * r * K * math.exp(-r * T)
               * _norm_cdf(d2 if kind == "call" else -d2))
    vega = S * pdf_d1 * math.sqrt(T) / 100          # 每 1% IV
    return {"price": price, "delta": delta,
            "theta_day": theta_y / 365.0, "vega_1pct": vega}


def warrant_metrics(S: float, K: float, days: int, iv: float, ratio: float,
                    wprice: float | None = None, kind: str = "call",
                    r: float = 0.017) -> dict:
    """權證層指標。ratio=行使比例(如0.05);wprice=市場權證價(未填用理論價)。"""
    g = bs_call_put(S, K, days, iv, r, kind)
    theo = g["price"] * ratio
    wp = wprice if wprice else theo
    lev = (g["delta"] * S * ratio / wp) if wp > 0 else 0.0
    if kind == "call":
        breakeven = K + wp / ratio
        moneyness = (S / K - 1) * 100
    else:
        breakeven = K - wp / ratio
        moneyness = (K / S - 1) * 100
    return {"理論價": round(theo, 3), "市價": round(wp, 3),
            "溢價率%": round((wp / theo - 1) * 100, 1) if theo > 0 else None,
            "Delta": round(g["delta"], 3),
            "實質槓桿x": round(lev, 2),
            "每日時間價值流失": round(-g["theta_day"] * ratio, 4),
            "每日流失%": round(-g["theta_day"] * ratio / wp * 100, 2) if wp > 0 else None,
            "IV每降1%損失": round(g["vega_1pct"] * ratio, 4),
            "損益兩平": round(breakeven, 2),
            "價內外%": round(moneyness, 1)}


def decay_table(S: float, K: float, days: int, iv: float, ratio: float,
                kind: str = "call") -> pd.DataFrame:
    """標的不動,時間流逝的權證價值表(時間就是成本)。"""
    rows = []
    for d in [days, max(days - 7, 1), max(days - 14, 1), max(days - 30, 1),
              max(days - 45, 1), 5, 1]:
        if rows and d >= rows[-1]["剩餘天數"]:
            continue
        v = bs_call_put(S, K, d, iv, kind=kind)["price"] * ratio
        rows.append({"剩餘天數": d, "理論價": round(v, 3)})
    base = rows[0]["理論價"]
    for r_ in rows:
        r_["相對今日%"] = round((r_["理論價"] / base - 1) * 100, 1) if base > 0 else None
    return pd.DataFrame(rows)


def scenario_table(S: float, K: float, days: int, iv: float, ratio: float,
                   wprice: float | None = None, kind: str = "call") -> pd.DataFrame:
    """標的 ±5/±10/±15% × 持有 0/10 天 → 權證價與報酬。"""
    wp0 = wprice or bs_call_put(S, K, days, iv, kind=kind)["price"] * ratio
    prem = (wp0 / (bs_call_put(S, K, days, iv, kind=kind)["price"] * ratio)
            if wp0 else 1.0)                       # 市價相對理論的溢價倍數,情境沿用
    rows = []
    for chg in [-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15]:
        s2 = S * (1 + chg)
        now = bs_call_put(s2, K, days, iv, kind=kind)["price"] * ratio * prem
        d10 = bs_call_put(s2, K, max(days - 10, 1), iv, kind=kind)["price"] * ratio * prem
        rows.append({"標的漲跌%": int(chg * 100),
                     "標的價": round(s2, 1),
                     "權證價(立刻)": round(now, 3),
                     "報酬%(立刻)": round((now / wp0 - 1) * 100, 1),
                     "權證價(持有10天)": round(d10, 3),
                     "報酬%(持有10天)": round((d10 / wp0 - 1) * 100, 1)})
    return pd.DataFrame(rows)


def hist_vol(code: str) -> dict:
    """年化歷史波動率 HV20/HV60/HV120(挑 IV 的比較基準)+現價。"""
    import numpy as np
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p, usecols=["Date", "Close"]).dropna().sort_values("Date")
        cl = pd.to_numeric(d["Close"], errors="coerce").dropna()
        if len(cl) < 130:
            return {}
        lr = np.log(cl / cl.shift(1)).dropna()
        out = {"現價": round(float(cl.iloc[-1]), 2)}
        for n in (20, 60, 120):
            out[f"HV{n}%"] = round(float(lr.tail(n).std() * math.sqrt(252) * 100), 1)
        return out
    return {}

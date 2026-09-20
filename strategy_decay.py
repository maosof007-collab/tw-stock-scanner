"""
strategy_decay.py — 策略衰減儀表(免疫系統的最後一塊)
=================================================================
每策略比對「近60日訊號的實際 fwd20 報酬」vs「歷史回測 EV」:
  衰減率 = 1 - 近期EV/歷史EV;>50% 🟡半衰、轉負 🔴失效、正常 🟢。
資料:scan_results/signals_*.csv(BUY級)+ 價格檔;鯨魚另用 forward log。
產出:data/_strategy_decay.csv(頁7 顯示;run_daily 週六重算)。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "_strategy_decay.csv"

# 歷史回測 EV(%/筆,系統記憶的基準;修改需附回測依據)
BASE_EV = {
    "量縮整理→出量突破（融資沒走）": 1.80,
    "波段第二買點": 1.70,
    "A+B+C 籌碼趨勢（完整版）": 1.43,
    "A+B+C 籌碼趨勢（M哥完整版）": 1.43,     # 舊名(歷史CSV)
    "大跌後外資買進（隔日跟單）": 1.28,
    "融資維持率創低反彈": 1.05,
    "腰斬打底＋外資回補": 0.89,
    "大跌中融資逆勢買": 0.92,
    "運價動能": 1.56,
    "運價動能（航運景氣跟蹤）": 1.56,
    "波段回檔再進場（第二買點）": 1.70,
    "融資維持率創低反彈（量增）": 1.05,
    "股價腰斬的中小型績優股": 0.89,
    "鯨魚訊號(權證)": 3.19,                  # 5日窗
}


def _px(code):
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            d = pd.read_csv(p, usecols=["Date", "Close"]).dropna().sort_values("Date")
            return (d["Date"].astype(str).tolist(),
                    pd.to_numeric(d["Close"], errors="coerce").tolist())
    return None


def compute(recent_days: int = 60) -> pd.DataFrame:
    """近 recent_days 的 BUY 訊號 fwd20 vs 歷史EV。"""
    cutoff = f"{now_tw() - pd.Timedelta(days=recent_days + 35):%Y%m%d}"
    recs = []
    for f in sorted(glob.glob(str(ROOT / "scan_results" / "signals_*.csv"))):
        ymd = f.split("_")[-1][:8]
        if ymd < cutoff:
            continue
        try:
            s = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
            cc = next((c for c in s.columns if c in ("代碼", "ticker", "code")), None)
            sc = next((c for c in s.columns if "策略" in c), None)
            gc = next((c for c in s.columns if "訊號等級" in c or "grade" in c), None)
            if not cc or not sc:
                continue
            if gc is not None:
                s = s[s[gc].astype(str).str.startswith("BUY")]
            for _, r in s.iterrows():
                code = str(r[cc]).split(".")[0]
                if code.isdigit():
                    recs.append((f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}", code, str(r[sc])))
        except Exception:
            continue
    sig = pd.DataFrame(recs, columns=["date", "code", "strat"]).drop_duplicates()
    px_cache = {}
    rows = []
    for strat, g in sig.groupby("strat"):
        rets = []
        for _, r in g.iterrows():
            if r["code"] not in px_cache:
                px_cache[r["code"]] = _px(r["code"])
            pxd = px_cache[r["code"]]
            if pxd is None:
                continue
            dates, closes = pxd
            try:
                i = dates.index(r["date"])
            except ValueError:
                continue
            if i + 20 < len(closes) and closes[i]:
                rets.append((closes[i + 20] / closes[i] - 1) * 100)
        if len(rets) < 8:
            continue
        ev_now = float(np.mean(rets))
        base = BASE_EV.get(strat)
        if base:
            decay = 1 - ev_now / base
            lamp = "🔴 失效中" if ev_now < 0 else ("🟡 半衰" if decay > 0.5 else "🟢 正常")
        else:
            decay, lamp = None, "⚪ 無基準"
        rows.append({"策略": strat, "近期訊號數": len(rets),
                     "近期EV(fwd20)%": round(ev_now, 2),
                     "歷史EV%": base,
                     "衰減率%": round(decay * 100) if decay is not None else None,
                     "狀態": lamp,
                     "勝率%": round(float(np.mean([x > 0 for x in rets])) * 100)})
    # 鯨魚訊號(forward log)
    try:
        w = pd.read_csv(ROOT / "data" / "warrants" / "whale_signals.csv", dtype={"ucode": str})
        rets = []
        for _, r in w.iterrows():
            if r["ucode"] not in px_cache:
                px_cache[r["ucode"]] = _px(r["ucode"])
            pxd = px_cache[r["ucode"]]
            if pxd is None:
                continue
            dates, closes = pxd
            try:
                i = dates.index(str(r["date"])[:10])
            except ValueError:
                continue
            if i + 5 < len(closes) and closes[i]:
                rets.append((closes[i + 5] / closes[i] - 1) * 100)
        if len(rets) >= 5:
            ev_now = float(np.mean(rets))
            base = BASE_EV["鯨魚訊號(權證)"]
            decay = 1 - ev_now / base
            rows.append({"策略": "鯨魚訊號(權證,5日窗)", "近期訊號數": len(rets),
                         "近期EV(fwd20)%": round(ev_now, 2), "歷史EV%": base,
                         "衰減率%": round(decay * 100),
                         "狀態": "🔴 失效中" if ev_now < 0 else ("🟡 半衰" if decay > 0.5 else "🟢 正常"),
                         "勝率%": round(float(np.mean([x > 0 for x in rets])) * 100)})
    except Exception:
        pass
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("衰減率%", ascending=False, na_position="last")
        df.insert(0, "計算日", f"{now_tw():%Y-%m-%d}")
        df.to_csv(OUT, index=False, encoding="utf-8-sig")
    return df


def load() -> pd.DataFrame:
    if OUT.exists():
        return pd.read_csv(OUT)
    return pd.DataFrame()


if __name__ == "__main__":
    df = compute()
    print(df.to_string(index=False))

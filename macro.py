"""
macro.py — 總經/總體環境指標
=================================================
大盤融資維持率（推估）：市場槓桿風險溫度計。
公式：維持率% = 100 × Σ(現值) / (融資成數 × Σ(推估成本))
  · 現值   = 個股收盤 × 融資餘額(張)
  · 成本   = 個股 MA60（融資平均買進成本推估）× 融資餘額(張)
  · 融資成數 = 0.6（上市），故剛買進(現值=成本)時 ≈ 1/0.6 = 166.7%
  · 越低＝槓桿壓力越大、越接近追繳(130%)/斷頭(120%)
資料：data/margin/*.csv（融資餘額，張）+ data/{code}.csv（收盤）。維持率為推估。
"""
from __future__ import annotations
import glob, os
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
CACHE = DATA / "_market_margin.csv"
MARGIN_RATE = 0.6     # 融資成數（上市）
COST_MA = 60          # 融資平均成本以 MA60 推估


def _price(code: str):
    for suf in (".TW", ".TWO"):
        p = DATA / f"{code}{suf}.csv"
        if p.exists():
            df = pd.read_csv(p)
            df.columns = [c.lower() for c in df.columns]
            dc = "date" if "date" in df.columns else df.columns[0]
            df = df.rename(columns={dc: "date"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            return df[["date", "close"]].dropna()
    return None


def build_market_margin_series(window_days: int = 500, rebuild: bool = False) -> pd.DataFrame:
    """回傳 DataFrame(date, ratio, margin_lots, twii)。當日算一次，快取到 data/_market_margin.csv。"""
    if CACHE.exists() and not rebuild:
        try:
            c = pd.read_csv(CACHE, parse_dates=["date"])
            if not c.empty:
                return c.tail(window_days).reset_index(drop=True)
        except Exception:
            pass

    files = glob.glob(str(DATA / "margin" / "*.csv"))
    parts = []
    for f in files:
        code = os.path.basename(f).replace("_margin.csv", "")
        try:
            mg = pd.read_csv(f, usecols=["date", "margin_balance"]).dropna()
            if mg.empty:
                continue
            mg["date"] = pd.to_datetime(mg["date"], errors="coerce")
            mg["margin_balance"] = pd.to_numeric(mg["margin_balance"], errors="coerce")
            mg = mg.dropna()
            mg = mg[mg["margin_balance"] > 0]
            if mg.empty:
                continue
            px = _price(code)
            if px is None or len(px) < COST_MA:
                continue
            px = px.sort_values("date")
            px["ma"] = px["close"].rolling(COST_MA).mean()
            m = mg.merge(px, on="date", how="inner").dropna(subset=["close", "ma"])
            if m.empty:
                continue
            m["numer"] = m["close"] * m["margin_balance"]
            m["cost"] = m["ma"] * m["margin_balance"]
            parts.append(m[["date", "numer", "cost", "margin_balance"]])
        except Exception:
            pass

    if not parts:
        return pd.DataFrame(columns=["date", "ratio", "margin_lots", "twii"])

    allm = pd.concat(parts, ignore_index=True)
    g = allm.groupby("date", as_index=False).sum()
    g["ratio"] = 100 * g["numer"] / (MARGIN_RATE * g["cost"])
    s = g[["date", "ratio", "margin_balance"]].rename(columns={"margin_balance": "margin_lots"})
    s = s.sort_values("date").reset_index(drop=True)

    # 併大盤指數
    try:
        bm = pd.read_csv(DATA / "benchmark_TWII.csv")
        bm["date"] = pd.to_datetime(bm["Date"], errors="coerce")
        bm = bm[["date", "Close"]].rename(columns={"Close": "twii"})
        s = s.merge(bm, on="date", how="left")
    except Exception:
        s["twii"] = np.nan

    try:
        s.to_csv(CACHE, index=False)
    except Exception:
        pass
    return s.tail(window_days).reset_index(drop=True)


def margin_status(ratio: float, warn: float = 150.0) -> tuple[str, str]:
    """回傳 (狀態文字, 顏色鍵)。130 追繳、120 斷頭。"""
    if ratio is None or np.isnan(ratio):
        return "無資料", "muted"
    if ratio < 130:
        return "⚠️ 接近追繳/斷頭", "down"
    if ratio < warn:
        return "警戒（槓桿偏高）", "ma30"
    if ratio >= 175:
        return "安全（槓桿寬鬆）", "up"
    return "正常", "text"

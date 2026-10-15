# -*- coding: utf-8 -*-
"""
resonance_backtest.py — 共振回調(日線版)歷史回測(2026-10-15)
=================================================================
規則與 resonance_pullback._check A級完全一致;逐日掃訊號→隔日起逐K模擬:
  進場:訊號日收盤
  停損:結構停損(訊號日前2日低);跳空低開以開盤成交(誠實計算滑價)
  停利:3R 目標價先到=+3R 出場(變體B:5R)
  時間出場:60 個交易日未觸發→以收盤出場
  同檔冷卻:部位結束前不重複進場
成本:來回 0.6%(稅 0.3%+手續費)。輸出:勝率/平均R/期望值/分年。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"


def _signals_and_trades(f: str, use_5r: bool = False, stop_mode: str = 'struct') -> list[dict]:
    code = os.path.basename(f).split(".")[0]
    try:
        px = pd.read_csv(f).dropna(subset=["Close"]).reset_index(drop=True)
    except Exception:
        return []
    n = len(px)
    if n < 300:
        return []
    dt = pd.to_datetime(px["Date"])
    c = px["Close"].astype(float).values
    h = px["High"].astype(float).values
    l = px["Low"].astype(float).values
    o = px["Open"].astype(float).values
    v = px["Volume"].astype(float).values
    # 向量化指標
    cs = pd.Series(c)
    e9 = cs.ewm(span=9, adjust=False).mean().values
    e21 = cs.ewm(span=21, adjust=False).mean().values
    e50 = cs.ewm(span=50, adjust=False).mean().values
    wk = pd.Series(c, index=dt).resample("W").last().dropna()
    we9 = wk.ewm(span=9, adjust=False).mean()
    we9_up_w = (we9 > we9.shift(1))
    # 把週訊號映回日(用該日所屬週的「上一完成週」判定→shift(1)再 reindex ffill)
    we9_up_daily = we9_up_w.shift(0).reindex(dt, method="ffill").fillna(False).values
    vol20 = pd.Series(v).shift(1).rolling(20).mean().values
    hi20 = pd.Series(h).shift(1).rolling(20).max().values
    chg = np.concatenate([[0], c[1:] / c[:-1] - 1])
    amt20 = pd.Series(v * c).rolling(20).mean().values
    anchor_ok = (v >= 1.5 * np.where(np.isnan(vol20), np.inf, vol20)) & (chg >= 0.03) \
                & (c > np.where(np.isnan(hi20), np.inf, hi20))
    tp = (h + l + c) / 3
    cum_tpv = np.concatenate([[0], np.cumsum(tp * v)])
    cum_v = np.concatenate([[0], np.cumsum(v)])
    hi5 = pd.Series(h).rolling(5).max().values
    lo5 = pd.Series(l).rolling(5).min().values
    lo2 = pd.Series(l).rolling(2).min().values
    lo3touch = pd.Series(l).rolling(5).min().values   # 近5日最低(觸區判定用)
    trades = []
    last_anchor = -1
    cooldown_until = -1
    for t in range(80, n - 1):
        if anchor_ok[t]:
            last_anchor = t
        if t <= cooldown_until:
            continue
        if last_anchor < 0 or t - last_anchor > 60 or t - last_anchor < 1:
            continue
        if np.isnan(amt20[t]) or amt20[t] < 5e7:
            continue
        if not (e9[t] > e21[t] > e50[t]) or not we9_up_daily[t]:
            continue
        if t < 26 or c[t - 5] / c[t - 25] - 1 < 0.15:
            continue
        if lo5[t] <= 0 or hi5[t] / lo5[t] - 1 > 0.10:
            continue
        a = last_anchor
        dv = cum_v[t + 1] - cum_v[a]
        if dv <= 0:
            continue
        avwap = (cum_tpv[t + 1] - cum_tpv[a]) / dv
        zlo = min(e9[t], e21[t], avwap)
        zhi = max(e9[t], e21[t], avwap)
        if zlo <= 0 or zhi / zlo - 1 > 0.05:
            continue
        if lo3touch[t] > zhi or c[t] < zlo * 0.99:
            continue
        if stop_mode == 'atr':
            tr = np.maximum.reduce([h[max(0,t-14):t+1]-l[max(0,t-14):t+1],
                                    np.abs(h[max(0,t-14):t+1]-np.roll(c,1)[max(0,t-14):t+1]),
                                    np.abs(l[max(0,t-14):t+1]-np.roll(c,1)[max(0,t-14):t+1])])
            stop = c[t] - 1.5*float(np.mean(tr))
        else:
            stop = lo2[t]
        risk = c[t] / stop - 1 if stop > 0 else -1
        if risk < 0.01 or risk > 0.08:
            continue
        # ── 模擬 ──
        entry = c[t]
        r1 = entry - stop
        tgt = entry + (5 if use_5r else 3) * r1
        exit_px, exit_i = None, None
        for j in range(t + 1, min(t + 61, n)):
            if o[j] <= stop:                       # 跳空破停損:開盤出
                exit_px, exit_i = o[j], j
                break
            if l[j] <= stop:
                exit_px, exit_i = stop, j
                break
            if h[j] >= tgt:
                exit_px, exit_i = tgt, j
                break
        if exit_px is None:
            exit_i = min(t + 60, n - 1)
            exit_px = c[exit_i]
        gross = exit_px / entry - 1
        net = gross - 0.006
        trades.append({"code": code, "date": str(px['Date'].iloc[t])[:10],
                       "entry": entry, "stop": stop, "exit": exit_px,
                       "R": net / (r1 / entry), "net%": net * 100,
                       "hold": exit_i - t, "year": str(px['Date'].iloc[t])[:4]})
        cooldown_until = exit_i
    return trades


def run(use_5r: bool = False, stop_mode: str = 'struct') -> pd.DataFrame:
    allt = []
    for f in glob.glob(str(D / "[0-9]*.csv")):
        if len(os.path.basename(f).split(".")[0]) != 4:
            continue
        allt += _signals_and_trades(f, use_5r, stop_mode)
    df = pd.DataFrame(allt)
    return df


if __name__ == "__main__":
    for tag, u5 in [("3R", False), ("5R", True)]:
        df = run(u5)
        if df.empty:
            print(tag, "無交易")
            continue
        win = (df["net%"] > 0).mean() * 100
        print(f"\n===== {tag} 版 =====")
        print(f"筆數 {len(df)}|勝率 {win:.1f}%|平均淨報酬 {df['net%'].mean():.2f}%|"
              f"平均R {df['R'].mean():.2f}|中位持有 {df['hold'].median():.0f} 日")
        print(f"期望值檢定:平均R>0 → {'✅' if df['R'].mean() > 0 else '❌'}")
        yr = df.groupby("year").agg(筆=("R", "size"), 勝率=("net%", lambda x: (x > 0).mean() * 100),
                                    平均R=("R", "mean")).round(2)
        print(yr.to_string())
        df.to_csv(D / f"_resonance_bt_{tag}.csv", index=False, encoding="utf-8-sig")

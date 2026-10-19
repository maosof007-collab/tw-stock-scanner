# -*- coding: utf-8 -*-
"""
margin_stress.py — 個股融資壓力對照(推估維持率 × 大盤急跌區)
=================================================================
起因(2026-10-19):tetsu_chang_ IG 的聯發科壓力對照圖——大盤下跌時,看個股
融資維持率跌到哪、開槓桿的人離斷頭多遠。我們的 10/16 研究(紅盤×高融資
= 60日 -15.6% 最毒象限)證明這個維度有效,本模組把它做成逐檔可查。
方法(與 strategies/margin_maintenance 同源):
  融資餘額增加 → 視為以當日收盤建倉,更新加權平均成本;餘額減少 → 減量不動成本
  維持率 = 收盤 / 加權成本 / 融資成數 × 100(上市 0.6、上櫃 0.5)
  紅色急跌區 = 加權指數 5 日跌幅 ≤-4% 或 距 20 日高 ≤-8%
誠實標註:這是「推估」——真實維持率只有授信端知道;長期持倉的舊成本會被
餘額進出沖淡,絕對值看趨勢與相對位置,不要當精確數字用。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"


def _weighted_cost(balance: np.ndarray, close: np.ndarray) -> np.ndarray:
    cost = np.full(len(balance), np.nan)
    hold, avg = 0.0, np.nan
    for i in range(len(balance)):
        b = balance[i]
        if b > hold:                       # 增量視為今日建倉
            add = b - hold
            avg = close[i] if hold <= 0 or np.isnan(avg) else (avg * hold + close[i] * add) / b
        elif b <= 0:
            avg = np.nan
        hold = b
        cost[i] = avg
    return cost


def build(code: str, days: int = 130) -> dict | None:
    mp = D / "margin" / f"{code}_margin.csv"
    if not mp.exists():
        return None
    mg = pd.read_csv(mp, parse_dates=["date"]).dropna(subset=["margin_balance"])
    ratio_pct = 0.6
    px = None
    for suf, rp in ((".TW.csv", 0.6), (".TWO.csv", 0.5)):
        p = D / f"{code}{suf}"
        if p.exists():
            px = pd.read_csv(p, parse_dates=["Date"]).dropna(subset=["Close"])
            ratio_pct = rp
            break
    if px is None:
        return None
    df = mg[["date", "margin_balance", "margin_quota"]].merge(
        px[["Date", "Close", "Volume"]], left_on="date", right_on="Date")
    if len(df) < 30:
        return None
    df["cost"] = _weighted_cost(df["margin_balance"].to_numpy(float),
                                df["Close"].to_numpy(float))
    df["維持率"] = df["Close"] / df["cost"] / ratio_pct * 100
    df["使用率"] = df["margin_balance"] / df["margin_quota"].replace(0, np.nan) * 100
    # 大盤急跌區
    bm = pd.read_csv(D / "benchmark_TWII.csv", parse_dates=["Date"]).dropna(subset=["Close"])
    bm["r5"] = (bm["Close"] / bm["Close"].shift(5) - 1) * 100
    bm["dd20"] = (bm["Close"] / bm["Close"].rolling(20).max() - 1) * 100
    bm["crash"] = (bm["r5"] <= -4) | (bm["dd20"] <= -8)
    df = df.merge(bm[["Date", "Close", "crash"]].rename(
        columns={"Close": "twii"}), on="Date", how="left")
    df = df.tail(days).reset_index(drop=True)
    df["個股=100"] = df["Close"] / df["Close"].iloc[0] * 100
    df["大盤=100"] = df["twii"] / df["twii"].iloc[0] * 100
    # 卡片
    weakest = None
    w = df.dropna(subset=["twii"]).copy()
    w["tw_r"] = w["twii"].pct_change() * 100
    if w["tw_r"].notna().any():
        i = w["tw_r"].idxmin()
        weakest = {"日期": f"{w.loc[i,'Date']:%Y-%m-%d}", "大盤%": round(w.loc[i, "tw_r"], 1),
                   "該日維持率": round(w.loc[i, "維持率"], 1) if pd.notna(w.loc[i, "維持率"]) else None}
    cards = {"最新維持率%": round(df["維持率"].iloc[-1], 1) if pd.notna(df["維持率"].iloc[-1]) else None,
             "期間股價%": round((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100, 1),
             "融資使用率%": round(df["使用率"].iloc[-1], 1) if pd.notna(df["使用率"].iloc[-1]) else None,
             "大盤最弱日": weakest}
    return {"df": df, "cards": cards, "ratio": ratio_pct}


def chart(code: str, days: int = 130):
    """Plotly 雙軸圖:個股/大盤(=100)+維持率(右軸)+急跌紅區。頁27 用。"""
    r = build(code, days)
    if r is None:
        return None, None
    df = r["df"]
    import plotly.graph_objects as go
    fig = go.Figure()
    # 急跌紅區
    in_zone = False
    for i, row in df.iterrows():
        if bool(row.get("crash")) and not in_zone:
            x0 = row["Date"]; in_zone = True
        elif not bool(row.get("crash")) and in_zone:
            fig.add_vrect(x0=x0, x1=row["Date"], fillcolor="red", opacity=0.10, line_width=0)
            in_zone = False
    if in_zone:
        fig.add_vrect(x0=x0, x1=df["Date"].iloc[-1], fillcolor="red", opacity=0.10, line_width=0)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["個股=100"], name="個股(=100)",
                             line=dict(color="#58a6ff", width=2)))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["大盤=100"], name="大盤(=100)",
                             line=dict(color="#9aa0a6", width=1.5)))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["維持率"], name="推估維持率%",
                             line=dict(color="#f85149", width=2, dash="dot"), yaxis="y2"))
    fig.add_hline(y=130, line=dict(color="#f85149", width=1, dash="dash"),
                  yref="y2", annotation_text="130% 追繳線", annotation_font_color="#f85149")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      yaxis=dict(title="相對位置(=100)"),
                      yaxis2=dict(title="維持率%", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.12),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig, r


if __name__ == "__main__":
    r = build("2454")
    print(r["cards"] if r else "no data")

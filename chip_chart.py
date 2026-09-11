"""
chip_chart.py — 籌碼總覽分軌圖(仿 aistockmap 版式)
=================================================================
分軌:①K線+量 ②大戶>400張%(TDCC週,含人數) ③外資區間累積買賣超
     ④投信區間累積 ⑤融資餘額。
誠實標註:外資/投信畫的是「區間累積買賣超」(系統無持股存量源);
借券賣出無資料源,待接(TWSE TWT93U)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).parent


def chip_overview(code: str, months: int = 6):
    """回傳 (fig, meta) 或 (None, 錯誤訊息)。"""
    px = None
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            px = pd.read_csv(p).dropna().sort_values("Date")
            break
    if px is None:
        return None, "無價格資料"
    for c in ("Open", "High", "Low", "Close", "Volume"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    n_days = months * 22
    px = px.tail(n_days).reset_index(drop=True)
    start = px["Date"].iloc[0]

    # 大戶%(TDCC 週)+人數
    big = pd.DataFrame()
    tp = ROOT / "data" / "tdcc" / f"{code}_tdcc.csv"
    if tp.exists():
        t = pd.read_csv(tp, dtype={"level": int})
        t = t[t["level"].isin([12, 13, 14, 15])]
        big = (t.groupby("date").agg(pct=("pct", "sum"), holders=("holders", "sum"))
               .reset_index())
        big = big[big["date"] >= start]

    # 外資/投信 區間累積
    inst = pd.DataFrame()
    ip = ROOT / "data" / "institutional" / f"{code}_inst.csv"
    if ip.exists():
        i = pd.read_csv(ip).sort_values("date")
        i = i[i["date"] >= start]
        inst = pd.DataFrame({
            "date": i["date"],
            "fi": i["外陸資買賣超股數(不含外資自營商)"].fillna(0).cumsum() / 1000,
            "it": i["it_net"].fillna(0).cumsum() / 1000,
        })

    # 融資餘額
    mar = pd.DataFrame()
    mp = ROOT / "data" / "margin" / f"{code}_margin.csv"
    if mp.exists():
        m = pd.read_csv(mp, usecols=["date", "margin_balance"]).dropna().sort_values("date")
        mar = m[m["date"] >= start]

    fig2 = make_subplots(rows=5, cols=1, shared_xaxes=True,
                         row_heights=[0.36, 0.16, 0.16, 0.16, 0.16],
                         vertical_spacing=0.025,
                         specs=[[{"secondary_y": True}], [{}], [{}], [{}], [{}]],
                         subplot_titles=("", "大戶>400張持股%(TDCC週)",
                                         "外資累積買賣超(張,區間內)",
                                         "投信累積買賣超(張,區間內)", "融資餘額(張)"))
    fig2.add_trace(go.Candlestick(x=px["Date"], open=px["Open"], high=px["High"],
                                  low=px["Low"], close=px["Close"], name="K",
                                  increasing_line_color="#D64545",
                                  decreasing_line_color="#2E9E5B"),
                   row=1, col=1)
    fig2.add_trace(go.Bar(x=px["Date"], y=px["Volume"] / 1000, name="量",
                          marker_color="#8899AA", opacity=0.35),
                   row=1, col=1, secondary_y=True)
    if not big.empty:
        fig2.add_trace(go.Scatter(x=big["date"], y=big["pct"], name="大戶%",
                                  line_shape="hv", line=dict(color="#B8860B", width=2.2)),
                       row=2, col=1)
    if not inst.empty:
        fig2.add_trace(go.Scatter(x=inst["date"], y=inst["fi"], name="外資累積",
                                  fill="tozeroy", line=dict(color="#3B82F6", width=2)),
                       row=3, col=1)
        fig2.add_trace(go.Scatter(x=inst["date"], y=inst["it"], name="投信累積",
                                  fill="tozeroy", line=dict(color="#8B5CF6", width=2)),
                       row=4, col=1)
    if not mar.empty:
        fig2.add_trace(go.Scatter(x=mar["date"], y=mar["margin_balance"], name="融資",
                                  fill="tozeroy", line=dict(color="#EC4899", width=2)),
                       row=5, col=1)
    fig2.update_layout(height=780, showlegend=False, xaxis_rangeslider_visible=False,
                       margin=dict(l=10, r=10, t=28, b=10))
    fig2.update_yaxes(secondary_y=True, showgrid=False, row=1, col=1)
    meta = {}
    if not big.empty:
        meta["大戶%"] = f"{big['pct'].iloc[-1]:.2f}%({int(big['holders'].iloc[-1])}人)"
    if not inst.empty:
        meta["外資區間累積"] = f"{inst['fi'].iloc[-1]:+,.0f}張"
        meta["投信區間累積"] = f"{inst['it'].iloc[-1]:+,.0f}張"
    if not mar.empty:
        meta["融資餘額"] = f"{int(mar['margin_balance'].iloc[-1]):,}張"
    return fig2, meta

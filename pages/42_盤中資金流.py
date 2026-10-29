# -*- coding: utf-8 -*-
"""
pages/42_盤中資金流.py — 即時族群資金流進流出(台新同款,自家免費版)
=================================================================
「我想做一個跟台新即時的平台,即時看族群資金流進流出」(2026-10-28)。
盤中(09:00-13:32)每 60 秒自動輪詢證交所 MIS 快照 → 量增量×價×方向=資金流。
紅=流入(漲)、綠=流出(跌)——台股習慣。收盤後顯示當日(或最近一日)全貌。
注意:這是推估(快照級),不是逐筆內外盤;族群排序才是重點,個股數字看相對。
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import ui_theme as T
from ui_theme import inject_css, page_header

st.set_page_config(page_title="盤中資金流", page_icon="🌊", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("盤中資金流(族群即時)", "LIVE MONEY FLOW", "🌊")

import rt_flow as RT
from twtime import now_tw

def _trading_now() -> bool:
    t = now_tw()
    return t.weekday() < 5 and "08:59" <= f"{t:%H:%M}" <= "13:32"


@st.fragment(run_every="60s")   # 永遠心跳:開盤前掛著,09:00 自動轉 LIVE
def _live():
    live = _trading_now()
    # ── 盤中:抓一輪快照(每分鐘一筆,重複呼叫同分鐘不重寫) ──
    if live:
        try:
            RT.record()
        except Exception:
            pass

    idx = RT.indices()
    c = st.columns(4)
    for i, (name, (px, pct)) in enumerate(idx.items()):
        c[i].metric(name, f"{px:,.0f}", f"{pct:+.2f}%",
                    delta_color="inverse")        # 台股紅漲:inverse 讓 + 顯紅
    c[2].metric("模式", "🔴 LIVE 60s" if live else "⏸ 收盤快照",
                f"{now_tw():%H:%M:%S}", delta_color="off")

    day = RT.load_day()
    if day.empty:
        st.info("還沒有今日快照——開盤(09:00)後這頁會自動每分鐘累積。"
                "掛著不用動,像看台新的盤一樣。")
        return
    ddate = day.attrs.get("date", "")
    if ddate and ddate != f"{now_tw():%Y%m%d}":
        c[3].metric("資料日", f"{ddate[4:6]}/{ddate[6:]}", "最近交易日", delta_color="off")

    tot, per_ts = RT.group_flows(day)
    if tot.empty:
        st.info("快照已開始,等前兩輪取得增量後出圖(約 2 分鐘)。")
        return

    # ── 主圖:族群淨流入排行(紅流入/綠流出) ──
    tot = tot.sort_values("淨流入")
    colors = [T.RED if v >= 0 else T.GREEN for v in tot["淨流入"]]
    fig = go.Figure(go.Bar(
        x=tot["淨流入"], y=tot["group"], orientation="h", marker_color=colors,
        text=[f"{v:+.1f}億({p:+.1f}%)" for v, p in zip(tot["淨流入"], tot["漲跌%"])],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="%{y}<br>淨流入 %{x:+.2f} 億<extra></extra>"))
    fig.update_layout(height=max(420, 24 * len(tot)), margin=dict(l=10, r=100, t=30, b=10),
                      xaxis=dict(range=[min(tot["淨流入"].min() * 1.3,
                                            -abs(tot["淨流入"].max()) * 0.22) - 1,
                                        tot["淨流入"].max() * 1.25]),
                      title=f"族群淨流入(億元,開盤累積到 {day.ts.iloc[-1][:5]})",
                      xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    # ── 走勢:流入前 5 + 流出前 3 的盤中累積線 ──
    lead = list(tot.tail(5)["group"]) + list(tot.head(3)["group"])
    sub = per_ts[per_ts["group"].isin(lead)]
    fig2 = go.Figure()
    for i, g in enumerate(reversed(lead)):
        s = sub[sub["group"] == g]
        fig2.add_scatter(x=s["ts"].str[:5], y=s["累積淨流"], name=g, mode="lines",
                         line=dict(width=2, color=T.PAL[i % len(T.PAL)]))
    fig2.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10),
                       title="盤中累積淨流走勢(誰在一路吸金/失血)",
                       yaxis_title="億元", legend=dict(orientation="h", y=-0.2),
                       xaxis=dict(categoryorder="category ascending"))
    st.plotly_chart(fig2, use_container_width=True)

    # ── 盤中強勢股(當沖觀察池) ──
    st.markdown("#### 🎯 盤中強勢股(當沖觀察池)")
    ss = RT.strong_stocks(day)
    if len(ss):
        v = ss.head(12).copy()
        v["淨流"] = (v["淨流"] / 1e4).round(2)
        v["額"] = (v["額"] / 1e4).round(2)
        st.dataframe(
            v.rename(columns={"淨流": "淨流入(億)", "額": "成交額(億)"}),
            hide_index=True, use_container_width=True,
            column_config={
                "漲%": st.column_config.NumberColumn(format="%+.2f%%"),
                "量比": st.column_config.NumberColumn(format="%.1f"),
                "買氣": st.column_config.NumberColumn(format="%+.2f"),
                "距日高%": st.column_config.NumberColumn(format="%+.2f%%"),
                "最新": st.column_config.NumberColumn(format="%.1f"),
                "強勢分": st.column_config.ProgressColumn(min_value=0, max_value=100,
                                                       format="%.0f"),
            })
        st.caption("強勢分=漲幅35%+量比25%+買氣20%+站均價10%+貼日高10(池門檻:上漲且"
                   "成交額≥3000萬)。量比=今日累積量÷(5日均量×U型時段曲線);買氣=淨流入/成交額。"
                   "⚠ 家內回測(6-10月、1339筆、含當沖成本0.435%):開盤買收盤賣整體勝率僅44.5%、"
                   "中位數-0.43%;唯一正期望組是「開盤跳空1~3%」(勝率52.1%、平均+0.58%),"
                   "跳空>3%追高無肉。這是觀察池不是買單;風險燈🔴時禁開新倉。")
    else:
        st.info("強勢池還沒有符合門檻的標的(上漲+成交額≥3000萬)。")

    # ── 個股明細 ──
    g1, g2 = st.columns([1, 3])
    pick = g1.selectbox("看族群成分", list(tot.sort_values("淨流入", ascending=False)["group"]))
    tbl = RT.stock_table(day, pick)
    if len(tbl):
        tbl["成交額"] = (tbl["成交額"] / 1e4).round(2)
        tbl["淨流入"] = (tbl["淨流入"] / 1e4).round(2)
        g2.dataframe(tbl.rename(columns={"成交額": "成交額(億)", "淨流入": "淨流入(億)"}),
                     hide_index=True, use_container_width=True,
                     column_config={"漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                                    "最新": st.column_config.NumberColumn(format="%.1f")})
    st.caption("方法:每分鐘快照的成交量增量×價格,漲判流入、跌判流出(平盤與昨收比)——"
               "推估值,非逐筆內外盤。族群相對排序是重點;一檔多族群會分別計入。"
               "資料源:證交所 MIS(上市+上櫃),免費、約 5 秒延遲。")


_live()

st.divider()
st.page_link("pages/39_強勢資金.py", label="💪 收盤後看「強勢資金」(成交注意力,含隔日沖雷達)")
st.page_link("pages/16_資金流向日誌.py", label="💸 盤後資金流向日誌(三大法人版)")

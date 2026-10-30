# -*- coding: utf-8 -*-
"""
pages/42_盤中資金流.py — 即時族群資金流(Shioaji Pro 同款四區版面,自家免費版)
=================================================================
「我想做一個跟台新即時的平台,即時看族群資金流進流出」(2026-10-28)
「即時頁面改這樣吧」(2026-10-29,附 Shioaji Pro 截圖)→ 改四區:
  ①市場脈動(指數/台幣/宇宙累計淨流大數字) ②族群資金流向泡泡圖
  ③累計淨流排行                         ④產業全景 treemap + 個股貢獻
盤中(09:00-13:32)每 60 秒自動輪詢證交所 MIS 快照 → 量增量×價×方向=資金流。
紅=流入(漲)、綠=流出(跌)——台股習慣。收盤後顯示當日(或最近一日)全貌。
注意:這是推估(快照級),不是逐筆內外盤;族群排序才是重點,個股數字看相對。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
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

# 長駐進程防呆:pages/*.py 會熱載入,但 import 的模組不會——偵測到舊版就地 reload
if not hasattr(RT, "_seed_last_px"):
    import importlib
    RT = importlib.reload(RT)

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

    day = RT.load_day()
    tot, per_ts = (RT.group_flows(day) if not day.empty
                   else (pd.DataFrame(), pd.DataFrame()))

    # ── ① 市場脈動 ──
    idx = RT.indices()
    c = st.columns(5)
    for i, (name, (px_, pct)) in enumerate(idx.items()):
        c[i].metric(name, f"{px_:,.0f}", f"{pct:+.2f}%",
                    delta_color="inverse")        # 台股紅漲:inverse 讓 + 顯紅
    fx = RT.usdtwd()
    if fx:
        c[2].metric("台幣(USD/TWD)", f"{fx[0]:.3f}",
                    f"{fx[1]:+.2f}% {'貶' if fx[1] > 0 else '升'}",
                    delta_color="inverse")        # 貶值顯紅(出口甜、資金流出訊號)
    if len(tot):
        net, amt = tot["淨流入"].sum(), tot["總成交"].sum()
        c[3].metric("宇宙資金流(億)", f"{amt:,.0f} 成交",
                    f"{net:+,.1f} 淨流", delta_color="inverse")
    c[4].metric("模式", "🔴 LIVE 60s" if live else "⏸ 收盤快照",
                f"{now_tw():%H:%M:%S}", delta_color="off")

    if day.empty:
        st.info("還沒有今日快照——開盤(09:00)後這頁會自動每分鐘累積。"
                "掛著不用動,像看 Shioaji 的盤一樣。")
        return
    ddate = day.attrs.get("date", "")
    if ddate and ddate != f"{now_tw():%Y%m%d}":
        c[4].metric("資料日", f"{ddate[4:6]}/{ddate[6:]}", "最近交易日", delta_color="off")
    if tot.empty:
        st.info("快照已開始,等前兩輪取得增量後出圖(約 2 分鐘)。")
        return

    # ── ②+③ 族群資金流向泡泡圖|累計淨流排行 ──
    L, R = st.columns([3, 2])
    bub = tot.dropna(subset=["漲跌%"]).copy()
    sz = bub["總成交"].clip(lower=0.1) ** 0.5
    sz = 14 + 40 * (sz - sz.min()) / max(float(sz.max() - sz.min()), 1e-9)
    # 標籤只給成交額前 12 大(全標會疊成一團);其餘 hover 看
    big = set(bub.nlargest(12, "總成交")["group"])
    figb = go.Figure(go.Scatter(
        x=bub["淨流入"], y=bub["漲跌%"], mode="markers+text",
        hovertext=bub["group"],
        text=[g if g in big else "" for g in bub["group"]],
        textposition="top center",
        textfont=dict(size=10, color=T.MUTED),
        marker=dict(size=sz, opacity=.8, line=dict(width=1, color=T.CARD),
                    color=[T.RED if v >= 0 else T.GREEN for v in bub["淨流入"]]),
        customdata=bub["總成交"],
        hovertemplate="%{hovertext}<br>淨流入 %{x:+.2f} 億|漲跌中位 %{y:+.2f}%|"
                      "成交 %{customdata:,.1f} 億<extra></extra>"))
    figb.add_vline(x=0, line_color=T.GRID, line_width=1)
    figb.add_hline(y=0, line_color=T.GRID, line_width=1)
    figb.update_layout(height=460, margin=dict(l=10, r=10, t=36, b=10),
                       title="族群資金流向(泡泡=成交額)",
                       xaxis_title="累計淨流入(億)", yaxis_title="漲跌%(成分中位)")
    L.plotly_chart(figb, use_container_width=True)

    # 箭頭=跟前一分鐘比(最後一輪快照的增量方向;小於門檻視為持平)
    def _arrow(d, dead):
        return "▲" if d > dead else ("▼" if d < -dead else "–")

    # 防呆:長駐進程熱載入時 rt_flow 模組可能還是舊版(沒算 Δ1分)→ 頁面自己補算
    if "Δ1分" not in tot.columns and len(per_ts):
        d1g = per_ts[per_ts["ts"] == per_ts["ts"].max()].set_index("group")["flow"] / 1e4
        tot["Δ1分"] = d1g.reindex(tot["group"]).fillna(0).values

    tot_s = tot.sort_values("淨流入")
    figr = go.Figure(go.Bar(
        x=tot_s["淨流入"], y=tot_s["group"], orientation="h",
        marker_color=[T.RED if v >= 0 else T.GREEN for v in tot_s["淨流入"]],
        text=[f"{v:+.1f} {_arrow(d, .02)}"
              for v, d in zip(tot_s["淨流入"], tot_s.get("Δ1分", pd.Series(0, index=tot_s.index)))],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="%{y}<br>淨流入 %{x:+.2f} 億<extra></extra>"))
    figr.update_layout(height=460, margin=dict(l=10, r=60, t=36, b=10),
                       title="累計淨流入排行(億)",
                       xaxis=dict(range=[float(tot_s["淨流入"].min()) * 1.35 - .5,
                                         float(tot_s["淨流入"].max()) * 1.35 + .5]),
                       yaxis=dict(tickfont=dict(size=10)))
    R.plotly_chart(figr, use_container_width=True)

    # ── ④ 產業全景 treemap(面積=成交額、顏色=漲跌%) ──
    alls = RT.all_stocks(day)
    tm = alls.dropna(subset=["族群"]).query("成交額 > 0").copy()
    if len(tm):
        tm["名稱"] = tm["名稱"].fillna(tm["代號"])
        tm["標籤"] = [f"{n}<br>{p:+.1f}%" for n, p in zip(tm["名稱"], tm["漲跌%"])]
        mid = "#2A3A55" if T.MODE == "dark" else "#E7EAF0"
        figt = px.treemap(tm, path=["族群", "標籤"], values="成交額", color="漲跌%",
                          color_continuous_scale=[T.GREEN, mid, T.RED],
                          range_color=[-5, 5], color_continuous_midpoint=0)
        figt.update_traces(marker_line_width=1, marker_line_color=T.DARK,
                           textfont=dict(size=11),
                           hovertemplate="%{id}<br>成交 %{value:,.0f} 萬<extra></extra>")
        figt.update_layout(height=560, margin=dict(l=4, r=4, t=36, b=4),
                           title="產業全景(面積=成交額、紅漲綠跌)",
                           coloraxis_showscale=False)
        st.plotly_chart(figt, use_container_width=True)

    # ── 走勢:流入前 5 + 流出前 3 的盤中累積線 ──
    lead = list(tot.sort_values("淨流入").tail(5)["group"]) \
         + list(tot.sort_values("淨流入").head(3)["group"])
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

    # ── 個股貢獻排行(買超/賣超金額) ──
    if len(alls):
        g1, g2 = st.columns(2)
        a = alls.copy()
        if "Δ1分" not in a.columns:          # 同上:舊模組防呆
            sf_ = RT.stock_flows(day)
            d1s = sf_[sf_["ts"] == sf_["ts"].max()].groupby("code")["flow"].sum()
            a["Δ1分"] = a["代號"].map(d1s).fillna(0)
        a["淨流入(億)"] = (a["淨流入"] / 1e4).round(2)
        a["成交額(億)"] = (a["成交額"] / 1e4).round(2)
        # 1分動向:跟前一分鐘比——▲持續流入 / ▼轉流出 / –持平(|增量|<50萬)
        d1 = a.get("Δ1分", pd.Series(0, index=a.index)).fillna(0)
        a["1分"] = [f"{_arrow(d, 50)} {d/1e4:+.2f}" if abs(d) >= 50 else "–"
                    for d in d1]
        cols = ["代號", "名稱", "族群", "最新", "漲跌%", "淨流入(億)", "1分", "成交額(億)"]
        cfg = {"漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
               "最新": st.column_config.NumberColumn(format="%.1f"),
               "1分": st.column_config.TextColumn("1分動向", help="跟前一分鐘快照比:"
                        "▲再流入 ▼轉流出(數字=該分鐘增量,億)")}
        g1.markdown("##### 🔴 淨流入最大(買超)")
        g1.dataframe(a.nlargest(10, "淨流入")[cols], hide_index=True,
                     use_container_width=True, column_config=cfg)
        g2.markdown("##### 🟢 淨流出最大(賣超)")
        g2.dataframe(a.nsmallest(10, "淨流入")[cols], hide_index=True,
                     use_container_width=True, column_config=cfg)

    # ── 盤中強勢股(當沖觀察池) ──
    st.markdown("#### 🎯 盤中強勢股(當沖觀察池)")
    ss = RT.strong_stocks(day)
    if live and len(ss):
        try:
            pushed = RT.strong_alert(ss)          # 駐留≥10分鐘 → LINE 一次/日
            for m in pushed:
                st.toast(m.splitlines()[0])
        except Exception:
            pass
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
               "推估值,非逐筆內外盤。族群相對排序是重點;一檔多族群會分別計入"
               "(僅 treemap/個股貢獻取第一族群,避免面積重複)。"
               "資料源:證交所 MIS(上市+上櫃),免費、約 5 秒延遲。")


_live()

st.divider()
st.page_link("pages/39_強勢資金.py", label="💪 收盤後看「強勢資金」(成交注意力,含隔日沖雷達)")
st.page_link("pages/16_資金流向日誌.py", label="💸 盤後資金流向日誌(三大法人版)")

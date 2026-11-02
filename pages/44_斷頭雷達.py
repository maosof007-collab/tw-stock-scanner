# -*- coding: utf-8 -*-
"""
pages/44_斷頭雷達.py — 融資維持率警戒池+投降日回溯+個股維持率曲線
=================================================================
「需要做這個 還有掃描進line」「每一檔都要」「我選號碼應該就看的到融資維持率?」
「斷頭雷達要做」(2026-11-01)。
分層:LINE 每晚只推投降日,這頁看全池+歷史驗證+任選個股的維持率曲線。
維持率=推估(近120交易日餘額增量×收盤推加權成本;收盤÷成本÷0.6)——
絕對值僅相對比較;投降日的「融資單日減≥5%」用的是 TWSE 真實張數。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import ui_theme as T
from ui_theme import inject_css, page_header

st.set_page_config(page_title="斷頭雷達", page_icon="💥", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("斷頭雷達(融資維持率)", "MARGIN CALL RADAR", "💥")

import margin_alert as MA

# ══════════════ ⓪ 大盤殺夠了沒(整體維持率溫度計) ══════════════
# 口徑:上市融資擔保市值(Σ張數×收盤×1000)÷ TWSE 公布融資金額餘額(真值)
# 個股推估看「誰會被斷頭」,這條看「全市場殺到哪」——兩層合起來才是斷頭雷達
try:
    from macro import build_market_margin_series

    @st.cache_data(ttl=1800)
    def _mkt() -> pd.DataFrame:
        return build_market_margin_series(window_days=500)

    _mk = _mkt().copy()
except Exception:
    _mk = pd.DataFrame()

if len(_mk):
    _mk["date"] = pd.to_datetime(_mk["date"])
    # 真值欄要「夠多且夠新」才用(回補中/斷更時自動退回推估口徑,避免顯示舊日期)
    _col = "ratio"
    if "ratio_real" in _mk.columns and _mk["ratio_real"].notna().sum() > 20:
        _lr = _mk.dropna(subset=["ratio_real"])["date"].max()
        if (_mk["date"].max() - _lr).days <= 7:
            _col = "ratio_real"
    _v = _mk.dropna(subset=[_col])
    cur, cur_d = float(_v[_col].iloc[-1]), _v["date"].iloc[-1]
    _y = _v.tail(240)
    _li = _y[_col].idxmin()
    lo, lo_d = float(_y.loc[_li, _col]), _y.loc[_li, "date"]
    tw_ret = None                                   # 低點以來大盤漲跌
    _tws = _mk.dropna(subset=["twii"]) if "twii" in _mk.columns else pd.DataFrame()
    if len(_tws):
        try:
            _base = float(_tws.loc[_tws["date"] >= lo_d, "twii"].iloc[0])
            tw_ret = (float(_tws["twii"].iloc[-1]) / _base - 1) * 100
        except Exception:
            pass
    if cur >= 180:
        zi, zl = "🟢", "還沒殺到——融資老神在在"
    elif cur >= 160:
        zi, zl = "🟡", "降溫中"
    elif cur >= 130:
        zi, zl = "🟠", "關鍵壓力區——歷史常見底部"
    else:
        zi, zl = "🔴", "全面追繳——極端恐慌"

    st.markdown("#### 🌡️ 判斷:大盤殺夠了沒(整體融資維持率)")
    c0 = st.columns(4)
    c0[0].metric(f"整體維持率({cur_d:%m-%d})", f"{cur:.0f}%",
                 f"{zi} {zl}", delta_color="off")
    c0[1].metric("溫度分區", "130|160|180",
                 "追繳←壓力區←降溫←沒殺到", delta_color="off")
    c0[2].metric("近一年低點", f"{lo:.0f}%", f"{lo_d:%m/%d}", delta_color="off")
    c0[3].metric("低點以來大盤",
                 f"{tw_ret:+.1f}%" if tw_ret is not None else "—",
                 "殺進壓力區=歷史常見買點", delta_color="off")

    figm = go.Figure()
    for _y0, _y1, _fc in [(100, 130, "rgba(214,69,65,.28)"),
                          (130, 160, "rgba(230,126,34,.20)"),
                          (160, 180, "rgba(241,196,15,.12)"),
                          (180, 230, "rgba(46,204,113,.10)")]:
        figm.add_hrect(y0=_y0, y1=_y1, fillcolor=_fc, line_width=0)
    figm.add_scatter(x=_y["date"], y=_y[_col], mode="lines", name="整體維持率%",
                     line=dict(color=T.CYAN, width=2.2))
    figm.add_annotation(x=cur_d, y=cur, text=f"現在 {cur:.0f}%",
                        showarrow=True, arrowhead=2)
    figm.add_annotation(x=lo_d, y=lo, text=f"低點 {lo:.0f}%",
                        showarrow=True, arrowhead=2, ay=28)
    figm.update_layout(height=300, margin=dict(l=10, r=10, t=12, b=10),
                       yaxis_range=[min(122, lo - 8), max(198, cur + 10)],
                       showlegend=False)
    st.plotly_chart(figm, use_container_width=True)
    _note = ("" if _col == "ratio_real"
             else "(真值金額回補中,暫以 MA60 推估口徑顯示)")
    st.caption("口徑:上市融資擔保市值(Σ張數×收盤)÷ 證交所公布融資金額餘額(分母真值)"
               + _note + "。判讀:**180%+ 融資還老神在在、殺不夠**;160–180% 降溫中;"
               "**130–160% 關鍵壓力區=歷史常見底部**;<130% 全面追繳。"
               "下面的個股投降日訊號只在大盤「殺夠+止穩」後才有肉——"
               "這條溫度計就是那個「殺夠了沒」的判斷。")
    st.divider()


@st.cache_data(ttl=3600)
def _pool(_mtime: float) -> pd.DataFrame:    # _mtime 只當快取鍵:日誌更新就重讀
    df = pd.read_csv(MA.LOG, dtype={"代號": str})
    return df[df["日期"] == df["日期"].max()]


@st.cache_data(ttl=3600)
def _hist(_mtime: float) -> pd.DataFrame:
    return pd.read_csv(MA.HIST, dtype={"代號": str})


# ══════════════ ① 最新警戒池 ══════════════
if not MA.LOG.exists():
    st.info("還沒有掃描日誌——先跑 `python margin_alert.py`,"
            "之後每晚 notify_push 會自動累積。")
    st.stop()
pool = _pool(MA.LOG.stat().st_mtime)
d = pool["日期"].max()
cap_n = int((pool["類型"] == "投降日").sum())
c = st.columns(4)
c[0].metric("資料日", d[5:])
c[1].metric("警戒池(維持率<135%)", len(pool), "火藥庫:斷頭賣壓候選", delta_color="off")
c[2].metric("投降日", cap_n, "融資單日大減≥5%(真值)", delta_color="off")
c[3].metric("追繳/斷頭線", "130/120%", "券商通例", delta_color="off")

st.markdown(f"#### 💥 {d[5:]} 警戒池(維持率低到高;投降日置頂)")
f1, f2 = st.columns([1, 3])
kind = f1.selectbox("類型", ["全部", "投降日", "警戒"])
kw = f2.text_input("搜尋", "", placeholder="代號或名稱,如 3363 或 上詮")
v = pool.copy()
if kind != "全部":
    v = v[v["類型"] == kind]
if kw.strip():
    k = kw.strip()
    v = v[v["代號"].str.contains(k) | v["名稱"].astype(str).str.contains(k)]
st.dataframe(v.sort_values(["類型", "維持率%"], ascending=[False, True]),
             hide_index=True, use_container_width=True, height=380,
             column_config={
                 "漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                 "維持率%": st.column_config.NumberColumn(format="%.1f%%"),
                 "日增減%": st.column_config.NumberColumn(format="%+.2f%%"),
                 "5日增減%": st.column_config.NumberColumn(format="%+.2f%%"),
             })
st.caption("**投降日**=警戒池+融資單日減≥5%(斷頭/停損出籠=賣壓出清訊號);"
           "**警戒**=還在凹單,賣壓未出清。接刀家規:量增+價穩才接、"
           "大盤破季線禁接刀、融資使用率>30% 大跌日禁接。"
           "每晚 notify_push 掃一輪並推 LINE;白天想重掃:本機跑 "
           "`python margin_alert.py`(約 2 分鐘)。")

st.divider()

# ══════════════ ② 投降日回溯戰績 ══════════════
st.markdown("#### 📜 投降日回溯戰績(訊號日收盤買,準不準歷史說話)")
if MA.HIST.exists():
    h = _hist(MA.HIST.stat().st_mtime)
    hv = h.dropna(subset=["20日%"]).copy()
    m = st.columns(5)
    m[0].metric("訊號筆數", f"{len(h):,}", f"{h['日期'].min()[:7]} 起", delta_color="off")
    m[1].metric("5日平均", f"{h['5日%'].mean():+.1f}%",
                f"中位 {h['5日%'].median():+.1f}%", delta_color="off")
    m[2].metric("20日平均", f"{hv['20日%'].mean():+.1f}%",
                f"中位 {hv['20日%'].median():+.1f}%", delta_color="off")
    m[3].metric("20日勝率", f"{(hv['20日%'] > 0).mean()*100:.0f}%")
    m[4].metric("20日內曾漲>10%", f"{(hv['20日內最高%'] >= 10).mean()*100:.0f}%",
                "反彈肉", delta_color="off")

    g1, g2 = st.columns([3, 2])
    figh = go.Figure(go.Histogram(x=hv["20日%"].clip(-50, 80), nbinsx=50,
                                  marker_color=T.CYAN, opacity=.85))
    figh.add_vline(x=0, line_color=T.MUTED, line_dash="dash")
    figh.update_layout(height=300, margin=dict(l=10, r=10, t=36, b=10),
                       title="20日報酬分佈", xaxis_title="20日%", yaxis_title="筆數")
    g1.plotly_chart(figh, use_container_width=True)
    bym = (hv.assign(月=hv["日期"].str[:7]).groupby("月")
             .agg(筆數=("20日%", "size"), 平均20日=("20日%", "mean"),
                  勝率=("20日%", lambda s: (s > 0).mean() * 100)).round(1)
             .tail(10).reset_index())
    g2.markdown("##### 按月(訊號擁擠=崩盤月)")
    g2.dataframe(bym, hide_index=True, use_container_width=True,
                 column_config={"平均20日": st.column_config.NumberColumn(format="%+.1f%%"),
                                "勝率": st.column_config.NumberColumn(format="%.0f%%")})

    t1, t2 = st.columns(2)
    show = ["日期", "代號", "名稱", "收盤", "維持率%", "融資減%", "5日%", "20日%", "20日內最高%"]
    t1.markdown("##### 🏆 20日報酬 Top 15")
    t1.dataframe(hv.nlargest(15, "20日%")[show], hide_index=True, use_container_width=True)
    t2.markdown("##### 💀 最慘 Top 15")
    t2.dataframe(hv.nsmallest(15, "20日%")[show], hide_index=True, use_container_width=True)
    with st.expander(f"完整訊號日誌({len(h):,} 筆)——搜代號或名稱"):
        k2 = st.text_input("篩選", "", placeholder="如 4764 或 雙鍵", key="histkw")
        sub = h
        if k2.strip():
            sub = h[h["代號"].str.contains(k2.strip())
                    | h["名稱"].astype(str).str.contains(k2.strip())]
        st.dataframe(sub.sort_values("日期", ascending=False)[show], hide_index=True,
                     use_container_width=True, height=420)
    st.caption("回放方法:逐檔歷史重算(成本分段滾動 120 日,與每晚掃描同口徑),"
               "條件=維持率<135%+融資單日減≥5%+餘額≥500張+價≥10元;"
               "報酬=訊號日收盤→之後第5/20個交易日收盤。"
               "⚠ 總平均被崩盤V轉灌水:2025-04 一個月佔過半訊號(平均+16%、勝率94%),"
               "排除後平均 +5.2%/中位 +2.3%/勝率 56%;而崩跌進行中的 2025-03 是 **-6.2%、"
               "勝率 17%**——投降日訊號在「大盤止穩後」才是肉,續跌中就是接刀。"
               "家規「大盤破季線禁接刀」就是這張按月表的結論。全收等權、不含滑價;"
               "維持率是推估,看相對位置別摳絕對值。")
else:
    st.info("還沒有回溯檔——本機跑 `python margin_alert.py backfill`(約 3 分鐘)。")

st.divider()

# ══════════════ ③ 個股維持率曲線(選號碼就看得到) ══════════════
st.markdown("#### 🔍 個股查詢(任何代號——維持率/估算成本/融資餘額)")
q = st.text_input("代號或名稱", "", placeholder="如 3363、上詮、2330")
if q.strip():
    code, name = q.strip(), q.strip()
    try:
        from symbols import resolve
        code, name = resolve(q.strip())
    except Exception:
        pass
    s = MA.maint_series(code) if code else None
    if s is None or s.empty:
        st.info("查不到融資資料——代號打錯、該股無融資,"
                "或這是雲端(融資原始檔不上雲,本機才有個股曲線)。")
    else:
        r = s.iloc[-1]
        c2 = st.columns(5)
        c2[0].metric(f"{name} {code}", f"{r['收盤']:.1f}",
                     f"{(r['收盤']/s['收盤'].iloc[-2]-1)*100:+.2f}%", delta_color="inverse")
        lvl = "🔴" if r["維持率%"] < 130 else ("🟡" if r["維持率%"] < 150 else "🟢")
        c2[1].metric("估算維持率", f"{r['維持率%']:.1f}%", f"{lvl} 追繳線130%",
                     delta_color="off")
        c2[2].metric("融資餘額", f"{r['融資餘額']:,.0f} 張",
                     f"今日 {r['日增減']:+,.0f}", delta_color="off")
        c2[3].metric("融資使用率", f"{r['使用率%']:.1f}%",
                     ">30% 大跌日禁接" if r["使用率%"] > 30 else "額度充裕",
                     delta_color="off")
        d5 = (s["融資餘額"].iloc[-1] / s["融資餘額"].iloc[-6] - 1) * 100 if len(s) >= 6 else 0
        c2[4].metric("5日融資增減", f"{d5:+.1f}%",
                     "投降中" if d5 <= -5 else ("凹單中" if d5 > -2 else "緩退"),
                     delta_color="off")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38],
                            vertical_spacing=0.06,
                            specs=[[{"secondary_y": True}], [{}]],
                            subplot_titles=("股價、估算成本與融資餘額", "估算維持率%"))
        fig.add_scatter(x=s.index, y=s["收盤"], name="股價", mode="lines",
                        line=dict(color=T.CYAN, width=2), row=1, col=1)
        fig.add_scatter(x=s.index, y=s["估算成本"], name="估算成本", mode="lines",
                        line=dict(color="#FFC857", width=1.8), row=1, col=1)
        fig.add_scatter(x=s.index, y=s["融資餘額"], name="融資餘額(張)", mode="lines",
                        line=dict(color="#8FB8FF", width=1.6), row=1, col=1,
                        secondary_y=True)
        fig.add_scatter(x=s.index, y=s["維持率%"], name="維持率%", mode="lines",
                        line=dict(color=T.RED if r["維持率%"] < 135 else T.GREEN,
                                  width=2), row=2, col=1)
        fig.add_hline(y=130, line_color=T.MUTED, line_dash="dash", row=2, col=1,
                      annotation_text="追繳130")
        fig.add_hline(y=120, line_color=T.RED, line_dash="dot", row=2, col=1,
                      annotation_text="斷頭120")
        fig.update_layout(height=560, margin=dict(l=10, r=10, t=40, b=10),
                          legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("成本=近120交易日融資增量×當日收盤推加權平均(融資限期半年,"
                   "陳年成本早換手);維持率=收盤÷成本÷0.6。推估值,"
                   "看趨勢與相對位置,別摳絕對數字。")

st.divider()
st.page_link("pages/43_新面孔雷達.py", label="👀 新面孔雷達(連續上榜)")
st.page_link("pages/8_籌碼分析儀表板.py", label="🧮 籌碼分析(法人/大戶五軌)")

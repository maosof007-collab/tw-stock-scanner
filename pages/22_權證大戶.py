"""頁22 — 權證大戶進出(每日監控):佈局榜/湧入榜/退潮榜/個股資金流圖。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="權證大戶", page_icon="🐳", layout="wide")

import warrant_flow as _wf
_wf = importlib.reload(_wf)          # 迭代中模組:無條件重載

st.title("🐳 權證大戶進出")


@st.cache_data(ttl=1800, show_spinner="掃描全市場權證資金流…")
def _scan(ver: int = 1):
    return _wf.market_scan(min_med=3.0)


@st.cache_data(ttl=1800)
def _panel(ver: int = 1):
    return _wf.build_panel()


panel = _panel()
if panel.empty:
    st.info("尚無資料——本機執行 `python warrant_flow.py --backfill 120`。")
    st.stop()

last_day = panel["date"].max()
sc = _scan()
st.caption(f"資料至 **{last_day}**|樣本 {panel['ucode'].nunique()} 檔標的(僅上市權證)|"
           f"單位:百萬元|run_daily 每日自動更新。**權證錢的三種狀態:🔵天天買(佈局)、🔥突然買(事件)、⚫不買了(收割完)**。")

t_in, t_hot, t_out, t_one = st.tabs(["🔵 佈局榜(天天買)", "🔥 湧入榜(近5日)", "⚫ 退潮榜(錢走了)", "🔎 個股資金流"])

_cols = ["ucode", "name", "日中位", "近20日日均", "倍數", "連續天數", "CP比", "動向"]
_ren = {"ucode": "代號", "name": "名稱"}

with t_in:
    d = sc[sc["動向"] == "🔵 佈局中"].sort_values("連續天數", ascending=False)
    st.markdown(f"**{len(d)} 檔**:認購權證金額連續 ≥15 天高於自身中位、近20日 ≥1.5 倍——有人天天在買。")
    st.dataframe(d[_cols].rename(columns=_ren), hide_index=True, width="stretch")
    st.caption("配現股看:錢進價未動=吸籌形(最優先);錢進價已噴=行情中段。點名後→頁6體檢卡覆核。")

with t_hot:
    d = sc[sc["動向"] == "🔥 近5日湧入"].sort_values("近5日日均", ascending=False)
    st.markdown(f"**{len(d)} 檔**:近 5 日日均 ≥2× 前 20 日——短期事件錢(法說/新聞/開獎前卡位)。")
    st.dataframe(d[[c for c in _cols + ["近5日日均", "前20日日均"] if c in d.columns]]
                 .rename(columns=_ren), hide_index=True, width="stretch")
    st.caption("⚠️ 事件研究:一般爆量隔日中位 -0.22%(偏隔日沖)——湧入榜是觀察名單,不是買單。")

with t_out:
    d = sc[sc["動向"].isin(["⚫ 退潮", "🌫️ 降溫"])].sort_values("倍數")
    st.markdown(f"**{len(d)} 檔**:近20日 ≤0.7× 中位——曾經的權證熱點,錢在離場(川湖 2059 型)。")
    st.dataframe(d[_cols].rename(columns=_ren), hide_index=True, width="stretch")
    st.caption("你持有的股票出現在這裡=幫你抬轎的槓桿資金在退場,對照大戶週報決定去留。")

with t_one:
    code = st.text_input("代號", key="wb_code")
    if code.strip():
        code = code.strip()
        sf = _wf.sustained_flow(code)
        if not sf:
            st.warning("樣本不足(<40 交易日)或無此標的權證。")
        else:
            st.markdown(f"### {sf['verdict']}")
            a, b, c, dcol = st.columns(4)
            a.metric("近20日/中位", f"{sf['近20日倍數']}x", f"日中位 {sf['日中位']}", delta_color="off")
            b.metric("連續高於中位", f"{sf['連續高於中位天數']} 天")
            c.metric("call/put(20日)", f"{sf['近20日CP比']}")
            dcol.metric("近40日股價", f"{sf['近40日價格%']:+.1f}%" if sf["近40日價格%"] is not None else "—")

            g = panel[panel["ucode"] == code].sort_values("date")
            fig = go.Figure()
            fig.add_bar(x=g["date"], y=g["call_val"], name="認購權證金額(百萬)",
                        marker_color="#00C2A8", opacity=0.7)
            fig.add_bar(x=g["date"], y=-g["put_val"], name="認售(反向顯示)",
                        marker_color="#FF5C77", opacity=0.5)
            # 現股價疊加
            for suf in (".TW", ".TWO"):
                p = Path(__file__).parent.parent / "data" / f"{code}{suf}.csv"
                if p.exists():
                    px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
                    px = px[px["Date"].isin(set(g["date"]))]
                    fig.add_scatter(x=px["Date"], y=pd.to_numeric(px["Close"]),
                                    name="現股收盤", yaxis="y2",
                                    line=dict(color="#FFD166", width=2))
                    break
            fig.update_layout(height=420, barmode="overlay",
                              yaxis=dict(title="權證金額(百萬)"),
                              yaxis2=dict(overlaying="y", side="right", title="股價",
                                          showgrid=False),
                              legend=dict(orientation="h", y=1.08),
                              margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(sf["monthly"], width="stretch")
            st.caption("看圖重點:綠柱持續墊高+黃線還在低檔=佈局;綠柱消失+黃線在高檔=收割完(川湖型)。")

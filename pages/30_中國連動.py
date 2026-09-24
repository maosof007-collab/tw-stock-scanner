"""
pages/30_中國連動.py — 中國連動雷達(A股龍頭 ↔ 台股受惠對照)
=================================================================
邏輯:同題材中國龍頭常先行(光通訊=中際旭創、電子布=宏和科技、矽晶圓=滬硅)。
每天比對 A 股龍頭動能 vs 台股對照,落後太多=補漲觀察名單(不是買訊)。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="中國連動", page_icon="🐉", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("中國連動雷達", "CN-TW LINKAGE", "🐉")

import cn_link


@st.cache_data(ttl=3600, show_spinner="更新A股資料+掃描…")
def _scan(ver: int = 1):
    p = ROOT / "data" / "cn" / "_cn_scan.csv"
    if p.exists():
        import time
        if time.time() - p.stat().st_mtime < 3600 * 20:
            return pd.read_csv(p, dtype={"代碼": str})
    cn_link.fetch_cn()
    return cn_link.scan()


df = _scan()
if df.empty:
    st.warning("尚無資料——本機執行 `python cn_link.py`。")
    st.stop()

st.caption("**為什麼看這個**:光通訊(中際旭創先噴→台鏈跟上)、電子布(宏和科技)、矽晶圓(滬硅↔台勝科)"
           "都是「中國龍頭先行」的前例。**對照是題材映射不是因果**;🔥補漲觀察=中國創高+台股明顯落後,"
           "是「該去查」的名單,查完仍要過體檢卡。對照表在 data/cn_pairs.json 可自行增修。")

hot = df[df.get("燈號", "").astype(str).str.contains("🔥", na=False)]
if not hot.empty:
    st.error("🔥 補漲觀察:" + "、".join(hot["名稱"] + hot["代碼"]))

for theme, g in df.groupby("主題", sort=False):
    with st.expander(f"**{theme}**|🇨🇳 " +
                     "、".join(g[g['市場'] == '🇨🇳']['名稱']) + " ↔ 🇹🇼 " +
                     "、".join(g[g['市場'] == '🇹🇼']['名稱']), expanded=True):
        show = g[["市場", "代碼", "名稱", "20日%", "60日%", "距60日高%"] +
                 (["燈號"] if "燈號" in g.columns else [])].fillna("")
        st.dataframe(show, hide_index=True, width="stretch")

# ── 配對走勢對照(指數化=各自60日前=100)──
st.markdown("---")
st.markdown("#### 📈 配對走勢對照(各自 60 日前 = 100)")
themes = df["主題"].unique().tolist()
sel_theme = st.selectbox("主題", themes)
g = df[df["主題"] == sel_theme]
fig = go.Figure()
for _, r in g.iterrows():
    if r["市場"] == "🇨🇳":
        d = cn_link.cn_series(r["代碼"])
        c = pd.to_numeric(d["Close"], errors="coerce").dropna().tail(60) if d is not None else None
        dash, width = "solid", 3
    else:
        c = cn_link._tw_close(r["代碼"])
        c = pd.to_numeric(c, errors="coerce").dropna().tail(60) if c is not None else None
        dash, width = "dot", 1.5
    if c is None or len(c) < 30:
        continue
    idx = (c / c.iloc[0] * 100).reset_index(drop=True)
    fig.add_scatter(y=idx, name=f"{r['市場']}{r['名稱']}",
                    line=dict(dash=dash, width=width))
fig.update_layout(height=420, margin=dict(l=8, r=8, t=30, b=8),
                  legend=dict(orientation="h", y=1.1),
                  yaxis_title="指數化(60日前=100)")
st.plotly_chart(fig, width="stretch")
st.caption(f"實線=🇨🇳中國龍頭,虛線=🇹🇼台股對照。<span style='color:{MUTED}'>"
           "A股資料:yfinance(每日快取);人民幣計價,只比相對強弱不比絕對價。</span>",
           unsafe_allow_html=True)

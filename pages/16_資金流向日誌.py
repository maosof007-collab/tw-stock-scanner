"""
頁面16:資金流向日誌
================================
當日各族群法人資金流向(外資+投信)一表看完 +
盤後自動生成的 CMoney 筆記風格解讀文章(搭配當日新聞歸因)。
文章由本機盤後排程產生(法人資料 16:00 公布後),git 同步上雲。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="資金流向日誌", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("資金流向日誌", "DAILY MONEY FLOW JOURNAL", "💸")

import importlib
import money_flow_daily as _mf
if not hasattr(_mf, "build_daily_flow"):
    _mf = importlib.reload(_mf)
import analyst_report as _ar
if not hasattr(_ar, "list_articles"):
    _ar = importlib.reload(_ar)


@st.cache_data(ttl=1800, show_spinner="彙整當日族群資金流向…")
def _flow():
    return _mf.build_daily_flow()


flow, asof = _flow()
if flow.empty:
    st.info("無法人資料")
    st.stop()

st.caption(f"🕐 **資料截至 {asof}**(外資+投信買賣超,金額=股數×收盤估算;法人資料約每日16:00後更新)")

# ── 當日流向長條圖 ──
top = pd.concat([flow.head(8), flow.tail(8)]).drop_duplicates(subset=["族群"])
top = top.sort_values("當日買超(億)")
colors = ["#FF4D6D" if v > 0 else "#2BE4A8" for v in top["當日買超(億)"]]
fig = go.Figure(go.Bar(
    x=top["當日買超(億)"], y=top["族群"], orientation="h",
    marker=dict(color=colors, opacity=0.85),
    text=[f"{v:+.1f}" for v in top["當日買超(億)"]], textposition="outside",
    textfont=dict(size=11, color=THEME["text"]),
    customdata=top[["當日均漲%", "5日累計(億)"]].values,
    hovertemplate="<b>%{y}</b><br>當日 %{x:+.1f} 億｜均漲 %{customdata[0]:+.1f}%"
                  "<br>5日累計 %{customdata[1]:+.1f} 億<extra></extra>"))
fig.add_vline(x=0, line_color=THEME["muted"], line_width=1)
fig.update_layout(height=520, template="plotly_dark", paper_bgcolor=THEME["bg"],
                  plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=12),
                  margin=dict(l=10, r=40, t=20, b=10),
                  xaxis=dict(title="當日法人買賣超金額(億元)", gridcolor=THEME["grid"]))
st.plotly_chart(fig, width="stretch")

with st.expander("📋 全部族群明細"):
    st.dataframe(flow, width="stretch", hide_index=True)

# ── 盤後解讀文章 ──
st.markdown("---")
st.markdown("### 📝 盤後資金流向解讀")

arts = [a for a in _ar.list_articles() if a.get("mode") == "資金流向"]
c1, c2 = st.columns([3, 1.4])
with c2:
    import llm as _llm
    _es = _llm.engine_status()
    if st.button("🖋️ 立即產生今日解讀", type="primary", width="stretch",
                 disabled=_es["engine"] == "none",
                 help="本機盤後排程會自動產生;這裡可手動補產"):
        with st.spinner("撰寫中(約 60 秒)…"):
            fn = _mf.run(force=True)
        _ar.list_articles.__dict__.pop("clear", None)
        st.rerun()
    if _es["engine"] == "none":
        st.caption("☁️ 雲端顯示模式:文章由本機盤後自動產生同步")

if arts:
    labels = [f"{a['date'][:10]}" for a in arts]
    with c1:
        pick = st.selectbox("選擇日期", labels, key="flow_pick")
    a0 = arts[labels.index(pick)]
    st.markdown("---")
    st.markdown(_ar.read_article(a0["file"]))
else:
    st.info("尚無解讀文章——本機法人資料到位後(16:00+)排程自動產生,或按上方按鈕手動產。")

"""
頁面13:個股法人報告(六層框架 × 正反方對照 × 月營收推估)
================================================
方法論:金居六層分析師框架(驅動力→供需量化→營收模型→毛利分層
→EPS/目標價三情境→反方風險)+ 正反方對照表。
系統算可驗證的數學(出貨動能/財報結構/月營收推估),Claude 寫敘事。
補充資料(法說紀要/產能/產品佔比)貼進來會一起縫入推論。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import page_header, inject_css, MUTED, RED, GREEN, GOLD, CYAN

st.set_page_config(page_title="個股法人報告", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("個股法人報告", "EQUITY RESEARCH BUILDER", "🧾")

from analyst_report import build_digest, forecast_monthly, eps_scenarios, generate_report

c1, c2 = st.columns([1, 3])
code_in = c1.text_input("股票代碼", placeholder="4991", key="rpt_code")
extra_in = c2.text_area("補充資料(選填:法說紀要/產能/產品佔比/ASP——會縫進報告推論)",
                        height=90, key="rpt_extra")
code = code_in.strip().replace(".TW", "").replace(".TWO", "")

if not code.isdigit():
    st.info("輸入代碼後自動載入:出貨動能、財報結構、月營收推估;再一鍵產生法人報告。")
    st.stop()


@st.cache_data(ttl=3600, show_spinner="抓取財務資料中…")
def _digest(c):
    return build_digest(c)

d = _digest(code)
mon: pd.DataFrame = d["monthly"]
q: pd.DataFrame = d["quarterly"]
if mon.empty:
    st.warning("抓不到月營收資料(FinMind 限流或代碼有誤),稍後再試。")
    st.stop()

st.caption(f"**{d['code']} {d['name']}**　{d['price']}　|　{d['chips'] or ''}")

# ── ① 出貨/營收動能圖(歷史+推估) ──
st.markdown("### 📦 出貨與營收動能")
ass_c = st.columns([1, 1, 1, 3])
default_assume = d["assume"]
ov = {}
ov["保守YoY%"] = ass_c[0].number_input("保守YoY%", value=float(default_assume.get("保守YoY%", 0)), step=5.0)
ov["中性YoY%"] = ass_c[1].number_input("中性YoY%", value=float(default_assume.get("中性YoY%", 10)), step=5.0)
ov["樂觀YoY%"] = ass_c[2].number_input("樂觀YoY%", value=float(default_assume.get("樂觀YoY%", 20)), step=5.0)
ass_c[3].caption("推估=去年同月×(1+YoY)。預設值由近月動能自動導出(保守=近6月最低/中性=近3月中位/樂觀=近3月最高),可手動改。")

fc, _ = forecast_monthly(code, months=6, override=ov)
eps_sc = eps_scenarios(code, fc)

hist = mon.tail(24)
fig = go.Figure()
fig.add_trace(go.Bar(x=hist["ym"], y=hist["revenue"], name="月營收(百萬)",
                     marker_color=CYAN, opacity=0.75))
if not fc.empty:
    for col, cc, dashed in [("保守", MUTED, "dot"), ("中性", GOLD, "dash"), ("樂觀", RED, "dash")]:
        fig.add_trace(go.Scatter(x=fc["月份"], y=fc[col], name=f"推估-{col}",
                                 mode="lines+markers", line=dict(color=cc, dash=dashed, width=2)))
fig.add_trace(go.Scatter(x=hist["ym"], y=hist["yoy%"], name="YoY%", yaxis="y2",
                         mode="lines", line=dict(color=GREEN, width=1.5)))
fig.update_layout(height=380, template="plotly_dark", paper_bgcolor=THEME["bg"],
                  plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=12),
                  margin=dict(l=10, r=10, t=30, b=10),
                  yaxis=dict(title="月營收(百萬)", gridcolor=THEME["grid"]),
                  yaxis2=dict(title="YoY%", overlaying="y", side="right", showgrid=False),
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, width="stretch")

fc_col, eps_col = st.columns([3, 2])
with fc_col:
    if not fc.empty:
        st.markdown("**未來 6 個月營收推估(百萬)**")
        st.dataframe(fc, width="stretch", hide_index=True)
with eps_col:
    if not eps_sc.empty:
        st.markdown("**EPS 情境(近2季淨利率±3pp)**")
        st.dataframe(eps_sc, width="stretch", hide_index=True)

# ── ② 財報結構 ──
st.markdown("### 🧮 財報結構(毛利分層的證據)")
if not q.empty:
    qc1, qc2 = st.columns([3, 2])
    with qc1:
        figm = go.Figure()
        for col, cc in [("毛利率%", RED), ("營益率%", GOLD), ("淨利率%", CYAN)]:
            if col in q.columns:
                figm.add_trace(go.Scatter(x=q["季度"], y=q[col], name=col,
                                          mode="lines+markers", line=dict(color=cc, width=2)))
        figm.update_layout(height=300, template="plotly_dark", paper_bgcolor=THEME["bg"],
                           plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=11),
                           margin=dict(l=10, r=10, t=10, b=10),
                           yaxis=dict(title="%", gridcolor=THEME["grid"]),
                           legend=dict(orientation="h", y=1.15))
        st.plotly_chart(figm, width="stretch")
    with qc2:
        st.dataframe(q.tail(8), width="stretch", hide_index=True, height=300)

# ── ③ 法人報告 ──
st.markdown("### 🧾 產生法人報告(六層框架+正反方對照表)")
if st.button("🖋️ 產生報告", type="primary", key="rpt_go"):
    with st.spinner("撰寫法人報告中(約 30-90 秒)…"):
        rpt = generate_report(code, extra=extra_in)
    st.session_state["last_rpt"] = rpt
    st.session_state["last_rpt_code"] = code

if st.session_state.get("last_rpt") and st.session_state.get("last_rpt_code") == code:
    st.markdown("---")
    st.markdown(st.session_state["last_rpt"])
    st.download_button("⬇️ 下載報告(Markdown)",
                       st.session_state["last_rpt"].encode("utf-8"),
                       file_name=f"report_{code}.md", mime="text/markdown", key="rpt_dl")

st.caption("方法論:六層分析師框架(驅動力/供需量化/營收模型/毛利分層/估值三情境/反方風險)+"
           "正反方對照表。推估=情境試算,非投資建議;關鍵數字請自行覆核。")

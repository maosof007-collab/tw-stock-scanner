"""
頁面9：總體環境觀測（總經）
================================
核心指標：大盤融資維持率（推估）— 市場槓桿風險溫度計。
越低＝槓桿壓力越大、越接近追繳(130%)/斷頭(120%)；越高＝籌碼安定。
疊大盤指數看背離。資料：全市場融資餘額 + 收盤（維持率為推估）。
"""
import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="總經", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("總體環境觀測", "MACRO MONITOR", "🌐")

import importlib
import macro as _mc
if not hasattr(_mc, "cache_is_stale"):
    _mc = importlib.reload(_mc)
build_market_margin_series = _mc.build_market_margin_series
margin_status = _mc.margin_status
cache_is_stale = _mc.cache_is_stale


@st.cache_data(ttl=900, show_spinner="讀取大盤融資維持率快取…")
def _series():
    return build_market_margin_series(window_days=500)

c1, c2, c3 = st.columns([1.2, 1, 3])
warn = c1.selectbox("警戒線 %", [150, 180, 170, 160, 140], index=0)
if c2.button("🔄 重新彙整", help="全市場重算約 20-60 秒;每日排程會自動重算,平常不用按"):
    with st.spinner("全市場重算中（約 20-60 秒）…"):
        build_market_margin_series(rebuild=True)
    _series.clear()
    st.rerun()

s = _series()
if cache_is_stale():
    st.caption("⏳ 快取落後於最新融資資料——每日排程會自動重算;急著看最新可按「重新彙整」。")
if s.empty:
    st.warning("尚無融資資料，無法計算大盤融資維持率。請先更新融資（fetch_margin）。")
    st.stop()

last = float(s["ratio"].iloc[-1])
last_date = str(s["date"].iloc[-1].date())
txt, colkey = margin_status(last, warn)
col = THEME.get(colkey, THEME["text"])

# ── KPI ──
k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"<div class='metric-card'><div class='l'>大盤融資維持率(推估)</div>"
            f"<div class='v' style='color:{col}'>{last:.1f}%</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='metric-card'><div class='l'>狀態</div>"
            f"<div class='v' style='color:{col};font-size:1.1rem'>{txt}</div></div>", unsafe_allow_html=True)
k3.markdown(f"<div class='metric-card'><div class='l'>融資餘額(總張)</div>"
            f"<div class='v'>{s['margin_lots'].iloc[-1]:,.0f}</div></div>", unsafe_allow_html=True)
k4.markdown(f"<div class='metric-card'><div class='l'>資料日</div>"
            f"<div class='v' style='font-size:1.1rem'>{last_date}</div></div>", unsafe_allow_html=True)

# ── 圖：維持率 + 大盤指數 ──
fig = make_subplots(specs=[[{"secondary_y": True}]])
# 危險區底色（<警戒線）
fig.add_hrect(y0=100, y1=warn, fillcolor=THEME["down"], opacity=0.06, line_width=0)
# 維持率線
fig.add_trace(go.Scatter(x=s["date"], y=s["ratio"], mode="lines",
                         line=dict(color=THEME["accent"], width=2), name="融資維持率(推估)"),
              secondary_y=False)
# 大盤指數（淡）
if s["twii"].notna().any():
    fig.add_trace(go.Scatter(x=s["date"], y=s["twii"], mode="lines",
                             line=dict(color=THEME["muted"], width=1.2, dash="dot"), name="加權指數"),
                  secondary_y=True)
# 參考線
for y, cc, lab in [(warn, THEME["ma30"], f"警戒 {warn}"),
                   (130, THEME["down"], "追繳 130"),
                   (120, "#B03050", "斷頭 120"),
                   (166.7, THEME["muted"], "基準 166.7")]:
    fig.add_hline(y=y, line_dash="dash", line_color=cc, line_width=1,
                  annotation_text=lab, annotation_position="right",
                  annotation_font=dict(color=cc, size=10), secondary_y=False)

fig.update_layout(
    height=520, template="plotly_dark",
    paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
    font=dict(color=THEME["text"], size=12),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    hovermode="x unified")
fig.update_xaxes(showgrid=True, gridcolor=THEME["grid"])
fig.update_yaxes(title_text="融資維持率 %", gridcolor=THEME["grid"], secondary_y=False)
fig.update_yaxes(title_text="加權指數", showgrid=False, secondary_y=True)
st.plotly_chart(fig, width="stretch")

st.caption(
    "💡 **怎麼看**：維持率**跌破警戒線並持續走低**＝市場槓桿壓力大、追繳賣壓升高（常見於下跌段）；"
    "**高檔（>175%）**＝籌碼安定但也可能過熱。與加權指數**背離**（指數創高但維持率下滑）要留意。")
st.caption(
    f"⚠️ 維持率為**推估**（成本以 MA60 近似、融資成數 0.6）。融資資料截至 **{last_date}**，"
    "若與今日差多天，代表 fetch_margin 未跟上每日更新。")

# ═══════════════ 季節性窗口（七月前10日 + 八月後7日）═══════════════
st.markdown("---")
st.markdown("### 📅 季節性窗口（七月前10日 ＋ 八月後7日）")

from macro import seasonal_window
sw = seasonal_window()
if sw is None:
    st.caption("大盤指數資料不足，無法計算季節性。")
else:
    ctext, ckey, chint = sw["current"]
    ccol = THEME.get(ckey, THEME["text"])
    s = sw["stats"]
    c0, c1, c2, c3 = st.columns([1.5, 1, 1, 1])
    c0.markdown(f"<div class='metric-card'><div class='l'>目前位置（{sw['as_of']}）</div>"
                f"<div class='v' style='color:{ccol};font-size:1.15rem'>{ctext}</div>"
                f"<div class='l' style='margin-top:2px'>{chint}</div></div>", unsafe_allow_html=True)
    c1.markdown(f"<div class='metric-card'><div class='l'>七月前10日</div>"
                f"<div class='v' style='color:{THEME['up']}'>{s['jul']['avg']:+.2f}%</div>"
                f"<div class='l'>勝率 {s['jul']['win']:.0f}%</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='l'>八月後7日</div>"
                f"<div class='v' style='color:{THEME['up']}'>{s['aug']['avg']:+.2f}%</div>"
                f"<div class='l'>勝率 {s['aug']['win']:.0f}%</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='l'>合併(17天)</div>"
                f"<div class='v' style='color:{THEME['up']}'>{s['combo']['avg']:+.2f}%</div>"
                f"<div class='l'>勝率 {s['combo']['win']:.0f}% · 最慘 {s['combo']['worst']:+.1f}%</div></div>",
                unsafe_allow_html=True)

    with st.expander("歷年逐年報酬（TWII 實測）"):
        st.dataframe(sw["table"], width="stretch", hide_index=True,
                     column_config={
                         "七月前10日%": st.column_config.NumberColumn(format="%+.2f%%"),
                         "八月後7日%": st.column_config.NumberColumn(format="%+.2f%%"),
                         "合併%": st.column_config.NumberColumn(format="%+.2f%%"),
                     })
    st.caption("💡 FinLab 提出的日曆效應：七月漲幅多集中在**前 10 個交易日**、八月強勢在**最後 7 個交易日**。"
               "本區用我們的大盤指數(TWII)實測——僅為統計現象，**過去成立不保證未來**，仍須配合大盤/籌碼判斷。")

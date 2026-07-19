"""
頁面5：籌碼分析儀表板（接 tw_backtest 真實資料）
左側排行 / 中間 K 線疊籌碼累積線 / 右欄研究報告摘要
"""
import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))
import data_provider as dp
from ui_common import inject_css, THEME
from ui_theme import page_header

st.set_page_config(page_title="籌碼分析儀表板", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("籌碼分析儀表板", "CHIP ANALYTICS", "📊")

# ---------------- 左側欄：股號輸入（秒開）+ 排行（點按才算）----------------
if "sel_ticker" not in st.session_state:
    st.session_state.sel_ticker = "2330"

with st.sidebar:
    st.header("個股")
    ticker = st.text_input("股號", st.session_state.sel_ticker).strip()
    st.session_state.sel_ticker = ticker

    st.markdown("---")
    st.header("籌碼排行")
    days = st.selectbox("近 N 天", [1, 5, 10, 20, 60], index=1)
    metric = st.selectbox("排序指標",
                          ["外資買超%", "投信買超%", "主力買超%", "大戶買進%"])
    # 排行要掃全市場（首次約20秒），故改成點按才載入，不卡主畫面
    if st.button("🔄 載入/更新排行", use_container_width=True):
        st.session_state.show_rank = True
    if st.session_state.get("show_rank"):
        rank = dp.get_ranking(days=days, metric=metric, top_n=50)
        st.markdown(f"**近{days}天 {metric} ↓**")
        if rank.empty:
            st.caption("無排行資料（請先更新三大法人/集保）")
        for _, r in rank.head(15).iterrows():
            label = f"{r['ticker']} {r['name']}  ({'+' if r['value']>=0 else ''}{r['value']:.2f}%)"
            if st.button(label, key=f"rk_{r['ticker']}", use_container_width=True):
                st.session_state.sel_ticker = r["ticker"]
                st.rerun()
            st.markdown(f"<div class='muted'>{r['industry']} · {r['legal_action']}</div>",
                        unsafe_allow_html=True)

ticker = st.session_state.sel_ticker
name = dp.stock_name(ticker)

# ---------------- 主區 ----------------
ohlc = dp.get_ohlcv(ticker)
if ohlc.empty:
    st.warning(f"找不到 {ticker} 的股價資料（data/{ticker}.TW.csv）")
    st.stop()

last = ohlc.iloc[-1]
st.markdown(f"### {ticker} {name}")
st.caption(f"{last['date'].date()}　收 {last['close']:.2f}　"
           f"MA30 {last['ma30']:.1f}　MA60 {last['ma60']:.1f}")

main_col, right_col = st.columns([3.3, 1])

with main_col:
    from chip_chart import build_chip_figure, CHIP_TRACKS, CHIP_TRACK_LABELS
    _all_keys = [k for k, _, _ in CHIP_TRACKS]
    _sel = st.multiselect(
        "顯示軌道（可只留想看的，例如單獨看『外資/投信/法人 累積』）",
        options=_all_keys, default=_all_keys,
        format_func=lambda k: CHIP_TRACK_LABELS.get(k, k),
        key="chip_tracks")
    _h = 860 if len(_sel) >= 4 else max(300, 180 * max(1, len(_sel)) + 120)
    fig = build_chip_figure(ticker, height=_h, tracks=_sel or None)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 分點 · 近5天累計")
    bf = dp.get_branch_flows(ticker, days=days)
    if bf.empty:
        st.caption("（台股無免費逐筆分點資料來源，此區暫無資料）")
    else:
        st.dataframe(bf.rename(columns={"branch": "分點", "net_lots": "淨張數",
                                        "pct": "佔股本%"}),
                     use_container_width=True, hide_index=True, height=300)

# ---------------- 右欄：SUPER TREND 統計 + 研究報告摘要 + 情緒 ----------------
with right_col:
    from chip_chart import render_supertrend_table
    with st.expander("⚙️ SUPER TREND 參數", expanded=False):
        _p  = st.selectbox("ATR 期間", [10, 14, 20], index=0, key="st_period")
        _m  = st.selectbox("ATR 乘數", [4.0, 3.0, 2.0, 1.5], index=0, key="st_mult")
        _n  = st.selectbox("統計年數 N", [10, 5, 3, 1], index=0, key="st_years",
                           format_func=lambda y: f"回測 {y} 年")
        _mm = st.selectbox("統計窗口 M", [20, 5, 10, 60], index=0, key="st_win",
                           format_func=lambda d: f"{d} 日窗口")
    render_supertrend_table(ticker, period=_p, mult=_m, cont_window=_mm, lookback_years=_n)
    st.markdown(f"#### {ticker} {name}")
    senti = dp.get_sentiment(ticker)
    if not senti:
        st.caption("近期無研究報告（可到「研究報告瀏覽器」頁新增）")
    else:
        st.caption(f"{senti.get('報告數', 0)} 份報告")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='metric-card'><div class='v'>{senti.get('平均目標價',0):.2f}</div>"
                    f"<div class='l'>平均目標價</div></div>", unsafe_allow_html=True)
        up = senti.get("平均上行%", 0)
        c2.markdown(f"<div class='metric-card'><div class='v {'pos' if up>=0 else 'neg'}'>{up:+.1f}%</div>"
                    f"<div class='l'>平均上行</div></div>", unsafe_allow_html=True)
        sidx = senti.get("情緒指數", 0)
        c3.markdown(f"<div class='metric-card'><div class='v {'pos' if sidx>=0 else 'neg'}'>{sidx:+.2f}</div>"
                    f"<div class='l'>情緒指數</div></div>", unsafe_allow_html=True)

    st.markdown("##### 研究報告")
    reps = dp.get_reports(ticker=ticker, limit=8)
    if reps.empty:
        st.caption("近期無報告")
    for _, r in reps.iterrows():
        rate_cls = "rating-buy" if r["rating"] == "買進" else (
            "rating-sell" if r["rating"] == "賣出" else "")
        tp = r["target_price"] if r["target_price"] is not None else 0
        st.markdown(
            f"<div class='rank-row'><b>{r['date']}</b> · {r['broker']}<br>"
            f"<span class='muted'>{r['title']}</span><br>"
            f"目標價 NT$ {tp:.1f} · <span class='{rate_cls}'>{r['rating']}</span></div>",
            unsafe_allow_html=True)

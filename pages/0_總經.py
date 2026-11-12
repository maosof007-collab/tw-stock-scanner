"""
頁面9：總體環境觀測（總經）
================================
核心指標：大盤融資維持率（推估）— 市場槓桿風險溫度計。
越低＝槓桿壓力越大、越接近追繳(130%)/斷頭(120%)；越高＝籌碼安定。
疊大盤指數看背離。資料：全市場融資餘額 + 收盤（維持率為推估）。
"""
import sys
from pathlib import Path
import pandas as pd
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

# ── 📐 每日大盤解析(兩把尺+裁決樹;本機盤後自動產生,git 同步) ──
try:
    import analyst_report as _arx
    if not hasattr(_arx, "list_articles"):
        import importlib as _il
        _arx = _il.reload(_arx)
    _idx_arts = [a for a in _arx.list_articles() if a.get("mode") == "大盤解析"]
    if _idx_arts:
        _a0 = _idx_arts[0]
        _today = str(_a0.get("date", ""))[:10]
        with st.expander(f"📐 大盤解析({_today})— {_a0['title']}", expanded=False):
            _pick = st.selectbox("日期", [a["date"][:10] for a in _idx_arts],
                                 key="idx_map_pick", label_visibility="collapsed") \
                if len(_idx_arts) > 1 else _today
            _sel = next(a for a in _idx_arts if a["date"][:10] == _pick)
            st.markdown(_arx.read_article(_sel["file"]))
except Exception:
    pass

import importlib
import macro as _mc
if not hasattr(_mc, "market_margin_conclusion"):
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

# ═══════════════ 大盤融資融券日表 + 每日結論 ═══════════════
st.markdown("### 🏦 大盤融資融券（每日結論）")
_mmt = _mc.market_margin_table(days=20)
if not _mmt.empty:
    for line in _mc.market_margin_conclusion(_mmt):
        st.markdown(f"- {line}")

    def _c_chg2(v):
        if isinstance(v, (int, float)) and not pd.isna(v):
            return f"color:{'#FF4D6D' if v > 0 else ('#2BE4A8' if v < 0 else '#647B9C')}"
        return ""
    st.dataframe(
        _mmt.style.map(_c_chg2, subset=[c for c in ["融資增減", "融券增減"] if c in _mmt.columns])
            .format({"加權指數": "{:,.0f}", "融資餘額(張)": "{:,.0f}", "融資增減": "{:+,.0f}",
                     "融券餘額(張)": "{:,.0f}", "融券增減": "{:+,.0f}",
                     "維持率(推估)%": "{:.1f}"}, na_rep="—"),
        width="stretch", hide_index=True, height=420)
    st.caption("融資融券為 TWSE 盤後約 21:00 公布（白天顯示前一日屬正常）；"
               "維持率為全市場加權推估。結算日=台指期每月第三個週三。")
else:
    st.caption("融資融券彙整資料不足。")

st.caption(
    "💡 **怎麼看**：維持率**跌破警戒線並持續走低**＝市場槓桿壓力大、追繳賣壓升高（常見於下跌段）；"
    "**高檔（>175%）**＝籌碼安定但也可能過熱。與加權指數**背離**（指數創高但維持率下滑）要留意。")
st.caption(
    f"⚠️ 維持率為**推估**（成本以 MA60 近似、融資成數 0.6）。融資資料截至 **{last_date}**，"
    "若與今日差多天，代表 fetch_margin 未跟上每日更新。")

# ═══════════════ 失土收復率(大跌週期的收復廣度)═══════════════
st.markdown("---")
st.markdown("### 🧭 失土收復率（大跌週期的收復廣度）")

import recovery_rate as _rr
if not hasattr(_rr, "build_text"):
    _rr = importlib.reload(_rr)
_D = Path(__file__).parent.parent / "data"

_rb1, _rb2 = st.columns([1.2, 4])
if _rb1.button("🔄 重算收復率", help="逐檔掃全市場約 1-2 分鐘;每日排程 17:00 後會自動算"):
    with st.spinner("逐檔掃描全市場（約 1-2 分鐘）…"):
        _rr.compute()
    st.rerun()

if not (_D / "recovery_rate.csv").exists():
    st.info("尚無收復率資料——按「重算收復率」產生第一筆（或等每日排程）。")
else:
    _rh = pd.read_csv(_D / "recovery_rate.csv")
    _cur = _rh.iloc[-1]
    _delta = float(_cur["full_pct"]) - float(_rh["full_pct"].iloc[-2]) if len(_rh) > 1 else None
    _stage = _rr._stage(float(_cur["full_pct"]), float(_cur["twii_pos"]), _delta)
    _ref_md = str(_cur["ref_date"])[5:].replace("-", "/")

    r1, r2, r3, r4 = st.columns(4)
    _sub1 = f"較前日 {_delta:+.1f}pp" if _delta is not None else f"樣本 {int(_cur['n'])} 檔"
    r1.markdown(f"<div class='metric-card'><div class='l'>全收復（站回 {_ref_md} 前高）</div><div class='v'>{_cur['full_pct']:.1f}%</div><div class='l'>{_sub1}</div></div>", unsafe_allow_html=True)
    r2.markdown(f"<div class='metric-card'><div class='l'>收復過半（自低點回升 >50%）</div><div class='v'>{_cur['half_pct']:.1f}%</div><div class='l'>樣本 {int(_cur['n'])} 檔</div></div>", unsafe_allow_html=True)
    r3.markdown(f"<div class='metric-card'><div class='l'>大盤自身回升</div><div class='v'>{_cur['twii_pos']:.1f}%</div><div class='l'>週期 {str(_cur['ref_date'])[5:]} 高 → {str(_cur['bot_date'])[5:]} 底（{_cur['twii_dd']:.1f}%）</div></div>", unsafe_allow_html=True)
    r4.markdown(f"<div class='metric-card'><div class='l'>情緒階段判讀（經驗映射）</div><div class='v' style='font-size:1.05rem'>{_stage}</div></div>", unsafe_allow_html=True)

    # 結論行:營收分組差距(=資金挑不挑基本面)+今日新收復
    if pd.notna(_cur.get("rev30_pct")) and pd.notna(_cur.get("revneg_pct")):
        _sp = float(_cur["rev30_pct"]) - float(_cur["revneg_pct"])
        st.markdown(f"- 營收>30% 組收復 **{_cur['rev30_pct']:.1f}%** vs 負成長組 **{_cur['revneg_pct']:.1f}%**（差距 {_sp:+.1f}pp）"
                    f"——7/30 研究裡快彈的乾淨因子是營收;**差距拉開=資金開始挑基本面=第 8 階段確認訊號**")
    _nf = [c for c in str(_cur.get("new_full", "")).split(",") if c and c != "nan"]
    if _nf:
        from data_provider import stock_name as _sn
        st.markdown("- 本日新收復:" + "、".join(f"{c} {_sn(c)}" for c in _nf[:10])
                    + (f" …共 {len(_nf)} 檔" if len(_nf) > 10 else ""))

    # 歷史曲線(逐日累積;剛上線時只有少數點)
    if len(_rh) > 1:
        _fg = go.Figure()
        for _col, _lab, _cc in [("full_pct", "全收復%", THEME["accent"]),
                                ("half_pct", "過半%", THEME["ma30"]),
                                ("twii_pos", "大盤回升%", THEME["muted"])]:
            _fg.add_trace(go.Scatter(x=_rh["asof"], y=_rh[_col], mode="lines+markers",
                                     name=_lab, line=dict(color=_cc, width=2)))
        _fg.update_layout(height=300, template="plotly_dark", paper_bgcolor=THEME["bg"],
                          plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=12),
                          margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
        _fg.update_yaxes(title_text="%", range=[0, 105], gridcolor=THEME["grid"])
        st.plotly_chart(_fg, width="stretch")

    with st.expander("📋 逐檔明細:最接近失土線的候補(未收復、回升幅度前 20)"):
        try:
            _rd = pd.read_csv(_D / "recovery_detail.csv", dtype={"code": str})
            from data_provider import stock_name as _sn2
            _cand = _rd[~_rd["full"]].sort_values("retrace", ascending=False).head(20).copy()
            _cand["名稱"] = _cand["code"].map(_sn2)
            _cand["距失土線%"] = (_cand["last"] / _cand["ref"] - 1) * 100
            _show = _cand.rename(columns={"code": "代碼", "ref": "失土線", "bot": "週期低點",
                                          "last": "收盤", "retrace": "回升幅度", "turn": "日均額(億)"})
            st.dataframe(_show[["代碼", "名稱", "失土線", "週期低點", "收盤", "距失土線%", "回升幅度", "日均額(億)"]]
                         .style.format({"距失土線%": "{:+.1f}", "回升幅度": "{:.0%}"}),
                         width="stretch", hide_index=True, height=420)
            st.caption("回升幅度=自週期低點回升占跌幅比例(100%=收復失土)。全明細在 data/recovery_detail.csv。")
        except Exception as _e:
            st.caption(f"明細讀取失敗:{_e}")

    st.caption(f"💡 **怎麼看**:大盤回升 {_cur['twii_pos']:.0f}% 但全收復只有 {_cur['full_pct']:.1f}%"
               "=指數的 V 是權值股撐的、多數股票還在水下(寬度不足);兩者收斂才是健康回升。"
               "資料日=" + str(_cur["asof"]) + ";每日 17:00 後排程自動更新+推播一則。")

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

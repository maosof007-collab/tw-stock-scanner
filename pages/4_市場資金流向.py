"""
頁面11：市場資金流向 RRG（全球市場相對輪動）
================================================
看資金在「國家/市場」之間怎麼流：炒韓國？炒台灣？炒美股？還是炒陸股？
每個市場一條軌跡（尾巴），點＝現在位置；可播放動畫看整段資金輪動。
RS 視窗對應短線 20 日 / 波段 60 日 / 大層級 120 日的講法：
大層級找「即將切換象限」的時機，小層級找具體切入時間。
"""
import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import page_header, inject_css

st.set_page_config(page_title="市場資金流向", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("市場資金流向 RRG", "GLOBAL MONEY FLOW", "🌍")

from market_rrg import build_market_rrg, QUADRANTS, BENCHMARKS


@st.cache_data(ttl=1800, show_spinner="抓取各國指數並計算相對輪動中（首次約 20-40 秒）…")
def _rrg(rs_win, tail_days, bench_ticker):
    return build_market_rrg(rs_win=rs_win, tail_days=tail_days,
                            bench_ticker=bench_ticker)

c = st.columns([1.2, 1, 1.2, 2])
rs_win = c[0].selectbox("RS 視窗(日)", [60, 20, 120], index=0,
                        help="20=短線資金流；60=波段；120=大層級。"
                             "先用 120 找即將切換象限的市場，再用 20 找切入時間。")
tail_days = c[1].selectbox("軌跡(交易日)", [30, 15, 60], index=0)
bench_name = c[2].selectbox("比較基準", list(BENCHMARKS.keys()), index=0,
                            help="RS＝各市場指數÷基準。想看「相對台股」誰強就選台股加權。")
with c[3]:
    st.caption("")
    if st.button("🔄 重新計算"):
        _rrg.clear()

pts, tails, asof = _rrg(rs_win, tail_days, BENCHMARKS[bench_name])
if pts.empty:
    st.warning("抓不到市場指數資料（yfinance 可能暫時被限流），稍後再試。")
    st.stop()

# ── 象限計數 ──
cnt = pts["象限"].value_counts().to_dict()
k = st.columns(4)
for i, q in enumerate(["領先", "改善", "弱化", "落後"]):
    col = QUADRANTS[q]["color"]
    k[i].markdown(f"<div class='metric-card'><div class='l'>{q}（{QUADRANTS[q]['en']}）</div>"
                  f"<div class='v' style='color:{col}'>{cnt.get(q,0)}<span style='font-size:12px'> 市場</span></div></div>",
                  unsafe_allow_html=True)

# ── 軸範圍（含所有軌跡，動畫時軸固定不跳） ──
all_r = [v for t in tails.values() for v in t["ratio"]]
all_m = [v for t in tails.values() for v in t["mom"]]
xmin, xmax = min(all_r), max(all_r)
ymin, ymax = min(all_m), max(all_m)
padx = max(0.4, (xmax - xmin) * 0.12); pady = max(0.4, (ymax - ymin) * 0.12)
x0, x1 = xmin - padx, xmax + padx
y0, y1 = ymin - pady, ymax + pady

COLOR = {r["市場"]: QUADRANTS[r["象限"]]["color"] for _, r in pts.iterrows()}
names = list(pts["市場"])

# 動畫時間軸：所有市場軌跡日期的聯集，每 2 個交易日一格
dates = sorted({d for t in tails.values() for d in t["date"]})
step_dates = dates[::2]
if dates and step_dates[-1] != dates[-1]:
    step_dates.append(dates[-1])


TAIL_SHOW = 8   # 任何時刻只畫最近 N 個交易日的短尾巴（移動視窗，全畫會糊成一團）


def _traces(upto=None):
    """每個市場一條短尾巴（截至 upto 日、只取最近 TAIL_SHOW 點），點由小到大＝方向。"""
    out = []
    for nm in names:
        t = tails.get(nm)
        seg = t if upto is None else t[t["date"] <= upto]
        seg = seg.tail(TAIL_SHOW)
        col = COLOR[nm]
        n = len(seg)
        if n == 0:
            out.append(go.Scatter(x=[], y=[], mode="lines", showlegend=False))
            continue
        texts = [""] * (n - 1) + [nm]
        sizes = [3 + 10 * i / max(n - 1, 1) for i in range(n)]   # 3→13 漸大＝行進方向
        out.append(go.Scatter(
            x=list(seg["ratio"]), y=list(seg["mom"]),
            mode="lines+markers+text",
            line=dict(color=col, width=1.4), opacity=0.9,
            marker=dict(size=sizes, color=col, line=dict(width=1, color="#04070D")),
            text=texts, textposition="top center",
            textfont=dict(size=11, color=THEME["text"]),
            customdata=[[nm, str(d)[:10]] for d in seg["date"]],
            hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}<br>"
                          "RS-Ratio %{x:.2f}<br>RS-Momentum %{y:.2f}<extra></extra>",
            showlegend=False))
    return out


fig = go.Figure(data=_traces())          # 初始 = 最新位置＋短尾巴
# 四象限底色 + 中心線 + 象限文字
for (qx0, qx1, qy0, qy1, q) in [
    (100, x1, 100, y1, "領先"), (x0, 100, 100, y1, "改善"),
    (x0, 100, y0, 100, "落後"), (100, x1, y0, 100, "弱化")]:
    fig.add_shape(type="rect", x0=qx0, x1=qx1, y0=qy0, y1=qy1,
                  fillcolor=QUADRANTS[q]["color"], opacity=0.06, line_width=0, layer="below")
fig.add_hline(y=100, line_color=THEME["muted"], line_width=1)
fig.add_vline(x=100, line_color=THEME["muted"], line_width=1)
for (ax, ay, q) in [(x1, y1, "領先 LEADING"), (x0, y1, "改善 IMPROVING"),
                    (x0, y0, "落後 LAGGING"), (x1, y0, "弱化 WEAKENING")]:
    fig.add_annotation(x=ax, y=ay, text=q, showarrow=False,
                       xanchor="right" if ax == x1 else "left",
                       yanchor="top" if ay == y1 else "bottom",
                       font=dict(size=12, color=THEME["muted"]))

# ── 動畫影格 + 播放鍵 + 時間滑桿 ──
frames, steps = [], []
for d in step_dates:
    lab = str(d)[:10]
    frames.append(go.Frame(data=_traces(upto=d), name=lab))
    steps.append(dict(method="animate", label=lab[5:],
                      args=[[lab], dict(mode="immediate",
                                        frame=dict(duration=0, redraw=True),
                                        transition=dict(duration=0))]))
fig.frames = frames

fig.update_layout(
    height=640, template="plotly_dark", paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
    font=dict(color=THEME["text"], size=12), margin=dict(l=10, r=10, t=20, b=10),
    xaxis=dict(title="RS-Ratio 相對強弱 →", range=[x0, x1], gridcolor=THEME["grid"]),
    yaxis=dict(title="RS-Momentum 相對動能 ↑", range=[y0, y1], gridcolor=THEME["grid"]),
    updatemenus=[dict(
        type="buttons", direction="left", x=0.0, y=1.08, xanchor="left",
        bgcolor=THEME["panel"], font=dict(color=THEME["text"]),
        buttons=[
            dict(label="▶ 播放", method="animate",
                 args=[None, dict(frame=dict(duration=220, redraw=True),
                                  transition=dict(duration=0), fromcurrent=True)]),
            dict(label="⏸ 暫停", method="animate",
                 args=[[None], dict(mode="immediate",
                                    frame=dict(duration=0, redraw=True))]),
        ])],
    sliders=[dict(steps=steps, active=max(len(steps) - 1, 0),
                  x=0.13, y=1.10, xanchor="left", len=0.85,
                  currentvalue=dict(prefix="截至 ", font=dict(size=11)),
                  font=dict(size=9), bgcolor=THEME["panel"])])
st.plotly_chart(fig, use_container_width=True)

asof_txt = f"（資料截至 {str(asof)[:10]}）" if asof is not None else ""
st.caption(f"💡 順時針轉：**改善→領先→弱化→落後**。點**由小到大＝行進方向**，大點=最新位置；"
           f"往右上＝資金流入、往左下＝資金流出；跌破領先區後一直沒站回去＝資金棄守，先避雷。"
           f"按 ▶ 播放看近{tail_days}個交易日的資金輪動（尾巴只顯示最近 {TAIL_SHOW} 日，跟著播放移動）{asof_txt}。")

# ── 亞洲大盤對照（台/韓/日 20日報酬差 極端監測）──
st.markdown("### 🌏 亞洲大盤對照")

@st.cache_data(ttl=1800, show_spinner="計算亞洲市場對照中…")
def _asia():
    from asia_watch import asia_snapshot
    return asia_snapshot()

asia = _asia()
if asia["markets"]:
    mc = st.columns(len(asia["markets"]))
    for i, m in enumerate(asia["markets"]):
        col = "#FF4D6D" if m["dd60"] > -5 else ("#FFC857" if m["dd60"] > -15 else "#B49BFF")
        mc[i].markdown(
            f"<div class='metric-card'><div class='l'>{m['name']}</div>"
            f"<div class='v' style='color:{col};font-size:20px'>{m['chg20']:+.1f}%"
            f"<span style='font-size:11px'> /20日</span></div>"
            f"<div style='font-size:11px;color:{THEME['muted']}'>距60日高 {m['dd60']:+.1f}%</div></div>",
            unsafe_allow_html=True)
    for sp in asia["spreads"]:
        extreme = sp["pctile"] <= 2 or sp["pctile"] >= 98
        icon = "🚨" if extreme else "·"
        st.caption(f"{icon} **{sp['pair']} 20日報酬差 {sp['cur']:+.1f}pp**　"
                   f"歷史百分位 {sp['pctile']:.1f}%（{sp['n']:,} 交易日）　z={sp['z']:+.1f}σ"
                   + ("　——**史級極端狀態（僅記錄，不預測方向）**" if extreme else ""))
    st.caption("⚠️ 報酬差極端＝罕見狀態的「紀錄」，不是方向預測。歷史上缺口多靠落後方反彈收斂，"
               "但 1997-11 亞洲金融風暴（同為兩邊齊跌型）缺口曾持續擴大——極端可以更極端。")

# ── 分象限清單 ──
cc = st.columns(4)
for i, q in enumerate(["領先", "改善", "弱化", "落後"]):
    sub = pts[pts["象限"] == q]
    with cc[i]:
        st.markdown(f"<b style='color:{QUADRANTS[q]['color']}'>{q}</b>", unsafe_allow_html=True)
        for _, r in sub.iterrows():
            st.caption(f"{r['市場']}　({r['RS-Ratio']}, {r['RS-Momentum']})")

st.caption("⚠️ 各指數以當地貨幣計價（越南/新興市場用 ETF 替代），RS 為近似 JdK RRG 演算，"
           "僅供市場間相對比較，非投資建議。")

"""
頁面10：產業輪動 RRG（相對輪動圖）
================================================
把每個產業的相對強度拆成 RS-Ratio × RS-Momentum 兩軸，畫四象限：
  改善(左上) → 領先(右上) → 弱化(右下) → 落後(左下)，順時針轉。
看「哪個產業正被資金青睞」。點＝現在位置，尾巴＝近幾週軌跡。
"""
import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import page_header, inject_css

st.set_page_config(page_title="產業輪動", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("產業輪動 RRG", "SECTOR ROTATION", "🎯")

from sector_rrg import build_rrg, QUADRANTS


@st.cache_data(ttl=1800, show_spinner="計算各產業相對輪動中（首次約 15-25 秒）…")
def _rrg(weeks, ratio_win, tail_weeks, max_members):
    return build_rrg(weeks=weeks, ratio_win=ratio_win,
                     tail_weeks=tail_weeks, max_members=max_members)

c = st.columns([1, 1, 1, 1, 2])
weeks = c[0].selectbox("觀察期(週)", [52, 78, 104], index=0)
ratio_win = c[1].selectbox("平滑窗(週)", [12, 8, 16], index=0)
tail_weeks = c[2].selectbox("尾巴(週)", [8, 5, 12], index=0)
maxm = c[3].selectbox("每產業取樣", [25, 40, 15], index=0)
with c[4]:
    show_tails = st.checkbox("顯示尾巴(軌跡)", value=True,
                             help="產業近幾週移動軌跡；嫌亂可關閉")
    if st.button("🔄 重新計算"):
        _rrg.clear()

pts, tails, asof = _rrg(weeks, ratio_win, tail_weeks, maxm)
if pts.empty:
    st.warning("資料不足，無法計算 RRG。")
    st.stop()

# ── 象限計數 ──
cnt = pts["象限"].value_counts().to_dict()
k = st.columns(4)
for i, q in enumerate(["領先", "改善", "弱化", "落後"]):
    col = QUADRANTS[q]["color"]
    k[i].markdown(f"<div class='metric-card'><div class='l'>{q}（{QUADRANTS[q]['en']}）</div>"
                  f"<div class='v' style='color:{col}'>{cnt.get(q,0)}<span style='font-size:12px'> 產業</span></div></div>",
                  unsafe_allow_html=True)

# ── RRG 圖 ──
TAIL_SHOW = 5   # 尾巴只畫最近 N 週（全長軌跡交叉會糊成一團）
xs, ys = list(pts["RS-Ratio"]), list(pts["RS-Momentum"])
if show_tails:
    for t in tails.values():
        seg = t.tail(TAIL_SHOW)
        xs += list(seg["ratio"]); ys += list(seg["mom"])
xmin, xmax = min(xs), max(xs)
ymin, ymax = min(ys), max(ys)
padx = max(0.4, (xmax - xmin) * 0.15); pady = max(0.4, (ymax - ymin) * 0.15)
x0, x1 = xmin - padx, xmax + padx
y0, y1 = ymin - pady, ymax + pady

fig = go.Figure()
# 四象限底色
for (qx0, qx1, qy0, qy1, q) in [
    (100, x1, 100, y1, "領先"), (x0, 100, 100, y1, "改善"),
    (x0, 100, y0, 100, "落後"), (100, x1, y0, 100, "弱化")]:
    fig.add_shape(type="rect", x0=qx0, x1=qx1, y0=qy0, y1=qy1,
                  fillcolor=QUADRANTS[q]["color"], opacity=0.06, line_width=0, layer="below")
fig.add_hline(y=100, line_color=THEME["muted"], line_width=1)
fig.add_vline(x=100, line_color=THEME["muted"], line_width=1)
# 象限文字
for (ax, ay, q) in [(x1, y1, "領先 LEADING"), (x0, y1, "改善 IMPROVING"),
                    (x0, y0, "落後 LAGGING"), (x1, y0, "弱化 WEAKENING")]:
    fig.add_annotation(x=ax, y=ay, text=q, showarrow=False,
                       xanchor="right" if ax == x1 else "left",
                       yanchor="top" if ay == y1 else "bottom",
                       font=dict(size=12, color=THEME["muted"]))

# 每產業一條「短尾巴」：只畫最近幾週、點由小到大＝行進方向
for _, r in pts.iterrows():
    t = tails.get(r["產業"])
    col = QUADRANTS[r["象限"]]["color"]
    seg = t.tail(TAIL_SHOW) if (show_tails and t is not None) else (t.tail(1) if t is not None else None)
    if seg is None or seg.empty:
        continue
    n = len(seg)
    sizes = [4 + 9 * i / max(n - 1, 1) for i in range(n)] if n > 1 else [13]
    texts = [""] * (n - 1) + [r["產業"]]
    fig.add_trace(go.Scatter(
        x=list(seg["ratio"]), y=list(seg["mom"]),
        mode="lines+markers+text" if n > 1 else "markers+text",
        line=dict(color=col, width=1.2), opacity=0.9,
        marker=dict(size=sizes, color=col, line=dict(width=1, color="#04070D")),
        text=texts, textposition="top center", textfont=dict(size=10, color=THEME["text"]),
        customdata=[[r["產業"], r["象限"], str(d)[:10]] for d in seg["date"]],
        hovertemplate="<b>%{customdata[0]}</b>（%{customdata[1]}）%{customdata[2]}<br>"
                      "RS-Ratio %{x:.2f}<br>RS-Momentum %{y:.2f}<extra></extra>",
        showlegend=False))

fig.update_layout(
    height=620, template="plotly_dark", paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
    font=dict(color=THEME["text"], size=12), margin=dict(l=10, r=10, t=20, b=10),
    xaxis=dict(title="RS-Ratio 相對強弱 →", range=[x0, x1], gridcolor=THEME["grid"]),
    yaxis=dict(title="RS-Momentum 相對動能 ↑", range=[y0, y1], gridcolor=THEME["grid"]))
st.plotly_chart(fig, use_container_width=True)

asof_txt = f"　資料截至 **{str(asof)[:10]}**。" if asof is not None else ""
st.caption(f"💡 順時針轉：**改善→領先→弱化→落後**。點**由小到大＝行進方向**（尾巴只畫最近 {TAIL_SHOW} 週）——"
           f"往右上（領先）走＝資金流入；往左下（落後）走＝資金流出。**領先且尾巴續往右上**的產業最強。{asof_txt}")

# ── 分象限清單 ──
cc = st.columns(4)
for i, q in enumerate(["領先", "改善", "弱化", "落後"]):
    sub = pts[pts["象限"] == q]
    with cc[i]:
        st.markdown(f"<b style='color:{QUADRANTS[q]['color']}'>{q}</b>", unsafe_allow_html=True)
        for _, r in sub.iterrows():
            st.caption(f"{r['產業']}　({r['RS-Ratio']}, {r['RS-Momentum']})")

st.caption("⚠️ 產業指數為成員股等權平均、RS 為近似 JdK RRG 演算。輪動是**傾向**非保證，"
           "仍須配合個股訊號與大盤環境。")

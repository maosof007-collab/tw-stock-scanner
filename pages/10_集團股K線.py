"""
頁面7：集團股 K 線 — 把同一集團成員合成「集團指數」K 線，看是否齊漲齊跌
============================================================
做法：每檔成員以共同起點歸一化(=100) → 平均成 1 條合成 K 線（集團指數），
疊上各成員線；再用 3 個指標量化「一起動」程度：
  - 今日齊漲家數 / 總家數
  - 成員間平均相關係數（日報酬，近窗）→ 越高越同步
  - 離散度（成員區間累積報酬標準差）→ 越低越同步
集團名單可編輯：data/groups.json
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))
import data_provider as dp
from ui_common import inject_css, THEME
from ui_theme import page_header

st.set_page_config(page_title="集團股K線", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("集團股 K 線", "GROUP INDEX KLINE", "🏢")

GROUPS_FILE = Path(__file__).parent.parent / "data" / "groups.json"


@st.cache_data(ttl=600, show_spinner=False)
def _load_groups() -> dict:
    if not GROUPS_FILE.exists():
        return {}
    raw = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    return {k: [str(c).strip() for c in v]
            for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}


@st.cache_data(ttl=300, show_spinner=False)
def _build_group(members: tuple, period_days: int):
    """回傳 (合成指數df, 各成員rebased close df, 各成員ohlcv dict, 缺檔清單)"""
    closes, opens, highs, lows, vols = {}, {}, {}, {}, {}
    missing = []
    for code in members:
        df = dp.get_ohlcv(code, period_days=period_days)
        if df.empty or len(df) < 20:
            missing.append(code); continue
        df = df.set_index("date")
        closes[code] = df["close"]; opens[code] = df["open"]
        highs[code] = df["high"]; lows[code] = df["low"]; vols[code] = df["volume"]
    if not closes:
        return None, None, None, missing

    C = pd.DataFrame(closes).dropna(how="any")          # 共同交易日（交集）
    if len(C) < 20:                                      # 交集太短 → 改用聯集+補值
        C = pd.DataFrame(closes).ffill().dropna(how="any")
    idx = C.index
    O = pd.DataFrame(opens).reindex(idx).ffill()
    H = pd.DataFrame(highs).reindex(idx).ffill()
    L = pd.DataFrame(lows).reindex(idx).ffill()
    V = pd.DataFrame(vols).reindex(idx).fillna(0)

    base = C.iloc[0]                                     # 各自起點收盤 → 歸一化基準
    cR = C / base * 100
    oR = O / base * 100
    hR = H / base * 100
    lR = L / base * 100

    grp = pd.DataFrame({
        "date":   idx,
        "open":   oR.mean(axis=1).values,
        "high":   hR.mean(axis=1).values,
        "low":    lR.mean(axis=1).values,
        "close":  cR.mean(axis=1).values,
        "volume": V.sum(axis=1).values,
    })
    grp["ma20"] = grp["close"].rolling(20).mean()
    grp["ma60"] = grp["close"].rolling(60).mean()
    return grp, cR, {c: dict(close=C[c]) for c in C.columns}, missing


groups = _load_groups()
if not groups:
    st.error("找不到集團名單。請建立 data/groups.json")
    st.stop()

# ---------------- 選集團（主畫面，不靠側欄）----------------
names = list(groups.keys())
if st.session_state.get("grp_sel") not in names:
    st.session_state.grp_sel = names[0]

top = st.columns([3, 1])
with top[1]:
    period = st.selectbox("觀察期間", [120, 250, 400, 600], index=1,
                          format_func=lambda d: f"近 {d} 交易日", key="grp_period")
with top[0]:
    st.markdown("<div class='muted'>點選集團 ↓</div>", unsafe_allow_html=True)

# 集團按鈕牆（每列 6 個）
per_row = 6
for i in range(0, len(names), per_row):
    cols = st.columns(per_row)
    for j, nm in enumerate(names[i:i + per_row]):
        active = (nm == st.session_state.grp_sel)
        if cols[j].button(nm, key=f"gbtn_{nm}", use_container_width=True,
                          type=("primary" if active else "secondary")):
            st.session_state.grp_sel = nm
            st.rerun()

gname = st.session_state.grp_sel
st.markdown(f"### {gname}　<span class='muted' style='font-size:.8rem'>"
            f"{'、'.join(f'{c} {dp.stock_name(c)}' for c in groups[gname])}</span>",
            unsafe_allow_html=True)
members = tuple(groups[gname])
grp, cR, _, missing = _build_group(members, period)

if grp is None:
    st.error(f"{gname} 的成員都查無股價資料（缺：{'、'.join(missing)}）")
    st.stop()

n_have = cR.shape[1]
# ---------------- 齊動指標 ----------------
rets = cR.pct_change().dropna()
# 成員間平均相關（off-diagonal 平均）
if n_have >= 2:
    cm = rets.corr().values
    iu = np.triu_indices_from(cm, k=1)
    avg_corr = float(np.nanmean(cm[iu]))
else:
    avg_corr = float("nan")
# 今日齊漲家數
last_ret = cR.iloc[-1] / cR.iloc[-2] - 1 if len(cR) >= 2 else cR.iloc[-1] * 0
up_cnt = int((last_ret > 0).sum()); dn_cnt = int((last_ret < 0).sum())
# 區間累積報酬 & 離散度
period_ret = cR.iloc[-1] / cR.iloc[0] - 1          # 已 rebased，等於各自累積報酬/100
disp = float(period_ret.std() * 100)
grp_today = grp["close"].iloc[-1] / grp["close"].iloc[-2] - 1 if len(grp) >= 2 else 0.0
grp_period = grp["close"].iloc[-1] / grp["close"].iloc[0] - 1


def _tag(c):
    if np.isnan(c): return ("—", THEME["muted"])
    if c >= 0.7:    return ("高度同步", THEME["up"])
    if c >= 0.4:    return ("中度同步", THEME["ma30"])
    return ("各走各的", THEME["down"])


sync_txt, sync_col = _tag(avg_corr)

c1, c2, c3, c4 = st.columns(4)
with c1:
    col = THEME["up"] if grp_today >= 0 else THEME["down"]
    st.markdown(f"<div class='metric-card'><div class='l'>集團指數 今日</div>"
                f"<div class='v' style='color:{col}'>{grp_today*100:+.2f}%</div></div>",
                unsafe_allow_html=True)
with c2:
    col = THEME["up"] if up_cnt >= dn_cnt else THEME["down"]
    st.markdown(f"<div class='metric-card'><div class='l'>今日齊漲家數</div>"
                f"<div class='v' style='color:{col}'>{up_cnt} / {n_have}</div></div>",
                unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='metric-card'><div class='l'>成員平均相關</div>"
                f"<div class='v' style='color:{sync_col}'>{avg_corr:.2f} {sync_txt}</div></div>",
                unsafe_allow_html=True)
with c4:
    st.markdown(f"<div class='metric-card'><div class='l'>離散度(區間報酬σ)</div>"
                f"<div class='v'>{disp:.1f}%</div></div>",
                unsafe_allow_html=True)

# ---------------- 圖：集團指數 K 線 + 各成員疊線 ----------------
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                    vertical_spacing=0.04,
                    subplot_titles=(f"{gname} 集團指數（成員歸一化平均，起點=100）", "集團合計量"))

# 各成員 rebased 線（細、半透明）— 看是否擠成一束
palette = [THEME["accent"], THEME["ma30"], THEME["ma60"], "#7CE2FF", "#FFB86C",
           "#9D7CFF", "#56D364", "#FF7B9C", "#5AC8FA", "#C3A6FF"]
for i, code in enumerate(cR.columns):
    fig.add_trace(go.Scatter(
        x=cR.index, y=cR[code], mode="lines",
        line=dict(width=1, color=palette[i % len(palette)]),
        opacity=0.45, name=f"{code} {dp.stock_name(code)}",
        hovertemplate=f"{code} {dp.stock_name(code)}<br>%{{x|%m/%d}}  %{{y:.1f}}<extra></extra>"),
        row=1, col=1)

# 集團指數合成 K 線（粗、主角）
fig.add_trace(go.Candlestick(
    x=grp["date"], open=grp["open"], high=grp["high"], low=grp["low"], close=grp["close"],
    increasing_line_color=THEME["up"], decreasing_line_color=THEME["down"],
    increasing_fillcolor=THEME["up"], decreasing_fillcolor=THEME["down"],
    name="集團指數", whiskerwidth=0.4, line=dict(width=1.4)), row=1, col=1)
fig.add_trace(go.Scatter(x=grp["date"], y=grp["ma20"], mode="lines",
                         line=dict(color=THEME["ma30"], width=1.6), name="MA20"), row=1, col=1)
fig.add_trace(go.Scatter(x=grp["date"], y=grp["ma60"], mode="lines",
                         line=dict(color=THEME["ma60"], width=1.6), name="MA60"), row=1, col=1)

# 合計量
fig.add_trace(go.Bar(x=grp["date"], y=grp["volume"], marker_color=THEME["accent"],
                     opacity=0.5, name="合計量"), row=2, col=1)

fig.update_layout(
    height=640, template="plotly_dark",
    paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
    font=dict(color=THEME["text"], size=12),
    margin=dict(l=10, r=10, t=46, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, font=dict(size=10)),
    xaxis_rangeslider_visible=False, hovermode="x unified", bargap=0.1)
fig.update_xaxes(showgrid=True, gridcolor=THEME["grid"])
fig.update_yaxes(showgrid=True, gridcolor=THEME["grid"])
fig.update_yaxes(title_text="相對指數", row=1, col=1)
st.plotly_chart(fig, use_container_width=True)

st.caption("💡 各成員線（細）擠成一束＝集團一起動；散開＝各走各的。"
           "粗 K 線是把成員拉到同起點後平均出來的「集團指數」。")

# ---------------- 成員明細表 ----------------
st.markdown("#### 成員明細")
corr_to_grp = {}
gret = grp.set_index("date")["close"].pct_change()
for code in cR.columns:
    mret = cR[code].pct_change()
    aligned = pd.concat([mret, gret], axis=1).dropna()
    corr_to_grp[code] = aligned.iloc[:, 0].corr(aligned.iloc[:, 1]) if len(aligned) > 5 else np.nan

rows = []
for code in cR.columns:
    rows.append({
        "股號": code,
        "名稱": dp.stock_name(code),
        "今日%": round(float(last_ret[code]) * 100, 2),
        "區間%": round(float(period_ret[code]) * 100, 2),
        "與集團相關": round(float(corr_to_grp[code]), 2) if not np.isnan(corr_to_grp[code]) else None,
    })
tbl = pd.DataFrame(rows).sort_values("區間%", ascending=False).reset_index(drop=True)
if missing:
    st.caption(f"⚠️ 查無資料已略過：{'、'.join(missing)}")
st.dataframe(
    tbl, use_container_width=True, hide_index=True,
    column_config={
        "今日%": st.column_config.NumberColumn(format="%.2f%%"),
        "區間%": st.column_config.NumberColumn(format="%.2f%%"),
        "與集團相關": st.column_config.ProgressColumn(
            "與集團相關", min_value=-1.0, max_value=1.0, format="%.2f"),
    })
st.caption("「區間%」領先群 vs 落後群差距大 → 集團內部分化；"
           "「與集團相關」低的成員是脫隊者。")

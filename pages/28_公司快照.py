"""
pages/28_公司快照.py — 個股研究第一頁(仿專業研究卡)
=================================================================
分析順序:公司快照(商業模式/估值區間/EPS/獲利能力)→ 再進月營收模型(頁19)。
資料:FinMind 季損益(fundamentals.py)+ 價格庫 + tp_radar 分析師共識。
估值區間:近3年 PE 分位(P25/P50/P75)× 近4季EPS;可自填 EPS 試算。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from twtime import now_tw
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="公司快照", page_icon="🏢", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("公司快照", "COMPANY SNAPSHOT", "🏢")

D = ROOT / "data"
NOTES = D / "company_notes"
NOTES.mkdir(exist_ok=True)


def _name_sector(code):
    try:
        sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        h = sl[sl["code"] == code]
        if not h.empty:
            return h["name"].iloc[0], h["sector"].iloc[0]
    except Exception:
        pass
    return code, ""


@st.cache_data(ttl=3600, show_spinner="組裝快照…")
def _assemble(code: str) -> dict:
    import fundamentals as F
    q = F.quarterly_fin(code, years=6)
    mon = F.monthly_revenue(code, 3)
    A = {"q": q, "mon": mon}
    # 價格
    close = None
    for suf in (".TW", ".TWO"):
        p = D / f"{code}{suf}.csv"
        if p.exists():
            px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
            close = float(px["Close"].iloc[-1])
            A["px"] = px
            break
    A["close"] = close
    if q.empty:
        return A
    qq = q.copy()
    qq["dt"] = pd.to_datetime(qq["季度"])
    qq["yr"] = qq["dt"].dt.year
    qq["季別"] = qq["dt"].dt.year.astype(str).str[2:] + "Q" + qq["dt"].dt.quarter.astype(str)
    A["qq"] = qq
    # 年度 EPS / 獲利能力(僅完整年度;毛利額加權)
    ann = []
    for yr, g in qq.groupby("yr"):
        if len(g) < 4:
            continue
        rev = g["營收(億)"].sum()
        row = {"年度": int(yr), "EPS": round(g["EPS"].sum(), 2), "營收(億)": round(rev, 1)}
        for c in ("毛利率%", "營益率%", "淨利率%"):
            if c in g:
                row[c] = round((g[c] * g["營收(億)"]).sum() / rev, 2)
        ann.append(row)
    A["annual"] = pd.DataFrame(ann).tail(5)
    # TTM EPS + PE 分位帶(近3年,以「季度+45天」為可得日對齊)
    qq = qq.sort_values("dt")
    qq["ttm"] = qq["EPS"].rolling(4).sum()
    A["ttm"] = float(qq["ttm"].iloc[-1]) if pd.notna(qq["ttm"].iloc[-1]) else None
    band = None
    if close and A["ttm"] and "px" in A:
        px = A["px"].copy()
        px["Date"] = pd.to_datetime(px["Date"])
        px = px[px["Date"] >= pd.Timestamp(now_tw().date()) - pd.Timedelta(days=365 * 3)]
        me = px.groupby(px["Date"].dt.to_period("M")).last()
        avail = qq.dropna(subset=["ttm"]).copy()
        avail["ok"] = avail["dt"] + pd.Timedelta(days=45)
        pes = []
        for _, r in me.iterrows():
            known = avail[avail["ok"] <= r["Date"]]
            if known.empty or known["ttm"].iloc[-1] <= 0:
                continue
            pe = r["Close"] / known["ttm"].iloc[-1]
            if 0 < pe < 100:
                pes.append(pe)
        if len(pes) >= 12:
            band = {"p25": float(np.percentile(pes, 25)),
                    "p50": float(np.percentile(pes, 50)),
                    "p75": float(np.percentile(pes, 75))}
    A["band"] = band
    return A


# ── 選股 ──
codes_hint = st.query_params.get("code", "3042")
code = st.text_input("個股代碼或名稱", value=codes_hint, max_chars=12).strip()
from symbols import resolve as _sym_resolve
code, _rn0 = _sym_resolve(code)
if not code:
    st.stop()
name, sector = _name_sector(code)
A = _assemble(code)

c_t, c_d = st.columns([3, 1])
c_t.markdown(f"## {name} `{code}`  <span style='color:{MUTED};font-size:.85rem'>{sector}</span>",
             unsafe_allow_html=True)
c_d.caption(f"最後研究更新 {now_tw():%Y.%m.%d}")

if A["q"].empty:
    st.warning("FinMind 抓不到季度財報(額度或代碼問題)——稍後再試。")
    st.stop()

# ── 商業模式(引擎摘要,快取檔) ──
bm_p = NOTES / f"{code}_bm.md"
st.markdown("#### 公司快照")
if bm_p.exists():
    st.markdown(f"**商業模式** {bm_p.read_text(encoding='utf-8').strip()}")
else:
    st.caption("尚無商業模式摘要——按下方按鈕由引擎讀財報+營收生成(離線模式不可用)。")
if st.button("✍️ 產生/更新商業模式摘要", key="bm_btn"):
    try:
        import fundamentals as F
        from llm import generate
        d = F.build_note_digest(code)
        digest = (f"{code} {name}(產業:{sector})\n"
                  f"季度損益近3年:\n{A['q'].tail(12).to_string(index=False)}\n"
                  f"月營收近13月:\n{d['monthly'].tail(13).to_string(index=False) if not d['monthly'].empty else '無'}")
        out = generate(
            "你是產業研究員。用90-130字寫一段「商業模式」:公司做什麼、賣給誰、"
            "獲利驅動是什麼(從毛利率水準與營收季節性推斷)。只寫確定的事,不猜產品細節、"
            "不喊多空。繁體中文,一段話,不加標題。", digest, max_tokens=400)
        if out:
            bm_p.write_text(out.strip(), encoding="utf-8")
            st.rerun()
        else:
            st.warning("引擎不可用(離線)。")
    except Exception as e:
        st.warning(f"生成失敗:{e}")

st.markdown("---")

# ── 目前估值 ──
v1, v2 = st.columns([1.2, 1])
with v1:
    st.markdown(f"#### 目前估值 <span style='color:{MUTED};font-size:.75rem'>"
                f"估值基準 {now_tw():%Y.%m.%d}</span>", unsafe_allow_html=True)
    band, ttm, close = A["band"], A["ttm"], A["close"]
    if band and ttm and close:
        lo, base, hi = (round(band["p25"] * ttm, 1), round(band["p50"] * ttm, 1),
                        round(band["p75"] * ttm, 1))
        gap = (base / close - 1) * 100
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("最新收盤", f"{close:g}")
        m2.metric("合理下緣", f"{lo:g}")
        m3.metric("Base", f"{base:g}", f"距 Base {gap:+.1f}%")
        m4.metric("合理上緣", f"{hi:g}")
        st.caption(f"PE 參考帶 {band['p25']:.0f}~{band['p75']:.0f}x(近3年分位)· "
                   f"Base {band['p50']:.0f}x · 近4季EPS {ttm:.2f} → 現價 PE {close/ttm:.1f}x")
        with st.expander("▶ 自填 EPS 試算"):
            my_eps = st.number_input("你預估的年度 EPS", value=float(round(ttm, 2)), step=0.1)
            st.markdown(f"合理下緣 **{band['p25']*my_eps:.0f}** · Base **{band['p50']*my_eps:.0f}**"
                        f" · 合理上緣 **{band['p75']*my_eps:.0f}**")
        with st.expander("▶ 估值依據"):
            st.markdown("- PE 帶=近3年「每月收盤/當時已知近4季EPS」的 25/50/75 分位——"
                        "是**這檔自己的歷史區間**,不是產業比較\n"
                        "- 假設獲利結構不變;若毛利率階梯式改變(如轉型),歷史PE帶會失真\n"
                        "- 高成長股常年在上緣之上,估值帶是**錨**不是買賣訊號")
    else:
        st.info("EPS 或價格歷史不足,無法建 PE 帶。")
    # 分析師共識(有才顯示)
    try:
        from tp_radar import latest_for
        tp = latest_for(code)
        if tp and tp.get("目標價") == tp.get("目標價"):
            st.markdown(f"📊 分析師共識目標價 **{tp['方向']}{tp['目標價']:g} 元**({tp['日期']})")
    except Exception:
        pass
with v2:
    st.markdown("#### 月營收動能")
    mon = A["mon"]
    if not mon.empty:
        fig = go.Figure()
        fig.add_bar(x=mon["ym"], y=mon["revenue"], marker_color="#5f7a6a", name="月營收(百萬)")
        fig.add_scatter(x=mon["ym"], y=mon["yoy%"], yaxis="y2", name="YoY%",
                        line=dict(color="#E8873A"))
        fig.update_layout(height=230, margin=dict(l=8, r=8, t=8, b=8),
                          yaxis2=dict(overlaying="y", side="right"), showlegend=False)
        st.plotly_chart(fig, width="stretch")
        last = mon.dropna(subset=["yoy%"]).iloc[-1]
        st.caption(f"最新 {last['ym']}:YoY {last['yoy%']:+.1f}%")

# ── 年度 / 季度 EPS ──
e1, e2 = st.columns(2)
ann, qq = A["annual"], A["qq"]
with e1:
    st.markdown("#### 年度 EPS")
    fig = go.Figure(go.Bar(x=ann["年度"].astype(str), y=ann["EPS"], marker_color="#5f7a6a",
                           text=ann["EPS"], textposition="outside"))
    fig.update_layout(height=240, margin=dict(l=8, r=8, t=24, b=8))
    st.plotly_chart(fig, width="stretch")
with e2:
    st.markdown("#### 季度 EPS")
    q8 = qq.tail(8)
    fig = go.Figure(go.Bar(x=q8["季別"], y=q8["EPS"], marker_color="#5f7a6a",
                           text=q8["EPS"], textposition="outside"))
    fig.update_layout(height=240, margin=dict(l=8, r=8, t=24, b=8))
    fig.update_xaxes(type="category")
    st.plotly_chart(fig, width="stretch")

# ── 年度 / 季度 獲利能力 ──
p1, p2 = st.columns(2)
with p1:
    st.markdown("#### 年度獲利能力")
    show = ann.set_index("年度")[[c for c in ("毛利率%", "營益率%", "淨利率%") if c in ann]].T
    show.columns = show.columns.astype(str)
    st.dataframe(show, width="stretch")
with p2:
    st.markdown("#### 季度獲利能力(最新 YoY)")
    q5 = qq.tail(5).set_index("季別")
    cols = [c for c in ("毛利率%", "營益率%", "淨利率%") if c in q5]
    tbl = q5[cols].T.round(2)
    # 最新 YoY ppt:最新季 vs 去年同季
    try:
        latest_q = qq.iloc[-1]
        same = qq[(qq["dt"].dt.quarter == latest_q["dt"].quarter)
                  & (qq["yr"] == latest_q["yr"] - 1)]
        if not same.empty:
            tbl["最新YoY"] = [f"{latest_q[c] - same[c].iloc[0]:+.1f} ppt" for c in cols]
    except Exception:
        pass
    st.dataframe(tbl, width="stretch")

st.markdown("---")
n1, n2, n3, n4 = st.columns(4)
with n1:
    st.page_link("pages/29_財務九宮格.py", label="🔲 財務九宮格(體質總覽)")
with n2:
    st.page_link("pages/19_月營收預測.py", label="🔮 下一步:月營收模型(開獎前瞻)")
with n3:
    st.page_link("pages/27_個股戰情室.py", label="🎯 個股戰情室(籌碼技術一屏)")
with n4:
    st.page_link("pages/13_個股法人報告.py", label="🔬 產完整研究報告")

"""
頁面46:多空雷達 — 照族群看兩邊的錢,附兩張「已驗證」的行動清單
================================
多方候補=7/30 復盤驗證因子(營收YoY>30%+殺深>10%+未收復 → 歷史快彈率 57%)
空方命中=S1 套牢池反彈空(回測 EV10 +3.1%/勝率75%/n76,三年全正)
族群表=同族群的多方分/空方分/淨傾向——錢往哪邊倒,一眼。
"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="多空雷達", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("多空雷達", "LONG / SHORT RADAR", "⚖️")

import dual_radar as _dr
if not hasattr(_dr, "compute"):
    _dr = importlib.reload(_dr)
D = Path(__file__).parent.parent / "data"

_c1, _c2 = st.columns([1.2, 4.5])
if _c1.button("🔄 重新掃描", help="全市場逐檔掃約 1-2 分鐘;每日排程會自動掃"):
    with st.spinner("全市場掃描中(約 1-2 分鐘)…"):
        _dr.compute()
    st.cache_data.clear()
    st.rerun()

if not (D / "_dual_radar_stocks.csv").exists():
    st.info("尚無雷達資料——按「重新掃描」產生第一份(或等每日排程)。")
    st.stop()


@st.cache_data(ttl=900)
def _load():
    s = pd.read_csv(D / "_dual_radar_stocks.csv", dtype={"code": str})
    g = pd.read_csv(D / "_dual_radar_groups.csv")
    return s, g


sdf, gdf = _load()
asof = str(sdf["date"].max())
bulls = sdf[sdf["bull_cand"] == True]  # noqa: E712
s1_today = sdf[sdf["s1_today"] == True]  # noqa: E712
s1_5d = sdf[sdf["s1_hits"].fillna("") != ""]

k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"<div class='metric-card'><div class='l'>資料日</div><div class='v' style='font-size:1.1rem'>{asof}</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='metric-card'><div class='l'>🌱 多方候補(營收驗證)</div><div class='v'>{len(bulls)}</div></div>", unsafe_allow_html=True)
k3.markdown(f"<div class='metric-card'><div class='l'>🐻 S1 今日命中</div><div class='v'>{len(s1_today)}</div></div>", unsafe_allow_html=True)
_top = gdf.iloc[0]["group"] if "group" in gdf.columns and len(gdf) else (gdf.index[0] if len(gdf) else "—")
k4.markdown(f"<div class='metric-card'><div class='l'>淨傾向最多方的族群</div><div class='v' style='font-size:1.1rem'>{_top}</div></div>", unsafe_allow_html=True)

cl, cr = st.columns(2)
with cl:
    st.markdown("### 🌱 多方候補(未收復的營收加速股)")
    st.caption("出處:7/30 大跌復盤——快彈的乾淨因子是**營收 YoY**(>30% 組快彈率 57% vs 負成長 38%);"
               "貼高點/高動能反而是反指標。條件:營收YoY>30% + 自身殺幅>10% + **尚未收復失土**。")
    if bulls.empty:
        st.info("目前無候補(或失土收復明細未更新)。")
    else:
        b = bulls.sort_values("turn", ascending=False).head(25)
        st.dataframe(b[["code", "name", "group", "close", "off_hi", "flush", "retrace", "rev_yoy", "turn"]]
                     .rename(columns={"code": "代碼", "name": "名稱", "group": "族群", "close": "收盤",
                                      "off_hi": "距250高%", "flush": "殺幅%", "retrace": "回升幅度",
                                      "rev_yoy": "營收YoY%", "turn": "日均額(億)"})
                     .style.format({"回升幅度": "{:.0%}", "距250高%": "{:+.1f}", "殺幅%": "{:+.1f}",
                                    "營收YoY%": "{:+.1f}"}, na_rep="—"),
                     hide_index=True, width="stretch", height=420)
        st.caption("⚠️ 進場紀律照家規:**不接刀**——等站回 MA20/突破確認才動手;爆量 2.3× 後 2-3 天禁入。")
with cr:
    st.markdown("### 🐻 空方命中(套牢池反彈空 S1)")
    st.caption("回測 2024-01〜2026-11 全市場:**EV10 +3.1%、勝率 75%**(n=76,三年全正;成本約0.6%自行扣)。"
               "條件:距250日高>30%跌幅 + 5日漲>12% + 爆量(>2×)收黑 + 融資餘額/日均量>4。"
               "**同場陣亡:反彈失敗空、爆量長黑追空都是負EV——只空瘋狂反彈,不追殺崩跌。**")
    if s1_5d.empty:
        st.info("近 5 日無命中(月均 2-3 筆,稀有訊號;命中會推播)。")
    else:
        h = s1_5d.sort_values("chg5", ascending=False)
        st.dataframe(h[["code", "name", "group", "close", "chg5", "off_hi", "margin_mult", "vol_mult", "s1_hits"]]
                     .rename(columns={"code": "代碼", "name": "名稱", "group": "族群", "close": "收盤",
                                      "chg5": "5日漲%", "off_hi": "距250高%", "margin_mult": "套牢倍數",
                                      "vol_mult": "量倍", "s1_hits": "命中日"})
                     .style.format({"5日漲%": "{:+.1f}", "距250高%": "{:+.1f}"}, na_rep="—"),
                     hide_index=True, width="stretch", height=420)
        st.caption("⚠️ 執行:次日**開盤**進場、**持有10日時間出場**(回測口徑);"
                   "處置股不可空、先確認券源;強制回補日(股東會/除權息前)要避開。")

st.markdown("### ⚖️ 族群雙溫度表(淨傾向=多方分-空方分)")
_gshow = gdf.rename(columns={gdf.columns[0]: "族群"}) if gdf.columns[0] != "族群" else gdf


def _c_net(v):
    if isinstance(v, (int, float)) and not pd.isna(v):
        return f"color:{'#FF4D6D' if v > 0 else '#2BE4A8'}"
    return ""


st.dataframe(_gshow.style.map(_c_net, subset=[c for c in ["淨傾向"] if c in _gshow.columns])
             .format({"收復率": "{:.0%}", "破MA60比": "{:.0%}", "今日收黑比": "{:.0%}",
                      "五日中位": "{:+.1f}", "套牢倍數中位": "{:.1f}",
                      "多方分": "{:.1f}", "空方分": "{:.1f}", "淨傾向": "{:+.1f}"}, na_rep="—"),
             hide_index=True, width="stretch", height=560)
st.caption("紅=偏多、綠=偏空(台股紅漲綠跌習慣)。多方分=收復率×50+營收加速檔×5+(1-破線比)×20;"
           "空方分=破線比×40+收黑比×20+套牢倍數×3。分數是排序用的體檢,不是買賣單。")

_grp_pick = st.selectbox("看單一族群成員", ["(選擇族群)"] + sorted(sdf["group"].dropna().unique().tolist()))
if _grp_pick != "(選擇族群)":
    m = sdf[sdf["group"] == _grp_pick].sort_values("chg5", ascending=False)
    st.dataframe(m[["code", "name", "close", "chg1", "chg5", "off_hi", "below_ma60",
                    "margin_mult", "retrace", "rev_yoy", "bull_cand", "s1_today"]]
                 .rename(columns={"code": "代碼", "name": "名稱", "close": "收盤", "chg1": "當日%",
                                  "chg5": "5日%", "off_hi": "距250高%", "below_ma60": "破MA60",
                                  "margin_mult": "套牢倍數", "retrace": "回升幅度",
                                  "rev_yoy": "營收YoY%", "bull_cand": "🌱候補", "s1_today": "🐻命中"})
                 .style.format({"當日%": "{:+.1f}", "5日%": "{:+.1f}", "距250高%": "{:+.1f}",
                                "回升幅度": "{:.0%}", "營收YoY%": "{:+.1f}", "套牢倍數": "{:.1f}"},
                               na_rep="—"),
                 hide_index=True, width="stretch", height=420)

st.caption("資料:價格官方源+融資TWSE+月營收MOPS+失土收復明細(總經頁同源)。"
           "每日排程自動重掃;S1 命中會推播,多方候補看失土收復率日報。研究用途,非投資建議。")

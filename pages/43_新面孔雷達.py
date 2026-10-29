# -*- coding: utf-8 -*-
"""
pages/43_新面孔雷達.py — 連續上榜但你還沒研究過的股(全池+回溯驗證)
=================================================================
「加上 然後要去回朔」「最後找原因 是因為單純炒作? 還是有題材? 還是PE太低
還他公道」(2026-10-29)。
分層:LINE 每晚只推 5 檔摘要(釘子戶3+新面孔2),這頁看全池+歷史戰績。
性質診斷(規則式初判):還他公道(低PE補漲)/題材/題材+過熱⚠/炒作⚠/不明。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import ui_theme as T
from ui_theme import inject_css, page_header

st.set_page_config(page_title="新面孔雷達", page_icon="👀", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("新面孔雷達(連續上榜)", "NEW FACES RADAR", "👀")

import new_faces as NF


@st.cache_data(ttl=1800, show_spinner="體檢+性質診斷中…")
def _enrich(codes: tuple) -> pd.DataFrame:
    """一行體檢 + 性質診斷(炒作/題材/還他公道)——用「現在」的資料。"""
    import research_rank as RR
    rev = pd.read_csv(RR.D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    q = pd.read_csv(RR.D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    rows = []
    for c in codes:
        r = RR._one(c, rev, q) or {"代碼": c, "名稱": c}
        r["性質"], r["證據"] = NF.diagnose(c, q, r)
        rows.append(r)
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner="回溯績效計算中…")
def _perf(_mtime: float) -> pd.DataFrame:   # _mtime 只當快取鍵:日誌一更新就重算
    return NF.performance()


log = (pd.read_csv(NF.LOG, dtype={"代號": str}) if NF.LOG.exists()
       else pd.DataFrame())
if log.empty:
    st.info("還沒有提醒日誌——先跑 `python new_faces.py backfill` 建歷史,"
            "之後每晚 notify_push 會自動累積。")
    st.stop()

# ══════════════ ① 近 7 日進池 ══════════════
latest = log["提醒日"].max()
since = f"{pd.Timestamp(latest) - pd.Timedelta(days=6):%Y-%m-%d}"
pool = log[log["提醒日"] >= since].drop_duplicates("代號", keep="last").copy()
c = st.columns(4)
c[0].metric("最新掃描日", latest[5:])
c[1].metric("近7日進池", len(pool),
            f"釘子戶 {(pool['類型']=='釘子戶').sum()}|新面孔 {(pool['類型']=='新面孔').sum()}",
            delta_color="off")
c[2].metric("規則", "近5掃描日", "釘子戶=全勤+回鍋|新面孔=≥3天初見", delta_color="off")
c[3].metric("LINE 摘要", "每晚 5 檔", "全池在這頁", delta_color="off")

st.markdown(f"#### 👀 近 7 日進池({since[5:]} ~ {latest[5:]},機器挑的,等你翻牌)")
en = _enrich(tuple(sorted(pool["代號"])))
if len(en):
    v = pool.merge(en.rename(columns={"代碼": "代號"}), on="代號", how="left",
                   suffixes=("", "_e"))
    cols = ["提醒日", "代號", "名稱", "類型", "性質", "證據", "收盤", "距年高%", "60日%",
            "營收YoY3", "外資天", "融資%", "大戶%", "上榜天"]
    v = v[[k for k in cols if k in v.columns]]
    st.dataframe(v.sort_values(["類型", "60日%"], ascending=[False, False]),
                 hide_index=True, use_container_width=True, height=420,
                 column_config={
                     "距年高%": st.column_config.NumberColumn(format="%+.1f%%"),
                     "60日%": st.column_config.NumberColumn(format="%+.1f%%"),
                     "營收YoY3": st.column_config.NumberColumn(format="%+.0f%%"),
                     "融資%": st.column_config.NumberColumn(format="%.0f%%"),
                     "大戶%": st.column_config.NumberColumn(format="%.0f%%"),
                 })
st.caption("性質=規則式初判(用現在的資料):**還他公道**=PE(TTM)≤12 且營收沒爛+籌碼乾淨;"
           "**題材**=營收YoY3≥20% 或在主題族群內;**+過熱⚠**=題材真但融資/爆量/外資0 湊滿兩項;"
           "**炒作⚠**=沒基本面、純籌碼。這是翻牌順序建議,不是結論——想深挖哪檔,一句「看看XXXX」。")

st.divider()

# ══════════════ ② 回溯戰績 ══════════════
st.markdown("#### 📜 回溯戰績(雷達準不準,歷史說話)")
p = _perf(NF.LOG.stat().st_mtime)
val = p.dropna(subset=["報酬%"]).copy()
if val.empty:
    st.info("績效還算不出來(日線資料不足)。")
    st.stop()

m = st.columns(5)
m[0].metric("提醒筆數", f"{len(val):,}", f"{val['提醒日'].min()[5:]} 起", delta_color="off")
m[1].metric("平均報酬", f"{val['報酬%'].mean():+.1f}%",
            f"中位 {val['報酬%'].median():+.1f}%", delta_color="off")
m[2].metric("勝率(現價>提醒價)", f"{(val['報酬%'] > 0).mean()*100:.0f}%")
m[3].metric("曾漲逾10%", f"{(val['最高漲幅%'] >= 10).mean()*100:.0f}%",
            "提醒後任一日", delta_color="off")
m[4].metric("曾漲逾30%", f"{(val['最高漲幅%'] >= 30).mean()*100:.0f}%",
            "右尾彩券", delta_color="off")

g1, g2 = st.columns([3, 2])
figh = go.Figure(go.Histogram(x=val["報酬%"].clip(-60, 150), nbinsx=60,
                              marker_color=T.CYAN, opacity=.85))
figh.add_vline(x=0, line_color=T.MUTED, line_dash="dash")
figh.update_layout(height=320, margin=dict(l=10, r=10, t=36, b=10),
                   title="報酬分佈(右偏彩券型:多數小賠、少數大賺)",
                   xaxis_title="報酬%", yaxis_title="筆數")
g1.plotly_chart(figh, use_container_width=True)

by = (val.groupby("類型")
        .agg(筆數=("報酬%", "size"), 平均報酬=("報酬%", "mean"),
             中位=("報酬%", "median"),
             勝率=("報酬%", lambda s: (s > 0).mean() * 100),
             曾漲10=("最高漲幅%", lambda s: (s >= 10).mean() * 100))
        .round(1).reset_index())
g2.markdown("##### 分類型")
g2.dataframe(by, hide_index=True, use_container_width=True,
             column_config={"平均報酬": st.column_config.NumberColumn(format="%+.1f%%"),
                            "中位": st.column_config.NumberColumn(format="%+.1f%%"),
                            "勝率": st.column_config.NumberColumn(format="%.0f%%"),
                            "曾漲10": st.column_config.NumberColumn("曾漲>10%", format="%.0f%%")})
g2.caption("⚠ 這是「全收等權」的誠實數字——雷達是注意力漏斗,不是買單。"
           "價值在右尾:三成標的曾漲逾一成,翻牌挑出它們才是你的工作。")

t1, t2 = st.columns(2)
show = ["提醒日", "代號", "名稱", "類型", "當日收盤", "現價", "報酬%", "最高漲幅%", "天數"]
t1.markdown("##### 🏆 報酬 Top 15")
t1.dataframe(val.nlargest(15, "報酬%")[show], hide_index=True, use_container_width=True,
             column_config={"報酬%": st.column_config.NumberColumn(format="%+.1f%%"),
                            "最高漲幅%": st.column_config.NumberColumn(format="%+.1f%%")})
t2.markdown("##### 💀 最慘 Top 15")
t2.dataframe(val.nsmallest(15, "報酬%")[show], hide_index=True, use_container_width=True,
             column_config={"報酬%": st.column_config.NumberColumn(format="%+.1f%%"),
                            "最高漲幅%": st.column_config.NumberColumn(format="%+.1f%%")})

with st.expander(f"完整日誌({len(val):,} 筆)——搜代號或名稱"):
    kw = st.text_input("篩選", "", placeholder="輸入代號或名稱,如 8099 或 大世科")
    sub = val
    if kw.strip():
        k = kw.strip()
        sub = val[val["代號"].str.contains(k) | val["名稱"].astype(str).str.contains(k)]
    st.dataframe(sub.sort_values("提醒日", ascending=False)[show], hide_index=True,
                 use_container_width=True, height=480,
                 column_config={"報酬%": st.column_config.NumberColumn(format="%+.1f%%"),
                                "最高漲幅%": st.column_config.NumberColumn(format="%+.1f%%")})

st.caption("回溯方法:歷史 signals 檔逐日重放(同實盤規則+14日冷卻),全池入誌;"
           "報酬=提醒日收盤→最新收盤,最高漲幅=提醒後最高收盤。兩個已知偏差:"
           "①排除名單用今天的研究宇宙(歷史當下更少→回溯偏嚴);"
           "②性質診斷用現在的財務資料,歷史當下的標籤可能不同——所以戰績表不按性質分組,不自欺。")

st.divider()
st.page_link("pages/1_今日選股.py", label="🎯 回今日選股(策略掃描)")
st.page_link("pages/14_訊號回查.py", label="🔍 訊號回查(個股歷史)")

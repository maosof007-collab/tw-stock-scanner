# -*- coding: utf-8 -*-
"""
pages/36_迴轉率.py — 迴轉率雷達(高迴轉榜+隔日沖指紋+單檔分點驗證)
=================================================================
迴轉率=當日成交股數÷集保總股數。隔日沖為行為指紋近似(無免費逐筆分點);
要確認就用下方「分點兩日對比」抓富邦DJ驗證。這頁=家規「爆量日+2~3天禁入」名單。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, RED, inject_css, page_header

st.set_page_config(page_title="迴轉率雷達", page_icon="🌪️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("迴轉率雷達", "TURNOVER RADAR", "🌪️")

import turnover_radar as tr


@st.cache_data(ttl=3600, show_spinner="全市場掃描迴轉率…")
def _scan(ver: int = 1):
    import time
    if tr.OUT.exists() and time.time() - tr.OUT.stat().st_mtime < 3600 * 6:
        return pd.read_csv(tr.OUT, dtype={"代碼": str})
    return tr.scan()


c1, c2 = st.columns([1, 4])
if c1.button("🔄 重新掃描"):
    _scan.clear()
    tr.scan()
    st.rerun()

df = _scan()
if df.empty:
    st.info("無資料——盤後 run_daily 會自動產生。")
    st.stop()

st.caption(f"資料日:{df['日期'].iloc[0]}|迴轉率=成交股數÷集保總股數(TDCC週)。"
           "**高迴轉=籌碼一天換手一輪的賭場桌**——是觀察清單也是禁入清單。")

warn = df[df["隔日沖指紋"].astype(str).str.contains("警戒", na=False)]
dump = df[df["隔日沖指紋"].astype(str).str.contains("昨鎖今倒", na=False)]
m1, m2, m3 = st.columns(3)
m1.metric("高迴轉入榜", len(df))
m2.metric("🔪 明日賣壓警戒", len(warn))
m3.metric("🩸 昨鎖今倒", len(dump))

if len(warn):
    st.error("🔪 **今日鎖量名單(漲≥8%+量比≥2.5)——明日開盤有隔日沖賣壓窗,家規禁入**:"
             + "、".join(f"{r['名稱']}{r['代碼']}" for _, r in warn.iterrows()))
if len(dump):
    st.warning("🩸 昨鎖今倒(教材組):" + "、".join(f"{r['名稱']}{r['代碼']}" for _, r in dump.iterrows()))

st.dataframe(df, hide_index=True, width="stretch", height=520)
st.caption("判讀:①迴轉率>20%=當沖/隔日沖主戰場,波動與你無關,是資金在對打 "
           "②🔪 警戒股想買=等 2~3 天洗完量縮回測(彰源教案) ③連續多日高迴轉+價不跌=有人真的在收(對照還沒發動名單)。")

# ── 分點兩日對比(單檔驗證隔日沖指紋)──────────────────
st.markdown("---")
st.markdown("### 🔬 分點兩日對比|驗證到底是不是隔日沖")
_q = st.text_input("代碼/名稱", key="tr_q", placeholder="例:6127 或 九豪")
_cc1, _cc2 = st.columns(2)
_d1 = _cc1.text_input("鎖量日(買進日)", value="", placeholder="2026-10-8", key="tr_d1")
_d2 = _cc2.text_input("次日(出貨日)", value="", placeholder="2026-10-9", key="tr_d2")
if st.button("🔬 抓分點對比", key="tr_btn") and _q.strip() and _d1.strip() and _d2.strip():
    from symbols import resolve as _rs
    code, nm = _rs(_q.strip())
    if not code:
        st.warning("代碼解析失敗。")
    else:
        with st.spinner("抓富邦DJ分點…"):
            try:
                out = tr.fetch_branch_days(code, _d1.strip(), _d2.strip())
                st.markdown(f"**{nm} {code}**|{_d1} 買超前15 在 {_d2} 的動作:")
                st.dataframe(out, hide_index=True, width="stretch")
                n_dump = int(out["判定"].astype(str).str.contains("🩸").sum())
                st.caption(f"🩸 隔日沖指紋 {n_dump}/15 —— 過半=隔日沖主導的行情,"
                           "跌下來不是利空是出貨;少數=真有人在收。來源:富邦DJ(公開分點日報)。")
            except Exception as e:
                st.warning(f"抓取失敗:{e}")

st.caption(f"<span style='color:{MUTED}'>隔日沖指紋為行為近似(漲幅+量比+迴轉率),"
           f"確認請用分點對比。本頁每日盤後自動更新。</span>", unsafe_allow_html=True)

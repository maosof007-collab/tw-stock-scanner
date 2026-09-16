"""頁25 — M哥選股地圖:五關串聯漏斗(長多位階→大錢進場→量縮不跌→突破確認)。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="M哥選股地圖", page_icon="🗺️", layout="wide")

import mmap_funnel as _mm
_mm = importlib.reload(_mm)          # 迭代中模組:無條件重載

st.title("🗺️ M哥選股地圖(五關漏斗)")
st.caption("**不是找現在最強的,而是找「即將進入長期多頭」的**:①A 位階(240MA翻揚站上)→ "
           "②B1 大錢進場(大戶連升不減)→ ③B2 量縮不跌(賣壓消失)→ ④量增突破確認 → ⑤D/E/F 強化欄。"
           "回測 2016-2026(2,617筆):**60日賺>30%比率 12.6%(基準7.6%),2026年 34.8%;虧>20%僅8.2%**——右尾不對稱,配「出場越鬆越賺」家規使用。")

pool = _mm.load_pool()
c_scan, c_info = st.columns([1, 3])
if c_scan.button("🔄 重掃全市場(約2-3分鐘)", type="primary"):
    with st.spinner("五關漏斗掃描中…"):
        r = _mm.scan_today()
    pool = r["pool"]
    st.session_state["mmap_funnel"] = r["funnel"]
    st.rerun()

if pool.empty:
    st.info("尚無候選池——按左上「重掃全市場」,或等每日 run_daily 自動掃。")
    st.stop()

c_info.caption(f"候選池掃描日:**{pool['掃描日'].iloc[0]}**(run_daily 每日自動重掃)")

# 漏斗視覺
fn = st.session_state.get("mmap_funnel")
if fn:
    cols = st.columns(len(fn))
    for i, (k, v) in enumerate(fn.items()):
        cols[i].metric(k, v)

# 🎯 剛突破
br = pool[pool["狀態"].str.contains("突破")]
st.markdown(f"### 🎯 剛突破(近3日,{len(br)} 檔)——地圖第④關:第一根K別追,回測不破再進")
if len(br):
    st.dataframe(br.drop(columns=["掃描日"]), hide_index=True, width="stretch")
else:
    st.caption("目前無新突破——蓄勢池才是彈藥庫,突破日它們會自動跳上來。")

# ⏳ 蓄勢池
wt = pool[~pool["狀態"].str.contains("突破")]
st.markdown(f"### ⏳ 蓄勢池(量縮不跌,{len(wt)} 檔)——地圖說的「賣壓消失、等量增」")
st.dataframe(wt.drop(columns=["掃描日"]), hide_index=True, width="stretch")

st.markdown("""
**用法(照地圖的紀律)**:
1. 蓄勢池=觀察名單,**不進場**;等它「量增突破」跳進 🎯 榜;
2. 突破後不追第一根 K:回測平台不破再進,體檢卡過(紅燈<2)、決策日誌記了才算單;
3. 強化欄自查:催化(YoY 轉強?)、大戶Δ(E:還在集中?)、倒貨率(F 反證:≥30% 的爆量日小心假突破);
4. 進場標準倉,**重壓留給賺 1R 之後的金字塔加碼**——大甲是抱出來的,不是選出來的。

**常見誤區(地圖原文)**:只看營收/只看法人單日/忽略量縮不跌/追已漲一大段/沒查大賣悄悄出貨/只信單一指標。
""")

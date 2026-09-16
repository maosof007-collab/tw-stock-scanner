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

# ── 🗺️ 地圖視覺(仿海報五關,數字即時)──
fn = st.session_state.get("mmap_funnel") or _mm.load_funnel() or {}
_n_all = fn.get("全市場(流動性過)", "—")
_n_a = fn.get("A 長多位階", "—")
_n_b1 = fn.get("B1 大戶不減", "—")
_n_b2 = fn.get("B2/④ 量縮不跌或突破", len(pool))
_n_br = int(pool["狀態"].str.contains("突破").sum())
_stages = [
    ("①A", "長多·即將長多", "#E5484D", _n_a,
     ["10年月線是否轉強", "240MA 走平或翻揚", "股價站上均線", "產業長期成長"],
     "找「長多的起點」,不是漲一大段的"),
    ("②B1", "大錢開始進來", "#E8873A", _n_b1,
     ["大戶持股比例逐步上升", "股東總人數下降", "法人持續買超", "融資不暴增"],
     "看的是連續性與斜率,不是單日"),
    ("③B2", "量縮不跌·賣壓消失", "#D6B60A", "含下關",
     ["成交量明顯縮小", "股價不再下跌", "關鍵均線不破", "低點逐步墊高"],
     "量縮+不跌=想賣的人賣完了"),
    ("④", "確認啟動·量增突破", "#2E9E5B", f"{_n_b2}(🎯{_n_br})",
     ["量能重新放大", "突破整理平台", "短期高點墊高", "第一根K別追"],
     "回測不破再進,寧可買貴不買錯"),
    ("⑤C", "趨勢還有多久", "#3B82F6", "強化欄",
     ["催化:營收YoY", "E:大戶4週Δ", "F反證:倒貨率", "體檢卡守門"],
     "評估空間與時間,才決定倉位"),
]
_cards = ""
for tag, title, color, n, checks, note in _stages:
    lis = "".join(f"<div style='font-size:.72rem;color:#c8d3e0;padding:1px 0'>☑ {c}</div>" for c in checks)
    _cards += (
        f"<div style='flex:1;min-width:150px;background:#141a24;border:1px solid {color}55;"
        f"border-top:3px solid {color};border-radius:10px;padding:8px 10px;margin:0 3px'>"
        f"<div style='color:{color};font-weight:800;font-size:.95rem'>{tag} {title}</div>"
        f"<div style='color:#fff;font-weight:700;font-size:1.25rem;padding:2px 0'>{n} <span style='font-size:.7rem;color:#8b98a8'>檔</span></div>"
        f"{lis}"
        f"<div style='font-size:.7rem;color:{color};margin-top:4px'>💡 {note}</div></div>")
st.markdown(
    f"<div style='display:flex;flex-wrap:wrap;align-items:stretch;margin-bottom:6px'>{_cards}</div>"
    f"<div style='text-align:center;color:#8b98a8;font-size:.78rem;margin-bottom:8px'>"
    f"全市場 {_n_all} 檔 ➜ 位階 {_n_a} ➜ 大戶 {_n_b1} ➜ <b style='color:#2E9E5B'>候選池 {_n_b2} 檔(少而精)</b>"
    f"|用機率思維做決策,在不確定中找到最值得下注的那一檔</div>",
    unsafe_allow_html=True)

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

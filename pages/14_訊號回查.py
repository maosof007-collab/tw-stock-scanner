"""
頁面14:訊號回查(這檔,策略以前找到過嗎?)
================================================
Key 股號 → ①歷史掃描出現紀錄(哪天/什麼等級/哪個策略)
②有沒有加入過持倉 ③為什麼當初沒選到(規則式診斷)
④K線圖疊「掃描BUY日」與策略歷史訊號,眼見為憑。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import page_header, inject_css, MUTED, GREEN, RED, GOLD

st.set_page_config(page_title="訊號回查", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("訊號回查", "SIGNAL LOOKBACK", "🔎")

import importlib
import signal_history as _sh
if not hasattr(_sh, "diagnose"):
    _sh = importlib.reload(_sh)

code = st.text_input("股票代碼", placeholder="2031", key="lb_code").strip()\
        .replace(".TW", "").replace(".TWO", "")
if not code.isdigit():
    st.info("輸入代碼,查它在歷史掃描中出現過幾次、哪幾天、為什麼當初沒選到。")
    st.stop()

name = ""
try:
    sl = pd.read_csv(Path(__file__).parent.parent / "data" / "stock_list.csv",
                     encoding="utf-8-sig", dtype=str)
    hit = sl[sl["code"] == code]
    name = hit["name"].iloc[0] if not hit.empty else ""
except Exception:
    pass

hist = _sh.scan_history(code)
pf = _sh.portfolio_history(code)

# ── 統計卡 ──
buys = hist[hist["等級"].str.startswith("BUY")] if not hist.empty else pd.DataFrame()
k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"<div class='metric-card'><div class='l'>{code} {name} 出現筆數</div>"
            f"<div class='v'>{len(hist)}</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='metric-card'><div class='l'>BUY 級次數</div>"
            f"<div class='v' style='color:{GREEN if len(buys) else MUTED}'>{len(buys)}</div></div>",
            unsafe_allow_html=True)
k3.markdown(f"<div class='metric-card'><div class='l'>最近一次 BUY</div>"
            f"<div class='v' style='font-size:18px'>{buys['掃描日'].iloc[-1] if not buys.empty else '—'}</div></div>",
            unsafe_allow_html=True)
k4.markdown(f"<div class='metric-card'><div class='l'>加入過持倉</div>"
            f"<div class='v' style='font-size:18px'>{('✅ '+str(len(pf))+' 次') if not pf.empty else '沒有'}</div></div>",
            unsafe_allow_html=True)

# ── 診斷 ──
st.markdown("### 🧭 為什麼當初沒選到?")
for line in _sh.diagnose(code, hist, pf):
    st.markdown(f"- {line}")

# ── 明細 ──
if not hist.empty:
    st.markdown("### 📜 歷史出現明細")
    def _c_grade(v):
        s = str(v)
        if s.startswith("BUY"):
            return f"color:{GREEN};font-weight:700"
        if s in ("SETUP",):
            return f"color:{GOLD}"
        return f"color:{MUTED}"
    st.dataframe(hist.style.map(_c_grade, subset=["等級"]),
                 width="stretch", hide_index=True,
                 height=min(420, len(hist) * 36 + 60))
if not pf.empty:
    st.markdown("### 💼 持倉紀錄對照")
    st.dataframe(pf, width="stretch", hide_index=True)

# ── K線疊訊號 ──
st.markdown("### 📈 K 線對照(▲=掃描 BUY 日)")
tk_full = ""
for suf in (".TW", ".TWO"):
    if (Path(__file__).parent.parent / "data" / f"{code}{suf}.csv").exists():
        tk_full = f"{code}{suf}"; break
if tk_full:
    strat_pick = ""
    if not hist.empty:
        strats = sorted(set(hist["策略"]))
        strat_pick = st.selectbox("疊哪個策略的歷史買賣訊", ["(不疊)"] + strats, index=min(1, len(strats)))
    from kline_chart import render_kline
    render_kline(tk_full, name,
                 strategy_name=("" if strat_pick in ("", "(不疊)") else strat_pick),
                 bars=200, height=480,
                 show_strategy_signals=(strat_pick not in ("", "(不疊)")))
    if not buys.empty:
        st.caption("BUY 掃描日:" + "、".join(buys["掃描日"]) +
                   "——對照上圖位置,看當時進場後走勢如何(這就是「錯過成本」的具象化)。")
else:
    st.caption("找不到價格檔。")

st.caption(f"掃描檔涵蓋:2026-06-03 起(共 {len(list((Path(__file__).parent.parent/'scan_results').glob('signals_*.csv')))} 個掃描日)。"
           "更早的日子沒有掃描紀錄,策略「歷史上會不會觸發」可用上圖疊策略訊號回看。")

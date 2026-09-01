"""
頁面18:大戶籌碼週報(集保股權分散表)
================================
每週五快照:400張以上大戶持股比例的週變化。
① 五週成績單(大戶買組 vs 賣組的次週報酬——誰在防守)
② 回頭車(上週賣→本週買)/下車(上週買→本週賣)
③ 本週大戶買/賣 Top 清單
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="大戶籌碼週報", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("大戶籌碼週報", "BIG HOLDER WEEKLY", "🐘")

import importlib
import big_holder as _bh
if not hasattr(_bh, "weekly_lists"):
    _bh = importlib.reload(_bh)


@st.cache_data(ttl=3600, show_spinner="彙整集保大戶週變化…")
def _data():
    return _bh.weekly_lists()


r = _data()
if "error" in r:
    st.info(r["error"])
    st.stop()

st.caption(f"🕐 **資料週:{r['week']}**(vs 上週 {r['prev']});集保股權分散表每週五快照、"
           f"隔週初公布。口徑:400張以上持股比例週變化(pp),|Δ|>15pp 視為股本事件剔除,"
           f"均量≥500張。")

# ── ① 五週成績單 ──
st.markdown("### 🏁 成績單:大戶買組 vs 大戶賣組(次週報酬)")
co = r["cohort"]
if not co.empty:
    st.dataframe(co, width="stretch", hide_index=True)
    # 自動結論:下跌週誰抗跌/上漲週誰彈更凶
    down = co[(co["大盤%"] < 0) & co["大戶買組%"].notna() & co["大戶賣組%"].notna()]
    up = co[(co["大盤%"] > 0) & co["大戶買組%"].notna() & co["大戶賣組%"].notna()]
    d_win = (down["大戶買組%"] > down["大戶賣組%"]).sum()
    u_win = (up["大戶賣組%"] > up["大戶買組%"]).sum()
    st.info(f"🧭 **誰在防守**:下跌週 {len(down)} 次中大戶買組抗跌 {d_win} 次;"
            f"上漲週 {len(up)} 次中散戶接的那組彈更凶 {u_win} 次。"
            f"結論與旺來方法論一致:**「跟大戶」是防守訊號,不是進攻訊號**——"
            f"殺盤時看大戶名單找抗跌,反彈時別嫌散戶組會噴。")

# ── ② 回頭車 / 下車 ──
c1, c2 = st.columns(2)
with c1:
    st.markdown("### 🔄 回頭車(上週賣→本週買)")
    rc = r["return_car"]
    if not rc.empty:
        avg = rc["本週漲跌%"].mean()
        st.caption(f"共 {len(rc)} 檔,本週平均 {avg:+.1f}%——「認錯回補付溢價」型")
        st.dataframe(rc, width="stretch", hide_index=True)
    else:
        st.caption("本週無")
with c2:
    st.markdown("### 🚪 下車(上週買→本週賣)")
    ec = r["exit_car"]
    if not ec.empty:
        avg = ec["本週漲跌%"].mean()
        st.caption(f"共 {len(ec)} 檔,本週平均 {avg:+.1f}%——多為獲利了結,非停損")
        st.dataframe(ec, width="stretch", hide_index=True)
    else:
        st.caption("本週無")

# ── ③ 本週大戶動向 Top ──
with st.expander("📋 本週大戶買超/賣超 Top 20(Δpp)", expanded=False):
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**大戶買組(Δ≥+1pp)**")
        st.dataframe(r["buy"], width="stretch", hide_index=True)
    with c4:
        st.markdown("**大戶賣組(Δ≤-1pp,散戶接)**")
        st.dataframe(r["sell"], width="stretch", hide_index=True)

st.caption("⚠️ 集保資料滯後(週五快照隔週公布);「籌碼告訴你誰在防守,不告訴你誰會噴」。"
           "與潮汐圖(法人日級)/倒貨率交叉:大戶買+法人買=雙背書;大戶買+法人賣=分點大戶在接法人貨,值得追籌碼分點。")

# -*- coding: utf-8 -*-
"""
pages/39_強勢資金.py — 今日強勢資金(EOD 成交注意力;白底報表)
=================================================================
外部「台股成交注意力」盤中掃描器的 EOD 融合版:占比倍數×RS×量比×收位。
介面特例:用戶指定白底 → 內容是獨立白底 HTML(components 內嵌),可直接分享。
"""
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="強勢資金", page_icon="💪", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("強勢資金", "ATTENTION FLOW", "💪")

ATT = ROOT / "data" / "attention"
files = sorted(ATT.glob("att_*.html"), reverse=True)
if not files:
    st.info("尚無報表——盤後 run_daily 自動產生,或按下方手動跑。")
else:
    pick = st.selectbox("日期", files, format_func=lambda p: p.stem.replace("att_", ""))
    components.html(pick.read_text(encoding="utf-8"), height=1600, scrolling=True)

c1, c2 = st.columns([1, 3])
if c1.button("🔄 立即重掃(約1分鐘)"):
    with st.spinner("全市場掃描中…"):
        import attention_scan
        r = attention_scan.scan()
        if r:
            p = attention_scan.save_html(r)
            st.success(f"完成:{p.name}——重新整理頁面看最新。")
        else:
            st.error("無資料。")
c2.caption("分數=RS/占比倍數/量比/收位 百分位均值;🔪⚠=隔日沖警戒(家規:爆量+2~3天禁入)。"
           "EOD 版,非盤中;黃底列=明天的賣壓名單。")

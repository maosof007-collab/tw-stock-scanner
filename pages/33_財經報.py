"""
pages/33_財經報.py — 財經報專刊閱讀頁(一期一檔 HTML,報紙級排版)
=================================================================
期刊在 data/papers/*.html(newspaper.py 產出);此頁選期→內嵌渲染。
"""
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="財經報", page_icon="🗞️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("財經報專刊", "THE PAPER", "🗞️")

# ── 🏆 研究名單總排名(2026-10-23「我們找那麼多,應該也要有排名」)──
with st.expander("🏆 研究名單總排名(覆蓋標的·每日重算)", expanded=False):
    try:
        import pandas as _rpd
        from pathlib import Path as _RP
        _rk = _rpd.read_csv(_RP(__file__).parent.parent / "data" / "_research_rank.csv",
                            dtype={"代碼": str})
        _cols = ["排名", "代碼", "名稱", "總分", "營收分", "獲利分", "籌碼分", "位置分",
                 "扣分", "營收YoY3", "毛利率", "外資天", "大戶4週Δ", "距年高%", "融資%"]
        st.dataframe(_rk[[c for c in _cols if c in _rk.columns]],
                     hide_index=True, use_container_width=True, height=560)
        st.caption("總分=營收30%+獲利30%+籌碼25%+位置15%-家規扣分(處置10/爆量8/融資≥30% 8/迴轉警5);"
                   "業外佔比重的獲利分腰斬。排名是體檢不是買單——高分看續航,低分看原因。")
        if st.button("🔄 立即重算(約2分鐘)"):
            import research_rank
            with st.spinner("全名單重算中…"):
                research_rank.build()
            st.rerun()
    except Exception as _e:
        st.info(f"排名表尚未生成——run_daily 會自動產生({_e})")

import newspaper as _np
from symbols import resolve as _rs

issues = _np.list_issues()
if not issues:
    st.info("尚無期刊——素材(法人報告/法說/筆記)交給系統即可組版。")
    st.stop()

labels = []
for i in issues:
    nm = _rs(i["code"])[1] or i["code"]
    labels.append(f"{nm} {i['code']}|{i['date'][:4]}/{i['date'][4:6]}/{i['date'][6:]}")
idx = st.selectbox("選期", range(len(issues)), format_func=lambda k: labels[k])
p = Path(issues[idx]["path"])
html = p.read_text(encoding="utf-8")
components.html(html, height=1400, scrolling=True)
st.download_button("⬇️ 下載本期 HTML(可傳 LINE/開瀏覽器)", html.encode("utf-8"),
                   file_name=p.name, mime="text/html")
st.caption("素材=法人報告/法說/使用者筆記;本刊為研究筆記非投資建議。")

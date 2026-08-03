"""
頁面12:研究文章(自產報告的網站式閱讀頁)
================================================
頁13產生的報告會自動發佈到這裡——像逛研究網站一樣:
左側文章清單(標題/個股/日期),右側閱讀版面。
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import page_header, inject_css, MUTED, CYAN

st.set_page_config(page_title="研究文章", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("研究文章", "RESEARCH LIBRARY", "📰")

import importlib
import analyst_report as _ar
if not hasattr(_ar, "list_articles"):
    _ar = importlib.reload(_ar)

arts = _ar.list_articles()
if not arts:
    st.info("還沒有文章——到「🧾 個股法人報告」頁產生報告,會自動發佈到這裡。")
    st.stop()

# 閱讀版面 CSS(文章寬度/字距,像網站)
st.markdown("""<style>
.article-body {max-width: 860px; margin: 0 auto; line-height: 1.9; font-size: 16px;}
.article-body h1 {font-size: 26px; line-height: 1.4; margin-bottom: 4px;}
.article-body h2 {font-size: 20px; margin-top: 28px; border-left: 4px solid #00E5FF;
                  padding-left: 10px;}
.article-body table {font-size: 14px;}
.article-meta {max-width: 860px; margin: 0 auto; color: #8b949e; font-size: 13px;}
</style>""", unsafe_allow_html=True)

left, right = st.columns([1.1, 3])

with left:
    st.markdown("**文章列表**")
    labels = [f"{a['date'][:10]}｜{a['code']} {a['name']}｜{a['mode']}" for a in arts]
    pick = st.radio("選擇文章", labels, key="lib_pick", label_visibility="collapsed")
    idx = labels.index(pick)
    meta = arts[idx]
    st.caption(f"共 {len(arts)} 篇")
    if st.button("🗑 刪除這篇", key="lib_del"):
        try:
            (_ar.ART_DIR / meta["file"]).unlink()
            st.rerun()
        except Exception:
            st.error("刪除失敗")

with right:
    body = _ar.read_article(meta["file"])
    st.markdown(f"<div class='article-meta'>📅 {meta['date']}　·　{meta['code']} "
                f"{meta['name']}　·　{meta['mode']}模式</div>", unsafe_allow_html=True)
    st.markdown("<div class='article-body'>", unsafe_allow_html=True)
    st.markdown(body)
    st.markdown("</div>", unsafe_allow_html=True)
    st.download_button("⬇️ 下載 Markdown", body.encode("utf-8"),
                       file_name=meta["file"], mime="text/markdown", key="lib_dl")

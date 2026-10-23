# -*- coding: utf-8 -*-
"""
pages/40_影片筆記.py — YT 影片→文字檔(含會員影片;寫報告的素材口)
=================================================================
用法:貼網址 → 轉錄 → 文字檔存 data/yt_notes/(gitignore,不進雲端)
→ 到對話跟 Claude 說「用最新的影片筆記寫報告」。
會員影片:需 data/_yt_cookies.txt(瀏覽器擴充 Get cookies.txt LOCALLY 匯出)
或完全關閉 Chrome 後重試(讀登入態)。
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="影片筆記", page_icon="🎬", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("影片筆記", "YT TRANSCRIPT", "🎬")

import yt_notes

ck = yt_notes.COOKIES.exists()
st.caption(("🔐 cookies 檔已就位(會員影片可抓)" if ck else
            "⚠️ 未設 cookies——會員影片需要 data/_yt_cookies.txt"
            "(擴充功能 Get cookies.txt LOCALLY 匯出)或完全關閉 Chrome 後再試"))

url = st.text_input("YouTube 網址", placeholder="https://www.youtube.com/watch?v=…")
if st.button("🎬 轉錄", type="primary") and url.strip():
    with st.spinner("抓取字幕中(約 10~30 秒)…"):
        r = yt_notes.fetch(url.strip())
    if r["ok"]:
        st.success(f"✅ {r['title']}|{r['source']}|{r['chars']:,} 字 → {r['path'].name}")
        st.info("下一步:到對話跟 Claude 說「用最新的影片筆記寫報告」。")
    else:
        st.error(f"失敗:{r['err']}")

notes = yt_notes.list_notes()
if notes:
    st.subheader(f"📚 筆記庫({len(notes)})")
    pick = st.selectbox("選擇", notes, format_func=lambda p: p.stem)
    txt = pick.read_text(encoding="utf-8")
    st.download_button("⬇️ 下載文字檔", txt, file_name=pick.name)
    with st.expander("預覽", expanded=True):
        st.text(txt[:6000] + ("\n…(預覽截斷)" if len(txt) > 6000 else ""))
st.caption("轉錄內容含會員授權素材——已 gitignore,僅存本機,不進雲端;僅供個人研究筆記。")

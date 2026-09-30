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

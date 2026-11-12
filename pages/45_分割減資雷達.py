"""
頁面45:分割/減資雷達 — 公告日合法提前布局,恢復買賣日主戰場。
(2026-11-12 從 22_權證大戶 的 tab 抽成專頁:側欄連結指 tab 會落在預設分頁,看起來像連錯。)
"""
import importlib
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="分割/減資雷達", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("分割/減資雷達", "CORP ACTION RADAR", "📜")

import corp_actions as _ca
if not hasattr(_ca, "render_radar"):
    _ca = importlib.reload(_ca)
_ca.render_radar()

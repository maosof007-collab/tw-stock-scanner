"""ui_common.py — 籌碼頁共用樣式（已統一為全站 HUD 霓虹風）
THEME 值改用 ui_theme 的調色盤；inject_css() 直接套用全站 HUD CSS +
籌碼頁專屬的小元件樣式（.rank-row / .metric-card .v/.l / .pos/.neg）。
籌碼頁的程式碼完全不用改 —— 圖表用 THEME 上色，會自動變色。
"""
import streamlit as st
from ui_theme import (DARK, CARD, BORDER, GRID, TEXT, MUTED,
                      GREEN, RED, GOLD, PURPLE, CYAN, inject_css as _hud_css)

# 對應原 ui_common 的鍵，但全部換成 HUD 配色
THEME = {
    "bg":     DARK,      # 深空底
    "panel":  CARD,      # 面板
    "up":     RED,       # 台股紅漲（HUD 紅 #FF4D6D）
    "down":   GREEN,     # 台股綠跌（HUD 綠 #2BE4A8）
    "ma30":   GOLD,      # 均線 30 = 金
    "ma60":   PURPLE,    # 均線 60 = 紫
    "grid":   GRID,      # 圖表格線
    "text":   TEXT,
    "muted":  MUTED,
    "accent": CYAN,      # 霓虹青強調
}


def inject_css():
    # 先套全站 HUD（背景網格、按鈕、Tabs、KPI 卡、捲軸…）
    _hud_css()
    # 再補籌碼頁專屬小元件，全部 HUD 化
    st.markdown(f"""
<style>
.rank-row {{
  padding:8px 10px; border-radius:6px; margin-bottom:4px;
  background:{CARD}; border:1px solid {BORDER};
  transition:border-color .15s, box-shadow .15s;
}}
.rank-row:hover {{ border-color:{CYAN}; box-shadow:0 0 12px rgba(0,229,255,.18); }}
.pos {{ color:{RED};  font-weight:500; }}
.neg {{ color:{GREEN};font-weight:500; }}
.muted {{ color:{MUTED}; font-size:.8rem; }}
.metric-card .v {{
  font-family:'Share Tech Mono',monospace; font-size:1.35rem;
  font-weight:400; color:{TEXT};
}}
.metric-card .l {{
  font-family:'Share Tech Mono',monospace; font-size:.72rem;
  letter-spacing:.12em; color:{MUTED};
}}
.rating-buy  {{ color:{RED};   font-weight:500; }}
.rating-sell {{ color:{GREEN}; font-weight:500; }}
</style>
""", unsafe_allow_html=True)


def pct_span(v: float) -> str:
    cls = "pos" if v >= 0 else "neg"
    sign = "+" if v >= 0 else ""
    return f'<span class="{cls}">{sign}{v:.2f}%</span>'

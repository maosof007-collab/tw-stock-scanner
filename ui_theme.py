"""
ui_theme.py — 全站統一設計系統(雙主題:白色 HUD / 深空 HUD)
=================================================================
2026-10-19:「介面想改白的」→ 改為雙主題引擎,白色為預設。
- 模式存 data/_ui_mode.txt(light|dark),首頁有切換開關
- 所有頁面照舊 `from ui_theme import *` + inject_css();常數每次頁面重跑時
  重新取值,切換後 st.rerun() 即全站換裝(不用重啟)
- 深色模式下原生元件(表格/對話框)底色跟 config.toml 的 light 基底,
  會偏亮——深色是懷舊選項,主線是白
所有頁面共用:
    from ui_theme import *
    inject_css()
    page_header("今日選股訊號", "TODAY SIGNALS", "📡")
"""
import streamlit as st
from datetime import datetime
from pathlib import Path

from twtime import now_tw

_MODE_F = Path(__file__).parent / "data" / "_ui_mode.txt"

# ════════════════════════════════════════
# 兩套調色盤(鍵名=舊常數名,頁面不用改)
# ════════════════════════════════════════
_LIGHT = dict(
    DARK="#FFFFFF", CARD="#F7F8FA", BORDER="#E2E6EC", GRID="#ECEEF3",
    TEXT="#1A1D24", MUTED="#6B7686",
    CYAN="#0E7490",          # 主題色:深青(白底上可讀,保留 HUD 血統)
    GREEN="#188A50", RED="#D0342C", GOLD="#B45309",
    BLUE="#2563EB", PURPLE="#7C3AED",
    ACC_RGB="14,116,144",    # 主題色 rgb(做 rgba 光暈用)
    GRID_RGB="200,206,216",  # 背景微網格
    SIDE2="#F2F4F7", CARD2="#FFFFFF", DIALOG="#FFFFFF",
    GLOW=0.10,               # 光暈強度(白底調低)
)
_DARK = dict(
    DARK="#04070D", CARD="#0B1322", BORDER="#1C2C4A", GRID="#13203A",
    TEXT="#D9E6F7", MUTED="#647B9C",
    CYAN="#00E5FF", GREEN="#2BE4A8", RED="#FF4D6D", GOLD="#FFC857",
    BLUE="#4FA8FF", PURPLE="#B49BFF",
    ACC_RGB="0,229,255", GRID_RGB="28,44,74",
    SIDE2="#060B16", CARD2="#0A101D", DIALOG="#070D18",
    GLOW=0.25,
)


def get_mode() -> str:
    try:
        m = _MODE_F.read_text().strip()
        return m if m in ("light", "dark") else "light"
    except Exception:
        return "light"


def set_mode(mode: str) -> None:
    _MODE_F.write_text(mode)
    _apply(mode)


def _apply(mode: str) -> None:
    pal = _LIGHT if mode == "light" else _DARK
    g = globals()
    for k, v in pal.items():
        g[k] = v
    g["MODE"] = mode
    g["PAL"] = [g["CYAN"], g["GREEN"], g["GOLD"], g["RED"], g["PURPLE"],
                g["BLUE"], "#5DCAA5" if mode == "dark" else "#0D9488",
                "#F0997B" if mode == "dark" else "#C2554F"]


_apply(get_mode())


# ════════════════════════════════════════
# 全站 CSS(由當前調色盤生成)
# ════════════════════════════════════════
def inject_css():
    try:
        from auto_refresh import ensure_started
        ensure_started()
    except Exception:
        pass
    # Plotly 模板跟著主題走:白色模式時把 "plotly_dark" 整個換成白版
    # (9 個舊頁面寫死 template="plotly_dark",這招讓它們零修改換裝)
    try:
        import copy
        import plotly.io as pio
        if "plotly_dark_orig" not in pio.templates:
            pio.templates["plotly_dark_orig"] = copy.deepcopy(pio.templates["plotly_dark"])
        if MODE == "light":
            pio.templates["plotly_dark"] = copy.deepcopy(pio.templates["plotly_white"])
        else:
            pio.templates["plotly_dark"] = copy.deepcopy(pio.templates["plotly_dark_orig"])
        pio.templates.default = "plotly_white" if MODE == "light" else "plotly_dark"
    except Exception:
        pass
    A, GB, GL = ACC_RGB, GRID_RGB, GLOW

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap');

:root {{
  --hud-cyan: {CYAN};
  --hud-card: {CARD};
  --hud-border: {BORDER};
}}

/* ── 頁面底:微網格 ───────────────── */
body, .stApp {{
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba({A},.05), transparent),
    repeating-linear-gradient(0deg, transparent 0 39px, rgba({GB},.16) 39px 40px),
    repeating-linear-gradient(90deg, transparent 0 39px, rgba({GB},.16) 39px 40px),
    {DARK} !important;
  color: {TEXT};
}}

/* ── 側欄 ───────────────────────────────── */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {SIDE2} 0%, {DARK} 100%) !important;
  border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] * {{ color: {TEXT}; }}
section[data-testid="stSidebar"] a:hover {{ color: {CYAN} !important; }}

h1, h2, h3 {{
  font-family: 'Rajdhani','Microsoft JhengHei',sans-serif !important;
  letter-spacing: .06em;
  color: {TEXT};
}}
.stMarkdown, p, li {{ color: {TEXT}; }}

/* ── HUD 頁首 ───────────────────────────── */
.hud-header {{
  position: relative;
  border: 1px solid {BORDER};
  border-left: 3px solid {CYAN};
  background: linear-gradient(90deg, rgba({A},.07), rgba({A},.012) 55%, transparent);
  border-radius: 4px;
  padding: 14px 20px 12px;
  margin: 2px 0 18px 0;
}}
.hud-header::before {{
  content:""; position:absolute; top:-1px; right:-1px; width:26px; height:26px;
  border-top:2px solid {CYAN}; border-right:2px solid {CYAN}; opacity:.85;
}}
.hud-header::after {{
  content:""; position:absolute; bottom:-1px; right:-1px; width:26px; height:26px;
  border-bottom:2px solid {CYAN}; border-right:2px solid {CYAN}; opacity:.45;
}}
.hud-title {{
  font-family:'Rajdhani','Microsoft JhengHei',sans-serif;
  font-size: 30px; font-weight: 700; letter-spacing:.05em;
  color:{TEXT}; line-height:1.15;
  text-shadow: 0 0 18px rgba({A},{GL});
}}
.hud-sub {{
  font-family:'Share Tech Mono',monospace;
  font-size: 12px; letter-spacing:.22em; color:{CYAN};
  opacity:.85; margin-top:3px; text-transform:uppercase;
}}

/* ── KPI 卡 ────────── */
.metric-card, .pnl-card, .score-card {{
  position: relative;
  background: linear-gradient(160deg, {CARD} 0%, {CARD2} 100%) !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px !important;
  padding: 15px 18px 13px !important;
  text-align: center;
  transition: border-color .2s, box-shadow .2s, transform .15s;
  overflow: hidden;
}}
.metric-card::before, .pnl-card::before, .score-card::before {{
  content:""; position:absolute; top:0; left:0; width:22px; height:22px;
  border-top:2px solid {CYAN}; border-left:2px solid {CYAN}; opacity:.7;
}}
.metric-card:hover, .pnl-card:hover, .score-card:hover {{
  border-color: rgba({A},.55) !important;
  box-shadow: 0 0 22px rgba({A},.12), inset 0 0 22px rgba({A},.03);
  transform: translateY(-1px);
}}
.metric-label, .pnl-label, .score-label {{
  font-family:'Share Tech Mono',monospace;
  color:{MUTED} !important; font-size:11px !important;
  letter-spacing:.18em; text-transform:uppercase; margin-bottom:6px !important;
}}
.metric-value, .pnl-value, .score-value {{
  font-family:'Share Tech Mono',monospace !important;
  font-size:26px !important; font-weight:400 !important;
  color:{TEXT};
  text-shadow: 0 0 14px rgba({A},{GL});
}}
.green {{ color:{GREEN} !important; }} .red  {{ color:{RED}  !important; }}
.gold  {{ color:{GOLD}  !important; }} .blue {{ color:{CYAN} !important; }}

/* ── 按鈕 ────────────────────── */
div[data-testid="stButton"] > button {{
  background: rgba({A},.05) !important;
  color: {CYAN} !important;
  border: 1px solid rgba({A},.4) !important;
  border-radius: 4px !important;
  font-family:'Rajdhani','Microsoft JhengHei',sans-serif !important;
  font-weight: 600 !important; letter-spacing:.05em;
  transition: all .18s ease !important;
}}
div[data-testid="stButton"] > button:hover {{
  background: rgba({A},.14) !important;
  border-color: {CYAN} !important;
  box-shadow: 0 0 16px rgba({A},.3);
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background: linear-gradient(180deg, rgba({A},.16), rgba({A},.06)) !important;
  border: 1px solid {CYAN} !important;
  color: {CYAN} !important;
  box-shadow: 0 0 12px rgba({A},.2), inset 0 0 18px rgba({A},.05);
}}

/* ── Tabs ─────────────────── */
.stTabs [data-baseweb="tab-list"] {{
  gap: 4px; background: transparent;
  border-bottom: 1px solid {BORDER};
}}
.stTabs [data-baseweb="tab"] {{
  font-family:'Rajdhani','Microsoft JhengHei',sans-serif;
  font-size:15px; font-weight:600; letter-spacing:.04em;
  color:{MUTED}; background:transparent;
  padding: 7px 20px; border-radius: 4px 4px 0 0;
}}
.stTabs [aria-selected="true"] {{
  color:{CYAN} !important;
  background: linear-gradient(180deg, rgba({A},.08), transparent) !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color:{CYAN} !important; }}

/* ── 進度條 ─────────────────────── */
.stProgress > div > div > div > div {{
  background: linear-gradient(90deg, {BLUE}, {CYAN}) !important;
  box-shadow: 0 0 14px rgba({A},.45);
}}
.stProgress > div > div {{ background: {BORDER} !important; }}

/* ── 表格 / 輸入 / 其他元件 ──────────────── */
div[data-testid="stDataFrame"] {{
  border: 1px solid {BORDER}; border-radius: 6px;
}}
div[data-testid="stMetricValue"] {{
  font-family:'Share Tech Mono',monospace; font-size:1.45rem; color:{TEXT};
}}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
.stTextInput input, .stNumberInput input, .stDateInput input {{
  background: {CARD} !important; border-color: {BORDER} !important; color:{TEXT} !important;
}}
div[data-testid="stExpander"] {{
  background: {CARD}; border: 1px solid {BORDER} !important; border-radius: 6px;
}}
div[data-testid="stFileUploader"] {{
  background:{CARD}; border:1px dashed rgba({A},.3); border-radius:6px; padding:12px;
}}
div[role="dialog"] {{
  background: {DIALOG} !important; border:1px solid {BORDER} !important;
}}
hr {{ border-color: {BORDER} !important; }}

div[data-testid="stAlert"] {{
  border-radius: 4px; border-left-width: 3px !important;
  font-family:'Microsoft JhengHei',sans-serif;
}}

::-webkit-scrollbar {{ width:9px; height:9px; }}
::-webkit-scrollbar-track {{ background:{DARK}; }}
::-webkit-scrollbar-thumb {{ background:{BORDER}; border-radius:5px; }}
::-webkit-scrollbar-thumb:hover {{ background:rgba({A},.45); }}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# HUD 頁首
# ════════════════════════════════════════
def page_header(title: str, subtitle_en: str = "", icon: str = ""):
    """統一頁首:中文標題+英文機讀風副標+系統時間;管線跑時顯示進度條。"""
    ts = now_tw().strftime("%Y-%m-%d %H:%M")
    sub = f"// {subtitle_en} · SYS {ts}" if subtitle_en else f"// SYS {ts}"
    st.markdown(f"""
<div class="hud-header">
  <div class="hud-title">{icon} {title}</div>
  <div class="hud-sub">{sub}</div>
</div>
""", unsafe_allow_html=True)
    _render_pipeline_progress()


def theme_toggle(key: str = "ui_mode_tg"):
    """主題切換開關(放駕駛艙頂部)。"""
    cur = get_mode()
    dark = st.toggle("🌙 深色模式", value=(cur == "dark"), key=key)
    want = "dark" if dark else "light"
    if want != cur:
        set_mode(want)
        st.rerun()


def _render_pipeline_progress():
    try:
        import time as _t
        from progress import read_progress
        p = read_progress()
        if not p or p.get("done"):
            return
        if _t.time() - float(p.get("ts", 0)) > 180:
            return
        cur = int(p.get("current", 0))
        total = max(int(p.get("total", 1)), 1)
        st.progress(
            min(cur / total, 1.0),
            text=(f"⏳ {p.get('phase','更新中')}　{cur:,} / {total:,}"
                  f"　·　{p.get('msg','')}　·　詳見「⏱️ 更新進度」頁"),
        )
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=3000, key="hud_pipeline_refresh")
        except Exception:
            pass
    except Exception:
        pass

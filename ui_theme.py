"""
ui_theme.py — 全站統一設計系統（科幻 HUD 風）
深空底 × 霓虹青 × 等寬數字 × 角框面板

所有頁面共用：
    from ui_theme import *          # 取得調色盤常數
    inject_css()                    # 注入全站 CSS（set_page_config 之後呼叫）
    page_header("今日選股訊號", "TODAY SIGNALS", "📡")

舊頁面的卡片 class（.metric-card / .pnl-card / .score-card）
會被這裡的 CSS 統一接管樣式，不需要改 HTML。
"""
import streamlit as st
from datetime import datetime

# ════════════════════════════════════════
# 調色盤（沿用各頁原變數名，直接換值即全站換裝）
# ════════════════════════════════════════
DARK   = "#04070D"   # 頁面底：近黑深空藍
CARD   = "#0B1322"   # 面板底
BORDER = "#1C2C4A"   # 面板邊
GRID   = "#13203A"   # 圖表格線
TEXT   = "#D9E6F7"   # 主文字
MUTED  = "#647B9C"   # 次要文字

CYAN   = "#00E5FF"   # 主題霓虹青（強調、邊框、標題）
GREEN  = "#2BE4A8"   # 獲利
RED    = "#FF4D6D"   # 虧損 / 警示
GOLD   = "#FFC857"   # 注意
BLUE   = "#4FA8FF"   # 資訊
PURPLE = "#B49BFF"   # 輔助

PAL = [CYAN, GREEN, GOLD, RED, PURPLE, BLUE, "#5DCAA5", "#F0997B"]


# ════════════════════════════════════════
# 全站 CSS
# ════════════════════════════════════════
def inject_css():
    # 啟動 App 內建自動更新（盤中刷持倉、收盤後全市場更新，每行程一條執行緒）
    try:
        from auto_refresh import ensure_started
        ensure_started()
    except Exception:
        pass

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap');

:root {{
  --hud-cyan: {CYAN};
  --hud-card: {CARD};
  --hud-border: {BORDER};
}}

/* ── 頁面底：深空 + 微網格 ───────────────── */
body, .stApp {{
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0,229,255,.07), transparent),
    repeating-linear-gradient(0deg, transparent 0 39px, rgba(28,44,74,.18) 39px 40px),
    repeating-linear-gradient(90deg, transparent 0 39px, rgba(28,44,74,.18) 39px 40px),
    {DARK} !important;
  color: {TEXT};
}}

/* ── 側欄 ───────────────────────────────── */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #060B16 0%, {DARK} 100%) !important;
  border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] * {{ color: {TEXT}; }}
section[data-testid="stSidebar"] a:hover {{ color: {CYAN} !important; }}

/* ── 標題字體 ───────────────────────────── */
h1, h2, h3 {{
  font-family: 'Rajdhani','Microsoft JhengHei',sans-serif !important;
  letter-spacing: .06em;
}}

/* ── HUD 頁首 ───────────────────────────── */
.hud-header {{
  position: relative;
  border: 1px solid {BORDER};
  border-left: 3px solid {CYAN};
  background: linear-gradient(90deg, rgba(0,229,255,.08), rgba(0,229,255,.012) 55%, transparent);
  border-radius: 4px;
  padding: 14px 20px 12px;
  margin: 2px 0 18px 0;
}}
.hud-header::before {{          /* 右上角框 */
  content:""; position:absolute; top:-1px; right:-1px; width:26px; height:26px;
  border-top:2px solid {CYAN}; border-right:2px solid {CYAN}; opacity:.85;
}}
.hud-header::after {{           /* 右下角框 */
  content:""; position:absolute; bottom:-1px; right:-1px; width:26px; height:26px;
  border-bottom:2px solid {CYAN}; border-right:2px solid {CYAN}; opacity:.45;
}}
.hud-title {{
  font-family:'Rajdhani','Microsoft JhengHei',sans-serif;
  font-size: 30px; font-weight: 700; letter-spacing:.05em;
  color:{TEXT}; line-height:1.15;
  text-shadow: 0 0 18px rgba(0,229,255,.25);
}}
.hud-sub {{
  font-family:'Share Tech Mono',monospace;
  font-size: 12px; letter-spacing:.22em; color:{CYAN};
  opacity:.8; margin-top:3px; text-transform:uppercase;
}}

/* ── KPI 卡（統一接管三種舊 class）────────── */
.metric-card, .pnl-card, .score-card {{
  position: relative;
  background: linear-gradient(160deg, {CARD} 0%, #0A101D 100%) !important;
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
  border-color: rgba(0,229,255,.55) !important;
  box-shadow: 0 0 22px rgba(0,229,255,.13), inset 0 0 22px rgba(0,229,255,.03);
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
  text-shadow: 0 0 14px rgba(0,229,255,.18);
}}
.green {{ color:{GREEN} !important; }} .red  {{ color:{RED}  !important; }}
.gold  {{ color:{GOLD}  !important; }} .blue {{ color:{CYAN} !important; }}

/* ── 按鈕：深底霓虹青 ────────────────────── */
div[data-testid="stButton"] > button {{
  background: rgba(0,229,255,.05) !important;
  color: {CYAN} !important;
  border: 1px solid rgba(0,229,255,.4) !important;
  border-radius: 4px !important;
  font-family:'Rajdhani','Microsoft JhengHei',sans-serif !important;
  font-weight: 600 !important; letter-spacing:.05em;
  transition: all .18s ease !important;
}}
div[data-testid="stButton"] > button:hover {{
  background: rgba(0,229,255,.14) !important;
  border-color: {CYAN} !important;
  box-shadow: 0 0 16px rgba(0,229,255,.35);
  color: #EAFDFF !important;
}}
div[data-testid="stButton"] > button[kind="primary"] {{
  background: linear-gradient(180deg, rgba(0,229,255,.18), rgba(0,229,255,.07)) !important;
  border: 1px solid {CYAN} !important;
  color: {CYAN} !important;
  box-shadow: 0 0 12px rgba(0,229,255,.25), inset 0 0 18px rgba(0,229,255,.06);
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{
  box-shadow: 0 0 24px rgba(0,229,255,.5);
  color:#FFFFFF !important;
}}

/* ── Tabs：HUD 分段控制 ─────────────────── */
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
  background: linear-gradient(180deg, rgba(0,229,255,.10), transparent) !important;
  text-shadow: 0 0 12px rgba(0,229,255,.4);
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color:{CYAN} !important; }}

/* ── 進度條：霓虹青 ─────────────────────── */
.stProgress > div > div > div > div {{
  background: linear-gradient(90deg, #007E8F, {CYAN}) !important;
  box-shadow: 0 0 14px rgba(0,229,255,.55);
}}
.stProgress > div > div {{ background: {BORDER} !important; }}

/* ── 表格 / 輸入 / 其他元件 ──────────────── */
div[data-testid="stDataFrame"] {{
  border: 1px solid {BORDER}; border-radius: 6px;
}}
div[data-testid="stMetricValue"] {{
  font-family:'Share Tech Mono',monospace; font-size:1.45rem;
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
  background:{CARD}; border:1px dashed rgba(0,229,255,.3); border-radius:6px; padding:12px;
}}
div[role="dialog"] {{
  background: #070D18 !important; border:1px solid {BORDER} !important;
}}
hr {{ border-color: {BORDER} !important; }}

/* ── 警示框 ─────────────────────────────── */
div[data-testid="stAlert"] {{
  border-radius: 4px; border-left-width: 3px !important;
  font-family:'Microsoft JhengHei',sans-serif;
}}

/* ── 捲軸 ───────────────────────────────── */
::-webkit-scrollbar {{ width:9px; height:9px; }}
::-webkit-scrollbar-track {{ background:{DARK}; }}
::-webkit-scrollbar-thumb {{
  background:{BORDER}; border-radius:5px;
}}
::-webkit-scrollbar-thumb:hover {{ background:rgba(0,229,255,.45); }}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# HUD 頁首
# ════════════════════════════════════════
def page_header(title: str, subtitle_en: str = "", icon: str = ""):
    """統一頁首：中文標題 + 英文機讀風副標 + 系統時間
    若有資料管線正在跑（更新/掃描），自動在頁首下方顯示即時進度條。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    sub = f"// {subtitle_en} · SYS {ts}" if subtitle_en else f"// SYS {ts}"
    st.markdown(f"""
<div class="hud-header">
  <div class="hud-title">{icon} {title}</div>
  <div class="hud-sub">{sub}</div>
</div>
""", unsafe_allow_html=True)
    _render_pipeline_progress()


def _render_pipeline_progress():
    """全域更新進度：管線運行中時在每一頁顯示，並讓頁面每 3 秒自動刷新跳動"""
    try:
        import time as _t
        from progress import read_progress
        p = read_progress()
        if not p or p.get("done"):
            return
        if _t.time() - float(p.get("ts", 0)) > 180:   # 太久沒心跳視為已結束
            return
        cur   = int(p.get("current", 0))
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

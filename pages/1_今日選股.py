"""
pages/1_今日選股.py  — 今日選股 + 族群熱點
"""
import sys, glob, warnings, subprocess
from pathlib import Path
from datetime import datetime, timedelta, date

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── 統一設計系統（科幻 HUD）───────────────
from ui_theme import (DARK, CARD, BORDER, TEXT, MUTED, GREEN, RED, GOLD,
                      BLUE, PURPLE, CYAN, inject_css, page_header)
from sector_view import load_stock_info, render_sector_section

SCAN_DIR = ROOT / "scan_results"
DATA_DIR = ROOT / "data"

# ─────────────────────────────────────────
st.set_page_config(page_title="今日選股", page_icon="📡", layout="wide")
inject_css()
from gate import require_login, logout_button
_USER = require_login(); logout_button()

# K線清單按鈕需要多行小字（覆寫全站按鈕的字級）
st.markdown("""
<style>
  div[data-testid="stButton"] > button {
    white-space: pre-line !important; line-height: 1.4 !important;
    font-size: 12.5px !important; padding: 6px 4px !important;
  }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────
@st.cache_data(ttl=60)
def load_latest_signals():
    csvs = sorted(SCAN_DIR.glob("signals_*.csv"), reverse=True)
    if not csvs:
        return pd.DataFrame(), ""
    latest = csvs[0]
    date_str = latest.stem.replace("signals_", "")
    return pd.read_csv(latest, encoding="utf-8-sig"), date_str

@st.cache_data(ttl=300)
def load_kline(ticker: str) -> pd.DataFrame:
    p = DATA_DIR / f"{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"]).tail(120)


@st.cache_data(ttl=300)
def load_institutional(ticker: str) -> pd.DataFrame:
    """載入三大法人資料"""
    code = ticker.replace(".TWO", "").replace(".TW", "").strip()
    p = DATA_DIR / "institutional" / f"{code}_inst.csv"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
        # 找外資淨買欄位（可能是中文或 fi_net）
        if "fi_net" not in df.columns:
            num_cols = [c for c in df.columns
                        if c not in ("ticker","name") and
                        pd.api.types.is_numeric_dtype(df[c])]
            if len(num_cols) >= 3:
                df["fi_net"] = df[num_cols[2]]
        return df.tail(60)
    except:
        return pd.DataFrame()


def calc_chips(inst_df: pd.DataFrame, kdf: pd.DataFrame) -> dict:
    """計算法人連買連賣天數 + 均線站上天數"""
    result = {}

    # ── 法人連買/賣天數 ──────────────────
    def consec(series: pd.Series):
        """計算最近連續方向天數（正=買，負=賣）"""
        if series.empty:
            return 0
        vals = series.dropna().values
        if len(vals) == 0:
            return 0
        last_dir = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
        if last_dir == 0:
            return 0
        count = 0
        for v in reversed(vals):
            cur_dir = 1 if v > 0 else (-1 if v < 0 else 0)
            if cur_dir == last_dir:
                count += 1
            else:
                break
        return count * last_dir  # 正=連買N天，負=連賣N天

    if not inst_df.empty:
        # 外資
        if "fi_net" in inst_df.columns:
            result["外資"] = consec(inst_df["fi_net"])
        # 投信
        if "it_net" in inst_df.columns:
            result["投信"] = consec(inst_df["it_net"])
        # 自營商
        for col in ["dealer_self_net", "total_net"]:
            if col in inst_df.columns:
                result["自營"] = consec(inst_df[col])
                break

    # ── 站上均線天數 ──────────────────────
    if not kdf.empty:
        close = kdf["Close"]
        for ma_n, label in [(5,"MA5"),(20,"MA20"),(60,"MA60"),(240,"MA240")]:
            if len(kdf) >= ma_n:
                ma = close.rolling(ma_n).mean()
                # 從最後一天往前算，連續站上幾天
                above = (close > ma).values
                cnt = 0
                for v in reversed(above):
                    if v:
                        cnt += 1
                    else:
                        break
                result[label] = cnt

    # ── 近期漲幅 ──────────────────────────
    if not kdf.empty and len(kdf) >= 2:
        result["今日漲跌"] = round(
            (kdf["Close"].iloc[-1] / kdf["Close"].iloc[-2] - 1) * 100, 2
        )
        result["5日漲跌"] = round(
            (kdf["Close"].iloc[-1] / kdf["Close"].iloc[-6] - 1) * 100, 2
        ) if len(kdf) >= 6 else 0
        result["20日漲跌"] = round(
            (kdf["Close"].iloc[-1] / kdf["Close"].iloc[-21] - 1) * 100, 2
        ) if len(kdf) >= 21 else 0

    return result

# ─────────────────────────────────────────
# K 線彈出視窗（@st.dialog）
# ─────────────────────────────────────────
@st.dialog("📈 K 線圖", width="large")
def kline_dialog(ticker: str, name: str, entry: float, stop: float):
    kdf     = load_kline(ticker)
    inst_df = load_institutional(ticker)
    if kdf.empty:
        st.error(f"找不到 {ticker} 的資料檔")
        return

    last = kdf.iloc[-1]
    prev = kdf.iloc[-2] if len(kdf) >= 2 else last
    chg  = (last["Close"] - prev["Close"]) / prev["Close"] * 100

    # ── 標題列 ───────────────────────────
    col_title, col_chg = st.columns([3, 1])
    with col_title:
        st.markdown(f"### {ticker}　{name}")
    with col_chg:
        color = "🔴" if chg < 0 else "🟢"
        st.markdown(f"<h3 style='text-align:right'>{last['Close']:.1f}　"
                    f"<span style='font-size:16px;color:{'#FF4D6D' if chg<0 else '#2BE4A8'}'>"
                    f"{chg:+.2f}%</span></h3>", unsafe_allow_html=True)

    # ── 基本指標列 ───────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("最高",   f"{last['High']:.1f}")
    c2.metric("最低",   f"{last['Low']:.1f}")
    c3.metric("量(張)", f"{last['Volume']/1000:.0f}")
    c4.metric("進場價", f"{entry:.1f}" if entry else "—")
    if entry and entry > 0:
        roi = (last["Close"] - entry) / entry * 100
        c5.metric("目前損益", f"{roi:+.1f}%",
                  delta_color="normal" if roi >= 0 else "inverse")
    else:
        c5.metric("停損價", f"{stop:.1f}" if stop else "—")

    # ── 籌碼面板 ─────────────────────────
    chips = calc_chips(inst_df, kdf)

    st.markdown("---")
    st.markdown("**三大法人連買連賣**")

    chip_cols = st.columns(6)

    def chip_badge(label, val):
        if val == 0:
            return f"<div style='background:#13203A;border-radius:8px;padding:10px;text-align:center'>" \
                   f"<div style='color:#647B9C;font-size:12px'>{label}</div>" \
                   f"<div style='font-size:22px;font-weight:700;color:#647B9C'>—</div></div>"
        arrow = "▲" if val > 0 else "▼"
        color = "#FF4D6D" if val > 0 else "#2BE4A8"
        days  = abs(val)
        word  = "連買" if val > 0 else "連賣"
        return (f"<div style='background:#0B1322;border:1px solid "
                f"{'#FF4D6D' if val>0 else '#2BE4A8'};border-radius:8px;"
                f"padding:10px;text-align:center'>"
                f"<div style='color:#647B9C;font-size:12px'>{label}</div>"
                f"<div style='font-size:26px;font-weight:700;color:{color}'>"
                f"{arrow}{days}</div>"
                f"<div style='font-size:11px;color:{color}'>{word}{days}天</div></div>")

    for col, (key, label) in zip(chip_cols[:3],
                                  [("外資","外資"),("投信","投信"),("自營","自營商")]):
        val = chips.get(key, 0)
        col.markdown(chip_badge(label, val), unsafe_allow_html=True)

    # ── 站上均線天數 ─────────────────────
    for col, ma in zip(chip_cols[3:], ["MA5","MA20","MA60","MA240"]):
        days = chips.get(ma, 0)
        color = "#2BE4A8" if days > 0 else "#647B9C"
        col.markdown(
            f"<div style='background:#0B1322;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='color:#647B9C;font-size:12px'>站上{ma}</div>"
            f"<div style='font-size:22px;font-weight:700;color:{color}'>{days}天</div></div>",
            unsafe_allow_html=True,
        )

    # ── 近期漲跌幅 ───────────────────────
    st.markdown("---")
    p1, p2, p3, p4, p5 = st.columns(5)
    def pct_metric(col, label, val):
        color = "#FF4D6D" if val > 0 else "#2BE4A8"
        col.markdown(
            f"<div style='background:#0B1322;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='color:#647B9C;font-size:12px'>{label}</div>"
            f"<div style='font-size:20px;font-weight:700;color:{color}'>{val:+.1f}%</div></div>",
            unsafe_allow_html=True,
        )
    pct_metric(p1, "今日漲跌", chips.get("今日漲跌", 0))
    pct_metric(p2, "5日漲跌",  chips.get("5日漲跌",  0))
    pct_metric(p3, "20日漲跌", chips.get("20日漲跌", 0))
    if entry and entry > 0:
        roi = (last["Close"] - entry) / entry * 100
        pct_metric(p4, "進場以來損益", roi)
    sl_pct = abs((last["Close"] - stop) / stop * 100) if stop and stop > 0 else 0
    p5.markdown(
        f"<div style='background:#0B1322;border-radius:8px;padding:10px;text-align:center'>"
        f"<div style='color:#647B9C;font-size:12px'>距停損</div>"
        f"<div style='font-size:20px;font-weight:700;color:#FF4D6D'>{sl_pct:.1f}%</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Candlestick
    fig = go.Figure()
    vol_colors = [GREEN if kdf["Close"].iloc[i] >= kdf["Open"].iloc[i] else RED
                  for i in range(len(kdf))]
    fig.add_trace(go.Bar(
        x=kdf.index, y=kdf["Volume"],
        marker=dict(color=vol_colors, opacity=0.45),
        name="量", yaxis="y2", showlegend=False,
    ))
    fig.add_trace(go.Candlestick(
        x=kdf.index, open=kdf["Open"], high=kdf["High"],
        low=kdf["Low"],  close=kdf["Close"],
        increasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),
        decreasing=dict(line=dict(color=RED,   width=1), fillcolor=RED),
        name="K線", showlegend=False,
    ))
    for ma, col, lbl in [(5,"#4FA8FF","MA5"),(20,"#FFC857","MA20"),
                          (60,"#B49BFF","MA60"),(240,"#F0997B","MA240")]:
        if len(kdf) >= ma:
            fig.add_trace(go.Scatter(
                x=kdf.index, y=kdf["Close"].rolling(ma).mean(),
                line=dict(color=col, width=1.3), name=lbl,
            ))
    if entry and entry > 0:
        fig.add_hline(y=entry, line_dash="dash", line_color=GREEN, line_width=1.5,
                      annotation_text=f"進場 {entry:.1f}",
                      annotation_font=dict(color=GREEN, size=12))
    if stop and stop > 0:
        fig.add_hline(y=stop, line_dash="dash", line_color=RED, line_width=1.5,
                      annotation_text=f"停損 {stop:.1f}",
                      annotation_font=dict(color=RED, size=12))

    fig.update_layout(
        paper_bgcolor=DARK, plot_bgcolor=CARD,
        font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
        title=dict(text=f"<b>{ticker}　{name}</b>　最近120根日線",
                   font=dict(size=16, color=TEXT), x=0.01),
        xaxis=dict(gridcolor=BORDER, rangeslider=dict(visible=False), type="date"),
        yaxis=dict(gridcolor=BORDER, side="right", title="價格"),
        yaxis2=dict(overlaying="y", side="left", showgrid=False,
                    showticklabels=False, range=[0, kdf["Volume"].max()*5]),
        legend=dict(orientation="h", x=0, y=1.06,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=TEXT)),
        height=500, hovermode="x unified",
        margin=dict(l=20, r=60, t=70, b=40),
    )

    # 分頁：原 K線 + 新增 5 軌籌碼圖
    tab_k, tab_chip = st.tabs(["📈 K 線 + 均線", "📊 籌碼 5 軌"])
    with tab_k:
        st.plotly_chart(fig, use_container_width=True)
    with tab_chip:
        try:
            from chip_chart import build_chip_figure
            cfig = build_chip_figure(ticker, height=720)
            if cfig is not None:
                st.plotly_chart(cfig, use_container_width=True)
            else:
                st.caption("無籌碼資料")
        except Exception as e:
            st.caption(f"籌碼圖載入失敗：{e}")


# ─────────────────────────────────────────
# 輔助
# ─────────────────────────────────────────
def run_scan():
    import subprocess
    return subprocess.Popen(
        [sys.executable, str(ROOT / "scan_signals.py")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
    )

def color_rs(val):
    if isinstance(val, (int, float)):
        if val >= 1.2: return f"color:{GREEN};font-weight:600"
        if val >= 1.0: return f"color:{GREEN}"
        return f"color:{GOLD}"
    return ""

def color_risk(val):
    if isinstance(val, (int, float)):
        if val > 10: return f"color:{RED};font-weight:600"
        if val > 5:  return f"color:{GOLD}"
        return f"color:{GREEN}"
    return ""

def render_kline_buttons(source_df, info, key_prefix):
    """每5個一排，點擊彈出 K線 dialog"""
    # 去重：同一 ticker 只顯示一個按鈕（保留第一筆）
    dedup_df = source_df.drop_duplicates(subset=["代碼"]).reset_index(drop=True)
    tickers  = dedup_df["代碼"].tolist()

    for idx, tk in enumerate(tickers):
        row_start = (idx // 5) * 5
        col_pos   = idx % 5
        if col_pos == 0:
            # 開新一排
            chunk_size = min(5, len(tickers) - row_start)
            _cols = st.columns(chunk_size)
            _current_cols = _cols
        col  = _current_cols[col_pos]
        name = info.get(tk, {}).get("name", "")
        label = f"{tk}\n{name}" if name else tk
        # key 用全局唯一 index，完全不會重複
        if col.button(label, key=f"{key_prefix}_{idx}", use_container_width=True):
            row = dedup_df[dedup_df["代碼"] == tk].iloc[0]
            kline_dialog(
                ticker=tk,
                name=name,
                entry=float(row.get("收盤", 0) or 0),
                stop =float(row.get("停損", 0) or 0),
            )


# ═════════════════════════════════════════
# 主畫面
# ═════════════════════════════════════════
page_header("今日選股訊號", "TODAY SIGNALS", "📡")

# ── 自動刷新邏輯 ──────────────────────────
def _is_trading_day() -> bool:
    return datetime.today().weekday() < 5

def _after_close() -> bool:
    now = datetime.now()
    return now.hour > 14 or (now.hour == 14 and now.minute >= 30)

def _data_is_today() -> bool:
    """今日資料是否已是最新"""
    csvs = sorted((ROOT / "scan_results").glob("signals_*.csv"), reverse=True)
    if not csvs: return False
    date_str = csvs[0].stem.replace("signals_","")
    return date_str == date.today().strftime("%Y%m%d")

def _auto_update_triggered() -> bool:
    """是否需要自動更新"""
    try:
        from auto_refresh import _pack_mode
        if _pack_mode():      # 雲端資料包模式：不自動跑 14 分鐘掃描（用包好的選股結果）
            return False
    except Exception:
        pass
    return (_is_trading_day() and _after_close() and not _data_is_today())

# 雲端模式（資料包）判定：雲端一切自動、不顯示手動更新 UI
def _is_cloud():
    try:
        from auto_refresh import _pack_mode
        return _pack_mode()
    except Exception:
        return False
CLOUD = _is_cloud()

# 狀態列
now = datetime.now()
status_col, refresh_col = st.columns([5, 1])
with status_col:
    if CLOUD:
        st.info("☁️ 雲端資料**每天自動更新**，你不用手動做任何事。大跌/量縮日可能顯示今日無新訊號，屬正常。")
    elif _auto_update_triggered():
        st.warning("⏰ 收盤後資料未更新，正在背景更新中...")
        if "auto_update_running" not in st.session_state:
            st.session_state.auto_update_running = True
            subprocess.Popen(
                [sys.executable, str(ROOT / "scan_signals.py")],
                cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    elif _data_is_today():
        st.success(f"✅ 今日資料已是最新　{now.strftime('%H:%M')} 自動刷新中")
    elif not _is_trading_day():
        st.info(f"📅 今日非交易日　顯示最近一次掃描結果")
    else:
        mins_to_close = max(0, (14*60+30) - (now.hour*60+now.minute))
        st.info(f"⏳ 距收盤自動更新約 {mins_to_close} 分鐘")

with refresh_col:
    # 交易時間內每 5 分鐘自動刷新；盤後每 30 分鐘
    if _is_trading_day() and 9 <= now.hour <= 14:
        interval_ms = 5 * 60 * 1000    # 5 分鐘
    else:
        interval_ms = 30 * 60 * 1000   # 30 分鐘
    count = st_autorefresh(interval=interval_ms, key="page_autorefresh")
    if count > 0 and "auto_update_running" in st.session_state:
        del st.session_state["auto_update_running"]

info_df   = load_stock_info()
info_map  = {r["ticker"]: r.to_dict() for _, r in info_df.iterrows()}
name_map  = {r["ticker"]: r["name"]   for _, r in info_df.iterrows()}
sector_map= {r["ticker"]: r.get("sector","") for _, r in info_df.iterrows()}

df_all, scan_date = load_latest_signals()

# ── 工具列 ────────────────────────────────
# 主推策略（回測期望值最高）：今日選股預設只看它，避免 7 策略合併破 50 檔
MAIN_STRATEGY = "量縮整理→出量突破（融資沒走）"

col_info, col_btn, col_grade, col_strat = st.columns([2.4, 1.6, 1.5, 2.5])
with col_info:
    if scan_date:
        fmt = f"{scan_date[:4]}-{scan_date[4:6]}-{scan_date[6:]}"
        st.markdown(f"**掃描日期：** `{fmt}`")
    else:
        st.warning("尚無掃描結果")

with col_btn:
    if CLOUD:
        st.caption("☁️ 每日自動更新")     # 雲端不給手動更新按鈕，避免混淆
    elif st.button("🔄 更新＋選股", type="primary", use_container_width=True,
                   help="股價未更新→自動抓新股價再選股；股價已最新→只快速重選。進度看『⏱️ 更新進度』頁。"):
        try:
            from auto_refresh import _data_behind, trigger_full_update
            stale = _data_behind()
        except Exception:
            stale = True
        if stale:
            trigger_full_update()   # 抓新股價 + 掃描（同「更新進度」那條管線）
            st.toast("股價未更新 → 已啟動『更新股價＋掃描』")
            st.info("🔄 背景更新中：抓新股價→選股。到 **⏱️ 更新進度** 頁看進度，完成後掃描日期會自動變新。")
        else:
            # 股價已最新 → 只重選股（背景 DEVNULL，進度寫 _progress.json 給更新進度頁看）
            subprocess.Popen([sys.executable, str(ROOT / "scan_signals.py")],
                             cwd=str(ROOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.toast("股價已最新 → 重新選股中")
            st.info("📡 股價已是最新，重新選股中（約 5 分）。到 **⏱️ 更新進度** 頁看進度。")
        load_latest_signals.clear()

with col_grade:
    grade_filter = st.multiselect(
        "訊號等級", ["BUY","SETUP","PRE","PRE-DEF"],
        default=["BUY"], label_visibility="collapsed",
    )

if df_all.empty:
    st.info("尚無資料，點擊「重新掃描全市場」"); st.stop()

with col_strat:
    all_strats = sorted(df_all["策略"].dropna().unique().tolist()) if "策略" in df_all.columns else []
    has_main = MAIN_STRATEGY in all_strats
    default_strat = [MAIN_STRATEGY] if has_main else ["（全部策略）"]
    strat_sel = st.multiselect(
        "策略", ["（全部策略）"] + all_strats,
        default=default_strat, label_visibility="collapsed",
        help="預設只看主推策略（回測期望值最高）；選「全部策略」看所有訊號",
    )

# 套用策略篩選（主推預設）
if strat_sel and "（全部策略）" not in strat_sel and "策略" in df_all.columns:
    df_all = df_all[df_all["策略"].isin(strat_sel)]
elif not has_main:
    st.caption(f"💡 主推策略「{MAIN_STRATEGY}」尚未在本次掃描中 → 點「重新掃描」即可只看主推、每天約 10 檔")

df_all["名稱"]    = df_all["代碼"].map(name_map).fillna("")
df_all["產業"]    = df_all["代碼"].map(sector_map).fillna("")
df_all["股號名稱"] = df_all["代碼"] + "  " + df_all["名稱"]

# ── 產業輪動 RRG 動態篩選（每次即時算，隨盤面輪動而變）──
@st.cache_data(ttl=1800, show_spinner=False)
def _rrg_quadrants():
    try:
        from sector_rrg import build_rrg
        pts, _ = build_rrg(weeks=52, max_members=25)
        return dict(zip(pts["產業"], pts["象限"])) if not pts.empty else {}
    except Exception:
        return {}

with st.expander("🎯 產業輪動篩選（RRG · 動態，只選資金流入的產業）", expanded=False):
    use_rrg = st.checkbox("啟用：只留所選象限的產業（首次即時算 RRG 約 15 秒，之後 30 分內秒開）",
                          value=False, key="rrg_filter_on")
    quads_pick = st.multiselect(
        "保留象限", ["領先", "改善", "弱化", "落後"], default=["領先", "改善"],
        help="領先=強且動能續升；改善=弱但動能翻上(potential)。落後/弱化=資金流出",
        key="rrg_quads") if use_rrg else ["領先", "改善"]

if use_rrg and quads_pick:
    _qmap = _rrg_quadrants()
    if _qmap:
        df_all["象限"] = df_all["產業"].map(_qmap).fillna("—")
        _b = len(df_all)
        df_all = df_all[df_all["象限"].isin(quads_pick)]
        st.success(f"🎯 產業輪動：{_b} → {len(df_all)} 檔（只留 {'、'.join(quads_pick)} 象限的產業）")
    else:
        st.caption("RRG 暫無結果（資料不足），未套用輪動篩選")

# 訊號等級基底分類：BUY★ / BUY★★ 都歸入「BUY」桶
# （否則帶星號的進場訊號會被 isin/== 精確比對濾掉，整批看不到）
def _base_grade(g):
    g = str(g)
    return "BUY" if g.startswith("BUY") else g
df_all["訊號基底"] = df_all["訊號等級"].map(_base_grade)

df      = df_all[df_all["訊號基底"].isin(grade_filter)] if grade_filter else df_all
buy_df  = df[df["訊號基底"] == "BUY"]
other_df= df[df["訊號基底"] != "BUY"]

# 同一檔多個策略都中 → 去重，只留訊號最強的那列（★★>★>無，再比 RS）
def _grade_rank(g):
    g = str(g)
    return 0 if "★★" in g else (1 if "★" in g else 2)
if not buy_df.empty:
    buy_df = buy_df.copy()
    buy_df["_gr"] = buy_df["訊號等級"].map(_grade_rank)
    buy_df = (buy_df.sort_values(["_gr", "RS相對強度"], ascending=[True, False])
              .drop_duplicates(subset=["代碼"], keep="first")
              .drop(columns="_gr").reset_index(drop=True))
if not other_df.empty:
    other_df = (other_df.sort_values("RS相對強度", ascending=False)
                .drop_duplicates(subset=["代碼"], keep="first").reset_index(drop=True))

# ── KPI 卡 ────────────────────────────────
st.markdown("---")
k1, k2, k3, k4, k5 = st.columns(5)
avg_rs   = buy_df["RS相對強度"].mean() if not buy_df.empty else 0
avg_risk = buy_df["風險%"].mean()      if not buy_df.empty else 0
for col, label, val, cls in [
    (k1, "BUY 訊號",  str(len(buy_df)),        "green"),
    (k2, "平均 RS",   f"{avg_rs:.2f}",          "green" if avg_rs>=1 else "gold"),
    (k3, "平均風險%", f"{avg_risk:.1f}%",        "green" if avg_risk<=5 else "gold"),
    (k4, "觀察訊號",  str(len(other_df)),        "blue"),
    (k5, "掃描總數",  str(len(df_all)),          ""),
]:
    with col:
        st.markdown(f"""<div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value {cls}">{val}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────
# ① 選股圖表
# ─────────────────────────────────────────
if not buy_df.empty:
    # 計算進場時機標籤（給圖表用）
    def parse_timing(grade):
        if "★★" in str(grade): return "突破當日"
        if "★"  in str(grade): return "早期確認"
        return "已確認"
    buy_df = buy_df.copy()
    buy_df["進場時機"] = buy_df["訊號等級"].apply(parse_timing)
    timing_order = {"突破當日": 0, "早期確認": 1, "已確認": 2}
    buy_df["_t"] = buy_df["進場時機"].map(timing_order)
    buy_df = buy_df.sort_values(["_t","RS相對強度"], ascending=[True, False]).drop("_t", axis=1)

    st.markdown("### 🟢 BUY 訊號圖表")
    ct1, ct2, ct3 = st.tabs(["RS 相對強度", "進場風險%", "泡泡總覽"])

    with ct1:
        sdf = buy_df.sort_values("RS相對強度", ascending=True)
        ylabels = [f"{r['代碼']}  {name_map.get(r['代碼'],'')}" for _, r in sdf.iterrows()]
        # 顏色：突破當日=橘紅，早期確認=金，已確認=綠
        timing_colors = {"突破當日": "#FF6B35", "早期確認": GOLD, "已確認": GREEN}
        bar_colors = [timing_colors.get(r.get("進場時機","已確認"), GREEN)
                      for _, r in sdf.iterrows()]
        fig = go.Figure(go.Bar(
            x=sdf["RS相對強度"], y=ylabels, orientation="h",
            marker=dict(color=bar_colors,
                        opacity=0.88, line=dict(width=0)),
            text=[f"  {v:.2f}" for v in sdf["RS相對強度"]],
            textposition="outside", textfont=dict(size=13, color=TEXT),
            hovertemplate="<b>%{y}</b><br>RS: %{x:.2f}<extra></extra>",
        ))
        fig.add_vline(x=1.0, line_dash="dash", line_color="white", line_width=1.5,
                      opacity=0.5, annotation_text="大盤=1.0",
                      annotation_font=dict(color=MUTED, size=12))
        fig.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=14, color=TEXT),
            xaxis=dict(gridcolor=BORDER, title="RS 值"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=13)),
            height=max(380, len(sdf)*34+80),
            margin=dict(l=10, r=90, t=20, b=40), showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with ct2:
        sdf2 = buy_df.sort_values("風險%", ascending=True)
        ylabels2 = [f"{r['代碼']}  {name_map.get(r['代碼'],'')}" for _, r in sdf2.iterrows()]
        fig2 = go.Figure(go.Bar(
            x=sdf2["風險%"], y=ylabels2, orientation="h",
            marker=dict(color=[BLUE if v<=5 else (GOLD if v<=10 else RED) for v in sdf2["風險%"]],
                        opacity=0.88, line=dict(width=0)),
            text=[f"  {v:.1f}%" for v in sdf2["風險%"]],
            textposition="outside", textfont=dict(size=13, color=TEXT),
            hovertemplate="<b>%{y}</b><br>風險: %{x:.1f}%<extra></extra>",
        ))
        fig2.add_vline(x=5, line_dash="dash", line_color=GOLD, line_width=1.5,
                       opacity=0.7, annotation_text="5% 警戒",
                       annotation_font=dict(color=GOLD, size=12))
        fig2.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=14, color=TEXT),
            xaxis=dict(gridcolor=BORDER, title="風險 %"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=13)),
            height=max(380, len(sdf2)*34+80),
            margin=dict(l=10, r=90, t=20, b=40), showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with ct3:
        bdf = buy_df.copy()
        bdf["量比"]  = bdf["量比(vs均)"].clip(0.1, 10)
        bdf["標籤"]  = bdf["代碼"] + " " + bdf["代碼"].map(name_map).fillna("")
        fig3 = go.Figure(go.Scatter(
            x=bdf["風險%"], y=bdf["RS相對強度"],
            mode="markers+text", text=bdf["標籤"],
            textposition="top center", textfont=dict(size=11, color=TEXT),
            marker=dict(size=bdf["量比"]*12,
                        color=[GREEN if v>=1 else GOLD for v in bdf["RS相對強度"]],
                        opacity=0.85, line=dict(width=1, color=BORDER)),
            hovertemplate="<b>%{text}</b><br>風險: %{x:.1f}%<br>RS: %{y:.2f}<extra></extra>",
        ))
        fig3.add_hline(y=1.0, line_dash="dash", line_color="white", line_width=1, opacity=0.4)
        fig3.add_vline(x=5.0, line_dash="dash", line_color=GOLD,   line_width=1, opacity=0.5)
        fig3.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            xaxis=dict(gridcolor=BORDER, title="風險%（停損距離）"),
            yaxis=dict(gridcolor=BORDER, title="RS 相對強度"),
            height=500, margin=dict(l=60, r=40, t=30, b=60), showlegend=False,
        )
        st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────
# ② 選股明細表 + K線按鈕
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 選股明細　　*點下方按鈕看 K 線*")

tab_buy, tab_watch = st.tabs([
    f"🟢 BUY ({len(buy_df)})",
    f"🟡 觀察 ({len(other_df)})",
])

with tab_buy:
    if buy_df.empty:
        st.info("今日無 BUY 訊號")
    else:
        # 加入進場時機欄位（從 signal_grade 解析）
        def parse_timing(grade):
            if "★★" in str(grade): return "突破當日"
            if "★"  in str(grade): return "早期確認"
            return "已確認"

        def timing_color(val):
            if val == "突破當日": return f"color:#FF6B35;font-weight:700"
            if val == "早期確認": return f"color:{GOLD};font-weight:600"
            return f"color:{MUTED}"

        buy_show = buy_df.copy()
        buy_show["進場時機"] = buy_show["訊號等級"].apply(parse_timing)

        # 排序：突破當日 > 早期確認 > 已確認，同類按 RS 排
        timing_order = {"突破當日": 0, "早期確認": 1, "已確認": 2}
        buy_show["_t"] = buy_show["進場時機"].map(timing_order)
        buy_show = buy_show.sort_values(["_t","RS相對強度"], ascending=[True, False]).drop("_t", axis=1)

        show_cols = ["進場時機","代碼","名稱","產業","收盤","停損","風險%","RS相對強度","量比(vs均)","狀態"]
        avail = [c for c in show_cols if c in buy_show.columns]
        buy_rows = buy_show.reset_index(drop=True)   # 與表格列號對齊，供勾選回查
        disp = buy_rows[avail]

        st.caption("☑️ 勾選左側核取方塊，可一鍵加入績效追蹤")
        event = st.dataframe(
            disp.style
                .map(timing_color, subset=["進場時機"])
                .map(color_rs,     subset=["RS相對強度"])
                .map(color_risk,   subset=["風險%"])
                .format({"收盤":"{:.1f}","停損":"{:.1f}",
                         "風險%":"{:.1f}%","RS相對強度":"{:.2f}","量比(vs均)":"{:.1f}x"}),
            use_container_width=True,
            height=min(600, len(disp)*38+60),
            on_select="rerun",
            selection_mode="multi-row",
            key="buy_table_select",
        )

        # ── 勾選 → 加入績效追蹤 ──────────────
        sel_rows = (event.selection.rows
                    if event is not None and hasattr(event, "selection") else [])
        ac1, ac2 = st.columns([1.6, 4])
        with ac1:
            add_clicked = st.button(
                f"➕ 加入績效追蹤（已選 {len(sel_rows)} 檔）",
                type="primary", use_container_width=True,
                disabled=(len(sel_rows) == 0),
            )
        with ac2:
            st.caption("進場價=收盤、停損=訊號停損、張數預設 1（可到績效頁修改）")

        if add_clicked and sel_rows:
            from portfolio import add_position
            fmt_date = (f"{scan_date[:4]}-{scan_date[4:6]}-{scan_date[6:]}"
                        if scan_date else "")
            added, dup = [], []
            for ridx in sel_rows:
                r = buy_rows.iloc[ridx]
                tk = str(r["代碼"])
                res = add_position(
                    _USER,
                    ticker      = tk,
                    name        = str(r.get("名稱", "")),
                    entry_price = float(r.get("收盤", 0) or 0),
                    stop_loss   = float(r.get("停損", 0) or 0),
                    strategy    = str(r.get("策略", "")),
                    note        = f"今日選股加入（{r.get('進場時機','')}）",
                    entry_date  = fmt_date,
                )
                (added if res == "added" else dup).append(tk)
            if added:
                st.success(f"✅ 已加入績效追蹤：{'、'.join(dict.fromkeys(added))}　"
                           f"→ 到「📈 績效追蹤」頁查看")
            if dup:
                st.info(f"⏭️ 已在持倉中，跳過：{'、'.join(dict.fromkeys(dup))}")

        st.markdown("**點擊看 K 線圖：**")
        render_kline_buttons(buy_show, info_map, "buy")
        csv = buy_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ 下載 BUY 清單 CSV", csv,
                           file_name=f"buy_signals_{scan_date}.csv", mime="text/csv")

with tab_watch:
    if other_df.empty:
        st.info("無觀察訊號")
    else:
        show2 = ["代碼","名稱","產業","訊號等級","策略","收盤","RS相對強度","狀態"]
        disp2 = other_df[show2].reset_index(drop=True)
        st.dataframe(
            disp2.style
                .map(color_rs, subset=["RS相對強度"])
                .format({"收盤":"{:.1f}","RS相對強度":"{:.2f}"}),
            use_container_width=True,
            height=min(560, len(disp2)*38+60),
        )
        st.markdown("**點擊看 K 線圖：**")
        render_kline_buttons(other_df, info_map, "watch")

# ─────────────────────────────────────────
# ③ 每日族群熱點分布（共用元件 sector_view）
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("### 🌡️ 今日族群熱點分布")
render_sector_section(key_prefix="scan_sec")


# ─────────────────────────────────────────
# ④ 分布圓餅（選填）
# ─────────────────────────────────────────
if not buy_df.empty:
    st.markdown("---")
    st.markdown("### 📊 訊號分布")
    c1, c2 = st.columns(2)
    for col, vals, title, pal in [
        (c1, buy_df["策略"].value_counts().reset_index().rename(columns={"策略":"label","count":"val"}),
         "策略分布", [GREEN,BLUE,GOLD,RED,PURPLE]),
        (c2, buy_df["代碼"].apply(
            lambda x: "上市(.TW)" if str(x).endswith(".TW") else "上櫃(.TWO)"
        ).value_counts().reset_index().rename(columns={"代碼":"label","count":"val"}),
         "上市 vs 上櫃", [BLUE,GOLD]),
    ]:
        fig_p = px.pie(vals, names="label", values="val",
                       color_discrete_sequence=pal, hole=0.45)
        fig_p.update_traces(textfont=dict(size=14, color="white"),
                            hovertemplate="<b>%{label}</b><br>%{value} 筆<extra></extra>")
        fig_p.update_layout(
            paper_bgcolor=DARK,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            title=dict(text=title, font=dict(size=15, color=TEXT), x=0.5),
            legend=dict(font=dict(size=12, color=TEXT), bgcolor=CARD),
            margin=dict(t=50,b=20,l=10,r=10), height=300,
        )
        col.plotly_chart(fig_p, use_container_width=True)

st.markdown(f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
            f"掃描結果：{SCAN_DIR}</p>", unsafe_allow_html=True)

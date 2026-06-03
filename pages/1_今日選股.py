"""
pages/1_今日選股.py  — 今日選股 + 族群熱點
"""
import sys, glob, warnings
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── 色彩主題 ─────────────────────────────
DARK   = "#0d1117"
CARD   = "#161b22"
BORDER = "#30363d"
TEXT   = "#e6edf3"
MUTED  = "#8b949e"
GREEN  = "#1D9E75"
RED    = "#F85149"
GOLD   = "#D29922"
BLUE   = "#58A6FF"
PURPLE = "#BC8CFF"

SCAN_DIR = ROOT / "scan_results"
DATA_DIR = ROOT / "data"

# ─────────────────────────────────────────
st.set_page_config(page_title="今日選股", page_icon="📡", layout="wide")

st.markdown(f"""
<style>
  body, .stApp {{ background-color:{DARK}; color:{TEXT}; }}
  .metric-card {{
    background:{CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:16px 20px; text-align:center;
  }}
  .metric-label {{ color:{MUTED}; font-size:13px; margin-bottom:4px; }}
  .metric-value {{ font-size:28px; font-weight:700; }}
  .green {{ color:{GREEN}; }} .red {{ color:{RED}; }}
  .gold  {{ color:{GOLD};  }} .blue {{ color:{BLUE}; }}

  /* K線按鈕樣式 */
  div[data-testid="stButton"] > button {{
    background-color:{CARD} !important; color:{BLUE} !important;
    border:1px solid {BORDER} !important; border-radius:8px !important;
    font-size:12px !important; font-weight:500 !important;
    padding:6px 4px !important; white-space:pre-line !important;
    line-height:1.4 !important; transition:all 0.15s ease !important;
  }}
  div[data-testid="stButton"] > button:hover {{
    background-color:#1f2937 !important; border-color:{BLUE} !important;
    color:#ffffff !important;
  }}
  div[data-testid="stButton"] > button[kind="primary"] {{
    background-color:{GREEN} !important; color:#ffffff !important;
    border-color:{GREEN} !important; font-size:14px !important; font-weight:600 !important;
  }}
  div[data-testid="stButton"] > button[kind="primary"]:hover {{
    background-color:#159060 !important;
  }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_stock_info() -> pd.DataFrame:
    """載入股票清單（含中文名 + 產業別）"""
    p = DATA_DIR / "stock_list.csv"
    if not p.exists():
        return pd.DataFrame(columns=["ticker","code","name","market","sector"])
    return pd.read_csv(p, encoding="utf-8-sig", dtype=str)

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
    code = ticker.replace(".TW", "").replace(".TWO", "").strip()
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

@st.cache_data(ttl=600)
def compute_sector_heatmap(info_df: pd.DataFrame) -> pd.DataFrame:
    """
    計算每個產業今日漲跌平均
    回傳 DataFrame: sector, avg_chg, up, down, total, top_gainers
    """
    rows = []
    csvs = (
        sorted(glob.glob(str(DATA_DIR / "*.TW.csv"))) +
        sorted(glob.glob(str(DATA_DIR / "*.TWO.csv")))
    )
    # 建立 ticker→sector map
    sec_map = dict(zip(info_df["ticker"], info_df["sector"]))
    name_map = dict(zip(info_df["ticker"], info_df["name"]))

    for fpath in csvs:
        ticker = Path(fpath).stem
        sector = sec_map.get(ticker, "")
        if not sector or sector == "nan":
            continue
        try:
            df = pd.read_csv(fpath, index_col=0, parse_dates=True,
                             usecols=[0, 4], nrows=None)  # Date, Close
            df.columns = ["Close"]
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            df = df.dropna()
            if len(df) < 2:
                continue
            chg = (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100
            rows.append({
                "ticker": ticker,
                "name":   name_map.get(ticker, ""),
                "sector": sector,
                "chg":    round(chg, 2),
                "close":  round(df["Close"].iloc[-1], 1),
            })
        except:
            pass

    if not rows:
        return pd.DataFrame()

    stock_df = pd.DataFrame(rows)
    agg = stock_df.groupby("sector").agg(
        avg_chg=("chg", "mean"),
        up     =("chg", lambda x: (x > 0).sum()),
        down   =("chg", lambda x: (x < 0).sum()),
        flat   =("chg", lambda x: (x == 0).sum()),
        total  =("chg", "count"),
    ).reset_index()
    agg["avg_chg"] = agg["avg_chg"].round(2)

    # 每個產業前3名漲幅股
    def top_g(grp):
        top = grp.nlargest(3, "chg")
        return ", ".join(f"{r['name']}({r['chg']:+.1f}%)" for _, r in top.iterrows())
    top_map = stock_df.groupby("sector").apply(top_g)
    agg["top_gainers"] = agg["sector"].map(top_map)

    return agg.sort_values("avg_chg", ascending=False)


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
                    f"<span style='font-size:16px;color:{'#F85149' if chg<0 else '#1D9E75'}'>"
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
            return f"<div style='background:#1e2d3d;border-radius:8px;padding:10px;text-align:center'>" \
                   f"<div style='color:#8b949e;font-size:12px'>{label}</div>" \
                   f"<div style='font-size:22px;font-weight:700;color:#8b949e'>—</div></div>"
        arrow = "▲" if val > 0 else "▼"
        color = "#F85149" if val > 0 else "#1D9E75"
        days  = abs(val)
        word  = "連買" if val > 0 else "連賣"
        return (f"<div style='background:#161b22;border:1px solid "
                f"{'#F85149' if val>0 else '#1D9E75'};border-radius:8px;"
                f"padding:10px;text-align:center'>"
                f"<div style='color:#8b949e;font-size:12px'>{label}</div>"
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
        color = "#1D9E75" if days > 0 else "#8b949e"
        col.markdown(
            f"<div style='background:#161b22;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='color:#8b949e;font-size:12px'>站上{ma}</div>"
            f"<div style='font-size:22px;font-weight:700;color:{color}'>{days}天</div></div>",
            unsafe_allow_html=True,
        )

    # ── 近期漲跌幅 ───────────────────────
    st.markdown("---")
    p1, p2, p3, p4, p5 = st.columns(5)
    def pct_metric(col, label, val):
        color = "#F85149" if val > 0 else "#1D9E75"
        col.markdown(
            f"<div style='background:#161b22;border-radius:8px;padding:10px;text-align:center'>"
            f"<div style='color:#8b949e;font-size:12px'>{label}</div>"
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
        f"<div style='background:#161b22;border-radius:8px;padding:10px;text-align:center'>"
        f"<div style='color:#8b949e;font-size:12px'>距停損</div>"
        f"<div style='font-size:20px;font-weight:700;color:#F85149'>{sl_pct:.1f}%</div></div>",
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
    for ma, col, lbl in [(5,"#58A6FF","MA5"),(20,"#D29922","MA20"),
                          (60,"#BC8CFF","MA60"),(240,"#F0997B","MA240")]:
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
    st.plotly_chart(fig, use_container_width=True)


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
    tickers = source_df["代碼"].tolist()
    for row_start in range(0, len(tickers), 5):
        chunk = tickers[row_start: row_start + 5]
        cols  = st.columns(len(chunk))
        for col, tk in zip(cols, chunk):
            name = info.get(tk, {}).get("name", "")
            label = f"{tk}\n{name}" if name else tk
            if col.button(label, key=f"{key_prefix}_{tk}", use_container_width=True):
                row = source_df[source_df["代碼"] == tk].iloc[0]
                kline_dialog(
                    ticker=tk,
                    name=name,
                    entry=float(row.get("收盤", 0) or 0),
                    stop =float(row.get("停損", 0) or 0),
                )


# ═════════════════════════════════════════
# 主畫面
# ═════════════════════════════════════════
st.title("📡 今日選股訊號")

info_df   = load_stock_info()
info_map  = {r["ticker"]: r.to_dict() for _, r in info_df.iterrows()}
name_map  = {r["ticker"]: r["name"]   for _, r in info_df.iterrows()}
sector_map= {r["ticker"]: r.get("sector","") for _, r in info_df.iterrows()}

df_all, scan_date = load_latest_signals()

# ── 工具列 ────────────────────────────────
col_info, col_btn, col_filter = st.columns([3, 1.8, 3])
with col_info:
    if scan_date:
        fmt = f"{scan_date[:4]}-{scan_date[4:6]}-{scan_date[6:]}"
        st.markdown(f"**掃描日期：** `{fmt}`　　共 **{len(df_all)}** 筆訊號")
    else:
        st.warning("尚無掃描結果")

with col_btn:
    if st.button("🔄 重新掃描全市場", type="primary", use_container_width=True):
        with st.spinner("掃描中，約需 5 分鐘..."):
            proc = run_scan()
            bar  = st.progress(0, text="掃描中...")
            for line in proc.stdout:
                try:
                    part = line.split("]")[0].split("[")[-1]
                    cur, tot = map(int, part.split("/"))
                    bar.progress(cur / tot, text=f"[{cur}/{tot}] 掃描中...")
                except: pass
            proc.wait(); bar.empty()
        load_latest_signals.clear(); st.rerun()

with col_filter:
    grade_filter = st.multiselect(
        "訊號等級", ["BUY","SETUP","PRE","PRE-DEF"],
        default=["BUY"], label_visibility="collapsed",
    )

if df_all.empty:
    st.info("尚無資料，點擊「重新掃描全市場」"); st.stop()

df_all["名稱"]    = df_all["代碼"].map(name_map).fillna("")
df_all["產業"]    = df_all["代碼"].map(sector_map).fillna("")
df_all["股號名稱"] = df_all["代碼"] + "  " + df_all["名稱"]

df      = df_all[df_all["訊號等級"].isin(grade_filter)] if grade_filter else df_all
buy_df  = df[df["訊號等級"] == "BUY"]
other_df= df[df["訊號等級"] != "BUY"]

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
        disp = buy_show[avail].reset_index(drop=True)

        st.dataframe(
            disp.style
                .applymap(timing_color, subset=["進場時機"])
                .applymap(color_rs,     subset=["RS相對強度"])
                .applymap(color_risk,   subset=["風險%"])
                .format({"收盤":"{:.1f}","停損":"{:.1f}",
                         "風險%":"{:.1f}%","RS相對強度":"{:.2f}","量比(vs均)":"{:.1f}x"}),
            use_container_width=True,
            height=min(600, len(disp)*38+60),
        )
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
                .applymap(color_rs, subset=["RS相對強度"])
                .format({"收盤":"{:.1f}","RS相對強度":"{:.2f}"}),
            use_container_width=True,
            height=min(560, len(disp2)*38+60),
        )
        st.markdown("**點擊看 K 線圖：**")
        render_kline_buttons(other_df, info_map, "watch")

# ─────────────────────────────────────────
# ③ 每日族群熱點分布
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("### 🌡️ 今日族群熱點分布")
st.caption("依產業別計算全市場平均漲跌幅，紅=強勢族群，綠=弱勢族群")

with st.spinner("計算族群熱點中..."):
    sector_df = compute_sector_heatmap(info_df)

if sector_df.empty:
    st.warning("無法計算族群資料")
else:
    ht1, ht2 = st.tabs(["📊 熱點地圖", "📋 族群明細"])

    with ht1:
        # Treemap（面積=股票數量，顏色=漲跌幅）
        fig_tm = go.Figure(go.Treemap(
            labels=sector_df["sector"],
            parents=["全市場"] * len(sector_df),
            values=sector_df["total"],
            customdata=np.stack([
                sector_df["avg_chg"],
                sector_df["up"],
                sector_df["down"],
                sector_df["top_gainers"],
            ], axis=-1),
            texttemplate=(
                "<b>%{label}</b><br>"
                "%{customdata[0]:+.2f}%<br>"
                "<span style='font-size:11px'>▲%{customdata[1]} ▼%{customdata[2]}</span>"
            ),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "平均漲跌：%{customdata[0]:+.2f}%<br>"
                "上漲：%{customdata[1]} 檔　下跌：%{customdata[2]} 檔<br>"
                "強勢股：%{customdata[3]}<extra></extra>"
            ),
            marker=dict(
                colors=sector_df["avg_chg"],
                colorscale=[
                    [0.0,  "#8B0000"],
                    [0.3,  RED],
                    [0.48, "#4a1515"],
                    [0.5,  CARD],
                    [0.52, "#0d3320"],
                    [0.7,  GREEN],
                    [1.0,  "#005030"],
                ],
                cmid=0,
                showscale=True,
                colorbar=dict(
                    title=dict(text="漲跌%", font=dict(color=TEXT, size=13)),
                    tickfont=dict(color=TEXT, size=12),
                    bgcolor=CARD, bordercolor=BORDER,
                    x=1.01,
                ),
            ),
            textfont=dict(family="Microsoft JhengHei, Arial", size=14, color="white"),
        ))
        fig_tm.update_layout(
            paper_bgcolor=DARK,
            font=dict(family="Microsoft JhengHei, Arial", size=14, color=TEXT),
            margin=dict(t=20, l=10, r=10, b=10),
            height=560,
        )
        st.plotly_chart(fig_tm, use_container_width=True)

        # 補充：橫條圖（更清楚看漲跌幅）
        sdf_sorted = sector_df.sort_values("avg_chg", ascending=True)
        bar_colors = [RED if v >= 0 else GREEN for v in sdf_sorted["avg_chg"]]
        fig_bar = go.Figure(go.Bar(
            x=sdf_sorted["avg_chg"],
            y=sdf_sorted["sector"],
            orientation="h",
            marker=dict(color=bar_colors, opacity=0.85, line=dict(width=0)),
            text=[f"  {v:+.2f}%" for v in sdf_sorted["avg_chg"]],
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            hovertemplate=(
                "<b>%{y}</b><br>平均漲跌：%{x:+.2f}%<br>"
                "上漲/下跌：%{customdata[0]}/%{customdata[1]}<extra></extra>"
            ),
            customdata=sdf_sorted[["up","down"]].values,
        ))
        fig_bar.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
        fig_bar.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            xaxis=dict(gridcolor=BORDER, title="平均漲跌幅 (%)"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=13)),
            height=max(500, len(sdf_sorted)*28+60),
            margin=dict(l=10, r=80, t=20, b=40), showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with ht2:
        disp_sec = sector_df[["sector","avg_chg","up","down","total","top_gainers"]].copy()
        disp_sec.columns = ["產業","平均漲跌%","上漲","下跌","合計","強勢股Top3"]
        disp_sec = disp_sec.reset_index(drop=True)

        def color_chg(val):
            if isinstance(val, float):
                if val > 1:  return f"color:{RED};font-weight:600"
                if val > 0:  return f"color:{RED}"
                if val < -1: return f"color:{GREEN};font-weight:600"
                if val < 0:  return f"color:{GREEN}"
            return ""

        st.dataframe(
            disp_sec.style
                .applymap(color_chg, subset=["平均漲跌%"])
                .format({"平均漲跌%":"{:+.2f}%","上漲":"{:.0f}","下跌":"{:.0f}","合計":"{:.0f}"}),
            use_container_width=True,
            height=min(700, len(disp_sec)*38+60),
        )

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

"""
sector_view.py — 今日族群熱點（共用元件）
首頁（app.py）與今日選股頁共用：
    from sector_view import load_stock_info, render_sector_section
    render_sector_section()        # 完整區塊：熱力色塊 + 族群明細 + 個股下鑽
"""
import glob
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from ui_theme import DARK, CARD, BORDER, TEXT, MUTED, GREEN, RED

ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "data"


# ════════════════════════════════════════
# 資料
# ════════════════════════════════════════
@st.cache_data(ttl=3600)
def load_stock_info() -> pd.DataFrame:
    """股票清單（含中文名 + 產業別）"""
    p = DATA_DIR / "stock_list.csv"
    if not p.exists():
        return pd.DataFrame(columns=["ticker", "code", "name", "market", "sector"])
    return pd.read_csv(p, encoding="utf-8-sig", dtype=str)


@st.cache_data(ttl=600)
def compute_stock_returns(info_df: pd.DataFrame) -> pd.DataFrame:
    """全市場個股今日漲跌幅：ticker, name, sector, chg, close, volume"""
    rows = []
    csvs = (sorted(glob.glob(str(DATA_DIR / "*.TW.csv"))) +
            sorted(glob.glob(str(DATA_DIR / "*.TWO.csv"))))
    sec_map  = dict(zip(info_df["ticker"], info_df["sector"]))
    name_map = dict(zip(info_df["ticker"], info_df["name"]))

    for fpath in csvs:
        ticker = Path(fpath).stem
        sector = sec_map.get(ticker, "")
        if not sector or sector == "nan":
            continue
        try:
            df = pd.read_csv(fpath, index_col=0, parse_dates=True, usecols=[0, 4, 5])
            df.columns = ["Close", "Volume"]
            df["Close"]  = pd.to_numeric(df["Close"],  errors="coerce")
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                continue
            rows.append({
                "ticker": ticker,
                "name":   name_map.get(ticker, ""),
                "sector": sector,
                "chg":    round((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100, 2),
                "close":  round(df["Close"].iloc[-1], 1),
                "volume": int(df["Volume"].iloc[-1] / 1000) if df["Volume"].iloc[-1] else 0,
            })
        except Exception:
            pass

    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def compute_sector_heatmap(info_df: pd.DataFrame) -> pd.DataFrame:
    """每個產業今日平均漲跌：sector, avg_chg, up, down, total, top_gainers"""
    stock_df = compute_stock_returns(info_df)
    if stock_df.empty:
        return pd.DataFrame()

    agg = stock_df.groupby("sector").agg(
        avg_chg=("chg", "mean"),
        up     =("chg", lambda x: (x > 0).sum()),
        down   =("chg", lambda x: (x < 0).sum()),
        flat   =("chg", lambda x: (x == 0).sum()),
        total  =("chg", "count"),
    ).reset_index()
    agg["avg_chg"] = agg["avg_chg"].round(2)

    def top_g(grp):
        top = grp.nlargest(3, "chg")
        return ", ".join(f"{r['name']}({r['chg']:+.1f}%)" for _, r in top.iterrows())
    top_map = stock_df.groupby("sector").apply(top_g)
    agg["top_gainers"] = agg["sector"].map(top_map)

    return agg.sort_values("avg_chg", ascending=False)


# ════════════════════════════════════════
# 視覺
# ════════════════════════════════════════
def _chg_to_color(chg: float) -> str:
    """台股慣例：紅漲綠跌，依幅度加深"""
    if   chg >= 3:  return "#8F1D2C"
    elif chg >= 2:  return "#C2334A"
    elif chg >= 1:  return "#A93A4C"
    elif chg >= 0:  return "#6B3640"
    elif chg >= -1: return "#1F5648"
    elif chg >= -2: return "#1E7A5F"
    else:           return "#0F8A66"


@st.dialog("📊 族群個股排行", width="large")
def _sector_drill_dialog(sector_name: str, stock_ret_df: pd.DataFrame):
    grp = stock_ret_df[stock_ret_df["sector"] == sector_name].copy()
    grp = grp.sort_values("chg", ascending=False).reset_index(drop=True)
    if grp.empty:
        st.info(f"「{sector_name}」無個股資料")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("族群均漲跌", f"{grp['chg'].mean():+.2f}%")
    k2.metric("上漲", f"{(grp['chg']>0).sum()} 檔")
    k3.metric("下跌", f"{(grp['chg']<0).sum()} 檔")
    k4.metric("合計", f"{len(grp)} 檔")

    plot_grp = grp.head(30)
    bar_c = [RED if v >= 0 else GREEN for v in plot_grp["chg"]]
    fig = go.Figure(go.Bar(
        x=plot_grp["chg"],
        y=plot_grp["ticker"] + "  " + plot_grp["name"],
        orientation="h",
        marker=dict(color=bar_c, opacity=0.9, line=dict(width=0)),
        text=[f"  {v:+.2f}%" for v in plot_grp["chg"]],
        textposition="outside", textfont=dict(size=12, color=TEXT),
        hovertemplate=("<b>%{y}</b><br>漲跌：%{x:+.2f}%<br>"
                       "收盤：%{customdata[0]}<br>量(張)：%{customdata[1]:,}<extra></extra>"),
        customdata=plot_grp[["close", "volume"]].values,
    ))
    fig.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
    fig.update_layout(
        paper_bgcolor=DARK, plot_bgcolor=CARD,
        font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
        title=dict(text=f"{sector_name}　前30名個股漲跌",
                   font=dict(size=15, color=TEXT), x=0.01),
        xaxis=dict(gridcolor=BORDER, title="漲跌幅 (%)"),
        # autorange reversed：讓排序第一名（漲最多）顯示在最上面
        yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12), autorange="reversed"),
        height=max(400, len(plot_grp) * 28 + 80),
        margin=dict(l=10, r=90, t=50, b=30), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**個股明細**")
    tbl = grp[["ticker", "name", "chg", "close", "volume"]].copy()
    tbl.columns = ["代碼", "名稱", "漲跌%", "收盤", "量(張)"]

    def _c(v):
        if isinstance(v, float):
            return (f"color:{'#FF4D6D' if v > 0 else '#2BE4A8'};"
                    f"font-weight:{'700' if abs(v) > 3 else '400'}")
        return ""

    st.dataframe(
        tbl.style.applymap(_c, subset=["漲跌%"])
           .format({"漲跌%": "{:+.2f}%", "收盤": "{:.1f}", "量(張)": "{:,}"}),
        use_container_width=True,
        height=min(500, len(tbl) * 36 + 60),
    )


def render_sector_section(key_prefix: str = "sec", n_cols: int = 5):
    """完整族群熱點區塊：熱力色塊網格 + 族群明細表 + 點擊下鑽個股"""
    info_df = load_stock_info()
    if info_df.empty:
        st.warning("找不到 data/stock_list.csv，無法計算族群資料")
        return

    with st.spinner("計算族群熱點中..."):
        sector_df = compute_sector_heatmap(info_df)
    if sector_df.empty:
        st.warning("無法計算族群資料")
        return

    stock_ret_df = compute_stock_returns(info_df)

    ht1, ht2 = st.tabs(["🌡️ 熱力地圖", "📋 族群明細"])

    with ht1:
        st.caption("紅＝強勢族群　綠＝弱勢族群　·　點色塊看族群個股排行")

        sdf_grid = sector_df.sort_values("avg_chg", ascending=False).reset_index(drop=True)
        rows = [sdf_grid.iloc[i:i + n_cols] for i in range(0, len(sdf_grid), n_cols)]

        for r_i, row_df in enumerate(rows):
            cols = st.columns(n_cols)
            for i, (_, sec) in enumerate(row_df.iterrows()):
                chg = sec["avg_chg"]
                bg  = _chg_to_color(chg)
                with cols[i]:
                    # 色塊本體（純視覺）＋下方窄按鈕（觸發下鑽）
                    st.markdown(
                        f"<div style='background:{bg};border-radius:6px 6px 0 0;"
                        f"padding:10px 6px 8px;text-align:center;min-height:74px;"
                        f"display:flex;flex-direction:column;justify-content:center;"
                        f"border:1px solid rgba(255,255,255,.06);border-bottom:none'>"
                        f"<div style='font-size:14px;font-weight:700;color:#fff'>{sec['sector']}</div>"
                        f"<div style='font-family:Share Tech Mono,monospace;font-size:16px;"
                        f"color:#fff'>{chg:+.2f}%</div>"
                        f"<div style='font-size:11px;color:rgba(255,255,255,.75)'>"
                        f"▲{int(sec['up'])}　▼{int(sec['down'])}</div></div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("查看個股", key=f"{key_prefix}_{sec['sector']}",
                                 use_container_width=True):
                        if not stock_ret_df.empty:
                            _sector_drill_dialog(sec["sector"], stock_ret_df)

    with ht2:
        disp = sector_df[["sector", "avg_chg", "up", "down", "total", "top_gainers"]].copy()
        disp.columns = ["產業", "平均漲跌%", "上漲", "下跌", "合計", "強勢股Top3"]
        disp = disp.reset_index(drop=True)

        def color_chg(val):
            if isinstance(val, float):
                if val > 1:  return f"color:{RED};font-weight:600"
                if val > 0:  return f"color:{RED}"
                if val < -1: return f"color:{GREEN};font-weight:600"
                if val < 0:  return f"color:{GREEN}"
            return ""

        st.dataframe(
            disp.style.applymap(color_chg, subset=["平均漲跌%"])
                .format({"平均漲跌%": "{:+.2f}%", "上漲": "{:.0f}",
                         "下跌": "{:.0f}", "合計": "{:.0f}"}),
            use_container_width=True,
            height=min(700, len(disp) * 38 + 60),
        )

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
            _v = df["Volume"].iloc[-1]
            rows.append({
                "ticker": ticker,
                "name":   name_map.get(ticker, ""),
                "sector": sector,
                "chg":    round((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100, 2),
                "close":  round(df["Close"].iloc[-1], 1),
                "volume": int(_v / 1000) if _v else 0,
                "value":  round(float(df["Close"].iloc[-1]) * float(_v or 0) / 1e8, 2),  # 成交額(億)
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
    st.plotly_chart(fig, width="stretch")

    st.markdown("**個股明細**")
    tbl = grp[["ticker", "name", "chg", "close", "volume"]].copy()
    tbl.columns = ["代碼", "名稱", "漲跌%", "收盤", "量(張)"]

    def _c(v):
        if isinstance(v, float):
            return (f"color:{'#FF4D6D' if v > 0 else '#2BE4A8'};"
                    f"font-weight:{'700' if abs(v) > 3 else '400'}")
        return ""

    st.dataframe(
        tbl.style.map(_c, subset=["漲跌%"])
           .format({"漲跌%": "{:+.2f}%", "收盤": "{:.1f}", "量(張)": "{:,}"}),
        width="stretch",
        height=min(500, len(tbl) * 36 + 60),
    )


def battle_table(stock_df: pd.DataFrame) -> pd.DataFrame:
    """產業多空戰況(日級,仿盤中多空雷達):
    紅額=上漲股成交額、綠額=下跌股、淨額=紅-綠、戰況分數=(紅-綠)/(紅+綠)×100。"""
    if stock_df.empty or "value" not in stock_df.columns:
        return pd.DataFrame()
    rows = []
    for sec, g in stock_df.groupby("sector"):
        red = float(g.loc[g["chg"] > 0, "value"].sum())
        grn = float(g.loc[g["chg"] < 0, "value"].sum())
        tot = float(g["value"].sum())
        if tot <= 0:
            continue
        rows.append({
            "產業": sec, "家數": len(g),
            "上漲": int((g["chg"] > 0).sum()), "下跌": int((g["chg"] < 0).sum()),
            "總額(億)": round(tot, 1),
            "紅額(億)": round(red, 1), "綠額(億)": round(grn, 1),
            "淨額(億)": round(red - grn, 1),
            "額加權漲跌%": round(float((g["chg"] * g["value"]).sum() / tot), 2),
            "戰況分數": round((red - grn) / (red + grn) * 100) if (red + grn) > 0 else 0,
        })
    return pd.DataFrame(rows).sort_values("淨額(億)", ascending=False)


def _render_battle(stock_df: pd.DataFrame, key_prefix: str):
    import plotly.graph_objects as go
    bt = battle_table(stock_df)
    if bt.empty:
        st.info("無法計算(缺成交額資料——更新股價後再試)。")
        return
    st.caption("**日級多空戰況**(收盤資料,非盤中tick):紅額=流向上漲股的成交額、綠額=下跌股;"
               "淨額=紅-綠 → **錢今天集中打哪個族群**。戰況分數=(紅-綠)/(紅+綠)×100,±100=一面倒。")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("##### 🔥 最強 10(淨額)")
        st.dataframe(bt.head(10)[["產業", "淨額(億)", "戰況分數", "額加權漲跌%", "上漲", "下跌"]],
                     hide_index=True, width="stretch")
    with s2:
        st.markdown("##### 🧊 最弱 10(淨額)")
        st.dataframe(bt.tail(10).iloc[::-1][["產業", "淨額(億)", "戰況分數", "額加權漲跌%", "上漲", "下跌"]],
                     hide_index=True, width="stretch")
    st.markdown("---")
    sec = st.selectbox("⚔️ 戰況詳情", bt["產業"].tolist(), key=f"{key_prefix}_battle_sec")
    r = bt[bt["產業"] == sec].iloc[0]
    g1, g2 = st.columns([1, 1.4])
    with g1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=float(r["戰況分數"]),
            number=dict(suffix=" 分"),
            gauge=dict(axis=dict(range=[-100, 100]),
                       bar=dict(color="#E5484D" if r["戰況分數"] >= 0 else "#3B82F6"),
                       steps=[dict(range=[-100, 0], color="rgba(59,130,246,.25)"),
                              dict(range=[0, 100], color="rgba(229,72,77,.25)")]),
            title=dict(text=f"{sec}|多方 vs 空方")))
        fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=8))
        st.plotly_chart(fig, width="stretch")
        _verdict = ("🔴 多方壓倒" if r["戰況分數"] >= 60 else
                    "🔴 多方占上風" if r["戰況分數"] >= 20 else
                    "🔵 空方壓倒" if r["戰況分數"] <= -60 else
                    "🔵 空方占上風" if r["戰況分數"] <= -20 else "⚪ 拉鋸")
        st.markdown(f"<div style='text-align:center;font-size:1.1rem;font-weight:700'>"
                    f"{_verdict}|淨額 {r['淨額(億)']:+.1f} 億</div>", unsafe_allow_html=True)
        _rp = r["紅額(億)"] / max(r["紅額(億)"] + r["綠額(億)"], 0.01) * 100
        st.markdown(f"<div style='display:flex;height:20px;border-radius:10px;overflow:hidden;"
                    f"margin-top:8px'><div style='width:{100-_rp:.0f}%;background:#3B82F6;"
                    f"color:#fff;font-size:11px;text-align:center'>{100-_rp:.0f}</div>"
                    f"<div style='width:{_rp:.0f}%;background:#E5484D;color:#fff;font-size:11px;"
                    f"text-align:center'>{_rp:.0f}</div></div>", unsafe_allow_html=True)
    with g2:
        mem = (stock_df[stock_df["sector"] == sec]
               .sort_values("value", ascending=False).head(12)
               [["ticker", "name", "chg", "close", "value"]]
               .rename(columns={"ticker": "代號", "name": "名稱", "chg": "漲跌%",
                                "close": "收盤", "value": "成交額(億)"}))
        mem["代號"] = mem["代號"].str.split(".").str[0]
        st.markdown("##### 💰 金額前 12 成員(誰在扛旗)")
        st.dataframe(mem, hide_index=True, width="stretch")


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

    ht3, ht1, htb, ht2 = st.tabs(["📝 強弱日報", "🌡️ 熱力地圖", "⚔️ 多空戰況表", "📋 族群明細"])

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
                                 width="stretch"):
                        if not stock_ret_df.empty:
                            _sector_drill_dialog(sec["sector"], stock_ret_df)

    with htb:
        _render_battle(stock_ret_df, key_prefix)

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
            disp.style.map(color_chg, subset=["平均漲跌%"])
                .format({"平均漲跌%": "{:+.2f}%", "上漲": "{:.0f}",
                         "下跌": "{:.0f}", "合計": "{:.0f}"}),
            width="stretch",
            height=min(700, len(disp) * 38 + 60),
        )

    with ht3:
        _render_daily_brief(key_prefix)


# ════════════════════════════════════════
# 強弱日報（自動成文；引擎見 daily_report.py）
# ════════════════════════════════════════
def _brief_bucket() -> str:
    """快取分桶:盤中(09:00-14:00)每30分鐘一桶;盤後/假日整天一桶。
    2026-09-20 修:原 ttl=1800 導致收盤後每30分鐘白白重寫(含引擎潤稿)。"""
    from twtime import now_tw
    t = now_tw()
    if t.weekday() < 5 and 9 <= t.hour < 14:
        return f"{t:%Y-%m-%d}#{t.hour}:{t.minute // 30}"
    return f"{t:%Y-%m-%d}#盤後"


@st.cache_data(ttl=24 * 3600, show_spinner="彙整今日強弱並撰寫日報中（約 10-30 秒）…")
def _daily_brief(polish: bool, bucket: str = "") -> str:
    import daily_report
    return daily_report.generate(polish=polish)


def _render_daily_brief(key_prefix: str = "sec"):
    """把大盤/族群強弱/RRG輪動/新聞熱度寫成一篇有感覺的短文"""
    c = st.columns([1.6, 1.4, 4])
    polish = c[0].toggle("🤖 Claude 潤稿", value=True, key=f"{key_prefix}_brief_polish",
                         help="需 ANTHROPIC_API_KEY；沒設也能出規則式版本")
    if c[1].button("🔄 重新生成", key=f"{key_prefix}_brief_regen"):
        _daily_brief.clear()
    try:
        art = _daily_brief(polish, _brief_bucket())
    except Exception as e:                      # 日報壞了不能拖垮整個主頁
        import traceback
        st.error(f"日報生成失敗：{type(e).__name__}: {e}")
        with st.expander("錯誤細節（回報用）"):
            st.code(traceback.format_exc()[-1500:])
        return
    st.markdown(art)
    st.download_button(
        "⬇️ 下載 Markdown", art.encode("utf-8"),
        file_name="daily_brief.md", mime="text/markdown",
        key=f"{key_prefix}_brief_dl")
    st.caption("盤中每 30 分鐘更新、收盤後凍結至隔日;強弱=族群成分等權漲跌,輪動=JdK RRG 近似,消息=產業新聞熱度。")

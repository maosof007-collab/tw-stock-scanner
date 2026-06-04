"""
pages/3_績效追蹤.py — 選股紀錄 & 績效追蹤

功能：
  - 新增持倉（股號、進場日、進場價、股數、停損價）
  - 即時損益（讀最新 CSV）
  - 績效圖表（持倉曲線、個別損益）
  - 已出場紀錄 & 統計
"""
import sys, json
from pathlib import Path
from datetime import datetime, date

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TRACK_FILE = ROOT / "data" / "portfolio_track.csv"

DARK   = "#0d1117"; CARD = "#161b22"; BORDER = "#30363d"
TEXT   = "#e6edf3"; MUTED = "#8b949e"
GREEN  = "#1D9E75"; RED = "#F85149"; GOLD = "#D29922"; BLUE = "#58A6FF"

st.set_page_config(page_title="績效追蹤", page_icon="📈", layout="wide")

st.markdown(f"""
<style>
  body, .stApp {{ background-color:{DARK}; color:{TEXT}; }}
  .pnl-card {{
    background:{CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:14px 18px; text-align:center;
  }}
  .pnl-label {{ color:{MUTED}; font-size:12px; margin-bottom:4px; }}
  .pnl-value {{ font-size:24px; font-weight:700; }}
  .green {{ color:{GREEN}; }} .red {{ color:{RED}; }}
  .gold  {{ color:{GOLD};  }} .blue {{ color:{BLUE}; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 工具
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def load_name_map():
    p = DATA_DIR / "stock_list.csv"
    if not p.exists(): return {}
    df = pd.read_csv(p, encoding="utf-8-sig")
    return dict(zip(df["ticker"].str.strip(), df["name"].str.strip()))

def load_portfolio() -> pd.DataFrame:
    """載入持倉紀錄"""
    if not TRACK_FILE.exists():
        return pd.DataFrame(columns=[
            "id","ticker","name","entry_date","entry_price",
            "shares","stop_loss","strategy","note",
            "exit_date","exit_price","status"
        ])
    df = pd.read_csv(TRACK_FILE, encoding="utf-8-sig")
    return df

def save_portfolio(df: pd.DataFrame):
    TRACK_FILE.parent.mkdir(exist_ok=True)
    df.to_csv(TRACK_FILE, index=False, encoding="utf-8-sig")

def get_current_price(ticker: str) -> float | None:
    """從本地 CSV 取最新收盤價"""
    for suffix in [".TW", ".TWO"]:
        p = DATA_DIR / f"{ticker.replace('.TW','').replace('.TWO','')}{suffix}.csv"
        if p.exists():
            try:
                df = pd.read_csv(p, index_col=0, parse_dates=True, usecols=[0,4])
                df.columns = ["Close"]
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                return float(df["Close"].dropna().iloc[-1])
            except: pass
    return None

def enrich_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """加入即時損益"""
    if df.empty: return df
    rows = []
    for _, r in df.iterrows():
        r = r.copy()
        if r.get("status") == "已出場":
            ep = float(r.get("exit_price") or 0)
            ent= float(r.get("entry_price") or 0)
            shares = float(r.get("shares") or 0)
            r["current_price"] = ep
            r["pnl_pct"]  = (ep - ent) / ent * 100 if ent else 0
            r["pnl_amt"]  = (ep - ent) * shares * 1000
        else:
            cp = get_current_price(str(r.get("ticker","")))
            ent = float(r.get("entry_price") or 0)
            shares = float(r.get("shares") or 0)
            r["current_price"] = cp or ent
            r["pnl_pct"] = (cp - ent) / ent * 100 if cp and ent else 0
            r["pnl_amt"] = (cp - ent) * shares * 1000 if cp and ent else 0
        rows.append(r)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 主畫面
# ─────────────────────────────────────────
st.title("📈 選股績效追蹤")
name_map = load_name_map()

portfolio = load_portfolio()
active_df  = portfolio[portfolio["status"] != "已出場"] if not portfolio.empty else pd.DataFrame()
closed_df  = portfolio[portfolio["status"] == "已出場"] if not portfolio.empty else pd.DataFrame()
active_rich = enrich_portfolio(active_df)
closed_rich = enrich_portfolio(closed_df)

# ── 新增持倉 sidebar ───────────────────────
with st.sidebar:
    st.markdown("## ➕ 新增持倉")

    # 從今日掃描結果快速匯入
    scan_csvs = sorted((ROOT / "scan_results").glob("signals_*.csv"), reverse=True)
    if scan_csvs:
        scan_df = pd.read_csv(scan_csvs[0], encoding="utf-8-sig")
        buy_df  = scan_df[scan_df["訊號等級"].str.contains("BUY", na=False)]
        if not buy_df.empty:
            st.markdown("**從今日訊號快速選入：**")
            selected = st.selectbox(
                "選擇股票",
                ["（手動輸入）"] + buy_df["代碼"].tolist(),
                label_visibility="collapsed",
            )
        else:
            selected = "（手動輸入）"
    else:
        selected = "（手動輸入）"
        buy_df   = pd.DataFrame()

    if selected != "（手動輸入）" and not buy_df.empty:
        row = buy_df[buy_df["代碼"] == selected].iloc[0]
        default_ticker = selected
        default_price  = float(row.get("收盤", 0))
        default_stop   = float(row.get("停損", 0))
        default_strat  = str(row.get("策略", ""))
    else:
        default_ticker = ""
        default_price  = 0.0
        default_stop   = 0.0
        default_strat  = ""

    with st.form("add_position", clear_on_submit=True):
        ticker_in = st.text_input("股票代碼（如 2330.TW）", value=default_ticker)
        c1, c2 = st.columns(2)
        entry_price = c1.number_input("進場價", value=default_price, min_value=0.0, step=0.1)
        shares_in   = c2.number_input("股數（張）", value=1, min_value=1, step=1)
        entry_date  = st.date_input("進場日", value=date.today())
        stop_loss   = st.number_input("停損價", value=default_stop, min_value=0.0, step=0.1)
        strategy_in = st.text_input("策略", value=default_strat)
        note_in     = st.text_input("備註")

        if st.form_submit_button("✅ 加入追蹤", type="primary", use_container_width=True):
            if not ticker_in:
                st.error("請輸入股票代碼")
            else:
                tk = ticker_in.strip().upper()
                # 補 suffix
                if not tk.endswith(".TW") and not tk.endswith(".TWO"):
                    tk += ".TW"
                name = name_map.get(tk, "")
                new_id = int(datetime.now().timestamp())
                new_row = pd.DataFrame([{
                    "id":          new_id,
                    "ticker":      tk,
                    "name":        name,
                    "entry_date":  str(entry_date),
                    "entry_price": entry_price,
                    "shares":      shares_in,
                    "stop_loss":   stop_loss,
                    "strategy":    strategy_in,
                    "note":        note_in,
                    "exit_date":   "",
                    "exit_price":  "",
                    "status":      "持倉中",
                }])
                portfolio = pd.concat([portfolio, new_row], ignore_index=True)
                save_portfolio(portfolio)
                st.success(f"已加入 {tk} {name}")
                st.rerun()

    st.markdown("---")
    st.markdown("**出場紀錄**")
    if not active_df.empty:
        exit_sel = st.selectbox(
            "選擇出場股票",
            active_df["ticker"].tolist(),
            label_visibility="collapsed",
        )
        exit_price_in = st.number_input("出場價", min_value=0.0, step=0.1, key="exit_price")
        exit_date_in  = st.date_input("出場日", value=date.today(), key="exit_date")
        if st.button("✅ 確認出場", use_container_width=True):
            idx = portfolio[
                (portfolio["ticker"] == exit_sel) & (portfolio["status"] == "持倉中")
            ].index
            if len(idx) > 0:
                portfolio.loc[idx[0], "exit_date"]  = str(exit_date_in)
                portfolio.loc[idx[0], "exit_price"] = exit_price_in
                portfolio.loc[idx[0], "status"]     = "已出場"
                save_portfolio(portfolio)
                st.success(f"{exit_sel} 已出場")
                st.rerun()


# ── KPI ────────────────────────────────────
st.markdown("---")
total_pnl   = float(active_rich["pnl_amt"].sum()) if not active_rich.empty else 0
total_cost  = float((active_rich["entry_price"] * active_rich["shares"] * 1000).sum()) if not active_rich.empty else 0
total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0
win_closed  = (closed_rich["pnl_pct"] > 0).sum() if not closed_rich.empty else 0
win_rate    = win_closed / len(closed_rich) * 100 if not closed_rich.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
for col, label, val, cls in [
    (k1, "持倉中",   f"{len(active_df)} 檔",     "blue"),
    (k2, "未實現損益", f"{total_pnl:+,.0f} 元",   "green" if total_pnl >= 0 else "red"),
    (k3, "未實現損益%", f"{total_pnl_pct:+.2f}%", "green" if total_pnl_pct >= 0 else "red"),
    (k4, "已出場",   f"{len(closed_df)} 筆",      ""),
    (k5, "出場勝率", f"{win_rate:.1f}%",           "green" if win_rate >= 50 else "gold"),
]:
    with col:
        st.markdown(
            f"""<div class="pnl-card">
            <div class="pnl-label">{label}</div>
            <div class="pnl-value {cls}">{val}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── 分頁 ────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 持倉損益圖", "📋 持倉明細", "🏁 出場紀錄"])

# ══ Tab1：損益圖 ════════════════════════════
with tab1:
    if active_rich.empty:
        st.info("尚無持倉，請從左側新增")
    else:
        # 個別損益橫條圖
        ar = active_rich.copy()
        ar["label"] = ar["ticker"] + "  " + ar["name"].fillna("")
        bar_c = [GREEN if v >= 0 else RED for v in ar["pnl_pct"]]

        fig_pnl = go.Figure(go.Bar(
            x=ar["pnl_pct"],
            y=ar["label"],
            orientation="h",
            marker=dict(color=bar_c, opacity=0.88),
            text=[f"  {v:+.2f}%  ({int(a/1000):+,}K)" for v, a in
                  zip(ar["pnl_pct"], ar["pnl_amt"])],
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "損益率：%{x:+.2f}%<br>"
                "損益額：%{customdata[0]:+,.0f} 元<br>"
                "進場：%{customdata[1]} @ %{customdata[2]:.1f}<extra></extra>"
            ),
            customdata=ar[["pnl_amt","entry_date","entry_price"]].values,
        ))
        fig_pnl.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
        fig_pnl.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            title=dict(text="持倉未實現損益",
                       font=dict(size=15, color=TEXT), x=0.01),
            xaxis=dict(gridcolor=BORDER, title="損益率 (%)"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
            height=max(350, len(ar)*40+80),
            margin=dict(l=10, r=120, t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

        # 距停損空間
        if "stop_loss" in ar.columns:
            ar2 = ar[ar["stop_loss"] > 0].copy()
            if not ar2.empty:
                ar2["to_stop"] = (ar2["current_price"] - ar2["stop_loss"]) / ar2["current_price"] * 100
                ar2 = ar2.sort_values("to_stop")
                stop_c = [RED if v < 3 else (GOLD if v < 8 else BLUE) for v in ar2["to_stop"]]
                fig_stop = go.Figure(go.Bar(
                    x=ar2["to_stop"],
                    y=ar2["ticker"] + "  " + ar2["name"].fillna(""),
                    orientation="h",
                    marker=dict(color=stop_c, opacity=0.85),
                    text=[f"  {v:.1f}%" for v in ar2["to_stop"]],
                    textposition="outside",
                    textfont=dict(size=12, color=TEXT),
                    hovertemplate="<b>%{y}</b><br>距停損：%{x:.1f}%<extra></extra>",
                ))
                fig_stop.update_layout(
                    paper_bgcolor=DARK, plot_bgcolor=CARD,
                    font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
                    title=dict(text="距停損空間（紅<3%警示）",
                               font=dict(size=15, color=TEXT), x=0.01),
                    xaxis=dict(gridcolor=BORDER, title="距停損 (%)"),
                    yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
                    height=max(300, len(ar2)*40+80),
                    margin=dict(l=10, r=80, t=50, b=30),
                    showlegend=False,
                )
                st.plotly_chart(fig_stop, use_container_width=True)


# ══ Tab2：持倉明細 ══════════════════════════
with tab2:
    if active_rich.empty:
        st.info("尚無持倉")
    else:
        show = [c for c in [
            "ticker","name","entry_date","entry_price","current_price",
            "pnl_pct","pnl_amt","stop_loss","shares","strategy","note"
        ] if c in active_rich.columns]

        rename = {
            "ticker":"代碼","name":"名稱","entry_date":"進場日",
            "entry_price":"進場價","current_price":"現價",
            "pnl_pct":"損益%","pnl_amt":"損益額",
            "stop_loss":"停損","shares":"張數",
            "strategy":"策略","note":"備註",
        }

        def color_pnl(val):
            if isinstance(val, float):
                if val > 5:   return f"color:{GREEN};font-weight:700"
                if val > 0:   return f"color:{GREEN}"
                if val < -5:  return f"color:{RED};font-weight:700"
                if val < 0:   return f"color:{RED}"
            return ""

        disp = active_rich[show].rename(columns=rename)
        st.dataframe(
            disp.style
                .applymap(color_pnl, subset=["損益%"] if "損益%" in disp.columns else [])
                .format({
                    "進場價":"{:.1f}","現價":"{:.1f}","停損":"{:.1f}",
                    "損益%":"{:+.2f}%","損益額":"{:+,.0f}",
                }),
            use_container_width=True,
            height=min(600, len(disp)*38+60),
        )

        # 刪除持倉
        with st.expander("🗑️ 刪除持倉"):
            del_sel = st.selectbox("選擇刪除", active_df["ticker"].tolist(), key="del_sel")
            if st.button("確認刪除", key="del_btn"):
                idx = portfolio[
                    (portfolio["ticker"] == del_sel) & (portfolio["status"] == "持倉中")
                ].index
                if len(idx):
                    portfolio = portfolio.drop(idx[0])
                    save_portfolio(portfolio)
                    st.rerun()


# ══ Tab3：出場紀錄 ══════════════════════════
with tab3:
    if closed_rich.empty:
        st.info("尚無出場紀錄")
    else:
        # 統計
        avg_win  = closed_rich[closed_rich["pnl_pct"]>0]["pnl_pct"].mean() if win_closed else 0
        avg_loss = closed_rich[closed_rich["pnl_pct"]<=0]["pnl_pct"].mean() if (len(closed_rich)-win_closed) else 0
        total_closed_pnl = closed_rich["pnl_amt"].sum()

        m1, m2, m3, m4 = st.columns(4)
        for col, label, val, cls in [
            (m1, "出場勝率",   f"{win_rate:.1f}%",        "green" if win_rate>=50 else "red"),
            (m2, "平均獲利",   f"+{avg_win:.2f}%",         "green"),
            (m3, "平均虧損",   f"{avg_loss:.2f}%",         "red"),
            (m4, "總實現損益", f"{total_closed_pnl:+,.0f}", "green" if total_closed_pnl>=0 else "red"),
        ]:
            with col:
                st.markdown(
                    f"""<div class="pnl-card">
                    <div class="pnl-label">{label}</div>
                    <div class="pnl-value {cls}">{val}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

        # 出場損益圖
        cr = closed_rich.copy()
        cr["label"] = cr["ticker"] + "  " + cr["name"].fillna("")
        cr = cr.sort_values("pnl_pct", ascending=False)
        bar_c2 = [GREEN if v > 0 else RED for v in cr["pnl_pct"]]
        fig_cl = go.Figure(go.Bar(
            x=cr["pnl_pct"],
            y=cr["label"],
            orientation="h",
            marker=dict(color=bar_c2, opacity=0.88),
            text=[f"  {v:+.2f}%" for v in cr["pnl_pct"]],
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            hovertemplate=(
                "<b>%{y}</b><br>損益率：%{x:+.2f}%<br>"
                "損益額：%{customdata[0]:+,.0f}<br>"
                "進場：%{customdata[1]}  出場：%{customdata[2]}<extra></extra>"
            ),
            customdata=cr[["pnl_amt","entry_date","exit_date"]].values,
        ))
        fig_cl.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
        fig_cl.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            title=dict(text="已出場損益", font=dict(size=15, color=TEXT), x=0.01),
            xaxis=dict(gridcolor=BORDER, title="損益率 (%)"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
            height=max(300, len(cr)*40+80),
            margin=dict(l=10, r=100, t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_cl, use_container_width=True)

        # 明細表
        show2 = [c for c in [
            "ticker","name","entry_date","entry_price",
            "exit_date","exit_price","pnl_pct","pnl_amt","strategy"
        ] if c in closed_rich.columns]
        rename2 = {
            "ticker":"代碼","name":"名稱","entry_date":"進場日",
            "entry_price":"進場價","exit_date":"出場日",
            "exit_price":"出場價","pnl_pct":"損益%","pnl_amt":"損益額","strategy":"策略"
        }
        disp2 = closed_rich[show2].rename(columns=rename2)
        st.dataframe(
            disp2.style
                .applymap(color_pnl, subset=["損益%"] if "損益%" in disp2.columns else [])
                .format({"進場價":"{:.1f}","出場價":"{:.1f}","損益%":"{:+.2f}%","損益額":"{:+,.0f}"}),
            use_container_width=True,
        )

        csv = disp2.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ 下載出場紀錄", csv,
                           file_name="trade_record.csv", mime="text/csv")

st.markdown(
    f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
    f"持倉資料：{TRACK_FILE}</p>",
    unsafe_allow_html=True,
)

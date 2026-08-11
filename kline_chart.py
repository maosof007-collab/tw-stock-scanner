"""
kline_chart.py — 共用 K 線圖（標買進箭頭）
給「績效追蹤」「今日選股」共用：畫蠟燭 + 均線 + 進場綠箭頭「買進」+ 停損線，
並可疊上策略的歷史買/賣訊（看波段中是否有第二買點）。
"""
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from ui_theme import DARK, CARD, BORDER, TEXT, GREEN, RED, GOLD, BLUE, PURPLE, CYAN

ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "data"


def _load_full(ticker: str) -> pd.DataFrame:
    code = ticker.replace(".TWO", "").replace(".TW", "").strip()
    for suf in [".TW", ".TWO"]:
        p = DATA_DIR / f"{code}{suf}.csv"
        if p.exists():
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            idx = pd.to_datetime(df.index)
            df.index = idx.tz_convert(None) if idx.tz is not None else idx
            for c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            return df.dropna(subset=["Close"])
    return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def _strategy_signals(ticker: str, strategy_name: str) -> pd.DataFrame:
    """跑策略取得買/賣訊（回傳只含 signal 的小表，已快取）"""
    try:
        from strategies import load_all_strategies
        from market_backtest import calc_indicators
        strat = load_all_strategies().get(strategy_name)
        if strat is None:
            return pd.DataFrame()
        df = _load_full(ticker)
        if len(df) < 260:
            return pd.DataFrame()
        bmp = DATA_DIR / "benchmark_TWII.csv"
        bm = pd.read_csv(bmp, index_col=0, parse_dates=True).iloc[:, 0] if bmp.exists() \
            else pd.Series(df["Close"].values, index=df.index)
        df.attrs["ticker"] = ticker
        df = calc_indicators(df, bm)
        out = strat.generate_signals(df, {k: v["default"] for k, v in strat.get_params().items()})
        return out[["signal"]].copy() if "signal" in out.columns else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def render_kline(ticker: str, name: str = "", *,
                 entry_date: str = "", entry_price: float = 0.0,
                 stop: float = 0.0, trail_stop: float = 0.0, lock_pct: float = 0.0,
                 strategy_name: str = "",
                 bars: int = 160, height: int = 460,
                 show_strategy_signals: bool = True):
    """畫一張 K 線圖：蠟燭+均線+進場綠箭頭(買進)+停損線+策略歷史買賣訊"""
    full = _load_full(ticker)
    if full.empty:
        st.warning(f"找不到 {ticker} 的價格資料")
        return
    kdf = full.tail(bars)

    fig = go.Figure()

    # 量（次座標）
    vol_c = [GREEN if kdf["Close"].iloc[i] >= kdf["Open"].iloc[i] else RED
             for i in range(len(kdf))]
    fig.add_trace(go.Bar(x=kdf.index, y=kdf["Volume"], marker=dict(color=vol_c, opacity=0.28),
                         name="量", yaxis="y2", showlegend=False,
                         hovertemplate="量 %{y:,.0f}<extra></extra>"))

    # 蠟燭
    fig.add_trace(go.Candlestick(
        x=kdf.index, open=kdf["Open"], high=kdf["High"], low=kdf["Low"], close=kdf["Close"],
        increasing=dict(line=dict(color=RED,   width=1), fillcolor=RED),     # 台股紅漲
        decreasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),   # 綠跌
        name="K線", showlegend=False,
    ))

    # 均線
    for ma, col, lbl in [(5, BLUE, "MA5"), (20, GOLD, "MA20"),
                         (60, PURPLE, "MA60"), (240, "#F0997B", "MA240")]:
        if len(full) >= ma:
            fig.add_trace(go.Scatter(
                x=kdf.index, y=full["Close"].rolling(ma).mean().tail(len(kdf)),
                line=dict(color=col, width=1.1), name=lbl,
            ))

    # ── 策略歷史買/賣訊（多次進場用不同顏色）──
    if show_strategy_signals and strategy_name:
        sig = _strategy_signals(ticker, strategy_name)
        if not sig.empty:
            # 先在「全歷史」上事件化(不能先切窗,否則持倉狀態會斷):
            # buy=進場(累計第幾次);sell 只有「持倉中遇到的第一個」算出場事件——
            # 很多策略的 sell 是條件旗標(條件成立天天標),全畫會變紅雨
            sg_full = sig["signal"]
            seq, sell_ev, cur, inpos = [], [], 0, False
            for s in sg_full.values:
                if s == "buy":
                    cur += 1
                    inpos = True
                    seq.append(cur)
                    sell_ev.append(False)
                elif s == "sell" and inpos:
                    cur = 0
                    inpos = False
                    seq.append(0)
                    sell_ev.append(True)
                else:
                    seq.append(0)
                    sell_ev.append(False)
            sig = sig.assign(seq=seq, sell_ev=sell_ev)
            sig = sig.reindex(kdf.index)
            sg = sig["signal"]

            # 第1~5+次進場各自顏色
            seq_colors = {1: CYAN, 2: GOLD, 3: PURPLE, 4: GREEN, 5: "#FF8FB1"}
            for k in sorted(set(s for s in seq if s > 0)):
                kk = min(k, 5)
                bb = kdf[sig["seq"] == k]
                if bb.empty:
                    continue
                lbl = f"第{k}次進場" if k < 5 else "第5+次進場"
                fig.add_trace(go.Scatter(
                    x=bb.index, y=bb["Low"] * 0.985, mode="markers",
                    marker=dict(symbol="triangle-up", size=13, color=seq_colors[kk],
                                line=dict(width=1, color="#021014")),
                    name=lbl,
                    hovertemplate=f"{lbl} %{{x|%Y-%m-%d}}<extra></extra>",
                ))
            sells = kdf[sig["sell_ev"] == True]          # noqa: E712 事件化出場
            if not sells.empty:
                fig.add_trace(go.Scatter(
                    x=sells.index, y=sells["High"] * 1.015, mode="markers",
                    marker=dict(symbol="triangle-down", size=11, color=RED,
                                line=dict(width=1, color="#021014")),
                    name="出場", hovertemplate="出場 %{x|%Y-%m-%d}<extra></extra>",
                ))

    # ── 我的進場：大綠箭頭 + 「買進」 ──
    if entry_date:
        try:
            ed = pd.to_datetime(entry_date)
            ep = float(entry_price) if entry_price else float(
                full.loc[full.index <= ed, "Close"].iloc[-1])
            if ed >= kdf.index[0]:
                fig.add_annotation(
                    x=ed, y=ep, text="買進", showarrow=True, arrowhead=2,
                    arrowsize=1.4, arrowwidth=2.5, arrowcolor=GREEN,
                    ax=0, ay=46,  # 箭頭從下往上指（綠箭頭朝上）
                    font=dict(color="#FFFFFF", size=13),
                    bgcolor=GREEN, bordercolor=GREEN, borderpad=3, opacity=0.95,
                )
        except Exception:
            pass

    # 初始停損線（淡）
    if stop and stop > 0:
        fig.add_hline(y=stop, line_dash="dot", line_color=RED, line_width=1.0,
                      annotation_text=f"初始停損 {stop:.1f}",
                      annotation_font=dict(color=RED, size=10))
    # 移動停利線（醒目）— 打到就賣、鎖住獲利
    if trail_stop and trail_stop > 0:
        _lk = f"（鎖利 {lock_pct:+.1f}%）" if lock_pct else ""
        fig.add_hline(y=trail_stop, line_dash="dash", line_color=GOLD, line_width=1.8,
                      annotation_text=f"移動停利 {trail_stop:.1f}{_lk}",
                      annotation_position="top left",
                      annotation_font=dict(color=GOLD, size=12))

    fig.update_layout(
        paper_bgcolor=DARK, plot_bgcolor=CARD,
        font=dict(family="Microsoft JhengHei, Arial", size=12, color=TEXT),
        title=dict(text=f"{ticker}　{name}", font=dict(size=14, color=TEXT), x=0.01),
        xaxis=dict(gridcolor=BORDER, rangeslider=dict(visible=False), type="date"),
        yaxis=dict(gridcolor=BORDER, side="right", title="價"),
        yaxis2=dict(overlaying="y", side="left", showgrid=False,
                    showticklabels=False, range=[0, kdf["Volume"].max() * 5]),
        legend=dict(orientation="h", x=0, y=1.04, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=TEXT)),
        height=height, hovermode="x unified",
        margin=dict(l=10, r=55, t=44, b=28),
    )
    st.plotly_chart(fig, width="stretch")

"""
chip_chart.py — 5 軌籌碼圖（共用）
籌碼分析儀表板 與 今日選股個股彈窗 共用同一張圖：
K線+MA / 外資每日買賣超 / 外資投信法人累積 / 大戶散戶持股% / 主力(融資)累積。
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import numpy as np
import pandas as pd
import data_provider as dp
from ui_common import THEME


def _supertrend(ohlc, period: int = 10, mult: float = 4.0):
    """SUPER TREND：ATR 通道趨勢線。回傳 (st_line, direction)
       direction: 1=多(線在價下), -1=空(線在價上)。標準遞迴實作。"""
    h = ohlc["high"].values; l = ohlc["low"].values; c = ohlc["close"].values
    n = len(c)
    hl2 = (h + l) / 2.0
    prev = np.empty(n); prev[0] = c[0]; prev[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    atr = pd.Series(tr).rolling(period).mean().values
    ub = hl2 + mult * atr
    lb = hl2 - mult * atr
    fub = ub.copy(); flb = lb.copy()
    st = np.full(n, np.nan); direction = np.ones(n)
    for i in range(1, n):
        if np.isnan(atr[i]):
            continue
        # 暖身後第一根有效：直接用原始band起始，避免 carry 到 NaN
        if np.isnan(fub[i-1]):
            fub[i] = ub[i]; flb[i] = lb[i]
            st[i] = fub[i]; direction[i] = -1
            continue
        fub[i] = ub[i] if (ub[i] < fub[i-1] or c[i-1] > fub[i-1]) else fub[i-1]
        flb[i] = lb[i] if (lb[i] > flb[i-1] or c[i-1] < flb[i-1]) else flb[i-1]
        if np.isnan(st[i-1]):
            st[i] = fub[i]; direction[i] = -1
        elif st[i-1] == fub[i-1]:
            if c[i] <= fub[i]:
                st[i] = fub[i]; direction[i] = -1
            else:
                st[i] = flb[i]; direction[i] = 1
        else:
            if c[i] >= flb[i]:
                st[i] = flb[i]; direction[i] = 1
            else:
                st[i] = fub[i]; direction[i] = -1
    return st, direction


def supertrend_stats(ticker: str, period: int = 10, mult: float = 4.0,
                     cont_window: int = 20, lookback_years: int = 10,
                     ohlc=None) -> dict | None:
    """SUPER TREND 統計（重現 XQ PRO MAX 左側表）。
    period=ATR期間, mult=ATR乘數, cont_window=統計窗口(M), lookback_years=統計年數(N)。
    回傳：目前多空、支撐/壓力線值、多頭空頭 平均/最小長度、延續機率(段長≥M 的比率)。"""
    if ohlc is None:
        days = max(period + 30, int(lookback_years * 245))   # N 年 ≈ N×245 交易日
        ohlc = dp.get_ohlcv(ticker, period_days=days)
    if ohlc is None or len(ohlc) < period + 10:
        return None
    st_line, direction = _supertrend(ohlc, period=period, mult=mult)
    valid = ~np.isnan(st_line)
    if valid.sum() < 5:
        return None
    dirs = direction[valid].astype(int)
    line = st_line[valid]

    # 切段：連續同方向為一段，記長度
    bull_lens, bear_lens = [], []
    cur = dirs[0]; length = 1
    for d in dirs[1:]:
        if d == cur:
            length += 1
        else:
            (bull_lens if cur == 1 else bear_lens).append(length)
            cur = d; length = 1
    current_dir = int(cur); current_len = int(length)   # 最後一段=進行中

    def _agg(lst):
        if not lst:
            return None, None, None
        a = np.array(lst)
        return float(a.mean()), int(a.min()), float((a >= cont_window).mean() * 100)

    b_avg, b_min, b_cont = _agg(bull_lens)
    s_avg, s_min, s_cont = _agg(bear_lens)
    cur_line = float(line[-1])
    return {
        "dir": current_dir, "current_len": current_len, "cont_window": cont_window,
        "bull_support": cur_line if current_dir == 1 else None,
        "bear_resist":  cur_line if current_dir == -1 else None,
        "bull_avg": b_avg, "bear_avg": s_avg,
        "bull_min": b_min, "bear_min": s_min,
        "bull_cont": b_cont, "bear_cont": s_cont,
    }


def render_supertrend_table(ticker: str, period: int = 10, mult: float = 4.0,
                            cont_window: int = 20, lookback_years: int = 10, ohlc=None):
    """在 Streamlit 畫出 XQ 風格的 SUPER TREND 左側統計表。"""
    import streamlit as st
    s = supertrend_stats(ticker, period, mult, cont_window, lookback_years, ohlc=ohlc)
    if s is None:
        st.caption("SUPER TREND：資料不足")
        return
    up, dn, mut = THEME["up"], THEME["down"], THEME["muted"]
    dir_txt = ("<span style='color:%s'>多頭 ▲</span>" % up) if s["dir"] == 1 \
        else ("<span style='color:%s'>空頭 ▼</span>" % dn)

    def fnum(v, suf="", dash="N/A"):
        return dash if v is None else f"{v:.2f}{suf}" if isinstance(v, float) else f"{v}{suf}"

    rows = [
        ("SUPER 多方支撐", fnum(s["bull_support"]), up),
        ("SUPER 空方壓力", fnum(s["bear_resist"]), dn),
        ("多頭平均長度", fnum(s["bull_avg"]), None),
        ("空頭平均長度", fnum(s["bear_avg"]), None),
        ("多頭最小長度", fnum(s["bull_min"]), None),
        ("空頭最小長度", fnum(s["bear_min"]), None),
        (f"支撐延續機率(≥{cont_window})", fnum(s["bull_cont"], "%"), up),
        (f"壓力延續機率(≥{cont_window})", fnum(s["bear_cont"], "%"), dn),
    ]
    body = "".join(
        f"<div style='display:flex;justify-content:space-between;padding:4px 8px;"
        f"border-bottom:1px solid rgba(255,255,255,.06)'>"
        f"<span style='color:{mut};font-size:.82rem'>{k}</span>"
        f"<span style='color:{c or THEME['text']};font-weight:600;font-size:.86rem'>{v}</span></div>"
        for k, v, c in rows
    )
    header = (f"<div style='padding:6px 8px;font-weight:700;color:{THEME['accent']}'>"
              f"⚡ SUPER TREND　目前：{dir_txt}"
              f"　<span style='color:{mut};font-weight:400;font-size:.8rem'>"
              f"已延續 {s['current_len']} 根</span></div>")
    st.markdown(
        f"<div style='background:{THEME['panel']};border:1px solid rgba(255,255,255,.1);"
        f"border-radius:8px;overflow:hidden;margin-bottom:10px'>{header}{body}</div>",
        unsafe_allow_html=True)


def build_supertrend_figure(ticker: str, period: int = 10, mult: float = 4.0,
                            bars: int = 200, height: int = 360, ohlc=None):
    """獨立 SUPER TREND 圖：K線 + 趨勢線（多段紅=支撐 / 空段綠=壓力）。"""
    if ohlc is None:
        ohlc = dp.get_ohlcv(ticker, period_days=max(period + 40, bars + 80))
    if ohlc is None or len(ohlc) < period + 10:
        return None
    st_line, direction = _supertrend(ohlc, period=period, mult=mult)
    o = ohlc.tail(bars).reset_index(drop=True)
    stl = st_line[-bars:]; dr = direction[-bars:]
    bull = np.where(dr == 1, stl, np.nan)
    bear = np.where(dr == -1, stl, np.nan)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=o["date"], open=o["open"], high=o["high"], low=o["low"], close=o["close"],
        increasing_line_color=THEME["up"], decreasing_line_color=THEME["down"],
        increasing_fillcolor=THEME["up"], decreasing_fillcolor=THEME["down"],
        name="K", showlegend=False))
    fig.add_trace(go.Scatter(x=o["date"], y=bull, mode="lines",
                             line=dict(color=THEME["up"], width=2), name="多頭支撐"))
    fig.add_trace(go.Scatter(x=o["date"], y=bear, mode="lines",
                             line=dict(color=THEME["down"], width=2), name="空頭壓力"))
    fig.update_layout(
        height=height, template="plotly_dark",
        paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
        font=dict(color=THEME["text"], size=11), title="⚡ SUPER TREND",
        margin=dict(l=6, r=6, t=32, b=6), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)))
    fig.update_xaxes(gridcolor=THEME["grid"])
    fig.update_yaxes(gridcolor=THEME["grid"], side="right")
    return fig


def _seg_stats(dirs, line, cont_window):
    """由 direction/st_line（已去暖身）算多空段統計。回傳 dict。"""
    bull_lens, bear_lens = [], []
    cur = dirs[0]; length = 1
    for d in dirs[1:]:
        if d == cur:
            length += 1
        else:
            (bull_lens if cur == 1 else bear_lens).append(length)
            cur = d; length = 1
    def _agg(lst):
        if not lst:
            return None, None, None
        a = np.array(lst)
        return float(a.mean()), int(a.min()), float((a >= cont_window).mean() * 100)
    b_avg, b_min, b_cont = _agg(bull_lens)
    s_avg, s_min, s_cont = _agg(bear_lens)
    return {"dir": int(cur), "current_len": int(length),
            "bull_support": float(line[-1]) if cur == 1 else None,
            "bear_resist":  float(line[-1]) if cur == -1 else None,
            "bull_avg": b_avg, "bear_avg": s_avg, "bull_min": b_min, "bear_min": s_min,
            "bull_cont": b_cont, "bear_cont": s_cont,
            "n_bull_seg": len(bull_lens), "n_bear_seg": len(bear_lens)}


def scan_supertrend_flips(period: int = 10, mult: float = 4.0, cont_window: int = 20,
                          lookback_years: int = 10, flip_within: int = 1,
                          progress=None):
    """全市場掃描：近 flip_within 個交易日內『空→多』翻多的股。
    回傳 DataFrame（代碼/名稱/翻多日/收盤/支撐/距支撐%/多頭平均長度/支撐延續機率%/已延續）。"""
    import glob, os
    days = max(period + 30, int(lookback_years * 245))
    files = sorted(glob.glob(str(dp.DATA / "*.TW.csv")) +
                   glob.glob(str(dp.DATA / "*.TWO.csv")))
    rows = []
    total = len(files)
    for k, f in enumerate(files):
        if progress and k % 100 == 0:
            progress(k, total)
        base = os.path.basename(f)
        code = base.replace(".TWO.csv", "").replace(".TW.csv", "")
        ohlc = dp.get_ohlcv(code, period_days=days)
        if ohlc is None or len(ohlc) < period + 20:
            continue
        st_line, direction = _supertrend(ohlc, period=period, mult=mult)
        valid = ~np.isnan(st_line)
        if valid.sum() < 10:
            continue
        d_all = direction[valid].astype(int)
        l_all = st_line[valid]
        if d_all[-1] != 1:               # 現在必須是多頭
            continue
        # 最近一次 空→多 的位置
        flip_i = None
        for i in range(len(d_all) - 1, 0, -1):
            if d_all[i] == 1 and d_all[i - 1] == -1:
                flip_i = i
                break
        if flip_i is None:
            continue
        days_since = (len(d_all) - 1) - flip_i
        if days_since >= flip_within:    # 只要「近 flip_within 內」剛翻多
            continue
        s = _seg_stats(d_all, l_all, cont_window)
        # 用有效段對應的日期
        vdates = ohlc["date"].values[valid]
        close = float(ohlc["close"].iloc[-1])
        support = float(l_all[-1])
        # 流動性:昨日量/20日均量(張)與日均成交值——沒量的翻多做不了
        v_lots = a_lots = turn_m = vol_ratio = None
        if "volume" in ohlc.columns:
            v = ohlc["volume"].dropna()
            if len(v):
                v_lots = float(v.iloc[-1]) / 1000
                a_lots = float(v.tail(20).mean()) / 1000
                turn_m = a_lots * 1000 * close / 1e6
                vol_ratio = v_lots / a_lots if a_lots else None
        rows.append({
            "代碼": code, "名稱": dp.stock_name(code),
            "翻多日": str(pd.to_datetime(vdates[flip_i]).date()),
            "收盤": round(close, 2), "支撐": round(support, 2),
            "距支撐%": round((close - support) / close * 100, 2) if close else None,
            "昨日量(張)": round(v_lots) if v_lots is not None else None,
            "20日均量(張)": round(a_lots) if a_lots is not None else None,
            "日均值(百萬)": round(turn_m, 1) if turn_m is not None else None,
            "量比": round(vol_ratio, 2) if vol_ratio is not None else None,
            "多頭平均長度": round(s["bull_avg"]) if s["bull_avg"] else None,
            "支撐延續機率%": round(s["bull_cont"], 1) if s["bull_cont"] is not None else None,
            "已延續": s["current_len"],
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["支撐延續機率%", "距支撐%"],
                            ascending=[False, True], na_position="last").reset_index(drop=True)
    return df


def _add_regime_ribbon(fig, ohlc, row=1):
    """雙重颱風多空色帶：close vs ma30、ma30 vs ma60 兩條件
       多(紅) / 空(綠) / 盤整(灰)。在 K 線面板底部放一條方塊色帶。"""
    import plotly.graph_objects as go
    c, m30, m60 = ohlc["close"], ohlc["ma30"], ohlc["ma60"]
    bull = (c > m30) & (m30 > m60)
    bear = (c < m30) & (m30 < m60)
    cmap = np.where(bull, THEME["up"], np.where(bear, THEME["down"], "#3A4A63"))
    label = np.where(bull, "多", np.where(bear, "空", "盤整"))
    y = float(ohlc["low"].min()) * 0.985  # 貼在價格區下緣
    fig.add_trace(go.Scatter(
        x=ohlc["date"], y=[y] * len(ohlc), mode="markers",
        marker=dict(symbol="square", size=7, color=list(cmap)),
        name="多空", showlegend=False,
        customdata=label,
        hovertemplate="%{x|%Y-%m-%d}　%{customdata}<extra></extra>",
    ), row=row, col=1)


# 5 軌定義（key, 標題, 相對高度）— 供「軌道獨立開關」用
CHIP_TRACKS = [
    ("price",         "　",                              0.42),
    ("foreign_daily", "外資每日買賣超(張) · 金=突增",     0.15),
    ("inst_cum",      "外資 / 投信 / 法人　累積買賣超(張)", 0.16),
    ("holders",       "大戶 / 散戶　持股%",               0.15),
    ("margin",        "融資餘額(張)",                     0.12),
]
CHIP_TRACK_LABELS = {
    "price": "K線＋均線＋SuperTrend", "foreign_daily": "外資每日買賣超",
    "inst_cum": "外資/投信/法人 累積", "holders": "大戶/散戶 持股%", "margin": "融資餘額",
}


def build_chip_figure(ticker: str, period_days: int = 400, height: int = 720,
                      tracks=None):
    """回傳籌碼 plotly 圖（可選軌道）；找不到股價回 None。
    tracks：要顯示的軌道 key 清單（見 CHIP_TRACKS），None＝全 5 軌。
    例：tracks=['inst_cum'] → 只單獨看法人累積。"""
    ohlc = dp.get_ohlcv(ticker, period_days)
    if ohlc.empty:
        return None
    chips  = dp.get_chip_flows(ticker, period_days)
    fdaily = dp.get_foreign_daily(ticker, spike_mult=3.0)

    keys_all = [k for k, _, _ in CHIP_TRACKS]
    if tracks is None:
        tracks = keys_all
    sel = [k for k in keys_all if k in tracks] or ["price"]   # 至少留一軌
    heights = [h for k, _, h in CHIP_TRACKS if k in sel]
    tot = sum(heights) or 1
    heights = [h / tot for h in heights]
    titles = [t for k, t, _ in CHIP_TRACKS if k in sel]
    row_of = {k: i + 1 for i, k in enumerate(sel)}   # key → 列號

    fig = make_subplots(
        rows=len(sel), cols=1, shared_xaxes=True,
        row_heights=heights, vertical_spacing=0.05, subplot_titles=titles,
    )

    if "price" in row_of:
        r = row_of["price"]
        fig.add_trace(go.Candlestick(
            x=ohlc["date"], open=ohlc["open"], high=ohlc["high"],
            low=ohlc["low"], close=ohlc["close"], name="K",
            increasing_line_color=THEME["up"], decreasing_line_color=THEME["down"],
        ), row=r, col=1)
        fig.add_trace(go.Scatter(x=ohlc["date"], y=ohlc["ma30"], name="MA30",
                                 line=dict(color=THEME["ma30"], width=1.2)), row=r, col=1)
        fig.add_trace(go.Scatter(x=ohlc["date"], y=ohlc["ma60"], name="MA60",
                                 line=dict(color=THEME["ma60"], width=1.2)), row=r, col=1)
        _add_regime_ribbon(fig, ohlc, row=r)   # 雙重颱風多空色帶

        st_line, st_dir = _supertrend(ohlc, period=10, mult=4.0)
        up_y   = np.where(st_dir == 1,  st_line, np.nan)
        down_y = np.where(st_dir == -1, st_line, np.nan)
        fig.add_trace(go.Scatter(x=ohlc["date"], y=up_y, name="SuperTrend多",
                                 mode="lines", connectgaps=False,
                                 line=dict(color=THEME["up"], width=2.2)), row=r, col=1)
        fig.add_trace(go.Scatter(x=ohlc["date"], y=down_y, name="SuperTrend空",
                                 mode="lines", connectgaps=False,
                                 line=dict(color=THEME["down"], width=2.2)), row=r, col=1)
        flip = np.where(st_dir[1:] != st_dir[:-1])[0] + 1
        if len(flip):
            fd = ohlc["date"].values[flip]; fy = st_line[flip]; fdir = st_dir[flip]
            fig.add_trace(go.Scatter(
                x=fd, y=fy, mode="markers", name="趨勢反轉",
                marker=dict(symbol=["triangle-up" if d == 1 else "triangle-down" for d in fdir],
                            size=11, color=["#FF4D6D" if d == 1 else "#2BE4A8" for d in fdir],
                            line=dict(width=1, color="#04070D")),
                hovertemplate="趨勢反轉 %{x|%Y-%m-%d}<extra></extra>",
            ), row=r, col=1)

    if "foreign_daily" in row_of and not fdaily.empty:
        r = row_of["foreign_daily"]
        base_col = [THEME["down"] if v >= 0 else THEME["up"] for v in fdaily["foreign_net"]]
        bar_col = ["#FFC857" if sp else base_col[i]
                   for i, sp in enumerate(fdaily["is_spike"])]
        fig.add_trace(go.Bar(
            x=fdaily["date"], y=fdaily["foreign_net"], name="外資買賣超",
            marker_color=bar_col, customdata=fdaily["foreign_pct"],
            hovertemplate="%{x|%Y-%m-%d}<br>外資 %{y} 張<br>佔成交量 %{customdata}%<extra></extra>",
        ), row=r, col=1)

    if "inst_cum" in row_of:
        r = row_of["inst_cum"]
        for col, color in [("外資", "#FFC857"), ("投信", THEME["down"]), ("法人", "#4FA8FF")]:
            if col in chips:
                fig.add_trace(go.Scatter(x=chips["date"], y=chips[col], name=col,
                                         legendgroup="g3", legendgrouptitle_text="累積張",
                                         connectgaps=False,
                                         line=dict(color=color, width=1.5)), row=r, col=1)

    if "holders" in row_of and "大戶" in chips:
        r = row_of["holders"]
        fig.add_trace(go.Scatter(x=chips["date"], y=chips["大戶"], name="大戶",
                                 legendgroup="g4", legendgrouptitle_text="持股%",
                                 connectgaps=False,
                                 line=dict(color="#FFC857", width=1.6)), row=r, col=1)
        fig.add_trace(go.Scatter(x=chips["date"], y=chips["散戶"], name="散戶",
                                 legendgroup="g4", connectgaps=False,
                                 line=dict(color="#8FB8FF", width=1.6)), row=r, col=1)

    if "margin" in row_of and "主力" in chips:
        r = row_of["margin"]
        fig.add_trace(go.Scatter(x=chips["date"], y=chips["主力"], name="融資餘額",
                                 legendgroup="g5", legendgrouptitle_text="融資",
                                 connectgaps=False,
                                 line=dict(color="#B49BFF", width=1.6),
                                 fill="tozeroy", fillcolor="rgba(180,155,255,0.10)"),
                      row=r, col=1)

    fig.update_layout(
        height=height, template="plotly_dark",
        paper_bgcolor=THEME["bg"], plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=120, t=20, b=12),
        xaxis_rangeslider_visible=False, showlegend=True,
        legend=dict(font=dict(size=10), tracegroupgap=12, y=1.0,
                    bgcolor="rgba(11,19,34,0.55)", bordercolor=THEME["grid"], borderwidth=1),
        font=dict(color=THEME["text"]),
        bargap=0.1,
    )
    # 格線淡一點、零軸明顯一點
    fig.update_xaxes(gridcolor="rgba(28,44,74,0.5)", showline=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(28,44,74,0.5)", zeroline=True,
                     zerolinecolor="rgba(100,123,156,0.45)", zerolinewidth=1)
    # 副標題：改成左上小字（不再置中壓在資料上）
    for ann in fig.layout.annotations:
        ann.update(xanchor="left", x=0.004, font=dict(size=11, color=THEME["accent"]),
                   bgcolor="rgba(4,7,13,0.55)")
    return fig

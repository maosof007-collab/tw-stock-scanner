# -*- coding: utf-8 -*-
"""
pages/42_盤中資金流.py — 即時族群資金流(Shioaji Pro 同款四區版面,自家免費版)
=================================================================
「我想做一個跟台新即時的平台,即時看族群資金流進流出」(2026-10-28)
「即時頁面改這樣吧」(2026-10-29,附 Shioaji Pro 截圖)→ 改四區:
  ①市場脈動(指數/台幣/宇宙累計淨流大數字) ②族群資金流向泡泡圖
  ③累計淨流排行                         ④產業全景 treemap + 個股貢獻
盤中(09:00-13:32)每 60 秒自動輪詢證交所 MIS 快照 → 量增量×價×方向=資金流。
紅=流入(漲)、綠=流出(跌)——台股習慣。收盤後顯示當日(或最近一日)全貌。
注意:這是推估(快照級),不是逐筆內外盤;族群排序才是重點,個股數字看相對。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import ui_theme as T
from ui_theme import inject_css, page_header

st.set_page_config(page_title="盤中資金流", page_icon="🌊", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("盤中資金流(族群即時)", "LIVE MONEY FLOW", "🌊")

import rt_flow as RT
from twtime import now_tw

# 長駐進程防呆:pages/*.py 會熱載入,但 import 的模組不會——偵測到舊版就地 reload
if not hasattr(RT, "_seed_last_px"):
    import importlib
    RT = importlib.reload(RT)

import margin_break as MB
if getattr(MB, "VERSION", 0) < 4:          # 同上:長駐進程裡若是舊版就地 reload
    import importlib
    MB = importlib.reload(MB)


def _mb_data() -> dict:
    """維持率破底名單:盤中用 MIS 即時價量,其餘時間用昨晚建檔的收盤口徑。"""
    w = MB.load()
    if w.empty:
        return {"w": w}
    n = int(st.session_state.get("mb_n", 60))
    amt = float(st.session_state.get("mb_amt", MB.MIN_AMT20))    # 20 日均成交額門檻(萬)
    ddate = w["日期"].max()
    t = now_tw()
    out = {"w": w, "n": n, "amt": amt, "ddate": ddate, "mode": "eod",
           "watch": int((w["均額20"] >= amt).sum())}
    if t.weekday() < 5 and f"{t:%Y-%m-%d}" > ddate and f"{t:%H:%M}" >= "09:00":
        try:
            cand = MB.candidates(w, n, min_amt=amt)
            q = MB.quotes(cand)
            lday = MB.live_day(q, w)
            if lday:
                MB.record(q, lday)
                out.update(mode="live", lday=lday, watch=len(cand), got=len(q),
                           stale=MB.stale_share(cand, q),
                           tbl=MB.live_table(cand, q, MB.load_hist(lday)))
            elif q.empty and _trading_now():
                out["warn"] = "盤中報價沒抓到(證交所 MIS 沒回應),暫時顯示收盤口徑;60 秒後會再試。"
        except Exception as e:
            out["warn"] = f"盤中即時計算失敗({type(e).__name__}),暫時顯示收盤口徑。"
    if out["mode"] == "eod":
        out["tbl"] = MB.eod_table(w, n, min_amt=amt)
    out["hot"] = MB.hot(out["tbl"], float(st.session_state.get("mb_vr", 1.5)))
    return out


def _mb_line(mb: dict) -> None:
    """頁首一行:今天有幾檔,點了跳到下面的表。"""
    if mb["w"].empty:
        return
    h = mb["hot"]
    names = "、".join(h.sort_values("量比", ascending=False)["名稱"].head(5)) if len(h) else "目前沒有"
    st.markdown(f'<div style="margin:.4rem 0 .2rem 0;font-size:.95rem">💥 <b>維持率破底 × 爆量:{len(h)} 檔</b>'
                f'<span style="color:{T.MUTED}">({names}{"…" if len(h) > 5 else ""})</span>'
                f' <a href="#mbreak" target="_self">↓ 看名單</a></div>', unsafe_allow_html=True)


def _mb_block(mb: dict) -> None:
    st.markdown('<div id="mbreak" style="scroll-margin-top:5rem"></div>', unsafe_allow_html=True)
    st.markdown("#### 💥 維持率破底 × 爆量(斷頭賣壓觀察)")
    if mb["w"].empty:
        st.info("還沒有名單——本機跑 `python margin_break.py`(約 30 秒);之後每晚排程會自動建。")
        return
    live_mode = mb["mode"] == "live"
    f = st.columns([1, 1, 1, 2])
    f[2].selectbox("20日均成交額至少", list(MB.AMT_CHOICES), key="mb_amt",
                   index=list(MB.AMT_CHOICES).index(MB.MIN_AMT20),
                   format_func=lambda x: f"{x/1e4:g} 億",
                   help="平常成交太少的股票整個不看(破底檔數、名單、下面的展開表都不算它)")
    f[0].selectbox("破底=跌破近幾日最低", list(MB.WINDOWS), index=1, key="mb_n",
                   format_func=lambda x: f"{x} 日")
    f[1].slider("量比至少", 1.0, 5.0, 1.5, 0.1, key="mb_vr")
    tbl, h = mb["tbl"], mb["hot"]
    if mb.get("warn"):
        st.warning(mb["warn"])
    if mb.get("stale", 0) > 0.3:
        st.warning(f"名單是 {mb['ddate'][5:]} 建的,不是上一個交易日——中間那幾天沒算進破底線,"
                   "結果會偏多。本機跑 `python margin_break.py` 重建(約 30 秒)。")
    c = st.columns(4)
    if live_mode:
        c[0].metric("口徑", "🔴 盤中即時", f"{now_tw():%H:%M:%S}", delta_color="off")
        c[1].metric("今天盯", f"{mb['watch']} 檔", f"跌停內會破底、均額≥{mb['amt']/1e4:g}億", delta_color="off")
    else:
        c[0].metric("口徑", "⏸ 收盤", f"資料日 {mb['ddate'][5:]}", delta_color="off")
        c[1].metric("納入觀察", f"{mb['watch']:,} 檔", f"有融資、20日均額≥{mb['amt']/1e4:g}億", delta_color="off")
    c[2].metric(f"維持率破 {mb['n']} 日低", f"{len(tbl)} 檔", delta_color="off")
    c[3].metric("其中爆量", f"{len(h)} 檔", f"量比≥{st.session_state.get('mb_vr', 1.5):.1f}"
                + (" 或近5分≥3倍" if live_mode else ""), delta_color="off")
    px_col = "最新" if live_mode else "收盤"
    chg_col = "今漲跌%" if live_mode else "漲跌%"
    has5 = live_mode and tbl["近5分量比"].notna().any()      # 沒有逐分紀錄時整欄是空的,不顯示
    cols = (["代號", "名稱", px_col, chg_col, "維持率%", "前低%", "前低日", "跌破%", "量比"]
            + (["近5分量比", "爆量"] if has5 else ([] if live_mode else ["日增減%"]))
            + ["成交額(億)", "融資餘額", "使用率%"])
    cfg = {
        chg_col: st.column_config.NumberColumn("漲跌%", format="%+.2f%%"),
        px_col: st.column_config.NumberColumn(format="%.2f"),
        "維持率%": st.column_config.NumberColumn("維持率", format="%.1f%%",
                                              help="現價÷估算融資成本÷0.6。推估值;130% 是追繳線"),
        "前低%": st.column_config.NumberColumn("前低", format="%.1f%%", help="破底之前,這段期間最低的維持率"),
        "跌破%": st.column_config.NumberColumn("跌破幅度", format="%+.2f%%"),
        "量比": st.column_config.NumberColumn(format="%.1f", help="盤中:累積量÷(5日均量×這個時間平常成交的比例);收盤:當日量÷前5日均量"),
        "近5分量比": st.column_config.NumberColumn("近5分量比", format="%.1f",
                                                help="最近約5分鐘成交的張數÷這5分鐘平常該有的張數。這頁要開著3分鐘以上才有值"),
        "日增減%": st.column_config.NumberColumn("融資當日增減", format="%+.2f%%",
                                              help="證交所真實張數。大減=斷頭或停損出場;增加=有人攤平"),
        "成交額(億)": st.column_config.NumberColumn(format="%.2f"),
        "融資餘額": st.column_config.NumberColumn("融資餘額(張)", format="%d"),
        "使用率%": st.column_config.NumberColumn("融資使用率", format="%.1f%%"),
    }
    if len(h):
        v = h.sort_values(["爆量", "量比"], ascending=[True, False]) if live_mode             else h.sort_values("量比", ascending=False)
        st.dataframe(v[cols], hide_index=True, use_container_width=True,
                     height=min(460, 38 + 35 * len(v)), column_config=cfg)
    else:
        st.info("目前沒有「破底又爆量」的股票。" + ("盤中每 60 秒重看一次。" if live_mode else ""))
    if live_mode and not has5:
        st.caption("「近5分量比」還沒有值:要這頁在盤中連續開著 3 分鐘以上才算得出來,現在先只看全日量比。")
    rest = tbl[~tbl["代號"].isin(h["代號"])] if len(tbl) else tbl
    if len(rest):
        with st.expander(f"破底但量沒放大的 {len(rest)} 檔"):
            st.dataframe(rest.sort_values("跌破%")[[x for x in cols if x != "爆量"]], hide_index=True,
                         use_container_width=True, height=360, column_config=cfg)
    st.caption("**破底**=維持率跌破前面這段期間的最低點(算法和斷頭雷達的個股曲線相同,是推估值)。"
               "**爆量**=量比達到門檻" + (",或近 5 分鐘的量是平常的 3 倍以上(標 ⚡)" if live_mode else "")
               + f"。**成交量太低的不看**:20 日均成交額不到 {mb['amt']/1e4:g} 億的股票,"
                 f"破底檔數和名單都不算(全市場有融資的 {len(mb['w']):,} 檔裡剩 "
                 f"{int((mb['w']['均額20'] >= mb['amt']).sum()):,} 檔)。"
               + ("盤中的成本用昨晚的數字,今天新增的融資要等晚上公布;"
                  "只抓今天跌停內會破底的股票的報價。"
                  if live_mode else "現在不是盤中,顯示的是資料日收盤的結果;開盤後這裡會自動改成即時。")
               + "這是觀察名單,不是買賣訊號——破底爆量可能是斷頭賣壓出清,也可能才剛開始跌。"
               "家規照舊:不接刀、爆量後禁入、大盤燈號 🔴 時禁開新倉。"
               "名單每晚排程重建;白天想重建:本機跑 `python margin_break.py`。")


def _trading_now() -> bool:
    t = now_tw()
    return t.weekday() < 5 and "08:59" <= f"{t:%H:%M}" <= "13:32"


@st.fragment(run_every="60s")   # 永遠心跳:開盤前掛著,09:00 自動轉 LIVE
def _live():
    live = _trading_now()
    # ── 盤中:抓一輪快照(每分鐘一筆,重複呼叫同分鐘不重寫) ──
    if live:
        try:
            RT.record()
        except Exception:
            pass

    day = RT.load_day()
    tot, per_ts = (RT.group_flows(day) if not day.empty
                   else (pd.DataFrame(), pd.DataFrame()))

    # ── ① 市場脈動 ──
    idx = RT.indices()
    c = st.columns(5)
    for i, (name, (px_, pct)) in enumerate(idx.items()):
        c[i].metric(name, f"{px_:,.0f}", f"{pct:+.2f}%",
                    delta_color="inverse")        # 台股紅漲:inverse 讓 + 顯紅
    fx = RT.usdtwd()
    if fx:
        c[2].metric("台幣(USD/TWD)", f"{fx[0]:.3f}",
                    f"{fx[1]:+.2f}% {'貶' if fx[1] > 0 else '升'}",
                    delta_color="inverse")        # 貶值顯紅(出口甜、資金流出訊號)
    if len(tot):
        net, amt = tot["淨流入"].sum(), tot["總成交"].sum()
        c[3].metric("宇宙資金流(億)", f"{amt:,.0f} 成交",
                    f"{net:+,.1f} 淨流", delta_color="inverse")
    c[4].metric("模式", "🔴 LIVE 60s" if live else "⏸ 收盤快照",
                f"{now_tw():%H:%M:%S}", delta_color="off")

    mb = _mb_data()
    _mb_line(mb)

    if day.empty:
        st.info("還沒有今日快照——開盤(09:00)後這頁會自動每分鐘累積。"
                "掛著不用動,像看 Shioaji 的盤一樣。")
        _mb_block(mb)
        return
    ddate = day.attrs.get("date", "")
    if ddate and ddate != f"{now_tw():%Y%m%d}":
        c[4].metric("資料日", f"{ddate[4:6]}/{ddate[6:]}", "最近交易日", delta_color="off")
    if tot.empty:
        st.info("快照已開始,等前兩輪取得增量後出圖(約 2 分鐘)。")
        _mb_block(mb)
        return

    # ── ②+③ 族群資金流向泡泡圖|累計淨流排行 ──
    L, R = st.columns([3, 2])
    bub = tot.dropna(subset=["漲跌%"]).copy()
    sz = bub["總成交"].clip(lower=0.1) ** 0.5
    sz = 14 + 40 * (sz - sz.min()) / max(float(sz.max() - sz.min()), 1e-9)
    # 標籤只給成交額前 12 大(全標會疊成一團);其餘 hover 看
    big = set(bub.nlargest(12, "總成交")["group"])
    figb = go.Figure(go.Scatter(
        x=bub["淨流入"], y=bub["漲跌%"], mode="markers+text",
        hovertext=bub["group"],
        text=[g if g in big else "" for g in bub["group"]],
        textposition="top center",
        textfont=dict(size=10, color=T.MUTED),
        marker=dict(size=sz, opacity=.8, line=dict(width=1, color=T.CARD),
                    color=[T.RED if v >= 0 else T.GREEN for v in bub["淨流入"]]),
        customdata=bub["總成交"],
        hovertemplate="%{hovertext}<br>淨流入 %{x:+.2f} 億|漲跌中位 %{y:+.2f}%|"
                      "成交 %{customdata:,.1f} 億<extra></extra>"))
    figb.add_vline(x=0, line_color=T.GRID, line_width=1)
    figb.add_hline(y=0, line_color=T.GRID, line_width=1)
    figb.update_layout(height=460, margin=dict(l=10, r=10, t=36, b=10),
                       title="族群資金流向(泡泡=成交額)",
                       xaxis_title="累計淨流入(億)", yaxis_title="漲跌%(成分中位)")
    L.plotly_chart(figb, use_container_width=True)

    # 箭頭=跟前一分鐘比(最後一輪快照的增量方向;小於門檻視為持平)
    def _arrow(d, dead):
        return "▲" if d > dead else ("▼" if d < -dead else "–")

    # 防呆:長駐進程熱載入時 rt_flow 模組可能還是舊版(沒算 Δ1分)→ 頁面自己補算
    if "Δ1分" not in tot.columns and len(per_ts):
        d1g = per_ts[per_ts["ts"] == per_ts["ts"].max()].set_index("group")["flow"] / 1e4
        tot["Δ1分"] = d1g.reindex(tot["group"]).fillna(0).values

    tot_s = tot.sort_values("淨流入")
    figr = go.Figure(go.Bar(
        x=tot_s["淨流入"], y=tot_s["group"], orientation="h",
        marker_color=[T.RED if v >= 0 else T.GREEN for v in tot_s["淨流入"]],
        text=[f"{v:+.1f} {_arrow(d, .02)}"
              for v, d in zip(tot_s["淨流入"], tot_s.get("Δ1分", pd.Series(0, index=tot_s.index)))],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="%{y}<br>淨流入 %{x:+.2f} 億<extra></extra>"))
    figr.update_layout(height=460, margin=dict(l=10, r=60, t=36, b=10),
                       title="累計淨流入排行(億)",
                       xaxis=dict(range=[float(tot_s["淨流入"].min()) * 1.35 - .5,
                                         float(tot_s["淨流入"].max()) * 1.35 + .5]),
                       yaxis=dict(tickfont=dict(size=10)))
    R.plotly_chart(figr, use_container_width=True)

    # ── ④ 產業全景 treemap(面積=成交額、顏色=漲跌%) ──
    alls = RT.all_stocks(day)
    tm = alls.dropna(subset=["族群"]).query("成交額 > 0").copy()
    if len(tm):
        tm["名稱"] = tm["名稱"].fillna(tm["代號"])
        tm["標籤"] = [f"{n}<br>{p:+.1f}%" for n, p in zip(tm["名稱"], tm["漲跌%"])]
        mid = "#2A3A55" if T.MODE == "dark" else "#E7EAF0"
        figt = px.treemap(tm, path=["族群", "標籤"], values="成交額", color="漲跌%",
                          color_continuous_scale=[T.GREEN, mid, T.RED],
                          range_color=[-5, 5], color_continuous_midpoint=0)
        figt.update_traces(marker_line_width=1, marker_line_color=T.DARK,
                           textfont=dict(size=11),
                           hovertemplate="%{id}<br>成交 %{value:,.0f} 萬<extra></extra>")
        figt.update_layout(height=560, margin=dict(l=4, r=4, t=36, b=4),
                           title="產業全景(面積=成交額、紅漲綠跌)",
                           coloraxis_showscale=False)
        st.plotly_chart(figt, use_container_width=True)

    # ── 走勢:每個族群一格,看「淨流占成交額的百分比」怎麼走 ──
    # 2026-11-20 使用者:「改%數,要不然根本看不懂;分族群,有的差異太多」
    # 原本全部族群畫在同一張、單位億元:晶圓代工一條 −400 億就把其他線全壓成平的。
    # 改法:①除以該族群自己的累積成交額(大小族群可以比)②一族群一格、縱軸各自獨立(看得出自己的走向)
    from plotly.subplots import make_subplots
    pt = per_ts.sort_values(["group", "ts"]).copy()
    if "amt" not in pt.columns:                 # 長駐進程的舊版 rt_flow 沒帶成交額 → 頁面自己補
        _m = RT.stock_flows(day).merge(RT.universe(), on="code")
        pt = (_m.groupby(["group", "ts"]).agg(flow=("flow", "sum"), amt=("amt", "sum"))
                .reset_index().sort_values(["group", "ts"]))
    pt["cum_flow"] = pt.groupby("group")["flow"].cumsum() / 1e4                 # 億
    pt["cum_amt"] = pt.groupby("group")["amt"].cumsum() / 1e4
    pt["淨流占比%"] = (pt["cum_flow"] / pt["cum_amt"].where(pt["cum_amt"] > 0) * 100).fillna(0)
    lastp = pt.groupby("group").tail(1).set_index("group")
    order = list(lastp.sort_values("淨流占比%", ascending=False).index)
    NC = 5
    NR = -(-len(order) // NC)
    fig2 = make_subplots(
        rows=NR, cols=NC, horizontal_spacing=0.035, vertical_spacing=min(0.09, 0.5 / max(NR, 1)),
        subplot_titles=[f"{g} {lastp.at[g, '淨流占比%']:+.0f}%({lastp.at[g, 'cum_flow']:+.1f} 億)" for g in order])
    for i, g in enumerate(order):
        s = pt[pt["group"] == g]
        col = T.RED if lastp.at[g, "淨流占比%"] >= 0 else T.GREEN
        r_, c_ = i // NC + 1, i % NC + 1
        fig2.add_scatter(x=s["ts"].str[:5], y=s["淨流占比%"], mode="lines", name=g, showlegend=False,
                         line=dict(width=2, color=col), customdata=s["cum_flow"],
                         hovertemplate=g + " %{x}<br>淨流占成交 %{y:+.1f}%|累積 %{customdata:+.1f} 億<extra></extra>",
                         row=r_, col=c_)
        lo, hi = float(s["淨流占比%"].min()), float(s["淨流占比%"].max())
        pad = max((hi - lo) * 0.25, 1.0)                    # 至少留 1 個百分點,免得整天沒動的被放大成鋸齒
        fig2.update_yaxes(range=[lo - pad, hi + pad], row=r_, col=c_)
        if lo - pad <= 0 <= hi + pad:
            fig2.add_hline(y=0, line_color=T.GRID, line_width=1, row=r_, col=c_)
    fig2.update_xaxes(nticks=3, tickfont=dict(size=9, color=T.MUTED), categoryorder="category ascending")
    fig2.update_yaxes(ticksuffix="%", nticks=4, tickfont=dict(size=9, color=T.MUTED))
    fig2.update_annotations(font=dict(size=11.5))
    fig2.update_layout(height=150 * NR + 70, margin=dict(l=10, r=10, t=64, b=10),
                       title="盤中累積淨流走勢(誰在一路吸金/失血)——每格一個族群,單位:占成交額 %")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("怎麼讀:每格是一個族群,標題是現在的數字,由吸金最多排到失血最多。"
               "百分比=這個族群今天的成交額裡,價格往上成交的減掉往下成交的,占多少"
               "(+100%=全部在漲的時候成交、−100%=全部在跌的時候成交)。"
               "每格縱軸各自獨立,看的是線往上還是往下;族群之間比大小看標題的數字。括號是累積淨流金額。")

    # ── 個股貢獻排行(買超/賣超金額) ──
    if len(alls):
        g1, g2 = st.columns(2)
        a = alls.copy()
        if "Δ1分" not in a.columns:          # 同上:舊模組防呆
            sf_ = RT.stock_flows(day)
            d1s = sf_[sf_["ts"] == sf_["ts"].max()].groupby("code")["flow"].sum()
            a["Δ1分"] = a["代號"].map(d1s).fillna(0)
        a["淨流入(億)"] = (a["淨流入"] / 1e4).round(2)
        a["成交額(億)"] = (a["成交額"] / 1e4).round(2)
        # 1分動向:跟前一分鐘比——▲持續流入 / ▼轉流出 / –持平(|增量|<50萬)
        d1 = a.get("Δ1分", pd.Series(0, index=a.index)).fillna(0)
        a["1分"] = [f"{_arrow(d, 50)} {d/1e4:+.2f}" if abs(d) >= 50 else "–"
                    for d in d1]
        cols = ["代號", "名稱", "族群", "最新", "漲跌%", "淨流入(億)", "1分", "成交額(億)"]
        cfg = {"漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
               "最新": st.column_config.NumberColumn(format="%.1f"),
               "1分": st.column_config.TextColumn("1分動向", help="跟前一分鐘快照比:"
                        "▲再流入 ▼轉流出(數字=該分鐘增量,億)")}
        g1.markdown("##### 🔴 淨流入最大(買超)")
        g1.dataframe(a.nlargest(10, "淨流入")[cols], hide_index=True,
                     use_container_width=True, column_config=cfg)
        g2.markdown("##### 🟢 淨流出最大(賣超)")
        g2.dataframe(a.nsmallest(10, "淨流入")[cols], hide_index=True,
                     use_container_width=True, column_config=cfg)

    # ── 盤中強勢股(當沖觀察池) ──
    st.markdown("#### 🎯 盤中強勢股(當沖觀察池)")
    ss = RT.strong_stocks(day)
    if live and len(ss):
        try:
            pushed = RT.strong_alert(ss)          # 駐留≥10分鐘 → LINE 一次/日
            for m in pushed:
                st.toast(m.splitlines()[0])
        except Exception:
            pass
    if len(ss):
        v = ss.head(12).copy()
        v["淨流"] = (v["淨流"] / 1e4).round(2)
        v["額"] = (v["額"] / 1e4).round(2)
        st.dataframe(
            v.rename(columns={"淨流": "淨流入(億)", "額": "成交額(億)"}),
            hide_index=True, use_container_width=True,
            column_config={
                "漲%": st.column_config.NumberColumn(format="%+.2f%%"),
                "距漲停%": st.column_config.NumberColumn(format="%.1f%%"),
                "量比": st.column_config.NumberColumn(format="%.1f"),
                "買氣": st.column_config.NumberColumn(format="%+.2f"),
                "距日高%": st.column_config.NumberColumn(format="%+.2f%%"),
                "最新": st.column_config.NumberColumn(format="%.1f"),
                "強勢分": st.column_config.ProgressColumn(min_value=0, max_value=100,
                                                       format="%.0f"),
            })
        st.caption("強勢分=漲幅35%+量比25%+買氣20%+站均價10%+貼日高10(池門檻:上漲、"
                   "成交額≥3000萬、距漲停≥2%——漲停/準漲停追不進也沒肉,不進池)。量比=今日累積量÷(5日均量×U型時段曲線);買氣=淨流入/成交額。"
                   "⚠ 家內回測(6-10月、1339筆、含當沖成本0.435%):開盤買收盤賣整體勝率僅44.5%、"
                   "中位數-0.43%;唯一正期望組是「開盤跳空1~3%」(勝率52.1%、平均+0.58%),"
                   "跳空>3%追高無肉。這是觀察池不是買單;風險燈🔴時禁開新倉。")
    else:
        st.info("強勢池還沒有符合門檻的標的(上漲+成交額≥3000萬)。")

    # ── 維持率破底 × 爆量(全市場有融資的股票,不限族群表) ──
    _mb_block(mb)

    # ── 個股明細 ──
    g1, g2 = st.columns([1, 3])
    pick = g1.selectbox("看族群成分", list(tot.sort_values("淨流入", ascending=False)["group"]))
    tbl = RT.stock_table(day, pick)
    if len(tbl):
        tbl["成交額"] = (tbl["成交額"] / 1e4).round(2)
        tbl["淨流入"] = (tbl["淨流入"] / 1e4).round(2)
        g2.dataframe(tbl.rename(columns={"成交額": "成交額(億)", "淨流入": "淨流入(億)"}),
                     hide_index=True, use_container_width=True,
                     column_config={"漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                                    "最新": st.column_config.NumberColumn(format="%.1f")})
    st.caption("方法:每分鐘快照的成交量增量×價格,漲判流入、跌判流出(平盤與昨收比)——"
               "推估值,非逐筆內外盤。族群相對排序是重點;一檔多族群會分別計入"
               "(僅 treemap/個股貢獻取第一族群,避免面積重複)。"
               "資料源:證交所 MIS(上市+上櫃),免費、約 5 秒延遲。")


_live()

st.divider()
st.page_link("pages/39_強勢資金.py", label="💪 收盤後看「強勢資金」(成交注意力,含隔日沖雷達)")
st.page_link("pages/16_資金流向日誌.py", label="💸 盤後資金流向日誌(三大法人版)")

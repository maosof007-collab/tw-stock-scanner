# -*- coding: utf-8 -*-
"""
ui_mini_war.py — 迷你戰情共用元件(2026-10-13)
=================================================================
點表格列→同頁展開 K線+財務+籌碼速讀,免跳頁;深看再進完整戰情室(頁27)。
用法:
    sel_df = mini_war_table(df, code_col="代號", key="xxx", extras=["狀態","A位階"])
表格自帶單列選取;選中時表格收合為摺疊列、面板展開在上方。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent


def render_panel(code: str, name: str, extra_rows: list[tuple[str, str]] | None = None,
                 key: str = "mw") -> None:
    """K線(左)+速讀欄(右)。extra_rows=[(label, value), ...] 顯示在右欄最上面。"""
    st.markdown(f"## 🎯 {name} {code} 迷你戰情")
    cL, cR = st.columns([2, 1])
    with cL:
        try:
            import plotly.graph_objects as go
            for suf in (".TW.csv", ".TWO.csv"):
                p = ROOT / "data" / f"{code}{suf}"
                if p.exists():
                    px = pd.read_csv(p).dropna(subset=["Close"]).tail(120)
                    fig = go.Figure(go.Candlestick(
                        x=px["Date"], open=px["Open"], high=px["High"],
                        low=px["Low"], close=px["Close"],
                        increasing_line_color="#e5544a", decreasing_line_color="#3fae6a"))
                    fig.update_layout(height=320, margin=dict(l=0, r=0, t=8, b=0),
                                      xaxis_rangeslider_visible=False,
                                      paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)")
                    fig.update_xaxes(type="category", nticks=8)
                    st.plotly_chart(fig, use_container_width=True, key=f"{key}_k")
                    break
            else:
                st.caption("無價格資料(興櫃或未入庫)。")
        except Exception as e:
            st.caption(f"K線載入失敗:{e}")
    with cR:
        for lbl, val in (extra_rows or [])[:4]:
            st.metric(lbl, val)
        try:
            fin = pd.read_csv(ROOT / "data" / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
            q = fin[fin["code"] == code].tail(1)
            if len(q):
                q = q.iloc[0]
                st.caption(f"最新季:毛利 {q['毛利率%']}%|營益 {q['營益率%']}%|EPS {q['EPS']}")
        except Exception:
            pass
        try:
            rv = pd.read_csv(ROOT / "data" / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
            m = rv[rv["code"] == code].tail(3)
            if len(m):
                st.caption("月營收YoY:" + " → ".join(
                    f"{str(r['ym'])[5:]}月 {r['yoy%']:+.0f}%" for _, r in m.iterrows()))
        except Exception:
            pass
        try:
            ins = pd.read_csv(ROOT / "data" / "institutional" / f"{code}_inst.csv")
            fi = pd.to_numeric(ins.iloc[:, 4], errors="coerce")
            st.caption(f"外資20日:買超 {int((fi.tail(20) > 0).sum())} 天,"
                       f"累計 {fi.tail(20).sum() / 1000:+,.0f} 張")
        except Exception:
            pass
        if st.button("🎯 開完整戰情室", key=f"{key}_war", type="primary"):
            st.session_state["war_code"] = code
            st.switch_page("pages/27_個股戰情室.py")


def mini_war_table(df: pd.DataFrame, code_col: str = "代號", name_col: str = "名稱",
                   key: str = "mw", height: int = 480,
                   extras: list[str] | None = None,
                   collapse_label: str = "📋 名單(點開換股;取消勾選=回全表)") -> None:
    """表格+單列選取+迷你戰情一條龍。extras=要放進右欄的欄位名。"""
    if df.empty:
        st.info("無資料。")
        return
    df = df.reset_index(drop=True)
    wkey = f"{key}_table"
    prev = st.session_state.get(wkey, {})
    prev_rows = (prev.get("selection", {}).get("rows", []) if isinstance(prev, dict)
                 else getattr(getattr(prev, "selection", None), "rows", []) or [])
    panel = st.container()
    if prev_rows:
        with st.expander(collapse_label, expanded=False):
            sel = st.dataframe(df, hide_index=True, width="stretch", height=height,
                               on_select="rerun", selection_mode="single-row", key=wkey)
    else:
        st.caption("👆 點每列最左邊的小圓圈 → 表格收合,迷你戰情展開")
        sel = st.dataframe(df, hide_index=True, width="stretch", height=height,
                           on_select="rerun", selection_mode="single-row", key=wkey)
    rows = (sel.get("selection", {}).get("rows", []) if isinstance(sel, dict)
            else sel.selection.rows)
    if rows:
        r = df.iloc[rows[0]]
        code = str(r[code_col])
        name = str(r.get(name_col, "")) if name_col in df.columns else ""
        extra_rows = [(c, str(r[c])) for c in (extras or []) if c in df.columns and str(r[c]).strip()]
        with panel:
            render_panel(code, name, extra_rows, key=key)

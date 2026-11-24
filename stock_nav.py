# -*- coding: utf-8 -*-
"""stock_nav.py — 個股工作列:一檔股票的各個細節頁排成同一排,代號輸入一次、走到哪帶到哪。
2026-11-24 使用者(看著首頁「③ 研究動線」的八個入口):「可以整合了吧 太亂了」。
做法:不把八頁併成一支大程式(每頁各有自己的模組與快取,硬併風險高),而是讓它們共用同一個「目前在看哪一檔」:
  cur_code()      讀:網址 ?code= 優先,其次這次連線上次看的那一檔,最後才是各頁自己的預設值
  set_cur_code()  寫:每頁解析出代號後呼叫,下一頁就會帶著;同時把網址的 ?code= 改成同一檔
                  (不改的話,從 ?code=6425 進來再改打 2330,工作列會被網址蓋回 6425)
  sync_widget()   有 key 的輸入框要在建立之前呼叫,把目前代號塞進去(這種輸入框不能再給 value=,否則 Streamlit 會警告)
  bar()           畫那一排分頁;目前所在的那一頁反白不能點
只動 session_state 和網址參數,不讀檔、不發請求。
"""
from __future__ import annotations

import streamlit as st

KEY = "cur_code"
PAGES = [("總覽", "pages/48_個股.py"), ("快照", "pages/28_公司快照.py"), ("體質", "pages/29_財務九宮格.py"),
         ("估值", "pages/38_估值前瞻.py"), ("戰情室", "pages/27_個股戰情室.py"), ("營收預測", "pages/19_月營收預測.py"),
         ("券商觀點", "pages/35_券商觀點.py"), ("研究中心", "pages/13_個股法人報告.py"), ("海報", "pages/33_財經報.py")]


def _resolve(raw: str) -> tuple[str | None, str | None]:
    try:
        from symbols import resolve
        return resolve(str(raw).strip())
    except Exception:
        return None, None


def cur_code(default: str = "2330") -> str:
    q = st.query_params.get("code")
    if q:
        c, _ = _resolve(q)
        if c:
            st.session_state[KEY] = c
    return st.session_state.get(KEY, default)


def set_cur_code(raw: str) -> None:
    c, _ = _resolve(raw) if raw else (None, None)
    if c:
        st.session_state[KEY] = c
        try:
            if st.query_params.get("code") != c:
                st.query_params["code"] = c
        except Exception:
            pass


def sync_widget(key: str, default: str = "") -> None:
    c = cur_code("")
    if c and st.session_state.get("_sn_" + key) != c:
        st.session_state[key] = c
        st.session_state["_sn_" + key] = c
    elif key not in st.session_state and default:
        st.session_state[key] = default


def bar(active: str = "", widget_key: str = "") -> None:
    if widget_key and st.session_state.get(widget_key):
        set_cur_code(st.session_state[widget_key])
    code = cur_code("")
    name = (_resolve(code)[1] or "") if code else ""
    cols = st.columns([2.4] + [1] * len(PAGES))
    cols[0].markdown(f'<div style="font-weight:900;font-size:1.02rem;padding-top:6px;white-space:nowrap">🔎 {code} {name}</div>' if code
                     else '<div style="padding-top:6px;opacity:.7">🔎 還沒選股票</div>', unsafe_allow_html=True)
    for c, (lab, pg) in zip(cols[1:], PAGES):
        c.page_link(pg, label=f"● {lab}" if lab == active else lab, disabled=(lab == active))

# -*- coding: utf-8 -*-
"""
pages/35_券商觀點.py — 券商觀點總覽(旺來站 222 檔投顧觀點彙整)
=================================================================
回答「我怎麼知道哪些有券商觀點?」:全站索引一表看完——最新觀點日期、
是否已入庫、我們抓取的時間;點任一檔直接讀全文。run_daily 每日增量(追蹤股)。
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="券商觀點", page_icon="🗂️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("券商觀點總覽", "ADVISORY VIEWS", "🗂️")

import advisory_hub as ah
from twtime import now_tw

IDX = ah.DIR / "_index.json"


@st.cache_data(ttl=3600, show_spinner="更新站上索引…")
def _index(ver: int = 1) -> pd.DataFrame:
    import json, time
    if not IDX.exists() or time.time() - IDX.stat().st_mtime > 3600 * 8:
        ah.fetch_index()
    rows = []
    for s in json.loads(IDX.read_text(encoding="utf-8")):
        c = s.get("code")
        if not c:
            continue
        p = ah.DIR / f"{c}.txt"
        rows.append({"代碼": c, "名稱": s.get("name", ""),
                     "最新觀點": s.get("rec", ""), "份數": max(len(s.get("files", [])) - 1, 0),
                     "已入庫": "✅" if p.exists() else "",
                     "抓取時間": datetime.fromtimestamp(p.stat().st_mtime).strftime("%m/%d %H:%M")
                                 if p.exists() else ""})
    df = pd.DataFrame(rows).sort_values("最新觀點", ascending=False)
    return df


c1, c2, c3 = st.columns([1, 1, 2])
if c1.button("🔄 重抓索引+追蹤股", help="索引全更新;追蹤股觀點增量(rec 沒變跳過)"):
    _index.clear()
    with st.spinner("抓取中…"):
        ah.fetch_index(); n = ah.refresh()
    st.success(f"完成:追蹤股更新 {n} 檔"); st.rerun()

df = _index()
today = f"{now_tw():%Y-%m-%d}"
df["🆕"] = df["最新觀點"].map(lambda d: "🔥" if str(d) >= f"{now_tw().date() - pd.Timedelta(days=3):%Y-%m-%d}" else "")
try:
    from fundamentals import tracked_codes
    _tr = set(tracked_codes())
    df["追蹤"] = df["代碼"].map(lambda c: "💼" if c in _tr else "")
except Exception:
    df["追蹤"] = ""

m1, m2, m3, m4 = st.columns(4)
m1.metric("站上有觀點", len(df))
m2.metric("近3日有新觀點", int((df["🆕"] == "🔥").sum()))
m3.metric("已入庫", int((df["已入庫"] == "✅").sum()))
m4.metric("追蹤股覆蓋", int((df["追蹤"] == "💼").sum()))

st.caption("來源:旺來台股情報站(**公開新聞整理摘要,非券商原始報告**);"
           "「最新觀點」=站方該檔最後收錄日;「抓取時間」=本系統入庫時間。"
           "run_daily 每日自動增量追蹤股;其他檔點下方檢視時自動補抓。")

only = st.radio("顯示", ["全部", "🔥 近3日有新觀點", "💼 追蹤股"], horizontal=True)
show = df if only == "全部" else df[df["🆕"] == "🔥"] if "🔥" in only else df[df["追蹤"] == "💼"]
st.dataframe(show[["🆕", "追蹤", "代碼", "名稱", "最新觀點", "份數", "已入庫", "抓取時間"]],
             hide_index=True, width="stretch", height=420)

# ── 點開讀全文 ──────────────────────────────
st.markdown("### 📖 讀某一檔的觀點彙整")
_q = st.text_input("代碼或名稱", placeholder="例:3042 或 晶技", key="adv_q")
if _q.strip():
    from symbols import resolve as _rs
    code, nm = _rs(_q.strip())
    if not code:
        st.warning("解析失敗。")
    elif code not in set(df["代碼"]):
        st.info(f"{nm or code} 不在站上收錄名單(共 {len(df)} 檔)——可用頁23 法說庫或快分析其他素材。")
    else:
        with st.spinner("載入(未入庫會自動抓)…"):
            txt = ah.latest_text(code, cap=20000)
        if txt:
            st.markdown(f"#### {nm} {code}")
            st.text_area("觀點彙整全文(含券商/日期/來源標註)", txt, height=480, label_visibility="collapsed")
            st.caption("引用鐵律:標券商與日期;目標價以原始報告為準。此素材已自動餵入 ⚡快分析(頁27)。")
        else:
            st.warning("抓取失敗,稍後再試。")

st.caption(f"<span style='color:{MUTED}'>素材分三層:法說簡報(公司口徑,頁23)>投顧觀點彙整(本頁)"
           f">新聞情緒(頁5)。層級越高,引用優先權越高。</span>", unsafe_allow_html=True)

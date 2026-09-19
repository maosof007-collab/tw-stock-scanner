"""頁26 — 每日晨報(07:15 自動產生):今日晨報+近日回顧,一頁讀完開盤前該知道的。"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="每日晨報", page_icon="🌅", layout="wide")

from analyst_report import list_articles, read_article
from twtime import now_tw

st.title("🌅 每日晨報")

briefs = [a for a in list_articles() if a.get("mode") == "晨報"]
if not briefs:
    st.info("尚無晨報——平日 07:15 排程自動產生(引擎需在線);雲端由 git 同步。")
    st.stop()

today = f"{now_tw():%Y-%m-%d}"
latest = briefs[0]
is_today = str(latest.get("date", ""))[:10] == today
if not is_today:
    st.warning(f"今日晨報尚未產生(最新一份:{str(latest.get('date',''))[:10]})——"
               "平日 07:15 自動跑;假日無晨報。")

tab_today, tab_hist = st.tabs(["📰 最新一份", "🗓️ 近日回顧"])
with tab_today:
    st.caption(f"{latest.get('date','')}|{latest['title']}")
    st.markdown(read_article(latest["file"]))
with tab_hist:
    opts = briefs[1:11]
    if not opts:
        st.info("無更早的晨報。")
    else:
        sel = st.selectbox("選擇日期", range(len(opts)),
                           format_func=lambda i: f"{str(opts[i].get('date',''))[:10]}|{opts[i]['title'][:40]}")
        st.markdown(read_article(opts[sel]["file"]))
st.caption("盤前資訊集鐵律:新聞窗截至當日 08:30;盤後補產生者有橫幅標註。非投資建議。")

"""頁23 — 法說行事曆:照時間排的法說時間表+行情醞釀度+持倉標記。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="法說行事曆", page_icon="🎤", layout="wide")

import conf_calendar as _cc
_cc = importlib.reload(_cc)          # 迭代中模組:無條件重載

st.title("🎤 法說行事曆")
st.caption("MOPS 法人說明會一覽(上市+上櫃,本月+下月),**照時間排**。"
           "「近20日%」=法說前行情醞釀度——行情常走在法說前;法說當天常是資訊落地日。")


@st.cache_data(ttl=3600, show_spinner="抓取法說行事曆…")
def _up(ver: int = 1):
    return _cc.upcoming(days=45)


@st.cache_data(ttl=3600)
def _done(ver: int = 1):
    return _cc.just_done(days=10)


up = _up()
if up.empty:
    st.info("暫無資料(MOPS 可能忙線,稍後重整)。")
    st.stop()

# 持倉/追蹤標記
_watch = set()
try:
    j = pd.read_csv(Path(__file__).parent.parent / "data" / "decision_journal.csv", dtype=str)
    _watch = set(j[j["status"] == "open"]["code"])
except Exception:
    pass
up["★"] = up["code"].map(lambda c: "💼" if c in _watch else "")

today = up["date"].min()
n_today = (up["date"] == f"{_cc.now_tw():%Y-%m-%d}").sum()
c1, c2, c3 = st.columns(3)
c1.metric("未來45日場次", len(up))
c2.metric("今日場次", int(n_today))
c3.metric("持倉相關", int((up["★"] == "💼").sum()))

only_watch = st.toggle("只看持倉/日誌相關", value=False)
show = up[up["★"] == "💼"] if only_watch else up
st.dataframe(
    show[["date", "time", "code", "name", "★", "market", "近20日%", "summary"]]
    .rename(columns={"date": "日期", "time": "時間", "code": "代號", "name": "名稱",
                     "market": "市場", "summary": "擇要"}),
    hide_index=True, width="stretch", height=560)
st.caption("判讀:近20日已大漲+法說=利多落地風險(自動化展-3.4%同款規律);近20日平靜+法說=資訊突襲窗。"
           "重點場次聽完用「法說筆記」存進系統(頁13),之後所有報告自動引用。")

with st.expander(f"🗓️ 剛開完(近10日,{len(_done())} 場)——簡報已上 MOPS"):
    d = _done()
    if not d.empty:
        st.dataframe(d[["date", "code", "name", "market", "summary"]]
                     .rename(columns={"date": "日期", "code": "代號", "name": "名稱",
                                      "market": "市場", "summary": "擇要"}),
                     hide_index=True, width="stretch")
        st.caption("簡報下載:MOPS →「法人說明會一覽表」→ 該公司列。查證家規:先讀簡報再讓任何人的解讀入庫。")

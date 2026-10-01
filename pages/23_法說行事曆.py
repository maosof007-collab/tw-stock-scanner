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

# ── 📚 法說簡報庫(2026-10-01 起:回答「我怎麼知道法說都抓了?」)──
st.markdown("---")
st.markdown("### 📚 法說簡報庫")
import concall as _con
from symbols import resolve as _rs23

_decks = sorted(_con.DIR.glob("*.pdf"), key=lambda p: p.stem.split("_")[1], reverse=True)
_rows = []
for _p in _decks:
    _c, _, _d = _p.stem.partition("_")
    _rows.append({"代號": _c, "名稱": _rs23(_c)[1] or "", "法說日期": f"{_d[:4]}/{_d[4:6]}/{_d[6:]}",
                  "追蹤股": ""})
try:
    from fundamentals import tracked_codes as _tc23
    _tracked23 = set(_tc23())
    for _r in _rows:
        _r["追蹤股"] = "✅" if _r["代號"] in _tracked23 else ""
except Exception:
    _tracked23 = set()
st.caption(f"庫存 **{len(_rows)}** 份簡報|自動抓取範圍=追蹤股({len(_tracked23)} 檔,持倉+ETF+追蹤清單),"
           "run_daily 每日增量;**非追蹤股要用下方手動補抓**。來源:finmoconf→MOPS 原始 PDF。")
_cq, _cb = st.columns([3, 1])
_qin = _cq.text_input("補抓任意代碼/名稱的最新法說", placeholder="例:3701 或 大眾控", key="con_fetch_q")
if _cb.button("⬇️ 抓取", key="con_fetch_btn") and _qin.strip():
    _code23, _nm23 = _rs23(_qin.strip())
    if not _code23:
        st.warning("代碼/名稱解析失敗。")
    else:
        with st.spinner(f"向 finmoconf/MOPS 抓 {_nm23 or _code23} 最新法說…"):
            _pp = _con.fetch_latest(_code23)
        if _pp:
            st.success(f"✅ {_nm23}{_code23}:{_pp.name} 已入庫(快分析/財經報會自動引用)")
            st.rerun()
        else:
            st.warning(f"{_nm23 or _code23} 在 finmoconf 查無法說簡報(公司可能未開或未上傳 MOPS)。")
_dfd = pd.DataFrame(_rows)
if not _dfd.empty:
    st.dataframe(_dfd, hide_index=True, width="stretch", height=380)

"""
頁面19:月營收預測(誰這個月會開得不錯)
================================
雙模型(YoY動能外推 × 歷年季節比)全市場預測下月營收,
疊籌碼偷跑層(大戶週Δ/法人5日);榜單自動入預實追蹤,
10日開獎自動對答案 → 模型每月累積命中率戰績。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="月營收預測", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("月營收預測", "MONTHLY REVENUE FORECAST", "🔮")

import importlib
import monthly_forecast as _mf
if not hasattr(_mf, "forecast_month"):
    _mf = importlib.reload(_mf)

from twtime import now_tw
_now = now_tw()
# 12日前:上月營收未公布完 → 預測上月;之後 → 預測本月
if _now.day <= 12:
    _y, _m = (_now.year, _now.month - 1) if _now.month > 1 else (_now.year - 1, 12)
else:
    _y, _m = _now.year, _now.month
target = st.text_input("預測月份", value=f"{_y}-{_m:02d}", key="mf_target")


@st.cache_data(ttl=6 * 3600, show_spinner="全市場雙模型預測中(首次約60秒)…")
def _run(t):
    return _mf.forecast_month(t)


df = _run(target.strip())
if df.empty:
    st.info("資料不足(需目標月前至少3個月營收)")
    st.stop()

st.caption(f"樣本 {len(df)} 檔(均量≥500張)。模型A=去年同月×(1+近3月YoY中位);"
           f"模型B=上月實際×歷年同月季節比(2019-2025中位);預測=兩法平均,"
           f"「兩法一致✅」=差距<10%。⚠️ 動能外推看不見產能爬坡與一次性事件;"
           f"YoY>300%多為併購/基期事件另行查證。")

t1, t2, t3 = st.tabs(["🏆 看好榜", "🕵️ 籌碼偷跑榜", "📊 模型戰績"])

with t1:
    show = df[(df["兩法一致"] != "❌") & (df["預測YoY%"] < 300)].head(30)
    st.dataframe(show, width="stretch", hide_index=True, height=560)
    st.caption("預測YoY 高+兩法一致=開得不錯機率高;「加速度」負值=動能在降溫,開獎日易失望。")

with t2:
    hot = df[(df["預測YoY%"] > 30) & (df["預測YoY%"] < 300)]
    if "大戶週Δpp" in hot.columns:
        hot = hot[(hot["大戶週Δpp"].fillna(0) >= 0.5) | (hot["法人5日(張)"].fillna(0) >= 500)]
    st.dataframe(hot.head(30), width="stretch", hide_index=True, height=520)
    st.caption("預測YoY>30% 且(大戶週Δ≥+0.5pp 或 法人5日≥+500張)——"
               "不只模型說會開好,而且**已經有人先卡位**。開獎行情可信度較高。")

with t3:
    from model_track import check_all
    tr = check_all()
    mine = tr[tr["備註"].astype(str).str.startswith("月營收預測模型")]
    if mine.empty:
        st.info("尚無戰績——榜單每月自動入預實追蹤,10日開獎後這裡顯示命中率")
    else:
        done = mine[mine["燈號"].isin(["🟢", "🟡", "🔴"])]
        if not done.empty:
            hit = (done["燈號"] == "🟢").mean() * 100
            st.metric("模型命中率(誤差±5%內)", f"{hit:.0f}%",
                      help=f"已開獎 {len(done)} 筆")
        st.dataframe(mine, width="stretch", hide_index=True, height=480)
    if st.button("📌 把本月榜前20寫入預實追蹤", key="mf_record"):
        n = _mf.record_top(df, target.strip())
        st.success(f"已寫入 {n} 筆,開獎自動對答案")

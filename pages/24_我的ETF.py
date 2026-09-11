"""頁24 — 我的ETF:自組模擬基金(00981A 概念),淨值 vs 大盤+候選池+改組日誌。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="我的ETF", page_icon="🧺", layout="wide")

import my_etf as _me
_me = importlib.reload(_me)          # 迭代中模組:無條件重載

st.title("🧺 我的 ETF")
st.caption("對標 00981A 的選股指紋(前300大×營收YoY>30%×題材集中×動能,top10佔67%)——"
           "但用**你系統的訊號**選:偷跑榜/權證佈局/體檢卡。改組全記錄,淨值天天對大盤。")

d = _me.load()
cons = pd.DataFrame(d["constituents"]) if d["constituents"] else pd.DataFrame(
    columns=["code", "name", "weight", "thesis"])

tab_hold, tab_pick, tab_log = st.tabs(["📊 淨值與持股", "🎯 候選池(系統訊號)", "📓 改組日誌"])

with tab_hold:
    nav = _me.nav_series()
    s = _me.stats(nav) if not nav.empty else {}
    if not s:
        if d["constituents"]:
            st.info("已建倉——淨值從明個交易日開始累積(今天是基期 100)。")
        nav = pd.DataFrame()
    if not nav.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("我的ETF報酬", f"{s['報酬%']:+.1f}%", f"{s['天數']}天", delta_color="off")
        c2.metric("同期大盤", f"{s['大盤%']:+.1f}%")
        c3.metric("超額", f"{s['超額pp']:+.1f}pp")
        c4.metric("最大回撤", f"{s['最大回撤%']:.1f}%")
        fig = go.Figure()
        fig.add_scatter(x=nav["date"], y=nav["我的ETF"], name="我的ETF",
                        line=dict(color="#00C2A8", width=2.5))
        fig.add_scatter(x=nav["date"], y=nav["大盤"], name="大盤",
                        line=dict(color="#888", width=1.5, dash="dot"))
        fig.update_layout(height=380, legend=dict(orientation="h", y=1.08),
                          margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("尚未建倉——用下方表格或「候選池」加入成分股。")

    st.markdown("#### 成分股(權重自動正規化為100%)")
    edit = st.data_editor(
        cons, num_rows="dynamic", hide_index=True, width="stretch",
        key="etf_editor",
        column_config={
            "code": st.column_config.TextColumn("代號"),
            "name": st.column_config.TextColumn("名稱"),
            "weight": st.column_config.NumberColumn("權重", format="%.1f"),
            "thesis": st.column_config.TextColumn("入選理由(像經理人一樣寫)", width="large"),
        })
    note = st.text_input("改組備註(寫進日誌)", key="etf_note")
    if st.button("💾 儲存/改組", type="primary"):
        rows = [r for r in edit.to_dict("records")
                if str(r.get("code", "")).strip() and float(r.get("weight") or 0) > 0]
        for r in rows:
            r["code"] = str(r["code"]).strip()
        _me.set_constituents(rows, note.strip())
        st.success(f"已儲存 {len(rows)} 檔(權重正規化)。")
        st.rerun()

    with st.expander("🆚 00981A top10 對照(2026-09-11)"):
        t10 = pd.DataFrame(_me.ETF_00981A_TOP10, columns=["代號", "名稱", "權重%"])
        mine = set(cons["code"].astype(str)) if not cons.empty else set()
        t10["我也有"] = t10["代號"].map(lambda c: "✅" if c in mine else "")
        st.dataframe(t10, hide_index=True, width="stretch")
        st.caption("它的指紋:top10 全是最新月營收YoY>30%的AI鏈大市值(中位+53.8%),不看散戶籌碼。"
                   "你的優勢=多三個它沒有的儀表:偷跑榜/權證資金流/體檢卡。")

with tab_pick:
    st.caption("候選=最新月營收YoY>30%(00981A指紋)∩ 權證資金🔵佈局/🔥湧入 ∩ 體檢卡紅燈數——"
               "紅燈≥2 照家規不進。挑中的到「淨值與持股」頁籤手動加入。")
    if st.button("🔎 掃描候選池"):
        with st.spinner("跑三訊號交集…"):
            cand = _me.candidates()
        st.dataframe(cand, hide_index=True, width="stretch")

with tab_log:
    if d["log"]:
        for e in reversed(d["log"][-20:]):
            st.markdown(f"**{e['date']}**|{e['note']}|{'、'.join(e['constituents'])}")
    else:
        st.info("尚無改組紀錄。")

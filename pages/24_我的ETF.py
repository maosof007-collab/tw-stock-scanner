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

with st.expander("❓ 怎麼用(三步)", expanded=False):
    st.markdown("""
1. **改持股**:在下方成分股表直接改——換股=把某列的代號/名稱/理由改掉;加股=最下面空白列輸入;
   刪股=選該列按 Delete。權重隨便填相對大小,儲存時會自動換算成合計 100%;
2. **按「💾 儲存持股變更」**:所有修改此刻才生效,並自動記一筆「改組日誌」(誰進誰出、哪天、為什麼)
   ——這就是「改組」的意思:像基金經理人調整持股,留下紀錄供日後檢討;
3. **每天只看兩個地方**:最上面的 🔔 換股提醒 + 績效對決圖。要不要動手,留到週六週檢視或每月10日再決定(系統憲法 L1)。
""")

d = _me.load()
cons = pd.DataFrame(d["constituents"]) if d["constituents"] else pd.DataFrame(
    columns=["code", "name", "weight", "thesis"])

tab_hold, tab_pick, tab_log = st.tabs(["📊 淨值與持股", "🎯 候選池(系統訊號)", "📓 改組日誌"])

with tab_hold:
    # ── 🔔 換股提醒(表現不好在最上面直接說)──
    try:
        _alerts = _me.swap_alerts()
        if _alerts:
            st.error("**🔔 換股提醒**\n\n" + "\n".join(f"- {a}" for a in _alerts))
    except Exception:
        pass
    # 圖永遠畫:比賽計分從建倉日起,但可切較長區間看四條線的歷史對照
    _rng = st.segmented_control("圖表區間", options=["建倉起(正式計分)", "近1月", "近3月"],
                                default="近1月", key="etf_rng")
    import pandas as _pd
    _since_map = {"建倉起(正式計分)": None,
                  "近1月": f"{_me.now_tw() - _pd.Timedelta(days=30):%Y-%m-%d}",
                  "近3月": f"{_me.now_tw() - _pd.Timedelta(days=90):%Y-%m-%d}"}
    nav = _me.nav_series(since=_since_map.get(_rng))
    s_official = _me.stats(_me.nav_series())        # 計分永遠用建倉起
    if s_official:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("我的ETF報酬(建倉起)", f"{s_official['報酬%']:+.1f}%",
                  f"{s_official['天數']}天", delta_color="off")
        c2.metric("同期大盤", f"{s_official['大盤%']:+.1f}%")
        c3.metric("超額", f"{s_official['超額pp']:+.1f}pp")
        c4.metric("最大回撤", f"{s_official['最大回撤%']:.1f}%")
    else:
        st.info("正式計分自建倉日(基期100)起,明個交易日出現第一筆;下圖先用較長區間看四條線對照。")

    if not nav.empty:
        st.markdown("#### 🏁 績效對決(基期 100,每天自動疊上)")
        fig = go.Figure()
        _styles = {"我的ETF": dict(color="#00C2A8", width=3),
                   "大盤": dict(color="#888", width=1.5, dash="dot"),
                   "0050": dict(color="#3B82F6", width=1.5),
                   "00981A": dict(color="#F59E0B", width=2)}
        for _ln, _st_ in _styles.items():
            if _ln in nav.columns:
                fig.add_scatter(x=nav["date"], y=nav[_ln], name=_ln, line=_st_)
        fig.update_layout(height=400, legend=dict(orientation="h", y=1.1),
                          margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, width="stretch")
        _last = nav.iloc[-1]
        _race = "|".join(f"{k} {_last[k]-100:+.1f}%" for k in _styles if k in nav.columns)
        st.caption(f"對決現況:{_race}(圖示區間自 {nav['date'].iloc[0]} 起;正式計分固定從建倉日)")
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
    # ── 💰 資金換算器:填總資金 → 權重換算成張/零股 ──
    with st.expander("💰 資金換算器(填多少錢,算每檔買幾張/幾股)", expanded=True):
        _cap_wan = st.number_input("總資金(萬元)", min_value=1.0, value=100.0, step=10.0,
                                   key="etf_capital")
        _cap = _cap_wan * 10000
        _rows = []
        _invested = 0.0
        for _r in edit.to_dict("records"):
            _code = str(_r.get("code", "")).strip()
            _w = float(_r.get("weight") or 0)
            if not _code or _w <= 0:
                continue
            _target = _cap * _w / 100
            if _code.upper() == "CASH":
                _rows.append({"代號": "CASH", "名稱": _r.get("name", "現金"),
                              "權重%": _w, "目標金額": round(_target),
                              "現價": None, "整張": None, "零股": None,
                              "實際投入": round(_target)})
                _invested += _target
                continue
            _px_ = _me._px(_code)
            if _px_ is None or _px_.empty:
                _rows.append({"代號": _code, "名稱": _r.get("name", ""),
                              "權重%": _w, "目標金額": round(_target),
                              "現價": None, "整張": None, "零股": None, "實際投入": 0})
                continue
            _p = float(_px_.iloc[-1])
            _lots = int(_target // (_p * 1000))
            _odd = int((_target - _lots * _p * 1000) // _p)
            _act = _lots * _p * 1000 + _odd * _p
            _invested += _act
            _rows.append({"代號": _code, "名稱": _r.get("name", ""),
                          "權重%": _w, "目標金額": round(_target),
                          "現價": round(_p, 1), "整張": _lots, "零股": _odd,
                          "實際投入": round(_act)})
        if _rows:
            _adf = pd.DataFrame(_rows)
            st.dataframe(_adf, hide_index=True, width="stretch",
                         column_config={
                             "目標金額": st.column_config.NumberColumn(format="%,d"),
                             "實際投入": st.column_config.NumberColumn(format="%,d")})
            _rest = _cap - _invested
            st.caption(f"總資金 {_cap:,.0f}|實際投入 {_invested:,.0f}"
                       f"|零頭餘額 {_rest:,.0f}(併入現金)。"
                       f"零股以收盤價估,盤中市價會有小差;高價股(光聖/大立光類)整張買不起就照零股欄下單。")

    note = st.text_input("改組備註(寫進日誌)", key="etf_note")
    if st.button("💾 儲存持股變更(=改組生效並寫日誌)", type="primary"):
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

"""
頁面2：研究報告瀏覽器(讀 SQLite 資料庫)
空庫 → 顯示引導;有報告 → 清單 + 精讀。底部附「新增報告」表單。
"""
import datetime as dt
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import data_provider as dp
import report_db as rdb
from ui_common import inject_css, THEME
from ui_theme import page_header

st.set_page_config(page_title="研究報告瀏覽器", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("研究報告瀏覽器", "RESEARCH REPORTS", "📑")
rdb.init_db()

total = rdb.count()

if total == 0:
    st.markdown("## 報告精讀")
    st.info("目前資料庫沒有任何報告。報告是「一篇篇加進來」的 —— "
            "用下方表單手動新增,或之後用 PDF 解析批次入庫。")
else:
    left, right = st.columns([1, 2.4])
    with left:
        st.markdown(f"### 最新報告　<span class='muted'>共 {total} 篇</span>",
                    unsafe_allow_html=True)
        kw = st.text_input("搜尋股號、券商、公司、主題", "")
        d1, d2 = st.columns(2)
        start = d1.date_input("起", value=None)
        end = d2.date_input("迄", value=None)
        reps = dp.get_reports(
            keyword=kw or None,
            start=start if isinstance(start, dt.date) else None,
            end=end if isinstance(end, dt.date) else None,
            limit=500)
        st.caption(f"符合 {len(reps)} 筆")
        if "sel_report_id" not in st.session_state and not reps.empty:
            st.session_state.sel_report_id = int(reps.iloc[0]["id"])
        for _, r in reps.iterrows():
            if st.button(f"{r['date']}　{r['ticker']} {r['name']}",
                         key=f"rp_{r['id']}", width="stretch"):
                st.session_state.sel_report_id = int(r["id"])
            st.markdown(f"<div class='muted'>{r['rtype']} · {r['broker']} · "
                        f"TWD {r['target_price']:.0f}</div>", unsafe_allow_html=True)
    with right:
        rid = st.session_state.get("sel_report_id")
        det = dp.get_report_detail(report_id=rid) if rid else None
        if not det:
            st.info("← 從左側選一份報告")
        else:
            st.markdown(f"## {det['name']}  ({det['ticker']} TT)")
            st.caption(f"{det['broker']} · {det['report_type']} · {det['date']}")
            h = st.columns(4)
            rcls = "pos" if det["rating"] == "買進" else "neg"
            for col, (l, v, c) in zip(h, [
                ("投資建議", det["rating"], rcls),
                ("收盤價", f"NT$ {det['close_price']}", ""),
                ("6個月目標價", f"NT$ {det['target_price']}", ""),
                ("產業", det["industry"] or "—", "")]):
                col.markdown(f"<div class='metric-card'><div class='l'>{l}</div>"
                             f"<div class='v {c}'>{v}</div></div>",
                             unsafe_allow_html=True)
            st.caption(f"本次報告：{det['report_basis']}")
            st.divider()
            cols = st.columns(2)
            with cols[0]:
                st.markdown("##### 交易資料")
                for k, v in (det["trade_data"] or {}).items():
                    st.markdown(f"<div style='display:flex;justify-content:space-between;"
                                f"padding:3px 0;border-bottom:1px solid {THEME['grid']}'>"
                                f"<span class='muted'>{k}</span><span>{v}</span></div>",
                                unsafe_allow_html=True)
            with cols[1]:
                st.markdown("##### 財務資料")
                for k, v in (det["financial_data"] or {}).items():
                    st.markdown(f"<div style='display:flex;justify-content:space-between;"
                                f"padding:3px 0;border-bottom:1px solid {THEME['grid']}'>"
                                f"<span class='muted'>{k}</span><span>{v}</span></div>",
                                unsafe_allow_html=True)
                if det["esg"]:
                    st.markdown("##### 永續評等")
                    for k, v in det["esg"].items():
                        st.markdown(f"<div style='display:flex;justify-content:space-between;"
                                    f"padding:3px 0;border-bottom:1px solid {THEME['grid']}'>"
                                    f"<span class='muted'>{k}</span><span>{v}</span></div>",
                                    unsafe_allow_html=True)

st.divider()
with st.expander("➕ 新增報告", expanded=(total == 0)):
    c = st.columns(4)
    tk = c[0].text_input("股號 *", placeholder="2006")
    nm = c[1].text_input("名稱", placeholder="東和鋼鐵")
    bk = c[2].text_input("券商", placeholder="永豐")
    rdate = c[3].date_input("報告日期 *", value=dt.date.today())
    c2 = st.columns(4)
    rating = c2[0].selectbox("投資建議", ["買進", "中立", "區間操作", "賣出"])
    close_p = c2[1].number_input("收盤價", min_value=0.0, value=0.0, step=0.1)
    target_p = c2[2].number_input("目標價", min_value=0.0, value=0.0, step=0.1)
    rtype = c2[3].text_input("報告類型", value="個股聚焦")
    if st.button("加入資料庫", type="primary"):
        if not tk:
            st.error("股號為必填")
        else:
            rid = dp.add_report({
                "ticker": tk.strip(), "name": nm.strip() or None,
                "broker": bk.strip() or None, "report_type": rtype.strip(),
                "report_date": rdate.isoformat(), "rating": rating,
                "close_price": close_p or None, "target_price": target_p or None,
                "title": f"{nm or tk} {rtype}",
            })
            st.success(f"已加入(id={rid})。重新整理即可在清單看到。")
            st.rerun()

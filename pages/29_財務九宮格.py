"""
pages/29_財務九宮格.py — 一屏九圖財務體質總覽(仿經典財報九宮格)
=================================================================
九格:①營收+利潤率 ②EPS本業/業外 ③月營收今昔 ④存貨/收現天數
     ⑤資本支出 ⑥負債比+現金流 ⑦營業現金流今昔 ⑧累計營收今昔 ⑨估值卡
資料:fin9.py(FinMind 三大報表)。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="財務九宮格", page_icon="🔲", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("財務九宮格", "9-GRID FUNDAMENTALS", "🔲")

D = ROOT / "data"
N_Q = 10          # 每格顯示最近幾季


@st.cache_data(ttl=3600, show_spinner="抓三大報表組九宮格…")
def _load(code: str) -> dict:
    import fin9
    return fin9.assemble(code)


def _name(code):
    try:
        sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        h = sl[sl["code"] == code]
        return h["name"].iloc[0] if not h.empty else code
    except Exception:
        return code


def _fig(height=225):
    f = go.Figure()
    f.update_layout(height=height, margin=dict(l=6, r=6, t=26, b=4),
                    legend=dict(orientation="h", y=1.18, font=dict(size=10)))
    f.update_xaxes(type="category")
    return f


c_in, c_lnk = st.columns([2, 2])
with c_in:
    code = st.text_input("個股代碼", value=st.query_params.get("code", "3042"),
                         max_chars=6).strip()
with c_lnk:
    st.page_link("pages/28_公司快照.py", label="🏢 公司快照(估值與EPS)")
if not code.isdigit():
    st.stop()

A = _load(code)
if "季別" not in A:
    st.warning("FinMind 抓不到財報(額度或代碼問題)——稍後再試。")
    st.stop()

lab = list(A["季別"][-N_Q:])
q = A["q"]

# ── 頭欄 ──
h = st.columns(6)
h[0].metric(f"{_name(code)} {code}", f"{A.get('close', '—')}")
h[1].metric("股本(億)", A.get("股本(億)", "—"))
h[2].metric("每股淨值", A.get("每股淨值", "—"))
h[3].metric("本業PE", A.get("本業PE", "—"))
if "負債比%" in A:
    h[4].metric("負債比", f"{A['負債比%'].dropna().iloc[-1]:.0f}%")
if "core_ratio%" in A:
    h[5].metric("本業比(最新季)", f"{A['core_ratio%'].dropna().iloc[-1]:.0f}%")

r1 = st.columns(3)
# ① 營收 + 毛利率/淨利率
with r1[0]:
    g = q.tail(N_Q)
    f = _fig()
    f.add_bar(x=lab, y=g["營收(億)"], name="營收(億)", marker_color="#3B82F6")
    f.add_scatter(x=lab, y=g["毛利率%"], name="毛利率", yaxis="y2", line=dict(color="#E5484D"))
    f.add_scatter(x=lab, y=g["淨利率%"], name="淨利率", yaxis="y2", line=dict(color="#8B5CF6"))
    f.update_layout(title=dict(text="營收與利潤率", font=dict(size=13)),
                    yaxis2=dict(overlaying="y", side="right", showgrid=False))
    st.plotly_chart(f, width="stretch")
# ② EPS 本業/業外
with r1[1]:
    if "eps_core" in A:
        f = _fig()
        f.add_bar(x=lab, y=A["eps_core"].tail(N_Q), name="本業EPS", marker_color="#2E9E5B")
        f.add_bar(x=lab, y=A["eps_other"].tail(N_Q), name="業外", marker_color="#A16207")
        f.add_scatter(x=lab, y=A["core_ratio%"].tail(N_Q), name="本業比%", yaxis="y2",
                      line=dict(color="#3B82F6", dash="dot"))
        f.update_layout(barmode="relative", title=dict(text="EPS 本業/業外分解", font=dict(size=13)),
                        yaxis2=dict(overlaying="y", side="right", range=[0, 130], showgrid=False))
        st.plotly_chart(f, width="stretch")
# ③ 月營收 今年 vs 去年
with r1[2]:
    mc = A.get("mon_cmp")
    if mc:
        f = _fig()
        f.add_scatter(x=mc["月"], y=mc["去年"], name=f"{mc['this_y']-1}", line=dict(color="#3B82F6"))
        f.add_scatter(x=mc["月"], y=mc["今年"], name=f"{mc['this_y']}", line=dict(color="#E5484D"))
        f.update_layout(title=dict(text="月營收(百萬):今年 vs 去年", font=dict(size=13)))
        st.plotly_chart(f, width="stretch")

r2 = st.columns(3)
# ④ 存貨/收現天數
with r2[0]:
    if "存貨天數" in A or "收現天數" in A:
        f = _fig()
        if "存貨天數" in A:
            f.add_scatter(x=lab, y=A["存貨天數"].tail(N_Q), name="存貨天數", line=dict(color="#E5484D"))
        if "收現天數" in A:
            f.add_scatter(x=lab, y=A["收現天數"].tail(N_Q), name="收現天數", line=dict(color="#3B82F6"))
        f.update_layout(title=dict(text="存貨/收現天數(愈低愈健康)", font=dict(size=13)))
        st.plotly_chart(f, width="stretch")
# ⑤ 資本支出
with r2[1]:
    if "資本支出" in A:
        f = _fig()
        f.add_bar(x=lab, y=A["資本支出"].tail(N_Q), name="資本支出(億)", marker_color="#3B82F6")
        f.update_layout(title=dict(text="資本支出(擴產強度)", font=dict(size=13)), showlegend=False)
        st.plotly_chart(f, width="stretch")
# ⑥ 負債比 + 營業/自由現金流
with r2[2]:
    if "營業現金流" in A:
        f = _fig()
        f.add_bar(x=lab, y=A["營業現金流"].tail(N_Q), name="營業現金(億)", marker_color="#E5484D")
        if "自由現金流" in A:
            f.add_bar(x=lab, y=A["自由現金流"].tail(N_Q), name="自由現金(億)", marker_color="#3B82F6")
        if "負債比%" in A:
            f.add_scatter(x=lab, y=A["負債比%"].tail(N_Q), name="負債比%", yaxis="y2",
                          line=dict(color="#A16207"))
        f.update_layout(barmode="group", title=dict(text="現金流與負債比", font=dict(size=13)),
                        yaxis2=dict(overlaying="y", side="right", range=[0, 100], showgrid=False))
        st.plotly_chart(f, width="stretch")

r3 = st.columns(3)
# ⑦ 營業現金流 今年 vs 去年(同季對比)
with r3[0]:
    if "營業現金流" in A:
        ocf = A["營業現金流"]
        qt = [s[-2:] for s in A["季別"]]
        yrs = [s[:2] for s in A["季別"]]
        this_y = yrs[-1]
        last_y = str(int(this_y) - 1)
        f = _fig()
        for y_, color, nm in ((last_y, "#3B82F6", f"20{last_y}"), (this_y, "#E5484D", f"20{this_y}")):
            xs = [qt[i] for i in range(len(yrs)) if yrs[i] == y_]
            ys = [ocf.iloc[i] for i in range(len(yrs)) if yrs[i] == y_]
            f.add_bar(x=xs, y=ys, name=nm, marker_color=color)
        f.update_layout(barmode="group",
                        title=dict(text="營業現金流(億):今年 vs 去年", font=dict(size=13)))
        st.plotly_chart(f, width="stretch")
# ⑧ 累計營收 今年 vs 去年
with r3[1]:
    mc = A.get("mon_cmp")
    if mc:
        cum_t, cum_l, s_t, s_l = [], [], 0.0, 0.0
        for i in range(12):
            s_t += mc["今年"][i] or 0; s_l += mc["去年"][i] or 0
            cum_t.append(s_t if mc["今年"][i] else None)
            cum_l.append(s_l if mc["去年"][i] else None)
        f = _fig()
        f.add_scatter(x=mc["月"], y=cum_l, name=f"{mc['this_y']-1}累計", line=dict(color="#3B82F6"))
        f.add_scatter(x=mc["月"], y=cum_t, name=f"{mc['this_y']}累計", line=dict(color="#E5484D"))
        f.update_layout(title=dict(text="累計營收(百萬):追趕進度", font=dict(size=13)))
        st.plotly_chart(f, width="stretch")
        t_last = max(i for i in range(12) if cum_t[i]) if any(cum_t) else None
        if t_last is not None and cum_l[t_last]:
            st.caption(f"至 {t_last+1} 月:累計 YoY {cum_t[t_last]/cum_l[t_last]-1:+.1%}")
# ⑨ 體質速評卡
with r3[2]:
    st.markdown("##### 🩺 體質速評(規則式)")
    checks = []
    try:
        if "自由現金流" in A:
            fcf4 = float(A["自由現金流"].tail(4).sum())
            checks.append(("🟢" if fcf4 > 0 else "🔴", f"近4季自由現金流 {fcf4:+.1f} 億"))
        if "core_ratio%" in A:
            cr = float(A["core_ratio%"].dropna().iloc[-1])
            checks.append(("🟢" if cr >= 70 else "🟡", f"獲利本業比 {cr:.0f}%(≥70 佳)"))
        if "負債比%" in A:
            dr = float(A["負債比%"].dropna().iloc[-1])
            checks.append(("🟢" if dr < 50 else ("🟡" if dr < 60 else "🔴"), f"負債比 {dr:.0f}%"))
        if "存貨天數" in A:
            iv = A["存貨天數"].dropna()
            if len(iv) >= 5:
                d = float(iv.iloc[-1] - iv.tail(5).mean())
                checks.append(("🟢" if d <= 5 else "🟡", f"存貨天數 較近5季均 {d:+.0f} 天"))
        if not q.empty:
            gm = q["毛利率%"].dropna()
            if len(gm) >= 5:
                d = float(gm.iloc[-1] - gm.tail(5).mean())
                checks.append(("🟢" if d >= -1 else "🔴", f"毛利率 較近5季均 {d:+.1f} pp"))
    except Exception:
        pass
    for lamp, txt in checks:
        st.markdown(f"{lamp} {txt}")
    st.caption("速評=體質面(現金流/本業比/負債/存貨/毛利),與買前體檢卡(籌碼面)互補。")

st.markdown("---")
n1, n2, n3 = st.columns(3)
with n1:
    st.page_link("pages/28_公司快照.py", label="🏢 公司快照(估值第一頁)")
with n2:
    st.page_link("pages/19_月營收預測.py", label="🔮 月營收模型")
with n3:
    st.page_link("pages/27_個股戰情室.py", label="🎯 個股戰情室(籌碼)")
st.caption(f"資料:FinMind 三大報表(快取20h)· <span style='color:{MUTED}'>財報為落後指標,"
           "體質看長期趨勢,別拿單季嚇自己</span>", unsafe_allow_html=True)

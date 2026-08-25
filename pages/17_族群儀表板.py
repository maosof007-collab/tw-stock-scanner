"""
頁面17:族群儀表板
================================
選一個族群 → 一頁看完:個股總表(價格/動能/營收/EPS/本益比/毛利/法人/倒貨率)
+ 營收雷達軌跡 + 美股對照 + 最新族群報告。
資料全部來自系統既有管線(價格官方源/月營收MOPS/財報FinMind快取/法人TWSE)。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="族群儀表板", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("族群儀表板", "GROUP DASHBOARD", "🗂️")

from theme_groups import THEME_GROUPS

ROOT = Path(__file__).parent.parent
D = ROOT / "data"

gname = st.selectbox("選擇族群", list(THEME_GROUPS.keys()), key="dash_grp")
codes = THEME_GROUPS[gname]


@st.cache_data(ttl=1800, show_spinner="組裝族群數據中…")
def build_table(gname: str, codes: tuple) -> pd.DataFrame:
    sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))
    try:
        bulk = pd.read_csv(D / "fundamentals" / "bulk_rev_2026_all.csv", dtype={"code": str})
        bulk["yoy"] = pd.to_numeric(bulk["yoy"], errors="coerce")
        rev_piv = bulk.pivot_table(index="code", columns="month", values="yoy")
    except Exception:
        rev_piv = pd.DataFrame()
    try:
        dump = pd.read_csv(D / "inst_dump_rate.csv", encoding="utf-8-sig", dtype={"code": str})
        dump_map = dict(zip(dump["code"], dump["dump_rate"]))
    except Exception:
        dump_map = {}
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0]
    except Exception:
        bm = None

    rows = []
    for c in codes:
        row = {"代碼": c, "名稱": nm.get(c, "")}
        px = None
        for suf in (".TW.csv", ".TWO.csv"):
            p = D / f"{c}{suf}"
            if p.exists():
                px = pd.read_csv(p, index_col=0, parse_dates=True, usecols=[0, 4, 5])
                px.columns = ["Close", "Volume"]
                px = px.apply(pd.to_numeric, errors="coerce").dropna()
                break
        if px is not None and len(px) > 61:
            c0 = px["Close"]
            row["收盤"] = round(float(c0.iloc[-1]), 1)
            row["當日%"] = round(float(c0.iloc[-1] / c0.iloc[-2] - 1) * 100, 2)
            row["20日均量(張)"] = round(float(px["Volume"].tail(20).mean()) / 1000)
            if bm is not None:
                b = bm.reindex(c0.index).ffill()
                row["RS60"] = round(float((c0.iloc[-1] / c0.iloc[-61]) /
                                          (b.iloc[-1] / b.iloc[-61])), 2)
        if c in rev_piv.index:
            t = rev_piv.loc[c]
            row["7月YoY%"] = round(t.get(7)) if pd.notna(t.get(7)) else None
            q1 = t.reindex([1, 2, 3]).mean()
            late = t.reindex([5, 6, 7]).mean()
            if pd.notna(q1) and pd.notna(late):
                row["營收改善pp"] = round(late - q1)
        try:
            from fundamentals import quarterly_fin
            q = quarterly_fin(c, years=2)
            if not q.empty:
                if "EPS" in q.columns:
                    eps_ttm = float(pd.to_numeric(q["EPS"], errors="coerce").tail(4).sum())
                    row["EPS(近4季)"] = round(eps_ttm, 2)
                    if eps_ttm > 0 and row.get("收盤"):
                        row["本益比"] = round(row["收盤"] / eps_ttm, 1)
                if "毛利率%" in q.columns:
                    row["毛利率%"] = round(float(q["毛利率%"].iloc[-1]), 1)
        except Exception:
            pass
        try:
            m = pd.read_csv(D / "institutional" / f"{c}_inst.csv",
                            usecols=lambda x: x in ("date", "外陸資買賣超股數(不含外資自營商)",
                                                    "外資買賣超股數", "it_net"))
            a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
            b2 = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
            it = pd.to_numeric(m.get("it_net"), errors="coerce").fillna(0)
            net5 = float((a.fillna(b2).fillna(0) + it).tail(5).sum())
            if row.get("收盤"):
                row["法人5日(億)"] = round(net5 * row["收盤"] / 1e8, 1)
        except Exception:
            pass
        if c in dump_map:
            row["倒貨率%"] = dump_map[c]
        rows.append(row)
    return pd.DataFrame(rows)


df = build_table(gname, tuple(codes))


def _verdict(r) -> tuple[int, str]:
    """綜合判讀:營收動能×法人籌碼×相對強弱×倒貨率 → (分數, 一句話結論)。"""
    rev_imp = r.get("營收改善pp") or 0
    yoy = r.get("7月YoY%") or 0
    rs = r.get("RS60") or 1.0
    fi5 = r.get("法人5日(億)") or 0
    dump = r.get("倒貨率%")
    hot = dump is not None and dump >= 40

    s_rev = 2 if (rev_imp >= 10 and yoy > 0) else (1 if rev_imp > 0 else 0)
    s_px = 1 if rs >= 1.05 else (-1 if rs < 0.95 else 0)
    s_fi = (1 if hot else 2) if fi5 > 0 else (-1 if fi5 < 0 else 0)
    score = s_rev + s_px + s_fi

    if s_rev == 2 and s_fi >= 1:
        v = "✅ 雙確認:營收轉強+法人買" + ("(⚠️熱區,等續買)" if hot else "")
    elif s_rev >= 1 and s_fi <= 0:
        v = "🟡 營收轉強,法人還沒進——等籌碼確認"
    elif s_rev == 0 and s_fi >= 1:
        v = "🔍 法人先行,營收未跟上——查在買什麼"
    elif s_rev == 0 and s_fi < 0 and s_px < 0:
        v = "🌑 三弱:先跳過"
    else:
        v = "— 觀望"
    pe = r.get("本益比")
    if pe is not None and pe < 12 and s_rev >= 1:
        v += "|低估值"
    return score, v


_sv = df.apply(_verdict, axis=1, result_type="expand")
df["綜合分"], df["判讀"] = _sv[0], _sv[1]
df = df.sort_values("綜合分", ascending=False)

n2 = (df["判讀"].str.startswith("✅")).sum()
n1 = (df["判讀"].str.startswith("🟡")).sum()
top = "、".join(df.head(3)["名稱"].astype(str))
st.info(f"🧭 **{gname} 總結**:{len(df)} 檔中 **{n2} 檔雙確認**(營收+法人)、{n1} 檔營收轉強待籌碼。"
        f"優先順序:**{top}**。下一步:✅檔丟「個股研究中心」跑報告+看法說筆記;"
        f"🟡檔進觀察,等潮汐圖法人翻買;進場點交給策略訊號(翻多/腰斬打底/運價動能)。")

st.markdown(f"### 📋 {gname} 個股總表(按綜合分排序)")
st.dataframe(df, width="stretch", hide_index=True,
             column_config={"倒貨率%": st.column_config.NumberColumn(
                 help="外資大買後隔日倒貨機率;≥40%=隔日沖熱區,買超訊號要打折"),
                 "綜合分": st.column_config.NumberColumn(
                 help="營收動能(0-2)+相對強弱(±1)+法人籌碼(±2,熱區折半)")})
st.caption("EPS/毛利=FinMind 季報(近4季);本益比=收盤÷近4季EPS;"
           "法人5日=外資+投信買賣超估算;RS60>1=近60日強於大盤。"
           "⚠️ 營收YoY分不出量增vs漲價轉嫁,重要判讀配法說筆記。")

# 營收雷達軌跡
try:
    rv = pd.read_csv(D / "revenue_trend.csv", encoding="utf-8-sig")
    s = rv[rv["group"] == gname].sort_values("ym")
    if not s.empty:
        st.markdown("**📈 族群營收 YoY 中位軌跡**:" +
                    "　".join(f"{r['ym'][5:]}月 {r['yoy_med']:+.0f}%" for _, r in s.tail(8).iterrows()))
except Exception:
    pass

# 美股對照
try:
    from us_peers import us_digest, US_PEERS
    if gname in US_PEERS:
        with st.expander(f"🇺🇸 美股同業對照({'/'.join(US_PEERS[gname])})", expanded=False):
            st.markdown(us_digest(gname) or "(暫無資料)")
except Exception:
    pass

# 最新族群報告 + 成分股報告捷徑
st.markdown("---")
import analyst_report as _ar
import importlib
if not hasattr(_ar, "list_articles"):
    _ar = importlib.reload(_ar)
arts = [a for a in _ar.list_articles()
        if a.get("name") == gname or (a.get("code") in codes and a.get("mode") != "晨報")]
if arts:
    st.markdown(f"### 📰 相關報告({len(arts)} 篇,新→舊)")
    labels = [f"{a['date'][:10]}｜{a['code']} {a['name']}｜{a['mode']}" for a in arts[:20]]
    pick = st.selectbox("選擇報告", labels, key="dash_art")
    a0 = arts[labels.index(pick)]
    with st.expander("閱讀", expanded=True):
        st.markdown(_ar.read_article(a0["file"]))
else:
    st.info(f"尚無 {gname} 相關報告——本機執行:python batch_group_reports.py {gname} --per-stock")

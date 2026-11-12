# -*- coding: utf-8 -*-
"""
pages/39_強勢資金.py — 今日強勢資金(EOD 成交注意力;白底報表)
=================================================================
外部「台股成交注意力」盤中掃描器的 EOD 融合版:占比倍數×RS×量比×收位。
介面特例:用戶指定白底 → 內容是獨立白底 HTML(components 內嵌),可直接分享。
"""
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="強勢資金", page_icon="💪", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("強勢資金", "ATTENTION FLOW", "💪")

ATT = ROOT / "data" / "attention"
files = sorted(ATT.glob("att_*.html"), reverse=True)
if not files:
    st.info("尚無報表——盤後 run_daily 自動產生,或按下方手動跑。")
else:
    pick = st.selectbox("日期", files, format_func=lambda p: p.stem.replace("att_", ""))
    components.html(pick.read_text(encoding="utf-8"), height=1600, scrolling=True)

c1, c2 = st.columns([1, 3])
if c1.button("🔄 立即重掃(約1分鐘)"):
    with st.spinner("全市場掃描中…"):
        import attention_scan
        r = attention_scan.scan()
        if r:
            p = attention_scan.save_html(r)
            st.success(f"完成:{p.name}——重新整理頁面看最新。")
        else:
            st.error("無資料。")
c2.caption("分數=RS/占比倍數/量比/收位 百分位均值;🔪⚠=隔日沖警戒(家規:爆量+2~3天禁入)。"
           "EOD 版,非盤中;黃底列=明天的賣壓名單。")

# ══════════ 明日空方觀察(榜單鏡像;「幫忙想另外一個方向 放空」2026-11-05) ══════════
import pandas as pd
import numpy as np

st.divider()
st.markdown("#### 🩸 明日空方觀察名單(榜單鏡像:開盤跳空 ≥3% 才空,當沖回補)")
try:
    import short_watch
    _sw = short_watch.build_short_watch()
except Exception as _e:
    _sw = None
    st.warning(f"空方名單產生失敗:{_e}")
if _sw:
    if _sw["df"].empty:
        st.info(f"{_sw['date']} 榜單 Top20 全數被剔除(處置/連榜),明日無空方候選。")
    else:
        st.caption(f"依 **{_sw['date']}** 榜單 Top20 剔除處置股與連榜≥2 後,"
                   f"剩 **{len(_sw['df'])} 檔**候選。開盤沒站上觸發價=整天不動。")
        st.dataframe(_sw["df"], hide_index=True, use_container_width=True,
                     column_config={
                         "收盤": st.column_config.NumberColumn(format="%.2f"),
                         "觸發價(開盤≥)": st.column_config.NumberColumn(format="%.2f"),
                         "停損(逆漲3.5%)": st.column_config.NumberColumn(format="%.2f"),
                         "漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                         "量比": st.column_config.NumberColumn(format="%.1f"),
                         "收位%": st.column_config.NumberColumn(format="%.0f%%")})
    if _sw["excluded"]:
        st.caption("已剔除:" + ";".join(_sw["excluded"]))
    st.caption("**回放依據(18,463 筆,2023 起)**:榜上股隔日開盤空→當日收盤回補,全榜 +0.48%/筆;"
               "**跳空≥3% 才進場 +1.21%、排除連榜後 +1.13%,四年逐年皆正**——賺的是隔日沖倒貨"
               "+追價套牢的結構財。鐵則:①只做現股當沖**先賣後買**(下單前確認在可先賣後買名單),"
               "收盤前必回補——同批股票抱空 5 天期望值歸零;②勝率僅 52%,期望值全靠砍右尾:"
               "**逆漲 3.5% 無條件回補**(回放單筆最慘 -28%);③大跌期留意金管會**限空令**。")

# ══════════════ 上榜戰績回放(2023 起;每晚 notify_push 自動檢討) ══════════════
# 「跑 然後每天檢討 我想看的是 有否策略可以生出來」(2026-11-02)

st.divider()
st.markdown("#### 📜 上榜戰績回放(隔日開盤買,追榜到底賺不賺,歷史說話)")
HIST = ROOT / "data" / "_attention_hist.csv"
if not HIST.exists():
    st.info("還沒有回放檔——本機跑 `python attention_replay.py`(約 3 分鐘)。")
else:
    @st.cache_data(ttl=3600)
    def _hist(mtime: float):   # 不可加底線前綴:Streamlit 會把 _ 開頭的參數排除在快取鍵外
        h = pd.read_csv(HIST, dtype={"代號": str})
        try:
            bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv",
                             usecols=["Date", "Close"]).dropna()
            c = pd.Series(bm["Close"].astype(float).values,
                          index=pd.to_datetime(bm["Date"]))
            f20 = (c.shift(-21) / c.shift(-1) - 1) * 100   # 同口徑:隔日起算20日
            h["bm20"] = pd.to_datetime(h["日期"]).map(f20)
        except Exception:
            h["bm20"] = np.nan
        return h

    h = _hist(HIST.stat().st_mtime)
    v1 = h.dropna(subset=["1日%"])
    v20 = h.dropna(subset=["20日%"])
    al = (v20["20日%"] - v20["bm20"]).dropna()
    m = st.columns(5)
    m[0].metric("回放筆數", f"{len(h):,}", f"{h['日期'].min()[:7]} 起 Top20/日",
                delta_color="off")
    m[1].metric("隔日買 D+1", f"{v1['1日%'].mean():+.2f}%",
                f"勝率 {(v1['1日%'] > 0).mean()*100:.0f}%", delta_color="off")
    m[2].metric("D+20", f"{v20['20日%'].mean():+.2f}%",
                f"中位 {v20['20日%'].median():+.2f}%", delta_color="off")
    m[3].metric("對大盤 α(20日)", f"{al.mean():+.2f}%",
                f"中位 {al.median():+.2f}%|勝大盤 {(al > 0).mean()*100:.0f}%",
                delta_color="off")
    m[4].metric("跳空追價成本", f"{h['跳空%'].dropna().mean():+.2f}%",
                "榜單熱度的入場稅", delta_color="off")

    def _row(d, tag):
        a1 = d.dropna(subset=["1日%"]); a20 = d.dropna(subset=["20日%"])
        aa = (a20["20日%"] - a20["bm20"]).dropna()
        if len(a20) < 30:
            return None
        return {"切片": tag, "筆數": len(d),
                "D+1均": a1["1日%"].mean(), "D+1勝": (a1["1日%"] > 0).mean() * 100,
                "D+20均": a20["20日%"].mean(), "D+20中位": a20["20日%"].median(),
                "D+20勝": (a20["20日%"] > 0).mean() * 100,
                "α20": aa.mean() if len(aa) else np.nan,
                "勝大盤%": (aa > 0).mean() * 100 if len(aa) else np.nan}

    rows = [r for r in [
        _row(h, "全部"),
        _row(h[h["量比"] < 2.5], "量比<2.5(溫和)"),
        _row(h[h["量比"] >= 5], "量比≥5(爆量)"),
        _row(h[h["隔日沖"] == "⚠"], "隔日沖⚠"),
        _row(h[h["隔日沖"] != "⚠"], "排除⚠"),
        _row(h[h["創20日高"] == 1], "創20日高"),
        _row(h[h["連榜"] >= 2], "連榜2+"),
        _row(h[h["連榜"] >= 3], "連榜3+"),
        _row(h[h["漲跌%"] >= 9.5], "漲停上榜"),
        _row(h[h["排名"] <= 5], "排名前5"),
    ] if r]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={k: st.column_config.NumberColumn(format=f)
                                for k, f in (("D+1均", "%+.2f%%"), ("D+1勝", "%.0f%%"),
                                             ("D+20均", "%+.2f%%"), ("D+20中位", "%+.2f%%"),
                                             ("D+20勝", "%.0f%%"), ("α20", "%+.2f%%"),
                                             ("勝大盤%", "%.0f%%"))})

    # 每天檢討:最近 10 期榜的隔日成績
    rec = (v1.groupby("日期")
             .agg(檔數=("1日%", "size"), 隔日均=("1日%", "mean"),
                  勝率=("1日%", lambda s: (s > 0).mean() * 100),
                  最佳=("1日%", "max"), 最差=("1日%", "min"))
             .round(2).tail(10).reset_index().sort_values("日期", ascending=False))
    st.markdown("##### 🔁 每日檢討(最近 10 期榜,隔日開盤買的成績)")
    st.dataframe(rec, hide_index=True, use_container_width=True,
                 column_config={"隔日均": st.column_config.NumberColumn(format="%+.2f%%"),
                                "勝率": st.column_config.NumberColumn(format="%.0f%%"),
                                "最佳": st.column_config.NumberColumn(format="%+.2f%%"),
                                "最差": st.column_config.NumberColumn(format="%+.2f%%")})
    with st.expander(f"完整回放日誌({len(h):,} 筆)——搜代號或名稱"):
        kw = st.text_input("篩選", "", placeholder="如 2330 或 台積", key="attkw")
        sub = h if not kw.strip() else h[h["代號"].str.contains(kw.strip())
                                         | h["名稱"].astype(str).str.contains(kw.strip())]
        st.dataframe(sub.sort_values(["日期", "排名"], ascending=[False, True])
                     .drop(columns=["bm20"]), hide_index=True,
                     use_container_width=True, height=420)
    st.caption("**結論(18,423 筆,2023 起,四年每年一致):追強勢榜不是策略,是付注意力稅**——"
               "隔日開盤買 D+1 平均 -0.5%/勝率 40%,20日中位數對大盤 α 約 -4%、"
               "只有 38% 的票跑贏 0050;平均數看似 +2% 全靠少數樂透尾巴。"
               "跳空 +1.2% 就是「大家都看到了」的入場稅。唯一中位數為正的切片是"
               "**量比<2.5 的溫和放量**(α +0.8%,但按年不穩),它的精神=「量縮整理後"
               "剛出量」——那就是已回測過的 volume_breakout 策略在做的事。"
               "**本頁定位:觀察雷達+明日賣壓名單(⚠),不是買單來源**;"
               "爆量⚠(量比≥5)20日中位 -2.6%,是回放裡最爛的一群,看到請迴避。"
               "每晚 notify_push 自動補熟成報酬並推 LINE 一行檢討。")

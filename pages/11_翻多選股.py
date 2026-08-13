"""
頁面8：SUPER TREND 全市場翻多選股
================================
用選定參數掃全市場（~1969 檔），列出近 K 日內『空→多』剛翻多的股，
附支撐位、距支撐%、多頭歷史平均長度、支撐延續機率，按延續機率排名。
參數與籌碼頁的 SUPER TREND 一致（ATR期間/乘數/統計年數N/統計窗口M）。
"""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import data_provider as dp
from ui_common import inject_css, THEME
from ui_theme import page_header

st.set_page_config(page_title="翻多選股", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("SUPER TREND 翻多選股", "BULL FLIP SCANNER", "🚀")


@st.cache_data(ttl=1800, show_spinner=False)
def _scan(period, mult, cont_window, lookback_years, flip_within, ver=2):   # ver:欄位改版時+1 破舊快取(底線開頭會被cache忽略,不能用)
    from chip_chart import scan_supertrend_flips
    bar = st.progress(0.0, text="掃描全市場中…")
    def cb(k, tot):
        bar.progress(min(1.0, k / tot), text=f"掃描中 {k}/{tot} …")
    df = scan_supertrend_flips(period, mult, cont_window, lookback_years,
                               flip_within, progress=cb)
    bar.empty()
    return df


# ── 參數（與籌碼頁 SUPER TREND 相同）──
c = st.columns([1, 1, 1, 1, 1.2, 1.4, 1.4])
period = c[0].selectbox("ATR 期間", [10, 14, 20], index=0)
mult   = c[1].selectbox("ATR 乘數", [4.0, 3.0, 2.0, 1.5], index=0)
years  = c[2].selectbox("統計年數 N", [10, 5, 3, 1], index=0, format_func=lambda y: f"{y} 年")
win    = c[3].selectbox("統計窗口 M", [20, 5, 10, 60], index=0, format_func=lambda d: f"{d} 日")
within = c[4].selectbox("翻多範圍", [1, 3, 5, 10], index=2,
                        format_func=lambda d: "今日剛翻多" if d == 1 else f"近 {d} 日翻多")
min_cont = c[5].slider("最低支撐延續機率%", 0, 100, 0, 5)
min_vol  = c[6].selectbox("最低20日均量", [0, 100, 300, 500, 1000, 2000], index=3,
                          format_func=lambda v: "不限" if v == 0 else f"{v:,} 張")

st.caption("翻多＝SuperTrend 由空翻多（趨勢反轉向上）。延續機率＝歷史多頭段中長度≥M 的比率，越高越少假訊號。")

@st.cache_data(ttl=1800, show_spinner=False)
def _strategy_pick_map():
    """歷史掃描檔(signals_*.csv)彙整:code → 策略第一次/最近選到(BUY級)與次數。"""
    import glob, os
    import pandas as pd
    m = {}
    for f in sorted(glob.glob(str(Path(__file__).parent.parent / "scan_results" / "signals_*.csv"))):
        d = os.path.basename(f)[8:16]
        d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        try:
            s = pd.read_csv(f, encoding="utf-8-sig", usecols=["代碼", "訊號等級"])
        except Exception:
            continue
        s = s[s["訊號等級"].astype(str).str.startswith("BUY")]
        for c in s["代碼"].astype(str):
            e = m.setdefault(c.split(".")[0], {"first": d_fmt, "n": 0, "last": d_fmt})
            e["n"] += 1
            e["last"] = d_fmt
    return m


if st.button("🚀 掃描全市場翻多", type="primary", width="stretch"):
    st.session_state.run_flip_scan = True

if st.session_state.get("run_flip_scan"):
    df = _scan(period, mult, win, years, within)
    if df.empty:
        st.info("此條件下無翻多股。可放寬「翻多範圍」或調整參數。")
    else:
        if min_cont > 0 and "支撐延續機率%" in df.columns:
            df = df[df["支撐延續機率%"].fillna(0) >= min_cont].reset_index(drop=True)
        n_all = len(df)
        if min_vol > 0 and "20日均量(張)" in df.columns:
            df = df[df["20日均量(張)"].fillna(0) >= min_vol].reset_index(drop=True)
        cut = f"(流動性濾掉 {n_all - len(df)} 檔)" if n_all != len(df) else ""
        # 對照自家策略掃描史:翻多日是技術指標翻轉日,「策略首選日」才是系統第一次選到它
        pm = _strategy_pick_map()
        df["策略首選日"] = df["代碼"].astype(str).map(lambda c: pm.get(c, {}).get("first", ""))
        df["策略入選次數"] = df["代碼"].astype(str).map(lambda c: pm.get(c, {}).get("n", 0))
        df["策略最近入選"] = df["代碼"].astype(str).map(lambda c: pm.get(c, {}).get("last", ""))
        _order = [c for c in ["代碼", "名稱", "翻多日", "策略首選日", "策略入選次數",
                              "策略最近入選"] if c in df.columns]
        df = df[_order + [c for c in df.columns if c not in _order]]
        st.success(f"共 {len(df)} 檔翻多（按支撐延續機率排序）{cut}")
        st.dataframe(
            df, width="stretch", hide_index=True, height=620,
            column_config={
                "收盤": st.column_config.NumberColumn(format="%.2f"),
                "支撐": st.column_config.NumberColumn(format="%.2f"),
                "距支撐%": st.column_config.NumberColumn(format="%.2f%%"),
                "昨日量(張)": st.column_config.NumberColumn(format="%,d"),
                "20日均量(張)": st.column_config.NumberColumn(format="%,d"),
                "日均值(百萬)": st.column_config.NumberColumn(format="%,.0f"),
                "量比": st.column_config.NumberColumn(format="%.2f"),
                "支撐延續機率%": st.column_config.ProgressColumn(
                    "支撐延續機率%", min_value=0, max_value=100, format="%.0f%%"),
            })
        st.download_button("⬇️ 下載 CSV", df.to_csv(index=False, encoding="utf-8-sig"),
                           file_name="supertrend_bull_flip.csv", mime="text/csv")
        st.caption("💡 排序靠前＝歷史上這種多頭較容易延續。「距支撐%」小＝離停損(支撐)近、風險小。"
                   "「已延續」小＝剛翻多不久，追進較不追高。"
                   "「量比」>1＝翻多當下有量進來(放量翻多可信度較高);"
                   "「日均值」太小(<數十百萬)滑價會吃掉利潤,買賣都難。"
                   "「翻多日」只是 SuperTrend 技術翻轉日;「策略首選日」是本系統策略掃描"
                   "(今日選股 BUY 級,2026-06 起有檔案)第一次選到它的日子——首選日很早+入選多次"
                   "＝多頭排列已久且策略反覆確認;空白＝策略從沒選過,純技術翻多要多留心。"
                   "細節到「訊號回查」頁 key 代碼看每一次紀錄。")
else:
    st.info("設定參數後，點上方「🚀 掃描全市場翻多」。全市場約 1969 檔，首次約 30-60 秒，"
            "同參數 30 分內秒開。")

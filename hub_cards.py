"""
hub_cards.py — 首頁駕駛艙(區塊卡導航+即時徽章)
=================================================================
起因(2026-09-19):側欄 25 頁太長,難讀且會遺漏。
解法:首頁改區塊卡(按使用時刻分六區),每卡帶徽章——有事的地方自己亮。
徽章全部讀輕量快取檔(無重運算),st.cache_data 10 分鐘。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
D = ROOT / "data"


@st.cache_data(ttl=600)
def _badges() -> dict:
    """輕量徽章:全部小檔讀取。"""
    from twtime import now_tw
    today = f"{now_tw():%Y-%m-%d}"
    b = {}
    try:
        p = pd.read_csv(D / "_mmap_pool.csv", dtype=str)
        b["breakout"] = int(p["狀態"].str.contains("突破").sum())
        b["pool"] = len(p)
    except Exception:
        pass
    try:
        w = pd.read_csv(D / "warrants" / "whale_signals.csv", dtype=str)
        b["whale"] = int((w["date"] == today).sum())
    except Exception:
        pass
    try:
        c = pd.read_csv(D / "_conf_calendar.csv", dtype=str)
        b["conf"] = int((c["date"] == today).sum())
    except Exception:
        pass
    try:
        ca = pd.read_csv(D / "corp_actions_log.csv", dtype=str)
        roc = f"{now_tw().year - 1911}{now_tw():%m%d}"
        b["corp"] = int(ca["發言日期"].astype(str).str.replace("/", "").str.endswith(
            f"{now_tw():%m%d}").sum())
    except Exception:
        pass
    try:
        h = pd.read_csv(D / "_health_report.csv", dtype=str)
        b["red"] = int((h["狀態"] == "🔴").sum())
    except Exception:
        pass
    try:
        j = pd.read_csv(D / "decision_journal.csv", dtype=str)
        b["open"] = int((j["status"] == "open").sum())
    except Exception:
        pass
    return b


def _card(col, icon, title, links, note=""):
    with col:
        st.markdown(f"##### {icon} {title}")
        for page, label in links:
            st.page_link(page, label=label)
        if note:
            st.caption(note)


def render():
    """首頁頂部駕駛艙。"""
    b = _badges()

    def n(key, tpl):
        v = b.get(key)
        return tpl.format(v) if v else ""

    # ── 直覺層:四張大數字(今天一眼) ──
    m1, m2, m3, m4 = st.columns(4)
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna().tail(2)
        _twii = float(bm["Close"].iloc[-1])
        _tchg = (_twii / float(bm["Close"].iloc[-2]) - 1) * 100
        m1.metric("大盤", f"{_twii:,.0f}", f"{_tchg:+.2f}%")
    except Exception:
        m1.metric("大盤", "—")
    try:
        import my_etf as _me
        _s = _me.stats(_me.nav_series())
        m2.metric("我的ETF", f"{_s['報酬%']:+.1f}%" if _s else "—",
                  f"超額 {_s['超額pp']:+.1f}pp" if _s else None)
    except Exception:
        m2.metric("我的ETF", "—")
    m3.metric("持倉筆數", b.get("open", "—"))
    _todo = sum(1 for k in ("breakout", "whale", "conf", "corp", "red") if b.get(k))
    m4.metric("今日紅點", _todo, "先看有紅點的卡" if _todo else "無待辦", delta_color="off")

    st.markdown("### 🎛️ 駕駛艙(有紅點的先看)")
    c1, c2, c3 = st.columns(3)
    _card(c1, "🌅", "開盤前",
          [("pages/26_晨報.py", "📰 每日晨報"),
           ("pages/19_月營收預測.py", "🔮 月營收預測"),
           ("pages/23_法說行事曆.py", f"🎤 法說行事曆{n('conf', ' 🔴今日{}場')}"),
           ("pages/25_籌碼地圖.py", f"🗺️ 籌碼地圖{n('breakout', ' 🎯突破{}檔')}")])
    _card(c2, "💼", "下單與部位",
          [("pages/6_績效追蹤.py", f"🩺 體檢卡+日誌{n('open', '(持倉{})')}"),
           ("pages/24_我的ETF.py", "🧺 我的ETF"),
           ("pages/21_權證專區.py", "🎫 權證專區")],
          "任何單:體檢卡 → 日誌 → 下單")
    _card(c3, "🌇", "盤後資金流",
          [("pages/22_權證大戶.py", f"🐳 權證大戶{n('whale', ' 🔴鯨魚{}檔')}"),
           ("pages/16_資金流向日誌.py", "💸 資金流向日誌"),
           ("pages/8_籌碼分析儀表板.py", "📊 籌碼分軌圖")])
    c4, c5, c6 = st.columns(3)
    _card(c4, "📅", "週期與事件",
          [("pages/18_大戶籌碼週報.py", "🐘 大戶週報(週)"),
           ("pages/22_權證大戶.py", f"📜 分割/減資雷達{n('corp', ' 🔴今日{}筆')}"),
           ("pages/17_族群儀表板.py", "🗂️ 族群儀表板")])
    _card(c5, "🔬", "研究室",
          [("pages/13_個股法人報告.py", "🔬 個股研究中心"),
           ("pages/12_研究文章.py", "📄 研究文章庫"),
           ("pages/20_深度潛力股.py", "💎 深度潛力股")])
    _card(c6, "⚙️", "系統",
          [("pages/7_更新進度.py", f"⏱️ 更新進度{n('red', ' 🔴體檢{}項')}"),
           ("pages/15_使用說明.py", "🏛️ 使用說明+憲法"),
           ("pages/0_總經.py", "🌡️ 總經溫度計")])
    st.markdown("---")

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
def _todo_list() -> list[str]:
    """今日待辦:具體行動句(直覺層核心——告訴你做什麼,不是給你連結)。"""
    from twtime import now_tw
    today = f"{now_tw():%Y-%m-%d}"
    todo = []
    # ① 晨報
    try:
        arts = list((D / "research_articles").glob(f"art_{today.replace('-','')}*_MKT.md"))
        if arts:
            todo.append("📰 讀今日晨報(題材攻防段先看)")
        elif now_tw().weekday() < 5 and now_tw().hour >= 8:
            todo.append("⚠️ 今日晨報未產生——查排程/引擎")
    except Exception:
        pass
    # ② 持倉距停損
    try:
        import weekly_review as wr
        j = pd.read_csv(D / "decision_journal.csv", dtype=str)
        for _, r in j[j["status"] == "open"].iterrows():
            bp = pd.to_numeric(r.get("buy_price"), errors="coerce")
            s = wr.stop_suggestion(r["code"], float(bp) if pd.notna(bp) else None)
            if s and s.get("建議") and s.get("現價"):
                gap = (s["現價"] / s["建議"] - 1) * 100
                if gap <= 3:
                    todo.append(f"🛑 {r['code']} {r['name']} 距停損只剩 {gap:.1f}%——跌破就走,不討論")
    except Exception:
        pass
    # ③ 法說
    try:
        c = pd.read_csv(D / "_conf_calendar.csv", dtype=str)
        td = c[c["date"] == today]
        if len(td):
            names = "、".join((td["code"] + td["name"]).head(4))
            todo.append(f"🎤 今天 {len(td)} 場法說:{names}——持倉相關的聽完存筆記")
    except Exception:
        pass
    # ③.5 持股/ETF 分析師目標價異動(近3天)
    try:
        import tp_radar
        codes = set()
        j = pd.read_csv(D / "decision_journal.csv", dtype=str)
        codes |= set(j[j["status"] == "open"]["code"])
        try:
            import my_etf
            codes |= {c["code"] for c in my_etf.load().get("constituents", [])
                      if c.get("code", "").isdigit()}
        except Exception:
            pass
        al = tp_radar.alerts(list(codes), days=3)
        for _, r in al.drop_duplicates(subset=["code", "類型"]).iterrows():
            v = r["目標價"] if r["類型"] == "目標價" else r["EPS預估"]
            todo.append(f"📊 {r['名稱']}{r['code']} 分析師{r['類型']}{r['方向']}至 {v:g}"
                        f"({r['日期'][5:]})——共識在動,對照自己的論點")
    except Exception:
        pass
    # ③.7 今日供應鏈發想(一天一題)
    try:
        import json as _json
        _dp = D / "supply_chain_drafts.json"
        if _dp.exists():
            _ds = _json.loads(_dp.read_text(encoding="utf-8"))
            if _ds and _ds[-1].get("date") == today:
                todo.append(f"⛓️ 今日供應鏈發想:{_ds[-1]['subject']}——"
                            f"想一想「第二個大甲」在哪(文章庫有題目)")
    except Exception:
        pass
    # ③.72 總經事件日(macro_events.csv,手動維護)
    try:
        ev = pd.read_csv(D / "macro_events.csv", dtype=str)
        for _, e in ev[(ev["date"] == today) & (ev["importance"] == "高")].iterrows():
            todo.append(f"📅 今晚事件:{e['event']}({e.get('time','')})——{str(e.get('note',''))[:40]}")
    except Exception:
        pass
    # ③.73 外資期貨淨空單急變(|日增減|≥5000口=大部位表態;10/15教案:10/13加空8138口兩天後-3.4%)
    try:
        _tf73 = pd.read_csv(D / "_taifex_fi.csv")
        if len(_tf73) and abs(float(_tf73["日增減"].iloc[-1])) >= 5000:
            _r73 = _tf73.iloc[-1]
            _dir = "加空" if _r73["日增減"] < 0 else "回補"
            todo.append(f"🧾 外資期貨單日{_dir} {abs(_r73['日增減']):,.0f} 口"
                        f"(淨OI {_r73['淨未平倉口數']:,.0f})——大部位在表態,順向別逆勢")
    except Exception:
        pass
    # ③.74 我的ETF:今日改組 diff + 成員距停損≤3%
    try:
        import my_etf as _me74
        _d74 = _me74.load()
        _last = _d74.get("log", [{}])[-1] if _d74.get("log") else {}
        if _last.get("date") == today:
            _df74 = _last.get("diff") or {}
            _seg = []
            if _df74.get("加"):
                _seg.append("加 " + "、".join(x.split("×")[0] for x in _df74["加"][:5]))
            if _df74.get("刪"):
                _seg.append("刪 " + "、".join(_df74["刪"][:5]))
            todo.append(f"🧺 我的ETF今日改組({_last.get('note','')}):"
                        + ("|".join(_seg) if _seg else "權重再平衡") + "——進出點見頁24")
        _pt74 = _me74.positions_table()
        _hit74 = _pt74[_pt74["⚠"] == "🛑"] if len(_pt74) else _pt74
        for _, r in _hit74.iterrows():
            todo.append(f"🛑 ETF成員 {r['名稱']}{r['代碼']} 距停損 {r['距停損%']}%"
                        f"(停損 {r['停損價']})——跌破就走")
    except Exception:
        pass
    # ③.745 ETF成員處置中(處置股不接刀研究)
    try:
        from disposal import current_set
        import my_etf as _me745
        _dpset = current_set()
        for c in _me745.load().get("constituents", []):
            if c.get("code") in _dpset:
                todo.append(f"⛔ ETF成員 {c.get('name','')}{c['code']} 處置中——分盤流動性差,"
                            f"停損單可能滑價,優先處理")
    except Exception:
        pass
    # ③.75 我的ETF換股警鈴(swap_alerts 四條件,響了才列)
    try:
        import my_etf as _meh
        for _al in _meh.swap_alerts()[:3]:
            todo.append(f"🧺 我的ETF警鈴:{_al}(頁24 處理或開自動駕駛)")
    except Exception:
        pass
    # ③.8 還沒發動觀察名單(低檔整理+外資吃貨+未出量)
    try:
        q = pd.read_csv(D / "_quiet_accum.csv", dtype=str)
        if len(q):
            todo.append(f"🤫 還沒發動 Top{len(q)}:{'、'.join((q['名稱'] + q['代碼']).head(5))}"
                        f"——外資在吃貨、還沒出量(選股頁置頂,等第一根)")
    except Exception:
        pass
    # ④ 突破/鯨魚
    try:
        p = pd.read_csv(D / "_mmap_pool.csv", dtype=str)
        nbr = int(p["狀態"].str.contains("突破").sum())
        if nbr:
            todo.append(f"🗺️ 地圖 {nbr} 檔剛突破——只看不追第一根,等回測不破")
    except Exception:
        pass
    try:
        w = pd.read_csv(D / "warrants" / "whale_signals.csv", dtype=str)
        tw_ = w[w["date"] == today]
        if len(tw_):
            todo.append(f"🐋 鯨魚訊號 {len(tw_)} 檔:{'、'.join(tw_['ucode'].head(5))}(5日窗,先過體檢卡)")
    except Exception:
        pass
    # ⑤ 資料體檢
    try:
        h = pd.read_csv(D / "_health_report.csv", dtype=str)
        nred = int((h["狀態"] == "🔴").sum())
        if nred:
            todo.append(f"🔧 資料體檢 {nred} 項紅——看數字前先修資料(頁7)")
    except Exception:
        pass
    if now_tw().weekday() == 5:
        todo.append("📋 今天週六:讀週檢視報告(五關+出場品質)")
    return todo


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

    # ── 🚦 大盤風險燈(2026-10-15 大跌教案:大盤級訊號從儀表升級為警報) ──
    try:
        import json as _mrj
        _mrp = D / "_market_risk.json"
        _mr = _mrj.loads(_mrp.read_text(encoding="utf-8"))
        # 數據過期防呆(2026-10-17「我很怕我沒看到」教案):燈沒更新≠天下太平
        import time as _t
        _age_h = (_t.time() - _mrp.stat().st_mtime) / 3600
        if _age_h > 20:
            st.warning(f"⏰ 風險燈數據已 {_age_h:.0f} 小時未更新——沉默≠安全,"
                       "先跑 run_daily 或 sentinel_morning 再做決策。")
        if _mr["lamp"] == "🔴":
            _nl = chr(10)
            st.error(f"🚦 **大盤風險燈 🔴({_mr['score']}分)|{_mr['rule']}**{_nl}{_nl}"
                     + _nl.join(f"- {r}" for r in _mr["reasons"]))
        elif _mr["lamp"] == "🟡":
            st.warning(f"🚦 大盤風險燈 🟡({_mr['score']}分)|{_mr['rule']}:"
                       + ";".join(_mr["reasons"]))
        else:
            st.caption(f"🚦 大盤風險燈 🟢({_mr['score']}分)|正常紀律")
    except Exception:
        pass

    # ── 📰 今日戰報(一天最多自動彈一次,且僅在 🟡🔴 或高重要事件日;手動鈕隨時可開)──
    from twtime import now_tw as _ntw
    _today_b = f"{_ntw():%Y-%m-%d}"

    @st.dialog("📰 今日戰報", width="large")
    def _briefing():
        try:
            import json as _bj
            _mr2 = _bj.loads((D / "_market_risk.json").read_text(encoding="utf-8"))
            st.markdown(f"## 🚦 {_mr2['lamp']}({_mr2['score']}分)|{_mr2['rule']}")
            for r in _mr2["reasons"]:
                st.markdown(f"- {r}")
        except Exception:
            st.caption("風險燈資料未生成")
        try:
            ev = pd.read_csv(D / "macro_events.csv", dtype=str)
            tv = ev[ev["date"] == _today_b]
            if len(tv):
                st.markdown("#### 📅 今日事件")
                for _, e in tv.iterrows():
                    st.markdown(f"- **{e['event']}**({e.get('time','')}):{e.get('note','')}")
        except Exception:
            pass
        try:
            import macro_news
            news = [n for n in macro_news.load() if n.get("risk")][:6]
            if news:
                st.markdown("#### 📰 總經頭條(風險相關)")
                for n in news:
                    st.markdown(f"- [{n['title']}]({n['url']})")
        except Exception:
            pass
        try:
            import my_etf as _meb
            _ptb = _meb.positions_table()
            _hb = _ptb[_ptb["⚠"] == "🛑"] if len(_ptb) else _ptb
            if len(_hb):
                st.markdown("#### 🛑 持倉警報")
                for _, r in _hb.iterrows():
                    st.markdown(f"- {r['名稱']}{r['代碼']}:距停損 {r['距停損%']}%(停損 {r['停損價']})")
        except Exception:
            pass
        st.caption("來源:風險燈/事件庫/鉅亨頭條/ETF 持倉——紀律在燈上,不在情緒上。")

    _c_brief, _c_sp = st.columns([1, 5])
    if _c_brief.button("📰 今日戰報", key="brief_btn"):
        _briefing()
    try:
        import json as _bj2
        _lamp_now = _bj2.loads((D / "_market_risk.json").read_text(encoding="utf-8"))["lamp"]
    except Exception:
        _lamp_now = "🟢"
    _bk = f"briefed_{_today_b}"
    if _lamp_now in ("🔴", "🟡") and not st.session_state.get(_bk):
        st.session_state[_bk] = True
        _briefing()

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

    # ── ✅ 今日待辦(具體行動句) ──
    todo = _todo_list()
    if todo:
        st.markdown("#### ✅ 今天做這幾件事")
        st.markdown("\n".join(f"{i+1}. {t}" for i, t in enumerate(todo)))
    else:
        st.success("今天沒有待辦——市場沒事就是好事,別手癢。")

    st.markdown("### 🎛️ 駕駛艙(每張卡回答一個問題;有紅點的先看)")
    c1, c2, c3 = st.columns(3)
    _card(c1, "🌅", "① 盤前|今天什麼局?",
          [("pages/0_總經.py", "🌡️ 總經溫度計(大盤融資維持率)"),
           ("pages/26_晨報.py", "📰 每日晨報"),
           ("pages/23_法說行事曆.py", f"🎤 法說行事曆{n('conf', ' 🔴今日{}場')}"),
           ("pages/5_新聞分析.py", "📰 新聞與情緒")],
          "順序:風險燈(頂部)→ 溫度計 → 晨報 → 今日事件")
    _card(c2, "📡", "② 選股|買什麼?",
          [("pages/1_今日選股.py", "📡 今日選股(策略掃描)"),
           ("pages/25_籌碼地圖.py", f"🗺️ 籌碼地圖{n('breakout', ' 🎯突破{}檔')}"),
           ("pages/11_翻多選股.py", "🔄 翻多選股(底部轉強)"),
           ("pages/14_訊號回查.py", "🔍 訊號回查(過去選股復盤)")],
          "掃出來的候選 → 先走③研究動線,別直接跳④")
    _card(c3, "🔬", "③ 研究動線|這檔值得買嗎?",
          [("pages/28_公司快照.py", "1️⃣ 公司快照(第一眼)"),
           ("pages/29_財務九宮格.py", "2️⃣ 財務九宮格(體質)"),
           ("pages/38_估值前瞻.py", "3️⃣ 估值前瞻(三情境×機率)"),
           ("pages/19_月營收預測.py", "4️⃣ 月營收預測(開獎前瞻)"),
           ("pages/27_個股戰情室.py", "5️⃣ 個股戰情室(一屏總檢)"),
           ("pages/33_財經報.py", "🗞️ 財經報專刊(深讀)"),
           ("pages/35_券商觀點.py", "🗂️ 券商觀點(222檔)"),
           ("pages/13_個股法人報告.py", "🔬 個股研究中心(產報告)")],
          "照編號走:快照→九宮格→估值前瞻→月營收→戰情室")
    c4, c5, c6 = st.columns(3)
    _card(c4, "💼", "④ 部位|手上的怎麼辦?",
          [("pages/6_績效追蹤.py", f"🩺 體檢卡+日誌{n('open', '(持倉{})')}"),
           ("pages/24_我的ETF.py", "🧺 我的ETF"),
           ("pages/21_權證專區.py", "🎫 權證專區"),
           ("pages/31_選擇權學院.py", "🎓 選擇權學院(模擬倉)")]
          + ([("pages/37_下單台.py", "🧾 Nova 下單台(家規守門)")]
             if (ROOT / "config.json").exists() else []),
          "任何單:體檢卡 → 日誌 → 下單")
    _card(c5, "🌇", "⑤ 盤後|今天誰在動錢?",
          [("pages/22_權證大戶.py", f"🐳 權證大戶{n('whale', ' 🔴鯨魚{}檔')}"),
           ("pages/39_強勢資金.py", "💪 強勢資金(成交注意力·白底)"),
           ("pages/36_迴轉率.py", "🌪️ 迴轉率雷達(隔日沖指紋)"),
           ("pages/16_資金流向日誌.py", "💸 資金流向日誌"),
           ("pages/8_籌碼分析儀表板.py", "📊 籌碼分軌圖"),
           ("pages/4_市場資金流向.py", "🌊 市場資金流向"),
           ("pages/34_美股連動.py", "🦅 美股連動雷達(US對照)"),
           ("pages/30_中國連動.py", "🐉 中國連動雷達(A股對照)")])
    _card(c6, "📅", "⑥ 週期掃描+系統",
          [("pages/32_產業鏈.py", "⛓️ 產業鏈魚骨圖+每日發想"),
           ("pages/18_大戶籌碼週報.py", "🐘 大戶週報(週)"),
           ("pages/22_權證大戶.py", f"📜 分割/減資雷達{n('corp', ' 🔴今日{}筆')}"),
           ("pages/17_族群儀表板.py", "🗂️ 族群儀表板"),
           ("pages/3_族群輪動.py", "🌀 族群輪動 RRG"),
           ("pages/2_產業輪動.py", "🔁 產業輪動"),
           ("pages/10_集團股K線.py", "📊 集團股K線"),
           ("pages/20_深度潛力股.py", "💎 深度潛力股(風格長文)"),
           ("pages/12_研究文章.py", "📄 研究文章庫"),
           ("pages/9_研究報告瀏覽器.py", "🗞️ 研究報告瀏覽器"),
           ("pages/7_更新進度.py", f"⏱️ 更新進度{n('red', ' 🔴體檢{}項')}"),
           ("pages/15_使用說明.py", "🏛️ 使用說明+憲法")],
          "上半=週/月級掃描與長文庫;下半=系統")
    st.markdown("---")

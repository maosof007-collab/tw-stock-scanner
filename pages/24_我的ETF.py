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

# 🤖 自動駕駛開關(開=每月第一個執行日自動量化重選並直接改組,日誌標🤖;關=一切手動)
_ap_on = st.toggle("🤖 自動駕駛:每月自動量化重選改組(00409A 式)",
                   value=bool(d.get("autopilot")), key="etf_ap",
                   help="開啟後 run_daily 每月自動跑因子重選並直接改組;警鈴與日誌照常,隨時可關。")
if _ap_on != bool(d.get("autopilot")):
    d["autopilot"] = bool(_ap_on)
    _me.save(d)
    st.toast("🤖 自動駕駛:" + ("已開啟,下次月初生效" if _ap_on else "已關閉"))
cons = pd.DataFrame(d["constituents"]) if d["constituents"] else pd.DataFrame(
    columns=["code", "name", "weight", "thesis"])

tab_hold, tab_exam, tab_pick, tab_log = st.tabs(["📊 淨值與持股", "🧪 高股息58檔考卷", "🎯 候選池(系統訊號)", "📓 改組日誌"])


# ── 高股息 58 檔(etf58_exam;只讀 data/etf58/raw 快取,每日流程 Step 4.5851 補資料)──
@st.cache_data(show_spinner="讀 58 檔快取…")
def _exam(stamp: float):
    import etf58_exam as _ex
    _t = _ex.table()
    return _t, dict(_t.attrs["mkt"]), _ex.windows()


@st.cache_data(show_spinner=False)
def _exam_lines(stamp: float, codes: tuple, since: str):
    import etf58_exam as _ex
    return _ex.lines(list(codes), since)


def _exam_stamp() -> float:
    import etf58_exam as _ex
    return _ex._stamp()

with tab_hold:
    # ── 📍 持倉進出表(2026-10-14:進場價/停損/距停損,家規內建)──
    try:
        _pt = _me.positions_table()
        if len(_pt):
            st.markdown("#### 📍 進出點與停損(家規:未賺1R守「進場價-1.5ATR」;賺1R後保本+移動2ATR只升不降)")
            st.dataframe(_pt, hide_index=True, width="stretch")
            _brk = _pt[_pt["距停損%"].notna() & (_pt["距停損%"] < 0)]
            if len(_brk):                    # 已跌破:由每日流程(enforce_stops)自動出場,不用人決定
                st.error("🛑 已跌破停損:" + "、".join(
                    f"{r['名稱']}{r['代碼']}(停損 {r['停損價']}、現價 {r['現價']})" for _, r in _brk.iterrows())
                    + "——下次每日流程系統自動出場、權重轉現金。")
            _hits = _pt[(_pt["⚠"] == "🛑") & ~_pt["代碼"].isin(_brk["代碼"])]
            if len(_hits):
                st.error("🛑 距停損 ≤3%:" + "、".join(
                    f"{r['名稱']}{r['代碼']}(停損 {r['停損價']})" for _, r in _hits.iterrows())
                    + "——跌破就走,不討論。")
    except Exception as _e:
        st.caption(f"進出表載入失敗:{_e}")
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
        # 疊上高股息 58 檔(含息,同一個基期);挑哪幾檔看「🧪 高股息58檔考卷」分頁
        try:
            import etf58_exam as _ex
            _ov = st.multiselect("➕ 疊上高股息 58 檔(含息,最多 4 檔;怎麼挑看上方「🧪 高股息58檔考卷」分頁)",
                                 options=_ex.E.CODES, format_func=lambda c: f"{c} {_ex.E.NAMES[c]}",
                                 max_selections=4, key="etf_ov")
            if _ov:
                _ol = _exam_lines(_exam_stamp(), tuple(_ov), str(nav["date"].iloc[0]))
                for _c, _col in zip(_ov, ["#7C3AED", "#DB2777", "#16A34A", "#92400E"]):
                    if _c in _ol.columns:
                        fig.add_scatter(x=_ol.index, y=_ol[_c], name=f"{_c} {_ex.E.NAMES[_c]}",
                                        line=dict(color=_col, width=1.8, dash="dash"))
        except Exception as _e:
            st.caption(f"高股息 58 檔疊圖載入失敗:{_e}")
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
            _bz = _me.buy_zone(_code)
            _rows.append({"代號": _code, "名稱": _r.get("name", ""),
                          "權重%": _w, "目標金額": round(_target),
                          "現價": round(_p, 1), "整張": _lots, "零股": _odd,
                          "實際投入": round(_act),
                          "建議買區": f"{_bz['lo']}~{_bz['hi']}" if _bz else "",
                          "位置": _bz.get("位置", "") if _bz else "",
                          "停損": _bz.get("停損", "") if _bz else ""})
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

with tab_exam:
    try:
        import etf58_exam as _ex
        _T, _MK, _W = _exam(_exam_stamp())
    except Exception as _e:
        _T = None
        st.error(f"58 檔快取讀不到:{_e}(先跑 python -X utf8 scripts/etf58_inception.py fetch)")
    if _T is not None:
        def _pct(v):
            return "—" if pd.isna(v) else f"{v * 100:+.1f}%"

        st.caption(f"58 檔畫成 58 條線沒辦法看,所以這裡**一檔一個點**。而且不比「上市以來」(新基金只遇過多頭,年化天生好看),"
                   f"改比**同一段期間**:這次空頭 {_W['peak']:%Y/%m/%d} → {_W['low']:%m/%d}(大盤 {_pct(_W['bear_m'])})"
                   f"和前一段多頭 {_W['bull0']:%Y/%m/%d} → {_W['peak']:%Y/%m/%d}(大盤 {_pct(_W['bull_m'])})。"
                   f"資料到 {_W['last']:%Y/%m/%d};含息、股息不再投入;大盤=加權指數(不含息)。")
        _tw_act = _T[_T.cat == "台股主動"]
        _k1, _k2, _k3, _k4 = st.columns(4)
        _k1.metric("這次空頭大盤", _pct(_W["bear_m"]), f"高點後最低 {_W['low']:%m/%d}", delta_color="off", delta_arrow="off")
        _k2.metric("58 檔裡跌得比大盤多", f"{int((_T.dn > 1).sum())} 檔", f"逆勢上漲 {int((_T.bear > 0).sum())} 檔(多為債券)", delta_color="off", delta_arrow="off")
        _k3.metric("主動式台股跌得比大盤多", f"{int((_tw_act.dn > 1).sum())} / {len(_tw_act)} 檔",
                   f"最深 {_tw_act.sort_values('bear').code.iloc[0]} {_pct(_tw_act.bear.min())}", delta_color="off", delta_arrow="off")
        _k4.metric("這次是第一次遇到空頭", f"{int((_T.n_prior == 0).sum())} 檔", f"考過拖半年以上空頭的只有 {int(_T.long_bear.sum())} 檔",
                   delta_color="off", delta_arrow="off")

        # ── ① 一檔一個點 ──
        st.markdown("#### ① 一檔一個點:漲的時候跟多少、跌的時候跟多少")
        _P = _T.dropna(subset=["up"])
        _f = go.Figure()
        _lo, _hi = -45, 160
        _f.add_scatter(x=[_lo, _hi], y=[_lo, _hi], mode="lines", line=dict(color="#B0B5BD", width=1, dash="dot"),
                       hoverinfo="skip", showlegend=False)
        for _cat in _ex.CAT_ORDER:
            _g = _P[_P.cat == _cat]
            if _g.empty:
                continue
            _col = _ex.CAT_COLOR[_cat]
            _lab = _cat in ("台股高股息", "台股主動")
            _f.add_scatter(
                x=_g.dn * 100, y=_g.up * 100, mode="markers+text" if _lab else "markers", name=f"{_cat}({len(_g)})",
                text=_g.code if _lab else None, textposition="top center", textfont=dict(size=10, color="#4B5563"),
                marker=dict(size=11, color=[_col if n > 0 else "#FFFFFF" for n in _g.n_prior], line=dict(color=_col, width=2)),
                customdata=[[r.code, r["name"], f"{r.listed:%Y/%m/%d}", _pct(r.bear), _pct(r.bull), f"{r.bull_from:%Y/%m/%d}",
                             f"{r.n_less}/{r.n_prior}" if r.n_prior else "第一次考", f"{r.asym * 100:+.0f}"] for _, r in _g.iterrows()],
                hovertemplate="<b>%{customdata[0]} %{customdata[1]}</b><br>上市 %{customdata[2]}<br>這次空頭 %{customdata[3]}(跌了大盤的 %{x:.0f}%)"
                              "<br>多頭 %{customdata[4]}(自 %{customdata[5]},漲了大盤的 %{y:.0f}%)<br>不對稱 %{customdata[7]} 點"
                              "<br>以前的空頭 少跌/考過:%{customdata[6]}<extra></extra>")
        _f.add_scatter(x=[100], y=[100], mode="markers+text", text=["大盤"], textposition="middle left",
                       textfont=dict(size=12, color="#111827"), marker=dict(symbol="diamond", size=12, color="#111827"),
                       hoverinfo="skip", showlegend=False)
        _f.add_annotation(x=_lo + 4, y=_hi - 6, xanchor="left", showarrow=False, font=dict(size=12, color="#4B5563"),
                          text="虛線上方:漲的時候跟得多、跌的時候跟得少")
        _f.add_annotation(x=_hi - 2, y=-22, xanchor="right", showarrow=False, font=dict(size=12, color="#4B5563"),
                          text="虛線下方:跌的時候跟得比漲的時候多")
        _f.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.06),
                         plot_bgcolor="#FFFFFF",
                         xaxis=dict(title="這次空頭:跌了大盤的幾 %(越左越抗跌,負數=逆勢上漲)", range=[_lo, _hi], gridcolor="#EEF0F3",
                                    zeroline=True, zerolinecolor="#D1D5DB", ticksuffix="%"),
                         yaxis=dict(title="前一段多頭:漲了大盤的幾 %", range=[-30, _hi], gridcolor="#EEF0F3",
                                    zeroline=True, zerolinecolor="#D1D5DB", ticksuffix="%"))
        st.plotly_chart(_f, width="stretch", key="exam_dots")
        _miss = _T[_T.up.isna()]
        st.caption("實心=以前考過空頭;**空心=這次是第一次,而且多頭只參加後半段**(從上市首日算)。點圖例可以關掉某一類;滑鼠移到點上看明細。"
                   "虛線=「漲跌都跟大盤同一個比例」,也就是只有曝險高低、沒有多出來的本事;離虛線越遠才是差別。"
                   + (("未入圖:" + "、".join(f"{r.code}(多頭只參加 {int(r.bull_days)} 天;這次空頭 {_pct(r.bear)})" for _, r in _miss.iterrows()) + "。")
                      if len(_miss) else ""))

        # ── ② 四關濃縮 ──
        st.markdown("#### ② 太多檔怎麼看:四關濾到剩幾檔(機械規則,是體檢不是買單)")
        _grp = {"台股(高股息+主動)": ("台股高股息", "台股主動"), "海外股票": ("海外股票",), "債券(含主動債)": ("債券", "主動債券"),
                "全部 58 檔": tuple(_ex.CAT_ORDER)}
        _gk = st.segmented_control("看哪一類", options=list(_grp), default="台股(高股息+主動)", key="exam_grp") or "台股(高股息+主動)"
        _fn = _ex.funnel(_grp[_gk])
        _flab = ["全部", "只看這一類", "這次空頭跌得比大盤少", "之前至少考過 1 次空頭", "不對稱 > 0(過四關)"]
        for _col_, _lab_, (_x, _codes_) in zip(st.columns(len(_fn)), _flab, _fn):
            _col_.metric(_lab_, f"{len(_codes_)} 檔")
        _pass = _fn[-1][1]
        _V = _T[_T.cat.isin(_grp[_gk])].copy()
        _V["過四關"] = _V.code.map(lambda c: "✅" if c in _pass else "")
        _V = _V.sort_values(["過四關", "asym"], ascending=[False, False])
        _show = pd.DataFrame({
            "過四關": _V["過四關"], "代號": _V.code, "名稱": _V["name"], "類別": _V.cat, "上市": _V.listed.dt.strftime("%Y/%m/%d"),
            "這次空頭%": (_V.bear * 100).round(1), "跌了大盤的%": (_V.dn * 100).round(0),
            "多頭%": (_V.bull * 100).round(1), "漲了大盤的%": (_V.up * 100).round(0), "不對稱(點)": (_V.asym * 100).round(0),
            "多頭起算": _V.bull_from.dt.strftime("%Y/%m/%d"),
            "以前空頭 少跌/考過": [f"{a}/{b}" if b else "第一次考" for a, b in zip(_V.n_less, _V.n_prior)],
            "四榜B年化%(至9/30)": ["未滿 1 年" if pd.isna(v) else f"{v * 100:.1f}" for v in _V.B1y]})
        st.dataframe(_show, hide_index=True, width="stretch", height=min(38 * (len(_show) + 1) + 4, 760))
        st.caption(f"四關:①只看這一類 ②這次空頭跌得比大盤少 ③之前至少考過 1 次空頭 ④不對稱 > 0(漲了大盤的 % − 跌了大盤的 %)。"
                   f"過關 {len(_pass)} 檔:{'、'.join(_pass) if _pass else '沒有'}。表格是這一類的全部 {len(_show)} 檔,沒過關的也列著。"
                   "「四榜B年化」是上市以來排名用的數字,放在旁邊對照:年化高的不一定抗跌。")

        # ── ③ 線圖只畫挑出來的 ──
        st.markdown("#### ③ 績效對決:只畫挑出來的幾檔,其他同類墊在後面當灰線")
        _c1, _c2 = st.columns([3, 2])
        _pick = _c1.multiselect("要上色的(最多 6 檔;預設=過四關的前 5 檔)", options=_ex.E.CODES, default=_pass[:5],
                                format_func=lambda c: f"{c} {_ex.E.NAMES[c]}", max_selections=6, key=f"exam_pick_{_gk}")
        _rk = _c2.segmented_control("從哪一天起算(基期 100)", options=["空頭起點", "多頭起點", "近 1 年"], default="空頭起點",
                                    key="exam_rng") or "空頭起點"
        _since = {"空頭起點": f"{_W['peak']:%Y-%m-%d}", "多頭起點": f"{_W['bull0']:%Y-%m-%d}",
                  "近 1 年": f"{_W['last'] - pd.Timedelta(days=365):%Y-%m-%d}"}[_rk]
        _bg = tuple(c for c in _V.code if c not in _pick)
        _L = _exam_lines(_exam_stamp(), tuple(_pick) + _bg, _since)
        _g = go.Figure()
        for _i, _c in enumerate(_bg):
            if _c in _L.columns:
                _g.add_scatter(x=_L.index, y=_L[_c], mode="lines", line=dict(color="#D5D8DD", width=1), hoverinfo="skip",
                               name="同類其他(灰)", legendgroup="bg", showlegend=_i == 0)
        _g.add_scatter(x=_L.index, y=_L["大盤"], name="大盤", line=dict(color="#111827", width=1.6, dash="dot"))
        _nav2 = _me.nav_series(since=_since) if _since >= str(d.get("inception") or "9999") else pd.DataFrame()
        if not _nav2.empty:
            _nav2 = _nav2[_nav2["date"] <= _L.index[-1]]
            for _ln, _st_ in {"我的ETF": dict(color="#00C2A8", width=3), "0050": dict(color="#3B82F6", width=1.5),
                              "00981A": dict(color="#F59E0B", width=2)}.items():
                if _ln in _nav2.columns:
                    _g.add_scatter(x=_nav2["date"], y=_nav2[_ln], name=_ln, line=_st_)
        for _c, _col in zip(_pick, ["#7C3AED", "#DB2777", "#16A34A", "#92400E", "#0E7490", "#B91C1C"]):
            if _c in _L.columns:
                _g.add_scatter(x=_L.index, y=_L[_c], name=f"{_c} {_ex.E.NAMES[_c]}", line=dict(color=_col, width=2))
        _g.update_layout(height=440, legend=dict(orientation="h", y=1.14), margin=dict(l=10, r=10, t=30, b=10),
                         plot_bgcolor="#FFFFFF", hovermode="x unified", xaxis=dict(gridcolor="#EEF0F3"), yaxis=dict(gridcolor="#EEF0F3"))
        st.plotly_chart(_g, width="stretch", key="exam_lines")
        _end = _L.iloc[-1]
        st.caption(f"自 {_L.index[0]} 起(基期 100)到 {_L.index[-1]}:大盤 {_end['大盤'] - 100:+.1f}%|"
                   + "|".join(f"{c} {_end[c] - 100:+.1f}%" for c in _pick if c in _L.columns and pd.notna(_end[c]))
                   + ("。我的ETF、0050、00981A 三條線和第一個分頁同一套(不含息)" if not _nav2.empty
                      else "。起算日早於我的ETF建倉日,所以這個區間不畫我的ETF")
                   + ";58 檔是含息(股息不再投入)。區間內才上市的,從上市首日的 100 開始畫。")

        # ── ④ 歷次空頭 ──
        with st.expander(f"④ 歷次空頭考卷:{int((_T.n_prior > 0).sum())} 檔以前考過,每次跌多少(第一列是大盤)"):
            _H = _T[_T.n_prior > 0].sort_values(["n_prior", "listed"], ascending=[False, True])
            _cols = _ex.PAST + [_ex.NOW]
            _mk = dict(_MK, **{_ex.NOW: _W["bear_m"]})
            _hh = pd.DataFrame([{"代號": "大盤", "名稱": "加權指數(不含息)", "類別": "", "少跌/考過(含這次)": "",
                                 **{k: round(_mk[k] * 100, 1) for k in _cols}}]
                               + [{"代號": r.code, "名稱": r["name"], "類別": r["cat"],
                                   "少跌/考過(含這次)": f"{r.n_less + int(r.bear > _W['bear_m'])}/{r.n_prior + 1}",
                                   **{k: (round(r[k] * 100, 1) if k != _ex.NOW else round(r.bear * 100, 1)) for k in _cols}}
                                  for _, r in _H.iterrows()])
            st.dataframe(_hh.style.format({k: "{:+.1f}" for k in _cols}, na_rep=""), hide_index=True, width="stretch",
                         height=min(38 * (len(_hh) + 1) + 4, 900))
            _ep = "、".join(n + " " + a[5:].replace("-", "/") + "→" + (b or f"{_W['low']:%Y-%m-%d}")[5:].replace("-", "/")
                           for n, a, b in _ex.EPISODES)
            st.caption("單位 %,含息。空白=那次空頭開始時還沒上市。2008、2011、2022 三次拖了半年以上,其餘都是 2~4 個月的急跌(2018 只跌 15%,算修正)。"
                       "區間:" + _ep)
        st.caption("限制:①這次空頭只有一個樣本,而且還沒確定落底(最低點會跟著資料每天重算);②主動式基金多半今年才上市,多頭只參加後半段,"
                   "「漲了大盤的幾 %」樣本很短;③債券、海外和台股大盤本來就不同步,跨類別比高低沒有意義,請分類看;④大盤不含息,ETF 含息,"
                   "ETF 在多頭那一欄略佔便宜。算法:etf58_exam.py。研究筆記,非投資建議。")

with tab_pick:
    st.caption("候選=最新月營收YoY>30%(00981A指紋)∩ 權證資金🔵佈局/🔥湧入 ∩ 體檢卡紅燈數——"
               "紅燈≥2 照家規不進。挑中的到「淨值與持股」頁籤手動加入。")
    if st.button("🔎 掃描候選池"):
        with st.spinner("跑三訊號交集…"):
            cand = _me.candidates()
        st.dataframe(cand, hide_index=True, width="stretch")

    # ── 🤖 量化重選(00409A 式,2026-10-05)─────────────────
    st.markdown("---")
    st.markdown("#### 🤖 量化重選(00409A 式全市場規則選股)")
    st.caption("篩選:站上60日線+距年高>-30%+日均額≥1億+最新季營益率>5%;"
               "評分=60日動能/月營收YoY/外資買超天 等權排名。**建議制**——按「採用」才改組。")
    _qc1, _qc2 = st.columns([1, 1])
    _qtop = _qc1.number_input("檔數", 5, 15, 10)
    _qcash = _qc2.number_input("現金保留 %", 0.0, 40.0, 10.0, step=5.0)
    if st.button("🤖 跑量化重選", key="qr_btn"):
        with st.spinner("全市場掃描+因子排名…"):
            st.session_state["qr_df"] = _me.quant_reselect(int(_qtop), float(_qcash))
    if "qr_df" in st.session_state and len(st.session_state["qr_df"]):
        _qdf = st.session_state["qr_df"]
        _cur = {c["code"] for c in d["constituents"] if c.get("code", "") != "CASH"}
        _new = set(_qdf["code"])
        _qdf2 = _qdf.copy()
        _qdf2["異動"] = _qdf2["code"].map(lambda c: "" if c in _cur else "🆕新增")
        st.dataframe(_qdf2, hide_index=True, width="stretch")
        _drop = _cur - _new
        if _drop:
            st.caption("將剔除:" + "、".join(sorted(_drop)))
        if st.button("✅ 採用此組合(改組生效並寫日誌)", key="qr_apply"):
            rows = [{"code": r["code"], "name": r["name"], "weight": r["weight"],
                     "thesis": f"量化重選 綜合分{r['綜合分']}"} for _, r in _qdf.iterrows()]
            if float(_qcash) > 0:
                rows.append({"code": "CASH", "name": "現金(乾火藥)",
                             "weight": float(_qcash), "thesis": "量化重選保留"})
            _me.set_constituents(rows, note=f"🤖量化重選 top{int(_qtop)} 現金{_qcash:g}%")
            st.success("已改組並寫入日誌。")
            st.rerun()

with tab_log:
    if d["log"]:
        for e in reversed(d["log"][-20:]):
            st.markdown(f"**{e['date']}**|{e['note']}|{'、'.join(e['constituents'])}")
            _df = e.get("diff") or {}
            _parts = []
            if _df.get("加"):
                _parts.append("🟢 加:" + "、".join(_df["加"]))
            if _df.get("刪"):
                _parts.append("🔴 刪:" + "、".join(_df["刪"]))
            if _df.get("調"):
                _parts.append("🔧 調:" + "、".join(_df["調"]))
            if _parts:
                st.caption("　→ " + "|".join(_parts))
    else:
        st.info("尚無改組紀錄。")

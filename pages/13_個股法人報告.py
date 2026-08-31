"""
頁面13:個股法人報告(六層框架 × 正反方對照 × 月營收推估)
================================================
方法論:金居六層分析師框架(驅動力→供需量化→營收模型→毛利分層
→EPS/目標價三情境→反方風險)+ 正反方對照表。
系統算可驗證的數學(出貨動能/財報結構/月營收推估),Claude 寫敘事。
補充資料(法說紀要/產能/產品佔比)貼進來會一起縫入推論。
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import page_header, inject_css, MUTED, RED, GREEN, GOLD, CYAN

st.set_page_config(page_title="個股法人報告", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("個股研究中心", "STOCK RESEARCH HUB", "🧾")

# 熱更新防護:雲端 git pull 後模組快取可能是舊版,缺新名字就 reload
import importlib
import analyst_report as _ar
if not hasattr(_ar, "generate_flash_note"):     # 熱更新防護:缺最新函式就 reload
    _ar = importlib.reload(_ar)
build_digest = _ar.build_digest
forecast_monthly = _ar.forecast_monthly
eps_scenarios = _ar.eps_scenarios
generate_report = _ar.generate_report
backcast_monthly = _ar.backcast_monthly
attribute_errors = _ar.attribute_errors
peer_compare = _ar.peer_compare
generate_industry_report = _ar.generate_industry_report

# 文章解讀「填入補充欄」的暫存(必須在 widget 建立前併入)
if st.session_state.get("extra_pending"):
    st.session_state["rpt_extra"] = (st.session_state.get("rpt_extra", "") + "\n"
                                     + st.session_state.pop("extra_pending")).strip()

c1, c2 = st.columns([1, 3])
code_in = c1.text_input("股票代碼", placeholder="4991", key="rpt_code")
extra_in = c2.text_area("補充資料(選填:法說紀要/產能/產品佔比/ASP——會縫進報告推論)",
                        height=90, key="rpt_extra")

with st.expander("📎 文章解讀(貼網址 → 個股情報卡,可一鍵填入補充欄)", expanded=False):
    import article_intel
    art_url = st.text_input("文章網址(優分析/鉅亨等)", key="hub_art_url")
    if st.button("🔍 解讀", key="hub_art_go") and art_url.strip().startswith("http"):
        with st.spinner("抓取並解讀中(約 30-60 秒)…"):
            rec = article_intel.ingest(art_url.strip())
        st.session_state["hub_art_rec"] = rec
    rec = st.session_state.get("hub_art_rec")
    if rec:
        st.markdown(f"**{rec['title']}**　·　{rec.get('source','')}")
        st.caption(rec.get("one_liner", ""))
        for s_ in rec.get("stocks", []):
            st.markdown(f"- **{s_.get('code','')} {s_.get('name','')}**"
                        f"({s_.get('stance','')}):{s_.get('summary','')}")
            for kp in s_.get("key_points", []):
                st.caption(f"　• {kp}")
        if st.button("⬇️ 把解讀重點填入補充欄", key="hub_art_fill"):
            bits = [f"文章解讀({rec.get('source','')}):{rec.get('one_liner','')}"]
            for s_ in rec.get("stocks", []):
                bits.append(f"{s_.get('code','')}{s_.get('name','')}:{s_.get('summary','')};"
                            + ";".join(s_.get("key_points", []) + s_.get("numbers", [])))
            st.session_state["extra_pending"] = "\n".join(bits)
            st.rerun()

code = code_in.strip().replace(".TW", "").replace(".TWO", "")

with st.expander("🎤 法說筆記(存下來,之後這檔與其族群的報告都會自動引用)", expanded=False):
    if not hasattr(_ar, "add_conf_note"):
        _ar = importlib.reload(_ar)
    if code:
        _notes = _ar.get_conf_notes(code)
        for n in _notes[:5]:
            st.markdown(f"- `{n['date']}` {n['note']}")
        _new_note = st.text_area("新增筆記(法說重點/質性判斷,例如「營收成長是漲價轉嫁,屬虛胖」)",
                                 height=70, key=f"conf_note_{code}")
        if st.button("💾 存筆記", key=f"conf_save_{code}") and _new_note.strip():
            _ar.add_conf_note(code, _new_note.strip())
            try:
                import subprocess as _sp
                _root = str(Path(__file__).parent.parent)
                _sp.run(["git", "add", "data/conf_notes.json"], cwd=_root, timeout=30)
                _sp.run(["git", "commit", "-q", "-m", f"docs: 法說筆記 {code}"], cwd=_root, timeout=30)
                _sp.run(["git", "push", "-q", "origin", "main"], cwd=_root, timeout=60)
            except Exception:
                pass
            st.success("已存(git 同步雲端);之後產生報告會自動縫進推論")
            st.rerun()
    else:
        st.caption("先輸入股票代碼")

if not code.isdigit():
    st.info("輸入代碼後自動載入:出貨動能、財報結構、月營收推估;再一鍵產生法人報告。")
    st.stop()


@st.cache_data(ttl=3600, show_spinner="抓取財務資料中…")
def _digest(c):
    return build_digest(c)

d = _digest(code)
mon: pd.DataFrame = d["monthly"]
q: pd.DataFrame = d["quarterly"]
if mon.empty:
    st.warning("抓不到月營收資料(FinMind 限流或代碼有誤),稍後再試。")
    st.stop()

st.caption(f"**{d['code']} {d['name']}**　{d['price']}　|　{d['chips'] or ''}")

# ── ① 出貨/營收動能圖(歷史+推估) ──
st.markdown("### 📦 出貨與營收動能")
ass_c = st.columns([1, 1, 1, 3])
default_assume = d["assume"]
ov = {}
ov["保守YoY%"] = ass_c[0].number_input("保守YoY%", value=float(default_assume.get("保守YoY%", 0)), step=5.0)
ov["中性YoY%"] = ass_c[1].number_input("中性YoY%", value=float(default_assume.get("中性YoY%", 10)), step=5.0)
ov["樂觀YoY%"] = ass_c[2].number_input("樂觀YoY%", value=float(default_assume.get("樂觀YoY%", 20)), step=5.0)
ass_c[3].caption("推估=去年同月×(1+YoY)。預設值由近月動能自動導出(保守=近6月最低/中性=近3月中位/樂觀=近3月最高),可手動改。")

fc, _ = forecast_monthly(code, months=6, override=ov)
eps_sc = eps_scenarios(code, fc)

hist = mon.tail(24)
fig = go.Figure()
fig.add_trace(go.Bar(x=hist["ym"], y=hist["revenue"], name="月營收(百萬)",
                     marker_color=CYAN, opacity=0.75))
if not fc.empty:
    for col, cc, dashed in [("保守", MUTED, "dot"), ("中性", GOLD, "dash"), ("樂觀", RED, "dash")]:
        fig.add_trace(go.Scatter(x=fc["月份"], y=fc[col], name=f"推估-{col}",
                                 mode="lines+markers", line=dict(color=cc, dash=dashed, width=2)))
fig.add_trace(go.Scatter(x=hist["ym"], y=hist["yoy%"], name="YoY%", yaxis="y2",
                         mode="lines", line=dict(color=GREEN, width=1.5)))
fig.update_layout(height=380, template="plotly_dark", paper_bgcolor=THEME["bg"],
                  plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=12),
                  margin=dict(l=10, r=10, t=30, b=10),
                  yaxis=dict(title="月營收(百萬)", gridcolor=THEME["grid"]),
                  yaxis2=dict(title="YoY%", overlaying="y", side="right", showgrid=False),
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, width="stretch")

# 月營收明細表(key 股號就有:營收/MoM/YoY/累計YoY)
with st.expander("📅 月營收明細表(近 18 月)", expanded=False):
    tbl = mon.tail(18).copy()
    tbl["MoM%"] = tbl["revenue"].pct_change() * 100
    cur_year = tbl["ym"].iloc[-1][:4]
    ytd = mon[mon["ym"].str.startswith(cur_year)]["revenue"].sum()
    ytd_prev = mon[mon["ym"].str.startswith(str(int(cur_year) - 1))].head(
        len(mon[mon["ym"].str.startswith(cur_year)]))["revenue"].sum()
    tbl = tbl.rename(columns={"ym": "月份", "revenue": "營收(百萬)", "yoy%": "YoY%"})
    tbl["營收(百萬)"] = tbl["營收(百萬)"].round(1)

    def _c(v):
        if isinstance(v, float):
            return f"color:{'#FF4D6D' if v > 0 else '#2BE4A8'}"
        return ""
    st.dataframe(
        tbl[["月份", "營收(百萬)", "MoM%", "YoY%"]].style
           .map(_c, subset=["MoM%", "YoY%"])
           .format({"營收(百萬)": "{:,.1f}", "MoM%": "{:+.1f}%", "YoY%": "{:+.1f}%"}),
        width="stretch", hide_index=True, height=400)
    if ytd_prev > 0:
        st.caption(f"{cur_year} 年累計 {ytd:,.0f} 百萬,累計 YoY {(ytd/ytd_prev-1)*100:+.1f}%")

fc_col, eps_col = st.columns([3, 2])
with fc_col:
    if not fc.empty:
        st.markdown("**未來 6 個月營收推估(百萬)**")
        st.dataframe(fc, width="stretch", hide_index=True)
with eps_col:
    if not eps_sc.empty:
        st.markdown("**EPS 情境(近2季淨利率±3pp)**")
        st.dataframe(eps_sc, width="stretch", hide_index=True)

# ── ①.3 融資融券日表 + 每日結論(含期貨結算對應) ──
st.markdown("### 🏦 融資融券(每日結論)")
mst = _ar.margin_short_table(code, days=20)
if not mst.empty:
    _mst_date = mst["日期"].iloc[0]
    st.caption(f"資料日:**{_mst_date}**(融資融券為 TWSE 盤後 21:00 左右公布;"
               "系統傍晚時段每 2 小時自動補抓,白天看到前一日屬正常)")
    for line in _ar.margin_conclusion(mst):
        st.markdown(f"- {line}")
    def _c_chg(v):
        if isinstance(v, (int, float)) and pd.notna(v):
            return f"color:{'#FF4D6D' if v > 0 else ('#2BE4A8' if v < 0 else '#647B9C')}"
        return ""
    st.dataframe(
        mst.style.map(_c_chg, subset=[c for c in ["融資增減", "融券增減"] if c in mst.columns])
           .format({"融資餘額(張)": "{:,.0f}", "融資增減": "{:+,.0f}",
                    "融券餘額(張)": "{:,.0f}", "融券增減": "{:+,.0f}",
                    "維持率(推估)%": "{:.1f}", "券資比%": "{:.1f}", "收盤": "{:.1f}"},
                   na_rep="—"),
        width="stretch", hide_index=True, height=420)
    st.caption("維持率為推估(收盤÷(0.6×MA60成本代理),與總經頁同口徑),非券商整戶真值。")
else:
    st.caption("無融資融券資料(可能非信用交易股)。")

# ── ①.35 重大訊息(MOPS) ──
with st.expander("📢 重大訊息(今年+去年,🔴=關鍵事項)", expanded=False):
    ann = _ar.fetch_announcements(code)
    if not ann.empty:
        n_imp = (ann["重要"] == "🔴").sum()
        st.caption(f"共 {len(ann)} 則,關鍵事項 {n_imp} 則(CB/增減資/財報/處置/裁罰等)")
        st.dataframe(ann, width="stretch", hide_index=True,
                     height=min(420, len(ann) * 36 + 60))
    else:
        st.caption("查無重大訊息(或 MOPS 暫時擋抓)。")

# ── ①.4 全年估值:H1 實績 + H2 推估(半年報視角) ──
st.markdown("### ⚖️ 全年估值(H1 實績 + H2 推估)")
# 自結 H1 輸入(公司公告自結時先填,財報公布後自動改用實績)
sr1, sr2 = st.columns([1.5, 4.5])
from twtime import now_tw as _ntw
_cur_year = _ntw().year
_self_now = _ar.get_self_h1(code, _cur_year)
self_in = sr1.number_input(f"自結 {_cur_year}H1 EPS(選填)",
                           value=float(_self_now or 0.0), step=0.05, format="%.2f",
                           key=f"self_h1_{code}")
if sr1.button("💾 存自結", key=f"self_save_{code}") and self_in > 0:
    _ar.set_self_h1(code, _cur_year, self_in)
    st.rerun()
sr2.caption("公司自結常早於正式財報(8/14)——填一次會記住;正式財報上架後自動改用實績並對答案。")

hv = _ar.h1_valuation(code)
if hv:
    q2_txt = (f"{hv['q2']:.2f}" if hv["q2"] is not None else "未公布")
    if hv.get("q2_src"):
        q2_txt += f"({hv['q2_src']})"
    hc1, hc2, hc3, hc4 = st.columns(4)
    hc1.metric(f"{hv['year']} Q1 EPS(實績)", f"{hv['q1']:.2f}")
    hc2.metric("Q2 EPS", q2_txt)
    hc3.metric("H1 合計", f"{hv['h1']:.2f}")
    if hv.get("implied_pe"):
        hc4.metric("現價隱含 PE(中性FY)", f"{hv['implied_pe']:.1f}x",
                   help=f"現價 {hv['price']:.1f} ÷ 中性情境全年EPS")
    st.dataframe(hv["table"], width="stretch", hide_index=True)
    for n in hv["notes"]:
        st.caption(f"※ {n}")
    st.caption("讀法:H1 是已落袋的實績(錨),只賭 H2——比純推估的年化EPS可信;"
               "×15/×20/×25/×30 為本益比階梯目標價,對照現價看市場給的定價站在哪一格。"
               "季報公布時點:Q2=8/14 前、Q3=11/14 前,公布後本表自動改用實績。")
else:
    st.caption("H1 估值需要今年 Q1 財報與月營收資料,目前不足。")

# ── ①.5 模型回測與誤差歸因 ──
st.markdown("### 🔬 模型回測(用當時資訊回推 vs 實際)")
bc = backcast_monthly(code, lookback=12)
if not bc.empty:
    mae = bc["誤差%"].abs().mean()
    hit5 = (bc["誤差%"].abs() <= 5).mean() * 100
    hit10 = (bc["誤差%"].abs() <= 10).mean() * 100
    st.caption(f"walk-forward 回測近 {len(bc)} 個月(預測=去年同月×前3月YoY中位,不偷看未來):"
               f"平均絕對誤差 **{mae:.1f}%**,±5%內 **{hit5:.0f}%**,±10%內 **{hit10:.0f}%**")
    figb = go.Figure()
    figb.add_trace(go.Scatter(x=bc["月份"], y=bc["實際"], name="實際",
                              mode="lines+markers", line=dict(color=CYAN, width=2.5)))
    figb.add_trace(go.Scatter(x=bc["月份"], y=bc["模型"], name="模型回推",
                              mode="lines+markers", line=dict(color=GOLD, dash="dash", width=2)))
    figb.add_trace(go.Bar(x=bc["月份"], y=bc["誤差%"], name="誤差%", yaxis="y2",
                          marker_color=[RED if abs(v) > 10 else (GOLD if abs(v) > 5 else GREEN)
                                        for v in bc["誤差%"]], opacity=0.5))
    figb.update_layout(height=340, template="plotly_dark", paper_bgcolor=THEME["bg"],
                       plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=11),
                       margin=dict(l=10, r=10, t=25, b=10),
                       yaxis=dict(title="月營收(百萬)", gridcolor=THEME["grid"]),
                       yaxis2=dict(title="誤差%", overlaying="y", side="right",
                                   showgrid=False, zeroline=True),
                       legend=dict(orientation="h", y=1.14))
    st.plotly_chart(figb, width="stretch")
    with st.expander("誤差明細表"):
        st.dataframe(bc, width="stretch", hide_index=True)
    if st.button("🧠 誤差歸因(找原因:新聞/法說/財報看哪裡)", key="attr_go"):
        with st.spinner("分析誤差來源中(約 30-60 秒)…"):
            attr = attribute_errors(code, bc, extra=extra_in)
        st.session_state["last_attr"] = attr
        st.session_state["last_attr_code"] = code
    if (st.session_state.get("last_attr")
            and st.session_state.get("last_attr_code") == code):
        st.markdown(st.session_state["last_attr"])
    st.caption("誤差判讀指南:**連續同向偏低**=動能模型抓不到轉折(放量/砍單)→看法說產能與月營收公告備註;"
               "**單月大誤差**=一次性(節慶/出貨遞延)→看財報存貨與業外;"
               "**誤差伴隨毛利率跳動**=產品組合轉換→看公開說明書產品別佔比。")
else:
    st.caption("月營收歷史不足 18 個月,無法回測。")

# ── ② 財報結構 ──
st.markdown("### 🧮 財報結構(毛利分層的證據)")
if not q.empty:
    qc1, qc2 = st.columns([3, 2])
    with qc1:
        figm = go.Figure()
        for col, cc in [("毛利率%", RED), ("營益率%", GOLD), ("淨利率%", CYAN)]:
            if col in q.columns:
                figm.add_trace(go.Scatter(x=q["季度"], y=q[col], name=col,
                                          mode="lines+markers", line=dict(color=cc, width=2)))
        figm.update_layout(height=300, template="plotly_dark", paper_bgcolor=THEME["bg"],
                           plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=11),
                           margin=dict(l=10, r=10, t=10, b=10),
                           yaxis=dict(title="%", gridcolor=THEME["grid"]),
                           legend=dict(orientation="h", y=1.15))
        st.plotly_chart(figm, width="stretch")
    with qc2:
        st.dataframe(q.tail(8), width="stretch", hide_index=True, height=300)

# ── ②.5 同業比較(產業寫作模式的素材) ──
st.markdown("### ⚔️ 同業比較")
# 預設帶入:①概念族群成員 ②否則官方產業別中市值最接近的3檔
_default_peers = ""
_peer_src = ""
try:
    from theme_groups import THEME_GROUPS
    for _g, _cs in THEME_GROUPS.items():
        if code in _cs:
            _default_peers = ",".join([c for c in _cs if c != code][:3])
            _peer_src = f"概念族群「{_g}」"
            break
except Exception:
    pass
if not _default_peers:
    try:
        from fundamentals import shares_map
        sl = pd.read_csv(Path(__file__).parent.parent / "data" / "stock_list.csv",
                         encoding="utf-8-sig", dtype=str)
        my = sl[sl["code"] == code]
        if not my.empty:
            sec = my["sector"].iloc[0]
            sm = shares_map()

            @st.cache_data(ttl=3600)
            def _close_map():
                import glob as _g2
                out = {}
                for f in _g2.glob(str(Path(__file__).parent.parent / "data" / "*.T*.csv")):
                    c2 = Path(f).stem.split(".")[0]
                    try:
                        with open(f, "rb") as fh:
                            fh.seek(-120, 2)
                            last = fh.read().decode("utf-8", "replace").strip().splitlines()[-1]
                        out[c2] = float(last.split(",")[4])
                    except Exception:
                        continue
                return out

            cm = _close_map()
            mycap = cm.get(code, 0) * sm.get(code, 0)
            cands = []
            for _, r in sl[(sl["sector"] == sec) & (sl["code"] != code)].iterrows():
                cap = cm.get(r["code"], 0) * sm.get(r["code"], 0)
                if cap > 0 and mycap > 0:
                    cands.append((abs(cap - mycap), r["code"]))
            _default_peers = ",".join(c for _, c in sorted(cands)[:3])
            _peer_src = f"官方產業「{sec}」市值最接近"
    except Exception:
        pass
peers_in = st.text_input(f"比較對象(逗號分隔;自動帶入:{_peer_src or '無'})",
                         value=_default_peers, key=f"rpt_peers_{code}")
peers = [p.strip() for p in peers_in.replace("、", ",").split(",") if p.strip().isdigit()]
if peers:
    rev_cmp, gm_cmp = peer_compare([code] + peers)
    pc1, pc2 = st.columns(2)
    with pc1:
        if not rev_cmp.empty:
            figr = go.Figure()
            for col in rev_cmp.columns[1:]:
                figr.add_trace(go.Scatter(x=rev_cmp["ym"], y=rev_cmp[col], name=col,
                                          mode="lines", line=dict(width=2)))
            figr.update_layout(title="月營收指數化(24月前=100)——誰先創高?",
                               height=300, template="plotly_dark", paper_bgcolor=THEME["bg"],
                               plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=11),
                               margin=dict(l=10, r=10, t=40, b=10),
                               legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(figr, width="stretch")
    with pc2:
        if not gm_cmp.empty:
            figg = go.Figure()
            for col in gm_cmp.columns[1:]:
                figg.add_trace(go.Scatter(x=gm_cmp["季度"].astype(str), y=gm_cmp[col], name=col,
                                          mode="lines+markers", line=dict(width=2)))
            figg.update_layout(title="季度毛利率%對比——產品結構的成績單",
                               height=300, template="plotly_dark", paper_bgcolor=THEME["bg"],
                               plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"], size=11),
                               margin=dict(l=10, r=10, t=40, b=10),
                               legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(figg, width="stretch")

# ── ③ 報告產生(兩種模式) ──
st.markdown("### 🧾 產生報告")
mode = st.radio("報告模式", ["月營收快評(晨報式:公布數字vs模型預期→歸因→展望,最快)",
                          "產業比較型(優分析風:問句標題/產品結構→客群→週期位置/教方法論)",
                          "法人六層型(驅動力→估值三情境→正反方對照表)"],
                horizontal=False, key="rpt_mode")

# 雲端(資料包模式)沒有 Claude 訂閱——與其讓使用者按下去才失敗,先講清楚
_cloud_no_engine = False
try:
    import auto_refresh as _arf
    from apikey import get_key as _getkey
    _cloud_no_engine = _arf._pack_mode() and not _getkey()
except Exception:
    pass

if _cloud_no_engine:
    st.info("☁️ **雲端顯示模式**:雲端沒有 Claude 引擎,報告請在**本機**產生——"
            "產生後會自動發佈到「📰 研究文章」並同步上雲,這裡就能看。"
            "(若想在雲端直接產生:Streamlit Secrets 設 `ANTHROPIC_API_KEY`)")
if st.button("🖋️ 產生報告", type="primary", key="rpt_go", disabled=_cloud_no_engine):
    with st.spinner("撰寫報告中(約 30-90 秒)…"):
        if mode.startswith("月營收快評"):
            rpt = _ar.generate_flash_note(code, extra=extra_in)
        elif mode.startswith("產業比較"):
            rpt = generate_industry_report(code, peers, extra=extra_in)
        else:
            rpt = generate_report(code, extra=extra_in)
    st.session_state["last_rpt"] = rpt
    st.session_state["last_rpt_code"] = code
    # 存進研究文章庫(頁12「研究文章」可像網站一樣瀏覽)
    if rpt and not rpt.startswith("（"):
        _mode_tag = ("月營收快評" if mode.startswith("月營收快評")
                     else ("產業比較" if mode.startswith("產業比較") else "法人六層"))
        fn = _ar.save_article(code, d.get("name", ""), _mode_tag, rpt)
        gmsg = _ar.git_publish(fn)
        st.success(f"已發佈到「📰 研究文章」:{fn}｜{gmsg}")

if st.session_state.get("last_rpt") and st.session_state.get("last_rpt_code") == code:
    st.markdown("---")
    st.markdown(st.session_state["last_rpt"])
    st.download_button("⬇️ 下載報告(Markdown)",
                       st.session_state["last_rpt"].encode("utf-8"),
                       file_name=f"report_{code}.md", mime="text/markdown", key="rpt_dl")

# ── ④ 模型預實追蹤(預測 vs 實際,自動對答案) ──
st.markdown("### 📋 模型預實追蹤")
from model_track import add_prediction, check_all

tc = st.columns([1.2, 1, 1, 1.4, 1])
mt_metric = tc[0].selectbox("指標", ["monthly_rev", "quarterly_rev", "quarterly_gm"],
                            format_func=lambda m: {"monthly_rev": "月營收(百萬)",
                                                   "quarterly_rev": "季營收(百萬)",
                                                   "quarterly_gm": "季毛利率(%)"}[m],
                            key="mt_metric")
mt_period = tc[1].text_input("期間", placeholder="2026-07 或 2026-Q3", key="mt_period")
mt_val = tc[2].number_input("預測值", value=0.0, step=1.0, key="mt_val")
mt_note = tc[3].text_input("備註", key="mt_note")
if tc[4].button("➕ 存預測", key="mt_add"):
    if mt_period.strip() and mt_val:
        add_prediction(code, mt_metric, mt_period.strip(), mt_val, mt_note)
        st.success("已存,公布後自動對答案")
        st.rerun()

# ── 損益表級 預測 vs 實際(整張 P&L 對照)──
with st.expander("📑 損益表級 預測 vs 實際(系統自動預測,財報公布自動對照)", expanded=False):
    from model_track import set_pl_forecast, get_pl_forecasts, pl_compare, auto_pl_forecast
    ac1, ac2 = st.columns([1.2, 3])
    auto_period = ac1.text_input("自動預測期間", placeholder="2026-Q3", key="pl_auto_period")
    if ac2.button("🤖 系統自動產生預測(免手填;財報公布後自動吸收新資訊修正下一季)",
                  key="pl_auto_go") and auto_period.strip():
        f = auto_pl_forecast(code, auto_period.strip())
        if f:
            st.success(f"已產生:{f['note']}")
            st.rerun()
        else:
            st.warning("資料不足(需月營收+至少3季財報)或該期已公布(凍結)")
    st.caption("修正機制:①營收混用已公布月份實際 ②毛利率錨定最新實際季+趨勢(±2pp截幅)"
               "③費用率/稅率滾動近4季——每次財報對完答案,下一季自動重算;已開獎期間凍結不改。"
               "手動預測(如券商版)可與系統版並存對照:")
    pc = st.columns([1, 1, 1, 1, 1, 1.4, 1])
    pl_period = pc[0].text_input("期間", placeholder="2026-Q3", key="pl_period")
    pl_rev = pc[1].number_input("營收(百萬)", value=0.0, step=10.0, key="pl_rev")
    pl_gm = pc[2].number_input("毛利率%", value=0.0, step=0.5, key="pl_gm")
    pl_opex = pc[3].number_input("營業費用(百萬)", value=0.0, step=5.0, key="pl_opex")
    pl_nonop = pc[4].number_input("業外(百萬)", value=0.0, step=1.0, key="pl_nonop")
    pl_note = pc[5].text_input("來源備註", placeholder="本模型/群益…", key="pl_note")
    if pc[6].button("💾 存", key="pl_save") and pl_period.strip() and pl_rev:
        set_pl_forecast(code, pl_period.strip(), pl_rev, pl_gm, pl_opex,
                        pl_nonop, 20.0, pl_note)
        st.success("已存;該季財報公布後下方自動出整表對照")
        st.rerun()
    st.caption("成本/營益/稅前/淨利由 營收×毛利率−費用+業外×(1−稅率20%) 自動推導;"
               "誤差=實際−預測(毛利率為 pp)。")
    for per, fc in sorted(get_pl_forecasts(code).items(), reverse=True):
        cmp_df = pl_compare(code, per)
        st.markdown(f"**{per}**(預測來源:{fc.get('note') or '未註明'})")
        if cmp_df is not None:
            st.dataframe(cmp_df, width="stretch", hide_index=True)
        else:
            st.caption("⏳ 實際財報未公布(季報:5/15、8/14、11/14、3/31)")

trk = check_all(code)
if not trk.empty:
    st.dataframe(trk, width="stretch", hide_index=True)
    st.caption("燈號:誤差 ±5% 🟢 | ±10% 🟡 | 更大 🔴(毛利率用 ±2pp/±4pp);"
               "月營收每月10日前公布、季報 5/15・8/14・11/14・3/31 前公布,系統自動抓新資料比對。")
else:
    st.caption("此股尚無追蹤中的預測——把模型的關鍵數字存進來,公布後自動對答案。")

st.caption("方法論:六層分析師框架(驅動力/供需量化/營收模型/毛利分層/估值三情境/反方風險)+"
           "正反方對照表。推估=情境試算,非投資建議;關鍵數字請自行覆核。")

"""頁27 — 個股戰情室:一屏儀表牆(仿 ECF 版式,拼裝系統既有引擎)。
K線/決策核心/五維雷達/體檢燈/法人計量/權證佈局/買區停損/主力語意 + KD/MACD/分軌圖。"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="個股戰情室", page_icon="🎯", layout="wide")

ROOT = Path(__file__).parent.parent

st.title("🎯 個股戰情室")
_tc, _tl = st.columns([3, 1])
with _tc:
    code = st.text_input("代號", value=st.session_state.get("war_code", "2330"), key="war_code_in")
with _tl:
    st.page_link("pages/28_公司快照.py", label="🏢 公司快照(基本面第一頁)")
    if st.button("⚡ 一鍵快分析(引擎寫報告,約1分鐘)", key="war_quick"):
        with st.spinner("價量+體檢+權證+財報+新聞 → 引擎撰寫中…"):
            try:
                import analyst_report as _ar
                import importlib as _il
                _ar = _il.reload(_ar)
                _txt = _ar.generate_quick_analysis(code.strip())
                if _txt.startswith("（"):
                    st.warning(_txt)
                else:
                    _fn = _ar.save_article(code.strip(), "", "快分析", _txt)
                    st.success(f"已存入文章庫:{_fn}(下方「相關報告」頁籤可看)")
                    st.markdown(_txt)
            except Exception as _e:
                st.error(f"快分析失敗:{_e}")
if not code.strip():
    st.stop()
code = code.strip()


@st.cache_data(ttl=900, show_spinner="組裝儀表牆…")
def _assemble(c: str, ver: int = 2):
    import pretrade
    import warrant_flow as wf
    import my_etf as me
    import weekly_review as wr
    out = {}
    d = pretrade._price_df(c)
    if d is None or len(d) < 80:
        return None
    d = d.reset_index(drop=True)
    out["px"] = d.tail(90).copy()
    cl = d["Close"]
    out["close"] = float(cl.iloc[-1])
    out["chg"] = float(cl.iloc[-1] / cl.iloc[-2] - 1) * 100
    out["vol"] = float(d["Volume"].iloc[-1] / 1000)
    out["ma20"] = float(cl.rolling(20).mean().iloc[-1])
    out["ma60"] = float(cl.rolling(60).mean().iloc[-1])
    out["hi252"] = float(cl.tail(252).max())
    # KD / MACD
    low9 = d["Low"].rolling(9).min()
    high9 = d["High"].rolling(9).max()
    rsv = (cl - low9) / (high9 - low9).replace(0, np.nan) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    dd_ = k.ewm(com=2, adjust=False).mean()
    out["kd"] = pd.DataFrame({"Date": d["Date"], "K": k, "D": dd_}).tail(90)
    e12 = cl.ewm(span=12, adjust=False).mean()
    e26 = cl.ewm(span=26, adjust=False).mean()
    dif = e12 - e26
    macd = dif.ewm(span=9, adjust=False).mean()
    out["macd"] = pd.DataFrame({"Date": d["Date"], "DIF": dif, "MACD": macd,
                                "OSC": dif - macd}).tail(90)
    # 儀表們
    out["hc"] = pretrade.health_check(c)
    out["reds"] = sum(1 for x in out["hc"]["rows"] if x["燈"] == "🔴")
    try:
        out["sf"] = wf.sustained_flow(c)
    except Exception:
        out["sf"] = {}
    out["bz"] = me.buy_zone(c)
    out["stop"] = wr.stop_suggestion(c)
    # 法人10日
    try:
        i = pd.read_csv(ROOT / "data" / "institutional" / f"{c}_inst.csv").sort_values("date").tail(10)
        out["inst"] = pd.DataFrame({
            "date": i["date"].astype(str).str[5:],
            "外資": i["外陸資買賣超股數(不含外資自營商)"].fillna(0) / 1000,
            "投信": i["it_net"].fillna(0) / 1000})
    except Exception:
        out["inst"] = pd.DataFrame()
    # 營收
    try:
        h = pd.read_csv(ROOT / "data" / "_rev_history.csv", dtype={"code": str})
        g = h[h.code == c].tail(1)
        out["yoy"] = float(g["yoy"].iloc[0]) if len(g) else None
    except Exception:
        out["yoy"] = None
    # 大戶Δ
    try:
        pan = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv")
        s = pan[c].dropna().tail(4)
        out["bigd"] = round(float(s.iloc[-1] - s.iloc[0]), 2) if len(s) >= 2 else None
    except Exception:
        out["bigd"] = None
    try:
        dr = pd.read_csv(ROOT / "data" / "inst_dump_rate.csv", dtype={"code": str})
        hit = dr[dr["code"] == c]
        out["dump"] = float(hit["dump_rate"].iloc[0]) if len(hit) else None
    except Exception:
        out["dump"] = None
    # 五維評分(0-100)
    fi5 = 0
    if not out["inst"].empty:
        fi5 = float(out["inst"]["外資"].tail(5).sum() + out["inst"]["投信"].tail(5).sum())
    trend = 50 + (25 if out["close"] > out["ma20"] else -25) + (25 if out["ma20"] > out["ma60"] else -25)
    mom = min(100, max(0, 50 + (out["chg"] * 5)))
    chips = 50 + (20 if fi5 > 0 else -20) + (30 if (out["bigd"] or 0) > 0.3 else (-30 if (out["bigd"] or 0) < -0.3 else 0))
    fund = 50 if out["yoy"] is None else min(100, max(0, 50 + out["yoy"] / 2))
    safe = max(0, 100 - (out["dump"] or 25) - out["reds"] * 15)
    out["scores"] = {"趨勢": trend, "動能": mom, "籌碼": chips, "基本面": fund, "安全度": safe}
    total = int(np.mean(list(out["scores"].values())))
    out["total"] = total
    out["grade"] = "A" if total >= 70 else ("B" if total >= 55 else ("C" if total >= 40 else "D"))
    # 主力語意(規則式)
    if fi5 > 0 and (out["bigd"] or 0) > 0.3:
        verdict, tag = "吸籌佈局", "🟢"
    elif fi5 < 0 and (out["bigd"] or 0) < -0.3:
        verdict, tag = "調節減碼", "🟠"
    elif fi5 > 0 and (out["bigd"] or 0) < -0.3:
        verdict, tag = "大戶倒給法人?觀察", "🟡"
    elif out["reds"] >= 2:
        verdict, tag = "風險警戒", "🔴"
    else:
        verdict, tag = "觀望整理", "⚪"
    out["verdict"], out["tag"] = verdict, tag
    return out


A = _assemble(code)
if A is None:
    st.warning("無此代號的價格資料。")
    st.stop()

sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
name = dict(zip(sl["code"], sl["name"])).get(code, "")

# ── 頂部即時列 ──
h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 1, 1, 1, 1])
h1.markdown(f"## {code} {name}")
h2.metric("收盤", f"{A['close']:.1f}", f"{A['chg']:+.2f}%")
h3.metric("成交(張)", f"{A['vol']:,.0f}")
h4.metric("綜合評分", f"{A['grade']}|{A['total']}")
h5.metric("體檢紅燈", A["reds"])
h6.metric("距年高", f"{(A['close']/A['hi252']-1)*100:+.0f}%")

# ── Row1:K線 | 決策核心 | 雷達 ──
r1a, r1b, r1c = st.columns([2.2, 1.1, 1.1])
with r1a:
    px = A["px"]
    fig = go.Figure()
    fig.add_candlestick(x=px["Date"], open=px["Open"], high=px["High"],
                        low=px["Low"], close=px["Close"],
                        increasing_line_color="#D64545", decreasing_line_color="#2E9E5B")
    ma20 = px["Close"].rolling(20).mean()
    fig.add_scatter(x=px["Date"], y=ma20, line=dict(color="#3B82F6", width=1.4), name="MA20")
    if A["bz"]:
        fig.add_hrect(y0=A["bz"]["lo"], y1=A["bz"]["hi"], fillcolor="#00C2A8",
                      opacity=0.12, line_width=0)
    fig.update_layout(height=330, showlegend=False, xaxis_rangeslider_visible=False,
                      margin=dict(l=8, r=8, t=8, b=8))
    st.plotly_chart(fig, width="stretch")
    st.caption("綠帶=建議買區(20日高×0.87~0.92)")
with r1b:
    st.markdown(f"#### 🧠 決策核心 {A['tag']}")
    _rows = [("趨勢", "多頭排列" if A["close"] > A["ma20"] > A["ma60"] else
              ("均線糾結" if A["close"] > A["ma60"] else "空方架構")),
             ("主力行為", A["verdict"]),
             ("權證資金", str(A["sf"].get("verdict", "樣本不足"))[:16] if A["sf"] else "無權證"),
             ("隔日沖風險", f"{A['dump']:.0f}%" if A["dump"] is not None else "無樣本"),
             ("支撐(買區)", f"{A['bz']['lo']}~{A['bz']['hi']}" if A["bz"] else "—"),
             ("停損建議", A["stop"].get("建議", "—") if A["stop"] else "—")]
    try:
        from tp_radar import latest_for as _tp_latest
        _tp = _tp_latest(code)
        if _tp and _tp.get("目標價") == _tp.get("目標價"):   # 非NaN
            _gap = (_tp["目標價"] / A["close"] - 1) * 100
            _rows.append(("分析師目標價",
                          f"{_tp['方向']}{_tp['目標價']:g} 距現價{_gap:+.0f}%({_tp['日期'][5:]})"))
    except Exception:
        pass
    for k_, v_ in _rows:
        st.markdown(f"<div style='display:flex;justify-content:space-between;"
                    f"border-bottom:1px solid #26303f;padding:4px 2px'>"
                    f"<span style='color:#8b98a8;font-size:.85rem'>{k_}</span>"
                    f"<b style='font-size:.88rem'>{v_}</b></div>", unsafe_allow_html=True)
with r1c:
    sc = A["scores"]
    fig = go.Figure(go.Scatterpolar(r=list(sc.values()) + [list(sc.values())[0]],
                                    theta=list(sc.keys()) + [list(sc.keys())[0]],
                                    fill="toself", line=dict(color="#00C2A8")))
    fig.update_layout(height=300, polar=dict(radialaxis=dict(range=[0, 100], showticklabels=False)),
                      margin=dict(l=30, r=30, t=30, b=20), showlegend=False,
                      title=dict(text=f"綜合 {A['grade']}({A['total']}/100)", font=dict(size=14)))
    st.plotly_chart(fig, width="stretch")

# ── Row2:體檢燈 | 法人計量 | 主力語意大字 ──
r2a, r2b, r2c = st.columns([1.3, 1.6, 1.1])
with r2a:
    st.markdown("#### 🩺 體檢七燈")
    for row in A["hc"]["rows"]:
        st.markdown(f"{row['燈']} **{row['項目']}**|{row['讀數']}")
with r2b:
    st.markdown("#### 🏦 法人 10 日計量(張)")
    ins = A["inst"]
    if not ins.empty:
        fig = go.Figure()
        fig.add_bar(x=ins["date"], y=ins["外資"], name="外資", marker_color="#3B82F6")
        fig.add_bar(x=ins["date"], y=ins["投信"], name="投信", marker_color="#8B5CF6")
        fig.update_layout(height=240, barmode="group", margin=dict(l=8, r=8, t=8, b=8),
                          legend=dict(orientation="h", y=1.15))
        fig.update_xaxes(type="category")     # 「09-18」別被當成2009年
        st.plotly_chart(fig, width="stretch")
with r2c:
    st.markdown("#### 🗣️ 主力語意")
    _color = {"🟢": "#2E9E5B", "🟠": "#E8873A", "🟡": "#D6B60A",
              "🔴": "#E5484D", "⚪": "#8b98a8"}[A["tag"]]
    st.markdown(f"<div style='background:#141a24;border:1px solid {_color};border-radius:12px;"
                f"padding:22px;text-align:center'><div style='font-size:1.9rem;font-weight:800;"
                f"color:{_color}'>{A['verdict']}</div>"
                f"<div style='color:#8b98a8;font-size:.8rem;margin-top:6px'>"
                f"規則式綜合(法人5日+大戶4週+體檢),非AI預測</div></div>",
                unsafe_allow_html=True)
    if A["yoy"] is not None:
        st.metric("最新月營收 YoY", f"{A['yoy']:+.1f}%")

# ── Row3:圖表頁籤 ──
t_kd, t_macd, t_chip, t_rep = st.tabs(["📈 KD+MA", "📉 MACD", "🗺️ 五軌分軌圖", "📄 相關報告"])
with t_kd:
    kd = A["kd"]
    fig = go.Figure()
    fig.add_scatter(x=kd["Date"], y=kd["K"], name="K", line=dict(color="#E8873A"))
    fig.add_scatter(x=kd["Date"], y=kd["D"], name="D", line=dict(color="#3B82F6"))
    fig.add_hline(y=80, line_dash="dash", line_color="#E5484D")
    fig.add_hline(y=20, line_dash="dash", line_color="#2E9E5B")
    fig.update_layout(height=280, margin=dict(l=8, r=8, t=8, b=8),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")
with t_macd:
    mc = A["macd"]
    fig = go.Figure()
    fig.add_bar(x=mc["Date"], y=mc["OSC"], name="OSC",
                marker_color=["#D64545" if x >= 0 else "#2E9E5B" for x in mc["OSC"]])
    fig.add_scatter(x=mc["Date"], y=mc["DIF"], name="DIF", line=dict(color="#3B82F6"))
    fig.add_scatter(x=mc["Date"], y=mc["MACD"], name="MACD", line=dict(color="#E8873A"))
    fig.update_layout(height=280, margin=dict(l=8, r=8, t=8, b=8),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")
with t_chip:
    import chip_chart as _cc
    _cc = importlib.reload(_cc)
    _f, _m = _cc.chip_overview(code, 6)
    if _f is not None:
        st.plotly_chart(_f, width="stretch")
with t_rep:
    from analyst_report import list_articles, read_article
    arts = [a for a in list_articles() if a.get("code") == code][:10]
    # 深度潛力股報告也一起收進來
    try:
        import deep_report as _dr
        arts += [dict(a, mode="深度潛力股", file=None, deep=a["fname"])
                 for a in _dr.list_deep() if a.get("code") == code][:3]
    except Exception:
        pass
    if arts:
        for a in arts:
            _label = f"📄 {a.get('mode','')}|{a['title'][:60]}({str(a.get('date',''))[:10]})"
            with st.expander(_label):
                try:
                    if a.get("deep"):
                        import deep_report as _dr2
                        st.markdown(_dr2.read_deep(a["deep"]))
                    else:
                        st.markdown(read_article(a["file"]))
                except Exception as _e:
                    st.warning(f"讀取失敗:{_e}")
        st.page_link("pages/13_個股法人報告.py", label="➕ 產生新報告(個股研究中心)")
    else:
        st.info("此股尚無報告。")
        st.page_link("pages/13_個股法人報告.py", label="➕ 到個股研究中心一鍵產生(六層/查核/潛力股/快評)")

st.caption("戰情室=規則式拼裝系統既有引擎(體檢卡/權證資金/買區/停損/評分),無黑箱;非投資建議。")

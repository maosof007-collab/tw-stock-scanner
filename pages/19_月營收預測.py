"""
頁面19:月營收預測(誰這個月會開得不錯)
================================
雙模型(YoY動能外推 × 歷年季節比)全市場預測下月營收,
疊籌碼偷跑層(大戶週Δ/法人5日);榜單自動入預實追蹤,
10日開獎自動對答案 → 模型每月累積命中率戰績。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_common import THEME
from ui_theme import inject_css, page_header

st.set_page_config(page_title="月營收預測", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("月營收預測", "MONTHLY REVENUE FORECAST", "🔮")

import importlib
import monthly_forecast as _mf
_mf = importlib.reload(_mf)   # 無條件reload:守門函式名追不上新增速度,模組輕直接重載一勞永逸

from twtime import now_tw
_now = now_tw()
# 12日前:上月營收未公布完 → 預測上月;之後 → 預測本月
if _now.day <= 12:
    _y, _m = (_now.year, _now.month - 1) if _now.month > 1 else (_now.year - 1, 12)
else:
    _y, _m = _now.year, _now.month
target = st.text_input("預測月份", value=f"{_y}-{_m:02d}", key="mf_target")


@st.cache_data(ttl=6 * 3600, show_spinner="全市場雙模型預測中(首次約60秒)…")
def _run(t, ver=2):                      # ver:欄位改版時+1 破舊快取
    df = _mf.forecast_month(t)
    try:                                 # 全表存檔=開獎後三層評比的原料
        df.to_csv(Path(__file__).parent.parent / "data" /
                  f"_monthly_forecast_{t.replace('-','')}.csv",
                  index=False, encoding="utf-8-sig")
    except Exception:
        pass
    return df


df = _run(target.strip())
if df.empty:
    st.info("資料不足(需目標月前至少3個月營收)")
    st.stop()

st.caption(f"樣本 {len(df)} 檔(均量≥500張)。模型A=去年同月×(1+近3月YoY中位);"
           f"模型B=上月實際×歷年同月季節比(2019-2025中位);預測=兩法平均,"
           f"「兩法一致✅」=差距<10%。⚠️ 動能外推看不見產能爬坡與一次性事件;"
           f"YoY>300%多為併購/基期事件另行查證。")

# ── 個股搜尋 ──
_q = st.text_input("🔎 股票搜尋(代碼或名稱,逗號可多檔)", placeholder="3324 或 雙鴻, 8103",
                   key="mf_search")
if _q.strip():
    _terms = [t.strip() for t in _q.replace(",", ",").split(",") if t.strip()]
    _hit = df[df.apply(lambda r: any(t in str(r["代碼"]) or t in str(r["名稱"])
                                     for t in _terms), axis=1)]
    if _hit.empty:
        st.warning("找不到——可能均量<500張被流動性濾掉,或目標月前不足3個月營收資料")
    else:
        import plotly.graph_objects as go
        for _, r in _hit.iterrows():
            _rank = int((df["預測YoY%"] > r["預測YoY%"]).sum()) + 1
            h = _mf.monthly_history(str(r["代碼"]))
            last = h.iloc[-1] if not h.empty else None
            st.markdown(f"### {r['代碼']} {r['名稱']}({r['產業']})"
                        + ("　🏆 **上月創歷史新高**" if last is not None and last["新高"] else ""))
            mcols = st.columns(6)
            if last is not None:
                mcols[0].metric(f"上月營收({last['ym'][5:]}月)", f"{last['rev_m']:,.0f} 百萬")
                mcols[1].metric("月增率 MoM", f"{last['mom%']:+.1f}%")
                mcols[2].metric("年增率 YoY", f"{last['yoy']:+.1f}%")
            mcols[3].metric("本月預測", f"{r['預測(百萬)']:,.0f} 百萬",
                            f"預測MoM {((r['預測(百萬)']/last['rev_m'])-1)*100:+.1f}%"
                            if last is not None and last["rev_m"] else None)
            mcols[4].metric("預測YoY", f"{r['預測YoY%']:+.1f}%",
                            f"全市場第 {_rank} 名")
            mcols[5].metric("大戶週Δ / 法人5日",
                            f"{r.get('大戶週Δpp', '—')}pp / {r.get('法人5日(張)', '—')}張")

            if not h.empty:
                hh = h.tail(42)
                figm = go.Figure()
                figm.add_trace(go.Bar(x=hh["ym"], y=hh["rev_m"], name="月營收(百萬)",
                                      marker_color="#F2A93B", opacity=0.75))
                # 預測月:斜紋幽靈柱 + 虛線連接(和實際柱一眼區分)
                _tgt_ym = target.strip()
                figm.add_trace(go.Bar(
                    x=[_tgt_ym], y=[r["預測(百萬)"]], name=f"預測({_tgt_ym})",
                    marker=dict(color="#FFD166", opacity=0.35,
                                pattern=dict(shape="/", fgcolor="#FFD166", solidity=0.25),
                                line=dict(color="#FFD166", width=1.5)),
                    text=[f"{r['預測(百萬)']:,.0f}"], textposition="outside",
                    textfont=dict(color="#FFD166", size=11)))
                figm.add_trace(go.Scatter(
                    x=[hh["ym"].iloc[-1], _tgt_ym],
                    y=[hh["rev_m"].iloc[-1], r["預測(百萬)"]],
                    mode="lines", name="預測路徑",
                    line=dict(dash="dash", width=2, color="#FFD166")))
                for col, cname, cc in (("ma3", "近3期均", "#FFD166"),
                                       ("ma6", "近6期均", "#FF4D6D"),
                                       ("ma12", "近12期均", "#00B4D8")):
                    figm.add_trace(go.Scatter(x=hh["ym"], y=hh[col], name=cname,
                                              line=dict(width=1.6, color=cc)))
                try:
                    _pp = None
                    for _suf in (".TW.csv", ".TWO.csv"):
                        _fp = Path(__file__).parent.parent / "data" / f"{r['代碼']}{_suf}"
                        if _fp.exists():
                            _px = pd.read_csv(_fp, index_col=0, parse_dates=True,
                                              usecols=[0, 4]).iloc[:, 0].dropna()
                            _pm = _px.resample("ME").last()
                            _pm.index = _pm.index.strftime("%Y-%m")
                            _pp = _pm.reindex(hh["ym"])
                            break
                    if _pp is not None:
                        figm.add_trace(go.Scatter(x=hh["ym"], y=_pp.values, name="股價",
                                                  yaxis="y2",
                                                  line=dict(width=1.8, color="#E8E8E8")))
                except Exception:
                    pass
                figm.update_layout(height=360, template="plotly_dark",
                                   paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["panel"],
                                   font=dict(color=THEME["text"], size=11),
                                   margin=dict(l=10, r=10, t=10, b=10),
                                   yaxis=dict(title="百萬", gridcolor=THEME["grid"]),
                                   yaxis2=dict(overlaying="y", side="right",
                                               showgrid=False, title="股價"),
                                   legend=dict(orientation="h", y=1.12))
                st.plotly_chart(figm, width="stretch")

            # ── 自動點評(規則式,數據可稽) ──
            notes = []
            if last is not None:
                if last["新高"]:
                    notes.append(f"🏆 上月營收**創歷史新高**({last['rev_m']:,.0f} 百萬)")
                sea = h[h["ym"].str[5:] == last["ym"][5:]]["mom%"].iloc[:-1].median()
                if pd.notna(sea):
                    d = last["mom%"] - sea
                    notes.append(f"{'🔥 超越' if d > 5 else ('❄️ 落後' if d < -5 else '➖ 貼近')}季節性:"
                                 f"上月 MoM {last['mom%']:+.1f}% vs 歷年同月中位 {sea:+.1f}%")
                m3, m6, m12 = last["ma3"], last["ma6"], last["ma12"]
                if pd.notna(m12):
                    if m3 > m6 > m12:
                        notes.append("📈 營收趨勢**多頭排列**(3期均>6期均>12期均)")
                    elif m3 < m6 < m12:
                        notes.append("📉 營收趨勢空頭排列(動能退坡)")
            ac = r.get("加速度pp")
            if pd.notna(ac):
                notes.append(f"{'⚡ YoY 仍在加速' if ac > 5 else ('🔻 YoY 動能降溫' if ac < -5 else '➡️ YoY 動能持平')}"
                             f"(近3月 vs 前3月 {ac:+.1f}pp)")
            bh_d = r.get("大戶週Δpp"); f5 = r.get("法人5日(張)")
            if pd.notna(bh_d) and pd.notna(f5):
                if bh_d >= 0.5 and f5 >= 500:
                    notes.append(f"🕵️ **籌碼偷跑雙訊號**:大戶週 +{bh_d}pp、法人5日 +{f5:,.0f} 張")
                elif bh_d <= -0.5 and f5 <= -500:
                    notes.append(f"⚠️ 籌碼撤退:大戶週 {bh_d}pp、法人5日 {f5:,.0f} 張——開好也提防出貨")
            if r["預測YoY%"] and r["預測YoY%"] > 300:
                notes.append("⚠️ 預測YoY>300%:多為併購/基期事件,查證後再用")
            if r["兩法一致"] == "❌":
                notes.append("⚠️ 動能法與季節法分歧>10%,本月預測不確定性高")
            st.markdown("**🗒️ 點評**\n" + "\n".join(f"- {n}" for n in notes))
            st.markdown("---")

t1, t2, t3 = st.tabs(["🏆 看好榜", "🕵️ 籌碼偷跑榜", "📊 模型戰績"])

with t1:
    show = df[(df["兩法一致"] != "❌") & (df["預測YoY%"] < 300)].head(30)
    st.dataframe(show, width="stretch", hide_index=True, height=560)
    st.caption("預測YoY 高+兩法一致=開得不錯機率高;「加速度」負值=動能在降溫,開獎日易失望。")

with t2:
    hot = df[(df["預測YoY%"] > 30) & (df["預測YoY%"] < 300)]
    if "大戶週Δpp" in hot.columns:
        hot = hot[(hot["大戶週Δpp"].fillna(0) >= 0.5) | (hot["法人5日(張)"].fillna(0) >= 500)]
    st.dataframe(hot.head(30), width="stretch", hide_index=True, height=520)
    st.caption("預測YoY>30% 且(大戶週Δ≥+0.5pp 或 法人5日≥+500張)——"
               "不只模型說會開好,而且**已經有人先卡位**。開獎行情可信度較高。")

with t3:
    # 三層評比:上一個「已開獎」的預測月成績單
    import glob as _g
    _saved = sorted(_g.glob(str(Path(__file__).parent.parent / "data" / "_monthly_forecast_*.csv")))
    for _f in _saved[::-1]:
        _t = Path(_f).stem.replace("_monthly_forecast_", "")
        _tgt = f"{_t[:4]}-{_t[4:6]}"
        _sc = _mf.score_month(_tgt)
        if _sc:
            st.markdown(f"#### 🎯 {_tgt} 三層評比(n={_sc['n']})")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**① 數字層(猜得準嗎)**")
                for k, v in _sc["數字層"].items():
                    st.caption(f"{k}:{v}")
            with c2:
                st.markdown("**② 排序層(挑對股了嗎)**")
                for k, v in _sc["排序層"].items():
                    st.caption(f"{k}:{v}")
            with c3:
                st.markdown("**③ 報酬層(有錢賺嗎)**")
                for k, v in _sc["報酬層"].items():
                    st.caption(f"{k}:{v}")
            st.caption("三層可以不同調:數字準但排序沒用=大家都猜得到;"
                       "排序對但報酬層輸=利多早已 price in——**報酬層才是最終裁判**。")
            break
    from model_track import check_all
    tr = check_all()
    mine = tr[tr["備註"].astype(str).str.startswith("月營收預測模型")]
    if mine.empty:
        st.info("尚無戰績——榜單每月自動入預實追蹤,10日開獎後這裡顯示命中率")
    else:
        done = mine[mine["燈號"].isin(["🟢", "🟡", "🔴"])]
        if not done.empty:
            hit = (done["燈號"] == "🟢").mean() * 100
            st.metric("模型命中率(誤差±5%內)", f"{hit:.0f}%",
                      help=f"已開獎 {len(done)} 筆")
        st.dataframe(mine, width="stretch", hide_index=True, height=480)
    if st.button("📌 把本月榜前20寫入預實追蹤", key="mf_record"):
        n = _mf.record_top(df, target.strip())
        st.success(f"已寫入 {n} 筆,開獎自動對答案")

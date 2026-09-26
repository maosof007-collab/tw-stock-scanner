"""頁22 — 權證大戶進出(每日監控):佈局榜/湧入榜/退潮榜/個股資金流圖。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="權證大戶", page_icon="🐳", layout="wide")

import warrant_flow as _wf
_wf = importlib.reload(_wf)          # 迭代中模組:無條件重載

st.title("🐳 權證大戶進出")


@st.cache_data(ttl=1800, show_spinner="掃描全市場權證資金流…")
def _scan(ver: int = 1):
    return _wf.market_scan(min_med=3.0)


@st.cache_data(ttl=1800)
def _panel(ver: int = 1):
    return _wf.build_panel()


panel = _panel()
if panel.empty:
    st.info("尚無資料——本機執行 `python warrant_flow.py --backfill 120`。")
    st.stop()

last_day = panel["date"].max()
sc = _scan()
try:                                  # 榜單快照(冪等,一天一筆)→ 新進榜/在榜天數
    _wf.board_log(sc)
    _meta = _wf.board_meta()
except Exception:
    _meta = pd.DataFrame(columns=["ucode", "在榜天數", "新進"])


def _decorate(d: pd.DataFrame) -> pd.DataFrame:
    """加 🆕新進 與 在榜天數欄(新進排最前)。"""
    if d.empty or _meta.empty:
        return d.assign(新進="", 在榜="—") if not d.empty else d
    out = d.merge(_meta, on="ucode", how="left")
    out["新進"] = out["新進"].map({True: "🆕", False: ""}).fillna("")
    out["在榜"] = out["在榜天數"].fillna(0).astype(int).astype(str) + "天"
    return out.sort_values(["新進", "連續天數"] if "連續天數" in out else ["新進"],
                           ascending=[False, False] if "連續天數" in out else [False])


_u1, _u2 = st.columns([1.6, 4])
with _u1:
    if st.button("🔄 抓最新權證資料", key="wf_refresh"):
        with st.spinner("抓當日權證資金流(TWSE)+鯨魚+榜單快照…"):
            try:
                from twtime import now_tw as _nt2
                _r2 = _wf.fetch_warrant_day(f"{_nt2():%Y%m%d}")
                if _r2 is None:
                    st.info("今日非交易日或資料未出(盤後約18:00後才有)。")
                else:
                    _wf.whale_today()
                    _wf.board_log()
                    st.cache_data.clear()
                    st.success(f"已更新 {len(_r2)} 檔,重新載入…")
                    st.rerun()
            except Exception as _e:
                st.error(f"更新失敗:{_e}")
with _u2:
    st.caption(f"資料至 **{last_day}**|樣本 {panel['ucode'].nunique()} 檔標的(僅上市權證)|"
               f"單位:百萬元|run_daily 每日自動更新;落後時按左鈕手動補。"
               f"**權證錢的三種狀態:🔵天天買(佈局)、🔥突然買(事件)、⚫不買了(收割完)**。")

t_in, t_hot, t_out, t_fi, t_one, t_ca = st.tabs(
    ["🔵 佈局榜(天天買)", "🔥 湧入榜(近5日)", "⚫ 退潮榜(錢走了)",
     "🌊 外資悄悄買(小型股)", "🔎 個股資金流", "📜 分割/減資雷達"])

_cols = ["新進", "在榜", "ucode", "name", "日中位", "近20日日均", "倍數", "連續天數", "CP比", "動向"]
_ren = {"ucode": "代號", "name": "名稱"}

with t_in:
    d = _decorate(sc[sc["動向"] == "🔵 佈局中"])
    _new_n = int((d["新進"] == "🆕").sum()) if "新進" in d else 0
    st.markdown(f"**{len(d)} 檔**(🆕今日新進 {_new_n}):認購權證金額連續 ≥15 天高於自身中位、"
                f"近20日 ≥1.5 倍——有人天天在買。")
    st.dataframe(d[[c for c in _cols if c in d.columns]].rename(columns=_ren),
                 hide_index=True, width="stretch")
    st.caption("配現股看:錢進價未動=吸籌形(最優先);錢進價已噴=行情中段。點名後→頁6體檢卡覆核。"
               "**在榜=連續出現在本榜幾天(榜單歷史今天起算)**。")

with t_hot:
    st.markdown("#### 🐋 鯨魚訊號(已驗證策略:5日中位+3.19%/勝率60%,18個月126筆)")
    try:
        wh = _wf.whale_today()
        if len(wh):
            st.dataframe(wh[[c for c in ["ucode", "name", "date", "call_val", "倍數", "put_val"] if c in wh.columns]]
                         .rename(columns={"ucode": "代號", "name": "名稱", "call_val": "call金額(百萬)"}),
                         hide_index=True, width="stretch")
            st.caption("條件:當日認購權證金額 ≥5×前20日中位 且 ≥5,000萬。**持有窗5日**;一樣先過現股體檢卡。訊號自動記入 forward-test。")
        else:
            st.info("今日無鯨魚訊號(≥5倍且≥5,000萬)。")
    except Exception as _e:
        st.warning(f"鯨魚訊號讀取失敗:{_e}")
    st.markdown("---")
    d = _decorate(sc[sc["動向"] == "🔥 近5日湧入"]).sort_values("近5日日均", ascending=False)
    _new_n = int((d["新進"] == "🆕").sum()) if "新進" in d else 0
    st.markdown(f"**一般湧入 {len(d)} 檔**(🆕今日新進 {_new_n}):近 5 日日均 ≥2× 前 20 日——短期事件錢。")
    if "連續天數" in d.columns:
        d["佈局進度"] = pd.to_numeric(d["連續天數"], errors="coerce").fillna(0).clip(0, 15) / 15
    st.dataframe(
        d[[c for c in _cols + ["近5日日均", "前20日日均", "佈局進度"] if c in d.columns]]
        .rename(columns=_ren), hide_index=True, width="stretch",
        column_config={"佈局進度": st.column_config.ProgressColumn(
            "距🔵佈局門檻", help="連續高於中位天數/15天;滿格=升級佈局榜",
            min_value=0.0, max_value=1.0, format=" ")})
    st.caption("⚠️ 事件研究:一般爆量隔日中位 -0.29%(偏隔日沖)——湧入榜是觀察名單,只有鯨魚級有統計背書。"
               "**進度條=連續高於中位天數/15:滿格就升級佈局榜(湧入→蓄勢→佈局的管線)**。")

with t_out:
    d = _decorate(sc[sc["動向"].isin(["⚫ 退潮", "🌫️ 降溫"])]).sort_values("倍數")
    _new_n = int((d["新進"] == "🆕").sum()) if "新進" in d else 0
    st.markdown(f"**{len(d)} 檔**(🆕今日新進 {_new_n}=剛開始退):近20日 ≤0.7× 中位"
                f"——曾經的權證熱點,錢在離場(川湖 2059 型)。")
    st.dataframe(d[[c for c in _cols if c in d.columns]].rename(columns=_ren),
                 hide_index=True, width="stretch")
    st.caption("你持有的股票出現在這裡=幫你抬轎的槓桿資金在退場,對照大戶週報決定去留。")

with t_fi:
    st.caption("**權證佈局榜的姐妹榜(外資版)**:外資「週淨買超」連續 ≥N 週為正的小型股"
               "(20日均量 200~8,000 張)——東捷/久元/天品那種「外資持股悄悄爬升」的指紋,量化版。"
               "誠實標註:用日買賣超累積計算,非持股存量;吸籌強度=12週累積相當於幾天的日均量。")
    _nw = st.slider("最少連續週數", 4, 12, 5, key="fi_nw")

    @st.cache_data(ttl=3600, show_spinner="掃描外資連續累積…")
    def _fi_scan(nw: int, ver: int = 1):
        import fi_accum
        return fi_accum.fi_accum_scan(min_weeks=nw)

    _fd = _fi_scan(_nw)
    if _fd.empty:
        st.info("目前無符合條件的標的。")
    else:
        st.markdown(f"**{len(_fd)} 檔**(連續週數×吸籌強度排序)")
        st.dataframe(_fd, hide_index=True, width="stretch", height=520)
        st.caption("判讀:距年高% 貼近 0 且吸籌強度高=錢進價穩(吸籌形,最優先);"
                   "距年高深負=外資接刀或攤平,配大戶Δ與投信欄交叉;"
                   "點名後 → 頁6 體檢卡覆核+個股資金流看權證面。")

with t_one:
    code = st.text_input("代號", key="wb_code")
    if code.strip():
        code = code.strip()
        sf = _wf.sustained_flow(code)
        if not sf:
            st.warning("樣本不足(<40 交易日)或無此標的權證。")
        else:
            st.markdown(f"### {sf['verdict']}")
            a, b, c, dcol = st.columns(4)
            a.metric("近20日/中位", f"{sf['近20日倍數']}x", f"日中位 {sf['日中位']}", delta_color="off")
            b.metric("連續高於中位", f"{sf['連續高於中位天數']} 天")
            c.metric("call/put(20日)", f"{sf['近20日CP比']}")
            dcol.metric("近40日股價", f"{sf['近40日價格%']:+.1f}%" if sf["近40日價格%"] is not None else "—")

            g = panel[panel["ucode"] == code].sort_values("date")
            fig = go.Figure()
            fig.add_bar(x=g["date"], y=g["call_val"], name="認購權證金額(百萬)",
                        marker_color="#00C2A8", opacity=0.7)
            fig.add_bar(x=g["date"], y=-g["put_val"], name="認售(反向顯示)",
                        marker_color="#FF5C77", opacity=0.5)
            # 現股價疊加
            for suf in (".TW", ".TWO"):
                p = Path(__file__).parent.parent / "data" / f"{code}{suf}.csv"
                if p.exists():
                    px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
                    px = px[px["Date"].isin(set(g["date"]))]
                    fig.add_scatter(x=px["Date"], y=pd.to_numeric(px["Close"]),
                                    name="現股收盤", yaxis="y2",
                                    line=dict(color="#FFD166", width=2))
                    break
            fig.update_layout(height=420, barmode="overlay",
                              yaxis=dict(title="權證金額(百萬)"),
                              yaxis2=dict(overlaying="y", side="right", title="股價",
                                          showgrid=False),
                              legend=dict(orientation="h", y=1.08),
                              margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(sf["monthly"], width="stretch")
            st.caption("看圖重點:綠柱持續墊高+黃線還在低檔=佈局;綠柱消失+黃線在高檔=收割完(川湖型)。")

with t_ca:
    import corp_actions as _ca
    _ca = importlib.reload(_ca)
    st.markdown("#### 公告雷達(每日掃全市場重大訊息:股票分割/面額變更/減資)")
    st.caption("「提前布局」的合法時點=**公告日**。公告→股東會→停止買賣→恢復買賣,中間通常有數週到數月——雷達命中後把恢復買賣日記進行事曆。")
    rec = _ca.recent()
    if rec.empty:
        st.info("尚無記錄(run_daily 每日自動掃;可先手動執行 python corp_actions.py)。")
    else:
        st.dataframe(rec.iloc[::-1], hide_index=True, width="stretch")
    st.markdown("#### 2025-2026 分割恢復買賣案例實測(恢復日進場)")
    st.dataframe(_ca.SPLIT_CASES, hide_index=True, width="stretch")
    st.markdown("""
**規則(從案例歸納,樣本仍小,持續累積)**:
1. **恢復買賣日才是主戰場**——不必真的搶「提前」:世紀* 分割前 60 日還跌 20%,錢全在恢復後(+116.6%);
2. **比例要大**(≥1拆4):1拆2 的強生只有 +1.3%,「變便宜」的錯覺不夠強;
3. **預跑是反指標**:分割前已暴漲(沛爾 +105%)=利多出盡,恢復日 -10% 教訓;預跑低或負的才有行情;
4. **首日量價定調**:恢復日漲停鎖死=跟(照天量統計掛 -15% 統計停損);開高走低=沛爾型,跳過;
5. 疊加題材(世紀*=AI 無人機)才有連續漲停的燃料——分割只是火柴,題材才是柴堆。
""")

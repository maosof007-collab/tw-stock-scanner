# -*- coding: utf-8 -*-
"""
pages/38_估值前瞻.py — 個股估值前瞻(三情境×機率×PE帶,融合家規/法說/籌碼)
=================================================================
外部卡的骨架(三情境EPS+機率/機構共識/總經傳導/護城河證據分級/最沒把握的地方)
× 我們的肌肉(業外剝離/法說庫/券商觀點/家規前置檢查/風險燈/同業排名全自動)。
鐵律:預設值全部可改——引擎給錨,人給判斷;存檔進查詢紀錄供對帳。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="估值前瞻", page_icon="🎯", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("估值前瞻", "VALUATION OUTLOOK", "🎯")

import forecast_card as FCX
import importlib
FCX = importlib.reload(FCX)          # 迭代中模組:無條件重載(常駐的 app 不會自己重載)

# ---------------------------------------------------------------- 查詢紀錄
recent = FCX.recent_cards(10)
if recent:
    with st.expander(f"🗂️ 查詢紀錄(共 {len(recent)} 筆·新到舊)", expanded=False):
        for r in recent:
            scen = r.get("scen", {})
            st.markdown(
                f"**{r['code']} {r.get('name','')}**|{r.get('year','')} 基準 "
                f"**{scen.get('基準','—')}** 元·機率 {r.get('probs',{}).get('基準','—')}%|"
                f"期望價 **{r.get('exp_px','—')}**|{r['ts']}")

import stock_nav as _sn
code = st.text_input("股票代碼", value=_sn.cur_code(st.session_state.get("fc_code", "2330"))).strip()
st.session_state["fc_code"] = code
if not code:
    st.stop()
_sn.set_cur_code(code)
_sn.bar("估值")

try:
    import symbols
    name = symbols.resolve(code)[1] or ""
except Exception:
    name = ""

A = FCX.anchor(code)
if not A.get("ok"):
    st.error("抓不到季報 EPS——確認代碼或等 bulk_fin 更新。"); st.stop()

band = FCX.pe_band(code, A["q"])
fl = FCX.flags(code)
mac = FCX.macro_block()

st.subheader(f"{code} {name} · {A['year']} 年三情境預估")
st.caption(f"錨:前 {A['n_done']} 季已實現 **{A['realized']}** 元鎖定下檔,"
           f"剩餘 {A['n_left']} 季以近 2/4 季 run-rate 外推——**預設值,請用你的判斷覆寫**。")

# ---------------------------------------------------------------- 三情境(可編輯)
c1, c2, c3 = st.columns(3)
scen, probs = {}, {}
defaults_p = {"保守": 30, "基準": 50, "樂觀": 20}
for col, k in zip((c1, c2, c3), ("保守", "基準", "樂觀")):
    with col:
        scen[k] = st.number_input(f"{k} EPS", value=float(A["scen"][k]), step=0.5,
                                  key=f"eps_{code}_{k}")
        probs[k] = st.number_input(f"{k} 機率%", value=defaults_p[k], step=5,
                                   min_value=0, max_value=100, key=f"p_{code}_{k}")
psum = sum(probs.values())
if psum != 100:
    st.warning(f"機率合計 {psum}%(≠100)——期望值按比例正規化。")
exp_eps = sum(scen[k] * probs[k] for k in scen) / max(psum, 1)

# 業外剝離警告(我們的獨門)+ 本業虧損/循環谷底兩道保險絲
core_dead = A["nonop_pct"] >= 40 and (A["ttm_core"] is None or A["ttm_core"] <= 0)
cyc_trough = (A.get("yr_avg_eps") and A["yr_avg_eps"] > 0
              and A["ttm"] < 0.4 * A["yr_avg_eps"])
if core_dead:
    st.error(f"⛔ 本業 TTM **{A['ttm_core']}**(虧損),帳面 TTM {A['ttm']} 全靠業外撐"
             f"({A['nonop_pct']}%)——**PE 法整個失效,估值矩陣停用**。"
             "這種股請改看 PB/循環位置/資產價值,不是 EPS 乘倍數。")
    scale = 1.0
elif A["nonop_pct"] >= 40:
    st.error(f"🚨 近4季獲利約 {A['nonop_pct']}% 來自業外(TTM {A['ttm']} vs 本業 TTM "
             f"{A['ttm_core']})——下方估值矩陣已改用「本業係數」折算,別拿全 EPS 配歷史 PE。")
    scale = A["ttm_core"] / A["ttm"] if A["ttm"] else 1.0
else:
    scale = 1.0
if cyc_trough:
    st.warning(f"🌀 循環股陷阱:TTM EPS {A['ttm']} 不到歷史年均 {A['yr_avg_eps']} 的四成"
               "——獲利在谷底時歷史 PE 帶會虛胖(高PE=谷底、低PE=循環頂)。"
               "下方矩陣僅供參考,循環股請用 PB 帶/景氣位置判斷。")

# ---------------------------------------------------------------- 估值矩陣
exp_px = None
if band and core_dead:
    st.info("估值矩陣停用(本業虧損)。可看的替代訊號:月營收 YoY 轉折(頁19)、"
            "同業毛利率排名(下方)、循環位置。")
elif band:
    st.subheader("估值矩陣(三情境 × 歷史 PE 帶)")
    st.caption(f"近3年 PE 分位:P25 {band['P25']} / P50 {band['P50']} / P75 {band['P75']}"
               f"|現價 {band['close']}" + ("|⚠️ 已按本業係數折算" if scale < 1 else ""))
    rows = []
    for k in ("保守", "基準", "樂觀"):
        e = scen[k] * scale
        rows.append({"情境": k, "EPS": round(scen[k], 2), "機率%": probs[k],
                     "×P25": round(e * band["P25"], 1), "×P50": round(e * band["P50"], 1),
                     "×P75": round(e * band["P75"], 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    exp_px = round(exp_eps * scale * band["P50"], 1)
    up = (exp_px / band["close"] - 1) * 100
    st.metric("期望價(機率加權 EPS × P50)", f"{exp_px}",
              f"{up:+.1f}% vs 現價 {band['close']}")
else:
    st.info("歷史 PE 樣本不足(虧損期太長或上市太短)——矩陣停用,只看情境 EPS。")

# ---------------------------------------------------------------- 本益比河流圖
st.subheader("本益比河流圖")
import pe_river as PR
_ry = st.radio("看幾年", [5, 10, 15, 20], index=1, horizontal=True, key=f"river_y_{code}")
RV = PR.series(code, _ry)
if not RV:
    st.info("畫不出河流圖:上市不到兩年、長期虧損,或 FinMind 這次沒回資料(免費額度用完時隔一小時再試)。")
else:
    st.plotly_chart(PR.figure(RV, name), use_container_width=True)
    _pe_txt = (f"本益比 **{RV['pe']:.1f} 倍**,在自己近 {RV['years']:.0f} 年裡排第 **{RV['rank']:.0f} 百分位**"
               if RV["pe"] else "近四季 EPS 是負的,沒有本益比")
    st.markdown(f"{RV['last']:%m/%d} 收盤 **{RV['close']:,.1f}**|近四季 EPS **{RV['ttm']:.2f}**(到 {RV['eps_q']:%Y/%m} 這一季)|{_pe_txt}。"
                f"歷史最低 {RV['pe_min']:.1f} 倍({RV['pe_min_d']:%Y/%m})、最高 {RV['pe_max']:.1f} 倍({RV['pe_max_d']:%Y/%m})。")
    st.dataframe(PR.table(RV), hide_index=True, use_container_width=True)
    _warn = ["「對應股價」是拿**現在的**近四季 EPS 去乘;EPS 往下修,整條河會一起往下移。"]
    if RV["loss_days"]:
        _warn.append(f"這段期間有 {RV['loss_days']} 個交易日近四季 EPS 是負的,那幾段沒有河道。")
    if RV["flags"]:
        _warn.append("股價單日跳動超過 15% 的日子:" + "、".join(RV["flags"]) + "(減資、分割或大額除權息;前後一年的河道可能失真)。")
    st.caption("怎麼讀:河道=每天的近四季 EPS × 這檔自己歷史本益比的第 5/25/50/75/95 百分位,顏色越深本益比越高;黑線是未還原股價。"
               "財報用當天已公布的(季報加 45 天、年報加 90 天)。" + " ".join(_warn)
               + "循環股獲利在高峰時本益比最低——股價掉到河底不代表便宜,要搭配下面的明年情境看。資料:FinMind。")

# ---------------------------------------------------------------- 明年情境(下修思考)
NY = FCX.next_year(code, A)
if NY.get("ok"):
    st.subheader(f"{NY['year']} 年情境:如果獲利回到正常,還便宜嗎?")
    if NY["peak"]:
        base_txt = "前年是虧損" if (NY["eps_y2"] or 0) <= 0 else f"是前年全年 {NY['eps_y2']} 元的 {NY['ttm'] / NY['eps_y2']:.1f} 倍"
        st.warning(f"🏔 獲利高峰旗標:最近兩季營益率 {NY['opm_now']}%,比近 12 季中位數 {NY['opm_med']}% 高 {NY['gap']} 點;"
                   f"近四季 EPS {NY['ttm']} 元,{base_txt}。上面的三情境是拿這個高峰往後推的——"
                   "景氣循環股在獲利最高時本益比最低,股價通常比營收早半年以上見頂。")
    cut_pct = st.number_input("壓力測試:營收比現在少幾 %", min_value=0, max_value=60, value=int(round(NY["cut"] * 100)), step=2,
                              key=f"ny_cut_{code}",
                              help="AI 相關族群預設 16(SemiAnalysis 對 2028 年實體量的下修幅度,第三方轉述);其他預設 0。"
                                   "上一輪循環(2021–22)個股營收從高點到低點的中位數是 −40%。這是壓力測試,不是預測。")
    NY2 = FCX.next_year(code, A, cut=cut_pct / 100)
    px_now = band["close"] if band else None
    ny_rows = FCX.next_year_rows(NY2, px_now)
    for r in ny_rows:
        r["×P50"] = round(r["EPS"] * band["P50"], 1) if (band and r["EPS"] and r["EPS"] > 0) else None
    st.dataframe(pd.DataFrame(ny_rows).rename(columns={"本益比": "現價隱含本益比", "×P50": "× 歷史本益比中位數"}),
                 hide_index=True, use_container_width=True)
    st.caption(f"算到 {NY['last_q']} 這一季。三列由好到壞;每一列都只改一個假設,業外和稅率不動。"
               + ("" if NY2["lev"] else " 營益率中位數太低(<3%),營收下修那一列不算。")
               + " 這一段不進上面的期望價,只回答「如果高峰過了」。")

elif NY.get("why"):
    st.caption(f"明年情境不列:{NY['why']}。")

# ---------------------------------------------------------------- 機構預估彙總
st.subheader("機構預估彙總")


@st.cache_data(ttl=3600, show_spinner="抓券商共識…")
def _cons(c):
    return FCX.consensus(c)


cons = _cons(code)
if cons:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("目標價均值", cons.get("mean", "—"),
              (f"{(cons['mean']/cons['current']-1)*100:+.1f}% 隱含"
               if cons.get("current") else None))
    k2.metric("中位/區間", f"{cons.get('median','—')}",
              f"{cons.get('low','—')}~{cons.get('high','—')}", delta_color="off")
    k3.metric("機構家數", cons.get("家數", "—"),
              str(cons.get("評等", "") or ""), delta_color="off")
    fw = cons.get("forwardEPS")
    k4.metric("共識 Forward EPS", fw if fw else "—",
              (f"對基準差 {(scen['基準']/fw-1)*100:+.0f}%" if fw else None),
              delta_color="off")
    if fw:
        st.caption(f"對帳:你的基準 {scen['基準']} vs 街上 forward {fw}"
                   f"——差距大就回頭檢查剩餘季 run-rate 假設;"
                   f"均值 {cons.get('mean')} 隱含 {cons['mean']/fw:.1f} 倍 forward PE。")
    st.caption("來源:yfinance(轉 FactSet 共識)·每小時快取——家數少(<5)時均值噪音大,看區間別看點。")
else:
    st.caption("yfinance 查無此檔共識(冷門股常見)——用下方手動欄。")
try:
    from tp_radar import latest_for, load
    hit = latest_for(code)
    if hit:
        st.markdown(f"📰 近期異動(鉅亨FactSet快報):{hit.get('日期','')} "
                    f"{hit.get('類型','')}{hit.get('方向','')} 目標價 "
                    f"**{hit.get('目標價','—')}**|EPS預估 {hit.get('EPS預估','—')}")
except Exception:
    pass
mc1, mc2 = st.columns(2)
with mc1:
    manual_tp = st.number_input("手動:機構目標價均值(選填,0=略過)", value=0.0, step=1.0,
                                key=f"tp_{code}")
with mc2:
    manual_n = st.number_input("手動:機構家數(選填)", value=0, step=1, key=f"tn_{code}")
if manual_tp > 0 and band:
    st.caption(f"→ 手動共識隱含 {(manual_tp/band['close']-1)*100:+.1f}%"
               f";對基準 EPS {scen['基準']} 為 {manual_tp/max(scen['基準'],0.01):.1f} 倍 PE。")

# ---------------------------------------------------------------- 總經傳導
st.subheader("總體經濟傳導(這一檔的受力點)")
st.caption(f"傳導路徑:{mac['傳導路徑']}")
_pe_now = (band["close"] / A["ttm"]) if (band and A["ttm"] and A["ttm"] > 0
                                         and not core_dead and not cyc_trough) else None
st.dataframe(pd.DataFrame(FCX.macro_for(code, _pe_now)),
             hide_index=True, use_container_width=True)
r = mac.get("risk")
if r:
    lamp = r.get("lamp", r.get("level", ""))
    st.markdown(f"本系統風險燈:**{lamp}**(分數 {r.get('score','—')})")
    for s in r.get("reasons", [])[:6]:
        st.caption(f"· {s}")
    if "🔴" in str(lamp):
        st.error("🔴 風險燈=禁開新倉——估值再便宜也先等燈退。家規優先於估值。")
else:
    st.caption("風險燈資料未更新(run_daily 後自動帶入)。")

# ---------------------------------------------------------------- 護城河:有數字 vs 推論
st.subheader("產業與護城河")
pr = FCX.peer_rank(code)
colA, colB = st.columns(2)
with colA:
    st.markdown("**有數字或有來源支撐的(自動)**")
    if pr:
        st.markdown(f"· 「{pr['族群']}」族群毛利率排名 **{pr['排名']}/{pr['共']}**(最新季)")
        st.dataframe(pr["表"].head(8), hide_index=True, use_container_width=True)
    st.markdown(f"· TTM EPS **{A['ttm']}**(本業 {A['ttm_core']},業外佔 {A['nonop_pct']}%)")
    if fl.get("法說"):
        d = fl["法說"]
        st.markdown(f"· 法說簡報庫:最新 **{d[:4]}/{d[4:6]}/{d[6:8]}**(頁23 可讀)")
    else:
        st.markdown("· 法說簡報庫:**無**——素材層級缺最高層,推論要降級看待")
with colB:
    st.markdown("**推論(沒有直接數字,看方向就好)——手動**")
    moat_note = st.text_area("推論筆記(存入查詢紀錄)",
                             value="", height=150, key=f"moat_{code}",
                             placeholder="例:漲價能力/客戶黏性/後進者難複製…"
                             "——寫下你「相信但還沒有數字」的部分,之後對帳。")

# ---------------------------------------------------------------- 家規與籌碼檢查
st.subheader("家規前置檢查(我們的,外部卡沒有)")
fcol = st.columns(4)
items = [("處置中", fl.get("處置中"), "⛔ 處置股不進場"),
         ("爆量窗", fl.get("爆量窗"), "家規:爆量+2~3天禁入"),
         ("迴轉率警戒", fl.get("迴轉率警戒"), "🔪 隔日沖戰場"),
         ("外資20日", f"{fl.get('外資買超天(20日)','—')}天/"
                      f"{fl.get('外資累計(張)','—')}張", "")]
for col, (k, v, note) in zip(fcol, items):
    with col:
        if v is True:
            st.error(f"**{k}**:是\n\n{note}")
        elif v is False:
            st.success(f"**{k}**:否")
        else:
            st.info(f"**{k}**:{v}")

# ---------------------------------------------------------------- 最沒把握的地方
st.subheader("最沒把握的地方")
auto_u = FCX.uncertainty(code, A)
uncertain = st.text_area("(自動偵測,可覆寫)", value=auto_u, height=80,
                         key=f"unc_{code}")

# ---------------------------------------------------------------- 綜合評論+存檔
st.subheader("綜合評論")
lines = [f"機率加權 EPS **{exp_eps:.2f}** 元"]
if band and exp_px:
    lines.append(f"期望價 **{exp_px}**({(exp_px/band['close']-1)*100:+.1f}% vs 現價)"
                 f",現價對 TTM 為 {band['close']/max(A['ttm'],0.01):.1f} 倍"
                 f"(歷史帶 {band['P25']}~{band['P75']})")
if A["nonop_pct"] >= 40:
    lines.append("⚠️ 業外佔比高,估值已折算本業")
if r and "🔴" in str(r.get("lamp", "")):
    lines.append("🔴 風險燈凍結新倉——結論僅供觀察")
st.markdown(";".join(lines) + "。")

if st.button("💾 存入查詢紀錄", type="primary"):
    FCX.save_card(code, {"name": name, "year": A["year"], "scen": scen, "probs": probs,
                         "exp_eps": round(exp_eps, 2), "exp_px": exp_px,
                         "nonop_pct": A["nonop_pct"], "moat": moat_note,
                         "uncertain": uncertain})
    st.success("已存——之後開獎(財報/法說)回來對帳,情報戰績表會長大。")

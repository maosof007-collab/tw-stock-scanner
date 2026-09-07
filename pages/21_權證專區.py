"""頁21 — 權證專區:教學 / 計算器 / 挑選SOP(與體檢卡、HV 對接)。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="權證專區", page_icon="🎫", layout="wide")

import warrant_tools as _wt
_wt = importlib.reload(_wt)          # 迭代中模組:無條件重載

st.title("🎫 權證專區")
st.caption("定位鐵律:權證是**放大既有訊號**的執行工具,不是選股工具——先有現股級的理由(體檢卡綠燈+裁決點),才考慮用權證表達。")

tab_learn, tab_calc, tab_sop = st.tabs(["📖 權證是什麼", "🧮 計算器", "✅ 挑選SOP"])

# ════════════════ 教學 ════════════════
with tab_learn:
    st.markdown("""
### 一句話:權證=向券商買的「限時看漲/看跌彩券」,價格由五個零件組成

| 零件 | 是什麼 | 你要記的事 |
|---|---|---|
| **履約價 K** | 到期時的對賭價位 | 價內(現價已過K)貴而穩;價外便宜但可能歸零 |
| **剩餘天數** | 彩券的保存期限 | **時間每天都在扣錢(Theta)**,越近到期扣越兇 |
| **行使比例** | 一張權證換幾股 | 常見 0.01~0.1;比例越小單價越低,但槓桿看Delta不是看單價 |
| **隱含波動率 IV** | 券商賣你的「保費費率」 | 和標的 HV 比:IV 遠高於 HV = 買貴了 |
| **Call / Put** | 看漲 / 看跌 | 台灣還有牛熊證(有下限價,時間價值結構不同) |

### 三個真正決定損益的數字
1. **實質槓桿**:標的漲 1%,權證漲幾 %。不是「單價便宜」=槓桿大,是 Delta×標的價×行使比例÷權證價;
2. **每日時間流失**:今天就算標的不動,明天權證值多少——短天期價外權證一天流失 2~5% 是常態;
3. **損益兩平價**:到期時標的要漲到哪你才不賠(履約價+權證價÷行使比例)。**買之前先看這個,很多權證要標的漲 15% 你才開始賺**。

### 台灣權證的五個坑(每個都吃過人)
1. **深價外+短天期**:看起來一張 0.5 元很便宜,其實是快過期的歸零彩券——散戶虧損主力來源;
2. **IV 被調降**:你買時 IV 45%,漲了之後券商造市掛單降到 38%——標的漲了權證沒漲,「贏了方向輸了保費」;
   買前看該券商同標的舊權證的 IV 穩不穩(隱波履歷);
3. **價差蟑螂**:流動性差的權證買賣價差 3~5%,進出一趟先虧一根停損;只買造市報價緊(≤2 tick)的;
4. **長假與空窗**:權證不能抱著等——連假、停牌、除權息調整期間 Theta 照扣、還可能沒人報價;
5. **末日輪賭徒**:剩 20 天內的權證是造市商的提款機,別把它當樂透。

### 和本系統的關係(家規)
- **只在體檢卡🟢的股票上用 Call**、只在確定事件裁決點前後用(例:9/10 營收開獎、11/14 財報);
- 權證部位上限=總資金 **5%**,單檔上限 2%——歸零也不傷本體;
- **時間停損**:事件過了沒發動,3 天內出場,不跟時間耗;
- 錯殺V轉/腰斬打底這類「等訊號」策略**不適合**權證(等待期 Theta 會把你磨死),
  適合的是**已觸發的突破訊號+近期裁決日**的組合。
""")

# ════════════════ 計算器 ════════════════
with tab_calc:
    st.caption("輸入權證條件 → 理論價/實質槓桿/時間流失/損益兩平/情境表。標的代號填了會自動帶現價與 HV 供對照。")
    c0, c1, c2, c3 = st.columns(4)
    code = c0.text_input("標的代號(選填,自動帶現價/HV)", key="w_code")
    hv = {}
    if code.strip():
        hv = _wt.hist_vol(code.strip())
        if hv:
            st.info(f"**{code}** 現價 {hv['現價']}|歷史波動率 HV20 {hv['HV20%']}% / HV60 {hv['HV60%']}% / HV120 {hv['HV120%']}%"
                    f" ← 權證 IV 高於 HV60 越多=保費越貴")
    S = c1.number_input("標的現價", min_value=0.1, value=float(hv.get("現價", 100.0)), step=0.5)
    K = c2.number_input("履約價", min_value=0.1, value=round(float(hv.get("現價", 100.0)) * 1.05, 1), step=0.5)
    days = c3.number_input("剩餘天數", min_value=1, value=90, step=1)
    c4, c5, c6, c7 = st.columns(4)
    iv = c4.number_input("隱含波動率 IV%", min_value=1.0, value=float(hv.get("HV60%", 40.0)), step=1.0) / 100
    ratio = c5.number_input("行使比例", min_value=0.001, value=0.05, step=0.01, format="%.3f")
    wprice = c6.number_input("權證市價(0=用理論價)", min_value=0.0, value=0.0, step=0.01)
    kind = c7.selectbox("類型", ["call", "put"])

    m = _wt.warrant_metrics(S, K, int(days), iv, ratio, wprice or None, kind)
    a, b, c, d = st.columns(4)
    a.metric("理論價", f"{m['理論價']}", f"市價 {m['市價']}" + (f"(溢價{m['溢價率%']}%)" if m["溢價率%"] is not None else ""), delta_color="off")
    b.metric("實質槓桿", f"{m['實質槓桿x']}x", f"Delta {m['Delta']}", delta_color="off")
    b2 = f"-{m['每日流失%']}%/日" if m["每日流失%"] is not None else ""
    c.metric("每日時間流失", f"{m['每日時間價值流失']}", b2, delta_color="off")
    d.metric("損益兩平", f"{m['損益兩平']}", f"價{'內' if m['價內外%']>=0 else '外'} {abs(m['價內外%'])}%", delta_color="off")
    be_need = (m["損益兩平"] / S - 1) * 100 if kind == "call" else (1 - m["損益兩平"] / S) * 100
    if be_need > 12:
        st.error(f"⚠️ 到期損益兩平需要標的再{'漲' if kind=='call' else '跌'} {be_need:.1f}%——這張是樂透,不是工具。")
    elif be_need > 6:
        st.warning(f"到期損益兩平需標的{'漲' if kind=='call' else '跌'} {be_need:.1f}%,只適合短打事件,不適合長抱。")

    st.markdown("##### ⏳ 時間衰減表(標的不動,純扣保費)")
    st.dataframe(_wt.decay_table(S, K, int(days), iv, ratio, kind), hide_index=True)
    st.markdown("##### 🎯 情境表(標的漲跌 × 持有時間)")
    st.dataframe(_wt.scenario_table(S, K, int(days), iv, ratio, wprice or None, kind), hide_index=True)
    st.caption("情境表沿用你輸入的市價溢價倍數;實際還受 IV 調整影響(IV 每降 1% 損失見上方 vega)。")

# ════════════════ 挑選SOP ════════════════
with tab_sop:
    st.markdown("""
### 買權證前的六步(照順序,不跳步)

| 步 | 動作 | 及格線 |
|---|---|---|
| 1 | **現股先過體檢卡**(頁6) | 🟢 才准用 Call;🔴🟡 免談——槓桿只放大對的事 |
| 2 | **有明確裁決日** | 14 天內有事件(營收開獎/財報/法說),否則 Theta 白繳 |
| 3 | **選價平附近** | 價內外 ±10% 以內;深價外=樂透 |
| 4 | **剩餘天數 > 60** | 事件日+至少 45 天緩衝;末日輪不碰 |
| 5 | **IV 對照 HV60** | IV ≤ HV60×1.2;用左邊計算器算損益兩平,需漲>12% 就換一檔 |
| 6 | **部位紀律** | 單檔 ≤2%、權證總計 ≤5%;事件過後 3 天沒發動就出場 |

### 用系統事件當發射窗(現成的)
- **每月 10 日營收開獎**:月營收預測頁的看好榜+偷跑榜,籌碼先行的標的配 60 天以上價平 Call;
- **財報日(11/14)**:查核式報告的驗收日曆就是權證的到期日規劃表;
- **大盤裁決樹**(總經頁):大盤紅燈期間權證全面停用——高 IV+高相關性=雙倍保費買雙倍風險。

### 出場鐵律
1. 標的到裁決點:**對了→權證漲幅是現股 3~5 倍,分批走**;錯了→當天出,權證不凹單;
2. 時間停損:事件後 3 天;3. 券商調降 IV(買時記下 IV,掉 3% 以上=保費被沒收,走人);
4. 權證**永遠不抱過 10 個交易日**——這是保費工具,不是存股。
""")
    st.info("📌 下一步(可選):接上 TWSE/TPEX 權證每日行情,做「輸入標的→自動列出所有掛牌權證+IV/價差/槓桿排名」的篩選器。目前先用計算器手動驗一張是一張。")

"""
pages/31_選擇權學院.py — 選擇權獨立教學+模擬倉(從權證專區分家)
=================================================================
三分頁:🎓四腿與控盤者(讀盤)/🧭麥氏矩陣(策略思維+考題)/🧪模擬倉(真實結算價練兵)。
模擬倉紀律:開倉必填矩陣象限+論點;每日期交所結算價自動洗損益。
"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="選擇權學院", page_icon="🎓", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("選擇權學院", "OPTIONS ACADEMY", "🎓")

st.caption("定位:**選擇權≠權證**(交易所撮合/歐式/有賣方),獨立學。"
           "讀盤(四腿指紋)→ 思維(麥氏矩陣)→ 練兵(模擬倉,真實結算價)。"
           "**現階段鐵律:名目不合身(一口TXO≈238萬),只開模擬倉與最小學習倉。**")

t_legs, t_mx, t_paper = st.tabs(["🎓 四腿與控盤者", "🧭 麥氏矩陣", "🧪 模擬倉"])

# ════════════════ 四腿與控盤者 ════════════════
with t_legs:
    st.markdown("""
### 四條腿,一張表看懂(關鍵:誰付錢、誰收錢)

| 腿 | 動作 | 錢 | 什麼人做 | 心態 |
|---|---|---|---|---|
| **BC** 買Call | 付權利金押漲 | 💸付 | 散戶追多/空單買「保險帽」 | 小錢搏大 or 避軋空 |
| **SC** 賣Call | 收租賭不漲 | 💰收 | **做空黑手的首選** | 我能把盤壓下去,Call必歸零 |
| **BP** 買Put | 付權利金押跌 | 💸付 | 恐慌避險者 | 付錢買保險,量大會露餡 |
| **SP** 賣Put | 收租賭不跌 | 💰收 | 做多的莊/撿貨者 | 跌下來我樂意接 |

**貪婪鐵律:控盤者當「賣方」收錢,不當「買方」付錢**——因為結局他自己決定。
所以:做空黑手=SC(收租+壓上檔);做多的莊=SP。**買方付錢的行為多半是散戶或避險。**

### 三組指紋(把這頁背下來)
1. **抓黑手做空**:SC 口數突然暴增 + Call 的 IV 被壓低(越漲越便宜)+ **BP 沒有跟著增**
   (他不買 Put——自己要砸的盤,買保險是浪費錢);
2. **抓做莊(區間收租)**:同時淨 SP+SC 雙賣、未平倉特大、IV 壓低不跟漲、期貨鎖住讓指數縮量橫盤
   ——時間價值天天進他口袋;
3. **BC 的兩張臉(2026-09-14 實戰教案)**:同一筆「買權淨買」——
   期貨偏多背景=順勢進攻;**期貨深空背景=空單的便宜保險帽**。
   單看選擇權四腿永遠是羅生門,**期貨淨部位才是定案的那塊拼圖**(下方儀表)。

### 📡 定案拼圖:外資台指期淨部位(期交所,每日)
""")
    try:
        import taifex_flow as _tf
        _tf = importlib.reload(_tf)
        st.info(f"**{_tf.fi_verdict()}**")
        _fd = _tf.fetch_fi_futures(8)
        st.dataframe(_fd.iloc[::-1], hide_index=True, width="stretch")
        st.caption("判讀:深空背景下的 BC=保險帽不是看多;期貨回補+BC=空方在鬆手;"
                   "期貨加空+SC 暴增=黑手佈局中。")
    except Exception as _e:
        st.warning(f"期交所資料讀取失敗:{_e}")

# ════════════════ 麥氏矩陣 ════════════════
with t_mx:
    st.markdown("""
### 🧭 麥氏矩陣 — McMillan《選擇權策略完全手冊》的核心思維

一句話:**選擇權策略 = f(方向觀點, 波動率貴賤)。先有觀點,才有策略,順序不能反。**
說不出「標的會在多久內、往哪、動多少,而且市場把這件事定價定貴/便宜了」——就沒有任何策略適合你。
這跟體檢卡同一哲學:**進場前先把論點寫清楚**。

---
#### 第一步:判斷 IV 貴還便宜(波動率是「價格」,不是「風險」)
| 工具 | 怎麼看 | 白話 |
|---|---|---|
| **IV vs HV20** | 隱含波動率 vs 近20日實際波動 | IV 遠高於 HV=保費貴(市場在怕);遠低=保費便宜(市場在睡) |
| **IV Rank** | 現在 IV 在過去一年的百分位 | >70%=貴、<30%=便宜;台指看「台灣VIX」 |
| **事件日曆** | FOMC/財報/連假前 | 事件前 IV 必貴;**事件後 IV 崩=買方方向對了還賠(雙殺)** |

#### 第二步:查矩陣(觀點 × IV → 策略)
| | **IV 便宜(<30分位)** | **IV 合理** | **IV 貴(>70分位)** |
|---|---|---|---|
| **看漲** | 買 Call | 牛市借方價差(買低賣高履約價) | 牛市信用價差(賣Put戴帽收租) |
| **中性** | 買跨式/勒式(賭要大動) | 日曆價差 | 鐵兀鷹(受限雙賣收租) |
| **看跌** | 買 Put | 熊市借方價差 | 熊市信用價差(賣Call戴帽) |

規律只有兩條:**IV 便宜→當買方(保費打折);IV 貴→當賣方但一定戴帽(價差,不裸賣)**。
還記得四腿課的結論嗎——控盤者永遠在貴的時候賣。你至少不要在貴的時候買。

#### 第三步:三個希臘字母,只記白話
- **Delta**=方向倉位:0.5 的 Call ≈ 半張現股。整戶 Delta 加總=你真正的方向曝險
- **Theta**=時間的房租:**買方天天付、賣方天天收**。買方拖越久越輸,所以買方要嘛快對,要嘛認錯
- **Vega**=IV 倉位:買方希望 IV 升、賣方希望 IV 跌。事件後 IV 崩就是 Vega 收你的錢

#### 第四步:Follow-up Action(McMillan 花最多篇幅的地方——進場只是前一半)
| 情境 | 動作 | 你的家規對應 |
|---|---|---|
| 對你有利 | 上滾(roll up)/把部位「保本化」(價差鎖住成本) | **賺1R→保本+移動停利** |
| 對你不利 | 減腿、轉價差降風險、到停損就認 | **跌破停損=出場,不討論** |
| 時間流逝 | 每天問:Theta 誰在付?買方沒動能就先撤 | **爆量後2-3天不進場**同源:時機錯=成本 |

#### 散戶鐵律(用你的數字)
1. **受限風險優先**:任何賣方都要戴帽(價差),裸賣=撿鋼板前的硬幣
2. **名目要合身**:TXO 一口名目≈238萬,你的組合111萬——一口就是2倍反手。**現階段用模擬倉練**
3. **買方只當事件保險**:連假/FOMC/財報前買,事件過就平,保費當學費
4. 說不出「IV 現在貴還便宜」就不進場——這就是選擇權版的體檢卡
""")
    st.markdown("---\n#### 📝 矩陣隨堂考(10題,連兩次滿分才算學會)")
    _MXQ = [
        ("McMillan 思維的第一步,進場前必須先有什麼?",
         ["會賺最多的策略", "方向觀點+波動率貴賤判斷,兩者缺一不可", "營業員報明牌", "最便宜的合約"],
         1, "策略=f(方向, IV)。先觀點後策略,順序不能反——說不出定價哪裡錯就沒有策略適合你。"),
        ("看漲、但 IV Rank 85%(很貴),矩陣說該用?",
         ["買價外Call梭哈", "牛市信用價差(賣Put戴帽收租)", "買跨式", "不動"],
         1, "IV貴→當賣方但戴帽。貴的時候買Call=方向對了還被Vega收錢。"),
        ("看漲、IV Rank 20%(很便宜),該用?",
         ["賣Put收租", "買Call或牛市借方價差", "鐵兀鷹", "賣跨式"],
         1, "IV便宜→當買方,保費打折。這是唯一該直接買Call的象限。"),
        ("覺得盤要橫很久、IV 又貴,收租結構是?",
         ["買勒式", "鐵兀鷹(受限雙賣)", "裸賣跨式", "買遠月Call"],
         1, "中性+IV貴=雙賣,但散戶必須戴帽(鐵兀鷹),裸賣跨式是撿硬幣。"),
        ("覺得快有大行情但不知方向、IV 便宜,該用?",
         ["買跨式/勒式", "賣跨式", "信用價差", "觀望"],
         0, "中性觀點+便宜保費=買跨式賭「會大動」。IV貴時同一觀點就不能這樣做。"),
        ("IV 貴便宜怎麼判斷?",
         ["看權利金絕對值", "IV vs HV20 + IV Rank(一年百分位),台指看台灣VIX", "看成交量", "問群組"],
         1, "波動率是價格。IV Rank>70=貴、<30=便宜;權利金絕對值大不代表貴。"),
        ("FOMC 前買 Put,會後指數真的跌了卻沒賺,最可能因為?",
         ["方向錯", "IV崩(事件落地保費洩氣)=Vega虧吃掉Delta賺,雙殺", "券商作弊", "手續費"],
         1, "事件前IV必貴、事件後必崩。買方要嘛買在IV便宜,要嘛事件過就平。"),
        ("Theta(時間價值)每天誰付給誰?",
         ["賣方付買方", "買方付賣方——買方拖越久越輸", "造市商吸收", "沒人付"],
         1, "買方天天付房租。所以買方要嘛快對,要嘛認錯,不能「放著等」。"),
        ("部位賺了1R之後,McMillan 的 follow-up 思想=你的哪條家規?",
         ["加倍攤平", "保本+移動停利(把部位保本化,只升不降)", "全部平掉", "改當賣方"],
         1, "Follow-up=賺了就鎖成本。你的「賺1R保本+收盤-2ATR移動」就是McMillan式後續管理。"),
        ("組合111萬、TXO一口名目238萬,現在想學選擇權,正確做法?",
         ["直接一口對沖", "微台對沖組合;選擇權用模擬倉/最小學習倉練greeks", "賣方收租補貼", "融資放大組合再對沖"],
         1, "一口=2倍反手,不是對沖。名目要合身——工具錯了,策略再對都是錯。"),
    ]
    _mxa = []
    for i, (q, opts, _, _) in enumerate(_MXQ):
        _mxa.append(st.radio(f"**{i+1}. {q}**", opts, index=None, key=f"mxq{i}"))
    if st.button("交卷", type="primary", key="mxq_submit"):
        score = 0
        for i, (q, opts, correct, why) in enumerate(_MXQ):
            ok = (_mxa[i] == opts[correct])
            score += ok
            (st.success if ok else st.error)(
                f"{i+1}. {'✅' if ok else '❌'} 正解:{opts[correct]}|{why}")
        st.metric("得分", f"{score}/{len(_MXQ)}")
        if score == len(_MXQ):
            st.balloons()
            st.success("滿分!去🧪模擬倉開始練——先把兩組示範倉的每日損益看懂。")
        elif score >= 7:
            st.warning("及格但有洞——錯的題就是Vega/Theta會收你錢的地方,回上面補。")
        else:
            st.error("先別碰選擇權。重讀矩陣表,每個象限都是真金白銀。")

# ════════════════ 模擬倉 ════════════════
with t_paper:
    import op_paper as _op
    _op = importlib.reload(_op)
    st.markdown("#### 🧪 模擬倉(期交所每日結算價自動洗損益;TXO每點50元)")
    if st.button("🔄 更新結算價並洗損益", key="op_mark"):
        try:
            _op.fetch_txo()
            _op.mark()
            st.success("已用最新結算價更新。")
        except Exception as _e:
            st.warning(f"更新失敗:{_e}")
    _op.seed_if_empty()
    dfp = _op.mark()
    _al = _op.alerts()
    if len(_al):
        st.error("🚨 觸發中:" + "|".join(
            f"{r['組合']} {r['腿']}{r['履約價']} {r['警示']}(現值{r['現值點']} vs "
            f"{'停損' + str(r['停損點']) if '停損' in str(r['警示']) else '停利' + str(r['停利點'])})"
            for _, r in _al.iterrows()) + " → 按下方「平倉」執行,不討論。")
    if dfp.empty:
        st.info("尚無模擬倉。")
    else:
        opn = dfp[dfp["狀態"] == "open"]
        pnl = pd.to_numeric(dfp["損益元"], errors="coerce")
        c1, c2, c3 = st.columns(3)
        c1.metric("未平倉腿數", len(opn))
        c2.metric("總損益",
                  f"{pnl.sum():+,.0f} 元" if pnl.notna().any() else "—")
        _b = pd.to_numeric(opn[opn["腿"].isin(["BC", "BP"])]["損益元"], errors="coerce").sum()
        _s = pd.to_numeric(opn[opn["腿"].isin(["SC", "SP"])]["損益元"], errors="coerce").sum()
        c3.metric("買方腿 vs 賣方腿", f"{_b:+,.0f} / {_s:+,.0f}",
                  "每天看這格:Theta 在把錢從左搬到右", delta_color="off")
        for 組合, g in dfp.groupby("組合"):
            gp = pd.to_numeric(g["損益元"], errors="coerce").sum()
            st.markdown(f"**{組合}**|小計 {gp:+,.0f} 元")
            st.dataframe(g[["開倉日", "腿", "月份", "履約價", "口數", "進場點",
                            "現值點", "停損點", "停利點", "警示", "損益元", "狀態",
                            "象限", "論點"]],
                         hide_index=True, width="stretch")
        st.caption("**觀察功課(每天30秒)**:①A組(買方)不跌就天天縮=Theta 房租;"
                   "②B組兩腿相加=淨收租,大漲時看「帽子」怎麼救命;③事件(連假)過後比較兩組——"
                   "這就是矩陣第一課的活教材。")

    with st.expander("➕ 開新模擬腿(必填象限+論點,說不出=不准開)"):
        f1, f2, f3, f4 = st.columns(4)
        _leg = f1.selectbox("腿", ["BC", "SC", "BP", "SP"], key="op_leg")
        _mon = f2.text_input("月份(如202610)", value="202610", key="op_mon")
        _stk = f3.number_input("履約價", value=47000, step=100, key="op_stk")
        _qty = f4.number_input("口數", 1, 10, 1, key="op_qty")
        _quad = st.selectbox("矩陣象限", [
            "看漲+IV便宜(買方)", "看漲+IV貴(信用價差)", "中性+IV便宜(買跨)",
            "中性+IV貴(鐵兀鷹)", "看跌+IV便宜(買方)", "看跌+IV貴(信用價差)",
            "事件保險", "學習觀察"], key="op_quad")
        g1, g2 = st.columns(2)
        _sl_in = g1.number_input("停損點(0=用預設:買方虧50%/賣方翻倍)",
                                 value=0.0, step=10.0, key="op_sl")
        _tp_in = g2.number_input("停利點(0=用預設:買方×2/賣方剩20%)",
                                 value=0.0, step=10.0, key="op_tp")
        _th = st.text_input("論點(為什麼開這腿)", key="op_th")
        if st.button("開倉(用今日結算價)", type="primary", key="op_add"):
            if not _th.strip():
                st.error("論點必填——說不出觀點就不准開,這是家規。")
            else:
                _cp = "C" if _leg in ("BC", "SC") else "P"
                _px = _op.settle_of(_mon.strip(), _stk, _cp)
                if _px is None:
                    st.error("查不到該合約結算價——檢查月份/履約價。")
                else:
                    _op.add_leg("自建", _leg, _mon.strip(), _stk, int(_qty),
                                _px, _quad, _th.strip(),
                                停損點=_sl_in or None, 停利點=_tp_in or None)
                    st.success(f"已開 {_leg} {_mon} {_stk} @ {_px} 點(模擬,停損停利已設)")
                    st.rerun()
    with st.expander("➖ 平倉"):
        dfp2 = _op.load()
        _opn2 = dfp2[dfp2["狀態"] == "open"]
        if _opn2.empty:
            st.info("無未平倉腿。")
        else:
            _sel = st.selectbox("選腿", _opn2.index.tolist(),
                                format_func=lambda i: f"{dfp2.loc[i,'組合']} {dfp2.loc[i,'腿']} "
                                f"{dfp2.loc[i,'月份']} {dfp2.loc[i,'履約價']}", key="op_close_sel")
            if st.button("用今日結算價平倉", key="op_close"):
                from twtime import now_tw as _nt
                _r = dfp2.loc[_sel]
                _cp = "C" if _r["腿"] in ("BC", "SC") else "P"
                _px = _op.settle_of(_r["月份"], _r["履約價"], _cp)
                if _px is None:
                    st.error("查不到結算價。")
                else:
                    dfp2.loc[_sel, ["狀態", "平倉日", "平倉點"]] = \
                        ["closed", f"{_nt():%Y-%m-%d}", _px]
                    _op.save(dfp2)
                    _op.mark()
                    st.success(f"已平 @ {_px} 點")
                    st.rerun()

st.caption(f"<span style='color:{MUTED}'>模擬倉為教學用,非投資建議;結算價來源:期交所 OpenAPI(每日)。"
           "權證(券商發行/美式/只能買方)請回 🎫 權證專區。</span>", unsafe_allow_html=True)

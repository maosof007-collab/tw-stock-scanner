# -*- coding: utf-8 -*-
"""
pages/41_期貨教室.py — 微台教室(教學+隨堂考+模擬倉;家規綁定)
=================================================================
「期貨教室順便綁進來,開始要做微台」(2026-10-27)。
三分頁:📚教室(六章+隨堂考)/🧪微台模擬倉(真實行情+保證金)/📊行情與籌碼。
紀律:模擬倉與實倉同規——🔴禁多單、開倉必填論點+停損。保證金動態抓(會過期教案)。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="期貨教室", page_icon="🎓", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("期貨教室(微台)", "MICRO FUTURES ACADEMY", "🎓")

import fut_paper as FP


@st.cache_data(ttl=1800, show_spinner="抓期交所行情…")
def _mkt():
    return FP.quote(), FP.margin()


q, mg = _mkt()
c1, c2, c3, c4 = st.columns(4)
if q:
    c1.metric(f"TMF 近月 {q['月份']}", f"{q['最新']:,.0f}" if q["最新"] else "—",
              f"{q['漲跌%']}({q['時段']})", delta_color="off")
    c2.metric("一般盤結算", f"{q['結算']:,.0f}" if q["結算"] else "—", f"OI {q['OI']}",
              delta_color="off")
if mg:
    c3.metric("原始保證金(動態)", f"{mg['原始']:,}", f"維持 {mg['維持']:,}", delta_color="off")
    c4.metric("每點價值", "10 元", f"保證金日期 {mg['日期']}", delta_color="off")
st.caption("保證金由期交所 OpenAPI 即時抓取——寫死的數字半年就過期(期貨 primer 教案)。")

tab_cls, tab_paper, tab_mkt = st.tabs(["📚 教室(六章+隨堂考)", "🧪 微台模擬倉", "📊 行情與籌碼"])

# ════════════════ 教室 ════════════════
_MG0 = mg["原始"] if mg else 35050
_CHAPTERS = [
    ("第 1 章|微台是什麼", f"""
**微型臺指期貨(TMF)**:追蹤加權指數的期貨,**1 點=10 元**——大台的 1/20、小台的 1/5。
指數 46,000 時一口名目價值 46 萬元,但你只要押**原始保證金 {_MG0:,} 元**就能持有一口
→ 槓桿約 13 倍。這是雙面刃:指數動 1%(460 點)= 你的保證金動 **4,600 元(約 {4600/_MG0*100:.0f}%)**。
到期:每月第三個週三結算;有週選嗎?微台只有月契約。交易時段:日盤 08:45-13:45、夜盤 15:00-次日 05:00。""",
     "微台一點多少錢?", ["10 元", "50 元", "200 元"], 0),
    ("第 2 章|保證金三層與追繳", f"""
三層(動態,期交所隨波動調):**原始 {_MG0:,}**(開倉門檻)→ **維持 {mg['維持'] if mg else 26900:,}**
(低於它=追繳)→ 結算。追繳(Margin Call)要在期限內補回**原始**水準,補不了就被強制平倉(斷頭)。
家規換算:帳戶只放一口原始保證金=滿槓桿賭徒;**一口微台背後至少放 2~3 倍原始保證金**,
讓 500 點的波動(5,000 元)不會逼你在最壞的時點離場。""",
     "帳戶淨值跌破哪一層會收到追繳?", ["原始保證金", "維持保證金", "結算保證金"], 1),
    ("第 3 章|結算日與轉倉", """
每月**第三個週三**結算,結算價=當日 13:00-13:30 加權指數算術平均。持倉到結算=現金差價自動了結。
要續抱就**轉倉**:結算週把近月平掉、開次月(注意價差=正逆價差成本)。
教案:結算週的週一到週三,行情常有「結算行情」雜訊——新手別在結算週開新倉。""",
     "台指期每月結算日是?", ["第三個週三", "最後一個週五", "每月 15 日"], 0),
    ("第 4 章|夜盤與跳空", """
夜盤 15:00-05:00 跟著美股走——**台股的跳空風險,期貨用夜盤先吸收**。
10/17 教案:夜盤 -1,100 點,現貨週一開盤前你已經知道要發生什麼。
持倉過夜=暴露在美股整晚的波動裡;一口微台過夜,夜盤 2% 的波動=±9,000 元上下搖。
家規:事件日(CPI/FOMC/台積法說)前夜,倉位減半或歸零——戰報的事件庫就是為這個存在。""",
     "夜盤最大的風險來源?", ["台股自己的消息", "美股與國際行情", "成交量太大"], 1),
    ("第 5 章|成本:稅與手續費", """
期交稅:**十萬分之 2**(買賣各收,按契約值)——46,000 點一口約 9 元。
手續費:微台行情價單邊約 8~15 元(可談)。一來一回全成本約 **35~50 元=3.5~5 點**。
含義:微台做 10 點以內的超短線,成本吃掉一半——**它適合波段與事件交易,不適合刮頭皮**。""",
     "微台一來一回的全成本約等於幾點?", ["0.5 點", "3.5~5 點", "20 點"], 1),
    ("第 6 章|風控(家規期貨版)", f"""
股票家規平移過來,三條鐵律:
① **先算風險再開倉**:停損點數 × 10 元 × 口數 = 這筆交易的錢;單筆風險 ≤ 帳戶 2%
②(例)帳戶 20 萬 → 單筆風險 4,000 元 → 停損設 200 點就只能開 **2 口**,設 400 點只能 **1 口**
③ **風險燈 🔴 禁開多單**(模擬倉已內建這條);移動停利只升不降、出場越鬆越賺的波段鐵律同樣適用
最重要的一句:**期貨的槓桿不會讓你更會看行情,只會放大你本來的樣子。**""",
     "帳戶 20 萬、單筆風險 2%、停損 400 點,最多開幾口微台?", ["1 口", "2 口", "5 口"], 0),
]
with tab_cls:
    for i, (title, body, qz, opts, ans) in enumerate(_CHAPTERS):
        with st.expander(title, expanded=(i == 0)):
            st.markdown(body)
            pick = st.radio(f"📝 隨堂考:{qz}", opts, index=None, key=f"qz{i}")
            if pick is not None:
                st.success("✅ 正確!") if opts.index(pick) == ans else \
                    st.error(f"❌ 再想想——答案是「{opts[ans]}」")

# ════════════════ 模擬倉 ════════════════
with tab_paper:
    last = q["最新"] if q and q["最新"] else (q["結算"] if q else None)
    try:
        import json as _j
        _lamp = _j.loads((ROOT / "data" / "_market_risk.json").read_text(encoding="utf-8"))["lamp"]
    except Exception:
        _lamp = "?"
    st.markdown(f"風險燈 **{_lamp}**|TMF 參考價 **{last:,.0f}**" if last else f"風險燈 {_lamp}")
    f1, f2, f3, f4 = st.columns(4)
    side = f1.selectbox("方向", ["多", "空"])
    lots = f2.number_input("口數", 1, 50, 1)
    px = f3.number_input("進場價", value=float(last) if last else 46000.0, step=1.0)
    stop = f4.number_input("停損(點)", value=200.0, step=50.0)
    thesis = st.text_input("論點(必填——說不出觀點=沒有交易)",
                           placeholder="例:連環崩後第5日+台幣止貶訊號出現,搶反彈至20EMA")
    rk = stop * 10 * lots
    st.caption(f"這筆交易的風險=**{rk:,.0f} 元**;若帳戶 20 萬,佔 {rk/200000*100:.1f}%"
               f"(家規上限 2%)。保證金需求約 {(_MG0)*lots:,} 元。")
    if st.button("🧪 開倉(模擬)", type="primary"):
        st.info(FP.open_pos(side, int(lots), float(px), float(stop), thesis))
    df = FP.mark(FP.load(), last)
    if len(df):
        st.dataframe(df, hide_index=False, use_container_width=True)
        openers = df[df["狀態"] == "持倉"]
        if len(openers):
            i1, i2, i3 = st.columns(3)
            idx = i1.selectbox("平倉部位", openers.index.tolist())
            cpx = i2.number_input("平倉價", value=float(last) if last else 46000.0,
                                  step=1.0, key="cpx")
            if i3.button("平倉"):
                st.info(FP.close_pos(int(idx), float(cpx)))
                st.rerun()
        done = df[df["狀態"] == "平倉"]
        if len(done):
            st.caption(f"戰績:{len(done)} 筆|總損益 {done['損益元'].sum():+,.0f} 元"
                       f"|平均 {done['R'].mean():+.2f}R|勝率 {(done['損益元']>0).mean()*100:.0f}%")

# ════════════════ 行情與籌碼 ════════════════
with tab_mkt:
    try:
        tf = pd.read_csv(ROOT / "data" / "_taifex_fi.csv")
        st.markdown("**外資台指期淨未平倉(風險燈訊號②的原料)**")
        st.dataframe(tf.tail(10), hide_index=True, use_container_width=True)
        st.caption("淨空沉重+單日急變≥5,000 口=風險燈加分;連兩日回補>3,000 口=反彈檢查表第一條。")
    except Exception:
        st.info("外資期貨資料待 run_daily 更新。")
    st.page_link("pages/0_總經.py", label="🌡️ 搭配總經溫度計看大盤位置")
    st.page_link("pages/26_晨報.py", label="🌅 事件日查晨報行事曆(結算週/CPI/法說)")

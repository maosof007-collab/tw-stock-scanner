# -*- coding: utf-8 -*-
"""海報總覽頁:全部研究海報+報紙期刊的超連結目錄(一屏導航)。"""
from pathlib import Path

from newspaper import save_issue
from poster import shell, card

PAPERS = Path(__file__).parent / "data" / "papers"
DATE = "20261111"

# (code, 名, 海報檔, 報紙檔, 燈, 一句判定, 關鍵數字)
STOCKS = [
    ("2465", "麗臺", "🔥 強勢進行式", "轉骨真/命門在輝達——年高進行式,只做突破單",
     "136 元=252日新高|Q3 EPS 4.03|融資紅燈"),
    ("1569", "濱川", "🔥 強勢進行式", "台階成立——10月5.3億踩上損益兩平的量,裁判是Q3毛利率",
     "95 元(距高-5%)|10月+134%|大戶8週+5.9pp"),
    ("6271", "同欣電", "🌱 復甦/打底", "衛星是葉子車用是樹幹——籌碼四綠,等收盤站上211",
     "203.5(距高-33%)|Q3毛利率33.7%|11/10上榜V轉"),
    ("6531", "愛普*", "🌱 復甦/打底", "矽電容現貨加速vs VHM夢想折現——融資+4,029張是雷",
     "730(距高-44%)|10月+156%創高|中性PE 10.8倍"),
    ("3264", "欣銓", "🌱 復甦/打底", "跌的是籌碼不是基本面——等外資連3買,不接大戶的刀",
     "192(距高-34%)|10月18.6億+48%|大戶8週-13pp"),
    ("8103", "瀚荃", "🌱 復甦/打底", "AI電源動能在、4億平台鬆動+大戶在退——等雙確認",
     "85.8(距高-37%)|10月+35%|大戶8週-5.2pp"),
    ("3287", "廣寰科", "⚠ 警示教材", "融券311張的主力控盤局——11/11開板收黑=出貨進行式",
     "79.2(高88.6)|10月營收-16%|不入觀察名單"),
    ("4909", "新復興", "⚠ 警示教材", "融資=日均量5〜8倍的套牢池——反彈全是解套賣壓",
     "30.0(距高-60%)|營收連六月負|重看=轉正+融資腰斬"),
    ("4977", "眾達-KY", "🛰 CPO 全鏈", "全鏈唯一MA20上——博通ELSFP題材+800G現在式,輪動第一棒",
     "187(距高-32%)|10月+117%|大戶+3.5pp·權證佈局中"),
    ("6442", "光聖", "🛰 CPO 全鏈", "價格腰斬錢沒走——權證大錢續佈局,深蹲高跳首選候補",
     "1135(距高-55%)|10月18.37億+83%|大戶持平"),
    ("3363", "上詮", "🛰 CPO 全鏈", "FAU耦光正宗——時程戰爭主戰場,最深受害者之一",
     "411(距高-61%)|10月+70%|大戶-2.5pp"),
    ("4979", "華星光", "🛰 CPO 全鏈", "傳綁Marvell的800G出貨者——營收真,客戶故事待證",
     "383(距高-50%)|10月+75%|大戶-6.0pp"),
    ("3450", "聯鈞", "🛰 CPO 全鏈", "⚠營收+75%救不了-13.6pp——全鏈最大出貨,反彈排最後",
     "370(距高-43%)|10月12.2億+75%|權證降溫"),
    ("4908", "前鼎", "🛰 CPO 全鏈", "ELS樣品驗證中——69倍前瞻PE,夢先付了錢",
     "170(距高-46%)|10月+47%|大戶-6.8pp"),
    ("3234", "光環", "🛰 CPO 全鏈", "+144%全鏈第一但無法歸因——透明度是最大折價",
     "138(距高-37%)|10月+144%|大戶-5.9pp"),
    ("3163", "波若威", "🛰 CPO 全鏈", "⚠雙弱:跌最深-64%+營收最弱+11%——反彈別找它",
     "476(距高-64%)|10月+11%|大戶-2.9pp"),
    ("6426", "統新", "🛰 CPO 全鏈", "衛星+CPO雙題材濾光片——Q2轉盈2.22,處置前科",
     "266(距高-35%)|10月+61%|大戶-8.5pp"),
    ("1597", "直得", "🛰 CPO 全鏈", "耦光設備對照組——題材是借的,本業傳動才是本體",
     "114(距高-49%)|10月+42%|二階受惠"),
    ("3055", "蔚華科", "🛰 CPO 全鏈", "檢測站卡位——設備認列月營收鋸齒,用季看不用月看",
     "131.5(距高-42%)|9月-57%→10月+192%|看Q4合計"),
]

GROUPS = ["🔥 強勢進行式", "🌱 復甦/打底", "⚠ 警示教材", "🛰 CPO 全鏈"]


def stock_rows(grp):
    rows = ""
    for code, name, g, verdict, stats in STOCKS:
        if g != grp:
            continue
        poster = f"{code}海報_{DATE}.html"
        paper_links = ""
        for p in sorted(PAPERS.glob(f"{code}_*.html"), reverse=True)[:1]:
            paper_links = f' <a href="./{p.name}" style="color:#1b5fa8">📰 報紙版</a>'
        rows += (f'<div class="kv" style="border-bottom:1px solid #e4ebf4;padding:7px 0;margin:0">'
                 f'<div class="k" style="font-size:15px"><a href="./{poster}" '
                 f'style="color:#0d2b52;text-decoration:underline">{name}({code})海報</a>{paper_links}</div>'
                 f'<div class="v" style="font-weight:700;margin:2px 0">{verdict}</div>'
                 f'<div class="v" style="font-size:12.5px;color:#567">{stats}</div></div>')
    return rows


cols = []
for grp in GROUPS:
    cols.append(card(grp, stock_rows(grp)))

# 期刊庫(報紙版全列表)
issues = sorted(PAPERS.glob("*.html"), key=lambda p: p.stem.split("_")[-1], reverse=True)
lib = ""
for p in issues:
    stem = p.stem
    code, _, d = stem.partition("_")
    if "海報" in code or code == "總覽":
        continue
    lib += (f'<tr><td><a href="./{p.name}" style="color:#0d2b52;text-decoration:underline">'
            f'{code}</a></td><td class="n">{d[:4]}/{d[4:6]}/{d[6:]}</td></tr>')
c_lib = card("📰 報紙期刊庫(全部)", f'<table><tr><th>期刊</th><th>日期</th></tr>{lib}</table>')

c_note = card("使用說明", """
<ul class="ck">
<li>在 <b>財經報頁</b>看:上方「選期」下拉切換各海報/期刊(iframe 內超連結不跳轉,屬正常)</li>
<li>把 <b>data/papers 資料夾</b>整包複製出去後,用瀏覽器開本頁,<b>所有連結可直接點</b></li>
<li class="wn">海報判定以產出日(2026/11/11)數據為準,價位會過期——以 app 即時頁為主</li>
</ul>""")

cols[0] += c_note
cols[2] += c_lib

html = shell(
    title_html="研究海報<b>總覽</b>",
    subtitle="8 檔個股研究海報+報紙期刊庫 · 分組:強勢進行式/復甦打底/警示教材",
    brand="TW·BACKTEST",
    cols=cols,
    footer="2026/11/11 · 本頁為導航目錄 · 各海報為研究筆記非投資建議")
p = save_issue("總覽", DATE, html)
print("saved:", p)

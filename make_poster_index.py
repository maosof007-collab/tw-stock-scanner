# -*- coding: utf-8 -*-
"""海報總覽頁:掃 data/papers,把全部研究海報+報紙期刊做成超連結目錄。
不用手動跑:poster.save_poster / newspaper.save_issue 每存一份就自動重產。手動重跑:python -X utf8 make_poster_index.py"""
import re
from pathlib import Path

import pandas as pd

from newspaper import save_issue
from poster import shell, card

from twtime import now_tw

PAPERS = Path(__file__).parent / "data" / "papers"

# (code, 名, 分組, 一句判定, 關鍵數字)——現在只有「分組」還在用;判定改讀海報自己的副標
STOCKS = [
    ("2465", "麗臺", "🔥 強勢進行式", "轉骨真/命門在輝達——年高進行式,只做突破單",
     "136 元=252日新高|Q3 EPS 4.03|融資紅燈"),
    ("1569", "濱川", "🔥 強勢進行式", "台階成立——10月5.3億踩上損益兩平的量,裁判是Q3毛利率",
     "95 元(距高-5%)|10月+134%|大戶8週+5.9pp"),
    ("4916", "事欣科", "🔥 強勢進行式", "外資一週 7%→18.7%——上一輪買到 20.8% 後三個月賣光;大戶在收,但這種錢待不久",
     "112.5(11/13 漲停)|10月營收+112%|融資占股本 11.6%"),
    ("6271", "同欣電", "🌱 復甦/打底", "衛星是葉子車用是樹幹——籌碼四綠,等收盤站上211",
     "203.5(距高-33%)|Q3毛利率33.7%|11/10上榜V轉"),
    ("6531", "愛普*", "🌱 復甦/打底", "矽電容現貨加速vs VHM夢想折現——融資+4,029張是雷",
     "730(距高-44%)|10月+156%創高|中性PE 10.8倍"),
    ("3264", "欣銓", "🌱 復甦/打底", "跌的是籌碼不是基本面——等外資連3買,不接大戶的刀",
     "192(距高-34%)|10月18.6億+48%|大戶8週-13pp"),
    ("8103", "瀚荃", "🌱 復甦/打底", "AI電源動能在、4億平台鬆動+大戶在退——等雙確認",
     "85.8(距高-37%)|10月+35%|大戶8週-5.2pp"),
    ("1216", "統一", "🛡 退路/內需", "大盤大跌的 22 天有 20 天跌得比大盤少——代價是營收只年增 4%,獲利有一塊來自統一證",
     "78.5(11/16)|前三季 EPS 3.70|殖利率 3.8%"),
    ("1232", "大統益", "🛡 退路/內需", "沙拉油市占約 55%,第二大的中聯停工、復工兩度被駁回——但一天只成交兩百張,政府同時開放免稅進口",
     "165(11/16)|Q3 EPS 3.32|7~10 月營收 +33~42%"),
    ("3312", "弘憶股", "🌱 復甦/打底", "在 11/6 錯殺名單裡但沒收復過——營收年增兩成是真的,毛利率只有 5%",
     "37.85(11/16)|跌前價 45.25|前10月營收+20%"),
    ("8176", "智捷", "⚠ 警示教材", "毛利率 42% 是真的,但日均成交只有 90 萬——研究歸研究,交易碰不得",
     "11.35|H1 營收-23%|半個市值是現金"),
    ("3287", "廣寰科", "⚠ 警示教材", "融券311張的主力控盤局——11/11開板收黑=出貨進行式",
     "79.2(高88.6)|10月營收-16%|不入觀察名單"),
    ("4909", "新復興", "⚠ 警示教材", "融資=日均量5〜8倍的套牢池——反彈全是解套賣壓",
     "30.0(距高-60%)|營收連六月負|重看=轉正+融資腰斬"),
    ("3008", "大立光", "🛰 CPO 全鏈", "本業13年最差的一季,換來高盛11,000目標——時程戰爭最大槓桿",
     "5065(距高-35%)|Q3毛利率42.2%新低|FAU明年開產能"),
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
    ("1568", "倉佑", "📣 法說對帳", "半導體零件才占 3%,公司說 2027 年雙位數——先等馬來西亞廠認證",
     "27.8(距高-44%)|前三季 EPS 1.41|體檢 2紅2黃"),
    ("3178", "公準", "📣 法說對帳", "毛利率 9%→28% 連四季回升——高科廠啟用與否還查不到",
     "62.3(距高-24%)|Q3 EPS 0.66|10月營收創高+50%"),
    ("2436", "偉詮電", "📣 法說對帳", "前三季獲利 64% 來自業外——本業營益率連兩季下滑",
     "55.0(距高-35%)|10月營收月減27%|11/19 法說"),
    ("6279", "胡連", "📣 法說對帳", "營收前10月+13%但毛利率連三季不到 27%——EPS 掉的三個原因只有一個是本業",
     "97.3(一年新低區)|Q3 毛利率 26.9%|約 8.6 倍"),
    ("2338", "光罩", "📣 法說對帳", "本業剛打平、財務靠增資撐——CoWoS 大尺寸光罩 Q4 才開始貢獻",
     "38.6(距高-37%)|前10月營收-2.1%|11/17 法說"),
]

GROUPS = ["🔥 強勢進行式", "🌱 復甦/打底", "🛡 退路/內需", "📣 法說對帳", "⚠ 警示教材", "🛰 CPO 全鏈"]
NEW_GROUP = "🆕 尚未分組(自動掃到)"
GROUP_OF = {c: g for c, _n, g, *_ in STOCKS}     # 上面的清單現在只用來分組;沒列到的海報照樣會出現
_LINK = 'style="color:#0d2b52;text-decoration:underline"'


def _meta(p: Path) -> dict:
    """從海報 HTML 自己身上讀標題與副標(一句話結論),不靠手寫。"""
    h = p.read_text(encoding="utf-8", errors="ignore")
    g = lambda pat: (re.sub(r"<[^>]+>", "", m.group(1)).strip() if (m := re.search(pat, h, re.S)) else "")
    head, _, d = p.stem.rpartition("_")
    return dict(path=p, key=head[:-2] if head.endswith("海報") else head, date=d, is_poster=head.endswith("海報"),
                title=g(r"<h1>(.*?)</h1>"), sub=g(r'class="sub">(.*?)</div>'))


def scan() -> list[dict]:
    """data/papers 裡除了總覽以外的每一份(海報+報紙),最新在前。"""
    out = [_meta(p) for p in PAPERS.glob("*.html") if not p.name.startswith("總覽")]
    out.sort(key=lambda m: (m["date"], m["is_poster"], m["key"]), reverse=True)
    return out


def _row(m: dict, name: str, paper: Path | None) -> str:
    pl = f' <a href="./{paper.name}" style="color:#1b5fa8">📰 報紙版</a>' if paper else ""
    return (f'<div class="kv" style="border-bottom:1px solid #e4ebf4;padding:7px 0;margin:0">'
            f'<div class="k" style="font-size:15px"><a href="./{m["path"].name}" {_LINK}>{name}</a>{pl}</div>'
            f'<div class="v" style="font-weight:700;margin:2px 0">{m["sub"] or m["title"]}</div>'
            f'<div class="v" style="font-size:12.5px;color:#567">海報 {m["date"][4:6]}/{m["date"][6:]}</div></div>')


def build() -> Path:
    """掃 data/papers 重產總覽;poster.save_poster / newspaper.save_issue 每存一份就會自動呼叫。"""
    date = now_tw().strftime("%Y%m%d")
    items = scan()
    if not items:
        raise RuntimeError("data/papers 裡沒有任何海報或報紙,不產總覽")
    names = pd.read_csv(Path(__file__).parent / "data" / "stock_list.csv", dtype=str, encoding="utf-8-sig").set_index("code")["name"].to_dict()
    latest = {}                                       # 每個題目只留最新一張海報
    for m in items:
        if m["is_poster"]:
            latest.setdefault(m["key"], m)
    papers = {}                                       # 同代號最新一份報紙
    for m in items:
        if not m["is_poster"]:
            papers.setdefault(m["key"], m["path"])
    stock = {k: m for k, m in latest.items() if k in names}
    group = {k: m for k, m in latest.items() if k not in names}

    cards = [(f"🗂 族群海報({len(group)})", "".join(_row(m, f"{k} 族群海報", None) for k, m in group.items()), len(group))]
    for g in GROUPS + [NEW_GROUP]:
        ks = [k for k in stock if GROUP_OF.get(k, NEW_GROUP) == g]
        if ks:
            cards.append((f"{g}({len(ks)})", "".join(_row(stock[k], f"{names[k]}({k})海報", papers.get(k)) for k in ks), len(ks)))
    half, col1, col2, acc = sum(n for *_, n in cards) / 2, "", "", 0
    for t, body, n in cards:                          # 兩欄大致平分
        if acc < half:
            col1 += card(t, body)
        else:
            col2 += card(t, body)
        acc += n

    lib = ""
    for m in items:
        label = f"{names[m['key']]} {m['key']}" if m["key"] in names else m["key"]
        lib += (f'<tr><td class="n">{m["date"][4:6]}/{m["date"][6:]}</td><td>{"🖼 海報" if m["is_poster"] else "📰 報紙"}</td>'
                f'<td><a href="./{m["path"].name}" {_LINK}>{label}</a></td></tr>')
    n_post = sum(m["is_poster"] for m in items)
    c_lib = card(f"📚 全部刊物:海報 {n_post} 張+報紙 {len(items) - n_post} 份(最新在上)",
                 f'<table><tr><th>日期</th><th>類型</th><th>名稱</th></tr>{lib}</table>')
    c_note = card("使用說明", """
<ul class="ck">
<li>本頁是<b>自動產生</b>的:每存一張海報或一份報紙,就會掃 data/papers 重產;每張的一句話取自海報自己的副標</li>
<li>在 <b>財經報頁</b>看:本頁的連結<b>直接點就會打開</b>那一份,上方有「← 回海報總覽」;也可以用「選期」下拉切換</li>
<li>把 <b>data/papers 資料夾</b>整包複製出去後,用瀏覽器開本頁,<b>所有連結可直接點</b></li>
<li class="wn">海報判定以各自產出日的數據為準(每列標了海報日期),價位會過期——以 app 即時頁為主</li>
</ul>""")

    html = shell(
        title_html="研究海報<b>總覽</b>",
        subtitle=f"個股海報 {len(stock)} 檔、族群海報 {len(group)} 張、報紙 {len(items) - n_post} 份 · 掃描資料夾自動產生,最新一張 {items[0]['date'][4:6]}/{items[0]['date'][6:]}",
        brand="TW·BACKTEST",
        cols=[col1 + c_note, col2, c_lib],
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 本頁為導航目錄 · 各海報為研究筆記非投資建議")
    p = save_issue("總覽", date, html)
    for old in PAPERS.glob("總覽_*.html"):            # 總覽只留最新一份,免得選單裡出現兩個
        if old != p:
            old.unlink()
    return p


if __name__ == "__main__":
    print("saved:", build())

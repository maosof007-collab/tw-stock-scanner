# -*- coding: utf-8 -*-
"""財經報:光頡 3624 專刊 — 量先到、理由後到(迴轉率榜首×上游洞見×10/6法說三路合流)。"""
from newspaper import shell, save_issue

T = """<b>光頡 3624</b> <span class="num">166.5</span>|距年高 <span class="num">-5.7%</span>(年低 36.6 起漲 4.5 倍)
|九月營收 <span class="up">+67.4%(連三月加速)</span>|2Q26 毛利率 <span class="up">32.8%</span> EPS <span class="num">1.11</span>
|大戶持股 <span class="up">53%→61%(五週)</span>|10/8 本系統迴轉率榜首 <span class="num">40.7%</span>"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">10/6 法說簡報+上游洞見下篇+本系統迴轉率雷達</span></div>
<div class="head1">量先到 理由後到 一顆電阻的漲價故事</div>
<div class="deck">10/8 它以 40.7% 迴轉率登上本系統雷達榜首——當時只知道錢在對打,不知道為什麼。一週後理由到齊:AI 電源缺料漲價、產能滿載、九月營收 +67.4% 連三月加速,10/6 法說攤出 1~8 月 EPS 2.94,已超過去年全年。</div>
<div class="byline">本報整理|素材:光頡 2026/10/06 法說簡報、上游洞見〈AI 電源兩段升級〉下篇、本系統價量籌碼</div>
<div class="cols2"><div>
<p class="dropcap">光頡做電阻——精密電阻佔 57%、一般電阻 36%,加一點電感電容。這種公司平常沒人看:單價以「分」計算、下游分散、股價十年如一日。直到 AI 伺服器把電源變成瓶頸:每台 PSU 都要鋪電阻,PSU 套數爆增+瓦數升級,而日系大廠(KOA 等)把產能讓給車用,大尺寸電源料出現缺口。</p>
<p>法說數字把轉折說得很清楚:1~8 月營收 23.4 億、<span class="hl">毛利率 32.5%</span>(2025 全年才 25.3%)、EPS 2.94——**八個月賺贏去年全年的 1.86**。2Q26 單季:營收 8.95 億(+26.8%)、毛利率 32.8%、營益率 18.5%、EPS 1.11。月營收更兇:7 月 +43%、8 月 +65.8%、九月 <span class="hl">+67.4%</span>,對照公司全年指引僅 +15%——**公司自己都低估了這波**。</p>
<p>上游洞見下篇給的定位一針見血:光頡的量「跟著 PSU 套數走,與 800V 關聯低」——它不是技術升級故事,是**元件漲價循環**故事:產能接近滿載、部分產品已漲價、2027 上半年前精密電阻產能只增約 18%。供給卡死+需求爆發=價格就是獲利彈性的全部來源。</p>
<p>籌碼面是這一期最驚人的一張表:大戶(400 張以上)持股比例五週從 53.4% 一路吸到 <span class="hl">61.2%</span>,同期外資 20 日累計買超接近零——**這是一場純內資大戶的盤**,10/8 那天 40.7% 的迴轉率就是他們在換手定價。</p>
</div><div class="sidebar"><h3>三十秒看懂光頡</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">電阻(精密 57%+一般 36%)+電感電容;新竹×2/高雄/無錫四廠</div></div>
<div class="kv"><div class="k">應用</div><div class="v">車用 44%、工業 21%、AI 13%、航太軍用 8%、醫療 5%</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">PSU 套數爆增+日廠讓出電源料+產能滿載=漲價循環</div></div>
<div class="kv"><div class="k">獲利</div><div class="v">1~8 月 EPS 2.94>2025 全年 1.86;毛利率 25.3→32.5%</div></div>
<div class="kv"><div class="k">體質</div><div class="v">零短期借款、權益比 80%——傳產級乾淨資產表</div></div>
<div class="kv"><div class="k">籌碼</div><div class="v">大戶 53→61%(五週)、外資缺席、10/8 迴轉率 40.7% 榜首</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>生意|電阻為什麼突然值錢</h2></div>
<div class="head1" style="font-size:28px">三個力同時擠一顆小元件</div>
<div class="card"><h4>①需求:跟 PSU 套數走(不跟 800V 走)</h4>AI 電源第一段升級(54V 內拉瓦數)=PSU 量價齊升,每台 PSU 的精密電阻/功率電阻用量跟著鋪。注意誠實標註:上游洞見明言它「與 800V 關聯低」——第二段升級(2027 後)不是它的故事,別把題材掛錯層。</div>
<div class="card"><h4>②供給:日廠退、自家滿、擴產慢</h4>日系(KOA 等)將產能轉向車用,讓出電源用大尺寸料;光頡產能接近滿載;2027H1 前精密電阻產能僅 +18%——三件事疊出賣方市場。1~8 月資產表的指紋:存貨 +37.9%、應收 +31.9%,典型「漲價循環中的備貨與放帳」。</div>
<div class="card"><h4>③價格:獲利彈性的全部來源</h4>毛利率 25.3%(2025)→28.6%(1Q26)→32.8%(2Q26)——營收 +26.8% 而營業利益 +51.4%,漲價的營業槓桿全開。對照同鏈的信昌電(MLCC 均漲 30%)、廣閎科(漲約 20%):**整個電源元件層都在同一個漲價循環裡**,光頡不是孤例,是族群。</div>
<p>基本盤別忘了:車用 44% +工業 21% 才是本業大頭(AI 僅 13%)——這是雙面刃:AI 的獲利槓桿要打折,但市場若殺 AI 題材,它的非 AI 底盤也比純 AI 股扛跌。</p></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|漲價循環的指紋</h2></div>
<div class="head1" style="font-size:28px">營收加兩成六 營業利益加五成一</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">7.06</td><td class="num">29.08%</td><td class="num">15.50%</td><td class="num hl">-0.02(匯損業外)</td></tr>
<tr><td>3Q25</td><td class="num">6.94</td><td class="num">22.19%</td><td class="num">6.13%</td><td class="num">0.69</td></tr>
<tr><td>4Q25</td><td class="num">6.57</td><td class="num">23.30%</td><td class="num">7.20%</td><td class="num">0.65</td></tr>
<tr><td>1Q26</td><td class="num">7.28</td><td class="num">28.56%</td><td class="num">13.25%</td><td class="num">0.75</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">8.95</td><td class="num gd">32.79%</td><td class="num gd">18.51%</td><td class="num gd">1.11</td></tr></table>
<table><tr><th>月營收</th><th>百萬</th><th>YoY</th></tr>
<tr><td>2026/06</td><td class="num">322.1</td><td class="num">+28.7%</td></tr>
<tr><td>2026/07</td><td class="num">351.6</td><td class="num">+43.3%</td></tr>
<tr><td>2026/08</td><td class="num">367.1</td><td class="num gd">+65.8%</td></tr>
<tr><td><b>2026/09</b></td><td class="num gd">380.2</td><td class="num gd">+67.4%</td></tr></table>
<p>估值帳:近 4 季 EPS 3.20 → 166.5 元約 52 倍;但用加速後的軌跡(1~8 月 2.94,下半年單季 1.3~1.5 節奏)看 2026 全年約 4.5~5 元,對應 **33~37 倍**。被動元件漲價循環股的歷史劇本是「循環頂給低估值」——市場不會為漲價付成長股倍數,**這檔的估值天花板由「漲價還能漲幾季」決定,不由 EPS 決定**。零短借+80% 權益比的資產表,給了循環逆轉時的安全墊。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>籌碼|一場內資大戶的定價戰</h2>
<span class="src">TDCC 週資料+本系統迴轉率雷達</span></div>
<div class="head1" style="font-size:28px">五週吸走 7.8 個百分點 外資全程缺席</div>
<table><tr><th>週</th><th>大戶(400張+)持股%</th></tr>
<tr><td>09/04</td><td class="num">53.37</td></tr>
<tr><td>09/11</td><td class="num">57.09</td></tr>
<tr><td>09/18</td><td class="num">53.26</td></tr>
<tr><td>09/24</td><td class="num">57.26</td></tr>
<tr><td>10/02</td><td class="num">58.85</td></tr>
<tr><td><b>10/08</b></td><td class="num gd">61.21</td></tr></table>
<div class="bigfact"><div>10/8 單日迴轉率(本系統雷達全市場第一)</div><div class="n">40.7%</div>
<div>當日 +9.72%、成交 83.5 億——籌碼一天換手四成,大戶邊換手邊墊高持股</div></div>
<p>外資 20 日累計買超趨近於零——**行情全由內資大戶定價**。這種結構的特性:走勢猛、回檔也猛,沒有外資型的持續性買盤護底;大戶比例一旦轉降(TDCC 每週五更新,頁18 自動盯),就是行情熄火的第一個訊號,比任何技術線都早。位置:166.5 距年高 -5.7%、60 日 +70%,按家規屬**發動中後段**,迴轉率 40% 那天正是「爆量日+2~3 天禁入」的教科書場景。</p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">漲價循環股 盯三個日期兩個比例</div>
<div class="card"><h4>追蹤清單</h4>①月營收 YoY 何時從 +67% 開始降速(循環頂的第一個訊號) ②3Q26 毛利率能否站上 34%(漲價續航證據) ③大戶持股 61% 何時轉降(頁18 每週自動) ④2027H1 擴產 +18% 開出時=供給解鎖、價格鬆動的倒數 ⑤AI 佔比 13% 能否往 20% 走(結構升級 vs 純漲價的分界)</div>
<div class="card"><h4>反方劇本</h4>①KOA 等日系若回頭搶電源料,漲價邏輯崩(台達佔營收 8~9%,大客戶議價) ②與 800V 關聯低——第二段升級行情輪不到它,題材有天花板 ③存貨 +38% 在循環逆轉時變跌價損失 ④內資大戶盤,61% 高持股=出貨時無人接 ⑤52 倍 TTM 已給足「循環延續」的價,降速一個月就殺估值</div>
<p><b>本報判準</b>:這是標準的「量先到、理由後到」案例——我們的雷達 10/8 抓到量,上游洞見一週後補上理由,法說同日給了數字。操作上它已在發動中後段:照家規不追爆量;若信漲價循環未完,等迴轉率降溫+回測 20 日線不破的二進場點;大戶比例轉降或月營收降速,兩者任一出現即離場,不等基本面確認。</p></div>"""

_QA = [
    ("光頡的主力產品與佔比?", "精密電阻 57%+一般電阻 36%;應用端車用 44%、工業 21%、AI 13%。"),
    ("為什麼說它「量跟 PSU 套數走」?", "每台 PSU 都要鋪電阻,AI 第一段升級=PSU 量價齊升;但與 800V 第二段關聯低。"),
    ("供給端三個擠壓因素?", "日廠(KOA 等)讓出電源料、自家產能滿載、2027H1 前精密電阻產能僅 +18%。"),
    ("1~8 月最震撼的數字?", "EPS 2.94,八個月賺贏 2025 全年的 1.86;毛利率 25.3%→32.5%。"),
    ("九月營收表現?", "3.80 億、+67.4%,連三月加速,遠超公司全年 +15% 指引。"),
    ("漲價的營業槓桿證據?", "2Q26 營收 +26.8%,營業利益 +51.4%——價漲直接灌進獲利。"),
    ("籌碼面最驚人的數字?", "大戶持股五週 53.4%→61.2%;10/8 迴轉率 40.7% 全市場第一;外資全程缺席。"),
    ("這檔估值該怎麼想?", "循環股邏輯:天花板由「漲價還能漲幾季」決定,市場不會給漲價故事成長股倍數。"),
    ("行情熄火的最早訊號?", "大戶持股比例轉降(TDCC 週更)——通常比技術線更早。"),
    ("本報的進出場紀律?", "發動中後段不追爆量;等量縮回測 20 日線二進場;大戶轉降或月營收降速任一出現即離場。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="光頡 3624",
    subtitle="光頡專刊:量先到、理由後到——一顆電阻的漲價循環 · 2026/10/14",
    nav=["頭版", "生意", "財報", "籌碼", "追蹤", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="素材:光頡 2026/10/06 法說簡報+上游洞見〈AI 電源兩段升級〉下篇+本系統迴轉率/集保資料 · "
           "本刊為研究筆記非投資建議 · TW-BACKTEST 財經報")
p = save_issue("3624", "20261014", html)
print("saved:", p)

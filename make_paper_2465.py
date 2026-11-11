# -*- coding: utf-8 -*-
"""財經報:麗臺 2465 專刊 — 連虧三年的代理商,崩盤裡逆勢創新高。"""
from newspaper import shell, save_issue

T = """<b>麗臺 2465</b> <span class="num">136.0</span>|距年高 <span class="up">0%(252日新高)</span>·20日 <span class="up">+62.1%</span>
|Q3 EPS <span class="up">4.03</span>(前三季 6.82·2022〜24 連虧三年)|10月營收 <span class="up">11.45億 +340.6%</span>
|外資20日 <span class="up">+3,403張</span>·大戶% 單週 <span class="up">+11.4pp</span>|但融資 <span class="hl">+1,447張</span>·投信 <span class="hl">0 張</span>·隔日沖⚠多次"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">工商時報/MoneyDJ/自由財經/經濟日報公開報導+本系統全套(Q3 為公司自結,未經核閱)</span></div>
<div class="head1">崩盤裡創新高的 是一家連虧三年的代理商</div>
<div class="deck">大盤 10/6 見頂、全市場在找跌深反彈的這一個月,麗臺收 136 元——正好踩在 252 日新高上,距高 0%,一年區間 49.25〜136。它 2022〜2024 連虧三年,今年第三季單季賺 4.03 元。市場給的新標籤是「AI 轉骨股」,媒體的錨是「明年挑戰賺一個股本」。本刊要拆的是:轉骨是真的嗎?136 元買的是轉骨,還是輝達的肩膀?</div>
<div class="byline">本報整理|Q3 數字為公司自結;EPS 情境之系統中性/樂觀值因月營收基期扭曲而失真,本刊棄用</div>
<div class="cols2"><div>
<p class="dropcap">先講數字,因為這次數字真的硬:季營收 1Q26 的 15.69 億 → 2Q 25.06 億 → <span class="gd">3Q 33.15 億</span>(年增約 70%),前三季累計 73.9 億、較去年同期<b>成長 1.09 倍</b>。更重要的是獲利率同步走:毛利率 10.65% → 12.29% → <span class="gd">16.92%</span>,營益率 5.87% → 6.91% → <span class="gd">11.59%</span>,EPS 1.15 → 1.64 → <span class="gd">4.03</span>。月營收從 7 月起站上全新臺階:10.71 → 11.81 → 10.64 → 11.45 億,是去年月額基準的 3〜4 倍。這不是單月急單,是四個月的平台。</p>
<p>動能來源寫得很白:代理 NVIDIA 的 <span class="hl">RTX PRO 6000 Blackwell 工作站繪圖卡</span>放量,法人並點名同業排擠下的轉單與陸系大型 CSP、在地客戶需求;接棒的是 <span class="hl">DGX Spark 個人 AI 超級電腦</span>——公司規畫年底前小量到貨、明年 Q1 起放量,供貨量上半年可達數千台。今年並成立新事業處,從 GPU 代理往工作站、AI 伺服器與水冷液冷設備延伸。</p>
<p>然後是本刊要潑的冷水:<b>它不生產 GPU。</b>麗臺的生意本質是「拿到貨的權利」——出貨受 NVIDIA 交期與記憶體供應限制,若高階貨源轉向大型 CSP/OEM 直供、或代理政策調整,量與毛利同時被動。毛利率 16.9% 已是代理生意的天花板級表現,不是 IC 設計的 50%。<b>漲的是輝達的肩膀,這是事實;肩膀會不會換人站,也是事實。</b></p>
<p>籌碼面是本篇最大的分歧點:外資 20 日買超 3,403 張、大戶>400 張比例 10/22〜10/30 一週從 37.13% 跳到 48.54%(<span class="hl">+11.4pp,幅度異常,需連續追蹤驗證</span>);但融資同步增 1,447 張、注意力榜近月上榜 35 次且多次掛「⚠隔日沖」、<span class="hl">投信整輪 0 張</span>。翻譯:大錢可能在進,但擠在同一節車廂的投機單也滿了。</p>
</div><div class="sidebar"><h3>三十秒看懂麗臺</h3>
<div class="kv"><div class="k">它是誰</div><div class="v">NVIDIA 在台主要經銷代理商,市值約 128 億;連虧三年後今年轉骨</div></div>
<div class="kv"><div class="k">轉骨引擎</div><div class="v">RTX PRO 6000 工作站卡放量;DGX Spark 年底小量、明年Q1放量</div></div>
<div class="kv"><div class="k">數字臺階</div><div class="v">月營收 7 月起 10〜12 億(去年的 3〜4 倍);Q3 EPS 4.03</div></div>
<div class="kv"><div class="k">生意本質</div><div class="v">代理商:毛利 16.9% 是天花板級,量價由 NVIDIA 分貨決定</div></div>
<div class="kv"><div class="k">籌碼分歧</div><div class="v">外資買+大戶單週+11pp vs 融資增+隔日沖⚠+投信 0</div></div>
<div class="kv"><div class="k">媒體錨</div><div class="v">「明年挑戰賺一個股本」=EPS 10;136 元對應 13.6 倍</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>生意|代理商的轉骨,爬的是哪一段價值鏈</h2></div>
<div class="head1" style="font-size:28px">從「賣卡的」到「賣整機的」 中間隔著輝達的分貨表</div>
<div class="card"><h4>①現在賺的:專業卡代理的「量」</h4>RTX PRO 6000 Blackwell 是工作站級專業卡——企業買去跑 AI 推論/繪圖/模擬。這波的本質是<b>產品週期紅利</b>:新卡上市+同業產能排擠+陸系 CSP 與在地需求同時到,代理商吃到量的瞬間爆發。代理生意的特性:營收爆發快、毛利天花板低(本季 16.9% 已是歷史高檔),而且<b>紅利屬於產品週期,不屬於麗臺</b>。</div>
<div class="card"><h4>②明年賭的:DGX Spark 的「普及」</h4>個人 AI 超級電腦是新品類——如果「一人一台 AI 工作站」成立,代理商就從賣給工作站部門變成賣給每個工程師。公司時間表:年底小量、明年 Q1 放量、上半年數千台。這是 Q4〜明年 Q1 唯一要驗證的新故事。</div>
<div class="card"><h4>③想長的:AI 伺服器+液冷整機</h4>新事業處今年成立,借重大股東在機殼與液冷的資源(報導口徑)。目前素材僅見布局描述、無可驗證營收佔比——本刊按素材留白,只提醒:這是從「代理」往「整機廠」爬的嘗試,成了才有重估值的資格,現在還不能計價。</div>
<p>一句話:<b>今年的錢是輝達新卡給的,明年的錢要 DGX Spark 給,後年的錢才輪到自己的整機夢</b>——三層故事,市場在 136 元已經買了前兩層。</p></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|連虧三年之後的三級跳</h2></div>
<div class="head1" style="font-size:28px">營收×毛利×槓桿三升 但 Q3 還是自結數</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>3Q25</td><td class="num">19.52</td><td class="num hl">4.77%</td><td class="num">1.50%</td><td class="num hl">-0.43</td></tr>
<tr><td>4Q25</td><td class="num">9.28</td><td class="num">10.44%</td><td class="num">2.26%</td><td class="num">0.34</td></tr>
<tr><td>1Q26</td><td class="num">15.69</td><td class="num">10.65%</td><td class="num">5.87%</td><td class="num">1.15</td></tr>
<tr><td>2Q26</td><td class="num">25.06</td><td class="num">12.29%</td><td class="num">6.91%</td><td class="num">1.64</td></tr>
<tr><td><b>3Q26</b></td><td class="num gd">33.15</td><td class="num gd">16.92%</td><td class="num gd">11.59%</td><td class="num gd">4.03</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/07</td><td class="num gd">10.71</td><td class="num gd">+280.9%</td></tr>
<tr><td>2026/08</td><td class="num gd">11.81</td><td class="num gd">+383.3%</td></tr>
<tr><td>2026/09</td><td class="num">10.64</td><td class="num hl">-25.4%*</td></tr>
<tr><td><b>2026/10</b></td><td class="num gd">11.45</td><td class="num gd">+340.6%</td></tr></table>
<p>讀法:①9 月的 -25.4% 是<b>基期假訊號</b>——去年 9 月有單月 14.26 億的一次性大出貨;看月額水位(10〜12 億平台)比看年增率準。②獲利結構是教科書級營運槓桿:營收放大 → 毛利率爬(產品組合轉高階)→ 費用率被稀釋 → EPS 跳。③估值算術:前三季 6.82 元;<b>Q4 守住 Q3 水準 → 全年約 10.8 元、現價 12.6 倍;媒體錨「明年賺一個股本」兌現 → 13.6 倍</b>。對轉骨確認的代理商不算貴,但前提是「守住」二字——Q3 是自結數,11 月中正式財報與 12/10 的 11 月營收(去年同月僅 3.07 億)是兩張最近的考卷。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>籌碼|大錢可能在進 投機單也滿了</h2></div>
<div class="head1" style="font-size:28px">大戶單週+11pp 外資+3,403張 對面是融資與隔日沖</div>
<table><tr><th>指標</th><th>數字</th><th>讀法</th></tr>
<tr><td>大戶>400張</td><td class="num gd">37.13%→48.54%(10/22→10/30)</td><td>單週 +11.4pp 異常巨大——真集中=本檔最強證據;先列「待驗證」,每週五追蹤</td></tr>
<tr><td>外資 20 日</td><td class="num gd">+3,403 張</td><td>站買方,崩盤期間逆勢收貨</td></tr>
<tr><td>投信 30 日</td><td class="num hl">0 張</td><td>整輪行情零機構背書,回檔時沒有投信接手</td></tr>
<tr><td>融資 20 日</td><td class="num hl">+1,447 張(餘額 6,545)</td><td>散戶槓桿在追——家規紅燈項</td></tr>
<tr><td>注意力榜</td><td class="num hl">近月上榜 35 次·多次⚠隔日沖</td><td>短線客群聚;10/22 起四根漲停有三根帶⚠</td></tr>
<tr><td>位置與量</td><td class="num">136 元=年高;11/10 漲停量僅 4,544 張</td><td>11/5 曾爆 43,975 張換手,如今量縮鎖高檔=浮額暫被收走</td></tr></table>
<p>這個組合的歷史劇本:<b>大戶+外資進、投信缺席、融資滿</b>——趨勢行情裡它漲得最兇,但每次回檔都會被隔日沖與融資放大震幅。它不在 55 檔研究名單內(尚未建檔),本刊判定:<b>基本面 B+ 級(轉骨成立、待核閱),籌碼結構 C 級(方向對、成分雜)</b>。</p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">兩張近考卷 一個結構性命門</div>
<div class="card"><h4>追蹤清單</h4>①<b>11 月中 Q3 正式財報</b>:核閱數 vs 自結 EPS 4.03 的落差——連虧三年翻正的公司,獲利品質要驗 ②<b>12/10 前後 11 月營收</b>:守住 10 億月額臺階(去年同月僅 3.07 億),斜率故事的生命線 ③<b>年底 DGX Spark 到貨</b>:公司自己給的時間表,跳票=明年 Q1 放量劇本直接降級 ④每週五大戶%:站穩 47% 一線,驗證那根 +11.4pp 是真集中還是資料噪音 ⑤融資增勢降溫+投信從 0 轉買=投機單換機構單的換手訊號 ⑥NVIDIA 財報與分貨政策:任何「直供大客戶」的措辭都是麗臺的減分項</div>
<div class="card"><h4>反方劇本</h4>①Q4 分貨收緊或記憶體缺料,月營收跌回 7 億以下——全年 EPS 8〜9 元,136 元變 15〜17 倍,高位補跌 ②正式財報與自結落差大(業外/一次性),轉骨敘事折損 ③大盤二次探底:年高股是獲利了結第一目標,融資 6,545 張+隔日沖結構會放大跌速 ④明年下半年起比較基期墊高,年增率驟降觸發估值下修 ⑤DGX Spark 這個品類本身不成立(個人 AI 超算需求是偽命題)——機率不低,列入</div>
<p><b>本報判準</b>:轉骨是真的(三季連升+四個月營收平台),但 136 元已含「Q4 守住+明年賺股本」兩層預期,而它的命門——NVIDIA 分貨——不在自己手上。操作:它在年高進行式,<b>不是低接標的,是突破單規格</b>:倉位=總資金 1%÷停損距,線用 MA20 收盤回破或訊號日低點;融資與隔日沖結構未降溫前,禁止重倉;11 月營收跌破 10 億臺階,整個論點降級重審。</p></div>"""

_QA = [
    ("麗臺的生意本質是什麼?", "NVIDIA 在台主要經銷代理商——不生產 GPU,賣的是「拿到貨的權利」與整機整合;量價由 NVIDIA 分貨決定。"),
    ("這波轉骨的動能來源?", "RTX PRO 6000 Blackwell 工作站卡放量+同業排擠轉單+陸系 CSP 與在地需求;接棒新品是 DGX Spark。"),
    ("最硬的數字證據?", "季營收 15.69→25.06→33.15 億、毛利率 10.65→12.29→16.92%、EPS 1.15→1.64→4.03;月營收 7 月起站上 10〜12 億平台(去年的 3〜4 倍)。"),
    ("9 月年增 -25.4% 怎麼讀?", "基期假訊號——去年 9 月有 14.26 億一次性大出貨;看月額水位比看年增率準。"),
    ("估值的兩個錨?", "Q4 守平→全年約 10.8 元=12.6 倍;媒體錨「明年賺一個股本」(EPS 10)=13.6 倍。前提都是『守住』。"),
    ("籌碼面最強與最弱的證據?", "最強:大戶單週 +11.4pp(待驗證)+外資 20 日 +3,403 張;最弱:投信 0 張+融資 +1,447 張+隔日沖⚠多次。"),
    ("Q3 數字有什麼保留?", "是公司自結、未經會計師核閱;連虧三年剛翻正,獲利品質要等 11 月中正式財報驗證。"),
    ("結構性命門是什麼?", "代理商命門=NVIDIA 交期/記憶體供應/分貨政策;高階貨源轉直供大客戶時,量與毛利同時被動。"),
    ("最近的兩張考卷?", "11 月中 Q3 正式財報 vs 自結 4.03 的落差;12/10 前後 11 月營收守住 10 億臺階。"),
    ("本報操作判準?", "年高進行式=突破單規格:1% 風險倉位、MA20 或訊號日低點停損;融資/隔日沖未降溫禁重倉;11 月營收破 10 億臺階即降級。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="麗臺 2465",
    subtitle="麗臺專刊:連虧三年的代理商,崩盤裡逆勢創新高 · 2026/11/11",
    nav=["頭版", "生意", "財報", "籌碼", "追蹤", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="素材:工商時報/MoneyDJ/自由財經/經濟日報公開報導+本系統全套(Q3 為自結數) · "
           "本刊為研究筆記非投資建議 · TW-BACKTEST 財經報")
p = save_issue("2465", "20261111", html)
print("saved:", p)

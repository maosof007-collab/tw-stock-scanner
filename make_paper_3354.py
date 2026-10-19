# -*- coding: utf-8 -*-
"""財經報:律勝 3354 專刊 — 故事巨大、公司極小(PI材料平台的選擇權定價)。"""
from newspaper import shell, save_issue

T = """<b>律勝 3354</b> <span class="num">45.95</span>|<span class="up">今日創年高</span>(YTD +122%)
|九月營收 <span class="up">+37.5%(連六月雙位數增)</span>|但季營收僅 <span class="num">0.37 億</span>·營益率 <span class="num">-32%(仍虧)</span>
|毛利率 <span class="up">5%→35.4% 連六季爬升</span>|外資缺席(20日買1天)·日均額 0.98 億|10/7 法說(素材最高層)"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">律勝 2026/10/07 法說簡報+富果備忘錄+本系統財報價量</span></div>
<div class="head1">故事巨大 公司極小 一張 PI 材料平台的選擇權</div>
<div class="deck">AI 先進封裝、CPO、折疊屏——律勝的產品型錄踩在 2026 最熱的三個字彙上。但翻開財報:季營收 0.37 億、營益率 -32%、EPS 連八季為負。45.95 元、市值約 31 億,買的不是獲利,是「材料認證全壘打」的選擇權。這期拆:選擇權值多少、憑什麼、什麼時候作廢。</div>
<div class="byline">本報整理|素材:10/7 法說(認證進度)、財報(毛利率軌跡)、本系統價量籌碼</div>
<div class="cols2"><div>
<p class="dropcap">律勝做的是 PI(聚醯亞胺)特用材料,一人分飾四角:①<span class="hl">耐高溫可剝 PSPI</span>——AI/光通訊/射頻封裝的製程保護膜,耐 230℃、剝除不留殘膠,法說說「中國多家板廠認證中、部分已採用」,主攻 HPC 高階軟板;②<span class="hl">液態感光 PSPI+BRINA 介電材料</span>——先進封裝 RDL 增層與 VCSEL 鈍化層,無氟、低介電損失,台灣市場推廣中;③<span class="hl">PTFE 超低損耗材料</span>——打 800G/1.6T 與 CPO;④<span class="hl">Mpior 透明 PI</span>——折疊/捲曲屏保護層,蘇州產線「逐步放量」,就近服務中國面板廠。</p>
<p>型錄完美。但財務是另一個宇宙:季營收 0.23~0.37 億(對,單位是億,很多上市櫃公司一天的營收比它一季多),營業費用吃掉營收的六成以上,營益率 -32%——<span class="hl">這是一家還在用資本養研發的材料新創</span>,掛著上櫃代號。</p>
<p>那為什麼值得寫?因為有一條曲線在誠實地動:<span class="hl">毛利率 5.5%(2Q25)→11.6→19.0→29.2→35.4%(2Q26),連六季爬升</span>。材料公司的毛利率就是「認證通過+量產良率」的溫度計——這條線騙不了人,它說認證確實在從實驗室走向產線。月營收 4 月起連六個月雙位數年增(+27~+72%),同方向佐證。</p>
<p>股價已經給了答案的一半:YTD +122%、10/19 創年高 45.95。年化營收約 1.3 億對市值 31 億=<span class="hl">股價營收比(PS)約 24 倍</span>——台股材料股給這種倍數的,全是「平台夢」定價。外資 20 日只買 1 天:這是純內資題材盤,沒有機構研究覆蓋,也沒有機構護底。</p>
</div><div class="sidebar"><h3>三十秒看懂律勝</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">PI 特用材料四線:可剝 PSPI/感光 PSPI+BRINA/PTFE 低損耗/透明 PI</div></div>
<div class="kv"><div class="k">踩的題材</div><div class="v">AI 先進封裝、CPO 光通訊、折疊屏——字彙表全滿分</div></div>
<div class="kv"><div class="k">殘酷現實</div><div class="v">季營收 0.37 億、營益率 -32%、EPS 連八季負</div></div>
<div class="kv"><div class="k">真實進展</div><div class="v">毛利率連六季 5.5%→35.4%;月營收連六月雙位數增</div></div>
<div class="kv"><div class="k">定價</div><div class="v">市值約 31 億=PS 24 倍,買的是選擇權不是獲利</div></div>
<div class="kv"><div class="k">籌碼</div><div class="v">外資缺席、日均額 0.98 億、今天創年高(發動中)</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>生意|四條產品線的誠實分級</h2></div>
<div class="head1" style="font-size:28px">法說的語言學:「部分採用」和「接觸測試」差三年</div>
<div class="card"><h4>①可剝 PSPI:最接近錢的一條(法說:「部分已採用」)</h4>AI 封裝製程保護是耗材邏輯——客戶產線跑多少,它用多少。法說明說中國多家板廠「認證中、部分已採用」,主攻 HPC 高階 FPC。毛利率連六季爬,最合理的解釋就是這條線在放量。<b>這是四條線裡唯一已經在貢獻的。</b></div>
<div class="card"><h4>②BRINA/感光 PSPI:字彙最性感、進度最模糊</h4>RDL 增層介電、VCSEL 鈍化——直通先進封裝與光通訊核心。但法說語言是「以推廣台灣市場為主」,無客戶、無認證時程。<b>半導體材料認證以年計(信越、富士軟片在這裡坐了二十年),這條線是 2028 年的故事,不是 2027 的。</b></div>
<div class="card"><h4>③PTFE 低損耗:蹭對了 CCL 大行情,但競技場殘酷</h4>800G/1.6T 與 CPO 用低損耗材料是真需求(高盛 mSAP 報告同一條邏輯鏈),但這裡的對手是台光電、羅傑斯、松下——<b>一家季營收 0.37 億的公司在巨人賽道上,只能做利基縫隙。</b></div>
<div class="card"><h4>④透明 PI:蘇州產線「逐步放量」,打地緣牌</h4>折疊屏保護層,對手是韓國 Kolon/SKC。律勝的牌是「中國面板廠就近採購」——邏輯成立,但也意味著客戶集中中國+面板業的砍價文化。法說語言「接觸測試認證」=還沒出貨。</div>
<p>一句話總結:<b>①在賺小錢、④在燒錢等訂單、②③還在簡報裡。</b>45.95 元把四條線全部當真——而法說的措辭誠實地告訴你,只有一條半是真的。</p></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|一條會說話的毛利率曲線</h2></div>
<div class="head1" style="font-size:28px">毛利率連六季爬 但損益兩平還在山的另一邊</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">0.23</td><td class="num">5.6%</td><td class="num hl">-103.6%</td><td class="num">-0.53</td></tr>
<tr><td>3Q25</td><td class="num">0.25</td><td class="num">11.6%</td><td class="num">-93.1%</td><td class="num">-0.03</td></tr>
<tr><td>4Q25</td><td class="num">0.24</td><td class="num">19.0%</td><td class="num">-79.9%</td><td class="num">-0.13</td></tr>
<tr><td>1Q26</td><td class="num">0.29</td><td class="num">29.2%</td><td class="num">-56.6%</td><td class="num">-0.17</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">0.37</td><td class="num gd">35.4%</td><td class="num hl">-32.1%</td><td class="num">-0.12</td></tr></table>
<table><tr><th>月營收</th><th>百萬</th><th>YoY</th></tr>
<tr><td>2026/04</td><td class="num">13.8</td><td class="num gd">+52.0%</td></tr>
<tr><td>2026/05</td><td class="num">13.0</td><td class="num gd">+72.6%</td></tr>
<tr><td>2026/07</td><td class="num">12.3</td><td class="num">+27.5%</td></tr>
<tr><td>2026/08</td><td class="num">9.1</td><td class="num">+31.9%</td></tr>
<tr><td><b>2026/09</b></td><td class="num">12.0</td><td class="num">+37.5%</td></tr></table>
<p>兩個讀法:①<b>毛利率是這家公司唯一該盯的數字</b>——材料公司從認證走向量產,毛利率先動、營收後動、獲利最後動。5.5→35.4% 的軌跡是真進展,不是會計魔術(營收同步升,排除單一訂單扭曲)。②<b>但損益兩平的門檻算給你看</b>:營業費用約 0.25 億/季(近乎固定),毛利率就算到 40%,營收要做到 <b>0.63 億/季(現在的 1.7 倍)</b>才打平;要撐起 31 億市值對應的合理獲利(假設給 30 倍 PE=賺 1 億/年),營收要到 <b>1.2 億/季(現在的 3.2 倍)</b>。月營收連六月雙位數增是對的方向,但從 0.37 到 1.2,中間隔著「部分採用」到「主力供應商」的整段認證長征。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>籌碼與股價|創年高的發動中題材盤</h2></div>
<div class="head1" style="font-size:28px">法說 10/7 開完 股價 10/19 創高 這不是巧合</div>
<table><tr><th>項目</th><th>數字</th><th>讀法</th></tr>
<tr><td>現價</td><td class="num gd">45.95(10/19 創年高)</td><td>YTD +122%,60 日線上</td></tr>
<tr><td>外資 20 日</td><td class="num hl">買超 1 天/淨賣 2 張</td><td>機構完全缺席,零研究覆蓋</td></tr>
<tr><td>日均額</td><td class="num">0.98 億</td><td>小票,進出都要限價分批</td></tr>
<tr><td>法說時點</td><td class="num">10/7</td><td>法說→盤面發動,典型「素材引爆題材」節奏</td></tr></table>
<p>這個型態在我們的框架裡叫<b>「發動中的本夢比小票」</b>:純內資定價、創新高、量能溫和放大。它不在還沒發動名單(已經動了),也還沒進迴轉率警戒(量還沒爆)。按家規:<b>創高日不是進場日</b>——若信這個故事,正確動作是等第一波衝完的量縮回測(20 日線不破),而不是在年高追;若不信,看戲就好。倉位規格無懸念:題材股 ≤2.5% 閒錢,1.5ATR 停損。</p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">選擇權的時間價值 盯四個續約條件</div>
<div class="card"><h4>追蹤清單(選擇權「續約」條件)</h4>①<b>3Q26 毛利率(11/14 前)能否站上 38%+</b>——曲線斷了故事就斷 ②單月營收何時突破 0.15 億(放量第二階證據) ③可剝 PSPI 從「部分採用」升級為具名客戶/明確佔比(下次法說的語言變化) ④透明 PI 蘇州線首批量產出貨公告 ⑤營業費用是否開始放大(擴產燒錢 vs 營收賽跑)</div>
<div class="card"><h4>反方劇本(選擇權「作廢」條件)</h4>①毛利率任一季回落 5pp 以上=認證放量敘事存疑 ②半導體級材料(BRINA)認證卡關——信越/富士軟片的地盤不是行銷文案打得進的 ③增資:燒錢公司股價創高後最常見的劇本就是伸手要錢,稀釋接踵而至 ④題材退潮時,PS 24 倍的小票沒有任何估值地板 ⑤日均額 0.98 億,跌時流動性瞬間蒸發</div>
<p><b>本報判準</b>:律勝是「正確字彙表+真實毛利率曲線+過早的定價」三者的組合。它不是假貨——毛利率連六季爬是裝不出來的;但 45.95 元已經把「四條線全成」當基本情境,而法說措辭誠實地說只有一條半在走。操作上當<b>選擇權</b>管理:小倉位(≤2.5%)、用毛利率當續約判準(季報是它的到期日)、創高不追等回測。這種票的最大風險從來不是公司做不出來,是<b>你在故事最熱的那天付了最貴的權利金</b>。</p></div>"""

_QA = [
    ("律勝的四條產品線?", "可剝 PSPI(AI封裝製程保護)、感光 PSPI+BRINA(RDL介電)、PTFE 低損耗(800G/CPO)、透明 PI(折疊屏)。"),
    ("四條線的誠實分級?", "可剝 PSPI「部分已採用」在賺小錢;透明 PI 蘇州線燒錢等訂單;BRINA/PTFE 還在簡報裡。"),
    ("這家公司唯一該盯的數字?", "毛利率:5.5%→35.4% 連六季爬——材料公司認證走向量產,毛利率先動。"),
    ("損益兩平要什麼條件?", "營業費用約 0.25 億/季固定,毛利率 40% 下營收要 0.63 億/季=現在的 1.7 倍。"),
    ("市值 31 億隱含什麼?", "PS 約 24 倍;要合理化需年賺 1 億=營收做到現在的 3.2 倍。"),
    ("法說語言學怎麼讀?", "「部分已採用」>「推廣中」>「接觸測試」——三種措辭差的是年,不是月。"),
    ("籌碼結構?", "外資 20 日只買 1 天、日均額 0.98 億——純內資題材盤,零機構覆蓋也零護底。"),
    ("為什麼創高日不是進場日?", "家規:發動中不追;信故事就等量縮回測 20 日線,不信就看戲。"),
    ("選擇權作廢的訊號?", "毛利率單季回落 5pp+、或宣布增資稀釋、或下次法說語言沒有升級。"),
    ("本報一句話定位?", "正確字彙表+真實毛利率曲線+過早的定價——當選擇權管理,權利金別在最熱的那天付。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="律勝 3354",
    subtitle="律勝專刊:故事巨大、公司極小——PI 材料平台的選擇權定價 · 2026/10/19",
    nav=["頭版", "生意", "財報", "籌碼", "追蹤", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="素材:律勝 2026/10/07 法說簡報+富果備忘錄+本系統財報價量 · "
           "本刊為研究筆記非投資建議 · TW-BACKTEST 財經報")
p = save_issue("3354", "20261019", html)
print("saved:", p)

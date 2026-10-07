# -*- coding: utf-8 -*-
"""財經報:AI 電源鏈研究報告(七步思考法練習 No.1,使用者與本報共同完成)。
素材:瀚荃8103專刊(paul_invest00)、台達/光寶法說報導口徑、GB300/VR200 瓦數表、
中興電/大亞研究(櫃外段)。方法論:Aoi CCL 報告之七步模板(文章庫 TEMPLATE)。"""
from newspaper import shell, save_issue

T = """<b>AI 電源鏈</b>|機櫃功耗 <span class="num">140→190-230kW</span>
|2027 機櫃總電力 <span class="num">7.7→15GW</span>(全轉Rubin情境)
|光寶 AI 營收佔比 <span class="up">>30%</span>|台達 <span class="num">約25%</span>
|瀚荃 AI Power 佔比 <span class="up">24%(2023僅5%)</span>"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>結論先行</h2>
<span class="src">七步思考法 Step 0+2</span></div>
<div class="head1">把電網的粗電 變成晶片的細電 每降一次壓收一次過路費</div>
<div class="deck">AI 電源鏈同時連接「總瓦數、HVDC 規格升級、熱預算、ASP、毛利率」五個投資變數。市場容易把焦點放在台達、光寶這些整機廠;但當 AI 硬體從出貨量成長進入「每瓦重新設計」的階段,電源內部的零組件與材料——連接器、Bus Bar、DrMOS、BBU——會是更乾淨的槓桿環節。</div>
<div class="byline">本報與使用者共同練習作品(七步思考法 No.1)|方法論源自 Aoi CCL 報告</div>
<div class="cols2"><div>
<p class="dropcap">定位句先寫:<b>我會把 AI 電源鏈定義為「把電網的粗電轉換成晶片的細電」的核心中介</b>——電網給的是 480V 高壓交流、會斷;晶片要的是 0.8V 超大電流、極穩、不能斷。中間每降一次電壓就是一站,每站收一次過路費;瓦數越大、電壓層級越多、穩定度要求越高,過路費越貴。</p>
<p>五個變數逐一掛回這句話:<b>總瓦數</b>=過路費的量(GB300 每櫃 140kW → VR200 190-230kW;2027 若全轉 Rubin,機櫃總電力約 7.7GW→15GW);<b>HVDC 規格升級</b>=重劃收費站(±400V/800V 直流進櫃,PDU/PSU 兩站要重組);<b>熱預算</b>=轉換損耗的物理稅(瓦數↑發熱必然↑,散熱價值量單向上升);<b>ASP</b>=單站費率(規格越高費率越貴);<b>毛利率</b>=費率減成本(瀚荃毛利率 31%→39% 與 AI 佔比同步,是已驗證的樣本)。</p>
<p>註:單顆 PSU 功率密度(5.5→18.3kW、每櫃顆數 48→18)是驅動機制不是投資變數——它對顆數型供應商是減項、對含量型是加項,方向不唯一,所以放內文不進結論。這個「變數要單向必然」的篩選,是本篇與一般題材文的差別。</p>
</div><div class="sidebar"><h3>五個投資變數</h3>
<div class="kv"><div class="k">總瓦數</div><div class="v">140→230kW/櫃;2027 總量看倍增</div></div>
<div class="kv"><div class="k">HVDC 升級</div><div class="v">±400V/800V 直流進櫃=收費站重劃</div></div>
<div class="kv"><div class="k">熱預算</div><div class="v">瓦數→發熱是物理必然,散熱單向受惠</div></div>
<div class="kv"><div class="k">ASP</div><div class="v">安規+客製=規格越高費率越貴</div></div>
<div class="kv"><div class="k">毛利率</div><div class="v">瀚荃 31%→39% 已示範「組合升級」</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>結構拆解|電從牆到晶片的五站</h2></div>
<div class="head1" style="font-size:28px">每一站管一段電壓 每一站都有台廠</div>
<table><tr><th>站</th><th>做什麼</th><th>電壓</th><th>台廠</th></tr>
<tr><td>[0] 櫃外</td><td>變壓器/GIS/UPS/機房配電</td><td>電網→480V AC</td><td>中興電 1513、台達——往上游接「強韌電網」研究線(中興電/大亞)</td></tr>
<tr><td>[1] PDU</td><td>機櫃配電</td><td>480V 分配</td><td>台達 2308、光寶 2301</td></tr>
<tr><td>[2] PSU</td><td>AC→DC 轉換(單顆 5.5→18.3kW)</td><td>480V AC→50V DC</td><td>台達、光寶、康舒 6282</td></tr>
<tr><td>[3] Busbar/連接器</td><td>大電流搬運</td><td>50V 高電流</td><td>瀚荃 8103(HVDC Bus Bar 連接器)、貿聯-KY 3665、乙盛-KY 5243</td></tr>
<tr><td>[4] VRM/DrMOS</td><td>最後一哩降壓</td><td>50V→0.8V</td><td>茂達 6138、力智 6719、杰力 5299+電感(奇力新)</td></tr>
<tr><td>[旁] BBU</td><td>備援電池(不能斷)</td><td>—</td><td>AES-KY 6781、順達 3211、加百裕 3323、新盛力 4931</td></tr></table>
<p><b>800V HVDC 的真正意思</b>:直流直接進櫃,[1][2] 兩站架構重組——有站會縮小、有站會變大(Bus Bar 與固態斷路器價值上升)。這是「規格升級」變數的物理根據:收費站重劃時,舊站的既得者與新站的卡位者會換手。<b>功率密度的重分配機制</b>也在這裡:單顆 PSU 18.3kW 體積不能等比放大,只能往上堆電路板——PSU 顆數 -63%,但單顆內的板對板連接器更多、規格更高,「每瓦零件含量」不降反升。</p></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>供給為何難複製</h2></div>
<div class="head1" style="font-size:28px">三道門檻 新進者用錢買不到時間</div>
<div class="card"><h4>①安規與熱管理的重新驗證(替換成本)</h4>電源零件不是末端可隨意替換——換一顆連接器,整台 PSU 的安規與熱管理要重新驗證,時間與風險由客戶承擔。供應商因此從賣零件升級為協同設計夥伴,黏著度是設計進去的。</div>
<div class="card"><h4>②量產穩定性(良率是十年功)</h4>18.3kW 塞進 3U、效率要鈦金級(97.5%+),熱與電的裕度極窄;新品初期良率爬坡連在位者都要跌一跤(瀚荃 2Q26 毛利率小滑即為例),新進者更無捷徑。</div>
<div class="card"><h4>③高功率密度的設計能力積累(電源界的「配方」)</h4>拓撲架構、磁性元件、GaN/SiC 功率元件 know-how——台達、光寶各養三十年,對應 CCL 世界「配方需要長時間累積」那一條。</div>
<p>註(方法論):「交期與就近生產」不在此列——那是<b>優勢</b>(進來的人誰贏)不是<b>門檻</b>(為什麼進不來),放在個股比較層(瀚荃 vs 安費諾/泰科)。檢驗法:套進「新進者需要幾年才能跨過」,套不進去的就不是門檻。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>相鄰環節|四個動詞防止一條鏈全買</h2></div>
<div class="head1" style="font-size:28px">整機看瓦數 零組件看含量 IC 看世代 BBU 看滲透率</div>
<table><tr><th>環節</th><th>一個動詞</th><th>為什麼</th></tr>
<tr><td>整機電源廠(台達/光寶/康舒)</td><td class="hl">看瓦數</td><td>營收≈出貨瓦數×每瓦單價;光寶 AI 佔比>30%、台達約25%,是最即時的需求溫度計</td></tr>
<tr><td>零組件(瀚荃/貿聯/乙盛)</td><td class="hl">看含量</td><td>每瓦零件含量不降→營收跟總瓦數走,不跟 PSU 顆數走(P×Q 精髓)</td></tr>
<tr><td>最後一哩 IC(茂達/力智/杰力)</td><td class="hl">看平台世代</td><td>GPU 每換代供電相數增加、DrMOS 顆數跳增、design-win 洗牌——跟世代走不跟瓦數走</td></tr>
<tr><td>BBU(AES-KY/順達/加百裕)</td><td class="hl">看滲透率</td><td>從選配變標配:滲透率×每櫃搭載量,是「從無到有」的品類成長</td></tr></table>
<p>風險也要分環節:整機廠怕客戶集中殺價;零組件怕舊料號壓價(P 的提升全靠高階佔比);IC 怕世代空窗與陸廠低價;BBU 怕規格變更(電芯/架構)。<b>同一條鏈,四種買法、四種死法——這就是 Step 4 存在的理由。</b></p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>個股觀察點+判斷框架</h2></div>
<div class="head1" style="font-size:28px">只給觀察指標 不給目標價</div>
<table><tr><th>位置</th><th>代表</th><th>看什麼(可驗證)</th><th>主要風險</th></tr>
<tr><td>整機</td><td>台達 2308/光寶 2301/康舒 6282</td><td>每季 AI 電源營收成長率(最即時的鏈上 Q)、800V 時程表態</td><td>估值已反映 AI、匯率</td></tr>
<tr><td class="hl">零組件</td><td class="hl">瀚荃 8103</td><td>AI Power 佔比(24%→?)與毛利率同步;<b>瀚荃成長率÷客戶 AI 電源成長率<1=份額被稀釋</b>;泰國廠出貨</td><td>客戶集中、舊料號壓價</td></tr>
<tr><td>零組件</td><td>貿聯-KY 3665/乙盛-KY 5243</td><td>伺服器電源線束/busbar 營收佔比、北美大客戶拉貨</td><td>單一大客戶波動</td></tr>
<tr><td>IC</td><td>茂達 6138/力智 6719/杰力 5299</td><td>新平台 design-win 公告、伺服器佔比、毛利率站穩</td><td>世代空窗、陸廠競價</td></tr>
<tr><td>BBU</td><td>AES-KY 6781/順達 3211</td><td>BBU 營收佔比與新案導入(標配化證據)</td><td>規格變更、電芯價格</td></tr>
<tr><td>材料(跨界)</td><td>騰輝 6672</td><td>散熱膜/金屬基板在 AI 電源的放量(法說七線之一)</td><td>仍以軍工為主引擎</td></tr></table>
<div class="card"><h4>判斷框架(六步,照 CCL 報告句式)</h4>①看雲端 capex 與機櫃瓦數是否持續上修 ②看高階(HVDC/高密度)出貨佔比是否提高——若成長全來自舊規格,槓桿弱 ③看毛利率是否跟著組合改善——AI 題材在而毛利率不動=報價能力不足 ④看認證與新產能節奏——量產與良率比宣布擴產重要 ⑤看上游(功率元件/銅/電芯)是否缺料,能轉嫁是利多、不能轉嫁壓毛利 ⑥看 800V 時程——重劃收費站之日,就是重新選股之時。</p></div>
<p><b>資料來源層級</b>:公司法說與財報(瀚荃/台達/光寶)>產業整理(paul_invest00 Threads,GB300/VR200 瓦數表)>本報推論(五站模型、四動詞)。全文無目標價。</p></div>"""

_QA = [
    ("這條鏈的定位句是什麼?", "把電網的粗電轉換成晶片的細電——每降一次壓收一次過路費。"),
    ("五個投資變數?", "總瓦數、HVDC 規格升級、熱預算、ASP、毛利率。"),
    ("功率密度為什麼不是投資變數?", "它對顆數型供應商是減項、含量型是加項,方向不唯一——它是機制,放內文。"),
    ("電從牆到晶片的五站?", "櫃外(變壓/UPS)→PDU→PSU→Busbar→VRM,旁邊掛 BBU。"),
    ("800V HVDC 的投資意義?", "直流進櫃=PDU/PSU 收費站重劃——舊站既得者與新站卡位者換手。"),
    ("三道供給門檻?", "安規熱管理重驗證(替換成本)、量產穩定性、高密度設計能力積累。"),
    ("「交期快」為什麼不算門檻?", "新進者養庫存就能交期快——用錢買得到的是優勢,買不到時間的才是門檻。"),
    ("四個環節各看什麼?", "整機看瓦數、零組件看含量、IC 看平台世代、BBU 看滲透率。"),
    ("「份額稀釋偵測器」怎麼算?", "瀚荃 AI Power 成長率 ÷ 客戶 AI 電源成長率,持續<1 即被稀釋。"),
    ("本篇和一般題材文的差別?", "變數要單向必然、門檻要用錢買不到、每環節一個動詞、全文零目標價。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="AI 電源鏈",
    subtitle="AI 電源鏈結構與台股投資機會研究報告|七步思考法練習 No.1(共同創作)· 2026/10/07",
    nav=["結論", "結構五站", "護城河", "環節動詞", "個股與框架", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="方法論:Aoi 七步模板(文章庫)· 素材:公司法說/財報+paul_invest00 整理+本報推論 · "
           "全文無目標價、非投資建議 · TW-BACKTEST 財經報")
p = save_issue("AIPOWER", "20261007", html)
print("saved:", p)

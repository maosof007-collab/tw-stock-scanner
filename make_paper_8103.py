# -*- coding: utf-8 -*-
"""財經報:瀚荃 8103 專刊 — AI Power 連接器轉型(素材:使用者提供之 paul_invest00
Threads 六篇拆解 + 公開財報 + 本系統價量籌碼)。P×Q 瓦數邏輯為該作者核心洞察,已註明出處。"""
from newspaper import shell, save_issue

T = """<b>瀚荃 8103</b> <span class="num">121.0</span>|距年高 <span class="num">-8.3%</span>(年高 132/年低 58.4)
|1H26 EPS <span class="up">2.75(+137%)</span>|毛利率 <span class="num">37.0%</span>
|AI Power 佔比 <span class="up">24%(2023 僅 5%)</span>|8月營收 <span class="up">+51.6%</span>"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:paul_invest00 Threads 拆解(使用者提供)+公開財報</span></div>
<div class="head1">連接器老廠的 AI 電力轉型 佔比三年翻五倍</div>
<div class="deck">AI Power 佔營收從 2023 年 5% 一路拉到 2026 上半年 24%,前七月 AI Power 營收年增 83%,上半年 EPS +137%——而市場給它的本益比,還停在線材廠的水位。這個落差,就是瀚荃這一期的全部。</div>
<div class="byline">本報整理|原始拆解:paul_invest00(Threads)·本報補財務與籌碼驗證</div>
<div class="cols2"><div>
<p class="dropcap">瀚荃 1990 年成立,連接器佔營收七成以上(電源/板對板/線對板/細間距/IO)、線纜組件近三成(線束/FFC/LVDS/Type-C)。過去的標籤是筆電與消費電子的零件廠——直到 AI 伺服器把「電力」變成最貴的瓶頸。</p>
<p>它的 AI Power 產品線:PSU 內部的板對板/線對板連接器、BBU/CBU/PDU、以及 <span class="hl">HVDC 匯流排(Bus Bar)連接器與線材</span>。佔比階梯清楚得像教科書:2023 年 5% → 2024 年 8% → 2025 年 18% → <span class="hl">2026 上半年 24%</span>;公司自估今明兩年 AI Power 還能成長 50~100%。</p>
<p>財報已經先給了證據:毛利率從 4Q24 的 31.2% 爬到 4Q25 的 39.1%(六季階梯),1H26 EPS 2.75 年增 137%,8 月營收 4.03 億年增 51.6% 續創高軌道。客戶端是台達電、光寶科兩大電源廠量產出貨,上半年客戶持續上修訂單。</p>
<p>而估值:121 元對近 4 季 EPS 5.51 約 22 倍、年化約 19 倍——原作者點出的疑問也是本報的疑問:<b>AI 成長性與佔比在連接器/線束族群排前幾名,本益比卻偏低</b>。市場的顧慮(非 AI 業務仍佔 76%、毛利率尚未跟上 AI 佔比)對不對,Q3 財報就有答案。</p>
</div><div class="sidebar"><h3>三十秒看懂瀚荃</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">連接器 >70%+線纜組件 <30%:網通/筆電/車用/消費/光電</div></div>
<div class="kv"><div class="k">AI 產品</div><div class="v">PSU 內連接器、BBU/CBU/PDU、HVDC Bus Bar 連接器與線材</div></div>
<div class="kv"><div class="k">佔比階梯</div><div class="v">5%(23)→8%(24)→18%(25)→24%(1H26);前七月 AI 營收 +83%</div></div>
<div class="kv"><div class="k">客戶</div><div class="v">台達電、光寶科量產出貨,訂單持續上修</div></div>
<div class="kv"><div class="k">獲利</div><div class="v">1H26 EPS 2.75(+137%),毛利率 37%</div></div>
<div class="kv"><div class="k">估值疑點</div><div class="v">年化約 19 倍——AI 含量族群前段班,線材廠價格</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>護城河|三道,一道比一道實際</h2></div>
<div class="head1" style="font-size:28px">從賣零件 到陪客戶設計</div>
<div class="card"><h4>①替換成本高</h4>電源連接器不是末端可隨意替換的零件——換掉它,整台 PSU 的安規與熱管理要重新驗證,時間和風險都由客戶承擔。瀚荃因此從「零件供應商」升級為「協同客戶做產品設計與開發的合作夥伴」——黏著度是設計進去的,不是價格買來的。</div>
<div class="card"><h4>②穩定量產(含一個誠實的檢核點)</h4>做出產品不等於做出良率。2Q26 毛利率小幅下滑(37.97%→37.00%),原因包括新產品初期良率與產品組合調整——這一方面說明放量有門檻,另一方面也給了檢核點:<b>看 3Q 毛利率是否回升</b>。已在台達電、光寶科兩大電源廠量產出貨是過了這關的證據。</div>
<div class="card"><h4>③交期與就近供貨</h4>論產品線齊全,安費諾(Amphenol)、泰科(TE)一定更完整——瀚荃真正贏的是<b>交期</b>,以及配合 China+N 在泰國、馬來西亞就近生產。供給吃緊時(稼動率已破 100%),交期就是訂單。</div></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>P×Q|看瓦數,不是 PSU 顆數</h2>
<span class="src">原作者核心洞察</span></div>
<div class="head1" style="font-size:28px">PSU 顆數砍六成 瀚荃為什麼反而受惠</div>
<p>直覺的利空:單顆 PSU 瓦數越高,每櫃需要的顆數越少——GB300 每櫃 48 顆,VR200 只剩 18 顆(-63%)。那連接器廠不是要被砍單?</p>
<table><tr><th></th><th>GB300 NVL72</th><th>VR200 NVL72</th><th>變化</th></tr>
<tr><td>單顆 PSU 瓦數</td><td class="num">5.5kW</td><td class="num">約 18.3kW</td><td class="num gd">約 3.3 倍</td></tr>
<tr><td>電源架配置</td><td>8 個 1U/每個 33kW</td><td>3 個 3U/每個 110kW</td><td>—</td></tr>
<tr><td>每櫃 PSU 顆數</td><td class="num">48 顆</td><td class="num">18 顆</td><td class="num hl">-63%</td></tr>
<tr><td>機櫃功耗</td><td class="num">約 140kW</td><td class="num">190~230kW</td><td class="num gd">+36~64%</td></tr></table>
<p>解答:單顆 PSU 從 5.5kW 跳到 18.3kW,但體積不能等比例放大——只能往上<b>堆疊更多電路板</b>,單顆 PSU 裡的板對板連接器反而變多、規格更高。所以<b>每瓦的連接器含量沒有下降,瀚荃的營收跟著「總瓦數」走,不跟顆數走</b>。</p>
<p>而總瓦數的 2027 劇本:TrendForce 預估 NVL72 出貨成長五成;若 2027 出貨全數轉 Rubin,機櫃總電力約從 7.7GW 增到 15GW(GB300/VR200 共存下實際略低)。客戶端印證:光寶科 2026 年 AI 營收占比超過三成、台達電約兩成五,±400V/800V HVDC 放量後還會再提高——<b>市場大方向是翻倍</b>,瀚荃的 Bus Bar 連接器正卡在 HVDC 這條新路上。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>財報|轉型的六季指紋</h2></div>
<div class="head1" style="font-size:28px">毛利率 31%→39% 的階梯 就是 AI 佔比的階梯</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>4Q24</td><td class="num">8.29</td><td class="num">31.20%</td><td class="num">6.89%</td><td class="num">0.93</td></tr>
<tr><td>2Q25</td><td class="num">8.51</td><td class="num">37.48%</td><td class="num">16.47%</td><td class="num">0.43</td></tr>
<tr><td>3Q25</td><td class="num">8.74</td><td class="num">38.35%</td><td class="num">15.98%</td><td class="num">1.31</td></tr>
<tr><td>4Q25</td><td class="num gd">8.92</td><td class="num gd">39.14%</td><td class="num">11.55%</td><td class="num">1.45</td></tr>
<tr><td>1Q26</td><td class="num">9.10</td><td class="num">37.97%</td><td class="num">14.24%</td><td class="num">1.17</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">10.97</td><td class="num">37.00%</td><td class="num gd">16.21%</td><td class="num gd">1.58</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/06</td><td class="num">3.76</td><td class="num gd">+45.0%</td></tr>
<tr><td>2026/07</td><td class="num">3.96</td><td class="num">+34.3%</td></tr>
<tr><td>2026/08</td><td class="num gd">4.03</td><td class="num gd">+51.6%</td></tr></table>
<p>三個註腳:①毛利率六季 +7.9pp,和 AI Power 佔比 8%→24% 同步——組合升級是真的;②2Q26 毛利率小滑 1pp=新品良率爬坡,3Q 回升與否是護城河②的考題;③營益率與淨利率的落差(2Q26 16.2% vs 11.2%)主要是業外匯損波動——出口型線材廠的常態,看本業要盯營益率。121 元=近 4 季 22 倍、年化 19 倍,對照「AI Power 今明年 +50~100%」的公司指引,這是收斂中的估值差。</p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>產能、追蹤指標與風險</h2></div>
<div class="head1" style="font-size:28px">稼動率破百 瓶頸在人不在廠</div>
<div class="card"><h4>產能布局</h4>2025/12 法說:稼動率超過 100%,瓶頸在人力不在廠房。擴產 2~3 成:泰國廠最快 2026 年底出貨、東莞兩廠 2027 年初整併完成。關鍵巧思:AI Power 只佔營收 24%,公司可以把筆電/消費電子產線挪給 AI Power——<b>AI 的量不會被總產能卡死</b>,還有 +2~3 成的內部騰挪空間。</div>
<div class="card"><h4>追蹤指標(原作者清單,本報照單全收)</h4>①NVL72 機櫃出貨與 VR200 量產時程 ②±400V/800V HVDC 時程 ③光寶、台達每季 AI 電源營收成長率(最即時的 Q)④<b>瀚荃 AI Power 成長率 ÷ 客戶 AI 電源成長率——持續低於 1 = 份額被稀釋</b> ⑤CSP 資本支出 ⑥瀚荃月營收與毛利率、AI 佔比是否同步 ⑦東莞 1 月整併、泰國出貨速度 ⑧銅價。</div>
<div class="card"><h4>反方劇本</h4>①客戶集中(台達+光寶),舊料號被壓價——P 的提升全靠 AI 佔比,佔比爬慢了毛利率就卡住 ②對手安費諾/泰科產品線更全,搶單戰隨時升級 ③非 AI 業務佔 76%,消費電子一冷就稀釋成長 ④匯損噪音大 ⑤本系統籌碼註記:外資近 20 日賣超 3,020 張、60 日已漲 30%、距年高 -8.3%——基本面強但<b>外資在高檔調節</b>,和牧德同款背離。</div>
<p><b>本報判準</b>:這是「估值差收斂」型標的——故事不用賭,佔比階梯和毛利率階梯都已在財報上;要賭的只有速度。進場按家規:距年高 -8.3% 不是追價位,等回測不破或 Q3 毛利率回升確認;10/10 九月營收(能否守 +35%+)是最近的對帳日。</p></div>"""

_QA = [
    ("瀚荃的 AI Power 佔比階梯?", "2023 年 5% → 2024 年 8% → 2025 年 18% → 2026 上半年 24%。"),
    ("AI Power 產品有哪些?", "PSU 內部板對板/線對板連接器、BBU/CBU/PDU、HVDC Bus Bar 連接器與線材。"),
    ("為什麼 PSU 顆數砍 63% 反而不是利空?", "單顆瓦數 5.5→18.3kW,體積不能等比放大只能堆更多電路板——單顆連接器變多、規格更高,營收跟總瓦數走。"),
    ("GB300 與 VR200 每櫃 PSU 顆數?", "48 顆 vs 18 顆;機櫃功耗反而從 140kW 升到 190~230kW。"),
    ("瀚荃對上安費諾/泰科,贏在哪?", "交期+China+N 就近生產(泰國/馬來西亞);產品線齊全度反而是對手強。"),
    ("護城河最誠實的檢核點是什麼?", "2Q 毛利率因新品良率小滑,看 3Q 是否回升。"),
    ("稼動率與產能瓶頸?", "2025/12 法說稼動率破 100%,瓶頸在人力;另可把筆電產線挪給 AI(+2~3 成空間)。"),
    ("「份額稀釋」怎麼偵測?", "瀚荃 AI Power 成長率 ÷ 客戶(台達/光寶)AI 電源成長率,持續低於 1 就是被稀釋。"),
    ("1H26 EPS 與年增率?", "2.75 元,+137%;毛利率六季從 31.2% 爬到 39.1%。"),
    ("本報的籌碼警示是什麼?", "外資近 20 日賣超 3,020 張、60 日已漲 30%——基本面強但外資高檔調節,等回測不追價。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="瀚荃 8103",
    subtitle="瀚荃專刊:AI Power 連接器——看瓦數不看顆數 · 2026/10/04",
    nav=["頭版", "護城河", "P×Q", "財報", "追蹤風險", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="素材:paul_invest00 Threads 個股拆解(使用者提供)+公開財報+本系統價量籌碼 · "
           "本刊為研究筆記非投資建議 · TW-BACKTEST 財經報")
p = save_issue("8103", "20261004", html)
print("saved:", p)

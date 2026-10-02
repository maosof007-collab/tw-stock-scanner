# -*- coding: utf-8 -*-
"""財經報:國精化 4722 專刊 — HC 事件(NVIDIA 改測碳氫樹脂無布 CCL,PTFE 讓位?)。
素材:郭明錤 X 調查(2026/10)、國精化 2026/08/07 法說簡報、bulk_fin 財報/月營收、外資掃描。"""
from newspaper import shell, save_issue

T = """<b>國精化 4722</b> <span class="num">209.5</span>|距年高 <span class="num">-31.4%</span>(年高 305)
|2Q26 EPS <span class="up">1.07(YoY N/M)</span>|毛利率 <span class="up">21.7%(+5.9pp)</span>
|電子材料營收 <span class="up">Q2 +66.4%</span>|8月營收 <span class="up">+24.1%</span>"""

A1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">郭明錤產業調查 2026/10 + 國精化 08/07 法說</span></div>
<div class="head1">輝達改測碳氫樹脂 PTFE 的王座鬆動了</div>
<div class="deck">郭明錤最新調查:NVIDIA 開始測試 HC(碳氫樹脂)無布 CCL,取代先前測的 PTFE 無布方案,用於 2H27 量產的 Rubin Ultra NVL576 交換器托盤 PCB。而國精化,正是台灣少數把高階 CCL 樹脂做到 M8/M9 認證通過的上游本體廠。</div>
<div class="byline">本報整理|素材:郭明錤 X、國精化法說簡報、高盛/AtlasPCB 市場數據(法說引用)</div>
<div class="cols2"><div>
<p class="dropcap">先講事件本身。AI 交換器的訊號速度逼近物理極限,板材的介電損耗(Df)成了瓶頸——損耗最低的材料是 PTFE(鐵氟龍,Df 可到 0.0005 以下),但它有個致命傷:<span class="hl">難加工、良率差、產能開不快</span>。郭明錤的調查說,NVIDIA 為了 PCB 的「生產性」,開始測試以 HC(hydrocarbon,碳氫樹脂)為主的無布 CCL 取代 PTFE 無布方案:初步電性「不及原 PTFE,但優於 M9 等級、甚至優於 M10 已公布規格」。</p>
<p>翻譯成供應鏈語言:<b>這是一場「電性最好」與「做得出來」的拔河</b>。PTFE 贏電性,HC 贏良率與量產速度——而 2H27 要量產 NVL576,時間站在「做得出來」這一邊。被點名的板材(SG1030N)出自中國生益,所以市場第一反應是「紅色供應鏈吃香」,PTFE 鏈的台虹、亞電應聲下挫。</p>
<p>那國精化在哪?它不做板子,它做板子裡的<b>樹脂</b>——CCL 成本 25~35% 是樹脂,僅次於銅箔。8/7 法說白紙黑字:高頻高速樹脂定位 <span class="hl">M8–M10,M8/M9 已通過客戶認證、M10 電性已達客戶標準</span>,國內 CCL 廠出貨中、海外開發中。市場傳其碳氫樹脂本體產能正從約 500 噸擴向 1,800~2,000 噸(此數字出自市場討論,非法說,待查證)。</p>
<p>一句話:輝達這一測,等於幫「HC 路線」開了國家級認證——上游能供 HC/低 Df 樹脂本體的廠,賽道變寬了。股價呢?209.5 元,距 7 月年高 305 還有 -31%,HC 事件前它正跟著整個 CCL 鏈修正。</p>
</div><div class="sidebar"><h3>三十秒看懂國精化</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">特化樹脂三事業群:電子化學材料(成長引擎)、UV 光固化(48% 基石)、功能性樹脂(PSMA)</div></div>
<div class="kv"><div class="k">CCL 角色</div><div class="v">上游樹脂本體——樹脂佔 CCL 成本 25~35%,決定 Dk/Df</div></div>
<div class="kv"><div class="k">等級</div><div class="v">M8/M9 認證通過、M10 電性達標;PSMA 管 M6 以下</div></div>
<div class="kv"><div class="k">HC 事件意義</div><div class="v">NVIDIA 測 HC 無布 CCL=碳氫樹脂路線的量產背書</div></div>
<div class="kv"><div class="k">獲利</div><div class="v">Q2 毛利 21.7%(+5.9pp)、營益率 12.1%、EPS 1.07</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">209.5,距年高 -31.4%;外資 20 日 13 天買超(量小 +300 張)</div></div>
</div></div></div>"""

A2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>事件解剖|PTFE vs HC vs 玻纖布</h2></div>
<div class="head1" style="font-size:28px">一張表看懂這場材料路線戰</div>
<table><tr><th>路線</th><th>Df(越低越好)</th><th>強項</th><th>弱點</th><th>代表/受惠</th></tr>
<tr><td>傳統玻纖布 CCL(M6~M9)</td><td class="num">0.010→0.0007</td><td>成熟、產能大</td><td>玻纖布限制電性上限</td><td>台光電/台燿/生益+樹脂廠</td></tr>
<tr><td>PTFE 無布 CCL</td><td class="num hl">&lt;0.0005(最強)</td><td>電性天花板</td><td class="hl">難加工、良率差、交期長</td><td>台虹/亞電(本次下挫)</td></tr>
<tr><td><b>HC 無布 CCL(本次主角)</b></td><td class="num">優於 M9/M10</td><td class="gd">良率/生產性佳</td><td>電性不及純 PTFE</td><td>生益 SG1030N;上游 HC 樹脂廠</td></tr></table>
<div class="card"><h4>郭明錤原文四個要點(2026/10 調查)</h4>①NVIDIA 開始測 HC 無布 CCL+HC 無布 PP,取代先前測試的 PTFE 無布方案 ②目標:2H27 量產的 Rubin Ultra NVL576 switch tray PCB ③初步電性:不及原 PTFE,但優於 M9、甚至優於 M10 已公布規格 ④動機:在滿足高頻電性前提下,改善 PCB 良率與生產效率。<b>注意他的但書:測試≠定案</b>。</div>
<div class="card"><h4>為什麼上游樹脂廠是「路線中立」的贏家?</h4>板材廠押錯路線會輸(台虹押 PTFE 這次挨打);但樹脂本體廠同時供玻纖布路線(M8/M9 樹脂)和無布路線(HC 樹脂)——只要「高階 CCL 總量」漲,上游都吃得到。法說引用的市場數據:2026 CCL 累計漲價 +70%、交期拉到 4~6 個月、配額供應、高盛稱產能已預訂到 2028 之後。<b>缺貨漲價是主旋律,路線之爭只是分配問題。</b></div>
<p>對照組提醒:同屬 CCL 樹脂鏈的雙鍵(4764)走 MPPO/HC 路線、M8 有份但 M9 沒打進(本報 9/27 專刊);國精化法說直接寫 <b>M9 已通過認證、M10 電性達標</b>——兩家的「等級進度」已經分出先後。</p></div>"""

A3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>法說|三引擎盤點</h2></div>
<div class="head1" style="font-size:28px">高頻樹脂衝鋒 UV 墊底 封裝押未來</div>
<div class="card"><h4>①高頻高速樹脂(當前主力)</h4>M8–M10 定位,M8/M9 已通過客戶認證、M10 電性達客戶標準;國內 CCL 廠出貨中、海外開發中。PSMA 特用樹脂(Df 0.008@10GHz)另管 M6 以下主流板。高階 CCL 材料「供應趨緊、交期延長」是法說四大要點之一。</div>
<div class="card"><h4>②安南廠(下半年新產能)</h4>台南安南廠 7 月正式量產,設計年產能 4~5 萬噸,初期以 UV 光固化為主力,Q3 起貢獻營收;高頻材料列為未來擴充選項。UV 還有一條新路:光學封裝——CPO 應用。</div>
<div class="card"><h4>③三方合作封裝散熱材料(中長期)</h4>與「知名美系材料商(MOD 金屬材料)+國際電子材料商」共設實驗室,開發半導體先進封裝散熱材料——國精化出樹脂配方與量產化。夥伴名稱依保密協議不揭露。從 CCL 樹脂延伸到封裝材料,是估值故事的第二章。</div>
<table><tr><th>產品線(1H26)</th><th>營收占比</th><th>YoY</th></tr>
<tr><td class="hl">電子化學材料</td><td class="num">19.8%(+6.4pp)</td><td class="num gd">+50.8%(Q2 +66.4%)</td></tr>
<tr><td>UV 光固化</td><td class="num">48.2%</td><td class="num hl">-9.9%</td></tr>
<tr><td>不飽和聚酯</td><td class="num">16.8%</td><td class="num">-2.0%</td></tr>
<tr><td>塗料樹脂</td><td class="num">13.2%</td><td class="num">+14.9%</td></tr></table>
<p>結構轉型進行中:<b>兩成的電子材料貢獻了幾乎全部成長</b>,近半壁江山的 UV 還在衰退——安南廠量產後 UV 能否止跌,決定整體營收斜率。</p></div>"""

A4 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>財報|利潤率的跳變</h2></div>
<div class="head1" style="font-size:28px">營收小增 獲利翻倍 這就是產品組合升級的長相</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">9.73</td><td class="num">15.83%</td><td class="num">6.20%</td><td class="num">0.01</td></tr>
<tr><td>3Q25</td><td class="num">9.69</td><td class="num">18.72%</td><td class="num">8.92%</td><td class="num">0.81</td></tr>
<tr><td>4Q25</td><td class="num">8.68</td><td class="num">17.84%</td><td class="num">5.11%</td><td class="num">0.67</td></tr>
<tr><td>1Q26</td><td class="num">8.90</td><td class="num">14.15%</td><td class="num">3.10%</td><td class="num">0.22</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">10.38</td><td class="num gd">21.69%</td><td class="num gd">12.11%</td><td class="num gd">1.07</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">2.95</td><td class="num hl">-6.7%</td></tr>
<tr><td>2026/06</td><td class="num">3.63</td><td class="num gd">+26.9%</td></tr>
<tr><td>2026/07</td><td class="num">4.43</td><td class="num gd">+27.2%</td></tr>
<tr><td>2026/08</td><td class="num">4.11</td><td class="num gd">+24.1%</td></tr></table>
<p>看點有三:①1Q26 毛利率 14.15% → 2Q26 21.69%,<b>單季跳 7.5 個百分點</b>——高階樹脂放量+漲價傳導的典型指紋 ②6 月起月營收連三月 +24~27%,對應安南廠量產+電子材料追單 ③全年若下半年維持 Q2 水準,EPS 約 3.3~3.5,209.5 元約 60 倍——<b>市場已經在用「HC 擴產兌現後」的 2027 定價</b>,不便宜,買的是等級升級(M9→M10)+擴產斜率。</p></div>"""

A5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">測試不是訂單 四個檢核點盯進度</div>
<div class="card"><h4>追蹤清單</h4>①郭明錤後續:HC 無布是否從「測試」升級為「定案」(2H27 NVL576 量產前必有結論) ②HC 本體擴產(市傳 500→1,800~2,000 噸)在下次法說是否被公司證實 ③電子材料營收占比:19.8% 之後每季要續升 ④毛利率守 20%+(證明 Q2 不是單季現象) ⑤三方封裝散熱材料的首個量產案 ⑥月營收維持 +20%+。</div>
<div class="card"><h4>反方劇本</h4>①郭明錤自己的但書:HC 僅在測試,NVIDIA 同時仍有 PTFE 與玻璃核(2028)排程——路線隨時可能再轉 ②板材端贏家是生益(紅鏈),國精化是否供料生益屬市場傳聞,供應關係待查 ③UV 佔 48% 還在衰退,拖累整體 ④60 倍 PE 已搶跑,等級認證若卡關殺估值會很快 ⑤外資 20 日雖 13 天買超但僅 +300 張——籌碼未表態,別把題材熱當籌碼熱。</div>
<p><b>本報判準</b>:HC 事件對國精化是「賽道加寬」不是「訂單到手」。它真正的護城河是<b>路線中立</b>——玻纖布(M8/M9/M10)和無布(HC)兩邊都供得上,缺貨漲價環境下上游樹脂廠旱澇保收。操作上照家規:距年高 -31% 是修正中的左側,等地圖出突破訊號+體檢卡過關,不替題材接刀。</p></div>"""

_QA = [
    ("郭明錤調查的核心內容是什麼?", "NVIDIA 開始測 HC(碳氫樹脂)無布 CCL,取代先前測試的 PTFE 無布方案,用於 2H27 Rubin Ultra NVL576 交換器托盤。"),
    ("PTFE 的致命傷是什麼?", "電性最強但難加工、良率差、產能開不快——「PTFE 問題」就是生產性問題。"),
    ("HC 無布的電性表現如何?", "不及純 PTFE,但優於 M9、甚至優於 M10 已公布規格。"),
    ("國精化在 CCL 裡的角色?", "上游樹脂本體——樹脂佔 CCL 成本 25~35%,決定 Dk/Df,僅次於銅箔的關鍵材料。"),
    ("國精化的等級進度到哪?", "M8/M9 已通過客戶認證、M10 電性已達客戶標準(8/7 法說)。"),
    ("為何說上游樹脂廠「路線中立」?", "玻纖布路線和無布 HC 路線都要樹脂——板材廠押錯邊會輸,樹脂廠兩邊都供。"),
    ("這次事件誰先受傷?", "PTFE 鏈的台虹、亞電下挫;被點名板材 SG1030N 出自中國生益。"),
    ("2Q26 獲利結構的亮點?", "毛利率單季跳 7.5pp 至 21.69%、營益率 12.11%、EPS 1.07——產品組合升級指紋。"),
    ("最大的拖油瓶是什麼?", "UV 光固化佔營收 48% 仍年減 9.9%——安南廠量產後能否止跌是關鍵。"),
    ("郭明錤的但書,也是最大風險?", "測試≠定案——NVIDIA 同時還有 PTFE 與玻璃核排程,路線隨時可能再轉。"),
]
QA = ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
      '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
      + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                for i, (q, a) in enumerate(_QA)) + "</div>")

BODY = A1 + A2 + A3 + A4 + A5 + QA
html = shell(
    masthead="TW·財經報", stamp="國精化 4722",
    subtitle="國精化專刊:HC 事件——輝達改測碳氫樹脂,PTFE 王座鬆動 · 2026/10/02",
    nav=["頭版", "事件解剖", "法說", "財報", "追蹤", "測驗"],
    ticker_html=T, body_html=BODY,
    footer="素材:郭明錤 X 產業調查(2026/10)+國精化 2026/08/07 法說簡報+公開財報+本系統外資掃描 · "
           "本刊為研究筆記非投資建議 · TW-BACKTEST 財經報")
p = save_issue("4722", "20261002", html)
print("saved:", p)

# -*- coding: utf-8 -*-
"""「還沒發動」系列財經報(2026-10-01):五檔低檔整理+外資連吃+未出量。
素材=各公司最新法說簡報(concall 庫)+ bulk_fin 財報/月營收 + quiet_accum 籌碼掃描。
鐵律:故事全部出自法說與財報,不猜;雷達標籤被法說推翻的,照實寫(鴻準教案)。"""
from newspaper import shell, save_issue

DATE = "20261001"
FOOT = ("素材:各公司法說簡報+公開財報+本系統外資籌碼掃描 · 本刊為研究筆記非投資建議 · "
        "TW-BACKTEST 財經報「還沒發動」系列")


def qa(items):
    return ('<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span>'
            '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
            + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                      for i, (q, a) in enumerate(items)) + "</div>")


def chip_sect(rows_html, bigfact_n, bigfact_note):
    """A4 籌碼版:還沒發動四條件+吸籌比大數字。"""
    return f"""<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span>
<h2>籌碼|為什麼說它「還沒發動」</h2><span class="src">本系統外資掃描 2026/10/01</span></div>
<div class="head1" style="font-size:28px">外資在吃貨 量還沒出來</div>
<table><tr><th>條件</th><th>門檻</th><th>本檔</th></tr>{rows_html}</table>
<div class="bigfact"><div>外資吸籌比(20日外資買超 ÷ 20日總成交量)</div>
<div class="n">{bigfact_n}</div><div>{bigfact_note}</div></div>
<p><b>這是觀察名單,不是買點。</b>家規禁追:等它自己出「第一根量」,回測不破、
體檢卡過關才進場;爆量日+2~3天禁入,停損=買價-1.5ATR。</p></div>"""


# ═══════════════════ 第一期:中興電 1513 ═══════════════════
T1 = """<b>中興電 1513</b> <span class="num">168.00</span>|距年高 <span class="num">-10.2%</span>
|外資20日買超 <span class="up">15天</span>|吸籌比 <span class="up">20.3%(全市場第一)</span>
|2Q26 EPS <span class="num">2.56</span>|毛利率 <span class="num">28.44%</span>|在手訂單 <span class="num">431億</span>"""

A1_1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:2026/04/23 法說</span></div>
<div class="head1">電網大牛市裡 市佔八成的那家還在盤整</div>
<div class="deck">華城、士電早已噴出,GIS 台電市佔 80% 的中興電卻距年高 -10% 原地整理——而外資 20 日內 15 天買超,吸籌比 20.3% 是全市場第一。</div>
<div class="byline">本報整理|素材:中興電 2026/04/23 法人說明會、台電公開資料</div>
<div class="cols2"><div>
<p class="dropcap">台電強韌電網計畫十年 5,645 億、配電系統五年升級 334 億、2026 年台電四部新燃氣機組同時試運轉——台灣電力建設正處於「台電從未遇見過的挑戰」(董事長曾文生語)。曾文生給的數字更直接:半導體擴廠未來五年新增用電 5.3~5.4GW,一座晶圓廠就要 200 萬瓩,平均一年新增 100 萬瓩,是過去十年的 2~2.5 倍。</p>
<p>吃這波最大的設備是 GIS(氣體絕緣開關設備),而中興電 GIS 在台電體系市佔約 <span class="hl">80%</span>、非台電體系約 65%,今年還要擴業務人力把市佔再拉 10%。法說揭露:至 3 月已取訂單 63 億,<span class="hl">在手訂單 431 億</span>——約是 2025 全年營收 274.5 億的 1.57 倍。</p>
<p>財報持續創高:2Q26 營收 75.3 億、毛利率 28.44%、EPS 2.56,三項都是近年單季新高;2025 全年 EPS 8.07 已是歷史高。8 月營收年增 8.9%,穩定但不算爆發——這正是它還在箱體的原因:市場在等訂單認列加速。</p>
<p>同族群的華城、士電股價早一步反映電網題材,中興電卻在 40 日 14.9% 的窄箱體裡——落後補漲或基本面有詐?外資用 15 個買超日投了票。</p>
</div><div class="sidebar"><h3>三十秒看懂中興電</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">GIS 開關設備、統包工程(EPC)、發電機機房空調、氫能、停車場(寶盛)</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">台電強韌電網+離岸風電 3.2/3.3 期+半導體擴廠+AI 資料中心機房</div></div>
<div class="kv"><div class="k">訂單</div><div class="v">在手 431 億(至 26/3),115 年取案目標 260 億</div></div>
<div class="kv"><div class="k">獲利</div><div class="v">2025 EPS 8.07 → 2Q26 單季 2.56 續創高</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">168 元,距年高 -10.2%,40 日箱體 14.9%</div></div>
<div class="kv"><div class="k">外資</div><div class="v">20 日 15 天買超 7,168 張,吸籌比 20.3%</div></div>
</div></div></div>"""

A2_1 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>法說|事業群逐一點名</h2></div>
<div class="head1" style="font-size:28px">重電之外 還有四條支線在長大</div>
<div class="card"><h4>重電(主引擎)</h4>台電強韌電網+電源開發+汰舊換新;配合離岸風電 3.2-3.3 期、半導體海內外擴廠、國際大廠在台建 AI/IDC 機房。115 年重電預計取案 260 億(公家 170/民間 80/外銷 7.6)。</div>
<div class="card"><h4>發電機、機房空調(+15%)</h4>電信業者與國際大廠在台建 IDC 機房及 AI 研發中心帶動;已有業者洽談「模組化機房」合作。自製磁懸浮離心冰水主機能效一級,進了國際知名企業雲端數據機房與桃園機場。</div>
<div class="card"><h4>停車事業(寶盛)</h4>2026/1/1 與系統公司整併完成,拓日本、泰國智慧停車,Q3 起獲利顯著提升。</div>
<div class="card"><h4>氫能</h4>氫能巴士(合資首都客運)+甲醇重組製氫貨櫃(150kg/d 供 75kW 燃料電池);光儲氫整合降工業用戶電費為商業模式。</div>
<div class="card"><h4>內功:自動化焊接+AI</h4>大型自動焊接設備上線(345KV/161KV CB 與支管),AI 報價/語音系統——預期產能提升 15~20%,這是出貨瓶頸的解方。</div>
<table><tr><th>電力需求證據(法說引用)</th><th>數字</th></tr>
<tr><td>全球資料中心耗電 2024→2030</td><td class="num">371→935 TWh(2.5 倍)</td></tr>
<tr><td>台電強韌電網十年計畫</td><td class="num">5,645 億</td></tr>
<tr><td>配電系統五年升級</td><td class="num">334 億</td></tr>
<tr><td>半導體未來五年新增用電</td><td class="num hl">5.3~5.4 GW</td></tr>
<tr><td>在建燃氣機組總裝置容量</td><td class="num">20,260~22,460 MW</td></tr></table></div>"""

A3_1 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|創高中的安靜</h2></div>
<div class="head1" style="font-size:28px">毛利率五季走高 月營收穩而不爆</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">71.04</td><td class="num">24.68%</td><td class="num">17.18%</td><td class="num">1.90</td></tr>
<tr><td>3Q25</td><td class="num">67.91</td><td class="num">25.87%</td><td class="num">19.11%</td><td class="num">2.31</td></tr>
<tr><td>4Q25</td><td class="num">71.06</td><td class="num">27.00%</td><td class="num">17.59%</td><td class="num">2.08</td></tr>
<tr><td>1Q26</td><td class="num">64.91</td><td class="num">25.98%</td><td class="num">18.54%</td><td class="num">1.94</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">75.33</td><td class="num gd">28.44%</td><td class="num gd">20.05%</td><td class="num gd">2.56</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">23.9</td><td class="num">+3.6%</td></tr>
<tr><td>2026/06</td><td class="num">28.3</td><td class="num">+8.3%</td></tr>
<tr><td>2026/07</td><td class="num">24.1</td><td class="num">+3.8%</td></tr>
<tr><td>2026/08</td><td class="num">25.0</td><td class="num">+8.9%</td></tr></table>
<p>年成長個位數,但<b>毛利率從 24.68% 一路墊到 28.44%</b>——統包工程占比與 GIS 價格結構在改善。431 億在手訂單 ÷ 年營收 275 億 = 1.57 年能見度;股價沒跟上獲利創高,本益比反而被動變便宜(2026 年化 EPS 約 9~10 元,168 元約 17~18 倍)。</p></div>"""

CHIP_1 = chip_sect(
    """<tr><td>低檔未發動</td><td>距年高 ≤ -10%</td><td class="num gd">-10.2%</td></tr>
<tr><td>整理區間</td><td>40日箱體 ≤ 25%</td><td class="num gd">14.9%(20日僅5.2%)</td></tr>
<tr><td>外資連吃</td><td>20日買超 ≥ 12天</td><td class="num gd">15天,+7,168張</td></tr>
<tr><td>未出量</td><td>近15日無 2.3×均量</td><td class="num gd">通過</td></tr>""",
    "20.3%", "本次掃描全市場第一——外資吃掉近期成交量的五分之一,而股價還沒動")

A5_1 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">追蹤清單與反方劇本</div>
<div class="card"><h4>追蹤清單</h4>①月營收何時站上 28 億常態(訂單認列加速的證據) ②毛利率守 27%+ ③ 115 年取案 260 億達成率 ④自動化焊接產能 +15~20% 兌現 ⑤華城/士電若回檔,中興電相對強弱 ⑥第一根爆量(>2.3×均量)出現日</div>
<div class="card"><h4>反方劇本</h4>①統包認列節奏慢,月營收持續個位數成長→箱體再磨半年 ②銅價等原物料吃毛利 ③重電族群整體評價下修(華城/士電領跌)拖累 ④氫能/停車等支線虧損擴大 ⑤法說是 4 月的,資訊已半年——等 Q3 法說更新訂單數字</div>
<p><b>本報判準</b>:這檔的故事不需要想像力——電網投資是十年國策,它是市佔 80% 的在位者,獲利已在創高。爭的只是「何時輪到它」。外資吸籌比 20.3% 說明有人不想等了。</p></div>"""

QA_1 = qa([
    ("中興電 GIS 在台電體系市佔約多少?", "約 80%(非台電體系約 65%)。"),
    ("至 2026 年 3 月在手訂單多少?", "431 億,約 2025 年營收的 1.57 倍。"),
    ("台電強韌電網十年計畫總額?", "5,645 億元。"),
    ("台電董座估半導體未來五年新增用電?", "5.3~5.4GW,一座晶圓廠就要 200 萬瓩。"),
    ("2Q26 毛利率與 EPS?", "28.44%、2.56,皆近年單季新高。"),
    ("發電機/機房空調業務今年預計成長?", "15%,受 IDC 機房與 AI 研發中心帶動。"),
    ("自動化焊接+AI 導入預期產能提升?", "15~20%——出貨瓶頸的解方。"),
    ("外資 20 日買超幾天?吸籌比?", "15 天、20.3%,本次掃描全市場第一。"),
    ("它為何還算「還沒發動」?", "距年高 -10.2%、40 日箱體 14.9%、近 15 日未出爆量。"),
    ("進場紀律是什麼?", "不追;等第一根量出現、回測不破、體檢卡過關,停損=買價-1.5ATR。"),
])

# ═══════════════════ 第二期:鴻準 2354 ═══════════════════
T2 = """<b>鴻準 2354</b> <span class="num">65.70</span>|距年高 <span class="num">-10.2%</span>
|外資20日買超 <span class="up">13天 31,006張</span>|吸籌比 <span class="num">13.5%</span>
|8月營收 <span class="up">+58.4%</span>|2Q26 EPS <span class="num">0.63</span>|2025營收 <span class="num">1,562億</span>"""

A1_2 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:2026/09/30 法說(前日剛開)</span></div>
<div class="head1">外資默吃三萬張 賭的是遊戲機回來了</div>
<div class="deck">7 月營收 +37%、8 月 +58%——遊戲機新主機放量把鴻準從衰退拉回成長;法說講的卻是機器人與美國製造。外資 20 日買超 31,006 張,是本系列吃貨張數最大的一檔。</div>
<div class="byline">本報整理|素材:鴻準 2026/09/30 法人說明會、月營收公告</div>
<div class="cols2"><div>
<p class="dropcap">先說本報的自我更正:本系統雷達原本標鴻準「AI 伺服器散熱/機殼」,翻完 9/30 法說,這標籤言過其實——鴻準營收 <span class="hl">76% 是遊戲機</span>(組裝代工),散熱模組 16%、機殼 6%。它不是 AI 散熱純度股,是遊戲機代工巨人。</p>
<p>但數字比標籤精彩:上半年遊戲機營收年減、2Q26 整體營收 -26.4%,然後 7 月突然 +37.5%、8 月 <span class="hl">+58.4%</span>——新一代主機開始放量出貨的典型曲線。外資 20 日 13 天買超、默吃 3.1 萬張,時間點正好在營收轉正之後、法說(9/30)之前。</p>
<p>法說本身講的是下一步:核心產品列了遊戲機、散熱模組、機殼、<b>機器人</b>四項;機器人頁數佔了簡報三分之一——巡檢、醫療、教育、智慧家庭,再加 RaaS(Robot as a Service)商業模式。另一個重點是美國肯塔基州路易維爾工廠:FTC USA 製造基地、垂直整合、自動化——關稅時代的在地製造牌。</p>
<p>風險同樣要念:毛利率只有 4.03%、營益率 1.13%,代工體質;2Q26 EPS 0.63。這種公司的獲利彈性全看稼動率——而稼動率正在被新主機填滿。</p>
</div><div class="sidebar"><h3>三十秒看懂鴻準</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">遊戲機代工 76%、散熱模組 16%、機殼 6%(鴻海集團,2025 營收 1,562 億)</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">新主機放量:7月+37%、8月+58%;低基期反轉</div></div>
<div class="kv"><div class="k">下一步</div><div class="v">機器人四場景+RaaS;美國肯塔基製造基地</div></div>
<div class="kv"><div class="k">體質</div><div class="v">毛利 4.03%/營益 1.13%——稼動率決定一切</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">65.7 元,距年高 -10.2%,40 日箱體 24.3%</div></div>
<div class="kv"><div class="k">外資</div><div class="v">13/20 天買超,31,006 張(本系列最大)</div></div>
</div></div></div>"""

A2_2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>法說|機器人與美國牌</h2></div>
<div class="head1" style="font-size:28px">簡報三分之一在講機器人 還給了商業模式</div>
<div class="card"><h4>機器人四場景</h4>①巡檢管理:工廠/倉儲異常偵測自動回報 ②醫療服務:物流配送→臨床輔助,緩解人力短缺 ③教育:遊戲化互動、STEM、特教個人化 ④智慧家庭:語音+環境感測+邊緣運算+大語言模型。</div>
<div class="card"><h4>RaaS 商業模式(法說原文框架)</h4>CapEx to OpEx:整合產品生命週期成「可預測的經常性收入流」;Data Flywheel:硬體規模收資料養 AI 模型;Land and Expand:首次部署驗證後擴場景。——代工廠講 LTV、講數據飛輪,是轉型姿態最完整的一頁。</div>
<div class="card"><h4>美國製造(FTC USA)</h4>肯塔基州路易維爾工廠:生產週期垂直整合+智能製造;規劃→NPI→製造與服務全鏈在地,主打關稅優化、快速換修、IP 保護。</div>
<table><tr><th>部門營收(1H26)</th><th>占比</th></tr>
<tr><td>遊戲機</td><td class="num">76%</td></tr>
<tr><td>散熱模組</td><td class="num">16%</td></tr>
<tr><td>機殼</td><td class="num">6%</td></tr>
<tr><td>其他</td><td class="num">2%</td></tr></table></div>"""

A3_2 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|反轉的形狀</h2></div>
<div class="head1" style="font-size:28px">上半年衰退兩成六 七八月突然轉正噴五成</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">412.2</td><td class="num">2.97%</td><td class="num">0.95%</td><td class="num">0.39</td></tr>
<tr><td>4Q25</td><td class="num">425.1</td><td class="num">4.22%</td><td class="num">2.17%</td><td class="num">0.64</td></tr>
<tr><td>1Q26</td><td class="num">252.8</td><td class="num">4.84%</td><td class="num">1.48%</td><td class="num">0.47</td></tr>
<tr><td>2Q26</td><td class="num">303.4</td><td class="num">4.03%</td><td class="num">1.13%</td><td class="num">0.63</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">87.6</td><td class="num hl">-40.6%</td></tr>
<tr><td>2026/06</td><td class="num">150.5</td><td class="num">+10.7%</td></tr>
<tr><td>2026/07</td><td class="num">214.2</td><td class="num gd">+37.5%</td></tr>
<tr><td>2026/08</td><td class="num">218.7</td><td class="num gd">+58.4%</td></tr></table>
<p>5 月 -40% → 8 月 +58%,三個月翻轉近百個百分點,這是<b>產品週期切換</b>的指紋:舊主機去化完、新主機 ramp。低毛利代工的盈虧槓桿在營收:稼動率填滿後,EPS 彈性比毛利率數字看起來大得多。2025 全年 EPS 約 2.0(四季合計),65.7 元約 33 倍——便宜要靠下半年證明。</p></div>"""

CHIP_2 = chip_sect(
    """<tr><td>低檔未發動</td><td>距年高 ≤ -10%</td><td class="num gd">-10.2%</td></tr>
<tr><td>整理區間</td><td>40日箱體 ≤ 25%</td><td class="num gd">24.3%(20日 9.0%)</td></tr>
<tr><td>外資連吃</td><td>20日買超 ≥ 12天</td><td class="num gd">13天,+31,006張</td></tr>
<tr><td>未出量</td><td>近15日無 2.3×均量</td><td class="num gd">通過</td></tr>""",
    "13.5%", "張數為本系列之最——營收轉正後、9/30 法說前,外資已先進場")

A5_2 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">時間順序本身就是訊號</div>
<div class="card"><h4>追蹤清單</h4>①9~12 月營收是否維持 200 億+/月、YoY 雙位數 ②3Q26 毛利率能否回 4.5%+(稼動率證據) ③法說後法人報告的出貨量預估 ④機器人:從簡報走到訂單的第一個客戶 ⑤散熱模組有無切入伺服器案(標籤翻案的機會)</div>
<div class="card"><h4>反方劇本</h4>①新主機備貨一次性,Q4 拉完就掉(遊戲機業的老劇本) ②毛利 4% 無防禦,營收一軟 EPS 歸零速度快 ③機器人簡報多於實績,RaaS 尚無收入證據 ④大箱體(24.3%)貼著 25% 門檻,其實波動不小</div>
<p><b>本報判準</b>:外資吃貨(營收轉正後)→法說(9/30)→接下來是 10/10 的 9 月營收。三個時間點連成一線,這檔的驗證成本很低:下一次月營收就見真章。</p></div>"""

QA_2 = qa([
    ("鴻準營收最大的部門是什麼?占比?", "遊戲機代工,約 76%——不是散熱。"),
    ("7、8 月營收年增多少?", "+37.5%、+58.4%,新主機放量指紋。"),
    ("5 月營收年增是多少?", "-40.6%——三個月內從 -40% 翻到 +58%。"),
    ("鴻準毛利率大約多少?", "4% 上下,獲利彈性靠稼動率不靠毛利。"),
    ("法說花最多篇幅講什麼新業務?", "機器人(巡檢/醫療/教育/智慧家庭)+RaaS 模式。"),
    ("RaaS 的三個關鍵詞?", "CapEx to OpEx、Data Flywheel、Land and Expand。"),
    ("美國製造基地在哪?", "肯塔基州路易維爾(FTC USA)。"),
    ("外資 20 日吃了多少張?", "31,006 張,本系列五檔中最大。"),
    ("本報對原雷達標籤做了什麼?", "自我更正:「AI 伺服器散熱」言過其實,本質是遊戲機代工+機器人轉型。"),
    ("這檔最便宜的驗證方法?", "10/10 的 9 月營收——維持 200 億+/月即故事成立。"),
])

# ═══════════════════ 第三期:南寶 4766 ═══════════════════
T3 = """<b>南寶 4766</b> <span class="num">340.50</span>|距年高 <span class="num">-18.3%</span>
|外資20日買超 <span class="up">12天</span>|吸籌比 <span class="num">13.1%</span>
|1H26 EPS <span class="up">13.82(+30%)</span>|年化ROE <span class="num">23.8%</span>|毛利率 <span class="num">32.5%</span>"""

A1_3 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:2026/08/19 法說</span></div>
<div class="head1">鞋膠王的半導體滲透 已經開始小量出貨</div>
<div class="deck">世界第一的運動鞋接著劑廠,法說白紙黑字:半導體封裝用膠與折疊螢幕 OCA「已取得關鍵技術突破,目前已開始小量出貨」。這不是題材,是進行式。</div>
<div class="byline">本報整理|素材:南寶 2026/08/19 法人說明會</div>
<div class="cols2"><div>
<p class="dropcap">南寶是誰?全球運動品牌的鞋用接著劑做到世界第一,毛利率長年 32~35%,上半年年化 ROE <span class="hl">23.8%</span>——傳產裡的資優生。但讓它上本系列的,是法說第 11 頁那段話:「半導體用膠與折疊螢幕用光學透明膠已取得關鍵技術突破,<span class="hl">目前已開始小量出貨</span>」、「主要應用在半導體封裝製程,持續與合作夥伴共同研發取得認證」。</p>
<p>策略名字叫「NextGen」:鎖定<b>進口替代需求、高技術門檻、潛在市場龐大</b>的項目,聚焦半導體與電子特化——半導體製程高階特化材料長年進口,供應鏈在地化是順風。Foldable OCA 這條線,南寶自稱已「躋身全球少數具備相關技術能力的供應商」,解的是折疊螢幕反覆彎折白化破膠的痛點。</p>
<p>本業也沒閒著:2Q26 營收 65.8 億(+13%)、EPS 7.27(+58%);1H26 EPS 13.82(+30%)。公司說全年營收創高把握度「較上季進一步提升」,獲利挑戰新高。塗料端還點名要搶「AI 基礎建設應用」商機。</p>
<p>一個誠實註記:市場曾把南寶跟「玻璃布」聯想,法說全篇<b>零提及</b>玻璃布/CCL——那是南亞的故事。南寶的電子轉型走的是封裝膠與 OCA,看錯供應鏈位置會追錯行情。</p>
</div><div class="sidebar"><h3>三十秒看懂南寶</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">接著劑 69%(鞋材世界第一)、塗料與建材 25%(澳洲為主)</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">半導體封裝膠+Foldable OCA 已小量出貨,客戶認證推進中</div></div>
<div class="kv"><div class="k">體質</div><div class="v">毛利 32.5%、年化 ROE 23.8%、1H26 EPS 13.82(+30%)</div></div>
<div class="kv"><div class="k">目標</div><div class="v">全年營收獲利雙創高;長期 ROE 20%+、費用率低於 15%</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">340.5 元,距年高 -18.3%,40 日箱體 14.2%</div></div>
<div class="kv"><div class="k">外資</div><div class="v">12/20 天買超;成交清淡(日均 0.36 億)是雙面刃</div></div>
</div></div></div>"""

A2_3 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>法說|NextGen 轉型地圖</h2></div>
<div class="head1" style="font-size:28px">從鞋底到晶片 用的是同一套膠水科學</div>
<div class="card"><h4>半導體用膠(封裝製程)</h4>已關鍵技術突破、小量出貨;「隨著客戶認證進度推進,今年營收將逐步提升」;與合作夥伴「攜手開發世界級領先技術」。鎖定進口替代——高階特化材料在地化。</div>
<div class="card"><h4>Foldable OCA(折疊螢幕光學膠)</h4>痛點:反覆彎折→白點/白化/破膠。南寶版本高耐彎折、維持高黏著彈性——全球少數具備此技術的供應商之一,已小量出貨。</div>
<div class="card"><h4>本業三引擎</h4>①鞋材:與品牌、鞋廠共同開發新材質接著技術搶單 ②工業接著劑:半導體、電子、木工紡織多點開花 ③塗料建材:澳洲市占續升+澳幣升值;目標搶政府基建、AI 基建、消費電子商機。</div>
<table><tr><th>法說關鍵詞詞頻(本系統自動掃描)</th><th>次數</th></tr>
<tr><td>半導體</td><td class="num hl">25</td></tr>
<tr><td>封裝</td><td class="num">5</td></tr>
<tr><td>認證</td><td class="num">5</td></tr>
<tr><td>先進封裝</td><td class="num">4</td></tr></table>
<p>詞頻會說話:一家鞋膠公司的法說講了 25 次半導體。E SG 順帶一提:S&P Global 化學產業全球前 1%、綠色產品占營收 72%——外資愛的那型。</p></div>"""

A3_3 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|資優生的成績單</h2></div>
<div class="head1" style="font-size:28px">EPS 年增三成 業外處分再添一筆</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">58.05</td><td class="num">34.49%</td><td class="num">16.96%</td><td class="num">4.59</td></tr>
<tr><td>3Q25</td><td class="num">59.10</td><td class="num">33.85%</td><td class="num">16.29%</td><td class="num">4.96</td></tr>
<tr><td>4Q25</td><td class="num">59.30</td><td class="num">33.74%</td><td class="num">16.17%</td><td class="num">4.65</td></tr>
<tr><td>1Q26</td><td class="num">58.36</td><td class="num">35.11%</td><td class="num">17.63%</td><td class="num">6.55</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">65.83</td><td class="num">32.50%</td><td class="num">15.85%</td><td class="num gd">7.27</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">22.0</td><td class="num">+12.3%</td></tr>
<tr><td>2026/06</td><td class="num">20.9</td><td class="num">+12.8%</td></tr>
<tr><td>2026/07</td><td class="num">24.0</td><td class="num gd">+20.8%</td></tr>
<tr><td>2026/08</td><td class="num">22.2</td><td class="num">+14.2%</td></tr></table>
<p>注意兩件事:①2Q26 毛利率 32.5% 比 1Q 低 2.6 個百分點——原物料上漲、調價有時間差,法說自己也說「客戶提前積極下單備貨」墊高了營收;②2Q26 EPS 7.27 裡有業外(淨非營業損益 2.05 億,含資產處分)。拆開看:本業穩健成長,電子轉型的營收貢獻現在還小——買的是斜率,不是現值。</p></div>"""

CHIP_3 = chip_sect(
    """<tr><td>低檔未發動</td><td>距年高 ≤ -10%</td><td class="num gd">-18.3%</td></tr>
<tr><td>整理區間</td><td>40日箱體 ≤ 25%</td><td class="num gd">14.2%(20日 6.2%)</td></tr>
<tr><td>外資連吃</td><td>20日買超 ≥ 12天</td><td class="num gd">12天,+279張</td></tr>
<tr><td>未出量</td><td>近15日無 2.3×均量</td><td class="num gd">通過</td></tr>""",
    "13.1%", "張數小(279張)但這檔日均成交只有 0.36 億——比率才是重點;流動性低,買賣都要分批")

A5_3 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">看認證 不看話術</div>
<div class="card"><h4>追蹤清單</h4>①下次法說:半導體膠從「小量出貨」是否升級為「量產/放量」用詞 ②合作夥伴/客戶名稱何時揭露 ③毛利率回 34%+(調價傳導完成) ④月營收維持雙位數增 ⑤Foldable OCA 有無進入品牌旗艦機供應鏈的訊號</div>
<div class="card"><h4>反方劇本</h4>①電子營收占比極小,轉型敘事先於數字——估值先走、基本面慢到 ②鞋材終端消費仍弱,Q2 的「提前備貨」可能預支 Q3 ③業外處分不可重複 ④日均 0.36 億流動性,出場成本高——倉位必須小</div>
<p><b>本報判準</b>:用戶方法論的教案——「不是要去猜,看法說是否有導入新的」。南寶法說給了可驗證的進行式(小量出貨+認證中),下一步只看認證進度,不看新聞稿形容詞。</p></div>"""

QA_3 = qa([
    ("南寶的本業世界第一是什麼?", "運動鞋用接著劑(鞋膠)。"),
    ("NextGen 策略鎖定什麼樣的項目?", "進口替代需求、高技術門檻、潛在市場龐大。"),
    ("法說說半導體用膠進度到哪?", "關鍵技術突破,已開始小量出貨,客戶認證推進中。"),
    ("Foldable OCA 解什麼痛點?", "折疊螢幕反覆彎折的白點/白化/破膠。"),
    ("1H26 EPS 與年增率?", "13.82 元,+30%;年化 ROE 23.8%。"),
    ("2Q26 毛利率為何下滑?", "原物料上漲、調價時間差;客戶提前備貨墊營收。"),
    ("南寶法說提了幾次玻璃布?", "零次——玻璃布是南亞的故事,別搞混供應鏈位置。"),
    ("法說詞頻最高的關鍵詞?", "半導體,25 次。"),
    ("這檔籌碼上最大的限制?", "日均成交僅 0.36 億,流動性低,倉位要小、進出要分批。"),
    ("下次法說最該盯的一個用詞變化?", "半導體膠從「小量出貨」是否變成「量產/放量」。"),
])

# ═══════════════════ 第四期:廣宇 2328 ═══════════════════
T4 = """<b>廣宇 2328</b> <span class="num">47.55</span>|距年高 <span class="num">-22.9%</span>
|外資20日買超 <span class="up">14天</span>|吸籌比 <span class="num">12.6%</span>
|1H26 EPS <span class="num hl">-0.24(虧損)</span>|AI+Robotics營收 <span class="up">+1,277%</span>|8月營收 <span class="up">+19.7%</span>"""

A1_4 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:2026/07/13 法說</span></div>
<div class="head1">虧損中的轉型賭局 外資卻連吃十四天</div>
<div class="deck">上半年每股虧 0.24 元,法說卻喊出「AI+Robotics 雙賽道」:馬來西亞廠今年量產 AI 伺服器、併購 Magnax 拿軸向磁通電機。本系列風險最高、故事最猛的一檔。</div>
<div class="byline">本報整理|素材:廣宇 2026/07/13 法人說明會、月營收公告</div>
<div class="cols2"><div>
<p class="dropcap">先把醜話放頭版:廣宇 1Q26 EPS -0.16、2Q26 -0.08,<span class="hl">連兩季虧損</span>,毛利率從 12% 掉到 8.55%。消費電子占 55%、車用 16% 衰退兩成——本業成長受限,法說自己承認,所以「選定 AI+Robotics 為下一賽道」。</p>
<p>轉型的兩條腿,法說給得具體。第一條:<b>AI 伺服器</b>。廣宇是鴻海集團唯一有馬來西亞產能的公司,東南亞 AI 資料中心建置潮下「就近服務當地廣大 AI 伺服器需求」,時間表寫 2026 年馬來西亞廠開始量產,先提供即時營收與現金流。第二條:<b>機器人</b>。完成併購比利時 Magnax 拿下軸向磁通電機(AFM)技術——高功率密度、高毛利屬性;時間表 2027 AFM 貢獻營收、2028 貢獻獲利;2030 年目標「供應機器人整體成本結構 25~50% 的零組件」。</p>
<p>數字端的苗頭:AI+Robotics 相關營收年增 <span class="hl">+1,277%</span>(占比僅 1%,基期極低);7 月營收 +16.4%、8 月 +19.7% 連兩月轉正雙位數。外資 20 日 14 天買超——在虧損股上連吃 14 天,買的顯然不是上半年財報,是馬來西亞廠的下半年。</p>
</div><div class="sidebar"><h3>三十秒看懂廣宇</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">鴻海系連接器/線束/組裝:消費電子 55%、車用 16%、工控 13%、通訊 15%</div></div>
<div class="kv"><div class="k">困境</div><div class="v">1H26 連兩季虧損,毛利率 8.55%,車用/工控/通訊全衰退</div></div>
<div class="kv"><div class="k">賭局一</div><div class="v">鴻海集團唯一馬來西亞產能→2026 量產 AI 伺服器</div></div>
<div class="kv"><div class="k">賭局二</div><div class="v">Magnax AFM 電機:2027 營收/2028 獲利/2030 佔機器人成本 25~50%</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">47.55 元,距年高 -22.9%(系列最深)</div></div>
<div class="kv"><div class="k">外資</div><div class="v">14/20 天買超 3,995 張;配息率長年 50%+</div></div>
</div></div></div>"""

A2_4 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>法說|雙賽道時間表</h2></div>
<div class="head1" style="font-size:28px">把五年路線圖攤開來對帳</div>
<table><tr><th>年份</th><th>AI 伺服器線</th><th>機器人線</th></tr>
<tr><td>2025</td><td>切入 AI 伺服器零組件市場</td><td>取得 AFM 技術;投資機器人品牌;取得減速器關鍵技術;切入 AGV</td></tr>
<tr><td><b>2026</b></td><td class="hl">馬來西亞廠開始量產 AI 伺服器</td><td>送樣試產 AGV 與人形機器人線束;Magnax 併購交割;常州工廠建設</td></tr>
<tr><td>2027</td><td>整合上下游形成生態系</td><td class="hl">AFM 產品開始貢獻營收</td></tr>
<tr><td>2028</td><td>關鍵模組營收顯著成長</td><td>AFM 開始貢獻獲利</td></tr>
<tr><td>2029-30</td><td>開拓全球 AI 運算中心在地化;進軍整機</td><td>目標供應機器人成本結構 25~50% 零組件;數據資產化</td></tr></table>
<div class="card"><h4>為什麼是馬來西亞?</h4>東南亞是 AI 資料中心新熱區,供應鏈重整給全球化產能布局者機會;廣宇是鴻海集團內唯一在馬來西亞有產能的公司——集團分工下的地利,「就近服務」是真實的物流與關稅優勢。</div>
<div class="card"><h4>為什麼是 AFM?</h4>軸向磁通電機:高功率密度+商業化可行性,縮短機器人開發時程;高毛利屬性,對 8% 毛利的廣宇是結構性升級。來源是併購(Magnax)而非自研——速度買來的,整合是考題。</div>
<div class="card"><h4>股東底線</h4>現金股利配發率長年維持 50%+,「新業務以獲利與現金流自主為首要考量」——轉型不靠增資稀釋,這句要盯住。</div></div>"""

A3_4 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|虧損的解剖</h2></div>
<div class="head1" style="font-size:28px">本業在流血 月營收先回溫</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">57.33</td><td class="num">12.41%</td><td class="num">6.15%</td><td class="num">0.46</td></tr>
<tr><td>3Q25</td><td class="num">53.71</td><td class="num">12.84%</td><td class="num">5.40%</td><td class="num">0.34</td></tr>
<tr><td>4Q25</td><td class="num">49.52</td><td class="num">12.48%</td><td class="num">4.05%</td><td class="num">0.34</td></tr>
<tr><td>1Q26</td><td class="num hl">42.52</td><td class="num hl">7.79%</td><td class="num hl">-0.34%</td><td class="num hl">-0.16</td></tr>
<tr><td>2Q26</td><td class="num">53.81</td><td class="num hl">8.55%</td><td class="num hl">0.27%</td><td class="num hl">-0.08</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">17.0</td><td class="num">+1.0%</td></tr>
<tr><td>2026/06</td><td class="num">19.6</td><td class="num">-0.7%</td></tr>
<tr><td>2026/07</td><td class="num">20.5</td><td class="num gd">+16.4%</td></tr>
<tr><td>2026/08</td><td class="num">21.7</td><td class="num gd">+19.7%</td></tr></table>
<p>毛利率 12%→8% 的四個百分點,是車用/工控衰退+新事業前期成本的疊加。虧損幅度在收斂(-0.16→-0.08),7、8 月營收轉正雙位數——若馬來西亞 AI 伺服器 2H26 如期認列,轉盈的路徑存在;若遞延,虧損股沒有估值地板。<b>這檔的下檔保護只有一個:帳上還在配息的現金流紀律。</b></p></div>"""

CHIP_4 = chip_sect(
    """<tr><td>低檔未發動</td><td>距年高 ≤ -10%</td><td class="num gd">-22.9%(系列最深)</td></tr>
<tr><td>整理區間</td><td>40日箱體 ≤ 25%</td><td class="num gd">16.1%(20日 8.6%)</td></tr>
<tr><td>外資連吃</td><td>20日買超 ≥ 12天</td><td class="num gd">14天,+3,995張</td></tr>
<tr><td>未出量</td><td>近15日無 2.3×均量</td><td class="num gd">通過</td></tr>""",
    "12.6%", "在連兩季虧損的股票上連吃 14 天——外資買的是 2H26 馬來西亞量產,不是財報")

A5_4 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">風險最高的一檔 檢核也最嚴</div>
<div class="card"><h4>追蹤清單(全部可證偽)</h4>①3Q26 轉盈與否——馬來西亞 AI 伺服器認列的直接證據 ②毛利率回 10%+ ③AI+Robotics 占比從 1% 爬到幾 % ④AFM 常州工廠進度與首張外部訂單 ⑤月營收 YoY 維持雙位數 ⑥配息率守住 50%(現金流紀律沒破)</div>
<div class="card"><h4>反方劇本</h4>①馬來西亞量產遞延→虧損延長,虧損股無估值地板 ②AI 伺服器「組裝」毛利未必高於本業,量產≠獲利 ③AFM 整合失敗(併購技術的老風險) ④鴻海集團訂單分配不由廣宇決定——命運他定 ⑤2030 路線圖太遠,五年期支票市場不見得買單</div>
<p><b>本報判準</b>:五檔中唯一「基本面還沒好轉」的——純粹的預期交易。倉位紀律要用興櫃標準對待:小倉、先寫出場、只跟不追。驗證點近在眼前:10/10 九月營收、11 月 Q3 財報,兩關都過才有資格加碼。</p></div>"""

QA_4 = qa([
    ("廣宇 1H26 賺還是虧?", "虧:1Q -0.16、2Q -0.08,連兩季虧損。"),
    ("法說選定的「下一賽道」是什麼?", "AI + Robotics 雙賽道。"),
    ("廣宇在鴻海集團的獨特地位?", "集團唯一馬來西亞產能——就近吃東南亞 AI 伺服器需求。"),
    ("馬來西亞廠量產 AI 伺服器的時間表?", "2026 年(法說路線圖)。"),
    ("AFM 是什麼?怎麼來的?", "軸向磁通電機,併購比利時 Magnax 取得;高功率密度、高毛利。"),
    ("AFM 何時貢獻營收/獲利?", "2027 營收、2028 獲利(法說時間表)。"),
    ("2030 年機器人業務目標?", "供應機器人整體成本結構 25~50% 的零組件。"),
    ("AI+Robotics 現在占營收多少?", "約 1%,但年增 +1,277%。"),
    ("這檔的下檔保護是什麼?", "幾乎只有配息紀律(50%+)——虧損股沒有估值地板。"),
    ("最近的兩個驗證點?", "10/10 九月營收、11 月 Q3 財報(轉盈與否)。"),
])

# ═══════════════════ 第五期:大亞 1609 ═══════════════════
T5 = """<b>大亞 1609</b> <span class="num">38.75</span>|距年高 <span class="num">-18.1%</span>
|外資20日買超 <span class="up">13天</span>|吸籌比 <span class="num">9.7%</span>
|1H26 EPS <span class="up">2.24(+90%)</span>|2Q26毛利率 <span class="num">18.72%(五年高)</span>|8月營收 <span class="up">+34.8%</span>"""

A1_5 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">素材:2026/08/26 法說</span></div>
<div class="head1">法說裡沒有 AI 兩個字 獲利照樣翻九成</div>
<div class="deck">電力線纜占七成、毛利率衝上五年新高、儲能 175MW 商轉、8 月營收 +34.8%——大亞是本系列唯一「不講 AI 故事」的,而這正是它的可貴之處。</div>
<div class="byline">本報整理|素材:大亞 2026/08/26 法人說明會、月營收公告</div>
<div class="cols2"><div>
<p class="dropcap">本系統的法說詞頻掃描在大亞只抓到「電網×4、電纜×6」,AI 相關字眼掛零。但數字自己會講話:1H26 營收 177.6 億(+17.2%)、毛利淨額 +49.7%、稅後淨利 <span class="hl">+89.6%</span>、EPS 2.24(去年同期 1.18);2Q26 毛利率 <span class="hl">18.72%</span>,比 2022 年的 8.13% 翻了一倍多,創五年新高。</p>
<p>成長來源很樸素:電力線纜(工程)占銷量 72%,台電強韌電網的配電端——汰換老舊架空線 3,087 公里、高壓電纜 802 公里——全是電纜的直接需求。1955 年成立的 70 年老廠,此刻正站在配電升級的主航道上。</p>
<p>第二引擎是能源事業:太陽能 70 座電廠 207MW;儲能端<b>智璞 100MW E-dReg(25/9 啟用)+大蓄 75MW(26/8/24 剛啟用)</b>,加計小案合計約 178MW 商轉,短期目標 200MW,還有 17 位台電電力交易平台合格交易員。2026Q2 智璞單季儲能收入 2.23 億,開始有感。</p>
<p>8 月營收 +34.8% 是本系列最高的單月增速——而股價距年高還有 -18%。銅價是把雙面刃:漲價推升營收與庫存利得,也可能在回落時反噬,這是讀大亞財報必須帶著的濾鏡。</p>
</div><div class="sidebar"><h3>三十秒看懂大亞</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">電力電纜 70%、漆包線 13%、裸銅線 10%+太陽能/儲能 6%</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">台電配電升級(汰換 3,087 公里架空線+802 公里高壓電纜)</div></div>
<div class="kv"><div class="k">第二引擎</div><div class="v">儲能 175MW E-dReg 商轉(智璞100+大蓄75),目標 200MW</div></div>
<div class="kv"><div class="k">獲利</div><div class="v">1H26 EPS 2.24(+90%),毛利率 18.72% 五年高</div></div>
<div class="kv"><div class="k">股價位置</div><div class="v">38.75 元,距年高 -18.1%,40 日箱體 13.7%</div></div>
<div class="kv"><div class="k">外資</div><div class="v">13/20 天買超 5,498 張,吸籌比 9.7%</div></div>
</div></div></div>"""

A2_5 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>法說|完整能源鏈盤點</h2></div>
<div class="head1" style="font-size:28px">產生、傳輸、轉換、儲存、管理 五環都有子公司</div>
<table><tr><th>環節</th><th>誰在做</th><th>進度(法說)</th></tr>
<tr><td>產生(太陽能)</td><td>大亞綠能/志光/心忠/博斯等</td><td>70 座電廠 207MW;七股 120MW 漁電共生;2026Q2 集團電業收入 10.2 億</td></tr>
<tr><td>傳輸(電纜)</td><td>大亞本業</td><td>銷量 72% 是電力線纜;1H26 銷量 29,026 噸</td></tr>
<tr><td>儲存(儲能)</td><td>大亞儲能/智璞/大蓄</td><td class="hl">智璞 100MW E-dReg 25/9 啟用;大蓄 75MW 26/8/24 啟用;目標累計 200MW</td></tr>
<tr><td>管理(售電/交易)</td><td>博曜售電/協同能源</td><td>17 位台電電力交易平台合格交易員,2022/5 即加入平台</td></tr></table>
<div class="card"><h4>E-dReg 是什麼?</h4>電能移轉複合動態調節備轉:儲能系統自動追隨電網頻率充放電+配合台電排程——再生能源占比越高,電網越需要這種「穩頻服務」,收入模式是賣服務給台電,不看電價臉色。</div>
<div class="card"><h4>光儲標案雙中</h4>志光能源:全國最大光儲合一(35MW 光電+23.3MW 儲能,24/6 商轉);心忠電業:11.97MW+7.98MW,2027 上線——標案能力已被驗證兩次。</div></div>"""

A3_5 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|毛利率翻倍之路</h2></div>
<div class="head1" style="font-size:28px">從 8% 到 18.7% 四年結構改善</div>
<table><tr><th>年度</th><th>毛利率</th><th>EPS</th></tr>
<tr><td>2022</td><td class="num">8.13%</td><td class="num">1.23</td></tr>
<tr><td>2023</td><td class="num">13.15%</td><td class="num">3.72</td></tr>
<tr><td>2024</td><td class="num">13.67%</td><td class="num">2.06</td></tr>
<tr><td>2025</td><td class="num">13.98%</td><td class="num">1.65</td></tr>
<tr><td><b>2026Q2</b></td><td class="num gd">18.72%</td><td class="num gd">1H 2.24(+90%)</td></tr></table>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>1Q26</td><td class="num">83.41</td><td class="num">18.85%</td><td class="num">14.08%</td><td class="num">0.66</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">94.23</td><td class="num">18.54%</td><td class="num">11.94%</td><td class="num gd">1.58</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/05</td><td class="num">31.4</td><td class="num">+22.0%</td></tr>
<tr><td>2026/06</td><td class="num">33.7</td><td class="num">+22.7%</td></tr>
<tr><td>2026/07</td><td class="num">29.1</td><td class="num">+11.5%</td></tr>
<tr><td>2026/08</td><td class="num">33.9</td><td class="num gd">+34.8%</td></tr></table>
<p>兩個註腳:①2Q26 EPS 1.58 含業外 0.78 億(處分與評價),本業營益率 11.94% 仍是高檔 ②每股營運現金流 2025 年 -0.60、2024 -1.61——電纜業銅料庫存吃現金是常態,搭配 21.8 元每股淨值與 0.7 元現金股利一起看,不是警報但要知道。</p></div>"""

CHIP_5 = chip_sect(
    """<tr><td>低檔未發動</td><td>距年高 ≤ -10%</td><td class="num gd">-18.1%</td></tr>
<tr><td>整理區間</td><td>40日箱體 ≤ 25%</td><td class="num gd">13.7%(20日 6.3%)</td></tr>
<tr><td>外資連吃</td><td>20日買超 ≥ 12天</td><td class="num gd">13天,+5,498張</td></tr>
<tr><td>未出量</td><td>近15日無 2.3×均量</td><td class="num gd">通過</td></tr>""",
    "9.7%", "與中興電同屬電網鏈:重電(變電)+電纜(配電)兩段被同步吸籌——族群訊號大於個股訊號")

A5_5 = """<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">不性感 但可以對帳</div>
<div class="card"><h4>追蹤清單</h4>①9 月營收是否站穩 30 億+/YoY 20%+ ②毛利率守 17%+(銅價回落測試) ③大蓄 75MW 滿季貢獻(3Q26 儲能收入環比) ④200MW 儲能目標達成時點 ⑤台電配電標案的新得標公告</div>
<div class="card"><h4>反方劇本</h4>①銅價回落→營收減速+庫存跌價雙殺(電纜業週期宿命) ②儲能電力交易價格競爭,E-dReg 服務費率逐年走低 ③營運現金流連兩年為負,若配息縮水市場會重新定價 ④法說無 AI 敘事=資金熱度天花板比中興電低</div>
<p><b>本報判準</b>:與中興電是同一條國策的上下游——變電站用 GIS,配電網用電纜。兩檔同時被外資吸籌,把它當「電網鏈組合」看:中興電是訂單能見度,大亞是毛利率斜率。族群同步訊號,比單檔訊號可信。</p></div>"""

QA_5 = qa([
    ("大亞法說詞頻掃描抓到 AI 幾次?", "零次——它是純電網/能源故事,本報照實標註。"),
    ("1H26 稅後淨利年增多少?", "+89.6%,EPS 2.24(去年同期 1.18)。"),
    ("2Q26 毛利率多少?有何意義?", "18.72%,五年新高,是 2022 年 8.13% 的兩倍多。"),
    ("銷量占比最大的產品?", "電力線纜(工程),占 72%。"),
    ("台電配電升級跟電纜的直接關係?", "汰換老舊架空被覆線 3,087 公里+高壓電纜 802 公里。"),
    ("儲能兩大案場?", "智璞 100MW(25/9 啟用)+大蓄 75MW(26/8/24 啟用),皆 E-dReg。"),
    ("E-dReg 賺的是什麼錢?", "幫台電穩頻的服務費:追隨頻率充放電+配合排程。"),
    ("8 月營收年增多少?", "+34.8%,本系列五檔中最高單月增速。"),
    ("讀大亞財報必備的濾鏡是什麼?", "銅價:漲時推營收與庫存利得,跌時雙殺。"),
    ("它和中興電該怎麼一起看?", "同一條電網國策的上下游:變電 GIS+配電電纜,族群同步吸籌訊號更可信。"),
])

# ═══════════════════ 組版輸出 ═══════════════════
NAV = ["頭版", "法說", "財報", "籌碼", "追蹤", "測驗"]
ISSUES = [
    ("1513", "中興電 1513", "中興電專刊:電網大牛市裡還在盤整的市佔王 ·「還沒發動」系列 No.1 · 2026/10/01",
     T1, A1_1 + A2_1 + A3_1 + CHIP_1 + A5_1 + QA_1),
    ("2354", "鴻準 2354", "鴻準專刊:外資默吃三萬張,賭遊戲機回來了 ·「還沒發動」系列 No.2 · 2026/10/01",
     T2, A1_2 + A2_2 + A3_2 + CHIP_2 + A5_2 + QA_2),
    ("4766", "南寶 4766", "南寶專刊:鞋膠王的半導體滲透已小量出貨 ·「還沒發動」系列 No.3 · 2026/10/01",
     T3, A1_3 + A2_3 + A3_3 + CHIP_3 + A5_3 + QA_3),
    ("2328", "廣宇 2328", "廣宇專刊:虧損中的 AI+Robotics 轉型賭局 ·「還沒發動」系列 No.4 · 2026/10/01",
     T4, A1_4 + A2_4 + A3_4 + CHIP_4 + A5_4 + QA_4),
    ("1609", "大亞 1609", "大亞專刊:法說沒有 AI,獲利照樣翻九成 ·「還沒發動」系列 No.5 · 2026/10/01",
     T5, A1_5 + A2_5 + A3_5 + CHIP_5 + A5_5 + QA_5),
]

if __name__ == "__main__":
    for code, stamp, sub, ticker, body in ISSUES:
        html = shell(masthead="TW·財經報", stamp=stamp, subtitle=sub,
                     nav=NAV, ticker_html=ticker, body_html=body, footer=FOOT)
        print("saved:", save_issue(code, DATE, html))

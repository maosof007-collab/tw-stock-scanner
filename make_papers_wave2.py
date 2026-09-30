# -*- coding: utf-8 -*-
"""財經報第二波:CPO/TGV/ASIC 族群特刊 + AMAX-KY 號外(動能即時取數)。"""
from newspaper import shell, save_issue
import supply_chain as sc


def sect(i, tag, title, inner, src=""):
    s = f'<span class="src">{src}</span>' if src else ""
    return (f'<div class="sect" id="{i}"><div class="slabel"><span class="tag">{tag}</span>'
            f'<h2>{title}</h2>{s}</div>{inner}</div>')


def quiz(qa):
    return "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                   for i, (q, a) in enumerate(qa))


def mom_rows(items):
    """[(code,name,note)] → 表列(20日動能即時)。"""
    out = []
    for c, n, note in items:
        m = sc._mom(c)
        cls = "up" if (m or 0) >= 5 else ("gd" if (m or 0) <= -5 else "")
        mt = f"{m:+.1f}%" if m is not None else "—(興櫃)"
        out.append(f'<tr><td>{n} {c}</td><td class="num {cls}">{mt}</td><td>{note}</td></tr>')
    return "".join(out)


NAV6 = ["頭版", "全鏈名單", "興櫃亮點", "法說攤位", "追蹤", "測驗"]
FOOT = "素材:各公司法說(自動管線)/系統動能/公開報導·研究筆記非投資建議 · TW-BACKTEST 財經報"

# ═════════ CPO 族群特刊(含興櫃四傑) ═════════
T = """<b>CPO 族群特刊</b>|光引擎→耦光設備→檢測→封裝→連接 <span class="up">全鏈點名</span>
|興櫃四傑:高明鐵 <span class="num">693</span>·東佑達 <span class="num">620</span>·連訊 <span class="num">358</span>·瑞峰 <span class="num">160</span>"""
A1 = """<div class="head1">CPO 不只光模組 一條鏈五個站的完整地圖</div>
<div class="deck">市場盯著光引擎,錢已經流向設備、檢測、封裝與連接——而最陡的幾根曲線,藏在興櫃。</div>
<div class="cols2"><div>
<p class="dropcap">共同封裝光學(CPO)把光引擎搬到晶片旁邊,整條供應鏈因此重排:光引擎要「耦光」(奈米級對位)、玻璃基板要驗孔、晶片要新封裝、機櫃間still要跳接線。每一站都是一群公司。</p>
<p>本刊把五個站一次點名,並特別把<b>興櫃四傑</b>攤開——高明鐵(耦光設備,股價從 11 元到 693)、東佑達(六軸對位第二路線)、連訊(光纖連接/跳接線,上櫃申請中)、瑞峰(CPO 封裝,Fabrinet 入股 14%)。興櫃=無漲跌幅+低流動性,按家規<b>單檔上限 2.5%、只用閒錢</b>。</p>
</div><div class="sidebar"><h3>五站地圖</h3>
<div class="kv"><div class="k">①光引擎/模組</div><div class="v">上詮/波若威/華星光/聯鈞/光聖/眾達/前鼎/光環+鍍膜統新</div></div>
<div class="kv"><div class="k">②耦光/對位設備</div><div class="v">高明鐵/東佑達/直得/上銀</div></div>
<div class="kv"><div class="k">③檢測</div><div class="v">蔚華科(玻璃耦合器量測,見TGV刊)</div></div>
<div class="kv"><div class="k">④封裝</div><div class="v">瑞峰(WLP/SiPh)</div></div>
<div class="kv"><div class="k">⑤連接</div><div class="v">連訊(跳接線/連接器)</div></div></div></div>"""
A2 = ('<table><tr><th>公司</th><th>20日動能</th><th>定位</th></tr>'
      + mom_rows([("3363", "上詮", "光引擎/耦光封裝"), ("3163", "波若威", "光引擎"),
                  ("4979", "華星光", "光模組"), ("3450", "聯鈞", "光模組"),
                  ("6442", "光聖", "光模組/連接"), ("4977", "眾達-KY", "高速光收發"),
                  ("4908", "前鼎", "光模組"), ("3234", "光環", "VCSEL/光模組"),
                  ("6426", "統新", "光學鍍膜(微型股命題本尊)"),
                  ("1597", "直得", "線性滑軌(耦光設備對照)")])
      + "</table><p>光引擎端多數仍距 60 日高有距離(八月回檔坑未填)——族群輪動時,先看誰先站回。</p>")
A3 = """<table><tr><th>興櫃四傑</th><th>現價/動能</th><th>故事與查證點</th></tr>
<tr><td><b>高明鐵 4573</b></td><td class="num up">693|20日+15.5%/60日+73%</td><td>鐵工廠→CPO耦光設備;媒體:訂單能見度達明年Q2、啟動擴廠;<b>查證:六軸對位市占與單價</b></td></tr>
<tr><td><b>東佑達 7942</b></td><td class="num">620|興櫃新掛(7/31興櫃前法說)</td><td>2000年設立/8廠/500人/資本額3.17億/年營收20億+;與高明鐵「同拚六軸對位、兩條路線」;<b>查證:CPO營收占比</b></td></tr>
<tr><td><b>連訊 6820</b></td><td class="num up">358|20日+12%/60日+39%</td><td>連展子公司;跳接線/連接器/適配器,數據中心+FTTH+5G;<b>已申請上櫃</b>=轉板催化</td></tr>
<tr><td><b>瑞峰 7873</b></td><td class="num">160|20日+11%/60日-21%</td><td>8/28 法說標題自答:「比GPU更緊張的瓶頸——IVR與矽光子」;開發 3D TSV Reveal(SiPh)/Chip-on-Wafer(IVR);股東欣銓/漢民/<b>Fabrinet 14%</b></td></tr></table>
<div class="card" style="background:#fff7e8">⚠️ 興櫃家規:無漲跌幅、流動性差——單檔≤2.5%、只用閒錢、出場條件先寫死。</div>"""
A4 = """<table><tr><th>公司</th><th>最新法說</th><th>一句重點(自動管線抓回)</th></tr>
<tr><td>瑞峰 7873</td><td class="num">2026/08/28</td><td>IVR+矽光子雙軸;12吋 SiPh 線;280人</td></tr>
<tr><td>東佑達 7942</td><td class="num">2026/07/31</td><td>興櫃前法說:自動化傳動全品項,新產品佈局章節點名對位應用</td></tr>
<tr><td>高明鐵 4573</td><td class="num hl">2018/10(最後一場)</td><td>七年沒開法說=資訊真空,故事全靠媒體與月營收——風險也是機會</td></tr>
<tr><td>連訊 6820</td><td class="num">2021/03(興櫃時)</td><td>上櫃過程將被迫增加揭露=透明度催化</td></tr></table>"""
A5 = """<div class="card"><h4>追蹤清單</h4>①興櫃四傑每月10日營收(唯一硬數字) ②高明鐵/東佑達的 CPO 營收占比揭露 ③連訊上櫃審議進度 ④瑞峰康寧/DNP級客戶驗證 ⑤光引擎端誰先站回 60 日高(輪動訊號)</div>"""
QA = [("CPO 供應鏈五站是?", "光引擎/模組→耦光對位設備→檢測→封裝→連接。"),
      ("高明鐵的轉型故事?", "鐵工廠→CPO 耦光設備,股價 11→693;但七年沒開法說。"),
      ("東佑達與高明鐵的關係?", "同拚六軸對位、兩條技術路線的對手。"),
      ("瑞峰 8/28 法說的核心命題?", "比 GPU 更緊張的瓶頸:IVR 與矽光子。"),
      ("連訊的轉板催化是?", "已申請上櫃(連展子公司)。"),
      ("興櫃參與的家規?", "單檔≤2.5%、只用閒錢、出場條件先寫死。")]
body = (sect(0, "A1", "頭版", A1) + sect(1, "A2", "全鏈名單|動能點名", A2)
        + sect(2, "A3", "興櫃四傑", A3) + sect(3, "A4", "法說攤位", A4)
        + sect(4, "A5", "追蹤", A5) + sect(5, "A6", "讀者測驗", quiz(QA)))
save_issue("CPO", "20260930", shell("TW·財經報", "CPO 族群",
           "CPO 族群特刊:五站地圖與興櫃四傑 · 2026/09/30", NAV6, T, body, FOOT))
print("CPO done")

# ═════════ TGV 族群特刊 ═════════
T = """<b>TGV 玻璃基板族群</b>|做孔 vs 驗孔 <span class="up">全員起漲</span>
|蔚華科 <span class="up">+74%</span>·東捷 <span class="up">+46%</span>·雷科 <span class="up">+43%</span>·鈦昇 <span class="up">+24%</span>·群翊 <span class="num">+8%</span>(20日)"""
A1 = """<div class="head1">玻璃基板開打 做孔的五家廝殺 驗孔的只有一家</div>
<div class="deck">Intel 玻璃基板登場、台積電 CoPoS 排程浮現,2027 量產倒數——台鏈 11 家從鑽孔到檢測全面卡位,20 日動能全員亮紅。</div>
<div class="cols2"><div>
<p class="dropcap">TGV(玻璃通孔)是玻璃基板的心臟工序:雷射改質、蝕刻穿孔、金屬化,三步都可能做壞,而玻璃透明脆性,傳統檢測要嘛切開要嘛看不進去。</p>
<p>這造就了本刊反覆強調的結構:<b>製程端五家互為競爭(雷科/鈦昇/東捷/群翊/直得),檢測端蔚華科唯一</b>——賣鏟人打架,驗鏟人全收。九月下旬市場開始理解這件事:蔚華科 20 日 +74% 全族最強。</p>
<p>時程共識:2026 試產線拉良率、2027-28 量產。設備商是最早反映營收的一群——每一條試產線都要成孔+濕蝕刻+清洗+金屬化+壓合烘烤+<b>檢測</b>設備。</p>
</div><div class="sidebar"><h3>分工表</h3>
<div class="kv"><div class="k">雷射鑽切</div><div class="v">雷科 6207(CoWoS 檢測設備穩定出貨+TSV/TGV 雷射鑽切過驗證)</div></div>
<div class="kv"><div class="k">雷射加工</div><div class="v">鈦昇 8027</div></div>
<div class="kv"><div class="k">玻璃改質</div><div class="v">東捷 8064</div></div>
<div class="kv"><div class="k">塗佈壓合</div><div class="v">群翊 6664(ABF 設備能力延伸)</div></div>
<div class="kv"><div class="k">檢測(唯一)</div><div class="v">蔚華科 3055(三站品管)</div></div></div></div>"""
A2 = ('<table><tr><th>公司</th><th>20日動能</th><th>定位</th></tr>'
      + mom_rows([("3055", "蔚華科", "檢測唯一·SP8000G 梯隊(見個股刊)"),
                  ("8064", "東捷", "玻璃雷射改質"), ("6207", "雷科", "TGV/TSV 雷射鑽切,客戶驗證通過"),
                  ("8027", "鈦昇", "TGV 雷射加工"), ("6664", "群翊", "塗佈/壓合設備延伸玻璃基板"),
                  ("1597", "直得", "線性元件(外圍)")])
      + '</table><div class="card">🔎 <b>落後者觀察</b>:群翊 +8% 是全族唯一還沒噴的——接力法則的下一棒候選,先查它玻璃基板設備的實際接單再說。</div>')
A3 = """<div class="card"><h4>興櫃/延伸(與 CPO 刊交叉)</h4>瑞峰 7873:TGV 之外的玻璃應用——3D TSV Reveal(SiPh);蔚華科法說頁16 玻璃耦合器量測=TGV 與 CPO 兩條浪一個工具。</div>"""
A4 = """<table><tr><th>公司</th><th>最新法說</th><th>重點</th></tr>
<tr><td>蔚華科 3055</td><td class="num">2026/09/10</td><td>24頁全讀:三站檢測/四頭量產機/康寧DNP驗證/H1毛利31.77%</td></tr>
<tr><td>雷科 6207</td><td class="num">2025/12/23</td><td>年度法說(一年一場):CoWoS檢測設備穩定出貨+TGV雷射鑽切客戶驗證陸續通過</td></tr></table>"""
A5 = """<div class="card"><h4>追蹤清單</h4>①各家 TGV 設備「正式訂單」公告(vs 驗證中) ②群翊接單(落後者補漲判據) ③Intel/台積 CoPoS 時程新聞 ④蔚華科 SP7000G 量產機出貨 ⑤族群動能是否從設備擴散到材料(台玻/富喬)</div>"""
QA = [("TGV 三步製程?", "雷射改質→蝕刻穿孔→金屬化。"),
      ("做孔 vs 驗孔的結構?", "五家製程互打(雷科/鈦昇/東捷/群翊/直得),檢測唯一蔚華科。"),
      ("全族 20 日最強與最弱?", "蔚華科 +74% 最強;群翊 +8% 落後=下一棒候選。"),
      ("雷科的法說頻率暗示什麼?", "一年一場(12月)——追蹤靠月營收與公告,不靠法說。"),
      ("量產時程共識?", "2026 試產、2027-28 量產;設備商最早反映。"),
      ("與 CPO 的交叉點?", "玻璃耦合器/SiPh——蔚華科量測、瑞峰封裝。")]
body = (sect(0, "A1", "頭版", A1) + sect(1, "A2", "全鏈名單|動能點名", A2)
        + sect(2, "A3", "交叉與延伸", A3) + sect(3, "A4", "法說攤位", A4)
        + sect(4, "A5", "追蹤", A5) + sect(5, "A6", "讀者測驗", quiz(QA)))
save_issue("TGV", "20260930", shell("TW·財經報", "TGV 族群",
           "TGV 玻璃基板族群特刊:做孔與驗孔 · 2026/09/30", NAV6, T, body, FOOT))
print("TGV done")

# ═════════ ASIC 族群特刊 ═════════
T = """<b>ASIC 設計服務族群</b>|M31 <span class="up">+35%</span>·創意 <span class="up">+32%</span>·晶心科 <span class="up">+31%</span>·智原 <span class="up">+20%</span>·<b>世芯 <span class="num">-7.5%</span>(落後之謎)</b>(20日)"""
A1 = """<div class="head1">雲端自研晶片潮 全族大漲 獨留世芯在原地</div>
<div class="deck">FactSet 上修潮打到設計服務:創意目標價 5,688→6,288。但族群裡漲最兇的是 IP 股,而昔日一哥世芯 20 日 -7.5%——分歧本身就是資訊。</div>
<div class="cols2"><div>
<p class="dropcap">AI 巨頭自研晶片(客製 ASIC)要三種人:前段規格與 IP(M31/晶心科)、設計服務與後段(創意/世芯/智原)、以及把算力裝起來的人(見號外 AMAX-KY)。</p>
<p>這波的排序很說話:<b>IP 股(M31 +35%、晶心科 +31%)></b> 設計服務(創意 +32%、智原 +20%)<b>>世芯 -7.5%</b>。市場在定價「誰吃到新專案的斜率」——IP 是每案必抽,設計服務看客戶名單,而世芯的落後,市場語言是對其大客戶集中度(單一北美客戶)的疑慮。</p>
<p>證據面:9 月中 FactSet 對創意目標價 5,688→6,288(9/20 目標價表)、智原 20 日 +20% 且我們的權證榜曾見其湧入。</p>
</div><div class="sidebar"><h3>族群座標</h3>
<div class="kv"><div class="k">IP</div><div class="v">M31 6643·晶心科 6533(RISC-V)</div></div>
<div class="kv"><div class="k">設計服務</div><div class="v">創意 3443(台積系)·世芯 3661·智原 3035(聯電系)</div></div>
<div class="kv"><div class="k">算力整合</div><div class="v">AMAX-KY 6933(見號外)</div></div>
<div class="kv"><div class="k">分歧點</div><div class="v">世芯落後=客戶集中疑慮 vs 錯殺?</div></div></div></div>"""
A2 = ('<table><tr><th>公司</th><th>20日動能</th><th>定位</th></tr>'
      + mom_rows([("6643", "M31", "介面矽智財,每案必抽"), ("3443", "創意", "台積系設計服務,FactSet 6288"),
                  ("6533", "晶心科", "RISC-V IP"), ("3035", "智原", "聯電系設計服務(權證曾湧入)"),
                  ("3661", "世芯", "北美大客戶 ASIC——落後之謎"), ("2379", "瑞昱", "對照:標準IC")])
      + "</table>")
A3 = """<div class="card"><h4>世芯落後之謎——兩種讀法</h4><b>空方</b>:大客戶(北美單一雲端)下一代案能見度雜音,族群漲它不漲=聰明錢用腳投票。<b>多方</b>:估值消化後的錯殺,若客戶續案落地就是族群補漲王。<b>判準</b>:別猜,看月營收+法說口徑;它是族群裡「用最少倉位表達觀點」的期權型部位。</div>"""
A4 = """<table><tr><th>對答案點</th><th>看什麼</th></tr>
<tr><td>10/10 起月營收</td><td>IP 股遞延認列少、最誠實;世芯連兩月 YoY 轉正=多方讀法勝出</td></tr>
<tr><td>FactSet 上修潮</td><td>目標價雷達自動盯(創意 6288 之後誰接棒)</td></tr>
<tr><td>北美雲端資本支出</td><td>自研晶片預算=族群總水位</td></tr></table>"""
A5 = """<div class="card"><h4>追蹤清單</h4>①世芯月營收轉折 ②創意/智原新案公告 ③M31/晶心科授權金 vs 權利金結構變化 ④族群 vs 台積電動能背離(設計服務先行指標) ⑤AMAX-KY 液冷算力訂單(下游需求溫度計)</div>"""
QA = [("ASIC 族群三層分工?", "IP(M31/晶心科)→設計服務(創意/世芯/智原)→算力整合(AMAX-KY)。"),
      ("這波 20 日動能排序?", "M31 +35% > 創意 +32% > 晶心科 +31% > 智原 +20% > 世芯 -7.5%。"),
      ("世芯落後的兩種讀法?", "客戶集中疑慮 vs 錯殺;判準=月營收連兩月轉正。"),
      ("FactSet 最新對創意的目標價?", "5,688→6,288(9月中上修)。"),
      ("IP 股為何領漲?", "每案必抽、認列乾淨,是自研晶片潮的純度標的。"),
      ("族群的先行指標?", "設計服務動能常領先台積電資本支出敘事。")]
body = (sect(0, "A1", "頭版", A1) + sect(1, "A2", "全族名單|動能點名", A2)
        + sect(2, "A3", "爭點|世芯之謎", A3) + sect(3, "A4", "對答案", A4)
        + sect(4, "A5", "追蹤", A5) + sect(5, "A6", "讀者測驗", quiz(QA)))
save_issue("ASIC", "20260930", shell("TW·財經報", "ASIC 族群",
           "ASIC 設計服務族群特刊:全漲獨缺世芯 · 2026/09/30", NAV6, T, body, FOOT))
print("ASIC done")

# ═════════ AMAX-KY 號外 ═════════
NAV4 = ["頭版", "財報", "籌碼家規", "測驗"]
T = """<b>AMAX-KY 6933</b> <span class="num">371</span>|20日 <span class="up">▲29.7%</span>|60日 <span class="up">▲144%</span>|距年高 -3.6%
|前8月營收 <span class="num">72億</span>>2025全年|Q2毛利率 <span class="num">21.95%</span>(+8.25pp)"""
A1 = """<div class="head1">號外|從賣伺服器到賣算力 AMAX 的第二次出生</div>
<div class="deck">9/17 法說把定位講明:「從單一伺服器、機櫃,走向高價值、大規模、更長生命週期的工程專案」——液冷 AI 基建+矽谷 HostMax 算力中心,毛利率一季跳 8 個百分點。</div>
<div class="cols2"><div>
<p class="dropcap">艾瑪斯科技(AMAX-KY)是美商台掛的 AI 伺服器/液冷整櫃整合商,工程服務貫穿架構設計、NPI 與量產、整櫃驗證(9/17 法說原文)。</p>
<p>數字的陡峭度:前 8 月營收 <span class="hl">72 億,已超越 2025 全年 69 億</span>;Q2 毛利率從 13.68% 跳到 <span class="hl">21.95%</span>(高附加價值液冷方案占比拉高);前 7 月獲利 4.8 億,<b>較 2025 全年 +177%</b>。第二曲線:矽谷首座液冷 AI 資料中心 HostMax 開幕——從賣設備走向<b>算力服務的經常性收入</b>。</p>
</div><div class="sidebar"><h3>三十秒看懂</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">AI 伺服器/液冷整櫃整合→算力服務(HostMax)</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">液冷滲透+算力租賃缺口;美洲據點=地緣紅利</div></div>
<div class="kv"><div class="k">轉折</div><div class="v">毛利率 13.68→21.95%;獲利+177%</div></div>
<div class="kv"><div class="k">爭議</div><div class="v">整合商毛利天花板 vs 算力服務重估</div></div></div></div>"""
A2 = """<table><tr><th>指標</th><th>數值</th></tr>
<tr><td>前8月營收</td><td class="num">72 億(>2025 全年 69 億)</td></tr>
<tr><td>H1 營收</td><td class="num">44.87 億</td></tr>
<tr><td>Q2 毛利率</td><td class="num gd">21.95%(Q1 13.68%)</td></tr>
<tr><td>前7月獲利</td><td class="num gd">4.8 億(+177% vs 2025 全年)</td></tr></table>
<p>爭點:市場給整合商的本益比天花板低;若 HostMax 算力服務占比放大,評價體系會換軌(設備→服務)。9/17 法說的「更長生命週期工程專案」就是在講這件事。</p>"""
A3 = """<p>座標:收 371,60 日 +144%,距年高 -3.6%。體檢卡 🟡1紅2黃(爆量窗+振幅 7.5% 倉位打折)。</p>
<div class="card"><h4>家規裁決</h4>爆量窗內不追;回測站穩(340-350 帶)半倉再打折;停損 -1.5ATR(約 -28 元)。追蹤:①月營收月月>9 億? ②HostMax 稼動/擴點 ③毛利率 20%+ 守線。</div>"""
QA = [("AMAX 9/17 法說的定位宣言?", "從單一伺服器/機櫃走向高價值、長生命週期的工程專案。"),
      ("前 8 月營收的里程碑?", "72 億,已超越 2025 全年 69 億。"),
      ("Q2 毛利率跳升幅度與原因?", "13.68→21.95%(+8.25pp),液冷高附加價值占比拉高。"),
      ("第二曲線是什麼?", "矽谷 HostMax 液冷 AI 資料中心——算力服務經常性收入。"),
      ("家規給的參與條件?", "爆量窗不追;回測 340-350 站穩、半倉再打折、停損約 -28 元。")]
body = (sect(0, "A1", "頭版", A1, "素材:9/17法說(管線自動抓)") + sect(1, "A2", "財報與爭點", A2)
        + sect(2, "A3", "籌碼與家規", A3) + sect(3, "A4", "讀者測驗", quiz(QA)))
save_issue("6933", "20260930", shell("TW·財經報", "AMAX-KY 號外",
           "AMAX-KY(6933)號外:從賣伺服器到賣算力 · 2026/09/30", NAV4, T, body, FOOT))
print("6933 done")
print("WAVE2 ALL DONE")

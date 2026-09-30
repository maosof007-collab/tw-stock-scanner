# -*- coding: utf-8 -*-
"""領先者看板總刊:七大族群領跑者同台(誰在吸錢,一頁看完)。"""
from newspaper import shell, save_issue


def sect(i, tag, title, inner, src=""):
    s = f'<span class="src">{src}</span>' if src else ""
    return (f'<div class="sect" id="{i}"><div class="slabel"><span class="tag">{tag}</span>'
            f'<h2>{title}</h2>{s}</div>{inner}</div>')


def quiz(qa):
    return "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                   for i, (q, a) in enumerate(qa))


T = """<b>領先者看板</b>|大甲 <span class="up">+160%</span>·蔚華科 <span class="up">+74%</span>·M31 <span class="up">+35%</span>
·騰輝 <span class="up">+34%</span>·統新 <span class="up">+32%</span>·AMAX <span class="up">+30%</span>·貿聯 <span class="up">+20%</span>(20日)"""

A1 = """<div class="head1">七族領跑者同台 錢正在往哪裡集中</div>
<div class="deck">把每個族群跑最快的那一檔放在同一張桌上,答案自己浮出來:管件、TGV、ASIC 在吸錢;光引擎——整族只剩統新一檔是正的。</div>
<div class="byline">本報整理|20 日動能,2026/09/30 收盤;個股詳情各見其專刊</div>
<table><tr><th>族群</th><th>領跑者</th><th>20日</th><th>為什麼是它</th><th>族內落後王</th></tr>
<tr><td>不鏽鋼管件</td><td><b>大甲 2221</b></td><td class="num up">+160%</td><td>EP/BA 純度題材本尊</td><td>允強 +21%</td></tr>
<tr><td>TGV 玻璃基板</td><td><b>蔚華科 3055</b></td><td class="num up">+74%</td><td>驗孔唯一+首批出貨</td><td class="hl">群翊 +8%</td></tr>
<tr><td>ASIC 設計服務</td><td><b>M31 6643</b></td><td class="num up">+35%</td><td>IP 每案必抽,純度最高</td><td class="hl">世芯 -8%</td></tr>
<tr><td>特規 CCL</td><td><b>騰輝 6672</b></td><td class="num up">+34%</td><td>供給側出清+軍工 80%</td><td class="hl">雙鍵 -22%</td></tr>
<tr><td>CPO 光引擎</td><td><b>統新 6426</b></td><td class="num up">+32%</td><td>鍍膜稀缺+體檢曾零紅</td><td>聯鈞 -19%</td></tr>
<tr><td>算力/連接</td><td><b>AMAX-KY 6933</b></td><td class="num up">+30%</td><td>賣伺服器→賣算力</td><td>宏致 +23%</td></tr>
<tr><td>AI 線材</td><td><b>貿聯-KY 3665</b></td><td class="num up">+20%</td><td>線束組裝先行</td><td class="hl">萬泰科 -0%(本尊未動)</td></tr></table>"""

A2 = """<div class="head1" style="font-size:26px">看板的三個讀法</div>
<div class="card"><h4>讀法一|錢在「建廠實體」不在「光」</h4>領跑前四名(大甲/蔚華科/M31/騰輝)全是建廠鏈與自研晶片鏈;<b>CPO 光引擎九檔裡八檔是負的</b>——八月那波的坑還沒填。光通訊此刻是「故事在、錢不在」的狀態,錢去了玻璃基板(TGV)這個更早期的站。</div>
<div class="card"><h4>讀法二|每族的「純度王」就是領跑者</h4>大甲=純度題材本尊、蔚華科=唯一驗孔、M31=每案必抽的 IP、騰輝=軍工 80%——七個族群不約而同把冠軍給了<b>業務與題材疊度最高</b>的那檔。這正是彰源教案的法則在全市場同步上演。</div>
<div class="card"><h4>讀法三|落後王欄是下一棒名單,不是垃圾桶</h4>群翊(+8%,TGV 唯一沒噴)、萬泰科(-0%,鏈上下游都動了本尊沒動)、世芯(-8%,判準=月營收連兩月轉正)——每一個都配了檢核條件,寫在各自專刊裡。</div>"""

A3 = """<div class="head1" style="font-size:26px">下一棒候選(帶檢核,非買訊)</div>
<table><tr><th>候選</th><th>落後原因假設</th><th>進場檢核(寫死)</th></tr>
<tr><td>群翊 6664</td><td>ABF 設備延伸玻璃基板,市場尚未定價</td><td>TGV 設備「正式訂單」公告+站回 60 日高</td></tr>
<tr><td>萬泰科 6190</td><td>雙引擎故事新、佔比僅 12-15%</td><td>10/10 營收月均衝 9 億+(百億目標軌道)</td></tr>
<tr><td>世芯 3661</td><td>大客戶集中疑慮</td><td>月營收 YoY 連兩月轉正</td></tr>
<tr><td>雙鍵 4764</td><td>產能爬坡延後+溢價修正</td><td>月營收重回 300M+ 且站回 60 日線</td></tr>
<tr><td>光引擎全族</td><td>八月坑未填</td><td>誰先站回 60 日高誰當族群復活訊號</td></tr></table>
<div class="card" style="background:#fff7e8">⚠️ 家規總則:領跑者多在爆量窗內(大甲/蔚華科體檢 3 紅)——<b>看板是用來找下一棒的,不是用來追冠軍的。</b></div>"""

QA = [("七族領跑者中前四名的共同點?", "全是建廠鏈/自研晶片鏈(大甲/蔚華科/M31/騰輝)——錢在實體不在光。"),
      ("CPO 光引擎族群的現狀?", "九檔八負,只有統新 +32% 為正——故事在、錢不在。"),
      ("每族冠軍的共同特徵?", "純度/疊度最高:題材與業務重疊度決定漲幅(彰源法則全市場化)。"),
      ("看板的正確用法?", "找下一棒(落後王+檢核),不是追冠軍(多在爆量窗3紅)。"),
      ("三個帶檢核的下一棒?", "群翊(TGV訂單公告)/萬泰科(月營收9億+)/世芯(YoY連兩月轉正)。")]

body = (sect(0, "A1", "頭版|領先者看板", A1) + sect(1, "A2", "三個讀法", A2)
        + sect(2, "A3", "下一棒候選", A3) + sect(3, "A4", "讀者測驗", quiz(QA)))
p = save_issue("LEADERS", "20260930", shell(
    "TW·財經報", "領先者看板",
    "領先者看板總刊:七族領跑者同台 · 2026/09/30",
    ["領先者看板", "三個讀法", "下一棒", "測驗"], T, body,
    "個股細節各見專刊·研究筆記非投資建議 · TW-BACKTEST 財經報"))
print("saved:", p)

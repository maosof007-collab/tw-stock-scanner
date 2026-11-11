# -*- coding: utf-8 -*-
"""海報批量 v2(警示組):3287 廣寰科/4909 新復興——完整規格,估值卡=為何不估值。"""
from poster import shell, card, checks, bignums, flow, save_poster, ud

D = "2026/11/11"


def build(code, name, title_b, subtitle, brand, cols, src_note):
    html = shell(title_html=f"{name}<b>({code})</b>{title_b}", subtitle=subtitle,
                 brand=brand, cols=cols,
                 footer=f"素材:{src_note} · {D} · 本海報為研究筆記非投資建議")
    print("saved:", save_poster(code, "20261111", html))


# ════════════════ 3287 廣寰科(警示·完整規格)════════════════
c1 = card("現況判定:純籌碼局(警示)", checks([
    ("xx", f"11/11 漲停打開收黑 79.2(盤中高 88.6、收 {ud(-1.7,'-1.7%')})——一字板遊戲的出貨訊號"),
    ("xx", f"10 月營收 0.87 億 {ud(-16.4,'-16.4%')}:基本面零支撐,漲的全是籌碼"),
    ("xx", "「嘎空」不成立:融券餘額僅 311 張、券資比 12%,連半根漲停都推不動"),
    ("wn", f"真推手=主力/外資:外資 20 日 {ud(3680,'+3,680 張')}、大戶 {ud(8.2,'8週+8.2pp')} 鎖籌拉一字"),
    ("wn", "連續漲停+大振幅:注意/處置股機率高,分盤後流動性瞬間消失"),
]), src="2026-11-10/11 分析", extra_cls="grow")
c2 = card("基本面(沒有故事的那種)", bignums([
    ("10 月營收", "0.87 億", ud(-16.4, "年減 16.4%")),
    ("年區間", "26.9→88.6", ud(230, "漲 3.3 倍")),
]).replace("repeat(4,1fr)", "repeat(2,1fr)") + """
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/08</td><td class="n">0.86</td><td class="n up2">▲6%</td></tr>
<tr><td>2026/09</td><td class="n">1.18</td><td class="n up2">▲34%</td></tr>
<tr><td><b>2026/10</b></td><td class="n">0.87</td><td class="n dn2">▼16%</td></tr></table>
<div class="note">9 月 +34% 是單月跳動,10 月立刻打回——營收方向與股價方向完全脫鉤。</div>""")
c3 = card("營運結構(誠實版)", """
<table><tr><th>項目</th><th>現實</th></tr>
<tr><td>本業</td><td>電腦/影音週邊小型股(上櫃),月營收不足 1 億</td></tr>
<tr><td>市值</td><td>窄——單一主力即可控盤</td></tr>
<tr><td>掛的題材</td><td>隨市場輪動蹭(衛星/週邊),<b>無公告訂單、無占比、無法說佐證</b></td></tr></table>
<div class="note">⚠ 本卡沒有圓環圖,因為公司沒有揭露任何可畫的結構——這本身就是答案。</div>""")
c4 = card("這局怎麼玩的(教材)", flow([
    ("11/3〜11/6 外資掃貨約 2,100 張", "+476/+1,121/+269", True),
    ("量縮鎖一字(11/9 僅 940 張)", "浮額收走,沒人賣=天天漲停", False),
    ("11/11 開板爆出:高 88.6 收 79.2", "接最後一棒的人已套 11%", True),
]), extra_cls="grow")
c5 = card("籌碼體檢", f"""
<table><tr><th>指標</th><th>數字</th><th>判讀</th></tr>
<tr><td>外資20日</td><td class="n">{ud(3680,'+3,680 張')}</td><td>拉抬主力之一</td></tr>
<tr><td>融券餘額</td><td class="n">311 張</td><td>「嘎空」燃料根本不夠</td></tr>
<tr><td>融資20日</td><td class="n rd">{ud(429,'+429 張')}</td><td>散戶開始追=風險轉移中</td></tr>
<tr><td>大戶>400張</td><td class="n">66.8% {ud(8.2,'8週+8.2pp')}</td><td>高度集中=控盤局</td></tr>
<tr><td>投信</td><td class="n">0 張</td><td>機構零背書</td></tr></table>""")
c6 = card("股價檯階", """
<table><tr><th>價位</th><th>相對 79.2</th><th>意義</th></tr>
<tr><td>64.9 元</td><td class="n dn2">▼18.1%</td><td>MA20(跌破=局結束)</td></tr>
<tr class="yl"><td><b>88.6 元</b></td><td class="n up2">▲11.9%</td><td><b>11/11 天花板——收復不了就是頭</b></td></tr>
<tr><td>26.9 元</td><td class="n dn2">▼66%</td><td>年低(起漲點=主力成本帶的下界)</td></tr></table>""")
c7 = card("為何不給估值(刻意留白)", """
<table><tr><th>估值前提</th><th>本檔狀態</th></tr>
<tr><td>獲利可預測</td><td class="rd">✘ 月營收不足 1 億且年減</td></tr>
<tr><td>價格反映基本面</td><td class="rd">✘ 年低至今 3.3 倍,全是籌碼</td></tr>
<tr><td>流動性可依賴</td><td class="rd">✘ 一字板+處置風險,想跑跑不掉</td></tr></table>
<div class="note"><b>任何 PE/情境表放在這檔上都是裝飾品</b>——控盤局的「目標價」只存在主力的出貨計畫裡,不在報表裡。</div>""")
c8 = card("判準與教材價值", checks([
    ("xx", "家規三殺:營收年減禁入+爆量窗+疑似處置——觀察名單都不用進"),
    ("wn", "天品教案的反面:噴完才看到的標的,唯一正確動作是欣賞"),
    ("ok", "教材價值:記住「掃貨→量縮一字→開板爆量收黑」完整劇本,下次更早辨認"),
]), extra_cls="risk grow")
build("3287", "廣寰科", "籌碼警示總整理", "嘎空?不是——融券 311 張的主力控盤局,11/11 開板收黑=出貨進行式",
      "廣寰科技 KWORLD",
      [c1 + c3 + c5, c2 + c4 + c7, c6 + c8], "11/10〜11 盤勢分析+系統 11/11 數據")

# ════════════════ 4909 新復興(警示·完整規格)════════════════
c1 = card("現況判定:散場後的融資套牢池", checks([
    ("xx", f"營收連六個月年減(10 月 {ud(-6.1,'-6.1%')});月額僅 1,600〜2,000 萬"),
    ("xx", "距年高 -60%(74.5→30.0),站不回 MA20(34.2)"),
    ("xx", "融資餘額 3,364 張=<b>日均量的 5〜8 倍</b>,每次反彈都是解套賣壓"),
    ("xx", f"外資 20 日 {ud(-913,'-913 張')}、投信 0——「跌深反彈 vs 誤殺」兩題皆錯"),
]), src="2026-11-10 分析", extra_cls="grow")
c2 = card("基本面(持續惡化)", bignums([
    ("10 月營收", "0.18 億", ud(-6.1, "連六月年減")),
    ("距年高", "-60%", ud(-60, "74.5→30.0")),
]).replace("repeat(4,1fr)", "repeat(2,1fr)") + """
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/08</td><td class="n">0.16</td><td class="n dn2">▼44%</td></tr>
<tr><td>2026/09</td><td class="n">0.19</td><td class="n dn2">▼10%</td></tr>
<tr><td><b>2026/10</b></td><td class="n">0.18</td><td class="n dn2">▼6%</td></tr></table>""")
c3 = card("營運結構(誠實版)", """
<table><tr><th>項目</th><th>現實</th></tr>
<tr><td>本業</td><td>通信網路線纜小型股(上櫃)</td></tr>
<tr><td>營收規模</td><td>月額 1,600〜2,000 萬——市值窄、基本面無法支撐波動</td></tr>
<tr><td>曾掛的題材</td><td>上半年炒作至 74.5(26.4 起漲近 3 倍),逃命波後無人接</td></tr></table>
<div class="note">⚠ 無產品別揭露、無法說、無訂單公告——跟 3287 同款的「結構真空」。</div>""")
c4 = card("下跌結構(教材)", flow([
    ("10/21〜22 拉高出貨(爆 3,600 張量)", "35→40.8 成逃命波", True),
    ("一路 40→26.4 無支撐", "11/6 落底", False),
    ("反彈=融資解套賣壓(餘 3,364 張)", "11/6 單日砍 273 張是樣本", True),
]), extra_cls="grow")
c5 = card("籌碼體檢", f"""
<table><tr><th>指標</th><th>數字</th><th>判讀</th></tr>
<tr><td>外資20日</td><td class="n">{ud(-913,'-913 張')}</td><td>賣方</td></tr>
<tr><td>投信20日</td><td class="n">0 張</td><td>全程零參與</td></tr>
<tr><td>融資20日</td><td class="n">{ud(-484,'-484 張(餘 3,364)')}</td><td>套牢盤慢慢砍</td></tr>
<tr><td>融資/日均量</td><td class="n rd">5〜8 倍</td><td>全場最大的結構地雷</td></tr>
<tr><td>大戶>400張</td><td class="n">25.5% {ud(0.7,'+0.7pp')}</td><td>籌碼分散,無主力</td></tr></table>""")
c6 = card("股價檯階", """
<table><tr><th>價位</th><th>相對 30.0</th><th>意義</th></tr>
<tr><td>26.4 元</td><td class="n dn2">▼12.0%</td><td>年低(11/6)</td></tr>
<tr class="yl"><td><b>34.2 元</b></td><td class="n up2">▲14.0%</td><td>MA20——上面全是套牢賣壓</td></tr>
<tr><td>74.5 元</td><td class="n up2">▲148%</td><td>年高(炒作遺跡)</td></tr></table>""")
c7 = card("為何不給估值(刻意留白)", """
<table><tr><th>估值前提</th><th>本檔狀態</th></tr>
<tr><td>獲利可預測</td><td class="rd">✘ 營收連六月年減,無獲利基礎</td></tr>
<tr><td>籌碼結構健康</td><td class="rd">✘ 融資=日均量 5〜8 倍的套牢池</td></tr>
<tr><td>有人接手</td><td class="rd">✘ 外資賣方、投信零、大戶僅 25.5%</td></tr></table>
<div class="note"><b>殘值股的「便宜」不是估值,是流動性折價</b>——重新估值的前提寫在右下角的重看條件裡。</div>""")
c8 = card("判準與重看條件", checks([
    ("xx", "家規兩殺:營收年減禁入+融資結構紅燈——連觀察名單都不進"),
    ("wn", "跟著低價股題材跳動=殘值波動,不是轉機"),
    ("ok", "重看它的唯一條件:<b>營收連三月轉正+融資餘額腰斬</b>——兩者缺一不可"),
]), extra_cls="risk grow")
build("4909", "新復興", "籌碼警示總整理", "飆完崩掉的屍體在彈——融資是日均量 5〜8 倍,反彈全是解套賣壓",
      "新復興 SHIN",
      [c1 + c3 + c5, c2 + c4 + c7, c6 + c8], "11/10 盤勢分析+系統 11/11 數據")

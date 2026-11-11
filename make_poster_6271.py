# -*- coding: utf-8 -*-
"""海報:同欣電 6271 深度研究總整理(台玻1802版式)。"""
from poster import shell, card, checks, bignums, donut, bars, flow, save_poster

# ── 左欄 ──────────────────────────────────────────────
c_concl = card("投資結論(重點先看)", checks([
    ("ok", "獲利大改善:Q3 毛利率 <b>33.7%</b>(+6.5pp)、EPS <b>3.62</b>,營業淨利年增 <b>+89.6%</b>"),
    ("ok", "營收動能:月營收連四月 +22〜25%,10 月 <b>12.16 億(+25.1%)</b>小幅加速"),
    ("ok", "籌碼四綠:外資+投信同買、融資 -984 張、大戶 50.41% 緩步收"),
    ("ok", "11/10 漲停上榜「崩盤錯殺V轉」,量僅均量 1.48×=惜售非出貨"),
    ("wn", "名與身錯位:市場喊衛星(RF 僅 12%),本體是車用(應用別 60%)"),
    ("wn", "公司自估 Q4 成長力道較 Q3 <b>趨於平緩</b>(法說原話)"),
]), src="10/30 Q3 法說(核閱數)")

c_mix = card("營運結構(2026 Q3 產品別)",
    donut("產品<br>結構", [
        ("影像產品(車用CIS)", 53, "YoY +25%"),
        ("陶瓷電路板", 19, "YoY +26%"),
        ("Hybrids", 15, "YoY -6%"),
        ("RF 模組", 12, "YoY +54%"),
    ])
    + '<div class="note">應用別(前九月):<b>車用 60%</b>/工業 16%/通訊 12%/手機 8%/醫療 3%——'
      '它是車用半導體的 beta,衛星是加分題。</div>',
    src="簡報 p.12〜17")

c_cust = card("主要客戶與供應鏈位置", """
<table><tr><th>客戶(市場共識)</th><th>角色</th></tr>
<tr><td><b>onsemi 安森美</b></td><td>車用 CIS 龍頭、特斯拉主要供應商——同欣電經 2020 併購勝麗取得其封裝訂單</td></tr>
<tr><td>OmniVision 豪威</td><td>CIS 設計廠(市場報導口徑)</td></tr>
<tr><td>Sony</td><td>CIS 設計廠(市場報導口徑)</td></tr></table>"""
+ __import__("poster").flow([
    ("CIS 設計:onsemi/豪威/Sony", "晶片設計與晶圓", False),
    ("同欣電:CIS 封裝+陶瓷基板", "車用為主(應用別 60%)", True),
    ("Tier1 → 歐美日車廠/特斯拉", "ADAS 鏡頭數持續增加", False),
])
+ '<div class="note">⚠ 誠實標註:年報客戶<b>匿名</b>揭露——2024 前三大客戶合計 <b>56.81%</b>(集中度高);'
  '安森美等名單為市場報導共識,非公司具名。</div>', src="年報+市場報導")

c_chip = card("籌碼體檢(11/10)", """
<table><tr><th>指標</th><th>數字</th><th>判讀</th></tr>
<tr><td>外資20日</td><td class="n gn">+1,964 張</td><td>由賣轉買</td></tr>
<tr><td>投信20日</td><td class="n gn">+562 張</td><td>有機構背書</td></tr>
<tr><td>融資20日</td><td class="n gn">-984 張</td><td>槓桿退場,無踩踏燃料</td></tr>
<tr><td>大戶>400張</td><td class="n">50.41%(8週+1.3pp)</td><td>緩步收籌</td></tr>
<tr><td>隔日沖風險</td><td class="n">29%</td><td>中等,非飆股結構</td></tr></table>
<div class="note">對照組:麗臺=融資增+投信0+隔日沖⚠(注意力資金);同欣電=復甦資金,慢但回檔有人接。</div>""")

# ── 中欄 ──────────────────────────────────────────────
c_fin = card("最新財報(2026 第三季)",
    bignums([
        ("營收", "34.92 億", "年增 +22.5%"),
        ("毛利率", "33.7%", "去年同期 27.2%"),
        ("營業利益率", "20.7%", "去年同期 13.4%"),
        ("EPS", "3.62", "去年同期 2.28"),
    ])
    + bars([("毛利率 25Q3", 27.2, "#8fb7e8"), ("毛利率 26Q3", 33.7, "#2f6db5"),
            ("營益率 25Q3", 13.4, "#f3cf8e"), ("營益率 26Q3", 20.7, "#f0a63a")])
    + '<div class="note">前九月:營收 94.65 億(+8.5%)、EPS <b>8.00</b>(+48%);'
      '營收年增率從連六季負值→Q2 +6% → Q3 +23%,V 轉成立。</div>',
    src="核閱數,非自結")

c_catalyst = card("題材鏈流程(誠實版)", flow([
    ("陸廠三環:陶瓷封裝基座漲價 10〜15%", "11/1 生效(advisory 9/10 收錄)", True),
    ("同欣電 陶瓷電路板(占 19%)", "Q3 YoY 已加速至 +26%,Q4 起看漲價落地", False),
    ("RF 模組(占 12%)YoY +54%", "市場掛 AST/低軌衛星題材", False),
    ("AST 鏈有公告訂單的是 事欣科 4916", "同欣電=題材代理,無公告訂單——按 12% 占比計價", True),
]))

c_cash = card("現金流與投資(2026 前九月)", """
<table><tr><th>項目</th><th>金額</th></tr>
<tr><td>現金及約當現金</td><td class="n">43.70 億</td></tr>
<tr><td>EBITDA</td><td class="n gn">30.09 億(去年 24.32)</td></tr>
<tr><td>折舊費用</td><td class="n">8.35 億</td></tr>
<tr><td>資本支出</td><td class="n rd">5.99 億(去年 6.46,2022 高峰 35.4)</td></tr></table>
<div class="note"><b>重點解讀:</b>擴產高峰已過、獲利回升——低資本支出+EBITDA 放大=自由現金流最舒服的階段;
負債比僅 23.2%,股東權益 76.8%。</div>""", src="簡報 p.7〜8")

# ── 右欄 ──────────────────────────────────────────────
c_px = card("股價評估:211 是門,302 是山", """
<table><tr><th>價位</th><th>相對 203.5</th><th>判斷</th></tr>
<tr><td>185 元</td><td class="n rd">-9.1%</td><td>訊號日低點=停損線</td></tr>
<tr class="yl"><td><b>210.5〜211.4</b></td><td class="n">+3.5%</td><td><b>買區下緣+MA20:收盤站上=空方架構翻面</b></td></tr>
<tr><td>222.6 元</td><td class="n">+9.4%</td><td>買區上緣(20日高×0.92)</td></tr>
<tr><td>302 元</td><td class="n gn">+48.4%</td><td>年高(距高 -32.6% 的收復目標)</td></tr></table>
<div class="note">操作規格:不追漲停;等收盤站上 211 進突破單——倉位=總資金 1%÷停損距,線用 185 或 MA20 回破。</div>""")

c_scn = card("三種情境估值(2026 全年)", """
<table><tr><th>情境</th><th>Q4 假設</th><th>全年 EPS</th><th>本益比</th><th>推估股價</th></tr>
<tr><td style="background:#eaf3ff"><b>保守</b></td><td>趨緩至 3.0</td><td class="n">11.0</td><td class="n">15 倍</td><td class="n">165 元</td></tr>
<tr class="yl"><td><b>中性</b></td><td>持平 3.6</td><td class="n">11.6</td><td class="n">17.5 倍</td><td class="n">203 元(≈現價)</td></tr>
<tr><td style="background:#fff3e8"><b>樂觀</b></td><td>陶瓷+RF 加速 4.0</td><td class="n">12.0</td><td class="n">20 倍</td><td class="n rd">240 元</td></tr></table>
<div class="note">前三季 EPS 8.00 為既成事實;分歧只在 Q4——公司口徑「成長但趨緩」介於保守與中性之間。
現價=中性定價,<b>便宜要跌出來(165〜185),夢要訂單餵(AST 公告)</b>。</div>""")

c_risk = card("關鍵風險與觀察重點", checks([
    ("wn", "車用 60% 主幹:歐美車市任何轉弱直接打 53% 的影像事業"),
    ("wn", "Q4 力道趨緩(公司自己說的)——Q3 +23% 是今年斜率高點"),
    ("wn", "AST 無公告訂單:衛星溢價隨時可被市場收回"),
    ("wn", "Hybrids 連八季衰退,工業/醫療需求仍疲"),
    ("wn", "年區間 117〜302 的 beta:大盤二次探底時跌幅會放大"),
    ("ok", "觀察:12/10 的 11 月營收|每週五大戶% 守 50%|12〜1 月陶瓷漲價落地|AST 訂單公告"),
]), extra_cls="risk")

COLS = [c_concl + c_mix + c_chip,
        c_fin + c_cust + c_catalyst,
        c_px + c_scn + c_risk + c_cash]

html = shell(
    title_html="同欣電<b>(6271)</b>深度研究總整理",
    subtitle="車用 CIS 封裝為體、陶瓷漲價+RF 放量為翼,211 站上可期待、衛星題材需訂單支撐",
    brand="同欣電子 TONG HSING",
    cols=COLS,
    footer="素材:10/30 Q3 法說簡報(核閱數)+advisory 新聞紀錄+本系統資料管線 · 2026/11/11 · 本海報為研究筆記非投資建議")
p = save_poster("6271", "20261111", html)
print("saved:", p)

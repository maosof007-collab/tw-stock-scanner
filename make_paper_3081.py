# -*- coding: utf-8 -*-
"""
make_paper_3081.py — 聯亞光電 10/28 法說報告:兩年六倍的產能賭注
=================================================================
素材層級:法說(10/28 線上法說,經濟日報/豐雲轉述)>自家管線數字(月營收/季報/籌碼)。
核心:Q3 EPS 6.12 創高+毛利率 59%;追加 30 億 capex 綁美系大客戶長約,
2027 產能 2.5 倍、2028 再 2.5 倍(兩年約六倍)。估值在預付 2027-28。
"""
from newspaper import shell, save_issue

DATE = "20261029"

ticker = (
    '<span><b>Q3 營收</b> 15.62億 <span class="up">+183%</span></span>'
    '<span><b>毛利率</b> <span class="up">59%</span>(+15pp YoY)</span>'
    '<span><b>Q3 EPS</b> <span class="up">6.12</span> 創高</span>'
    '<span><b>前三季 EPS</b> 13.88(去年同期 2.36)</span>'
    '<span><b>Q4 指引</b> 季增約 +16%</span>'
    '<span><b>累積資本支出</b> 80億(追加30億)</span>'
)

body = """
<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版|法說重點</h2>
<span class="src">2026-10-28 線上法說</span></div>
<div class="head1">兩年六倍的產能賭注<br>聯亞把 80 億押在美系長約上</div>
<div class="deck">Q3 稅後 6.21 億年增 528%、EPS 6.12 創高;更重的訊息是資本支出:
一年砸 80 億、其中 30 億是為「美系大客戶長約」追加——法說同一晚,Marvell 傳購 Lumentum。</div>
<div class="byline">TW·財經報 編輯室|2026-10-29|素材:法說(轉述)+自家管線</div>
<div class="cols2"><div>
<p class="dropcap">聯亞三季報把成長曲線又拉陡了一格:單季營收 15.62 億,季增 28%、年增 183%;
毛利率 59%,比上季再高 2 個百分點、比去年同期高 15 個百分點;稅後純益 6.21 億,
季增 33%、<b>年增 528%</b>;EPS 6.12 元單季新高。前三季稅後 14.07 億、年增 491%,
EPS 13.88 元——去年同期只有 2.36 元。</p>
<p>但這場法說真正的頭條是供給面:過去一年累積資本支出已達 <b>80 億元</b>,其中
<b>30 億是臨時追加</b>,原因寫得很白——「與美系大客戶簽訂長期供貨合約」。產能規劃:
<b>2027 年為目前的 2.5 倍,2028 年再乘 2.5 倍</b>,兩年合計約六倍。主要客戶已開始
下六個月以上長單,目前訂單大於產能、供不應求。</p>
<p>第四季指引:營收季增約 16%(與去年 Q4 相當)。明年新產能自 Q1 起陸續開出,
公司明言「營運優於今年」。產品端:1.6T 已量產,3.2T 與 NPO 高功率產品
與客戶共同開發驗證中,下一代 CPO 依計畫推進。</p>
<p>時間點的巧合值得記一筆:法說當晚,彭博報導 Marvell 深入洽購 Lumentum——
聯亞正是 LITE InP 磊晶委外的主力。那紙「美系長約」的分量,市場隔天用
開盤 +8.3% 投了票(開 2,795,一分鐘後 +6.2%)。</p>
</div><div class="sidebar"><h3>法說速記</h3>
<div class="kv"><div class="k">Q3 成績</div><div class="v">營收15.62億(+183%)/毛利率59%/EPS 6.12</div></div>
<div class="kv"><div class="k">Q4 指引</div><div class="v">營收季增約 +16%</div></div>
<div class="kv"><div class="k">資本支出</div><div class="v">一年累積 80 億,其中 30 億為美系長約追加</div></div>
<div class="kv"><div class="k">產能</div><div class="v">2027=2.5x → 2028 再 2.5x(兩年約六倍)</div></div>
<div class="kv"><div class="k">訂單</div><div class="v">主要客戶六個月以上長單;訂單>產能</div></div>
<div class="kv"><div class="k">自己說的風險</div><div class="v">「毛利率不會無限制提高」——折舊與人力費用兩年內將增加</div></div>
</div></div></div>

<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>六季財務|從 0.46 到 6.12 的斜率</h2>
<span class="src">自家管線(TWSE 申報)+法說</span></div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2025 Q1</td><td class="num">4.55</td><td class="num">32.4%</td><td class="num">9.9%</td><td class="num">0.46</td></tr>
<tr><td>2025 Q2</td><td class="num">5.53</td><td class="num">43.3%</td><td class="num">27.0%</td><td class="num">1.05</td></tr>
<tr><td>2025 Q3</td><td class="num">5.53</td><td class="num">43.6%</td><td class="num">18.8%</td><td class="num">1.08</td></tr>
<tr><td>2025 Q4</td><td class="num">6.42</td><td class="num">48.7%</td><td class="num">32.8%</td><td class="num">2.07</td></tr>
<tr><td>2026 Q1</td><td class="num">9.04</td><td class="num">54.8%</td><td class="num">41.3%</td><td class="num">3.44</td></tr>
<tr><td>2026 Q2</td><td class="num">12.21</td><td class="num">57.5%</td><td class="num">46.9%</td><td class="num">4.62</td></tr>
<tr><td class="hl">2026 Q3</td><td class="num hl">15.62</td><td class="num hl">59%</td><td class="num">—(待公告)</td><td class="num hl">6.12</td></tr></table>
<p>月營收同步驗證:7月 5.01 億(+177%)、8月 5.21 億(+181%)、9月 5.41 億(+190%)——
年增率還在<b>加速</b>,不是高基期鈍化。毛利率六季走 32→43→44→49→55→57→59,
每一季都是結構升級(產品組合往矽光雷射/CW 高功率走),不是一次性。</p>
<div class="bigfact"><div class="n">獲利品質乾淨:營益率 46.9%(Q2),淨利率與營益率同步——沒有業外妝</div>
對照自結照妖鏡專刊(10/28)的標準:這是一張不需要「三查」就能過的損益表。</div></div>

<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>產品與瓶頸|供給才是故事主角</h2></div>
<div class="card"><h4>產品梯隊</h4>
<p>1.6T 雷射<b>已量產</b>;3.2T 與 NPO(近封裝光學)所需高功率產品,與客戶合作開發驗證中;
下一代 CPO 依既定計畫開發。磊晶(AP 端)是擴產重心,<b>磊晶完成後的後段製程仍委外</b>——
這解釋了聯鈞們為什麼跟著吃得到。</p></div>
<div class="card"><h4>上游綁定</h4>
<p>InP 基板已簽<b>五年長約</b>(4月),另備一年庫存、分散日德供應商降低中國依賴;
設備端通過上限 13.15 億投資案導入半導體級曝光、推 6 吋磊晶製程。</p></div>
<div class="card"><h4>瓶頸誠實列</h4>
<p>①日系 E-beam 設備缺口 2026 年仍補不上——擴產時程的最大變數
②折舊+人力費用兩年內明顯增加,公司自己說「毛利率不會無限制提高」——59% 接近頂部區
③後段委外=產出受代工夥伴產能節奏牽制(法說原話:隨下游代工夥伴產能增加,矽光出貨量才持續成長)。</p></div></div>

<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>估值算術|市場在預付 2027-28</h2></div>
<table><tr><th>情境</th><th>EPS</th><th>股價 2,795(10/29 開盤)對應 PE</th></tr>
<tr><td>2026 全年(前三季13.88+Q4約7.2)</td><td class="num">約 21</td><td class="num hl">約 133 倍</td></tr>
<tr><td>2027(產能 2.5x,出貨彈性打八折、毛利率見頂)</td><td class="num">約 40~46</td><td class="num">約 61~70 倍</td></tr>
<tr><td>2028(再 2.5x,同樣打折)</td><td class="num">市場的想像空間</td><td class="num">—</td></tr></table>
<p>白話:<b>今天的價格已經把 2027 的產能全開買進去了</b>,買的人賭的是 2028 那一腳。
這不是說它貴錯了——供不應求+六個月長單+長約綁 capex,是真實需求;但這種結構下,
任何「擴產延遲」(E-beam!)或「客戶端整併凍單」(Marvell-LITE 交易審查期)都會先打估值再打基本面。</p>
<p>年線位置:年低 389 → 年高 3,530(9 倍),10/28 收 2,580(距年高 -27%),
10/29 跳空開 2,795。籌碼:融資 22%(安全區)、外資 20 日買 8 天、
<b>大戶持股四週 -1.6pp</b>——高檔略有調節,不髒但不是進貨型。</p></div>

<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>判準與家規</h2></div>
<div class="card"><h4>三個判準日</h4>
<p>①<b>11/10 十月營收</b>:Q4 指引 +16% QoQ 換算,月營收要往 5.8~6.0 億走——低於 5.5 億就是指引打折
②<b>Marvell-LITE 官宣(最快下週)</b>:成局看聯亞訂單語言有無升級;破局看跳空缺口(2,580→2,795)守不守得住
③<b>明年 Q1 新產能開出</b>:法說承諾的第一張供給兌現支票。</p></div>
<div class="card"><h4>家規檢查</h4>
<p>風險燈仍 🔴 ——禁開新倉,本報告是體檢不是買單;觀察名單零部位。
素材層級:本刊以法說為準(法說>投顧>新聞),轉述來源已交叉比對兩家(經濟日報/豐雲)。
興奮劑警告:今天 +9% 是「交易傳聞+法說」雙題材疊加日,情緒價佔多少,下週官宣見分曉。</p></div></div>

<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span><h2>讀者測驗|十題</h2></div>
<details><summary>第1題:Q3 三個關鍵數字?</summary><p>✅ 營收 15.62 億(+183%)、毛利率 59%、EPS 6.12 創高。</p></details>
<details><summary>第2題:追加 30 億資本支出的原因?</summary><p>✅ 與美系大客戶簽訂長期供貨合約——一年累積 capex 達 80 億。</p></details>
<details><summary>第3題:產能路線圖?</summary><p>✅ 2027 年為目前 2.5 倍,2028 年再 2.5 倍,兩年合計約六倍。</p></details>
<details><summary>第4題:Q4 指引?</summary><p>✅ 營收季增約 16%,與去年 Q4 相當;11/10 十月營收要看到 5.8 億上下。</p></details>
<details><summary>第5題:公司自己承認的毛利率風險?</summary><p>✅ 折舊與人力費用兩年內增加,「毛利率不會無限制提高」——59% 接近頂部區。</p></details>
<details><summary>第6題:最大的擴產瓶頸?</summary><p>✅ 日系 E-beam 設備,2026 年供應缺口仍在。</p></details>
<details><summary>第7題:為什麼聯鈞跟著受惠?</summary><p>✅ 聯亞只擴磊晶,後段製程仍委外——磊晶放量,後段代工跟著吃。</p></details>
<details><summary>第8題:估值現況一句話?</summary><p>✅ 開盤價對 2026 全年約 134 倍,對 2027 產能全開約 61~70 倍——市場在預付 2027-28。</p></details>
<details><summary>第9題:籌碼面唯一的扣分?</summary><p>✅ 大戶持股四週 -1.6pp,高檔略有調節;融資 22% 仍在安全區。</p></details>
<details><summary>第10題:跟 Marvell-LITE 交易的關係?</summary><p>✅ 聯亞是 LITE InP 磊晶委外主力;交易成局=接上更大需求,審查期=凍單風險。兩面都要記。</p></details>
</div>
"""

html = shell(
    masthead="TW·財經報", stamp="3081",
    subtitle="聯亞光電法說報告:兩年六倍的產能賭注 · Q3 EPS 6.12 創高 · 2026/10/29",
    nav=["頭版", "六季財務", "產品瓶頸", "估值算術", "判準家規", "測驗"],
    ticker_html=ticker, body_html=body,
    footer="素材:10/28 線上法說(經濟日報/豐雲轉述,交叉比對)+自家管線 · 研究筆記非投資建議 · TW-BACKTEST 財經報",
)
p = save_issue("3081", DATE, html)
print("saved:", p)

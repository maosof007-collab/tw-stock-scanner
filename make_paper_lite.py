# -*- coding: utf-8 -*-
"""
make_paper_lite.py — 專刊:Marvell 傳購 Lumentum,台鏈的「股東 vs 供應商」之辨
=================================================================
素材:彭博/經濟日報 2026-10-28 報導(談判中未定案)、聯亞 10/28 法說、
自家 12 檔族群體檢(research_rank 維度,data/_lite_chain_rank.csv)。
核心命題:被收購的溢價歸「股東」;台廠全是「供應商」,吃的是訂單不是溢價。
供應鏈分層(直接/舊鏈/同業沾光/別家的鏈)是本刊與媒體名單的差異所在。
"""
from newspaper import shell, save_issue

DATE = "20261029"

ticker = (
    '<span><b>LITE</b> 盤後最高 <span class="up">+17%</span>(收+9%)</span>'
    '<span><b>MRVL</b> 盤後 <span class="gd">-7%</span></span>'
    '<span><b>聯亞</b> 開 <span class="up">+8.3%</span>→一分鐘 +6.2%</span>'
    '<span><b>穩懋</b> 開 <span class="up">+10%</span>→秒回平盤</span>'
    '<span><b>華星光</b> <span class="up">+6.0%</span></span>'
    '<span><b>上詮</b> <span class="gd">-0.6%</span> 逆勢</span>'
    '<span>LITE 市值約 <b>830億美元</b></span>'
)

body = """
<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版|交易還沒簽,錢先跑了</h2>
<span class="src">彭博 2026-10-28 盤後</span></div>
<div class="head1">Marvell 傳深入洽購 Lumentum<br>光通訊的「垂直整合」時刻</div>
<div class="deck">網通晶片巨頭要把雷射與高速光元件整家買下來——最快下週宣布,也可能破局。
台股光通訊族群今晨全面跳空,但先想清楚:台廠拿到的是什麼?</div>
<div class="byline">TW·財經報 編輯室|2026-10-29|素材層級:外電報導(未定案)+自家體檢管線</div>
<div class="cols2"><div>
<p class="dropcap">彭博十月二十八日美股盤後引述知情人士報導,Marvell(MRVL)正就收購
Lumentum(LITE)進行<b>深入談判,最快下週敲定</b>——但條款未定、可能破局。消息一出
LITE 盤後一度大漲 17%,Marvell 反跌 7%:市場一邊給溢價,一邊嫌買貴。</p>
<p>為什麼買?Marvell 的資料中心網路晶片(DSP/交換器/客製 ASIC)跑得愈快,愈依賴
「別人家的」雷射與光元件。把 LITE 買進來,等於把光學這條腿接到自己身上——
從晶片到光引擎垂直整合,對打的是 Broadcom 同樣路數。</p>
<p>對台鏈的意義一句話:<b>LITE 自家 InP 產能缺口約三成、長期委外台灣;
被 Marvell 買走,外包需求接上的是更大的老闆</b>。巧的是,核心受惠者聯亞
同一天開法說,宣布「因美系大客戶長約、追加 30 億資本支出」——時間點自己會說話。</p>
<p>風險也要先寫:①談判可能破局(MRVL 盤後 -7% 這口氣會原路吐回台鏈)
②反壟斷審查曠日廢時 ③整併期間 LITE 下單決策可能短暫凍結。</p>
</div><div class="sidebar"><h3>交易速覽</h3>
<div class="kv"><div class="k">狀態</div><div class="v">深入談判,未簽約;最快下週宣布(彭博)</div></div>
<div class="kv"><div class="k">規模</div><div class="v">LITE 市值約 830 億美元;MRVL 約 2,210 億</div></div>
<div class="kv"><div class="k">目的</div><div class="v">資料中心光學垂直整合(雷射/高速光元件)</div></div>
<div class="kv"><div class="k">盤後反應</div><div class="v">LITE +9%(高見+17%)/MRVL -7%</div></div>
<div class="kv"><div class="k">台股反應</div><div class="v">10/29 開盤一分鐘:聯亞開+8.3%、穩懋開+10%隨即殺回平盤、上詮逆勢-0.6%</div></div>
</div></div></div>

<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>股東 vs 供應商|溢價是誰的?</h2>
<span class="src">本刊核心課</span></div>
<div class="bigfact"><div class="n">收購溢價歸「股東」;台廠全是「供應商」,一毛溢價都拿不到</div>
查遍公開資料:沒有任何台廠是 LITE 的具名股東(5%以上依法必須披露,名單裡全是指數基金)。</div>
<div class="card"><h4>兩條受惠路徑,天差地遠</h4>
<p><b>股東路徑</b>:持有 LITE 美股的人(含複委託)——消息日直接吃 +9~17%,成交再吃溢價。快、直接、一次性。</p>
<p><b>供應商路徑</b>:台廠——邏輯是新老闆需求更大 → 委外訂單變多。慢、間接、要等下單才兌現,
而且中間隔著「交易成不成、審查過不過、整併凍不凍結」三道門。</p>
<p>今晨跳空買進的人,買的是供應商路徑,卻付了股東路徑的情緒價。
開盤一分鐘就有活教材:<b>穩懋以 +10% 漲停價開出,隨即殺回平盤</b>——
有人用漲停的開盤印把貨倒給追消息的人;融資 41% 的股,家規本來就說了大跌日禁接,
開盤倒貨日同理。</p></div>
<div class="card"><h4>順帶闢謠:日月光 ≠ AAOI 股東</h4>
<p>AAOI(應用光電)大股東是 BlackRock 約 9%、Vanguard 約 3.8%、Invesco 約 4.3%、
創辦人林志祥約 2.9%——<b>沒有日月光</b>。AAOI 是 LITE 在光模組端的「同業」,不是誰的供應鏈;
日月光在這題材裡的角色是未來 CPO 放量的封裝外圍,也不在 LITE 供應鏈名單。</p></div></div>

<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>供應鏈分層|直接、舊鏈、沾光,別混著買</h2>
<span class="src">媒體名單 ≠ 受惠程度</span></div>
<table><tr><th>層級</th><th>標的</th><th>跟 LITE 的真實關係</th></tr>
<tr><td class="hl">① 直接供應</td><td><b>聯亞 3081</b></td><td>InP 磊晶——LITE 產能缺口三成的委外主力;10/28 法說「美系大客戶長約+追加30億」</td></tr>
<tr><td class="hl">① 直接供應</td><td><b>聯鈞 3450</b></td><td>雷射 COS/TO-CAN 封裝,美系光通訊大廠代工(光電業,<b>不是封測業</b>)</td></tr>
<tr><td class="hl">① 直接供應</td><td><b>穩懋 3105</b></td><td>市場視為 LITE 雷射晶片長期代工廠(III-V 代工)</td></tr>
<tr><td>② 舊鏈</td><td>同欣電 6271/精材 3374</td><td>LITE 的 VCSEL <b>3D感測時代</b>封測鏈;AI 光通訊成分低,吃題材是外圍</td></tr>
<tr><td>③ 同業沾光</td><td>華星光 4979/光環 3234/東典 6588/前鼎 4908</td><td>光模組/雷射元件同族群,客戶未必是 LITE</td></tr>
<tr><td>④ 別家的鏈</td><td>訊芯-KY 6451(Broadcom)/上詮 3363(台積電 FAU)</td><td>各自效忠別的光學陣營——今晨上詮逆勢開黑、訊芯只漲 1%,市場自己在分層</td></tr>
<tr><td>⑤ 外圍</td><td>日月光 3711</td><td>CPO 先進封裝的未來受惠者,與本交易無直接關係</td></tr></table>
<p>①層才是「交易若成、訂單真來」的名單;③④層漲的是情緒。前刊
<b>CPO 族群特刊(9/30)</b>的五站地圖仍然有效,本次事件只點燃其中「光引擎上游」一站。</p></div>

<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>12 檔體檢|族群內互比(10/28 收盤)</h2>
<span class="src">research_rank 維度</span></div>
<table><tr><th>#</th><th>標的</th><th>總分</th><th>距年高</th><th>營收YoY3</th><th>毛利率(Δ)</th><th>融資%</th><th>旗標</th></tr>
<tr><td>1</td><td class="hl">聯亞 3081</td><td class="num">71.1</td><td class="num">-27%</td><td class="num up">+183%</td><td class="num">61.7(+2.7)</td><td class="num">22</td><td>直接供應核心</td></tr>
<tr><td>2</td><td>光聖 6442</td><td class="num">69.5</td><td class="num">-41%</td><td class="num up">+100%</td><td class="num">65.8(+7.1)</td><td class="num">21</td><td>營收獲利雙升</td></tr>
<tr><td>3</td><td>光環 3234</td><td class="num">63.2</td><td class="num">-18%</td><td class="num up">+116%</td><td class="num">86.4 急升</td><td class="num">—</td><td>唯一站60MA</td></tr>
<tr><td>4</td><td>同欣電 6271</td><td class="num">54.6</td><td class="num">-25%</td><td class="num">+22%</td><td class="num">31.1(+3.1)</td><td class="num gd">12</td><td>外資天14,籌碼最乾淨</td></tr>
<tr><td>5</td><td>東典 6588</td><td class="num">51.0</td><td class="num">-43%</td><td class="num">+132%</td><td class="num">39.4(+18.2)</td><td class="num">28</td><td></td></tr>
<tr><td>6</td><td>穩懋 3105</td><td class="num">50.3</td><td class="num">-13%</td><td class="num">+31%</td><td class="num">28.2(+1.9)</td><td class="num hl">41⚠</td><td>融資紅線</td></tr>
<tr><td>7</td><td>訊芯 6451</td><td class="num">47.1</td><td class="num">-49%</td><td class="num">+32%</td><td class="num">16.8(+4.9)</td><td class="num">27</td><td>Broadcom 鏈</td></tr>
<tr><td>8</td><td>前鼎 4908</td><td class="num">44.6</td><td class="num">-30%</td><td class="num">+32%</td><td class="num">45.7(-1.2)</td><td class="num">24</td><td></td></tr>
<tr><td>9</td><td>聯鈞 3450</td><td class="num">44.2</td><td class="num">-32%</td><td class="num up">+103%</td><td class="num">32.4(+7.6)</td><td class="num hl">39⚠</td><td>大戶4週-8.8pp 在倒</td></tr>
<tr><td>10</td><td>華星光 4979</td><td class="num">36.7</td><td class="num">-32%</td><td class="num">+55%</td><td class="num">22.4(-3.0)</td><td class="num hl">33⚠</td><td></td></tr>
<tr><td>11</td><td>精材 3374</td><td class="num">30.8</td><td class="num">0%</td><td class="num">+30% 減速</td><td class="num">27.7(-2.0)</td><td class="num hl">42⚠</td><td>爆量窗,扣16全場最重</td></tr>
<tr><td>12</td><td>上詮 3363</td><td class="num">28.1</td><td class="num">-46%</td><td class="num">+18%</td><td class="num hl">0.2 虧損邊緣</td><td class="num">25</td><td>營益率-21%</td></tr></table>
<p>注意基本面與題材的錯位:體檢前三名(聯亞/光聖/光環)只有聯亞是①層直接供應;
①層的聯鈞體檢排第 9——基本面最烈(營收連三月翻倍)但<b>融資 39%+大戶邊漲邊倒</b>。
融資 ⚠ 四檔(穩懋/聯鈞/華星光/精材)按家規:大跌日禁接。</p></div>

<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span><h2>劇本與追蹤</h2></div>
<div class="card"><h4>劇本A|下週正式宣布(彭博的基準情境)</h4>
<p>LITE 股東落袋;台鏈看「審查期訂單語言」——聯亞的美系長約是先行指標,已在 10/28 法說兌現一半。
①層逢回才看,③④層的情緒溢價會在一週內還回去。</p></div>
<div class="card"><h4>劇本B|破局</h4>
<p>MRVL 盤後那 -7% 會漲回去,台鏈今晨的跳空會吐回——屆時誰沒跌回起漲點,誰就有真單(觀察名單用法)。</p></div>
<div class="card"><h4>追蹤清單</h4>
<p>①官方公告(最快下週)與收購價 ②反壟斷審查範圍(中國商務部是變數)
③聯亞 11/10 十月營收(QoQ 要接上 +16% 軌道) ④聯鈞大戶持股是否止跌(四週 -8.8pp)
⑤上詮/訊芯若補漲=族群過熱訊號(別家的鏈也漲,代表買的人沒在分層)
⑥穩懋開盤倒貨(開+10%→平盤)後,收盤落點=沾光層情緒的溫度計。</p></div>
<p>⚠ 家規三條:風險燈仍 🔴 禁開新倉;融資>30% 大跌日禁接;排名是體檢不是買單,觀察名單零部位。</p></div>

<div class="sect" id="5"><div class="slabel"><span class="tag">A6</span><h2>讀者測驗|十題</h2></div>
<details><summary>第1題:Marvell 買 Lumentum 的戰略目的?</summary><p>✅ 資料中心光學垂直整合——把依賴外購的雷射/高速光元件接進自家網通晶片平台,對標 Broadcom。</p></details>
<details><summary>第2題:交易現在是什麼狀態?</summary><p>✅ 深入談判、未簽約,最快下週宣布,也可能破局(彭博引述知情人士)。</p></details>
<details><summary>第3題:收購溢價誰拿得到?</summary><p>✅ 只有 LITE 股東。台廠全是供應商,吃訂單不吃溢價——沒有任何台廠是 LITE 具名股東。</p></details>
<details><summary>第4題:台鏈受惠的核心邏輯?</summary><p>✅ LITE 自家 InP 產能缺口約三成、長期委外台灣;被買走後接上 Marvell 更大的需求。</p></details>
<details><summary>第5題:①層直接供應是哪三家?</summary><p>✅ 聯亞(InP 磊晶)、聯鈞(雷射 COS 封裝)、穩懋(雷射代工)。</p></details>
<details><summary>第6題:同欣電/精材為什麼只算「舊鏈」?</summary><p>✅ 它們是 LITE 的 VCSEL 3D感測時代封測鏈,AI 光通訊成分低。</p></details>
<details><summary>第7題:上詮和訊芯為什麼歸「別家的鏈」?</summary><p>✅ 上詮效忠台積電(CPO 光纖陣列)、訊芯效忠 Broadcom(光模組封測)——今晨上詮逆勢翻黑是市場在分層。</p></details>
<details><summary>第8題:聯鈞是封測廠嗎?</summary><p>✅ 不是。產業分類是光電業,做雷射二極體封裝(COS/TO-CAN)——製程像封裝,但不是半導體封測業(OSAT)。</p></details>
<details><summary>第9題:體檢裡融資踩紅線(≥30%)的四檔?</summary><p>✅ 精材 42%、穩懋 41%、聯鈞 39%、華星光 33%——家規:大跌日禁接。</p></details>
<details><summary>第10題:破局怎麼辦?</summary><p>✅ 今晨跳空會吐回;屆時誰守住不回起漲點,誰就有真單——事件是照妖鏡,拿來更新觀察名單。</p></details>
</div>
"""

html = shell(
    masthead="TW·財經報", stamp="LITE",
    subtitle="Marvell 傳購 Lumentum 專刊:股東 vs 供應商 · 供應鏈分層 · 12 檔體檢 · 2026/10/29",
    nav=["頭版", "股東vs供應商", "分層地圖", "12檔體檢", "劇本追蹤", "測驗"],
    ticker_html=ticker, body_html=body,
    footer="素材:彭博/經濟日報 10/28 報導(交易未定案)+聯亞法說+自家體檢管線 · 研究筆記非投資建議 · TW-BACKTEST 財經報",
)
p = save_issue("LITE", DATE, html)
print("saved:", p)

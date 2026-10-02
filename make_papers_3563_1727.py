# -*- coding: utf-8 -*-
"""財經報兩期:牧德 3563(AI 檢測)+ 中華化 1727(電子級硫酸轉機)。
素材:牧德 3/30、6/30 法說報導與備忘錄、中華化電子級硫酸認證報導、bulk_fin 財報/月營收、外資掃描。
註:finmoconf 當日逾時,法說細節採媒體備忘錄轉述,標註來源;公司原始簡報補抓後再校。"""
from newspaper import shell, save_issue

FOOT = ("素材:公開法說報導/備忘錄+公開財報+本系統外資掃描 · 本刊為研究筆記非投資建議 · "
        "TW-BACKTEST 財經報")


def qa(items):
    return ('<div class="sect" id="4"><div class="slabel"><span class="tag">A5</span>'
            '<h2>讀者測驗|十題,看你讀懂幾分</h2></div>'
            + "".join(f"<details><summary>第{i+1}題:{q}</summary><p>✅ {a}</p></details>"
                      for i, (q, a) in enumerate(items)) + "</div>")


# ═══════════════ 牧德 3563 ═══════════════
T1 = """<b>牧德 3563</b> <span class="num">754</span>|距年高 <span class="num">-21.2%</span>(年高 957)
|毛利率 <span class="up">60.4%</span>|近4季EPS <span class="num">16.18</span>
|8月營收 <span class="up">+35.7%(連6月創高)</span>|外資20日 <span class="num hl">賣超 1,146張</span>"""

A1_1 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">法說報導綜整(3/30、6/30)</span></div>
<div class="head1">連六個月創高的檢測廠 外資卻在賣</div>
<div class="deck">訂單排到 2027 下半年、載板專案能見度長達三年、產能目標一口氣喊到 100 億——基本面全壘打的牧德,股價距年高 -21%,外資近 20 日還賣超千張。基本面與籌碼的背離,是這一期的主題。</div>
<div class="byline">本報整理|素材:經濟日報/工商/鉅亨法說報導、富果備忘錄</div>
<div class="cols2"><div>
<p class="dropcap">牧德做的是 AOI(自動光學檢測)——板子越高階、層數越多、線路越細,檢測越不可省。AI 把這門生意從「成本項」變成「保險項」:一片 AI 載板價值是傳統板的數倍,漏檢一片的代價足以買好幾台設備。這就是牧德 2026 年 <span class="hl">AI 相關產品佔營收 70%</span>、明年看 80~90% 的底層邏輯。</p>
<p>數字兇悍:<b>連續 24 個月營收年增、連續 10 個月月增、連續 6 個月改寫單月新高</b>;8 月 3.61 億(+35.7%)。訂單能見度從過去 3~5 個月拉長到接近一年,新增訂單多數排到 2027 下半年交貨,部分載板專案能見度長達三年——設備股罕見的長單結構。公司對應的動作是把年底產能目標提高到 100 億元,後續可再擴至 130 億。</p>
<p>獲利體質是台股設備族群頂級:毛利率 60.4%、營益率 39%、近 4 季 EPS 16.18;產品線從 PCB AOI 一路延伸到 Wafer AOI 與 Packaged IC AOI,客戶包括台積電、日月光等封測大廠。接單強度排序:半導體載板最強、類載板光模組第二、伺服器明年穩定成長。</p>
<p>然後是這一期的問題:這麼好的數字,股價為什麼距年高 -21%、外資近 20 日賣超 1,146 張(僅 7 天買超)?答案大概率是估值消化——754 元對近 4 季 EPS 是 46 倍、對年化約 36 倍,市場在等獲利追上去年那波預期。</p>
</div><div class="sidebar"><h3>三十秒看懂牧德</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">AOI 檢測設備:PCB/載板 → Wafer AOI、Packaged IC AOI(台積電/日月光)</div></div>
<div class="kv"><div class="k">為何現在</div><div class="v">AI 載板+先進封裝檢測需求;AI 產品佔比 70%→80-90%</div></div>
<div class="kv"><div class="k">訂單</div><div class="v">能見度近一年,新單排 2027 下半年;載板專案最長 3 年</div></div>
<div class="kv"><div class="k">產能</div><div class="v">年底目標 100 億,可擴至 130 億;2027 毛利率拚回 60%+</div></div>
<div class="kv"><div class="k">體質</div><div class="v">毛利 60.4%/營益 39%/近4季 EPS 16.18</div></div>
<div class="kv"><div class="k">背離</div><div class="v">距年高 -21%、外資 20 日賣超 1,146 張——估值消化中</div></div>
</div></div></div>"""

A2_1 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>題材|檢測的三層階梯</h2></div>
<div class="head1" style="font-size:28px">從 PCB 到晶圓 檢測單價一路往上爬</div>
<table><tr><th>階梯</th><th>產品</th><th>客戶端</th><th>現況</th></tr>
<tr><td>第一層</td><td>PCB/HDI AOI</td><td>PCB 廠</td><td>本業基石,AI 板升級帶動換機</td></tr>
<tr><td>第二層</td><td class="hl">載板 AOI(接單最強)</td><td>載板廠</td><td>專案能見度最長 3 年</td></tr>
<tr><td>第三層</td><td>Wafer AOI/Packaged IC AOI</td><td>台積電、日月光等</td><td>半導體級驗證通過,單價最高</td></tr></table>
<div class="card"><h4>為什麼訂單排得這麼長?</h4>檢測設備的需求=「新廠數 × 檢測站數」,載板與封測擴產潮(同盟立天車邏輯)讓設備商吃的是確定性資本支出;加上 AI 板單價高、容錯低,檢測密度本身也在升級——量與質雙升。</div>
<div class="card"><h4>TGV 玻璃基板檢測?——誠實標註</h4>本系統 TGV 拆解圖把牧德列為「檢板 AOI(假設)」。本次查證的法說報導與備忘錄<b>均未見玻璃基板著墨</b>——維持 ? 標註,等公司親口說。它現在的成長不需要 TGV,玻璃基板若成真是額外選擇權。</div></div>"""

A3_1 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|頂級體質的驗證</h2></div>
<div class="head1" style="font-size:28px">毛利六成 營收連六創高</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>2Q25</td><td class="num">9.69</td><td class="num">64.23%</td><td class="num">45.06%</td><td class="num">4.20</td></tr>
<tr><td>3Q25</td><td class="num">7.67</td><td class="num">55.58%</td><td class="num">27.82%</td><td class="num">3.86</td></tr>
<tr><td>4Q25</td><td class="num">6.64</td><td class="num">59.86%</td><td class="num">29.84%</td><td class="num">2.52</td></tr>
<tr><td>1Q26</td><td class="num">8.63</td><td class="num">60.58%</td><td class="num">38.68%</td><td class="num">4.61</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">10.47</td><td class="num gd">60.41%</td><td class="num gd">39.05%</td><td class="num gd">5.19</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/06</td><td class="num">3.55</td><td class="num">+15.6%</td></tr>
<tr><td>2026/07</td><td class="num">3.60</td><td class="num gd">+31.8%</td></tr>
<tr><td>2026/08</td><td class="num">3.61</td><td class="num gd">+35.7%</td></tr></table>
<p>注意加速度:YoY 從年初的 +3~15% 一路升到 7、8 月的 +32/+36%——<b>去年下半年基期低+今年出貨加速的雙重效果,下半年 YoY 還會更好看</b>。估值:754 元/近 4 季 16.18 = 46.6 倍;年化 2Q(5.19×4≈20.8)= 36 倍。設備股給 36 倍不便宜也不離譜——取決於你信不信 100 億產能有一天填滿(那對應 EPS 是另一個量級)。</p></div>"""

A4_1 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">基本面無可挑剔 盯的是估值與籌碼</div>
<div class="card"><h4>追蹤清單</h4>①月營收連創高何時中斷(第一個警訊) ②3Q26 毛利率守 60% ③100 億產能擴充的資本支出與交期 ④外資何時由賣轉買(現在 20 日 -1,146 張) ⑤Wafer AOI 在台積電的滲透進度 ⑥玻璃基板 AOI 有無首次公開著墨(TGV ? 轉 ✓ 的時刻)</div>
<div class="card"><h4>反方劇本</h4>①46 倍 PE 消化不完,好消息鈍化——漲不動的好股票 ②載板擴產若遞延,三年能見度會縮水(同盟立風險) ③2025 毛利率曾從 64% 滑到 55%,產品組合波動不小 ④外資持續賣超,內資撐的行情波動大</div>
<p><b>本報判準</b>:這是「等回檔買」不是「追」的類型——基本面連六創高給了底,估值與籌碼決定進場點。掛進觀察池,等外資轉買+地圖突破訊號同時出現。</p></div>"""

QA_1 = qa([
    ("牧德的核心產品是什麼?", "AOI 自動光學檢測設備:PCB/載板 AOI 到 Wafer AOI、Packaged IC AOI。"),
    ("2026 年 AI 相關產品佔營收多少?", "約 70%,明年看 80~90%。"),
    ("訂單能見度有多長?", "接近一年,新單排 2027 下半年;部分載板專案長達 3 年。"),
    ("連續創高紀錄是什麼?", "連 24 個月營收年增、連 10 個月月增、連 6 個月創單月新高。"),
    ("產能目標是多少?", "年底拉到 100 億元,後續可擴至 130 億。"),
    ("半導體端客戶有誰?", "台積電、日月光等(Wafer AOI/Packaged IC AOI)。"),
    ("毛利率水準?", "60.4%(2Q26);2027 年目標回 60% 以上穩住。"),
    ("接單強度排序?", "半導體載板最強、類載板光模組第二、伺服器穩定。"),
    ("本期點出的最大背離是什麼?", "基本面連創高 vs 股價距年高 -21%、外資 20 日賣超 1,146 張。"),
    ("TGV 玻璃基板檢測查證結果?", "法說報導未見著墨——維持「假設待查」,等公司親口說。"),
])

# ═══════════════ 中華化 1727 ═══════════════
T2 = """<b>中華化 1727</b> <span class="num">112</span>|距年高 <span class="num hl">-5.5%</span>(年高 118.5)
|2Q26 毛利率 <span class="up">17.77%(年增+5.5pp)</span>|2Q26 EPS <span class="num">0.38</span>
|8月營收 <span class="up">+62.7%</span>|外資20日 <span class="num hl">賣超 2,224張</span>"""

A1_2 = """<div class="sect" id="0"><div class="slabel"><span class="tag">A1</span><h2>頭版</h2>
<span class="src">電子級硫酸認證與擴產報導綜整</span></div>
<div class="head1">硫酸老廠的先進製程轉生 認證過了 股價也先跑了</div>
<div class="deck">國內硫酸大廠轉型電子級硫酸,先進製程產線 2026 年 3 月拿下半導體龍頭認證、Q2 起認列——毛利率從 9% 跳到 18%、8 月營收 +62.7%。但股價距年高只剩 -5.5%,外資在高檔賣超:轉機是真的,問題是價格。</div>
<div class="byline">本報整理|素材:鉅亨/理財周刊/市場報導、公開財報</div>
<div class="cols2"><div>
<p class="dropcap">中華化是傳產裡的傳產——國內硫酸主要製造商,做硫酸、化工原料買賣與化工設計。這種公司的股價十年如一日,直到半導體把「硫酸」變成「電子級硫酸」:晶圓清洗(RCA/SPM 製程)要用超高純度硫酸,先進製程與先進封裝的清洗步驟越多,用量越大。市場估台灣電子級硫酸需求 2025 年約 3 萬噸/月,<span class="hl">2027 年將倍增至 6 萬噸/月</span>。</p>
<p>轉機的證據鏈在財報上看得見:2025 全年四季 EPS 合計只有 0.04 元、毛利率 9~12%、營益率在損平線掙扎;<b>2026/3 先進製程產線獲半導體龍頭認證</b>後,1Q26 毛利率跳上 17.95%、2Q 營益率 9.45%、EPS 0.38——兩季賺的比去年全年多十五倍。市場並estimate電子級硫酸營收占比從 2024 的 22% 升到 2026 的 35%。8 月營收 2.57 億(+62.7%)是加速的最新讀數。</p>
<p>但這一期必須把另一半講完:股價 112 元,距年高 118.5 只剩 -5.5%——<b>行情已經走了一大段</b>(波段曾自 46 元漲停起算翻倍再翻倍);年化 2Q EPS(0.38×4=1.52)對 112 元是 74 倍,市場流傳的目標價 100 元/EPS 1.78 已被股價超車;外資近 20 日賣超 2,224 張,高檔調節的跡象清楚。</p>
<p>一句話:這是教科書級的轉機股——但現在的位置,是轉機「被發現之後」的價格。</p>
</div><div class="sidebar"><h3>三十秒看懂中華化</h3>
<div class="kv"><div class="k">做什麼</div><div class="v">國內硫酸大廠+化工原料;轉型電子級硫酸(晶圓清洗)</div></div>
<div class="kv"><div class="k">轉機引信</div><div class="v">先進製程產線 2026/3 獲半導體龍頭認證,Q2 起認列</div></div>
<div class="kv"><div class="k">需求</div><div class="v">台灣電子級硫酸 3萬噸/月(2025)→6萬噸/月(2027E)</div></div>
<div class="kv"><div class="k">財務指紋</div><div class="v">毛利率 9%→18%、營益率 -1.8%→9.45%、EPS 0.01→0.38</div></div>
<div class="kv"><div class="k">估值</div><div class="v">112 元=年化 74 倍;市場目標價 100 已被超車</div></div>
<div class="kv"><div class="k">籌碼</div><div class="v">距年高 -5.5% 高檔;外資 20 日賣超 2,224 張</div></div>
</div></div></div>"""

A2_2 = """<div class="sect" id="1"><div class="slabel"><span class="tag">A2</span><h2>題材|電子級硫酸是什麼生意</h2></div>
<div class="head1" style="font-size:28px">純度就是售價 認證就是門票</div>
<table><tr><th>等級</th><th>用途</th><th>特性</th></tr>
<tr><td>工業級硫酸</td><td>肥料/化工/電池</td><td>大宗商品,殺價競爭,毛利個位數</td></tr>
<tr><td class="hl">電子級硫酸</td><td>晶圓清洗(SPM 等製程)</td><td>ppb 級純度門檻+客戶認證,毛利率翻倍起跳</td></tr></table>
<div class="card"><h4>為什麼需求會倍增?</h4>先進製程層數越多、先進封裝(CoWoS 等)步驟越複雜,清洗次數就越多——電子級化學品用量跟製程複雜度成正比,跟景氣的相關性反而低。這與 3042 石英、4722 樹脂同屬「AI 的耗材稅」:設備一開,化學品月月要買。</div>
<div class="card"><h4>認證的重量</h4>半導體龍頭的認證要跑一年以上:純度、供貨穩定性、槽車物流、廠內稽核全要過。2026/3 過關代表<b>門票到手且對手短期進不來</b>;同樣意味著:營收兌現的天花板=客戶拉貨速度,不是中華化的產能。在地供應鏈化(取代進口)是順風。</div>
<p>同鏈對照:電子特化族群(長興/勝一/中華化/永光/國精化/中碳)今年的共同劇本都是「傳產體質+半導體新引擎」——中華化是其中財務翻轉最劇烈、但也漲最兇的一檔。</p></div>"""

A3_2 = """<div class="sect" id="2"><div class="slabel"><span class="tag">A3</span><h2>財報|轉機的解剖</h2></div>
<div class="head1" style="font-size:28px">從損平線到 9.45% 營益率 只用了兩季</div>
<table><tr><th>季度</th><th>營收(億)</th><th>毛利率</th><th>營益率</th><th>EPS</th></tr>
<tr><td>1Q25</td><td class="num">4.52</td><td class="num">9.24%</td><td class="num hl">-1.80%</td><td class="num hl">-0.05</td></tr>
<tr><td>2Q25</td><td class="num">5.19</td><td class="num">12.30%</td><td class="num">1.51%</td><td class="num">0.06</td></tr>
<tr><td>4Q25</td><td class="num">4.84</td><td class="num">11.85%</td><td class="num">-0.08%</td><td class="num">0.01</td></tr>
<tr><td>1Q26</td><td class="num">5.19</td><td class="num gd">17.95%</td><td class="num gd">8.31%</td><td class="num gd">0.28</td></tr>
<tr><td><b>2Q26</b></td><td class="num gd">6.38</td><td class="num gd">17.77%</td><td class="num gd">9.45%</td><td class="num gd">0.38</td></tr></table>
<table><tr><th>月營收</th><th>億</th><th>YoY</th></tr>
<tr><td>2026/06</td><td class="num">2.24</td><td class="num">+19.2%</td></tr>
<tr><td>2026/07</td><td class="num">2.35</td><td class="num">+32.5%</td></tr>
<tr><td>2026/08</td><td class="num gd">2.57</td><td class="num gd">+62.7%</td></tr></table>
<p>這張表就是「認證→認列」的教科書:認證(3月)後毛利率立即跳 6 個百分點、月營收 YoY 逐月加速(+19→+33→+63)。但也要念清楚:<b>基數小</b>(單月 2.5 億)、EPS 絕對值低(半年 0.66),112 元的股價已經把 2027 的產能故事先付了錢。年化 74 倍 vs 牧德 36 倍、國精化 60 倍——電子特化題材裡它是最貴的。</p></div>"""

A4_2 = """<div class="sect" id="3"><div class="slabel"><span class="tag">A4</span><h2>追蹤與風險</h2></div>
<div class="head1" style="font-size:28px">轉機真 價格貴 家規管得住手嗎</div>
<div class="card"><h4>追蹤清單</h4>①9 月營收 YoY 能否站穩 +50%+(兌現速度) ②3Q26 毛利率突破 20%(產品組合續升的證據) ③電子級占比:22%→35% 的路徑每季驗證 ④新產線稼動/擴產公告 ⑤外資由賣轉買的時點</div>
<div class="card"><h4>反方劇本</h4>①年化 74 倍,只要一個月營收不如預期就是雙殺 ②基數小,大客戶拉貨節奏一變,YoY 波動劇烈 ③工業級硫酸本業仍是半數以上營收,大宗價格回落會稀釋毛利率 ④外資 20 日賣超 2,224 張+距年高 -5.5%——籌碼在派發不在吸收,和「還沒發動」名單剛好相反 ⑤市場目標價(100 元)已被超車,再往上需要新的預估上修</div>
<p><b>本報判準</b>:轉機的證據鏈完整(認證✓/毛利率✓/營收加速✓),但現在的位置是「發動之後」——按家規,距高 -5.5% 的高檔+外資派發,<b>禁追</b>;要參與只有兩條路:等像樣的回檔整理出第二個平台,或等 9 月營收開獎證明 +60% 是常態而非單月。它適合放進「對照組」:跟還沒發動名單比著看,你就知道自己買的是哪一種位置。</p></div>"""

QA_2 = qa([
    ("中華化的本業是什麼?", "國內硫酸主要製造商+化工原料買賣,十足傳產。"),
    ("轉機引信是哪一天的什麼事?", "2026 年 3 月,先進製程產線獲半導體龍頭認證,Q2 起認列營收。"),
    ("電子級硫酸用在哪?", "晶圓清洗(SPM 等製程)——先進製程/封裝步驟越多,用量越大。"),
    ("台灣電子級硫酸需求展望?", "2025 約 3 萬噸/月 → 2027 估倍增至 6 萬噸/月。"),
    ("認證前後毛利率變化?", "9~12% → 17.95%/17.77%,認證當季立即跳 6 個百分點。"),
    ("8 月營收年增多少?", "+62.7%,且逐月加速(+19→+33→+63)。"),
    ("電子級營收占比的路徑?", "2024 約 22% → 2026 市場估 35%。"),
    ("現在估值貴不貴?", "年化 2Q EPS 1.52 對 112 元約 74 倍——電子特化題材裡最貴。"),
    ("籌碼面最大的警訊?", "距年高僅 -5.5% 的高檔,外資 20 日賣超 2,224 張——派發不是吸收。"),
    ("本報的操作判準?", "轉機真但位置是發動後:禁追;等回檔第二平台或 9 月營收驗證常態化。"),
])

NAV = ["頭版", "題材", "財報", "追蹤", "測驗"]
for code, stamp, sub, t, body in [
    ("3563", "牧德 3563", "牧德專刊:連六創高的 AI 檢測廠,外資卻在賣 · 2026/10/02",
     T1, A1_1 + A2_1 + A3_1 + A4_1 + QA_1),
    ("1727", "中華化 1727", "中華化專刊:硫酸老廠的先進製程轉生——認證過了,股價也先跑了 · 2026/10/02",
     T2, A1_2 + A2_2 + A3_2 + A4_2 + QA_2),
]:
    html = shell(masthead="TW·財經報", stamp=stamp, subtitle=sub, nav=NAV,
                 ticker_html=t, body_html=body, footer=FOOT)
    print("saved:", save_issue(code, "20261002", html))

# tw_backtest Feature Map

這份文件是給 Agent 找路用的：每個功能在哪一頁、由哪個模組負責、用什麼網址開、有沒有會寫入的操作。
**新增頁面、改模組名稱時，同步更新這份文件，以及 `app.py` 裡的 `st.navigation`。**

## 怎麼開

- preview 名稱是 `tw-backtest-app`，網址 http://localhost:8599（設定寫在 stride_os 的 `.claude/launch.json`）
- 路由：`app.py` 用 `st.navigation(position="hidden")`，側欄是隱藏的，靠頂列 8 顆 `st.page_link` 和首頁的駕駛艙卡片導航
- **網址 = `pages/` 檔名去掉數字前綴**。例如 `pages/44_斷頭雷達.py` → `/斷頭雷達`。首頁是 `views/home.py`，網址 `/`
- **登入**：`gate.require_login()`。`_auth_enabled()` 為假時（本機預設）會直接以管理者身分進入，不需要密碼。雲端開啟登入時：點密碼欄 → 輸入密碼 → Enter → 點「進入」
- 每次 navigate 都會整頁重載、session 歸零；雲端還得重新登入
- 很多頁第一次載入會跑 `@st.cache_data` 的重計算（例如首頁 `compute_sector_heatmap`），要等 spinner 消失才判斷結果
- 錯誤偵測：`[data-testid="stException"]`，以及頁面文字中的 `Traceback`
- 批次巡檢做法：在同源 iframe 裡依序載入 `/<網址>`，等 `stMain` 的文字長度穩定下來，再檢查有沒有 stException。腳本由 `python scripts/sweep_js.py [頁名...]` 產生（網址直接讀 app.py），流程見 `/verify`

## 頁面對照

欄位說明：**寫**＝頁面上有會寫檔或寫 Sheets 的操作；**代號**＝頁面有股票代號或搜尋輸入欄；**reload**＝頁面裡有 `importlib.reload`（熱更新防護）

### 頂層
| 網址 | 標題 | 主要模組 | 備註 |
|---|---|---|---|
| `/` | 今日總覽（駕駛艙） | `views/home.py`、strategies、updater | 回測參數在「⚙️ 回測策略參數與執行」expander；族群熱力圖 |
| `/晨報` | 每日晨報 | analyst_report | 產生邏輯在 `morning_brief.py`（07:15 排程） |
| `/總經` | 總經（大盤溫度計） | macro、recovery_rate | 2026-11-23 加「🌊 大盤本益比河流圖」:`pe_river.market_series/market_trio`,資料=證交所上市公司月報的官方大盤本益比/殖利率/股價淨值比月底值(`fetch_twse_pe.py` → `data/twse_market_pe.csv`,2002/12 起;每日排程 daily_task.bat 會跑,當月檔 9 號後才去問;需要 xlrd)。月底之後才公布的財報由 fetch_twse_pe.py 順手估一次(`pe_river.nowcast`,快取在 data/fundamentals/market_nowcast.json),**頁面只讀快取不發請求**。驗證點:`python -X utf8 pe_river.py market` 印出的「官方月底本益比」要等於 CSV 最後一列,「自己加總的月底本益比」應接近官方值;頁面那行的「現在約 N 倍」要和它一致;2026-11-23 加「🏭 半導體庫存循環燈」:`chip_cycle.py`(六顆燈,只用當時已公布的資料;客戶端三顆=IC 設計營收降溫、IC 設計存貨堆高、系統組裝存貨堆高;另附回測、歷次修正亮燈順序、IC 設計/系統組裝每一檔、美國大客戶、川湖・銅「測過不採用」),資料由每日排程 `chip_cycle.py fetch` 抓 FinMind+yfinance → `data/chip_cycle.json`,**頁面只讀這個檔**。驗證點:`python -X utf8 chip_cycle.py` 印出的「客戶端三顆現在亮 N 顆」和回測表要和頁面一致;改了模組要重開 app;融資維持率風險燈（MA60 推估口徑）；失土收復率（大跌週期收復廣度+情緒階段，`data/recovery_rate.csv` 每日排程更新） |

### 選股與持倉
| 網址 | 標題 | 主要模組 | 寫 | 代號 |
|---|---|---|---|---|
| `/今日選股` | 今日選股 | sector_view；讀 `scan_results/signals_*.csv` | ✓ | |
| `/籌碼地圖` | 籌碼選股地圖（五關漏斗） | mmap_funnel、ui_mini_war | | |
| `/翻多選股` | 翻多選股 | data_provider、chip_chart（SuperTrend） | ✓ | |
| `/月營收預測` | 月營收預測 | monthly_forecast、model_track | ✓ | ✓ |
| `/訊號回查` | 訊號回查 | signal_history | | ✓ |
| `/新面孔雷達` | 新面孔雷達 | new_faces；`data/_new_faces_log.csv` | | ✓ |
| `/斷頭雷達` | 斷頭雷達 | margin_alert、macro（`ratio_real`） | | ✓ |
| `/績效追蹤` | 績效追蹤（持倉、體檢卡） | portfolio、pretrade、trailing、weekly_review、sheets_store | ✓✓ | ✓ |
| `/權證專區` | 權證專區 | warrant_tools | | ✓ |
| `/選擇權學院` | 選擇權學院 | op_paper | ✓ | |
| `/期貨教室` | 期貨教室 | fut_paper | | |
| `/我的ETF` | 我的ETF（停損/停利：`weekly_review.stop_suggestion(代號, 進場價, 進場日)` 從進場日逐日走，賺 1R 後停損只升不降，跌破由 run_daily 的 `enforce_stops` 出場；驗證點：頁面「🛑 距停損」的停損價＝`python -X utf8 -c "import my_etf;print(my_etf.positions_table())"` 的停損價;**「🧪 高股息58檔考卷」分頁**:58 檔高股息/收益型 ETF 一檔一個點(橫軸=這次空頭跌了大盤的幾 %、縱軸=前一段多頭漲了大盤的幾 %、空心=第一次遇到空頭),四關濾到剩幾檔,線圖只畫挑出來的 ≤6 檔+同類灰線+我的ETF/大盤/0050/00981A,另有歷次空頭考卷表;第一個分頁的績效對決圖可用「➕ 疊上高股息 58 檔」加最多 4 檔。只讀 `data/etf58/raw` 快取,每日流程 Step 4.5851 `etf58_inception.update()` 增量補。驗證點:分頁上方四張卡和「過四關」檔數=`python -X utf8 etf58_exam.py` 印出的表與漏斗） | my_etf、weekly_review、etf58_exam | ✓ | |
| `/下單台` | Nova 下單台 | nova_trade；`data/trade_log.csv` | ⚠真單 | ✓ |

`/下單台` 只在有 `config.json` 時出現（本機限定）。**驗證時絕對不能按下單相關的按鈕。**

### 市場與資金流
| 網址 | 標題 | 主要模組 |
|---|---|---|
| `/盤中資金流` | 盤中資金流 | rt_flow（強勢池駐留，頁面開著時才運作）、theme_groups；**維持率破底×爆量**：margin_break（名單 `data/_margin_break_watch.csv` 由 notify_push 每晚 `refresh()` 重建，頁面只讀檔＋盤中用 MIS 抓即時價量；逐分紀錄 `data/_rt_flow/_mbreak_YYYYMMDD.csv`）。驗證點：頁首一行與區塊的「其中爆量 N 檔」＝ `python -X utf8 margin_break.py` 印的「破 60 日低…其中爆量」；個股維持率＝`/斷頭雷達` 個股查詢的數字；`build(asof=前一交易日)` 配今天報價可在收盤後重現盤中口徑。**盤中累積淨流走勢**(2026-11-20 改):一族群一格、縱軸各自獨立,單位是「累積淨流÷累積成交額 %」,由高排到低;驗證點:格數=`rt_flow.universe()` 的族群數(30),標題的 % =`group_flows()` 分時表 flow 累加÷amt 累加 |
| `/產業鏈` | 產業鏈魚骨圖 | supply_chain；`data/supply_chain.json`、`data/tech_maps/` |
| `/產業樹` | 產業樹（樹幹上下游→枝葉→慣性/痛點/限制，節點接營收・籌碼・體檢・擴產查核） | industry_tree；`data/industry_trees/*.json`、`data/_tree_capex.csv`（run_daily Step 4.56 每週重建；頁面按鈕「重新計算擴產查核」會**寫**檔） |
| `/美股連動` | 美股連動雷達 | us_link；`data/us_pairs.json` |
| `/中國連動` | 中國連動雷達 | cn_link；`data/cn_pairs.json` |
| `/資金流向日誌` | 資金流向日誌 | money_flow_daily |
| `/權證大戶` | 權證大戶進出 | warrant_flow |
| `/分割減資雷達` | 分割/減資雷達（公告日布局） | corp_actions（`render_radar` 與 /權證大戶 的 tab 共用） |
| `/多空雷達` | 多空雷達（照族群；多方候補=7/30營收因子、空方=S1套牢池反彈空 EV10+3.1%/勝75%） | dual_radar；`data/_dual_radar_*.csv`、`data/_bear_backtest.csv` |
| `/迴轉率` | 迴轉率雷達 | turnover_radar |
| `/強勢資金` | 強勢資金 | attention_scan、attention_replay（戰績回放） |
| `/法說行事曆` | 法說行事曆 | concall、conf_calendar |
| `/市場資金流向` | 全球資金流向 | market_rrg（RRG 尾巴 8 日） |
| `/產業輪動` | 產業輪動 | sector_rrg（RRG 尾巴 5 週） |
| `/族群輪動` | 主題族群 | sector_rrg、theme_groups |
| `/新聞分析` | 新聞與情緒 | news_trend、apikey/llm |

### 個股研究（幾乎每頁都有代號輸入欄）
| 網址 | 標題 | 主要模組 |
|---|---|---|
| `/財經報` | 財經報專刊+研究海報(先選「🖼 海報／📰 報紙期刊」再選期;海報一律存 `data/papers/<代號>海報_<日期>.html`,目錄是 `總覽_<日期>.html`:`newspaper.save_issue`/`poster.save_poster` 每存一份就自動呼叫 `make_poster_index.build()` 掃資料夾重產,一句話結論讀海報自己的副標,不用手動維護清單;`scripts/check.py` 會檢查資料夾每一份都在總覽裡)。**🗂 族群強弱(族群)** 那張是族群聚集雷達:每日流程 Step 4.59906 自動重產、只留最新一份;亮燈規則=注意力榜前 20 名同一官方產業 ≥4 檔且是產業比重 3 倍以上,或創 20 日新高比例連 3 天全市場第一;出現新亮燈產業才推 LINE。驗證點:海報「🧲 聚集亮燈」卡的產業數=`python -X utf8 sector_cluster.py` 印出的亮燈清單。**🗂 電子通路(族群)** 是存貨/預收/現金流查核:財報數字由 `scripts/dist_bs.py` 從公開資訊觀測站抓到 `data/_dist_bs.csv`(每季手動重跑),海報由 `make_poster_dist.py` 重產。**🗂 金融(族群)**、統一 1216、大統益 1232 是「電子出事時的退路」查核:`make_poster_fin.py` 的 `haven()` 用 2015 年起日線算大盤大跌日與歷次修正的表現,`make_posters_haven.py` 共用它產兩張個股海報;`make_poster_uni.py`(統一集團 8 檔)、`make_poster_scan.py`(避險掃描:25 產業+全部個股+反向 ETF/美債/黃金/美元,後者用 yfinance 抓、存 `data/_haven_assets.csv`)也用同一個 `haven()`。**🗂 金融海嘯對照(族群)** 是 2008 年複習+歷次跌破 20% 之後一年+六種場景:`make_poster_2008.py` 手動重跑,加權指數長歷史在 `data/_twii_long.csv`(1997-07 起,之後接 benchmark_TWII),表格每次重算;美國信用指標是寫死的快照,要更新手動改檔內 `IND`。**🗂 錯殺(每日掃描)** 是策略「崩盤錯殺V轉」的現況追蹤:`make_poster_crash.py` **手動重跑**(不會自己更新,大盤再出現兩日跌 ≥5% 的新事件後要重跑),事件日自動抓最新的(`scripts/crash_scan.py` 的 `Ed` 欄),同時列上一批還站著幾檔;查證筆記 `crash_notes_1116*.py` 是 11/16 查的、只對應 11/06 那一批。驗證點:副標的「收復跌前價的 N 檔」要等於 `data/_crash_cands.csv` 最新 `Ed`、`vol20>=500`、`hit` 非空的列數。**🗂 委屈股(族群)** 是「這一波跌 ≥30% 但營收與本業獲利還在成長」的篩選:`make_poster_wronged.py` 手動重跑,循環股(系統族群表+檔內 `EXTRA` 手補)、設備股(`EQUIP`)、股價仍高於一年前 10% 的都排除,掃描結果存 `data/_wronged_scan.csv`,個股查證寫在檔內 `CHECKED`。驗證點:海報「歷史上 N 次跌破 20%」表的列數=`python -X utf8 -c "import make_poster_2008 as m;print(len(m.episodes(m.load()))-1)"`。**🗂 〈股名〉分點(族群)** 是單檔個股的分點庫存:`branch_hist.py` 從富邦 DJ 公開分點日報抓「掛牌以來每個分點逐日買賣」存 `data/branch/<代號>_branch.csv.gz`(一檔約 3~5 分鐘,只在手動重跑時抓),`make_poster_branch.py <代號>` 出海報(累計庫存前 10、賣的比買的多的分點、最近 14 日賣方有沒有庫存;人工結論寫在檔內 `NOTES`)。另外兩張表拿公開資訊觀測站原始申報來對分點:「內部人申報 × 分點」(`branch_hist.insiders` 抓每月董監持股餘額存 `<代號>_insider.csv`,`insider_match` 找月變動對得上的分點)、「新股從哪來」(`new_shares` 抓增資基準日公告存 `<代號>_newshares.csv`,`conv_windows` 對同期融券賣出/現券償還與淨賣最多的分點);兩個快取只補缺的月份,沒抓過的股票第一次約 15~20 分鐘。驗證點:海報第一名分點的累計=`python -X utf8 branch_hist.py <代號>` 印出的第一列;內部人表最後一列=公開資訊觀測站該月「董監事持股餘額明細」。**內部人質押(族群)** 是全市場事件研究:`insider_pledge.py` 抓公開資訊觀測站「內部人設質解質彙總公告」(上市+上櫃 2014 年起,一年一次請求)存 `data/insider_pledge.csv.gz`,取自然人本人「累積設質 0→有」為事件,算之後 3/6/12/24 個月報酬中位數、同日全市場個股中位數對照、第一次漲到 +50% 要多久;`make_poster_pledge.py` 出海報(加 `--refresh` 重抓今年和去年)。驗證點:海報「四個數字」的事件數與 12 個月中位數=`python -X utf8 insider_pledge.py` 印出的「自然人本人」那一列 | newspaper、poster、sector_cluster、make_poster_cluster；`data/papers/*.html`、`data/_sector_cluster.csv`、`data/_sector_cluster_state.json`；資安 ETF 比較 `make_poster_cyber_etf.py`（執行時從 Yahoo Finance 抓價格/規模/費用/持股，驗證點：海報「報酬」表＝腳本印出的 ytd/y1/y5）；**海報六類**(2026-11-20 核定,`poster.KINDS`:個股深度/族群產業鏈/比較挑選/事件研究/觀點查證/每日掃描,各有顏色與主角;新海報用 `shell_flow(kind=…)`,主角放 blocks 最前面)；版面由海報內嵌的排版程式分欄(不留洞、寬表自動滿列);改了 `poster.CSS` 後跑 `python -X utf8 scripts/restyle_posters.py` 把全部舊海報換樣式並標上類型(內容不動)；限空令 `make_poster_shortban.py`、AI 支出下修 `make_poster_ai_capex.py`+`ai_capex_exposure.py`(驗證點:海報族群總表＝`python -X utf8 ai_capex_exposure.py` 印的表);AI 支出下修海報(`make_poster_ai_capex.py`)另含:左右分開的「股價漲得比獲利多還是少」圖(`poster.dbars`,負值往左、不是跌幅)、「股價走在營收前面」卡(`ai_capex_exposure.cycle_lead`/`now_state`:上一輪 112 檔 81% 股價先見頂、早 8 個月;這一輪各族群營收是否還在創高)、AMD 放空報告+美國新出口規定卡;驗證點:海報有 14 張卡、圖上 AI 伺服器在左側且有「沒有消失」那句、高峰個股 26 檔全列;選擇權 SP 防守地圖(`make_poster_sp.py`+`op_defense.py`,比較類):賣權未平倉集中區、月選各履約價的即時權利金/翻倍點/歷史機率/保證金、同樣處境之後再跌多少;要最新數字就重跑腳本(會抓期交所即時報價);驗證點:海報 10 張卡、四個數字有「現在期貨」且標日盤時間、月選表權利金欄有「現在 / 昨收」兩個數;內需防禦海報(`make_poster_domestic.py`+`bear_sector.py`,事件研究類):內需六組/車用/單車/國防在六次大盤下跌的跌幅、落底後 60/120 日反彈、龍頭(蠱王)市占與股價檢定;手選代號寫在 `bear_sector.EXPECT`,名稱對不上會報錯;驗證點:海報 13 張卡、歷次表有 9 個族群列;個股海報整批重產:`python -X utf8 scripts/regen_stock_posters.py`(跑 16 支腳本、32 檔;同代號舊日期且已進 git 的版本會刪掉);手寫數字的舊版式(wave1111/warn1111/6271)用 `poster_stock.auto_cards` 掛 🆕 更新卡,已有同一季/同一月的不重複掛;國家政策海報(`make_poster_policy.py`+`policy_groups.py`,族群類):116 年度預算的錢給誰、過去四件政策宣布後 6/12/24 個月對應族群 vs 大盤、現在各政策族群營收與股價位置、各族群龍頭;手挑代號寫在 `policy_groups.EXPECT`;驗證點:海報 13 張卡、最上面是預算總表;2026-11-23 加 🗂 流動性凍結(無量跌停案例):`make_poster_liquidity.py`+`scripts/liquidity_scan.py`(本機日線 2015 起,跌停=收在當日最低且跌幅達跌停、量<20 日均量 30%;產 `data/_liquidity_runs.csv`、`_liquidity_days.csv`),要手動重跑:`python -X utf8 make_poster_liquidity.py`;驗證點:`python -X utf8 scripts/liquidity_scan.py verify` 抽樣核對跌停判定;🗂 銀行停水 = `make_poster_credit.py` + `scripts/credit_scan.py`(銀行借貸變嚴對大盤的影響:放款年增 − 存款年增 ≥2 點=吃緊、民間放款年增比半年前低 2 點=降溫、<0=萎縮,回測大盤之後 6/12 個月;另列融資餘額每一次大減。資料=央行金融統計月報公開接口 1987 年起+FinMind 上市融資餘額,快取 `data/_cbc_credit.json`;新聞事實 FACTS 是 2026-11-23 的快照),要手動重跑:`python -X utf8 scripts/credit_scan.py fetch` → `python -X utf8 make_poster_credit.py`(央行每月 25 日前後公布上個月);驗證點:`python -X utf8 scripts/credit_scan.py` 印出現在的數字、回測表、歷次吃緊/降溫/萎縮、融資大減;🗂 跳空漲停(事件研究,2026-11-23)= `make_poster_gapup.py`:2015-06 以來大盤單日漲 ≥4% 的日子,個股分七類(一字鎖死/開盤漲停盤中開過/收不住/開盤沒漲停但收漲停…)算開盤買、收盤買、隔天開盤買之後 5/20 日中位數;規模最像的一次(`MAIN`=2025-04-10)再拆成交值×跌幅 25 格的開盤漲停率,套到最新一天、配委屈股掃描的業績條件出名單(全部個股的數字存 `data/_gapup_scan.csv`);期貨夜盤數字是檔內 `FACTS` 的新聞快照。要手動重跑:`python -X utf8 make_poster_gapup.py`;驗證點:腳本印出的事件表與七類表=海報「歷次表」「那天怎麼走」兩張表;🗂 轉虧為盈(每日掃描,2026-11-24)= `make_poster_turnaround.py`:用 `data/bulk_fin/fin_q_all.csv.gz` 的營益率分 A 剛轉盈/B 轉盈第二季/C 準備轉盈(還在虧、連兩季收斂、外推一次過零),另算 S 三率三升(毛利率、營益率、淨利率都高於上季與去年同季);濃縮名單=A/B/C+近 120 日漲幅 ≤10%+20 日均成交值 ≥0.5 億+沒處置+最新月營收年增;附 2024 Q2 起每季「財報截止日後買進抱 60 個交易日」對全部個股中位數的驗證;金融保險、建材營造不列入;另有族群彙總(官方產業+`theme_groups.py`:合計三率、個股三率三升比例、是否景氣循環、合計毛利率在 2023 Q1 以來排第幾高;存 `data/_turnaround_groups.csv`)與「是不是只賺一季」(歷史上轉盈後下一季還賺的比例、個股「賺了又虧」次數);全部個股的分類存 `data/_turnaround_scan.csv`。`run_daily.py` Step 5.8621 每天在 bulk 財報更新後自動重產(只讀本機檔,約 20 秒,只留最新一份);手動:`python -X utf8 make_poster_turnaround.py`;驗證點:腳本印出的「歷史驗證表」「濃縮名單」=海報上的兩張表;🗂 季節與展覽(事件研究,2026-11-24)= `make_poster_season.py`:①族群(手寫族群+官方產業)每個月份贏過「全部個股等權平均」的年數(2015-02 起),附前半段/後半段驗證與個股層級的運氣對照 ②月營收季節指數(當月÷置中 12 個月平均;資料只有 2023-05 起)與接下來三個月是旺季的個股(存 `data/_season_rev.csv`) ③2027 展覽行事曆 × 對應族群的展前/展後 20 日超額——展覽日期寫在檔內 `EXPO`(2026-11-24 網路查詢,● 有來源、? 未公布),每年要人工補新日期。沒有接排程,手動重跑:`python -X utf8 make_poster_season.py`;驗證點:腳本印出的「驗證」「展覽彙總」=海報結論卡的數字 |
| `/券商觀點` | 券商觀點總覽 | advisory_hub |
| `/個股` | 個股整合頁(一檔一頁,2026-11-24):報價列+分頁「總覽/月營收/財務/估值/籌碼/研究與海報」;「估值」分頁=本益比位置(近 3 年分位)+今年三情境×本益比帶+明年情境(下修思考)+本益比河流圖,前三張用本機 bulk 季報算(`forecast_card.anchor(q=…)`),河流圖只讀「估值前瞻」抓過的快取、這一頁不發請求,沒抓過的顯示「到估值前瞻抓」;總覽是六張卡片(財務摘要、營收、三大法人、籌碼、內部人設質、研究與海報),每張=小圖+關鍵數字+一句白話+「更多」連到原細節頁;網址帶代號 `/個股?code=6425`;「研究與海報」分頁直接內嵌這檔最新的海報。只讀本機檔(日線、bulk 季報/月營收、institutional、margin、tdcc、insider_pledge、papers),不發請求。個股殖利率、淨值比、內部人買賣事後申報目前沒有資料所以不顯示。總覽另有一張滿版的「內部人(董監)持股增減」圖(月底收盤線+董監淨增/淨減圓點+每月估計金額;資料=`insider_trades.py` 的快取)。最上面一排是「個股工作列」(`stock_nav.py`):總覽·快照·體質·估值·戰情室·營收預測·券商觀點·研究中心·海報,代號存在 `st.session_state['cur_code']`,切頁會帶著走(公司快照、財務九宮格、估值前瞻、個股戰情室、券商觀點的輸入框會自動帶入;研究中心輸入代號就會開始載入資料,所以不自動帶;月營收預測是全市場表)。首頁「③ 研究動線」卡縮成三個入口(個股、財經報、券商觀點總表)。驗證點:報價列的收盤=日線最後一筆、近四季 EPS=fin_q_all 最後四季相加;從個股頁點工作列任何一頁,那一頁的代號要和個股頁相同 | symbols、ui_theme、stock_nav、insider_trades |
| `/公司快照` | 公司快照 | symbols、fundamentals |
| `/估值前瞻` | 估值前瞻 | forecast_card（widget key 要綁代號）;2026-11-23 加「本益比河流圖」:`pe_river.py`(`series`/`table`/`figure`)——FinMind 單季 EPS+**未還原**股價(各一個請求,快取 20h 在 data/fundamentals/*_river_*.json,不進 git),河道=近四季 EPS × 自己歷史本益比第 5/25/50/75/95 百分位,可選 5/10/15/20 年;財報用當天已公布的(季報+45 天、年報+90 天)。驗證點:`python -X utf8 pe_river.py 2330` 印出的本益比要和頁面那行、以及證交所公布的當日本益比一致(11/20 是 20.4 倍)。改了 pe_river.py 要重啟 app(模組不重載);2026-11-20 加「明年情境(下修思考)」:`forecast_card.next_year`——維持現況/營益率回近 12 季中位/再加營收下修(AI 族群預設 −16%,頁面可改),外加獲利高峰旗標(營益率比中位高 5 點以上且近四季 EPS ≥ 前年 2 倍);本業虧損或業外占四成以上顯示「不列」。季報、月營收來源落後時 `fundamentals._topup` 會用本機全市場檔補最新一期,`bulk_q_all` 會把股本變動造成的錯誤單季 EPS 設成空值。驗證點:輸入 2383 看到「2027 年情境」標題、🏔 高峰旗標、三列的表;輸入 2338 看到「明年情境不列」 |
| `/財務九宮格` | 財務九宮格 | fin9 |
| `/個股戰情室` | 個股戰情室（彙整頁，牽動模組最多） | chip_chart、pretrade、margin_stress、warrant_flow、tp_radar、supply_chain、lines_check |
| `/個股法人報告` | 個股研究中心 | analyst_report、model_track（會寫報告） |
| `/深度潛力股` | 深度潛力股 | deep_report |
| `/族群儀表板` | 族群儀表板 | theme_groups |
| `/籌碼分析儀表板` | 籌碼分析 | data_provider |
| `/大戶籌碼週報` | 大戶籌碼週報 | big_holder；`data/_bigholder_panel.csv` |
| `/集團股K線` | 集團股K線 | `data/groups.json` |
| `/研究文章` | 研究文章 | analyst_report（save_article） |
| `/研究報告瀏覽器` | 券商報告庫 | report_db |
| `/影片筆記` | 影片筆記 | yt_notes |

### 系統
| 網址 | 標題 | 主要模組 |
|---|---|---|
| `/更新進度` | 更新進度 | progress；`data/_progress.json` |
| `/使用說明` | 使用說明 | — |

## 巡檢基準（2026-11-02 本機）

首頁加上 44 個網址全部可以載入，0 個 stException。大多數頁面 5–12 秒載完。偏慢的頁面：
- 新面孔雷達 23s
- 權證大戶 24s
- 新聞分析 24s
- 大戶籌碼週報 20s
- 產業輪動 16s

2026-11-03 第一次用 `sweep_js.py` 全站巡檢：46 頁（含 `/下單台`）全部通過，共 405 秒。最慢的是月營收預測 27s、權證大戶 24s、新聞分析 23s、首頁 20s。

之後的巡檢如果比這個基準慢很多，就是退化了。`/績效追蹤` 有一個郵件「應用程式密碼」欄，不是登入門，巡檢只認標籤是「密碼」的欄位。

## 登入門（2026-11-02 修正）

- 全站的登入門放在 `app.py`，位置在 `st.navigation(...)` 之後、`nav.run()` 之前，所有網址都會先經過它。個別頁裡的 `require_login()` 留著也無妨（已登入時直接放行）
- **不可以把登入門移到 `st.navigation` 之前**。在那之前就 `st.stop()` 的話，Streamlit 會退回 `pages/` 的舊式路由，直接執行該頁檔案，登入門等於沒用（實測：`/深度潛力股` 直接顯示內容）
- 測試登入門：preview 用 `tw-backtest-auth`（port 8600，`APP_AUTH=1`），在 iframe 裡依序開各網址，每一頁都應該停在密碼框

## 背景管線（不在頁面上，改了要實跑驗證）

| 入口 | 時段 | 內容 |
|---|---|---|
| `run_daily.py` | 盤後（`check_run_needed` 守門） | 官方增量 → 掃描 → 各雷達重建 |
| `notify_push.py` | 每個 bat 時段獨立執行 | LINE 推播：日報、新面孔、斷頭、強勢榜檢討 |
| `morning_brief.py` | 07:15 平日 | 晨報 |
| GitHub Action | 15:10 / 17:00 / 22:30 TW | 雲端資料更新 |

- **ETF58 上市以來四榜(不在頁面上,產出是檔案)**:`scripts/etf58_inception.py`(抓資料+計算)+ `scripts/etf58_build.py`(Excel、PDF)。58 檔高股息/收益型 ETF 從各自上市首日算到截止日(預設 2026-09-30)的 B/C/D/E 四榜,分「含成本/不含成本」兩組,格式照使用者給的 ETF58_BCDE_*_20261101 檔案;有成本組滿一年的用年化/年均排名、未滿一年另列。資料=FinMind(股價、配息、美元匯率)+yfinance(IQQQ、QQA),快取 `data/etf58/raw/`,輸出 `data/etf58/ETF58_上市以來_<截止日>/`。每日流程 Step 4.5851 會跑 `update()` 把快取補到最新(股價每天、配息表每 3 天整份重抓,日期記在 `raw/_meta.json`;手動:`python -X utf8 scripts/etf58_inception.py update`),給 `/我的ETF` 的考卷分頁用;四榜的 Excel/PDF 不會自動重產。重跑:`python -X utf8 scripts/etf58_inception.py fetch --force` → `python -X utf8 scripts/etf58_inception.py build [截止日]`(PDF 用本機 Chrome/Edge 無頭列印)。驗證點:`python -X utf8 scripts/etf58_inception.py check <原檔.xlsx>` 用同一條管線重算原檔期間逐檔核對(2026-11-23:55 檔完全相同、3 檔美元計價差 0.03~0.06 點);輸出 Excel 的「公式驗收」分頁要全部 PASS

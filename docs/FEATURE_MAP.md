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
| `/總經` | 總經（大盤溫度計） | macro、recovery_rate | 融資維持率風險燈（MA60 推估口徑）；失土收復率（大跌週期收復廣度+情緒階段，`data/recovery_rate.csv` 每日排程更新） |

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
| `/我的ETF` | 我的ETF | my_etf | ✓ | |
| `/下單台` | Nova 下單台 | nova_trade；`data/trade_log.csv` | ⚠真單 | ✓ |

`/下單台` 只在有 `config.json` 時出現（本機限定）。**驗證時絕對不能按下單相關的按鈕。**

### 市場與資金流
| 網址 | 標題 | 主要模組 |
|---|---|---|
| `/盤中資金流` | 盤中資金流 | rt_flow（強勢池駐留，頁面開著時才運作）、theme_groups |
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
| `/財經報` | 財經報專刊+研究海報(先選「🖼 海報／📰 報紙期刊」再選期;海報一律存 `data/papers/<代號>海報_<日期>.html`,目錄是 `總覽_<日期>.html`:`newspaper.save_issue`/`poster.save_poster` 每存一份就自動呼叫 `make_poster_index.build()` 掃資料夾重產,一句話結論讀海報自己的副標,不用手動維護清單;`scripts/check.py` 會檢查資料夾每一份都在總覽裡)。**🗂 族群強弱(族群)** 那張是族群聚集雷達:每日流程 Step 4.59906 自動重產、只留最新一份;亮燈規則=注意力榜前 20 名同一官方產業 ≥4 檔且是產業比重 3 倍以上,或創 20 日新高比例連 3 天全市場第一;出現新亮燈產業才推 LINE。驗證點:海報「🧲 聚集亮燈」卡的產業數=`python -X utf8 sector_cluster.py` 印出的亮燈清單。**🗂 電子通路(族群)** 是存貨/預收/現金流查核:財報數字由 `scripts/dist_bs.py` 從公開資訊觀測站抓到 `data/_dist_bs.csv`(每季手動重跑),海報由 `make_poster_dist.py` 重產。**🗂 金融(族群)**、統一 1216、大統益 1232 是「電子出事時的退路」查核:`make_poster_fin.py` 的 `haven()` 用 2015 年起日線算大盤大跌日與歷次修正的表現,`make_posters_haven.py` 共用它產兩張個股海報;`make_poster_uni.py`(統一集團 8 檔)、`make_poster_scan.py`(避險掃描:25 產業+全部個股+反向 ETF/美債/黃金/美元,後者用 yfinance 抓、存 `data/_haven_assets.csv`)也用同一個 `haven()` | newspaper、poster、sector_cluster、make_poster_cluster；`data/papers/*.html`、`data/_sector_cluster.csv`、`data/_sector_cluster_state.json` |
| `/券商觀點` | 券商觀點總覽 | advisory_hub |
| `/公司快照` | 公司快照 | symbols、fundamentals |
| `/估值前瞻` | 估值前瞻 | forecast_card（widget key 要綁代號） |
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

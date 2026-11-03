# tw_backtest — Agent 工作守則

台股回測與選股系統。Streamlit 多頁 app：`app.py` 是 `st.navigation` 路由，回測主體在 `views/home.py`，各功能頁在 `pages/`。
雲端：Streamlit Community Cloud，repo `maosof007-collab/tw-stock-scanner`（**public**），push 到 main 就會自動部署。
策略說明見 [STRATEGY_DOCS.md](STRATEGY_DOCS.md)，安裝與排程見 [README.md](README.md)。

## 完成的定義

1. **畫面相關的改動**：要在真的 app 裡看過才算完成。
   - preview 名稱是 `tw-backtest-app`（port 8599，設定寫在 stride_os 的 launch.json）
   - 登入方式：點密碼欄 → 輸入管理者密碼 → Enter → 點「進入」
   - 每次 navigate 都會整頁重載、session 歸零，必須重新登入
   - 截圖常逾時，改用 `get_page_text` / `read_page` 驗證
   - 頁面上不能出現 `Traceback` 或 `stException`
2. **策略或回測的改動**：附上數字（筆數、期望值/筆、勝率、分年表現），並跟改之前的基準比較。只看總平均不算數，要拆分年份、拆掉極端事件之後再看一次（2025-04 V 轉曾經一個月就佔了五成訊號）
3. **排程或管線的改動**：實際跑一次，確認產出檔有更新，日期要用 `now_tw()` 看
4. 超過約 50 行的改動，commit 前先跑 `/code-review`。寫程式的人不審自己的程式

## 鐵律（每一條都出過事）

能自動檢查的鐵律已經寫進 `scripts/check.py`，**commit 前先跑 `python scripts\check.py`**。它會檢查：語法、`datetime.now()`/`date.today()`（棘輪：舊用法記在 `NOW_BASELINE`，只擋新增的）、`.applymap`、bat 的 `git add` 萬用字元、登入門位置、`pages/` 有沒有掛進 navigation 和 Feature Map、金鑰檔有沒有被 git 追蹤。
又抓到新的重複失誤時，**優先加進 check.py**，做不到才寫在下面。修掉舊的 `datetime.now()` 後，把 `NOW_BASELINE` 的數字調小。

### 程式碼
- **不可以整檔覆寫既有模組**。用 Edit 做局部修改；必須重寫時，先 `git diff` 確認沒有吃掉別人的函式（chip_chart 的 SuperTrend 引擎被蓋掉過，頁 11 因此掛掉）
- **熱更新殘留**：長時間執行的 app 會一直留著舊模組。正在快速迭代的模組，頁面裡直接無條件 `importlib.reload(mod)`；不要用 `hasattr` 檢查函式名稱來決定要不要 reload，新增函式就會漏掉。等模組穩定了再拿掉
- **登入門在 `app.py` 的 `st.navigation` 之後**：在 navigation 之前呼叫 `st.stop()`，Streamlit 會退回 `pages/` 舊式路由，直接執行該頁，等於繞過登入
- **widget key 要綁股票代號**，否則換股後會殘留上一檔的數值
- **時間一律用 `twtime.now_tw()`**，不可以用 `datetime.now()`。雲端（Streamlit Cloud、GitHub Action）跑在 UTC，會差 8 小時
- 雲端環境是新版 pandas / Python：`Styler.applymap` 已經移除，要改用 `.map`；日期欄如果 str 和 date 混在一起會丟 TypeError。主頁的區塊要用 try/except 包起來，避免一塊壞掉拖垮整頁
- Windows 排程裡 print emoji 會因為 cp950 編碼而當掉。入口程式要加 `sys.stdout.reconfigure(encoding="utf-8")`

### 資料與回測
- **新鮮度要有保險絲**：融資、法人資料落後股價超過 7 天，就當作沒有資料。**不可以用 ffill 把舊值拖到今天**（2026-07-20 曾因此出現假訊號，選出了融資其實天天在減的股票）
- **增量更新要能偵測缺口**：從實際的最後一天接著抓，不可以寫死「回抓 7 天」
- **更新不可以靠開頁面觸發**：頁面沒人開，資料就會斷。所有更新都要排進 `run_daily` 或 GitHub Action
- **通知和管線要脫鉤**：`notify_push.py` 每個時段獨立執行，寧可空轉，也不可以沒發通知
- **未來函數**：盤前資訊集的新聞，上緣一律截到當天 08:30；沒有時間戳的新聞不用
- 每日增量用官方資料源（`fetch_daily_official.py`）。yfinance 只負責歷史回補和還原價
- 跌停股（≤ -9.4%）、處置股要在掃描階段就剔除
- 融資維持率是**推估值**（TWSE 不公布逐檔融資金額），只能拿來比相對高低。大盤的真值是另一個口徑（`ratio_real`），兩個不要混用

### 雲端與 git
- **雲端只看得到 git 裡的東西和資料包**。新功能如果要讀本機快取，要嘛把快取放進 git（控制在小量），要嘛放進資料包，否則雲端那一頁會壞
- `.gitignore` 排除目錄時要寫成 `dir/*`，`!` 例外規則才會生效
- **bat 裡的 `git add` 不可以用 glob pathspec**：檔案還沒產生時會 fatal，連帶同一行的其他 pattern 全部失效。要改用目錄層級，例如 `git add -A data/...`
- 遇到 push 被每日資料 commit 擋住：先 `pull --rebase` 再 push
- 這是 **public repo**：金鑰、密碼、個人持倉都不能進 git（金鑰放 `config.json` / secrets，持倉放 Google Sheets）

### LLM 產出
- 一律經過 `llm.py` 的三層降級：API → 本機 CLI → 離線
- **股票代號要經過查核器**（用名稱反查來修正模型幻想出來的代號）。報告裡的數字只能用系統算出來的，不可以讓模型編造還沒公布的月份
- system prompt 要寫明「輸出即報告本文」，否則 CLI 引擎會回一段摘要而不是本文
- 新聞原文連結由程式直接輸出，不讓模型抄（網址太長，抄了會斷）

## 產品原則
- **新增任何榜單，都要附濃縮層**：駐留、冷卻、排除已研究過的。不可以把整張表直接推到 LINE
- RRG 圖的尾巴只畫短視窗（產業 5 週、市場 8 日），點由小到大表示方向
- 研究結論要看期望值，不是看勝率。出場越鬆越賺（移動停利抱波段）

## 環境
- Bash 預設的 cwd 是 stride_os，**每條指令都要先 `cd /g/Stock/tw_backtest/tw_backtest`**，否則資料會寫錯位置
- 隨身版：START.bat 必須先 cd 到 app 目錄；`.lnk` 要用絕對路徑；`.bat` 裡有中文會亂碼
- claude CLI 登入壞掉時：先殺掉殘留的小 claude.exe，刪除 `.credentials.json`，再重新 /login

## 動手前
需求不清楚時，先用自己的話把問題重述給使用者確認。研究型問題先查 `research/` 和 STRATEGY_DOCS，看看是不是已經驗證過。

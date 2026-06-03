# 🇹🇼 台股多策略量化選股系統

> 全市場掃描 × 籌碼分析 × K線圖 × 族群熱點 — 每天 5 分鐘選出今日標的

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📸 功能截圖

| 今日選股 | K線 + 籌碼面板 | 族群熱點 |
|---------|--------------|---------|
| 按時機分級：突破當日 / 早期確認 / 已確認 | 法人連買賣天數 + 站上均線 + 損益追蹤 | Treemap 族群強弱 |

---

## ✨ 主要功能

### 📡 今日選股（`pages/1_今日選股.py`）
- **全市場掃描** 1,900+ 檔上市 + 上櫃，約 5 分鐘出結果
- **進場時機分三級**
  - 🔴 `BUY★★ 突破當日` — 今天量大突破，最佳入場點
  - 🟡 `BUY★ 早期確認` — 突破後 1-2 天，距突破低點 <10%
  - 🟢 `BUY 已確認` — 三天站穩確認
- **自動排除處置股**（每日從台灣證交所/櫃買中心抓取）
- **K線彈出視窗** — 點股票看即時 K 線、均線、法人籌碼、損益追蹤
- **族群熱點地圖** — 35 個產業今日強弱 Treemap

### 📊 全市場回測（`market_backtest.py`）
- 1,900+ 檔 × 任意策略，輸出整體勝率、期望值、逐年分析
- 圖表含：逐年勝率、損益分布、持倉天數分析、月份熱圖

### 🔍 策略回測稽核（主 APP `app.py`）
- 六項稽核：vs 買入持有、參數敏感度、牛熊分段、猴子對照、成本衝擊、Walk-Forward

---

## 🚀 快速開始

### 1. 安裝

```bash
git clone https://github.com/YOUR_NAME/tw_backtest.git
cd tw_backtest
pip install -r requirements.txt
```

### 2. 下載全市場股價（約 20 分鐘，首次執行）

```bash
python download_all_tw_stocks.py
```

> 下載上市 1,092 檔（.TW）+ 上櫃 887 檔（.TWO），共約 1,979 檔，儲存到 `data/`

### 3. 下載外資籌碼歷史（選配，約 70 分鐘）

```bash
python fetch_institutional.py --mode history --start 2020-01-01
```

### 4. 啟動 APP

```bash
streamlit run app.py
```

瀏覽器開啟 `http://localhost:8501`，左側導覽選「📡 今日選股」

---

## 📅 每日更新流程

收盤後執行（約 10 分鐘）：

```bash
python download_all_tw_stocks.py   # 更新股價
python fetch_institutional.py      # 更新外資籌碼
python scan_signals.py             # 掃描今日訊號
```

或一鍵執行：

```bash
python run_daily.py
```

---

## 📁 專案結構

```
tw_backtest/
├── app.py                      # Streamlit 主 APP（回測 + 稽核）
├── pages/
│   └── 1_今日選股.py           # 選股頁面（掃描 + K線 + 族群熱點）
├── scan_signals.py             # 全市場選股掃描
├── market_backtest.py          # 全市場整體勝率回測
├── download_all_tw_stocks.py   # 下載全市場股價
├── fetch_institutional.py      # 三大法人籌碼爬蟲
├── fetch_tdcc.py               # 集保股東結構爬蟲
├── run_daily.py                # 每日自動化腳本
├── strategies/
│   ├── base.py                 # 策略抽象介面
│   ├── stage2.py               # Stage 2 突破策略
│   └── abc_institutional.py    # A+B+C 籌碼趨勢策略
├── requirements.txt
└── data/                       # 自動建立（不上傳 git）
    ├── *.TW.csv / *.TWO.csv    # 個股股價
    ├── benchmark_TWII.csv      # 大盤指數
    ├── stock_list.csv          # 股票清單（含產業別）
    ├── institutional/          # 三大法人資料
    └── tdcc/                   # 集保股東資料
```

---

## 🧠 內建策略

### Stage 2 突破（變盤三部曲）
基於 Stan Weinstein 四階段理論：
- 突破末跌高 → 不破底 → 突破平台
- RS 相對強度 + ATR 移動停損

**全市場回測結果**（2015-2026）
- 整體勝率 39.2%　平均獲利 +10.7%　平均虧損 -5.3%
- **期望值 +0.98%**　獲利因子 1.30

### A+B+C 籌碼趨勢（M哥 v4.0 + 突破確認）
- **A 趨勢**：MA240 上翹 + 扣抵價預測 + 多頭排列
- **B1 外資**：累積淨買達門檻 + 斜率加速
- **B2 賣壓**：量縮小平台（賣壓消失）
- **突破觸發**：量能突然放大（相對均量 1.5x）
- **站穩確認**：3 天不跌破突破日低點
- 訊號分級：`突破當日 > 早期確認 > 已確認`

---

## ➕ 新增策略

```python
# strategies/my_strategy.py
from strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    name        = "我的策略"
    description = "說明"
    version     = "1.0"

    def get_params(self):
        return {
            "ma_period": {
                "type": "int", "default": 20,
                "min": 5, "max": 60, "step": 1,
                "label": "均線週期",
            },
        }

    def generate_signals(self, df, params):
        df["signal"]    = "hold"   # buy / sell / hold
        df["stop_loss"] = float("nan")
        df["state"]     = ""
        # ... 你的邏輯 ...
        return df

    def get_audit_config(self):
        return {"tests": ["A","B","C","D","E","F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}
```

存檔後重啟 APP，策略自動出現在側欄。

---

## 📊 資料來源

| 資料 | 來源 | 更新頻率 |
|------|------|---------|
| 股價 OHLCV | Yahoo Finance（yfinance） | 每日 |
| 大盤指數 | ^TWII | 每日 |
| 三大法人買賣超 | 台灣證交所 T86 | 每日 |
| 集保股東結構 | 集保結算所 opendata | 每週 |
| 處置股清單 | 台灣證交所 + 櫃買中心 | 每日即時 |
| 產業別分類 | TWSE ISIN 公開資料 | 每週 |

---

## ⚠️ 免責聲明

本系統所有策略與回測結果**僅供技術研究與學習參考**，不構成任何投資建議。
股市有風險，投資需謹慎，過去績效不代表未來表現。

---

## 🤝 貢獻

歡迎 PR！特別需要：
- 新策略插件
- 上市 OTC 更多選股條件
- 回測績效優化

---

*Built with ❤️ for Taiwan stock market research*

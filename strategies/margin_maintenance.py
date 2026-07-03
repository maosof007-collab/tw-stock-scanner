"""
strategies/margin_maintenance.py
融資維持率創低反彈（量增）v1.0

核心概念
────────────────────────────────────────────────
融資維持率 = 擔保品市值 / 融資金額 × 100%
          ≈ 收盤價 × 融資餘額(張) / 融資金額(千元)

維持率「創波段新低」代表融資戶套得最深、最接近斷頭（券商通常 130% 追繳、
120% 強制處分）。這是市場最悲觀、賣壓即將出盡的位置。

此時若「成交量突然放大」，代表在最恐慌處有人進場承接，常是融資斷頭洗清
→ 籌碼換手 → 出現報復性反彈（經驗值 +30% 以上）。

訊號邏輯
────────────────────────────────────────────────
進場（買）：
  1. 融資維持率創 N 日新低（套牢最深）
  2. 融資餘額仍處高檔（套牢量大 = 反彈燃料多）
  3. 當日成交量放大（量增 = 有人承接，賣壓出清）
  4. 價格止穩（收盤 > 開盤 或 收盤 > 昨收）
出場（賣）：
  - 觸及停損（近期低點 / ATR）
  - 達到目標漲幅後改用 ATR 移動停利（由回測引擎接手）
  - 融資維持率大幅回升後再度走弱（反彈結束）

資料來源
────────────────────────────────────────────────
最佳：data/margin/{ticker}_margin.csv
      欄位需含：date, margin_balance(融資餘額張), margin_amount(融資金額千元)
      （可另寫 fetch_margin.py 從 TWSE MI_MARGN 抓取）
退而求其次：無檔案時，用「收盤價創 N 日新低」當維持率代理
      （維持率幾乎與股價同步，股價創低 ≈ 融資戶最套）
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

MARGIN_DIR = Path("data/margin")


class MarginMaintenanceStrategy(BaseStrategy):

    name        = "融資維持率創低反彈（量增）"
    description = (
        "融資維持率創波段新低（融資戶套最深、接近斷頭）+ 融資餘額仍高（套牢量大）"
        "+ 成交量放大（有人在恐慌處承接）→ 搏報復性反彈。"
        "有 data/margin/ 資料用真實維持率，無則以股價創低為代理。"
    )
    version = "1.0"

    # ════════════════════════════════════
    def get_params(self) -> dict:
        return {
            "maint_low_period": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "融資維持率創新低回看天數",
            },
            "balance_high_period": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "融資餘額高檔回看天數（套牢量確認）",
            },
            "balance_high_pct": {
                "type": "float", "default": 0.80, "min": 0.5, "max": 1.0, "step": 0.05,
                "label": "融資餘額需達區間高點的比例",
            },
            "vol_surge_mult": {
                "type": "float", "default": 1.8, "min": 1.2, "max": 4.0, "step": 0.1,
                "label": "量增倍數（相對 20 日均量）",
            },
            "signal_valid_days": {
                "type": "int", "default": 3, "min": 1, "max": 10, "step": 1,
                "label": "維持率創低後幾日內量增有效",
            },
            "target_pct": {
                "type": "float", "default": 30.0, "min": 10.0, "max": 60.0, "step": 5.0,
                "label": "目標反彈幅度（%，僅供顯示/分級）",
            },
            "atr_stop": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 3.5, "step": 0.5,
                "label": "停損：ATR 倍數",
            },
            "market_filter": {
                "type": "select",
                "default": "大盤站上季線才進場",
                "options": ["大盤站上季線才進場", "大盤站上月線才進場", "停用（不看大盤）"],
                "label": "大盤多空過濾（避開續跌接刀）",
            },
            "use_margin_data": {
                "type": "select",
                "default": "自動（有資料就用）",
                "options": ["自動（有資料就用）", "強制使用", "停用（用股價代理）"],
                "label": "融資維持率資料來源",
            },
        }

    # ════════════════════════════════════
    def get_audit_config(self) -> dict:
        return {
            "tests":     ["A", "B", "C", "D", "E", "F"],
            "benchmark": "buy_hold",
            "monkey_n":  300,
            "wf_split":  0.5,
        }

    # ════════════════════════════════════
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()

        maint_low_period   = int(params.get("maint_low_period", 60))
        bal_high_period    = int(params.get("balance_high_period", 60))
        bal_high_pct       = float(params.get("balance_high_pct", 0.80))
        vol_surge_mult     = float(params.get("vol_surge_mult", 1.8))
        valid_days         = int(params.get("signal_valid_days", 3))
        target_pct         = float(params.get("target_pct", 30.0))
        atr_stop           = float(params.get("atr_stop", 2.0))
        market_filter      = params.get("market_filter", "大盤站上季線才進場")
        use_margin         = params.get("use_margin_data", "自動（有資料就用）")

        atr = df["ATR"] if "ATR" in df.columns else df["Close"] * 0.02
        if "Vol_MA" in df.columns:
            df["Vol_MA"] = df["Vol_MA"].fillna(df["Volume"].rolling(20).mean())
        else:
            df["Vol_MA"] = df["Volume"].rolling(20).mean()

        # ── 載入 / 代理 融資維持率 ────────────────
        df = self._attach_margin(df, use_margin)

        # ① 融資維持率創 N 日新低（融資戶套最深）
        maint_min = df["maint_ratio"].rolling(maint_low_period).min()
        df["maint_new_low"] = df["maint_ratio"] <= maint_min * 1.001  # 容忍微小浮點誤差

        # ② 融資餘額仍處高檔（套牢量大 → 反彈燃料多）
        bal_max = df["margin_balance"].rolling(bal_high_period).max()
        df["balance_high"] = df["margin_balance"] >= bal_max * bal_high_pct

        # ③ 成交量放大（恐慌處有人承接）
        df["vol_surge"] = df["Volume"] > df["Vol_MA"] * vol_surge_mult

        # ④ 價格止穩
        df["price_steady"] = (df["Close"] >= df["Open"]) | \
                             (df["Close"] > df["Close"].shift(1))

        # ⑤ 大盤多空過濾（避開大盤續跌時接刀）
        df["market_ok"] = self._market_above_ma(df, market_filter)

        # ── 維持率創低後 valid_days 日內仍算「最套區」──
        df["recent_new_low"] = (
            df["maint_new_low"].rolling(valid_days).max().fillna(0).astype(bool)
        )

        # ════════════════════════════════
        # 進場條件
        # ════════════════════════════════
        buy_cond = (
            df["recent_new_low"] &
            df["balance_high"] &
            df["vol_surge"] &
            df["price_steady"] &
            df["market_ok"]
        )

        df["signal"]    = "hold"
        df["stop_loss"] = np.nan
        df["state"]     = "觀察中"
        df["signal_grade"] = ""

        # 停損 = max(近期低點, 收盤 - ATR×倍數)，取較高者（較緊）
        recent_low = df["Low"].rolling(valid_days + 1).min()
        atr_stop_line = df["Close"] - atr * atr_stop
        df["stop_line"] = np.maximum(recent_low, atr_stop_line)

        df.loc[buy_cond, "signal"]    = "buy"
        df.loc[buy_cond, "stop_loss"] = df.loc[buy_cond, "stop_line"]
        df.loc[buy_cond, "state"]     = (
            f"維持率創低+融資套牢+量增 → 搏反彈 {target_pct:.0f}%"
        )

        # 分級：當日創低當日量增（最即時）vs 創低後數日才量增
        is_same_day = buy_cond & df["maint_new_low"]
        df.loc[buy_cond,     "signal_grade"] = "BUY"
        df.loc[is_same_day,  "signal_grade"] = "BUY★"
        df.loc[is_same_day,  "state"] = (
            f"維持率當日創低即放量承接 → 搏反彈 {target_pct:.0f}%"
        )

        # ════════════════════════════════
        # 出場：維持率反彈後再度轉弱
        # ════════════════════════════════
        maint_ma = df["maint_ratio"].rolling(5).mean()
        # 反彈一波後（維持率已脫離低點）又連 3 日走弱
        recovered = df["maint_ratio"] > maint_min * 1.10
        weakening = (
            (df["maint_ratio"] < maint_ma) &
            (df["maint_ratio"].diff() < 0) &
            (df["maint_ratio"].diff().shift(1) < 0)
        )
        # ③ 爆量後量縮下跌出場（移植自 abc）：近4日曾爆量上漲、今天量縮收黑
        vol_blowoff = (
            (df["Volume"] > df["Vol_MA"] * vol_surge_mult) &
            (df["Close"] > df["Close"].shift(1))
        )
        had_blowoff = vol_blowoff.rolling(4).max().fillna(0).astype(bool)
        shrink_down = (
            (df["Volume"] < df["Vol_MA"]) &
            (df["Close"] < df["Close"].shift(1))
        )
        blowoff_exit = had_blowoff & shrink_down

        maint_weak_cond = recovered & weakening
        sell_cond = (maint_weak_cond | blowoff_exit) & (df["signal"] != "buy")
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[maint_weak_cond & (df["signal"] != "buy"), "state"] = "反彈後維持率轉弱出場"
        df.loc[blowoff_exit & (df["signal"] != "buy"), "state"]    = "爆量後量縮下跌出場"

        # ── 進出場原因 ───────────────────
        src = df["margin_source"].iloc[-1] if "margin_source" in df.columns else "proxy"
        df["entry_reason"] = np.where(
            buy_cond,
            (f"融資維持率創{maint_low_period}日低+融資餘額高檔"
             f"+量增{vol_surge_mult}x+價穩（資料:{src}）"),
            ""
        )
        df["exit_reason"] = np.where(
            blowoff_exit & (df["signal"] == "sell"), "爆量後量縮下跌",
            np.where(maint_weak_cond, "反彈後維持率連續走弱", "")
        )
        return df

    # ════════════════════════════════════
    # 大盤多空過濾：加權指數是否站上均線
    # ════════════════════════════════════
    def _market_above_ma(self, df: pd.DataFrame, market_filter: str) -> pd.Series:
        """
        回傳與 df 對齊的布林序列：大盤收盤是否站上指定均線。
        讀 data/benchmark_TWII.csv；停用或讀不到時一律回傳 True（不過濾）。
        """
        if market_filter.startswith("停用"):
            return pd.Series(True, index=df.index)
        ma_period = 20 if "月線" in market_filter else 60

        path = Path("data/benchmark_TWII.csv")
        if not path.exists():
            return pd.Series(True, index=df.index)
        try:
            bm = pd.read_csv(path, index_col=0, parse_dates=True)
            idx = pd.to_datetime(bm.index)
            bm.index = idx.tz_convert(None) if idx.tz is not None else idx
            bm_close = pd.to_numeric(bm.iloc[:, 0], errors="coerce")
            bm_ma    = bm_close.rolling(ma_period).mean()
            above    = (bm_close > bm_ma)
            # 對齊到個股日期（用最近一筆大盤資料）
            aligned = above.reindex(df.index, method="ffill")
            # 大盤資料缺漏（如均線暖身期）時不擋，預設放行
            return aligned.fillna(True).astype(bool)
        except Exception:
            return pd.Series(True, index=df.index)

    # ════════════════════════════════════
    # 融資加權平均成本（從餘額增量推估）
    # ════════════════════════════════════
    @staticmethod
    def _weighted_cost(balance: np.ndarray, close: np.ndarray) -> np.ndarray:
        """
        融資餘額增加時視為以當日收盤建倉、更新加權平均成本；
        餘額減少（償還）時只減持股、成本不變。回傳逐日加權平均成本。
        """
        n = len(balance)
        cost = np.full(n, np.nan)
        hold_qty  = 0.0
        hold_cost = 0.0
        for i in range(n):
            b  = balance[i] if not np.isnan(balance[i]) else 0.0
            px = close[i]
            if i == 0:
                hold_qty, hold_cost = max(b, 0.0), px
            else:
                delta = b - max(balance[i - 1], 0.0)
                if delta > 0 and px > 0:                       # 新增融資 → 更新均價
                    new_qty   = hold_qty + delta
                    hold_cost = (hold_cost * hold_qty + px * delta) / new_qty \
                                if new_qty > 0 else px
                    hold_qty  = new_qty
                elif delta < 0:                                # 償還 → 只減量
                    hold_qty = max(hold_qty + delta, 0.0)
                if hold_qty <= 0:                              # 融資清空 → 成本歸位
                    hold_cost = px
                    hold_qty  = max(b, 0.0)
            cost[i] = hold_cost
        return cost

    # ════════════════════════════════════
    # 融資維持率資料載入（含代理）
    # ════════════════════════════════════
    def _attach_margin(self, df: pd.DataFrame, use_margin: str) -> pd.DataFrame:
        """
        產生兩個欄位：
            maint_ratio     融資維持率（真實或代理）
            margin_balance  融資餘額（張，真實或代理）
        """
        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        tc = ticker.replace(".TWO", "").replace(".TW", "").strip()

        if use_margin != "停用（用股價代理）" and tc:
            path = MARGIN_DIR / f"{tc}_margin.csv"
            if path.exists():
                try:
                    m = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
                    bal = m["margin_balance"].reindex(df.index).ffill().fillna(0.0)
                    # TWSE 逐檔只有融資餘額（張），無金額。
                    # 以餘額「增量 × 當日股價」推估融資加權平均成本，
                    # 維持率 = 收盤 / 加權成本 / 融資成數(上市0.6) × 100%
                    cost = self._weighted_cost(bal.values, df["Close"].values)
                    ratio = df["Close"].values / np.where(cost > 0, cost, np.nan) / 0.6
                    df["maint_ratio"]    = ratio * 100.0
                    df["margin_balance"] = bal.values
                    df["margin_source"]  = "real"
                    return df
                except Exception:
                    pass
            elif use_margin == "強制使用":
                import warnings
                warnings.warn(f"融資資料不存在：{path}，改用股價代理")

        # ── 代理：維持率幾乎與股價同步 ──
        # 維持率創低 ≈ 股價相對成本創低；以「收盤 / 60日均成本」為代理指標
        cost_basis = df["Close"].rolling(60, min_periods=10).mean()
        df["maint_ratio"] = (df["Close"] / cost_basis.replace(0, np.nan) * 130.0).values
        # 融資餘額代理：量能堆高（近期累積量相對長期）→ 套牢量大
        vol_acc_s = df["Volume"].rolling(20).sum()
        vol_acc_l = df["Volume"].rolling(120).sum() / 6.0
        df["margin_balance"] = (vol_acc_s / vol_acc_l.replace(0, np.nan)).fillna(1.0).values
        df["margin_source"]  = "proxy（股價/量能代理）"
        return df

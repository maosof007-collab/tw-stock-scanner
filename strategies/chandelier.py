"""
strategies/chandelier.py
吊燈出場策略（Chandelier Exit）v1.0

原始邏輯來自 XQ全球贏家，完整移植為 Python：

  _atrv    = ATR_倍數 × ATR(N)
  多頭停利 = Highest(Close, N) - _atrv   → 只上不下（追漲）
  空頭停利 = Lowest(Close, N)  + _atrv   → 只下不上（追跌）
  方向判斷：
    Close > 空方線[1] → 翻多
    Close < 多方線[1] → 翻空
    否則              → 維持

進場訊號：方向由空翻多 → buy
出場訊號：方向由多翻空 → sell
停損：持多時停損 = 多頭停利線（隨趨勢向上移動）
"""

import numpy as np
import pandas as pd
from strategies.base import BaseStrategy


class ChandelierStrategy(BaseStrategy):

    name        = "吊燈出場（Chandelier Exit）"
    description = (
        "ATR 追蹤停利策略。多頭：最近N日最高收盤 - ATR×倍數（只上不下）；"
        "空頭：最近N日最低收盤 + ATR×倍數（只下不上）。"
        "方向翻轉即進出場，停損 = 當前吊燈線。"
    )
    version = "1.0"

    # ════════════════════════════════════
    def get_params(self) -> dict:
        return {
            "period": {
                "type": "int", "default": 22, "min": 5, "max": 60, "step": 1,
                "label": "ATR 期數（N）",
            },
            "mult": {
                "type": "float", "default": 3.0, "min": 1.0, "max": 6.0, "step": 0.5,
                "label": "ATR 倍數（越大越鬆）",
            },
            "use_close_for_hl": {
                "type": "select",
                "default": "收盤價",
                "options": ["收盤價", "高低價"],
                "label": "高低點計算基準",
            },
            "min_bars": {
                "type": "int", "default": 5, "min": 1, "max": 30, "step": 1,
                "label": "翻多後最少持倉 K 棒數",
            },
        }

    # ════════════════════════════════════
    def get_audit_config(self) -> dict:
        return {
            "tests":    ["A", "B", "C", "D", "E", "F"],
            "benchmark":"buy_hold",
            "monkey_n": 300,
            "wf_split": 0.5,
        }

    # ════════════════════════════════════
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()

        period   = int(params.get("period", 22))
        mult     = float(params.get("mult", 3.0))
        use_close= params.get("use_close_for_hl", "收盤價") == "收盤價"
        min_bars = int(params.get("min_bars", 5))

        c = df["Close"]
        n = len(df)

        # ── ATR ──────────────────────────
        # 用 market_backtest 注入的 ATR，若無則自行計算
        if "ATR" in df.columns and not df["ATR"].isna().all():
            atr = df["ATR"]
        else:
            h, l, pc = df["High"], df["Low"], c.shift(1)
            tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()

        _atrv = mult * atr

        # ── 高低點基準 ───────────────────
        if use_close:
            hi = c.rolling(period).max()
            lo = c.rolling(period).min()
        else:
            hi = df["High"].rolling(period).max()
            lo = df["Low"].rolling(period).min()

        # ── 吊燈線（向量化實作，模擬 XQ 遞迴邏輯）──────
        # 初始
        longstop_raw  = hi - _atrv
        shortstop_raw = lo + _atrv

        longstop  = np.full(n, np.nan)
        shortstop = np.full(n, np.nan)
        direction = np.full(n, 1)   # 預設多頭

        for i in range(n):
            ls_raw = longstop_raw.iloc[i] if not np.isnan(longstop_raw.iloc[i]) else 0
            ss_raw = shortstop_raw.iloc[i] if not np.isnan(shortstop_raw.iloc[i]) else 0
            cv     = c.iloc[i]

            if i == 0:
                longstop[i]  = ls_raw
                shortstop[i] = ss_raw
                direction[i] = 1
            else:
                prev_cv = c.iloc[i - 1]
                # 多頭停利：只上不下
                if prev_cv > longstop[i - 1]:
                    longstop[i] = max(ls_raw, longstop[i - 1])
                else:
                    longstop[i] = ls_raw

                # 空頭停利：只下不上
                if prev_cv < shortstop[i - 1]:
                    shortstop[i] = min(ss_raw, shortstop[i - 1])
                else:
                    shortstop[i] = ss_raw

                # 方向判斷
                if cv > shortstop[i - 1]:
                    direction[i] = 1
                elif cv < longstop[i - 1]:
                    direction[i] = -1
                else:
                    direction[i] = direction[i - 1]

        df["CE_longstop"]  = longstop
        df["CE_shortstop"] = shortstop
        df["CE_dir"]       = direction
        df["CE_dir_prev"]  = np.concatenate([[np.nan], direction[:-1]])

        # ── 訊號產生 ─────────────────────
        df["signal"]    = "hold"
        df["stop_loss"] = np.nan
        df["state"]     = "觀察"

        for i in range(1, n):
            d     = direction[i]
            d_pre = direction[i - 1]
            cv    = c.iloc[i]

            if d == 1:
                df.iloc[i, df.columns.get_loc("state")] = (
                    f"多頭｜停利 {longstop[i]:.1f}"
                )
                df.iloc[i, df.columns.get_loc("stop_loss")] = longstop[i]
            else:
                df.iloc[i, df.columns.get_loc("state")] = (
                    f"空頭｜停利 {shortstop[i]:.1f}"
                )

            # 翻多進場
            if d == 1 and d_pre == -1:
                df.iloc[i, df.columns.get_loc("signal")]    = "buy"
                df.iloc[i, df.columns.get_loc("stop_loss")] = longstop[i]

            # 翻空出場
            elif d == -1 and d_pre == 1:
                df.iloc[i, df.columns.get_loc("signal")] = "sell"
                df.iloc[i, df.columns.get_loc("state")]  = "翻空出場"

        # ── 進出場原因 ───────────────────
        df["entry_reason"] = np.where(
            df["signal"] == "buy",
            f"吊燈翻多：收盤突破空方停利線",
            "",
        )
        df["exit_reason"] = np.where(
            df["signal"] == "sell",
            "吊燈翻空：收盤跌破多方停利線",
            "",
        )

        return df

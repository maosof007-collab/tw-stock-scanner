"""
strategies/pullback_reentry.py
波段回檔再進場（抱波段的第二買點）v1.0

概念
────────────────────────────────────────────────
針對「已在上升波段」的股票，找回檔不破均線、再起翻紅的「第二買點」。
出場交給回測引擎的移動停利 —— 讓贏單抱住整個波段（呼應回測結論：
抱波段 > 爆量見頂快跑）。只有跌破趨勢均線才主動出場。

進場（買）：
  1. 波段確認：收盤 > MA60、MA20 > MA60、MA60 上揚（趨勢往上）
  2. 回檔：近 pull_days 日內 最低價曾觸及 MA20（拉回測均線）
  3. 不破：回檔期間收盤未跌破 MA60（趨勢沒壞）
  4. 再起：今天收盤 > 昨收 且 收盤站回 MA20（翻紅續攻）
  5. 不追高：收盤未離 MA20 太遠（< extend 倍數）

出場（賣）：收盤跌破 MA60（波段趨勢結束）；其餘交給移動停利
停損：近 pull_days 日最低點 與 MA60 取較高者
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy


class PullbackReentryStrategy(BaseStrategy):

    name        = "波段回檔再進場（第二買點）"
    description = (
        "上升波段中回檔測均線不破、再起翻紅的第二買點。"
        "出場用移動停利抱波段，跌破季線才出。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "ma_fast": {
                "type": "int", "default": 20, "min": 5, "max": 60, "step": 5,
                "label": "回檔測試均線（快）",
            },
            "ma_slow": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "波段趨勢均線（慢）",
            },
            "pull_days": {
                "type": "int", "default": 12, "min": 3, "max": 30, "step": 1,
                "label": "回檔回看天數",
            },
            "extend_mult": {
                "type": "float", "default": 1.12, "min": 1.03, "max": 1.30, "step": 0.01,
                "label": "不追高：收盤離快均線上限倍數",
            },
            "vol_confirm": {
                "type": "float", "default": 1.0, "min": 0.5, "max": 2.5, "step": 0.1,
                "label": "再起量能門檻（相對均量，1=不限）",
            },
            "market_filter": {
                "type": "select",
                "default": "大盤站上季線才進場",
                "options": ["大盤站上季線才進場", "大盤站上月線才進場", "停用（不看大盤）"],
                "label": "大環境：大盤多空過濾",
            },
            "exit_mode": {
                "type": "select",
                "default": "跌破季線(慢均線)",
                "options": [
                    "跌破季線(慢均線)",      # 最鬆：抱整個波段（預設，回測最佳）
                    "跌破快均線",            # 較緊：第一次跌破就出
                    "跌破快均線連2日",        # 中等：確認跌破才出
                    "快均線下彎",            # 動能轉弱即出
                ],
                "label": "出場法（搭配引擎移動停利）",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        ma_f   = int(params.get("ma_fast", 20))
        ma_s   = int(params.get("ma_slow", 60))
        pull   = int(params.get("pull_days", 10))
        extend = float(params.get("extend_mult", 1.12))
        vmult  = float(params.get("vol_confirm", 1.0))
        market_filter = params.get("market_filter", "大盤站上季線才進場")
        exit_mode     = params.get("exit_mode", "跌破季線(慢均線)")

        c = df["Close"]
        df["MA_f"]    = c.rolling(ma_f).mean()
        df["MA_s"]    = c.rolling(ma_s).mean()
        df["Vol_MA"]  = df["Volume"].rolling(20).mean() if "Vol_MA" not in df.columns \
                        else df["Vol_MA"].fillna(df["Volume"].rolling(20).mean())
        df["MA_s_up"] = df["MA_s"] > df["MA_s"].shift(20)

        # ① 波段確認
        uptrend = (c > df["MA_s"]) & (df["MA_f"] > df["MA_s"]) & df["MA_s_up"]
        # ② 近 pull 日曾回檔觸及快均線
        touched = (df["Low"] <= df["MA_f"] * 1.01).rolling(pull).max().fillna(0).astype(bool)
        # ③ 回檔期間收盤沒跌破慢均線
        held    = (c >= df["MA_s"]).rolling(pull).min().fillna(0).astype(bool)
        # ④ 今天翻紅、站回快均線
        resume  = (c > c.shift(1)) & (c > df["MA_f"]) & (c.shift(1) <= df["MA_f"].shift(1) * 1.02)
        # ⑤ 不追高 + 量能
        not_ext = c < df["MA_f"] * extend
        vol_ok  = df["Volume"] >= df["Vol_MA"] * vmult
        market_ok = self._market_above_ma(df, market_filter)

        buy_cond = uptrend & touched & held & resume & not_ext & vol_ok & market_ok

        df["signal"]    = "hold"
        df["stop_loss"] = np.nan
        df["state"]     = "觀察中"
        df["signal_grade"] = ""

        recent_low = df["Low"].rolling(pull).min()
        df["stop_line"] = np.maximum(recent_low, df["MA_s"])

        df.loc[buy_cond, "signal"]       = "buy"
        df.loc[buy_cond, "stop_loss"]    = df.loc[buy_cond, "stop_line"]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"]        = "波段回檔再進場（第二買點）"

        # ── 出場法（搭配引擎移動停利；策略出場主要負責「趨勢壞掉就砍」）──
        below_s = c < df["MA_s"]
        below_f = c < df["MA_f"]
        if exit_mode == "跌破季線(慢均線)":
            exit_sig = below_s & (c.shift(1) >= df["MA_s"].shift(1))
            ex_label = f"跌破MA{ma_s}"
        elif exit_mode == "跌破快均線":
            exit_sig = below_f & (c.shift(1) >= df["MA_f"].shift(1))
            ex_label = f"跌破MA{ma_f}"
        elif exit_mode == "快均線下彎":
            exit_sig = (df["MA_f"] < df["MA_f"].shift(2)) & below_f
            ex_label = f"MA{ma_f}下彎"
        else:  # 跌破快均線連2日（預設）
            exit_sig = below_f & below_f.shift(1).fillna(False) & (c.shift(2) >= df["MA_f"].shift(2))
            ex_label = f"跌破MA{ma_f}連2日"

        sell_cond = exit_sig & (df["signal"] != "buy")
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[sell_cond, "state"]  = f"{ex_label}出場"

        df["entry_reason"] = np.where(buy_cond,
            f"波段(MA{ma_s}上揚)回檔測MA{ma_f}不破+翻紅再起", "")
        df["exit_reason"]  = np.where(sell_cond, ex_label, "")
        return df

    # ════════════════════════════════════
    # 大盤多空過濾：大盤是否站上均線
    # ════════════════════════════════════
    def _market_above_ma(self, df: pd.DataFrame, market_filter: str) -> pd.Series:
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
            above = bm_close > bm_close.rolling(ma_period).mean()
            return above.reindex(df.index, method="ffill").fillna(True).astype(bool)
        except Exception:
            return pd.Series(True, index=df.index)

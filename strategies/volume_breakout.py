"""
strategies/volume_breakout.py
量縮整理 → 出量突破（融資沒走）v1.0

針對「買點太多、但真正出量的地方不多」設計：只在
  ① 前面盤整夠久（量縮、區間收斂）
  ② 今天「真正出量」放量突破整理區高點
  ③ 融資沒走（融資餘額沒減 = 籌碼還鎖著）
三者同時成立才進場 —— 訊號少而精。

出場用移動停利抱波段（回測鐵律：出場越鬆越賺），跌破季線才主動出。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

MARGIN_DIR = Path("data/margin")


class VolumeBreakoutStrategy(BaseStrategy):

    name        = "量縮整理→出量突破（融資沒走）"
    description = (
        "前面量縮盤整、今天真出量突破整理區高點、且融資餘額沒減（籌碼鎖著）才進場。"
        "訊號少而精，移動停利抱波段。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "base_days": {
                "type": "int", "default": 20, "min": 10, "max": 60, "step": 5,
                "label": "整理區回看天數",
            },
            "base_range": {
                "type": "float", "default": 0.18, "min": 0.08, "max": 0.40, "step": 0.02,
                "label": "整理區高低振幅上限（越小越緊）",
            },
            "quiet_mult": {
                "type": "float", "default": 0.9, "min": 0.5, "max": 1.2, "step": 0.05,
                "label": "整理期量縮門檻（相對均量）",
            },
            "surge_mult": {
                "type": "float", "default": 2.0, "min": 1.5, "max": 5.0, "step": 0.25,
                "label": "真出量門檻（突破日量 / 均量）",
            },
            "margin_days": {
                "type": "int", "default": 10, "min": 3, "max": 30, "step": 1,
                "label": "融資沒走回看天數",
            },
            "market_filter": {
                "type": "select",
                "default": "大盤站上季線才進場",
                "options": ["大盤站上季線才進場", "大盤站上月線才進場", "停用（不看大盤）"],
                "label": "大環境：大盤多空過濾",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        base_days  = int(params.get("base_days", 20))
        base_range = float(params.get("base_range", 0.18))
        quiet_mult = float(params.get("quiet_mult", 0.9))
        surge_mult = float(params.get("surge_mult", 2.5))
        margin_days = int(params.get("margin_days", 10))
        market_filter = params.get("market_filter", "大盤站上季線才進場")

        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
        df["Vol_MA"] = (df["Vol_MA"].fillna(v.rolling(20).mean())
                        if "Vol_MA" in df.columns else v.rolling(20).mean())
        df["MA60"] = c.rolling(60).mean()

        # ① 整理區：前 base_days 日（不含今天）高低振幅收斂 + 量縮
        base_hi = h.shift(1).rolling(base_days).max()
        base_lo = l.shift(1).rolling(base_days).min()
        rng = (base_hi - base_lo) / base_lo.replace(0, np.nan)
        tight = rng <= base_range
        quiet = (v.shift(1).rolling(base_days).mean() < df["Vol_MA"] * quiet_mult)

        # ② 真出量突破：今天量 > 均量×surge、收盤突破整理區高點、收紅
        surge = v > df["Vol_MA"] * surge_mult
        breakout = c > base_hi
        up = c > df["Open"]

        # ③ 融資沒走：融資餘額 >= margin_days 日前（沒資料則不擋）
        df = self._attach_margin(df)
        if "margin_balance" in df.columns:
            mb = df["margin_balance"]
            margin_ok = (mb >= mb.shift(margin_days)) | (mb.shift(margin_days).isna())
        else:
            margin_ok = pd.Series(True, index=df.index)

        # ④ 大盤
        market_ok = self._market_above_ma(df, market_filter)

        buy_cond = tight & quiet & surge & breakout & up & margin_ok & market_ok

        df["signal"] = "hold"
        df["stop_loss"] = np.nan
        df["state"] = "觀察中"
        df["signal_grade"] = ""

        # 停損：整理區低點 與 季線 取較高者（較緊）
        df["stop_line"] = np.maximum(base_lo, df["MA60"])
        df.loc[buy_cond, "signal"] = "buy"
        df.loc[buy_cond, "stop_loss"] = df.loc[buy_cond, "stop_line"]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"] = "量縮整理後真出量突破（融資沒走）"

        # 出場：跌破季線（其餘交給引擎移動停利）
        break_trend = (c < df["MA60"]) & (c.shift(1) >= df["MA60"].shift(1))
        sell_cond = break_trend & (df["signal"] != "buy")
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[sell_cond, "state"] = "跌破季線出場"

        df["entry_reason"] = np.where(buy_cond,
            f"量縮整理+出量{surge_mult}x突破+融資沒走", "")
        df["exit_reason"] = np.where(sell_cond, "跌破MA60", "")
        return df

    # ════════════════════════════════════
    def _attach_margin(self, df: pd.DataFrame) -> pd.DataFrame:
        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        tc = ticker.replace(".TWO", "").replace(".TW", "").strip()
        if not tc:
            return df
        p = MARGIN_DIR / f"{tc}_margin.csv"
        if not p.exists():
            return df
        try:
            m = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
            if "margin_balance" in m.columns:
                df["margin_balance"] = m["margin_balance"].reindex(df.index).ffill().values
        except Exception:
            pass
        return df

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
            bc = pd.to_numeric(bm.iloc[:, 0], errors="coerce")
            above = bc > bc.rolling(ma_period).mean()
            return above.reindex(df.index, method="ffill").fillna(True).astype(bool)
        except Exception:
            return pd.Series(True, index=df.index)

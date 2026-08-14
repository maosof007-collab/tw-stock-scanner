"""
strategies/bottom_accumulate.py
腰斬打底＋外資回補（溫水吸籌）v1.0

使用者描述的型（2026-08-14）：
  股價腰斬 → 跌不動了在底部平盤(波動收斂) → 外資開始慢慢買回(不是單日爆買)。
  邏輯:深跌洗光浮額後,大資金只能在平盤區慢慢撿(買快了會把價格推走),
  底部平盤+外資連續溫和回補 = 有人在收貨的腳印。

進場（全部盤後可知,無前視）:
  ① 腰斬:收盤 ≤ 近250日高點 ×(1−halved_pct%)
  ② 打底平盤:近 base_days 日收盤振幅 ≤ base_range%,且 20 日報酬絕對值 ≤ 3%
  ③ 外資溫水回補:近 acc_days 日外資「累計買超>0」且「買超天數 ≥ 60%」
     (排除單日爆買:單日最大買超 < 累計的一半 → 是慢慢買不是隔日沖)
  ④ 均量 ≥ 500 張;法人資料落後 >7 天=保險絲不出訊號
出場:創 base_days 日新低=打底失敗砍;其餘交給引擎移動停利(出場越鬆越賺)。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

INST_DIR = Path("data/institutional")


class BottomAccumulateStrategy(BaseStrategy):

    name        = "腰斬打底＋外資回補"
    description = (
        "深跌(預設-40%)後底部平盤(波動收斂),外資連續溫和買回(非單日爆買)＝"
        "大資金收貨腳印。破打底區間低點=打底失敗出場,其餘交給移動停利。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "halved_pct": {
                "type": "float", "default": 40.0, "min": 30.0, "max": 60.0, "step": 5.0,
                "label": "距250日高點跌幅門檻（%）",
            },
            "base_days": {
                "type": "int", "default": 20, "min": 10, "max": 60, "step": 5,
                "label": "打底觀察窗（日）",
            },
            "base_range": {
                "type": "float", "default": 10.0, "min": 5.0, "max": 20.0, "step": 1.0,
                "label": "打底振幅上限（%）",
            },
            "acc_days": {
                "type": "int", "default": 20, "min": 10, "max": 60, "step": 5,
                "label": "外資回補觀察窗（日）",
            },
            "atr_stop": {
                "type": "float", "default": 1.5, "min": 1.0, "max": 3.0, "step": 0.25,
                "label": "初始停損（ATR 倍數）",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        halved = float(params.get("halved_pct", 40.0)) / 100.0
        base_days = int(params.get("base_days", 20))
        base_range = float(params.get("base_range", 10.0)) / 100.0
        acc_days = int(params.get("acc_days", 20))
        atr_stop = float(params.get("atr_stop", 1.5))

        c, v = df["Close"], df["Volume"]
        atr = df["ATR"] if "ATR" in df.columns else (c * 0.02)

        df["signal"] = "hold"
        df["stop_loss"] = np.nan
        df["state"] = "觀察中"
        df["signal_grade"] = ""
        df["entry_reason"] = ""
        df["exit_reason"] = ""

        df = self._attach_fi(df)
        if "fi_lots" not in df.columns:
            df["state"] = "無法人資料"
            return df
        fi = df["fi_lots"]

        # ① 腰斬
        hi250 = c.rolling(250, min_periods=120).max()
        cond_halved = c <= hi250 * (1 - halved)
        # ② 打底平盤:窗內振幅收斂 + 趨勢走平
        roll_max = c.rolling(base_days).max()
        roll_min = c.rolling(base_days).min()
        cond_base = ((roll_max / roll_min - 1) <= base_range) & \
                    (c.pct_change(20).abs() <= 0.03)
        # ③ 外資溫水回補:累計>0、買超天數≥60%、非單日爆買
        fi0 = fi.fillna(0)
        acc_sum = fi0.rolling(acc_days).sum()
        buy_days = (fi0 > 0).rolling(acc_days).sum()
        max_day = fi0.rolling(acc_days).max()
        cond_acc = (acc_sum > 0) & (buy_days >= acc_days * 0.6) & \
                   (max_day < acc_sum * 0.5) & fi.notna()
        # ④ 流動性
        cond_liq = v.rolling(20).mean() >= 500_000

        all_cond = (cond_halved & cond_base & cond_acc & cond_liq).fillna(False)
        buy = all_cond & ~all_cond.shift(1).fillna(False)      # 邊緣觸發

        df.loc[buy, "signal"] = "buy"
        df.loc[buy, "stop_loss"] = (c - atr * atr_stop)[buy]
        df.loc[buy, "signal_grade"] = "BUY"
        df.loc[buy, "state"] = "腰斬打底外資回補"
        df.loc[buy, "entry_reason"] = "腰斬後平盤打底+外資連續溫和買超"

        # 出場:創打底窗新低=打底失敗
        new_low = c < roll_min.shift(1)
        sell = new_low & (~buy)
        df.loc[sell, "signal"] = "sell"
        df.loc[sell, "state"] = "破打底低點出場"
        df.loc[sell, "exit_reason"] = f"創{base_days}日新低(打底失敗)"
        return df

    # ════════════════════════════════════
    def _attach_fi(self, df: pd.DataFrame) -> pd.DataFrame:
        """外資買賣超(張);過期>7天=無資料,不 ffill(同 fi_follow 保險絲)。"""
        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        tc = ticker.replace(".TWO", "").replace(".TW", "").strip()
        if not tc:
            return df
        p = INST_DIR / f"{tc}_inst.csv"
        if not p.exists():
            return df
        try:
            m = pd.read_csv(p, usecols=lambda col: col in
                            ("date", "外陸資買賣超股數(不含外資自營商)", "外資買賣超股數"))
            m["date"] = pd.to_datetime(m["date"], errors="coerce")
            m = m.dropna(subset=["date"]).set_index("date").sort_index()
            if len(m) == 0 or (df.index[-1] - m.index[-1]).days > 7:
                return df
            a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
            b = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
            fi = a.fillna(b) / 1000.0
            df["fi_lots"] = fi.reindex(df.index).values
        except Exception:
            pass
        return df

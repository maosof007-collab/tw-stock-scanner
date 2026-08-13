"""
strategies/crash_resilient.py
崩盤抗跌強勢（大戶不肯賣）v1.0

與 crash_recovery 相對的另一個假說：
  大盤兩日崩跌(≥5%)時「幾乎沒跌」的股 = 恐慌中大戶不肯賣、買盤硬接,
  等大盤止跌訊號出現後,這批抗跌股往往率先創高（相對強勢延續）。

進場（全部盤後可知,無前視）：
  事件日 E:大盤 2 日累跌 ≥ crash_drop%
  個股條件:同窗口跌幅 ≤ resil_drop%（跌不到大盤一半）,且仍站在季線上,均量 ≥ 500 張
  觸發:E 後 confirm_days 日內,大盤單日反彈 ≥ rebound%（止跌確認日)→ 當日收盤買
出場：引擎移動停利＋跌破季線才主動出（鐵律:出場越鬆越賺）。
"""

import numpy as np
import pandas as pd
from strategies.base import BaseStrategy
from strategies.crash_recovery import _load_benchmark


class CrashResilientStrategy(BaseStrategy):

    name        = "崩盤抗跌強勢（大戶不肯賣）"
    description = (
        "大盤兩日崩跌時幾乎沒跌、且仍站季線上的股（恐慌中買盤硬接），"
        "大盤止跌確認日跟進。出場交給移動停利＋跌破季線。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "crash_drop": {
                "type": "float", "default": 5.0, "min": 3.0, "max": 10.0, "step": 0.5,
                "label": "大盤2日崩跌門檻（%）",
            },
            "resil_drop": {
                "type": "float", "default": 2.0, "min": 0.0, "max": 5.0, "step": 0.5,
                "label": "個股最多跌幅（%,越小越抗跌）",
            },
            "rebound": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 5.0, "step": 0.5,
                "label": "大盤止跌確認（單日反彈%）",
            },
            "confirm_days": {
                "type": "int", "default": 10, "min": 3, "max": 20, "step": 1,
                "label": "確認期限（事件後 N 日內）",
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
        crash_drop = float(params.get("crash_drop", 5.0)) / 100.0
        resil_drop = float(params.get("resil_drop", 2.0)) / 100.0
        rebound = float(params.get("rebound", 2.0)) / 100.0
        confirm_days = int(params.get("confirm_days", 10))
        atr_stop = float(params.get("atr_stop", 1.5))

        c, v = df["Close"], df["Volume"]
        atr = df["ATR"] if "ATR" in df.columns else (c * 0.02)

        df["signal"] = "hold"
        df["stop_loss"] = np.nan
        df["state"] = "觀察中"
        df["signal_grade"] = ""
        df["entry_reason"] = ""
        df["exit_reason"] = ""

        bm = _load_benchmark()
        if bm.empty:
            df["state"] = "無大盤資料"
            return df
        bm2 = bm.pct_change(2)
        bm1 = bm.pct_change()
        events = bm2[bm2 <= -crash_drop].index

        ma60 = c.rolling(60).mean()
        vol_ok = v.rolling(20).mean() >= 500_000
        buy = pd.Series(False, index=df.index)
        reason = pd.Series("", index=df.index)
        pos = df.index

        for E in events:
            loc = pos.searchsorted(E)
            if loc >= len(pos) or pos[loc] != E or loc < 3:
                continue
            ref = float(c.iloc[loc - 2])
            if not ref or np.isnan(ref):
                continue
            drop = c.iloc[loc] / ref - 1
            if drop < -resil_drop:
                continue                              # 跌太多,不算抗跌
            if not (c.iloc[loc] > ma60.iloc[loc]):
                continue                              # 崩盤中仍要站季線上
            # 大盤止跌確認日:E 後 N 日內第一個單日反彈 ≥ rebound
            bseg = bm1[(bm1.index > E)].head(confirm_days)
            conf = bseg[bseg >= rebound]
            if conf.empty:
                continue
            d0 = conf.index[0]
            j = pos.searchsorted(d0)
            if j >= len(pos) or pos[j] != d0:
                continue
            if bool(vol_ok.iloc[j]):
                buy.iloc[j] = True
                reason.iloc[j] = (f"事件{E:%m/%d}抗跌({drop*100:+.1f}%)守季線,"
                                  f"大盤止跌確認跟進")

        df.loc[buy, "signal"] = "buy"
        df.loc[buy, "stop_loss"] = (c - atr * atr_stop)[buy]
        df.loc[buy, "signal_grade"] = "BUY"
        df.loc[buy, "state"] = "崩盤抗跌強勢"
        df.loc[buy, "entry_reason"] = reason[buy]

        sell = (c < ma60) & (c.shift(1) >= ma60.shift(1)) & (~buy)
        df.loc[sell, "signal"] = "sell"
        df.loc[sell, "state"] = "跌破季線出場"
        df.loc[sell, "exit_reason"] = "跌破MA60"
        return df

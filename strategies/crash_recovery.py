"""
strategies/crash_recovery.py
崩盤錯殺V轉（收復失土）v1.0

假說（2026-07-28/29 大屠殺驗證出的型）：
  大盤兩日崩跌(≥5%)時,好股票會被融資斷頭/恐慌賣壓「錯殺」得比大盤更慘;
  之後最快收復崩盤前價位的,代表有真實買盤把它撿回去 → 跟上去。
  案例:川湖/宏致/鈺創/聯茂 在 7/28-29 跌 13~22%,兩週內全數創新高。

進場（全部盤後可知,無前視）：
  事件日 E:大盤 2 日累跌 ≥ crash_drop%
  個股條件:同窗口跌幅 ≥ stock_drop%（跌得比大盤慘 = 錯殺候選）,均量 ≥ 500 張
  觸發:E 後 recover_days 日內,收盤第一次站回「崩盤前收盤價」→ 當日收盤買
出場：引擎移動停利（賺1R保本→鎖利）＋跌破季線才主動出（鐵律:出場越鬆越賺）。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy


def _load_benchmark() -> pd.Series:
    p = Path("data/benchmark_TWII.csv")
    if not p.exists():
        return pd.Series(dtype=float)
    bm = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = pd.to_datetime(bm.index)
    bm.index = idx.tz_convert(None) if idx.tz is not None else idx
    return pd.to_numeric(bm.iloc[:, 0], errors="coerce").dropna()


class CrashRecoveryStrategy(BaseStrategy):

    name        = "崩盤錯殺V轉（收復失土）"
    description = (
        "大盤兩日崩跌時跌得比大盤更慘的股（錯殺候選），"
        "N 日內收盤收復崩盤前價位＝真實買盤回補 → 跟進。"
        "出場交給移動停利＋跌破季線（出場越鬆越賺）。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "crash_drop": {
                "type": "float", "default": 5.0, "min": 3.0, "max": 10.0, "step": 0.5,
                "label": "大盤2日崩跌門檻（%）",
            },
            "stock_drop": {
                "type": "float", "default": 10.0, "min": 6.0, "max": 20.0, "step": 1.0,
                "label": "個股同窗口跌幅門檻（%）",
            },
            "recover_days": {
                "type": "int", "default": 10, "min": 3, "max": 30, "step": 1,
                "label": "收復期限（事件後 N 日內）",
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
        stock_drop = float(params.get("stock_drop", 10.0)) / 100.0
        recover_days = int(params.get("recover_days", 10))
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
        events = bm2[bm2 <= -crash_drop].index      # 大盤事件日(2日累跌達標)

        buy = pd.Series(False, index=df.index)
        reason = pd.Series("", index=df.index)
        vol_ok = v.rolling(20).mean() >= 500_000

        pos = df.index
        for E in events:
            loc = pos.searchsorted(E)
            if loc >= len(pos) or pos[loc] != E or loc < 3:
                continue                              # 該股當日無資料
            ref = float(c.iloc[loc - 2])              # 崩盤前收盤(E-2)
            if not ref or np.isnan(ref):
                continue
            drop = c.iloc[loc] / ref - 1
            if drop > -stock_drop:
                continue                              # 沒被錯殺,不是本策略的菜
            win = slice(loc + 1, min(loc + 1 + recover_days, len(pos)))
            seg = c.iloc[win]
            hit = seg[seg > ref]
            if hit.empty:
                continue                              # 期限內沒收復
            d0 = hit.index[0]
            if bool(vol_ok.loc[d0]):
                buy.loc[d0] = True
                reason.loc[d0] = (f"事件{E:%m/%d}錯殺{drop*100:.0f}%,"
                                  f"{(pos.searchsorted(d0)-loc)}日收復崩盤前價")

        df.loc[buy, "signal"] = "buy"
        df.loc[buy, "stop_loss"] = (c - atr * atr_stop)[buy]
        df.loc[buy, "signal_grade"] = "BUY"
        df.loc[buy, "state"] = "錯殺V轉收復"
        df.loc[buy, "entry_reason"] = reason[buy]

        ma60 = c.rolling(60).mean()
        sell = (c < ma60) & (c.shift(1) >= ma60.shift(1)) & (~buy)
        df.loc[sell, "signal"] = "sell"
        df.loc[sell, "state"] = "跌破季線出場"
        df.loc[sell, "exit_reason"] = "跌破MA60"
        return df

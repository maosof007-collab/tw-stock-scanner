"""
strategies/margin_contrarian.py
大跌中融資逆勢買 v1.0

找出「今天大跌、但融資餘額不減反增」的股票 —— 融資戶在逆勢承接/攤平。
此訊號傳統上是「反指標」（散戶不認輸越攤越套），但也可能是有人逆勢承接。
直接產生訊號回測，由數據判斷是買點還是警訊。

訊號（signal）：
  1. 今天大跌：當日跌幅 <= -drop_pct
  2. 近 N 日股價在跌（close < N日前）
  3. 同期間融資餘額卻增加（margin_balance > N日前）→ 逆勢加碼
  需有融資資料（上市+上櫃皆已具備）

出場：移動停利（引擎）+ 跌破近期低點停損；反彈後維持率轉弱不在此檔處理。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

MARGIN_DIR = Path("data/margin")


class MarginContrarianStrategy(BaseStrategy):

    name        = "大跌中融資逆勢買"
    description = (
        "今天大跌、但融資餘額不減反增（融資戶逆勢承接/攤平）。"
        "傳統視為反指標，實際買賣勝負由回測決定。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "drop_pct": {
                "type": "float", "default": 3.5, "min": 1.0, "max": 9.0, "step": 0.5,
                "label": "今日大跌門檻（跌幅%）",
            },
            "window": {
                "type": "int", "default": 3, "min": 1, "max": 15, "step": 1,
                "label": "融資逆勢回看天數",
            },
            "min_margin_up": {
                "type": "float", "default": 0.0, "min": 0.0, "max": 10.0, "step": 0.5,
                "label": "融資增幅下限（% of 餘額，0=只要增加）",
            },
            "entry_mode": {
                "type": "select",
                "default": "連續大跌再接",
                "options": ["大跌當天", "次日翻紅確認", "連續大跌再接"],
                "label": "進場時機（連續大跌再接=回測最佳）",
            },
            "atr_stop": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 4.0, "step": 0.5,
                "label": "停損：ATR 倍數",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        drop_pct = float(params.get("drop_pct", 3.5)) / 100.0
        window   = int(params.get("window", 3))
        min_up   = float(params.get("min_margin_up", 0.0)) / 100.0
        atr_stop = float(params.get("atr_stop", 2.0))

        c = df["Close"]
        atr = df["ATR"] if "ATR" in df.columns else c * 0.02

        # ① 今天大跌
        ret_today = c / c.shift(1) - 1
        big_drop = ret_today <= -drop_pct

        # ② 近 window 日股價在跌
        price_down = c < c.shift(window)

        # ③ 融資逆勢增加
        df = self._attach_margin(df)
        if "margin_balance" not in df.columns:
            # 無融資資料 → 此策略無法判斷，不發訊
            df["signal"] = "hold"; df["stop_loss"] = np.nan
            df["state"] = "無融資資料"; df["signal_grade"] = ""
            df["entry_reason"] = ""; df["exit_reason"] = ""
            return df
        mb = df["margin_balance"]
        prev = mb.shift(window)
        margin_up = (mb - prev) > (prev * min_up)
        margin_up = margin_up & prev.notna()

        entry_mode = params.get("entry_mode", "大跌當天")
        base = big_drop & price_down & margin_up   # 大跌+融資逆勢加碼
        if entry_mode == "次日翻紅確認":
            # 昨天是訊號、今天翻紅(收>昨收)且融資仍沒跑 → 不接刀，等止穩
            reclaim = (c > c.shift(1)) & (mb >= mb.shift(1))
            buy_cond = base.shift(1).fillna(False) & reclaim
        elif entry_mode == "連續大跌再接":
            # 今天訊號，且近 window 內已有過大跌（第2跌+，更洗到底）
            prior_drop = big_drop.shift(1).rolling(window).max().fillna(0).astype(bool)
            buy_cond = base & prior_drop
        else:  # 大跌當天
            buy_cond = base

        df["signal"]       = "hold"
        df["stop_loss"]    = np.nan
        df["state"]        = "觀察中"
        df["signal_grade"] = ""

        # 停損：今日低點 與 收盤-ATR×倍數 取較高（較緊）
        recent_low = df["Low"].rolling(window + 1).min()
        df["stop_line"] = np.maximum(recent_low, c - atr * atr_stop)

        df.loc[buy_cond, "signal"]       = "buy"
        df.loc[buy_cond, "stop_loss"]    = df.loc[buy_cond, "stop_line"]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"]        = "大跌中融資逆勢加碼"

        # 出場：跌破 5 日均線（趨勢續弱）；其餘交給引擎移動停利
        ma5 = c.rolling(5).mean()
        sell_cond = (c < ma5) & (c.shift(1) >= ma5.shift(1)) & (df["signal"] != "buy")
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[sell_cond, "state"]  = "跌破5日線出場"

        df["entry_reason"] = np.where(buy_cond,
            f"今日跌>{drop_pct*100:.1f}%+近{window}日融資逆勢增", "")
        df["exit_reason"]  = np.where(sell_cond, "跌破MA5", "")
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
            # 保險絲：融資資料落後股價 >7 天＝過期，寧可不出訊號也不用舊資料亂判
            if len(m) and (df.index[-1] - m.index[-1]).days > 7:
                return df
            if "margin_balance" in m.columns:
                df["margin_balance"] = m["margin_balance"].reindex(df.index).ffill().values
        except Exception:
            pass
        return df

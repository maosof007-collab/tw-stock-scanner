"""
strategies/halved_quality.py
股價腰斬的中小型績優股 v1.0

複刻使用者提供的四條件選股（開盤前全部符合）：
  ① 月營收較去年同期成長 ≥ 10%（基本面還在長）
  ② 近 5 年 EPS 平均 ≥ 1 元（有賺錢底子的績優股）
  ③ 近 60 交易日累計跌幅 ≥ 30%（被錯殺/重挫）
  ④ 總市值 < 500 億（中小型，彈性大）
邏輯：好公司被大盤或消息重挫，基本面沒壞 → 撿便宜搏均值回歸。

資料與防未來函數：
  月營收 YoY / 5年EPS 用 FinMind 歷史資料（快取），並模擬公布時滯——
  月營收「次月10日」、年報 EPS「隔年4/1」才可得；市值用「目前股本×當日收盤」
  近似（歷史股本變動忽略，回測早期市值略有誤差）。
出場：交給引擎移動停利（賺1R保本→鎖利）；初始停損 收盤−2×ATR（接刀給寬）。
"""

import numpy as np
import pandas as pd
from strategies.base import BaseStrategy


class HalvedQualityStrategy(BaseStrategy):

    name        = "股價腰斬的中小型績優股"
    description = (
        "月營收YoY≥10% + 近5年EPS平均≥1 + 近60日跌幅≥30% + 市值<500億——"
        "基本面沒壞卻被重挫的中小型績優股，撿便宜搏回歸，移動停利抱波段。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "drop_pct": {
                "type": "float", "default": 30.0, "min": 20.0, "max": 50.0, "step": 5.0,
                "label": "近N日累計跌幅門檻（%）",
            },
            "drop_days": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "跌幅回看交易日數",
            },
            "yoy_min": {
                "type": "float", "default": 10.0, "min": 0.0, "max": 50.0, "step": 5.0,
                "label": "月營收YoY下限（%）",
            },
            "eps5_min": {
                "type": "float", "default": 1.0, "min": 0.0, "max": 5.0, "step": 0.5,
                "label": "近5年EPS平均下限（元）",
            },
            "mcap_max": {
                "type": "float", "default": 500.0, "min": 50.0, "max": 2000.0, "step": 50.0,
                "label": "市值上限（億）",
            },
            "atr_stop": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 3.0, "step": 0.25,
                "label": "初始停損（ATR倍數，接刀給寬）",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        drop_pct = float(params.get("drop_pct", 30.0)) / 100.0
        drop_days = int(params.get("drop_days", 60))
        yoy_min = float(params.get("yoy_min", 10.0))
        eps5_min = float(params.get("eps5_min", 1.0))
        mcap_max = float(params.get("mcap_max", 500.0))
        atr_stop = float(params.get("atr_stop", 2.0))

        c = df["Close"]
        atr = df["ATR"] if "ATR" in df.columns else (c * 0.02)

        def _empty(state):
            df["signal"] = "hold"; df["stop_loss"] = np.nan
            df["state"] = state; df["signal_grade"] = ""
            df["entry_reason"] = ""; df["exit_reason"] = ""
            return df

        # ③ 價格條件先算（不成立就不必打基本面 API，全市場掃描才快）
        drawdown = c / c.shift(drop_days) - 1
        crashed = drawdown <= -drop_pct
        if not crashed.any():
            return _empty("觀察中")

        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        code = ticker.replace(".TWO", "").replace(".TW", "").strip()
        if not code:
            return _empty("無代碼")

        # ①② 基本面（時點對齊 + 公布時滯；FinMind 快取）
        try:
            from fundamentals import revenue_yoy_series, eps5_series, shares_map
            yoy = revenue_yoy_series(code)
            eps5 = eps5_series(code)
            shares = shares_map().get(code, 0.0)
        except Exception:
            return _empty("基本面資料不可用")
        if yoy.empty or eps5.empty or shares <= 0:
            return _empty("基本面資料不足")

        yoy_d = yoy.reindex(df.index, method="ffill")
        eps_d = eps5.reindex(df.index, method="ffill")
        mcap_d = c * shares / 1e8                     # 億（以目前股本近似）

        fund_ok = (yoy_d >= yoy_min) & (eps_d >= eps5_min) & (mcap_d < mcap_max)
        cond = crashed & fund_ok

        # 進場：條件「首次成立」那天（edge），連續符合期間內續跌不重複進
        buy_cond = cond & ~cond.shift(1).fillna(False)

        df["signal"] = "hold"
        df["stop_loss"] = np.nan
        df["state"] = "觀察中"
        df["signal_grade"] = ""
        df.loc[buy_cond, "signal"] = "buy"
        df.loc[buy_cond, "stop_loss"] = (c - atr * atr_stop)[buy_cond]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"] = "腰斬績優股（基本面未壞）"

        df["entry_reason"] = np.where(
            buy_cond,
            f"{drop_days}日跌{drop_pct*100:.0f}%+YoY≥{yoy_min:.0f}%+5yEPS≥{eps5_min}",
            "")
        df["exit_reason"] = ""
        return df

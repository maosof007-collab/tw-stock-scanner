"""
strategies/fi_follow.py
大跌後外資買進（隔日跟單）v1.0

研究驗證（2015-2026 全市場，10 萬筆大跌事件）：
  大跌日外資買超 → 後 5 日平均 +1.00%（外資賣超僅 +0.34%）→ 外資的錢有資訊含量。
  但固定 5 日出場太死（違反「出場越鬆越賺」鐵律），這裡把出場換成
  引擎移動停利（賺 1R 保本→鎖利）+ 跌破月線才主動出，讓贏單抱波段。

進場（訊號平移一日，避免偷看未來——外資買賣超盤後才公布）：
  D 日：跌幅 ≤ -drop_pct 且 外資買超 ≥ min_fi_lots 張 且 成交量 ≥ 500 張
  D+1 日收盤進場（排除 D+1 又近跌停 = 接刀失敗不進）
資料保險絲：法人資料落後股價 >7 天 = 過期，不出訊號。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

INST_DIR = Path("data/institutional")


class FiFollowStrategy(BaseStrategy):

    name        = "大跌後外資買進（隔日跟單）"
    description = (
        "當日大跌但外資逆勢買超 → 隔日收盤跟單。出場交給移動停利抱波段，"
        "跌破月線才主動出（回測鐵律：出場越鬆越賺）。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "drop_pct": {
                "type": "float", "default": 3.5, "min": 2.0, "max": 7.0, "step": 0.5,
                "label": "當日大跌門檻（跌幅%）",
            },
            "min_fi_lots": {
                "type": "int", "default": 1, "min": 1, "max": 3000, "step": 100,
                "label": "外資最少買超（張）",
            },
            "atr_stop": {
                "type": "float", "default": 1.5, "min": 1.0, "max": 3.0, "step": 0.25,
                "label": "初始停損（ATR 倍數）",
            },
            "market_filter": {
                "type": "select",
                "default": "停用（不看大盤）",
                "options": ["停用（不看大盤）", "大盤站上季線才進場", "大盤站上月線才進場"],
                "label": "大環境：大盤多空過濾（研究顯示逐年皆正，預設不擋）",
            },
        }

    def get_audit_config(self) -> dict:
        return {"tests": ["A", "B", "C", "D", "E", "F"],
                "benchmark": "buy_hold", "monkey_n": 300, "wf_split": 0.5}

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        drop_pct = float(params.get("drop_pct", 3.5)) / 100.0
        min_lots = float(params.get("min_fi_lots", 1))
        atr_stop = float(params.get("atr_stop", 1.5))
        market_filter = params.get("market_filter", "停用（不看大盤）")

        c, v = df["Close"], df["Volume"]
        atr = df["ATR"] if "ATR" in df.columns else (c * 0.02)

        df = self._attach_fi(df)
        if "fi_lots" not in df.columns:
            df["signal"] = "hold"; df["stop_loss"] = np.nan
            df["state"] = "無法人資料"; df["signal_grade"] = ""
            df["entry_reason"] = ""; df["exit_reason"] = ""
            return df

        ret_today = c.pct_change()
        # D 日條件：大跌 + 外資逆勢買超 + 流動性
        cond = ((ret_today <= -drop_pct)
                & (df["fi_lots"] >= min_lots)
                & (v >= 500_000))

        # 大盤過濾（預設停用）
        if not market_filter.startswith("停用"):
            cond = cond & self._market_above_ma(df, market_filter)

        # 平移一日：外資買賣超盤後公布 → D+1 收盤才進得去
        # 並排除 D+1 再殺近跌停（接刀失敗，開不了單）
        buy_cond = cond.shift(1).fillna(False) & (c > c.shift(1) * 0.905)

        df["signal"]       = "hold"
        df["stop_loss"]    = np.nan
        df["state"]        = "觀察中"
        df["signal_grade"] = ""

        df.loc[buy_cond, "signal"]       = "buy"
        df.loc[buy_cond, "stop_loss"]    = (c - atr * atr_stop)[buy_cond]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"]        = "大跌後外資買進（隔日跟單）"

        # 出場：跌破月線（其餘交給引擎移動停利：賺1R保本→鎖利只升不降）
        ma20 = c.rolling(20).mean()
        sell_cond = (c < ma20) & (c.shift(1) >= ma20.shift(1)) & (~buy_cond)
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[sell_cond, "state"]  = "跌破月線出場"

        df["entry_reason"] = np.where(buy_cond,
            f"昨日跌>{drop_pct*100:.1f}%+外資買超≥{min_lots:.0f}張", "")
        df["exit_reason"]  = np.where(sell_cond, "跌破MA20", "")
        return df

    # ════════════════════════════════════
    def _attach_fi(self, df: pd.DataFrame) -> pd.DataFrame:
        """外資買賣超（張）。新舊欄位合併；資料過期(>7天)視同無資料。不 ffill。"""
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
                return df          # 保險絲：法人資料過期不亂判
            a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
            b = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
            fi = a.fillna(b) / 1000.0          # 股 → 張
            df["fi_lots"] = fi.reindex(df.index).values   # 缺日=NaN，不填平
        except Exception:
            pass
        return df

    def _market_above_ma(self, df: pd.DataFrame, market_filter: str) -> pd.Series:
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

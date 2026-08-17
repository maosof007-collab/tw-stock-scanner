"""
strategies/freight_momentum.py
運價動能（航運景氣跟蹤）v1.0

使用者觀察(2026-08-14,數據已證實):航運 Q2 起月營收 YoY 翻正加速
(長榮4月+5%→7月+43%,萬海7月+50%,散裝慧洋+56%)——運價是航運股的領先變數。

運價代理(免費可回測):
  散裝 → BDRY(乾散裝運價期貨ETF,≈BDI 代理,2018/03 起)
  貨櫃 → ZIM(以星航運,運價彈性最大的純貨櫃股,2021/01 起)
  美股收盤領先台股一個交易日可知——序列已 shift(1) 防前視。

進場:運價代理「站上60日線且20日動能>0」(景氣向上)時,
     台股航運對應族群個股「突破20日高」→ 買。
出場:運價代理跌破60日線(景氣轉弱)或個股跌破月線;其餘交給移動停利。
只對 貨櫃航運/散裝航運 成分股出訊號,其他股票一律 hold。
"""

import time
import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

MKT_DIR = Path("data/markets")
MKT_DIR.mkdir(parents=True, exist_ok=True)

_CONTAINER = {"2603", "2609", "2615"}
_BULK = {"2637", "2606", "2605", "2612", "2617"}


def _proxy_series(tkr: str) -> pd.Series:
    """美股運價代理日收盤;20h 快取,失敗退舊快取。"""
    p = MKT_DIR / f"{tkr}_us.csv"
    if p.exists() and (time.time() - p.stat().st_mtime) < 20 * 3600:
        try:
            s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
            return pd.to_numeric(s, errors="coerce").dropna()
        except Exception:
            pass
    try:
        import yfinance as yf
        h = yf.Ticker(tkr).history(period="max")["Close"].dropna()
        h.index = pd.to_datetime(h.index).tz_localize(None)
        h.to_csv(p)
        return h
    except Exception:
        if p.exists():
            try:
                s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
                return pd.to_numeric(s, errors="coerce").dropna()
            except Exception:
                pass
        return pd.Series(dtype=float)


class FreightMomentumStrategy(BaseStrategy):

    name        = "運價動能（航運景氣跟蹤）"
    description = (
        "運價代理(散裝=BDRY、貨櫃=ZIM)站上60日線且動能向上時,"
        "航運成分股突破20日高跟進;運價轉弱或跌破月線出。"
        "只掃貨櫃/散裝航運成分股。"
    )
    version = "1.0"

    def get_params(self) -> dict:
        return {
            "proxy_ma": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "運價代理趨勢線（日）",
            },
            "mom_days": {
                "type": "int", "default": 20, "min": 10, "max": 60, "step": 5,
                "label": "運價動能窗口（日）",
            },
            "breakout_days": {
                "type": "int", "default": 20, "min": 10, "max": 60, "step": 5,
                "label": "個股突破 N 日高",
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
        df["signal"] = "hold"
        df["stop_loss"] = np.nan
        df["state"] = "觀察中"
        df["signal_grade"] = ""
        df["entry_reason"] = ""
        df["exit_reason"] = ""

        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        code = ticker.replace(".TWO", "").replace(".TW", "").strip()
        if code in _CONTAINER:
            proxy_tkr, seg = "ZIM", "貨櫃"
        elif code in _BULK:
            proxy_tkr, seg = "BDRY", "散裝"
        else:
            df["state"] = "非航運成分股(本策略不掃)"
            return df

        proxy_ma = int(params.get("proxy_ma", 60))
        mom_days = int(params.get("mom_days", 20))
        brk = int(params.get("breakout_days", 20))
        atr_stop = float(params.get("atr_stop", 1.5))

        us = _proxy_series(proxy_tkr)
        if us.empty or len(us) < proxy_ma + mom_days:
            df["state"] = f"無運價代理資料({proxy_tkr})"
            return df
        # 防前視:美股 D 日收盤在台股 D+1 才可知 → 整條序列先平移一日再對齊台股日曆
        us_ok = (us > us.rolling(proxy_ma).mean()) & (us.pct_change(mom_days) > 0)
        us_ok = us_ok.shift(1).reindex(df.index, method="ffill").fillna(False).astype(bool)

        c, v = df["Close"], df["Volume"]
        atr = df["ATR"] if "ATR" in df.columns else (c * 0.02)
        vol_ok = v.rolling(20).mean() >= 500_000
        breakout = c > c.rolling(brk).max().shift(1)

        buy = (us_ok & breakout & vol_ok).fillna(False)

        df.loc[buy, "signal"] = "buy"
        df.loc[buy, "stop_loss"] = (c - atr * atr_stop)[buy]
        df.loc[buy, "signal_grade"] = "BUY"
        df.loc[buy, "state"] = f"運價向上+突破{brk}日高({seg}:{proxy_tkr})"
        df.loc[buy, "entry_reason"] = f"{seg}運價代理{proxy_tkr}趨勢向上,個股突破{brk}日高"

        ma20 = c.rolling(20).mean()
        freight_off = (~us_ok) & us_ok.shift(1).fillna(False)      # 運價轉弱那天
        below_ma = (c < ma20) & (c.shift(1) >= ma20.shift(1))
        sell = (freight_off | below_ma) & (~buy)
        df.loc[sell, "signal"] = "sell"
        df.loc[sell, "state"] = "運價轉弱/跌破月線出場"
        df.loc[sell, "exit_reason"] = np.where(freight_off[sell], "運價代理跌破趨勢", "跌破MA20")
        return df

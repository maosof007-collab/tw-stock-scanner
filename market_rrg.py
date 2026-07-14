"""
market_rrg.py — 市場資金流向 RRG（全球市場相對輪動）引擎
=================================================================
把各國股市指數對「全球基準」的相對強度 RS 拆成兩軸（中心=100）畫四象限，
看資金在市場間怎麼流：炒韓國？炒台灣？炒美股？還是炒陸股？

與 sector_rrg 同一套 JdK 近似演算，但用「日線」：
  RS = 市場指數 / 基準；RS-Ratio = 100 + zscore(RS, N日)；
  RS-Momentum = 100 + zscore(RS-Ratio 動能, N日)。
  N = RS 視窗（20 短線 / 60 波段 / 120 大層級），對應「20日RS/60日RS/120日RS」講法。

資料：yfinance 抓各國指數，快取 data/markets/{代號}.csv（<20 小時內不重抓）。
注意：各指數以當地貨幣計價，RS 已含匯率效果之外的純指數比價，僅供相對比較。
"""
from __future__ import annotations
import time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data" / "markets"
DATA.mkdir(parents=True, exist_ok=True)
CACHE_HOURS = 20

# 名稱 → yfinance 代號（指數優先；抓不到指數的市場用 ETF 替代）
MARKETS = {
    "美國":     "^GSPC",
    "那斯達克": "^IXIC",
    "費半":     "^SOX",
    "台灣":     "^TWII",
    "南韓":     "^KS11",
    "日本":     "^N225",
    "中國":     "000300.SS",   # 滬深300
    "香港":     "^HSI",
    "印度":     "^NSEI",
    "德國":     "^GDAXI",
    "英國":     "^FTSE",
    "歐洲":     "^STOXX50E",
    "澳洲":     "^AXJO",
    "巴西":     "^BVSP",
    "越南":     "VNM",         # ETF 替代（雅虎無越南指數）
    "新興市場": "EEM",         # ETF
}

BENCHMARKS = {
    "全球 ACWI": "ACWI",
    "美股 S&P500": "^GSPC",
    "台股加權": "^TWII",
}

QUADRANTS = {
    "領先": {"color": "#FF4D6D", "en": "LEADING"},
    "改善": {"color": "#00E5FF", "en": "IMPROVING"},
    "落後": {"color": "#B49BFF", "en": "LAGGING"},
    "弱化": {"color": "#FFC857", "en": "WEAKENING"},
}


def _quadrant(ratio, mom):
    if ratio >= 100 and mom >= 100:
        return "領先"
    if ratio < 100 and mom >= 100:
        return "改善"
    if ratio < 100 and mom < 100:
        return "落後"
    return "弱化"


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("^", "_").replace(".", "-")
    return DATA / f"{safe}.csv"


def _fetch_close(ticker: str, period: str = "2y") -> pd.Series | None:
    """日收盤序列；本地快取 20 小時，逾時才重抓 yfinance。"""
    p = _cache_path(ticker)
    if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_HOURS * 3600:
        try:
            df = pd.read_csv(p)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            s = df.dropna(subset=["date"]).set_index("date")["close"]
            s = pd.to_numeric(s, errors="coerce").dropna()
            if len(s) > 50:
                return s
        except Exception:
            pass
    try:
        import yfinance as yf
        raw = yf.download(ticker, period=period, interval="1d",
                          auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            raise ValueError("empty")
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):   # 新版 yfinance MultiIndex
            close = close.iloc[:, 0]
        s = pd.to_numeric(close, errors="coerce").dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.rename_axis("date").rename("close").reset_index().to_csv(p, index=False)
        return s
    except Exception:
        # 抓失敗但有舊快取 → 用舊的
        if p.exists():
            try:
                df = pd.read_csv(p)
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                s = df.dropna(subset=["date"]).set_index("date")["close"]
                return pd.to_numeric(s, errors="coerce").dropna()
            except Exception:
                return None
        return None


def build_market_rrg(rs_win: int = 60, tail_days: int = 30,
                     bench_ticker: str = "ACWI"):
    """回傳 (points_df, tails_dict, asof_date)。
    points_df: 市場/RS-Ratio/RS-Momentum/象限；
    tails: {市場: DataFrame(date, ratio, mom)}（近 tail_days 個交易日）。"""
    bench = _fetch_close(bench_ticker)
    if bench is None or len(bench) < rs_win + tail_days + 10:
        return pd.DataFrame(), {}, None

    points, tails, asof = [], {}, None
    for name, tk in MARKETS.items():
        if tk == bench_ticker:
            continue
        s = _fetch_close(tk)
        if s is None:
            continue
        df = pd.concat([s.rename("mkt"), bench.rename("bench")], axis=1)
        df = df.ffill().dropna()
        if len(df) < rs_win + tail_days + 5:
            continue
        rs = df["mkt"] / df["bench"]
        rs = rs / rs.iloc[0] * 100
        m = rs.rolling(rs_win).mean()
        sd = rs.rolling(rs_win).std()
        rs_ratio = 100 + (rs - m) / sd.replace(0, np.nan)
        roc = rs_ratio.diff()
        rm = roc.rolling(rs_win).mean()
        rsd = roc.rolling(rs_win).std()
        rs_mom = 100 + (roc - rm) / rsd.replace(0, np.nan)

        both = pd.concat([rs_ratio.rename("ratio"), rs_mom.rename("mom")], axis=1).dropna()
        if both.empty:
            continue
        tail = both.tail(tail_days)
        cur = tail.iloc[-1]
        points.append({
            "市場": name, "代號": tk,
            "RS-Ratio": round(float(cur["ratio"]), 2),
            "RS-Momentum": round(float(cur["mom"]), 2),
            "象限": _quadrant(cur["ratio"], cur["mom"]),
        })
        tails[name] = tail.rename_axis("date").reset_index()
        d = tail.index[-1]
        asof = d if asof is None or d > asof else asof

    pts = pd.DataFrame(points)
    if not pts.empty:
        order = {"領先": 0, "改善": 1, "弱化": 2, "落後": 3}
        pts["_o"] = pts["象限"].map(order)
        pts = pts.sort_values(["_o", "RS-Ratio"], ascending=[True, False])\
                 .drop(columns="_o").reset_index(drop=True)
    return pts, tails, asof

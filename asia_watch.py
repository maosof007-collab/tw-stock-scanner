"""
asia_watch.py — 亞洲大盤對照（台/韓/日 + 港/陸）
=================================================================
監測「同一批資金在亞洲怎麼移動」：
  · 各市場 20 日報酬、距近 60 日高點回落
  · 跨市場 20 日報酬差（韓-台、日-台）：現值 / 歷史百分位 / z 分數
    —— 極端值=「罕見狀態」的紀錄，不是方向預測。
歷史統計用全期間日線（yfinance period=max，快取 20 小時）。
"""
from __future__ import annotations
import time
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data" / "markets"
DATA.mkdir(parents=True, exist_ok=True)
CACHE_HOURS = 20

MARKETS = {"台股": "^TWII", "韓國": "^KS11", "日本": "^N225",
           "香港": "^HSI", "中國": "000300.SS"}
SPREADS = [("韓國", "台股"), ("日本", "台股")]


def _long_close(ticker: str) -> pd.Series | None:
    safe = ticker.replace("^", "_").replace(".", "-")
    p = DATA / f"long_{safe}.csv"
    if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_HOURS * 3600:
        try:
            d = pd.read_csv(p)
            d["date"] = pd.to_datetime(d["date"])
            return d.set_index("date")["close"].dropna()
        except Exception:
            pass
    try:
        import yfinance as yf
        raw = yf.download(ticker, period="max", interval="1d",
                          auto_adjust=True, progress=False)["Close"]
        if isinstance(raw, pd.DataFrame):
            raw = raw.iloc[:, 0]
        s = pd.to_numeric(raw, errors="coerce").dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.rename_axis("date").rename("close").reset_index().to_csv(p, index=False)
        return s
    except Exception:
        if p.exists():
            try:
                d = pd.read_csv(p)
                d["date"] = pd.to_datetime(d["date"])
                return d.set_index("date")["close"].dropna()
            except Exception:
                pass
        return None


def asia_snapshot() -> dict:
    """回傳 {asof, markets:[...], spreads:[...]}；抓不到資料的市場略過。"""
    closes = {}
    for name, tk in MARKETS.items():
        s = _long_close(tk)
        if s is not None and len(s) > 300:
            closes[name] = s
    if "台股" not in closes:
        return {"asof": None, "markets": [], "spreads": []}

    mkts = []
    for name, s in closes.items():
        chg20 = (s.iloc[-1] / s.iloc[-21] - 1) * 100 if len(s) > 21 else 0.0
        hi60 = s.tail(60).max()
        mkts.append({"name": name, "last": float(s.iloc[-1]),
                     "chg20": round(float(chg20), 1),
                     "dd60": round(float((s.iloc[-1] / hi60 - 1) * 100), 1),
                     "date": str(s.index[-1].date())})

    spreads = []
    asof = None
    for a, b in SPREADS:
        if a not in closes or b not in closes:
            continue
        # 成對對齊（不跟其他市場取交集，保留最長共同歷史）
        pair_df = pd.concat([closes[a].rename("a"), closes[b].rename("b")],
                            axis=1).ffill().dropna()
        r20 = pair_df.pct_change(20) * 100
        sp = (r20["a"] - r20["b"]).dropna()
        if len(sp) < 500:
            continue
        cur = float(sp.iloc[-1])
        asof = str(pair_df.index[-1].date())
        spreads.append({
            "pair": f"{a}−{b}", "cur": round(cur, 1),
            "pctile": round(float((sp < cur).mean() * 100), 2),
            "z": round(float((cur - sp.mean()) / sp.std()), 1),
            "n": int(len(sp)),
        })
    return {"asof": asof, "markets": mkts, "spreads": spreads}

"""
trailing.py — 移動停利（與 market_backtest 引擎同規則：保本 → 鎖利）
=================================================================
規則（來自你的策略引擎 market_backtest.py:161-163）：
  · 初始停損 = 進場價 − 1.5×ATR(14)（若使用者已自設停損，用自設的）
  · 當獲利 ≥ 1×初始風險 → 開始移動（第一次剛好抬到進場價=保本）
  · 移動後停損 = max(舊停損, 現價 − 1.5×ATR)，只升不降
純 pandas，直接讀 data/{code}.csv，背景守護也能呼叫（不依賴 streamlit）。
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"
ATR_PER = 14
ATR_MULT = 1.5


def _load(ticker: str):
    code = str(ticker).replace(".TWO", "").replace(".TW", "").strip()
    for suf in (".TW", ".TWO"):
        p = DATA / f"{code}{suf}.csv"
        if p.exists():
            df = pd.read_csv(p)
            df.columns = [c.lower() for c in df.columns]
            dc = "date" if "date" in df.columns else df.columns[0]
            df = df.rename(columns={dc: "date"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            for c in ("open", "high", "low", "close"):
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            return df.dropna(subset=["close"])
    return None


def _atr(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(ATR_PER).mean()


def trailing_stop(ticker: str, entry_price: float, entry_date,
                  init_stop: float = 0.0, atr_mult: float = ATR_MULT) -> dict:
    """
    回傳 dict:
      stop      動態停損價（打到就賣）
      triggered 是否已達保本（開始鎖利）
      lock_pct  鎖住的獲利%（停損相對進場）
      state     顯示文字：⏳持有中(初始停損) / 🔒持有中(已保本) / 📈持有中(鎖利+X%)
    """
    ep = float(entry_price or 0)
    df = _load(ticker)
    if df is None or ep <= 0:
        return {"stop": float(init_stop or 0), "triggered": False, "lock_pct": 0.0, "state": "—"}

    df = df.copy()
    df["atr"] = _atr(df)
    df = df.set_index("date")
    ed = pd.to_datetime(entry_date, errors="coerce")

    # 初始停損：優先用使用者設的；沒設就 進場 − 1.5×ATR(進場時)
    atr_hist = df.loc[df.index <= ed, "atr"].dropna() if ed is not pd.NaT else df["atr"].dropna()
    a0 = atr_hist.iloc[-1] if len(atr_hist) else (df["atr"].dropna().iloc[-1]
                                                  if df["atr"].notna().any() else ep * 0.05)
    sl = float(init_stop) if init_stop and init_stop > 0 else ep - atr_mult * a0
    risk = ep - sl

    seg = df[df.index >= ed] if ed is not pd.NaT else df.tail(1)
    trig = False
    for _, row in seg.iterrows():
        cv, av = row["close"], row["atr"]
        if pd.isna(cv):
            continue
        if not trig and risk > 0 and cv >= ep + risk:
            trig = True
        if trig and av > 0:
            sl = max(sl, cv - atr_mult * av)

    lock = (sl - ep) / ep * 100 if ep else 0.0
    if trig:
        state = "🔒 持有中（已保本）" if abs(lock) < 0.6 else f"📈 持有中（鎖利 {lock:+.1f}%）"
    else:
        state = "⏳ 持有中（初始停損）"
    return {"stop": round(sl, 2), "triggered": trig, "lock_pct": round(lock, 2), "state": state}

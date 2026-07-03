"""
data_provider.py — 統一資料存取層（已接 tw_backtest 真實資料）
============================================
原為假資料 Demo，現全部接到本專案既有資料：
  - 股價 K 線      → data/{code}.TW.csv / .TWO.csv（yfinance 下載）
  - 三大法人        → data/institutional/{code}_inst.csv（TWSE）
  - 大戶/散戶持股   → data/tdcc/{code}_tdcc.csv（集保股權分散）
  - 主力/融資       → data/margin/{code}_margin.csv（TWSE 融資融券）
  - 研究報告        → reports.db（SQLite，report_db.py）
UI 完全不變。分點(branch)台股無免費逐筆來源 → 回傳空表並提示。
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"
INST = DATA / "institutional"
TDCC = DATA / "tdcc"
MARGIN = DATA / "margin"


# ----------------------------------------------------------------------
# 股票池 / 名稱（來自 data/stock_list.csv）
# ----------------------------------------------------------------------
@lru_cache(maxsize=1)
def _stock_list() -> pd.DataFrame:
    p = DATA / "stock_list.csv"
    if not p.exists():
        return pd.DataFrame(columns=["code", "name", "sector"])
    df = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
    df["code"] = df["ticker"].str.replace(".TWO", "", regex=False)\
                             .str.replace(".TW", "", regex=False).str.strip()
    return df[["code", "name", "sector"]].dropna(subset=["code"])


_STOCK_UNIVERSE = [(r.code, r.name, r.sector) for r in _stock_list().itertuples()]


def stock_name(code: str) -> str:
    code = str(code).replace(".TWO", "").replace(".TW", "").strip()
    m = _stock_list()
    hit = m[m["code"] == code]
    return hit.iloc[0]["name"] if not hit.empty else code


def _price_path(code: str) -> Path | None:
    code = str(code).replace(".TWO", "").replace(".TW", "").strip()
    for suf in (".TW", ".TWO"):
        p = DATA / f"{code}{suf}.csv"
        if p.exists():
            return p
    return None


def _inst_net_cols(df: pd.DataFrame) -> dict:
    """找出 外資/投信/法人 淨買賣超欄位（欄名可能是中文）"""
    out = {}
    for c in df.columns:
        if ("外" in c and "買賣超" in c) and "外資自營商" not in c.replace("不含外資自營商", ""):
            out.setdefault("外資", c)
    if "外資" not in out:
        for c in df.columns:
            if "外陸資買賣超" in c or ("外資" in c and "買賣超" in c):
                out["外資"] = c; break
    if "it_net" in df.columns:
        out["投信"] = "it_net"
    if "total_net" in df.columns:
        out["法人"] = "total_net"
    return out


# ======================================================================
# 1. K 線 + 均線
# ======================================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_ohlcv(ticker: str, period_days: int = 400) -> pd.DataFrame:
    """日 K 線：date, open, high, low, close, volume, ma30, ma60"""
    p = _price_path(ticker)
    if p is None:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close",
                                     "volume", "ma30", "ma60"])
    df = pd.read_csv(p)
    df.columns = [c.lower() for c in df.columns]
    dc = "date" if "date" in df.columns else df.columns[0]
    df = df.rename(columns={dc: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"]).tail(period_days).reset_index(drop=True)
    df["ma30"] = df["close"].rolling(30).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    return df


# ======================================================================
# 2. 籌碼排行（近 N 日三大法人 / 大戶）
# ======================================================================
@st.cache_data(ttl=900, show_spinner="計算籌碼排行中（首次約20秒，當日後續秒開）…")
def get_ranking(days: int = 5, metric: str = "外資買超%", top_n: int = 50) -> pd.DataFrame:
    """
    個股籌碼排行：ticker, name, industry, value(買超佔20日均量%), legal_action
    value = 近 N 日累積淨買(張) ÷ 20日均量(張) × 100
    大戶買進% → 改用 TDCC 大戶持股率近 N 週變化
    每日磁碟快取：data/_rank_{metric}_{days}_{date}.csv（一天只算一次）
    """
    key = {"外資買超%": "外資", "投信買超%": "投信", "主力買超%": "法人",
           "大戶買進%": "大戶"}.get(metric, "外資")
    cache_f = DATA / f"_rank_{key}_{days}_{dt.date.today()}.csv"
    if cache_f.exists():
        try:
            return pd.read_csv(cache_f, encoding="utf-8-sig", dtype={"ticker": str})
        except Exception:
            pass
    rows = []
    for code, name, ind in _STOCK_UNIVERSE:
        try:
            if key == "大戶":
                val = _tdcc_big_change(code, weeks=max(1, days // 5))
                if val is None:
                    continue
            else:
                ip = INST / f"{code}_inst.csv"
                pp = _price_path(code)
                if not ip.exists() or pp is None:
                    continue
                idf = pd.read_csv(ip)
                cols = _inst_net_cols(idf)
                if key not in cols:
                    continue
                net = pd.to_numeric(idf[cols[key]], errors="coerce").fillna(0).tail(days).sum()
                vol = pd.read_csv(pp, usecols=lambda c: c.lower() in ("volume",))
                vol.columns = [c.lower() for c in vol.columns]
                vma = pd.to_numeric(vol["volume"], errors="coerce").tail(20).mean()
                if not vma or vma <= 0:
                    continue
                val = round(net / vma * 100, 2)
            rows.append({"ticker": code, "name": name, "industry": ind,
                         "value": float(val),
                         "legal_action": "法人買超" if val > 0 else "法人賣超"})
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=["ticker", "name", "industry", "value", "legal_action"])
    df = pd.DataFrame(rows).drop_duplicates("ticker")
    df = df.sort_values("value", ascending=False).head(top_n).reset_index(drop=True)
    try:
        df.to_csv(cache_f, index=False, encoding="utf-8-sig")
    except Exception:
        pass
    return df


# ======================================================================
# 3. 籌碼累積線
# ======================================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_chip_flows(ticker: str, period_days: int = 400) -> pd.DataFrame:
    """date, 外資, 投信, 法人(累積買賣超 張), 大戶, 散戶(持股%), 主力(融資累積 張)"""
    code = str(ticker).replace(".TWO", "").replace(".TW", "").strip()
    base = get_ohlcv(code, period_days)[["date"]].copy()
    if base.empty:
        base = pd.DataFrame({"date": pd.bdate_range(end=dt.date.today(), periods=period_days)})

    # 三大法人累積（張）
    ip = INST / f"{code}_inst.csv"
    for label in ("外資", "投信", "法人"):
        base[label] = 0.0
    if ip.exists():
        idf = pd.read_csv(ip)
        if "date" in idf.columns:
            idf["date"] = pd.to_datetime(idf["date"], errors="coerce")
            cols = _inst_net_cols(idf)
            for label, col in cols.items():
                s = idf[["date", col]].dropna()
                s[col] = pd.to_numeric(s[col], errors="coerce").fillna(0) / 1000.0  # 股→張
                s = s.set_index("date")[col].reindex(base["date"]).fillna(0)
                base[label] = s.cumsum().values

    # 大戶 / 散戶 持股%（TDCC）—— 只在有資料的區間畫，缺資料留 NaN（不回填0造成假跳空）
    base["大戶"], base["散戶"] = np.nan, np.nan
    big_retail = _tdcc_series(code)
    if big_retail is not None:
        for label in ("大戶", "散戶"):
            # 對齊到交易日（ffill 在 TDCC 起始日之後才有值，之前保持 NaN）
            base[label] = big_retail[label].reindex(base["date"], method="ffill").values

    # 主力：融資餘額（張，絕對值）—— 缺資料留 NaN
    base["主力"] = np.nan
    mp = MARGIN / f"{code}_margin.csv"
    if mp.exists():
        m = pd.read_csv(mp)
        if "date" in m.columns and "margin_balance" in m.columns:
            m["date"] = pd.to_datetime(m["date"], errors="coerce")
            bal = pd.to_numeric(m.set_index("date")["margin_balance"], errors="coerce")
            base["主力"] = bal.reindex(base["date"], method="ffill").values
    return base


@st.cache_data(ttl=300, show_spinner=False)
def get_foreign_daily(ticker: str, period_days: int = 400,
                      spike_mult: float = 3.0, vol_window: int = 20) -> pd.DataFrame:
    """每日外資買賣超(張) + 佔當日成交量% + 突增標記"""
    code = str(ticker).replace(".TWO", "").replace(".TW", "").strip()
    px = get_ohlcv(code, period_days)
    cols = ["date", "foreign_net", "volume", "foreign_pct", "is_spike", "abs_net"]
    if px.empty:
        return pd.DataFrame(columns=cols)
    out = px[["date", "volume"]].copy()
    out["volume"] = (out["volume"] / 1000).round().astype(int)   # 張
    out["foreign_net"] = 0
    ip = INST / f"{code}_inst.csv"
    if ip.exists():
        idf = pd.read_csv(ip)
        if "date" in idf.columns:
            idf["date"] = pd.to_datetime(idf["date"], errors="coerce")
            c = _inst_net_cols(idf).get("外資")
            if c:
                s = idf[["date", c]].dropna()
                s[c] = pd.to_numeric(s[c], errors="coerce").fillna(0) / 1000.0
                out["foreign_net"] = s.set_index("date")[c].reindex(out["date"]).fillna(0).round().astype(int).values
    out["foreign_pct"] = np.where(out["volume"] > 0,
                                  out["foreign_net"] / out["volume"] * 100, 0).round(2)
    out["abs_net"] = out["foreign_net"].abs()
    avg = out["abs_net"].rolling(vol_window, min_periods=5).mean()
    out["is_spike"] = out["abs_net"] > (avg * spike_mult)
    return out[cols]


def get_branch_flows(ticker: str, days: int = 5, side: str = "買") -> pd.DataFrame:
    """分點進出 —— 台股無免費逐筆分點來源，回傳空表（UI 會顯示空）。"""
    return pd.DataFrame(columns=["branch", "net_lots", "pct"])


# ----------------------------------------------------------------------
# TDCC 大戶/散戶 工具
# ----------------------------------------------------------------------
@lru_cache(maxsize=512)
def _tdcc_series(code: str):
    """回傳 DataFrame(index=date, 大戶%, 散戶%)；無檔回 None"""
    p = TDCC / f"{code}_tdcc.csv"
    if not p.exists():
        return None
    try:
        raw = pd.read_csv(p)
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        raw["level"] = pd.to_numeric(raw["level"], errors="coerce")
        raw["pct"] = pd.to_numeric(raw["pct"], errors="coerce")
        # 排除「合計」級距（pct≈100 那層）
        piv = raw.pivot_table(index="date", columns="level", values="pct", aggfunc="first")
        levels = [c for c in piv.columns if c <= 15]
        retail = [l for l in levels if l <= 5]      # 散戶：小持股級距
        big    = [l for l in levels if l >= 12]     # 大戶：大持股級距
        out = pd.DataFrame(index=piv.index)
        out["散戶"] = piv[retail].sum(axis=1) if retail else 0
        out["大戶"] = piv[big].sum(axis=1) if big else 0
        return out.sort_index()
    except Exception:
        return None


def _tdcc_big_change(code: str, weeks: int = 1):
    s = _tdcc_series(code)
    if s is None or len(s) < weeks + 1:
        return None
    return round(float(s["大戶"].iloc[-1] - s["大戶"].iloc[-1 - weeks]), 2)


# ======================================================================
# 4. 研究報告（SQLite，原樣保留）
# ======================================================================
import report_db as rdb
rdb.init_db()


def get_reports(ticker=None, broker=None, start=None, end=None,
                keyword=None, limit: int = 50) -> pd.DataFrame:
    cols = ["date", "ticker", "name", "broker", "rtype",
            "target_price", "rating", "close_price", "title", "id"]
    rows = rdb.list_reports(ticker=ticker, broker=broker, keyword=keyword,
                            start=start, end=end, limit=limit)
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame([{
        "date": r["report_date"], "ticker": r["ticker"], "name": r["name"],
        "broker": r["broker"], "rtype": r["report_type"],
        "target_price": r["target_price"], "rating": r["rating"],
        "close_price": r["close_price"], "title": r["title"], "id": r["id"],
    } for r in rows])
    return df[cols]


def get_report_detail(report_id=None, ticker=None, broker=None, report_date=None):
    d = rdb.get_report(report_id=report_id, ticker=ticker,
                       broker=broker, report_date=report_date)
    if not d:
        return None
    return {
        "broker": d["broker"], "report_type": d["report_type"],
        "date": d["report_date"], "ticker": d["ticker"], "name": d["name"],
        "industry": d["industry"], "rating": d["rating"],
        "close_price": d["close_price"], "target_price": d["target_price"],
        "report_basis": d["report_basis"],
        "trade_data": d["trade_data"], "financial_data": d["financial_data"],
        "esg": d["esg"],
    }


def get_sentiment(ticker: str, months: int = 3):
    return rdb.get_sentiment(ticker, months=months)


def add_report(r: dict) -> int:
    return rdb.add_report(r)

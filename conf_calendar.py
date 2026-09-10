"""
conf_calendar.py — 法說會行事曆(MOPS 法人說明會一覽,上市+上櫃)
================================================================
來源:mopsov ajax_t100sb02_1(月表)。快取 data/_conf_calendar.csv(12h)。
「法說行情」欄=法說前 20 交易日漲跌%(醞釀度)——行情常走在法說前。
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "_conf_calendar.csv"
_HDR = {"User-Agent": "Mozilla/5.0"}


def _fetch_month(typek: str, roc_year: int, month: int) -> pd.DataFrame:
    r = requests.post("https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1",
                      data={"encodeURIComponent": "1", "step": "1", "firstin": "1",
                            "off": "1", "TYPEK": typek,
                            "year": str(roc_year), "month": f"{month:02d}"},
                      timeout=40, headers=_HDR)
    r.encoding = "utf-8"
    try:
        tbl = max(pd.read_html(io.StringIO(r.text)), key=len)
    except Exception:
        return pd.DataFrame()
    tbl.columns = [c[0] if isinstance(c, tuple) else c for c in tbl.columns]
    tbl = tbl.loc[:, ~pd.Index(tbl.columns).duplicated()]
    need = {"公司代號": "code", "公司名稱": "name", "召開法人說明會日期": "roc_date",
            "召開法人說明會時間": "time", "法人說明會擇要訊息": "summary"}
    keep = {k: v for k, v in need.items() if k in tbl.columns}
    df = tbl[list(keep)].rename(columns=keep)
    df = df[df["code"].astype(str).str.match(r"^\d{4,6}$", na=False)].copy()
    # 民國 115/09/11 → 2026-09-11
    def _d(s):
        try:
            y, m, d = str(s).split("/")
            return f"{int(y) + 1911}-{int(m):02d}-{int(d):02d}"
        except Exception:
            return None
    df["date"] = df["roc_date"].map(_d)
    df["market"] = "上市" if typek == "sii" else "上櫃"
    return df.dropna(subset=["date"])[["date", "time", "code", "name", "summary", "market"]]


def refresh(force: bool = False) -> pd.DataFrame:
    """本月+下月,上市+上櫃。12h 快取。"""
    if CACHE.exists() and not force and (time.time() - CACHE.stat().st_mtime) < 12 * 3600:
        return pd.read_csv(CACHE, dtype=str)
    t = now_tw()
    roc, m = t.year - 1911, t.month
    nroc, nm = (roc + 1, 1) if m == 12 else (roc, m + 1)
    frames = []
    for typek in ("sii", "otc"):
        for ry, mm in [(roc, m), (nroc, nm)]:
            try:
                frames.append(_fetch_month(typek, ry, mm))
                time.sleep(1.5)
            except Exception:
                continue
    df = pd.concat([f for f in frames if f is not None and not f.empty],
                   ignore_index=True) if frames else pd.DataFrame()
    if not df.empty:
        df = df.drop_duplicates(subset=["date", "code"]).sort_values(["date", "time"])
        df.to_csv(CACHE, index=False, encoding="utf-8-sig")
    return df


def _pre_runup(code: str) -> float | None:
    """法說前行情醞釀度:近 20 交易日漲跌%。"""
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            d = pd.read_csv(p, usecols=["Date", "Close"]).dropna().sort_values("Date")
            cl = pd.to_numeric(d["Close"], errors="coerce").dropna()
            if len(cl) > 21:
                return round(float(cl.iloc[-1] / cl.iloc[-21] - 1) * 100, 1)
    return None


def upcoming(days: int = 30) -> pd.DataFrame:
    """今天起 N 天內的法說,照時間排,附近20日漲跌%(醞釀度)。"""
    df = refresh()
    if df.empty:
        return df
    today = f"{now_tw():%Y-%m-%d}"
    end = f"{now_tw() + pd.Timedelta(days=days):%Y-%m-%d}"
    up = df[(df["date"] >= today) & (df["date"] <= end)].copy()
    up["近20日%"] = up["code"].map(_pre_runup)
    return up.sort_values(["date", "time"]).reset_index(drop=True)


def just_done(days: int = 10) -> pd.DataFrame:
    """剛開完的法說(簡報應已上 MOPS)。"""
    df = refresh()
    if df.empty:
        return df
    today = f"{now_tw():%Y-%m-%d}"
    start = f"{now_tw() - pd.Timedelta(days=days):%Y-%m-%d}"
    d = df[(df["date"] < today) & (df["date"] >= start)].copy()
    return d.sort_values("date", ascending=False).reset_index(drop=True)

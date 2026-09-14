"""
taifex_flow.py — 期交所三大法人期貨部位(選擇權判讀的定案拼圖)
=================================================================
教訓(2026-09-14 選擇權羅生門):BC/SC/BP/SP 四腿不含期貨部位就是羅生門
——同一張 BC 淨買,期貨偏多=進攻,期貨深空=保險帽。
本模組抓外資台指期淨未平倉,快取 data/_taifex_fi.csv(進 git)。
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "_taifex_fi.csv"
_HDR = {"User-Agent": "Mozilla/5.0"}


def fetch_fi_futures(days: int = 10) -> pd.DataFrame:
    """外資台指期(TXF)近 N 日淨未平倉。快取 6h。"""
    if CACHE.exists() and (time.time() - CACHE.stat().st_mtime) < 6 * 3600:
        c = pd.read_csv(CACHE)
        if not c.empty:
            return c.tail(days)
    end = now_tw()
    start = end - pd.Timedelta(days=days + 8)
    r = requests.post("https://www.taifex.com.tw/cht/3/futContractsDateDown",
                      data={"queryStartDate": f"{start:%Y/%m/%d}",
                            "queryEndDate": f"{end:%Y/%m/%d}",
                            "commodityId": "TXF"},
                      timeout=40, headers=_HDR)
    d = pd.read_csv(io.BytesIO(r.content), encoding="big5")
    fi = d[d["身份別"].astype(str).str.contains("外資")].copy()
    out = pd.DataFrame({
        "date": fi["日期"].str.replace("/", "-"),
        "淨未平倉口數": pd.to_numeric(fi["多空未平倉口數淨額"], errors="coerce"),
    }).dropna()
    out["日增減"] = out["淨未平倉口數"].diff()
    out.to_csv(CACHE, index=False, encoding="utf-8-sig")
    return out.tail(days)


def fi_verdict() -> str:
    """外資期貨姿勢一句話(給選擇權表當背景)。"""
    try:
        d = fetch_fi_futures(6)
        net = int(d["淨未平倉口數"].iloc[-1])
        chg = d["日增減"].iloc[-1]
        chg_s = f"{chg:+,.0f}" if pd.notna(chg) else "?"
        if net < -50000:
            pose = "深度淨空(避險常態偏深)"
        elif net < -15000:
            pose = "中度淨空"
        elif net > 15000:
            pose = "淨多"
        else:
            pose = "中性"
        act = "回補中" if (pd.notna(chg) and chg > 1500) else ("加空中" if (pd.notna(chg) and chg < -1500) else "持平")
        return f"外資台指期淨未平倉 {net:+,} 口({pose}),當日 {chg_s} 口({act})"
    except Exception as e:
        return f"期貨部位讀取失敗:{e}"

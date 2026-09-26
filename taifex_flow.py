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
    """外資台指期(TXF)淨未平倉。
    2026-09:舊 CSV 下載端點被期交所擋掉(回HTML) → 改走 OpenAPI(僅回最新一日),
    每日抓一次併入快取累積歷史;快取 6h。"""
    old = pd.read_csv(CACHE) if CACHE.exists() else pd.DataFrame()
    if CACHE.exists() and (time.time() - CACHE.stat().st_mtime) < 6 * 3600 and len(old):
        return old.tail(days)
    try:
        import json
        import urllib.request
        req = urllib.request.Request(
            "https://openapi.taifex.com.tw/v1/"
            "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate",
            headers=_HDR)
        rows = json.load(urllib.request.urlopen(req, timeout=30))
        fi = [r for r in rows if r.get("ContractCode") == "臺股期貨"
              and "外資" in str(r.get("Item"))]
        if fi:
            r0 = fi[0]
            ymd = str(r0["Date"])
            new = pd.DataFrame([{
                "date": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}",
                "淨未平倉口數": float(r0["OpenInterest(Net)"]),
            }])
            merged = pd.concat([old[["date", "淨未平倉口數"]] if len(old) else old, new],
                               ignore_index=True)
            merged = (merged.drop_duplicates(subset=["date"], keep="last")
                            .sort_values("date").reset_index(drop=True))
            merged["日增減"] = merged["淨未平倉口數"].diff()
            merged.to_csv(CACHE, index=False, encoding="utf-8-sig")
            return merged.tail(days)
    except Exception:
        pass
    if len(old):                          # 抓不到就用舊快取(不論多舊)
        return old.tail(days)
    raise RuntimeError("期交所 OpenAPI 無回應且無快取")


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

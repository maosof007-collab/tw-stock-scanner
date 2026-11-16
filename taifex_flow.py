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
    # 快取閘門看「內容有沒有到應到日」,不看檔案時間。舊版「6 小時內不重抓」:
    # 15:10 抓到的還是前一日(期交所晚間才更新)→ 檔案時間被刷新 → 19:41 那次直接跳過,
    # 整晚停在前一日(2026-11-12 全站盤點抓到)。20 分鐘內不重打只是禮貌性限流。
    if len(old):
        try:
            from check_data_current import latest_expected_trading_day
            fresh = str(old["date"].max())[:10] >= f"{latest_expected_trading_day():%Y-%m-%d}"
        except Exception:
            fresh = False
        if fresh or (time.time() - CACHE.stat().st_mtime) < 20 * 60:
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


def _fetch_day(day: str) -> float | None:
    """期交所網站「三大法人-區分各期貨契約」歷史查詢:指定日的外資台指期淨未平倉口數。
    day='YYYY-MM-DD';當天還沒公布或非交易日回 None。OpenAPI 只給最新一日,補洞要靠這個。"""
    r = requests.post("https://www.taifex.com.tw/cht/3/futContractsDate",
                      data={"queryType": "1", "goDay": "", "doQuery": "1", "dateaddcnt": "",
                            "queryDate": day.replace("-", "/"), "commodityId": "TXF"},
                      headers=_HDR, timeout=30)
    if r.status_code != 200 or day.replace("-", "/") not in r.text:   # 查無資料時頁面會回別的日期或空表
        return None
    for tb in pd.read_html(io.StringIO(r.text)):
        if tb.shape[1] < 15:
            continue
        tb.columns = range(tb.shape[1])
        hit = tb[tb[1].astype(str).str.contains("臺股期貨") & tb[2].astype(str).str.contains("外資")]
        if len(hit):
            return float(str(hit.iloc[0, 13]).replace(",", ""))       # 未平倉餘額-多空淨額-口數
    return None


def backfill(max_days: int = 25) -> list[str]:
    """補齊快取裡缺的交易日(以大盤日線的日期為準),回傳這次補上的日期。
    2026-11-16:快取 33 個交易日缺了 14 天——每日流程只要有一天沒在公布後跑到,那天就永遠缺,
    而且「日增減」會變成跨兩天的差。每次 fetch_fi_futures 後都會跑一次,最多補 max_days 天。"""
    old = pd.read_csv(CACHE) if CACHE.exists() else pd.DataFrame(columns=["date", "淨未平倉口數"])
    bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", usecols=["Date"])["Date"].astype(str).str[:10]
    have = set(old["date"].astype(str))
    start = min(have) if have else bm.iloc[-30]
    miss = [d for d in bm[bm >= start] if d not in have][-max_days:]
    _now = now_tw()
    if _now.hour < 15:                      # 當天的未平倉 15 點後才公布;之前查會拿到上一日的表
        miss = [d for d in miss if d != f"{_now:%Y-%m-%d}"]
    got = []
    for d in miss:
        try:
            v = _fetch_day(d)
        except Exception:
            v = None
        if v is not None:
            got.append({"date": d, "淨未平倉口數": v})
        time.sleep(1.5)                                             # 期交所網站限流
    if got:
        m = pd.concat([old[["date", "淨未平倉口數"]], pd.DataFrame(got)], ignore_index=True)
        m = m.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
        m["日增減"] = m["淨未平倉口數"].diff()
        m.to_csv(CACHE, index=False, encoding="utf-8-sig")
    return [g["date"] for g in got]


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

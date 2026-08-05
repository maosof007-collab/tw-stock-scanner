"""
fetch_daily_official.py — 官方源當日快速更新（取代 Yahoo 的每日增量）
=================================================================
Yahoo 的台股當日日K「不保證」傍晚可得（有時 22:30 後才出）；
證交所/櫃買中心官方盤後資料 **約 14:00~15:00 就公布**，且整批下載：

  上市個股  TWSE  exchangeReport/STOCK_DAY_ALL（CSV，全部個股 OHLCV）
  上櫃個股  TPEX  openapi tpex_mainboard_daily_close_quotes（JSON）
  加權指數  TWSE  exchangeReport/MI_INDEX（發行量加權股價指數 OHLC）

把「今天這一根K」直接 append 到 data/*.csv 與 benchmark_TWII.csv。
共 3 個請求搞定全市場——下午三點看盤就有今日資料。

註：官方價=原始價；歷史檔是 yfinance 還原價。除權息日該股會有落差，
隔日 yfinance 增量會覆寫修正（updater 合併時以新抓為準），屬短暫近似。
執行：python fetch_daily_official.py
"""
from __future__ import annotations
import csv
import io
import sys
import logging
from pathlib import Path

import requests
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DATA = ROOT / "data"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)


def _f(x):
    try:
        v = float(str(x).replace(",", "").replace("--", "nan"))
        return v if v == v and v > 0 else None
    except Exception:
        return None


def fetch_twse(date_str: str) -> dict:
    """上市當日全部個股 {code: (o,h,l,c,vol)}"""
    u = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=csv&date={date_str}"
    r = requests.get(u, headers=H, timeout=30)
    r.encoding = "utf-8"
    out = {}
    # 欄位：日期,證券代號,證券名稱,成交股數,成交金額,開盤,最高,最低,收盤,漲跌,筆數
    for row in csv.reader(io.StringIO(r.text)):
        if len(row) < 9:
            continue
        code = row[1].strip()
        if not (code.isdigit() and len(code) == 4):
            continue
        if row[0].strip() != _roc(date_str):        # 確認是要求的那一天
            continue
        vol = _f(row[3]); o = _f(row[5]); hi = _f(row[6]); lo = _f(row[7]); c = _f(row[8])
        if c:
            out[code] = (o or c, hi or c, lo or c, c, vol or 0)
    return out


def _roc(date_str: str) -> str:
    """20260729 → 1150729（民國年）"""
    return str(int(date_str[:4]) - 1911) + date_str[4:]


def fetch_tpex() -> tuple[dict, str]:
    """上櫃當日 {code: (...)}；回傳 (dict, 資料日期yyyymmdd)"""
    u = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    r = requests.get(u, headers=H, timeout=30)
    out, date_roc = {}, ""
    for row in r.json():
        code = str(row.get("SecuritiesCompanyCode", "")).strip()
        if not (code.isdigit() and len(code) == 4):
            continue
        c = _f(row.get("Close"))
        if not c:
            continue
        out[code] = (_f(row.get("Open")) or c, _f(row.get("High")) or c,
                     _f(row.get("Low")) or c, c, _f(row.get("TradingShares")) or 0)
        date_roc = str(row.get("Date", ""))
    date_str = ""
    if len(date_roc) == 7:                       # 1150729 → 20260729
        date_str = str(int(date_roc[:3]) + 1911) + date_roc[3:]
    return out, date_str


def fetch_index(date_str: str):
    """加權指數當日 OHLC（MI_5MINS_HIST：日期,開,高,低,收）。查無回 None。
    ※舊版誤用 MI_INDEX（那張表是收盤/漲跌點/漲跌%，無OHLC），曾把漲跌%
      當收盤寫進大盤檔（0.62之亂），已換端點並在寫入端加防呆。"""
    month = date_str[:6] + "01"
    u = f"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={month}"
    r = requests.get(u, headers=H, timeout=30)
    j = r.json()
    if j.get("stat") != "OK":
        return None
    roc = f"{int(date_str[:4]) - 1911}/{date_str[4:6]}/{date_str[6:]}"
    for row in (j.get("data") or []):
        if row and str(row[0]).strip() == roc:
            o, hi, lo, c = (_f(row[1]), _f(row[2]), _f(row[3]), _f(row[4]))
            if c:
                return (o or c, hi or c, lo or c, c)
    return None


def _append_row(path: Path, date_iso: str, row_vals: list) -> bool:
    """檔案最後日 < date_iso 才追加；回傳是否有追加"""
    try:
        with open(path, "rb") as f:
            f.seek(-min(200, path.stat().st_size), 2)
            last_line = f.read().decode("utf-8", errors="replace").strip().splitlines()[-1]
        if last_line[:10] >= date_iso:
            return False
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write(",".join(str(v) for v in row_vals) + "\n")
        return True
    except Exception:
        return False


def run(date_override: str = "") -> int:
    t = now_tw()
    if date_override:
        date_str = date_override
        date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    else:
        if t.weekday() >= 5:
            log.info("週末，跳過"); return 0
        if t.hour < 14:
            log.info("未到 14:00（官方盤後資料未出），跳過"); return 0
        date_str = t.strftime("%Y%m%d")
        date_iso = t.strftime("%Y-%m-%d")

    twse = fetch_twse(date_str)
    tpex, tpex_date = fetch_tpex()
    log.info(f"官方源：上市 {len(twse)} 檔、上櫃 {len(tpex)} 檔（上櫃資料日 {tpex_date}）")
    if len(twse) < 500:
        log.warning("上市資料不足（可能今日休市或尚未公布），不追加"); return 1
    if tpex_date != date_str:
        log.info("上櫃資料日非今日 → 上櫃跳過")
        tpex = {}

    n = 0
    for code, (o, hi, lo, c, v) in twse.items():
        p = DATA / f"{code}.TW.csv"
        if p.exists() and _append_row(p, date_iso, [date_iso, o, hi, lo, c, int(v)]):
            n += 1
    for code, (o, hi, lo, c, v) in tpex.items():
        p = DATA / f"{code}.TWO.csv"
        if p.exists() and _append_row(p, date_iso, [date_iso, o, hi, lo, c, int(v)]):
            n += 1

    idx = fetch_index(date_str)
    if idx:
        o, hi, lo, c = idx
        # 防呆：與前一日收盤差 >15% 視為壞資料拒寫（0.62之亂的保險絲）
        ok = True
        try:
            bm = pd.read_csv(DATA / "benchmark_TWII.csv", usecols=["Date", "Close"])
            prev = float(pd.to_numeric(bm["Close"], errors="coerce").dropna().iloc[-1])
            if prev > 0 and abs(c / prev - 1) > 0.15:
                log.warning(f"加權指數 {c} 與前日 {prev:,.0f} 差異>15%，疑壞資料拒寫")
                ok = False
        except Exception:
            pass
        # benchmark 欄位順序：Date,Close,Open,High,Low,Volume
        if ok and _append_row(DATA / "benchmark_TWII.csv", date_iso,
                              [date_iso, c, o, hi, lo, 0]):
            log.info(f"加權指數 {date_iso} 收 {c:,.0f} 已追加")
    log.info(f"完成：{n} 檔個股追加今日K（3 個官方請求）")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="補指定日 YYYYMMDD（預設今天，14:00 前自動跳過）")
    a = ap.parse_args()
    sys.exit(run(a.date))

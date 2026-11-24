# -*- coding: utf-8 -*-
"""
insider_trades.py — 內部人股權異動(董監每月增加/減少股數;經理人、10% 大股東每月持股)
=================================================================
2026-11-24 使用者貼了別的網站的「內部人買賣」圖:「這張圖 盡量做」。
來源:公開資訊觀測站彙總報表 IRB110「董事、監察人、經理人及百分之十以上大股東股權異動彙總表(不含金控子公司)」
      每個市場每個月一個靜態檔(一次請求):https://siis.twse.com.tw/publish/{sii|otc}/{民國年}IRB110_{MM}.HTM
      公司每月 15 日前申報上個月,所以 N 月的檔大約在 N+1 月 15 日之後才完整。
欄位:公司、實際發行股數、董監本月增加股數、董監本月減少股數、董監持有股數、占比、經理人持有股數、10% 大股東持有股數。
和別的網站那張圖的差別(做不到的部分要講清楚):
  - 這份彙總表只有「董監合計」的增加/減少,沒有逐人、沒有職稱,也分不出是集中市場買賣、贈與還是信託;
  - 經理人與大股東只有月底持股,增減是我用前後兩個月相減算的(換人、改選也會造成變動);
  - 金額=股數 × 當月平均收盤價(還原價),是估計值,不是申報金額。
  逐人、分交易方式的明細在觀測站 query6_1(一家公司一個月一次請求),這支沒有抓。
快取:data/insider_trades.csv.gz(一列=一家公司一個月)。只由排程或手動抓,頁面只讀快取。
用法:python -X utf8 insider_trades.py            # 補缺的月份(預設回補 36 個月)
      python -X utf8 insider_trades.py --months 60
      python -X utf8 insider_trades.py --show 6425
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = DATA / "insider_trades.csv.gz"
COLS = ["ym", "mkt", "code", "name", "shares", "add", "sub", "hold_dir", "pct_dir", "hold_mgr", "hold_big"]
URL = "https://siis.twse.com.tw/publish/{mk}/{y}IRB110_{m:02d}.HTM"


def fetch_month(mk: str, year: int, month: int) -> pd.DataFrame:
    """一個市場一個月(一次請求)。還沒公布或抓不到就回空表。"""
    import requests

    import ssl_trust
    u = URL.format(mk=mk, y=year - 1911, m=month)
    r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=120, verify=str(ssl_trust.build()))
    if r.status_code != 200 or len(r.content) < 2000:
        return pd.DataFrame(columns=COLS)
    t = r.content.decode("cp950", errors="replace")
    tabs = pd.read_html(io.StringIO(t))
    b = max(tabs, key=len)
    if b.shape[1] < 8:
        return pd.DataFrame(columns=COLS)
    b = b.iloc[:, :8].copy()
    b.columns = ["co", "shares", "add", "sub", "hold_dir", "pct_dir", "hold_mgr", "hold_big"]
    b["code"] = b.co.astype(str).str.extract(r"^(\d{4})")[0]
    b = b.dropna(subset=["code"])
    b["name"] = b.co.astype(str).str[4:].str.strip()
    for c in ("shares", "add", "sub", "hold_dir", "pct_dir", "hold_mgr", "hold_big"):
        b[c] = pd.to_numeric(b[c].astype(str).str.replace(",", ""), errors="coerce")
    b["ym"], b["mkt"] = f"{year}-{month:02d}", mk
    return b[COLS].drop_duplicates(["ym", "code"])


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(CACHE, dtype={"code": str, "ym": str})


def _due_months(months: int) -> list[tuple[int, int]]:
    """該有資料的月份:今天 16 號以後算到上個月,否則算到上上個月。"""
    t = now_tw()
    last = (pd.Timestamp(t.year, t.month, 1) - pd.DateOffset(months=1 if t.day >= 16 else 2))
    return [((last - pd.DateOffset(months=k)).year, (last - pd.DateOffset(months=k)).month) for k in range(months)][::-1]


def refresh(months: int = 36, sleep: float = 1.2, log=print) -> str:
    """補抓快取裡沒有的(市場, 月份)。每個缺口一次請求;全部補齊後每個月只會多打兩次。"""
    old = load()
    have = set(zip(old.ym, old.mkt)) if len(old) else set()
    new, miss = [], []
    for y, m in _due_months(months):
        for mk in ("sii", "otc"):
            if (f"{y}-{m:02d}", mk) in have:
                continue
            try:
                d = fetch_month(mk, y, m)
            except Exception as e:
                log(f"  ⚠️ {mk} {y}-{m:02d}: {e!r}"[:160])
                d = pd.DataFrame(columns=COLS)
            if len(d):
                new.append(d)
                log(f"  {mk} {y}-{m:02d}: {len(d)} 家")
            else:
                miss.append(f"{mk} {y}-{m:02d}")
            time.sleep(sleep)
    if new:
        allv = pd.concat([old] + new, ignore_index=True).drop_duplicates(["ym", "code"], keep="last").sort_values(["ym", "code"])
        tmp = CACHE.with_suffix(".tmp.gz")
        allv.to_csv(tmp, index=False, compression="gzip", encoding="utf-8-sig")
        tmp.replace(CACHE)
    return f"新增 {len(new)} 個(市場×月份)" + (f";沒有資料 {len(miss)} 個:{'、'.join(miss[:6])}" if miss else "")


def monthly_price(code: str) -> pd.DataFrame:
    """月均收盤與月底收盤(本機日線;還原價)。"""
    fs = sorted(DATA.glob(f"{code}.TW*.csv"))
    if not fs:
        return pd.DataFrame(columns=["ym", "avg", "close"])
    d = pd.read_csv(fs[0], parse_dates=["Date"]).dropna(subset=["Close"])
    g = d.groupby(d.Date.dt.strftime("%Y-%m")).Close
    return pd.DataFrame({"avg": g.mean(), "close": g.last()}).rename_axis("ym").reset_index()


def series(code: str, allv: pd.DataFrame | None = None) -> pd.DataFrame:
    """一檔股票的月序列:董監增加/減少(張)、淨額、估計金額(萬元)、經理人與大股東持股的月變動(張)。"""
    a = load() if allv is None else allv
    d = a[a.code == str(code)].sort_values("ym").reset_index(drop=True)
    if d.empty:
        return d
    p = monthly_price(code)
    d = d.merge(p, on="ym", how="left")
    d["add_k"], d["sub_k"] = d["add"].fillna(0) / 1000, d["sub"].fillna(0) / 1000
    d["net_k"] = d.add_k - d.sub_k
    d["buy_amt"] = d["add"].fillna(0) * d["avg"] / 1e4            # 萬元(估計)
    d["sell_amt"] = d["sub"].fillna(0) * d["avg"] / 1e4
    d["net_amt"] = d.buy_amt - d.sell_amt
    gap = pd.PeriodIndex(d.ym, freq="M").astype("int64")
    ok = pd.Series(gap).diff().eq(1).values                        # 只在連續兩個月都有資料時才算變動
    d["mgr_chg_k"] = np.where(ok, d.hold_mgr.diff() / 1000, np.nan)
    d["big_chg_k"] = np.where(ok, d.hold_big.diff() / 1000, np.nan)
    return d


def market_summary(ym: str | None = None) -> dict:
    """全市場一個月:幾家公司董監有增加/減少、合計張數。"""
    a = load()
    if a.empty:
        return {}
    ym = ym or a.ym.max()
    d = a[a.ym == ym]
    return dict(ym=ym, n=len(d), n_add=int((d["add"] > 0).sum()), n_sub=int((d["sub"] > 0).sum()),
                add_k=float(d["add"].sum() / 1000), sub_k=float(d["sub"].sum() / 1000))


if __name__ == "__main__":
    if "--show" in sys.argv:
        pd.set_option("display.width", 250, "display.max_rows", 80)
        s = series(sys.argv[sys.argv.index("--show") + 1])
        print(s[["ym", "shares", "add_k", "sub_k", "net_k", "avg", "net_amt", "hold_dir", "pct_dir", "mgr_chg_k", "big_chg_k"]].round(2).to_string(index=False))
        print(market_summary())
    else:
        n = int(sys.argv[sys.argv.index("--months") + 1]) if "--months" in sys.argv else 36
        print(refresh(n))
        print(market_summary())

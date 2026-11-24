# -*- coding: utf-8 -*-
"""
branch_hist.py — 單檔個股的券商分點「掛牌以來逐日買賣」+累計庫存(2026-11-18)
=================================================================
來源:富邦 DJ 公開分點日報(同 turnover_radar.fetch_branch_days)。
  zco.djhtm?a=代號&e=起&f=迄            → 區間買超/賣超前 15 名(拿分點名單與連結)
  zco0.djhtm?...&C=1&D=起&E=迄           → 單一分點對這檔股票的逐日買進/賣出張數
做法:用每年+近期幾個區間的前 15 名收集分點名單(排不進任何區間前 15 的小分點會漏),
     再逐一抓 2016 年起的逐日明細,存 data/branch/<代號>_branch.csv.gz(date,br,buy,sell)。
用途:匯撥(帳戶之間轉股票)不是交易、分點日報看不到;但「掛牌以來賣的比買的多」算得出來——
     那些股票不是在這個分點從市場買的,來源只可能是原始股/配股/可轉債轉換/從別處匯撥進來/融券借券。
抓一檔約 3~5 分鐘(170 個分點各一次請求),只在手動重跑時抓,不掛在頁面上。
手動:python -X utf8 branch_hist.py 4566 [--refresh]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DIR = ROOT / "data" / "branch"
BASE = "http://fubon-ebrokerdj.fbs.com.tw"
UA = {"User-Agent": "Mozilla/5.0"}


def _get(url: str) -> str:
    import requests

    import ssl_trust
    r = requests.get(url, headers=UA, timeout=60, verify=str(ssl_trust.build()))
    return r.content.decode("big5", errors="replace")


def _branches(code: str, e: str, f: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_get(f"{BASE}/z/zc/zco/zco.djhtm?a={code}&e={e}&f={f}"), "html.parser")
    t = max(soup.find_all("table"), key=lambda x: len(x.find_all("tr")))
    out = {}
    for tr in t.find_all("tr"):
        tds = tr.find_all("td")
        cells = [td.get_text(strip=True) for td in tds]
        if len(cells) >= 10 and cells[0] and "券商" not in cells[0]:
            for off in (0, 5):
                a = tds[off].find("a")
                if a and a.get("href"):
                    out[cells[off]] = a.get("href")
    return out


def _one(href: str, end: str) -> pd.DataFrame:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_get(f"{BASE}{href}&C=1&D=2016-1-1&E={end}"), "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        c = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(c) == 5 and re.match(r"\d{4}/\d\d/\d\d$", c[0]):
            try:
                rows.append((c[0].replace("/", "-"), float(c[1].replace(",", "")), float(c[2].replace(",", ""))))
            except ValueError:
                continue
    return pd.DataFrame(rows, columns=["date", "buy", "sell"]).drop_duplicates("date")


def fetch(code: str, refresh: bool = False) -> pd.DataFrame:
    """回傳長表 date,br,buy,sell(張)。有快取就讀快取;refresh=True 才重抓。"""
    p = DIR / f"{code}_branch.csv.gz"
    if p.exists() and not refresh:
        return pd.read_csv(p, parse_dates=["date"])
    t = now_tw()
    end = f"{t.year}-{t.month}-{t.day}"
    wins = [(f"{y}-1-1", f"{y}-12-31") for y in range(2017, t.year)] + [(f"{t.year}-1-1", end)]
    for k in (20, 60, 120, 250):                      # 近期幾個區間,補進最近才活躍的分點
        s = t - pd.Timedelta(days=int(k * 1.45))
        wins.append((f"{s.year}-{s.month}-{s.day}", end))
    brs: dict = {}
    for e, f in wins:
        try:
            brs.update(_branches(code, e, f))
        except Exception as ex:
            print(f"{e}~{f} 名單失敗:{ex}")
        time.sleep(0.3)
    parts = []
    for i, (nm, href) in enumerate(brs.items(), 1):
        try:
            d = _one(href, end)
            d.insert(1, "br", nm)
            parts.append(d)
        except Exception as ex:
            print(f"{nm} 失敗:{ex}")
        time.sleep(0.3)
    if not parts:
        raise RuntimeError(f"{code} 沒抓到任何分點")
    out = pd.concat(parts, ignore_index=True)
    DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False, compression="gzip")
    print(f"{code}:{len(brs)} 個分點、{len(out)} 筆 → {p}")
    return pd.read_csv(p, parse_dates=["date"])


def shares_lots(code: str) -> float | None:
    """發行張數:集保股權分散表最新一週,用最大級距的 股數÷占比 反推。"""
    p = ROOT / "data" / "tdcc" / f"{code}_tdcc.csv"
    if not p.exists():
        return None
    t = pd.read_csv(p)
    x = t[(t.date == t.date.max()) & (t.pct > 0)].sort_values("pct").iloc[-1]
    return float(x.shares) / float(x.pct) * 100 / 1000


def inventory(df: pd.DataFrame, recent_days: int = 14) -> pd.DataFrame:
    """每個分點:買、賣、累計(掛牌以來淨買)、各年淨額、最近 recent_days 個交易日淨額、那之前的累計。"""
    df = df.assign(net=df.buy - df.sell, year=df.date.dt.year)
    days = sorted(df.date.unique())
    cut = days[-recent_days] if len(days) >= recent_days else days[0]
    g = df.groupby("br")
    out = pd.DataFrame({"買": g.buy.sum(), "賣": g.sell.sum(), "累計": g.net.sum(),
                        "近期": df[df.date >= cut].groupby("br").net.sum(),
                        "之前累計": df[df.date < cut].groupby("br").net.sum()}).fillna(0)
    yr = df.pivot_table(index="br", columns="year", values="net", aggfunc="sum").fillna(0)
    yr.columns = [str(c) for c in yr.columns]
    out = out.join(yr)
    out.attrs["cut"] = pd.Timestamp(cut)
    return out.sort_values("累計", ascending=False)


# ── 交叉查核:分點看不到的那一半(內部人申報、新股來源)。來源都是公開資訊觀測站原始申報 ──
MOPS = "https://mopsov.twse.com.tw/mops/web/"


def _mops(page: str, **kw) -> str:
    import requests

    import ssl_trust
    d = dict(encodeURIComponent=1, step=1, firstin=1, off=1, keyword4="", code1="", TYPEK2="", checkbtn="",
             queryName="co_id", inpuType="co_id", TYPEK="all", isnew="false")
    d.update(kw)
    for _ in range(4):
        try:
            r = requests.post(MOPS + page, data=d, headers=UA, timeout=60, verify=str(ssl_trust.build()))
            r.encoding = "utf-8"
            if r.text and "頻繁" not in r.text:
                return r.text
        except Exception as ex:
            print(f"{page} 重試:{ex}")
        time.sleep(15)
    return ""


def _months(code: str, old: pd.DataFrame) -> list:
    """要抓的 (年, 月):從分點資料第一天起;快取已有的月份只重抓最後一個(當月可能還沒申報完)。"""
    t = now_tw()
    s = fetch(code).date.min()
    have = set(zip(old.y, old.m)) - ({(int(old.y.iloc[-1]), int(old.m.iloc[-1]))} if len(old) else set())
    out, y, m = [], s.year, s.month
    while (y, m) <= (t.year, t.month):
        if (y, m) not in have:
            out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _cached(code: str, kind: str, cols: list, refresh: bool, scan) -> pd.DataFrame:
    """快取 data/branch/<代號>_<kind>.csv:有快取就讀;沒有或 refresh=True 才補抓缺的月份。"""
    p = DIR / f"{code}_{kind}.csv"
    old = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=cols)
    if p.exists() and not refresh:
        return old
    todo = _months(code, old)
    keep = old[~old.set_index(["y", "m"]).index.isin(todo)] if len(old) else old
    rows = []
    for y, m in todo:
        rows += [(y, m) + r for r in scan(y, m)]
        time.sleep(2.5)
    out = pd.concat([keep, pd.DataFrame(rows, columns=cols)], ignore_index=True).sort_values(["y", "m"], kind="stable")
    DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"{code} {kind}:補 {len(todo)} 個月、共 {len(out)} 筆 → {p}")
    return pd.read_csv(p)


def insiders(code: str, refresh: bool = False) -> pd.DataFrame:
    """董監事、經理人、大股東每月持股餘額(公開資訊觀測站 stapap1):y,m,title,name,hold,pledge(股)。"""
    from bs4 import BeautifulSoup

    def scan(y, m):
        rows = []
        for tr in BeautifulSoup(_mops("ajax_stapap1", co_id=code, year=y - 1911, month=f"{m:02d}"), "html.parser").find_all("tr"):
            c = [x.get_text(strip=True).replace(",", "") for x in tr.find_all("td")]
            if len(c) == 9 and c[3].isdigit() and c[4].isdigit():
                rows.append((c[0], c[1], int(c[3]), int(c[4])))
        return rows
    return _cached(code, "insider", ["y", "m", "title", "name", "hold", "pledge"], refresh, scan)


def new_shares(code: str, refresh: bool = False) -> pd.DataFrame:
    """重大訊息裡的「增資基準日」公告(可轉債轉換、員工認股、現金增資發的新股):y,m,date,title,shares(股)。"""
    from bs4 import BeautifulSoup

    def scan(y, m):
        rows = []
        for tr in BeautifulSoup(_mops("ajax_t05st01", co_id=code, year=y - 1911, month=f"{m:02d}"), "html.parser").find_all("tr"):
            c = [x.get_text(" ", strip=True) for x in tr.find_all("td")]
            btn = tr.find("input")
            if len(c) < 5 or "增資基準日" not in c[4] or not btn:
                continue
            kv = dict(re.findall(r"(\w+)\.value\s*=\s*['\"]([^'\"]*)['\"]", btn.get("onclick", "")))
            time.sleep(2.5)
            txt = BeautifulSoup(_mops("ajax_t05st01", **{**kv, "step": 2}), "html.parser").get_text("\n", strip=True)
            mm = re.search(r"發行(?:普通股新股|股數[^:\n]*:)\s*([\d,]+)\s*股", txt)
            ry, rm, rd = c[2].split("/")
            rows.append((f"{int(ry) + 1911}-{rm}-{rd}", re.sub(r"\s+", "", c[4]), int(mm.group(1).replace(",", "")) if mm else 0))
        return rows
    return _cached(code, "newshares", ["y", "m", "date", "title", "shares"], refresh, scan)


def insider_match(df: pd.DataFrame, ins: pd.DataFrame, min_lots: int = 50) -> pd.DataFrame:
    """每位內部人「申報持股的月變動」對上哪個分點的「當月淨買賣」。
    回傳 name, br, months(變動 ≥ min_lots 張的月數), hit(分點當月淨額落在 ±10% 內的月數), 明細 detail(ym, 變動, 分點淨額)。"""
    d = df.assign(ym=df.date.dt.year * 100 + df.date.dt.month, net=df.buy - df.sell)
    piv = d.pivot_table(index="ym", columns="br", values="net", aggfunc="sum").fillna(0)
    out = []
    g0 = ins.assign(ym=ins.y * 100 + ins.m).drop_duplicates(["ym", "name"])
    allm = sorted(g0.ym.unique())
    for nm, g in g0.groupby("name"):
        h = g.set_index("ym").hold.reindex(allm)
        ch = (h.diff() / 1000).dropna()                 # 只算連續兩個月都在名單上的變動
        ch = ch[ch.abs() >= min_lots]
        if len(ch) < 2:
            continue
        sub = piv.reindex(ch.index).fillna(0)
        hit = sub.sub(ch, axis=0).abs().le(ch.abs() * 0.1, axis=0).sum()
        br = hit.idxmax()
        out.append(dict(name=nm, br=br, months=len(ch), hit=int(hit.max()),
                        detail=pd.DataFrame({"chg": ch, "net": sub[br]})))
    return pd.DataFrame(out).sort_values("hit", ascending=False) if out else pd.DataFrame(columns=["name", "br", "months", "hit", "detail"])


def conv_windows(code: str, df: pd.DataFrame, ns: pd.DataFrame, min_lots: int = 500) -> pd.DataFrame:
    """每個增資基準日公告(新股 ≥ min_lots 張)對應的那一季:新股張數、同期融券賣出/現券償還、淨賣最多的 3 個分點。
    公告結的是「前一個日曆季」申請轉換的股數(3 月結去年 Q4、5 月結 Q1、8 月結 Q2、11 月結 Q3);
    換來的股票隔幾天才入帳,所以區間整個往後移 7 天。
    現券償還=拿手上的股票去還融券,不是買進——先放空、再用可轉債換來的股票還,分點上就只看得到賣。"""
    ns = ns.assign(date=pd.to_datetime(ns.date))
    g = ns.groupby("date").shares.sum().sort_index() / 1000
    mp = ROOT / "data" / "margin" / f"{code}_margin.csv"
    mg = pd.read_csv(mp, parse_dates=["date"]) if mp.exists() else None
    d = df.assign(net=df.buy - df.sell)
    lag = pd.Timedelta(days=7)
    rows = []
    for dt, lots in g[g >= min_lots].items():
        q = dt.to_period("Q") - 1
        s, e = q.start_time + lag, q.end_time.normalize() + lag
        w = d[(d.date > s) & (d.date <= e)].groupby("br").net.sum().sort_values().head(3)
        m = mg[(mg.date > s) & (mg.date <= e)] if mg is not None and mg.date.min() <= s else None
        rows.append(dict(q=str(q), date=dt, lots=lots,
                         short_sell=m.short_sell.sum() if m is not None else None,
                         short_redeem=m.short_redeem.sum() if m is not None else None,
                         top="、".join(f"{b} {v:+,.0f}" for b, v in w.items())))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "4566"
    d = fetch(code, refresh="--refresh" in sys.argv)
    if "--refresh" in sys.argv:                          # 內部人月報與增資公告各約 5~8 分鐘
        insiders(code, refresh=True)
        new_shares(code, refresh=True)
    inv = inventory(d)
    print(inv[["買", "賣", "累計", "近期"]].head(10).to_string())
    print(inv[["買", "賣", "累計", "近期"]].tail(10).to_string())

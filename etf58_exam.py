# -*- coding: utf-8 -*-
"""ETF58 空頭考卷(2026-11-23)。/我的ETF 頁「🧪 高股息58檔考卷」分頁用,只讀 data/etf58/raw 快取,不發請求。

要解決的兩件事:
  1. 58 檔畫成 58 條線沒辦法看 → 一檔一個點(table → 散布圖),線圖只畫挑出來的幾檔。
  2. 上市以來的年化排名偏袒只經歷過多頭的新基金 → 改用「同一段期間」比:
       下跌參與 dn = 這次空頭(大盤高點 → 高點後最低點)該檔含息報酬 ÷ 大盤報酬     1.0 = 跟大盤跌一樣多
       上漲參與 up = 前一段多頭(上次落底 2025-04-09 → 高點)該檔含息報酬 ÷ 大盤報酬;多頭途中才上市的,從上市首日算、標「只參加一部分」,
                     參加不到 60 天的不算
       不對稱 asym = up − dn     > 0 = 漲的時候跟得比跌的時候多
     再加「以前考過幾次空頭、幾次跌得比大盤少」。
含息報酬口徑同四榜:(期末價 − 期初價 + 期間內除息的股息) ÷ 期初價,股息不再投入;大盤 = 加權指數,不含息。

  python -X utf8 etf58_exam.py        # 印出整張表(驗證點)"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))
import etf58_inception as E  # noqa: E402

# (名稱, 大盤高點日, 大盤低點日);最後一段的低點 = 高點之後到資料最後一天的最低收盤(每天重算)。2018 那次只跌 14%,算修正
EPISODES = [("2008", "2008-05-19", "2008-11-20"), ("2011", "2011-01-28", "2011-12-19"), ("2015", "2015-04-27", "2015-08-24"),
            ("2018", "2018-10-01", "2019-01-04"), ("2020", "2020-01-14", "2020-03-19"), ("2022", "2022-01-04", "2022-10-25"),
            ("2025", "2025-02-21", "2025-04-09"), ("2026", "2026-10-06", None)]
PAST = [e[0] for e in EPISODES[:-1]]
NOW = EPISODES[-1][0]
BULL0 = EPISODES[-2][2]                 # 上一次落底日 = 這段多頭的起點
MIN_BULL_DAYS = 60                      # 多頭參加不到 60 天的不算上漲參與(樣本太短,比值會亂跳)
LONG = ("2008", "2011", "2022")         # 拖超過半年的空頭(其餘都是 2~4 個月的急跌)

CAT_ORDER = ["台股高股息", "台股主動", "海外股票", "債券", "主動債券"]
CAT_COLOR = {"台股高股息": "#0072B2", "台股主動": "#D55E00", "海外股票": "#009E73", "債券": "#8A8F98", "主動債券": "#CC79A7"}
_OVERSEAS = {"00702", "00771", "00882", "00956", "00960", "00963", "00964", "00972", "IQQQ", "QQA"}


def cat(code: str) -> str:
    if code in _OVERSEAS:
        return "海外股票"
    if code[-1] == "A":
        return "台股主動"
    if code[-1] == "D":
        return "主動債券"
    if code[-1] in "BC":
        return "債券"
    return "台股高股息"


def _stamp() -> float:
    return max((p.stat().st_mtime for p in E.RAW.glob("*.json")), default=0.0)


@lru_cache(maxsize=2)
def _data(stamp: float):
    FX = E.fx()
    d = {c: E.load(c, FX) for c in E.CODES}
    last = max(s.index[-1] for c, (s, _) in d.items() if c not in E.US)      # 台股最後一個交易日
    idx = E.twii()
    return d, idx[idx.index <= last], last


def data():
    return _data(_stamp())


def windows() -> dict:
    """這次空頭 / 前一段多頭 的起訖與大盤報酬。"""
    _, idx, last = data()
    pk = pd.Timestamp(EPISODES[-1][1])
    after = idx[idx.index >= pk]
    lo = after.idxmin()
    return dict(peak=pk, low=lo, last=last, bull0=pd.Timestamp(BULL0),
                bear_m=float(idx.asof(lo) / idx.asof(pk) - 1), bull_m=float(idx.asof(pk) / idx.asof(pd.Timestamp(BULL0)) - 1),
                since_low=float(idx.asof(last) / idx.asof(lo) - 1))


def ret(s: pd.Series, dv: pd.DataFrame, a, b) -> float:
    """a → b 的含息報酬(股息不再投入)。a 那天還沒上市 → NaN。"""
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    if s.index[0] > a or s.index[-1] < a:
        return np.nan
    p0 = float(s.asof(a))
    return (float(s.asof(b)) - p0 + float(dv.twd[(dv.ex > a) & (dv.ex <= b)].sum())) / p0


@lru_cache(maxsize=2)
def _table(stamp: float) -> pd.DataFrame:
    d, idx, last = data()
    W = windows()
    mk = {n: float(idx.asof(pd.Timestamp(b)) / idx.asof(pd.Timestamp(a)) - 1) for n, a, b in EPISODES[:-1]}
    board = {r["code"]: r for r in E.compute_all()}                      # 四榜(截止 E.END)的年化,拿來對照
    rows = []
    for c in E.CODES:
        s, dv = d[c]
        r = {"code": c, "name": E.NAMES[c], "cat": cat(c), "listed": s.index[0], "yrs": (last - s.index[0]).days / 365.25}
        r["B1y"] = board[c]["B1y"] if c in board else np.nan
        r["bear"] = ret(s, dv, W["peak"], W["low"])
        r["dn"] = r["bear"] / W["bear_m"]
        r["rebound"] = ret(s, dv, W["low"], last) if last > W["low"] else np.nan
        a = max(W["bull0"], s.index[0])
        r["bull_from"], r["partial"] = a, bool(s.index[0] > W["bull0"])
        r["bull"] = ret(s, dv, a, W["peak"])
        r["bull_m"] = float(idx.asof(W["peak"]) / idx.asof(a) - 1)
        r["bull_days"] = (W["peak"] - a).days
        r["up"] = r["bull"] / r["bull_m"] if r["bull_m"] >= 0.05 and r["bull_days"] >= MIN_BULL_DAYS else np.nan
        r["asym"] = r["up"] - r["dn"]
        n = less = 0
        for nm, a0, b0 in EPISODES[:-1]:
            v = ret(s, dv, a0, b0)
            r[nm] = v
            if pd.notna(v):
                n += 1
                less += int(v > mk[nm])
        r["n_prior"], r["n_less"] = n, less
        r["long_bear"] = bool(any(pd.notna(r[k]) for k in LONG))
        rows.append(r)
    t = pd.DataFrame(rows)
    t.attrs["mkt"] = mk
    return t


def table() -> pd.DataFrame:
    """58 檔一檔一列(報酬都是小數,0.1 = 10%)。t.attrs['mkt'] = 歷次空頭大盤報酬。"""
    return _table(_stamp())


def funnel(cats: tuple = ("台股高股息", "台股主動")) -> list:
    """58 檔 → 剩幾檔。每一關:(說明, 剩下的代號)。機械規則,是體檢不是買單。"""
    t = table()
    a = t[t.cat.isin(cats)]
    b = a[a.dn < 1]
    c = b[b.n_prior >= 1]
    d = c[c.asym > 0]
    return [("全部", list(t.code)), ("只看 " + "、".join(cats), list(a.code)), ("這次空頭跌得比大盤少", list(b.code)),
            ("之前至少考過 1 次空頭", list(c.code)), ("漲的時候跟得比跌的時候多(不對稱 > 0)", list(d.sort_values("asym", ascending=False).code))]


def lines(codes: list, since: str) -> pd.DataFrame:
    """含息淨值線(基期 100;價格 + 基期之後累計除息,股息不再投入)。index = 日期字串,欄 = 代號;另附「大盤」。"""
    d, idx, last = data()
    x = idx[idx.index >= pd.Timestamp(since)]
    out = pd.DataFrame(index=x.index)
    out["大盤"] = x / x.iloc[0] * 100
    for c in codes:
        s, dv = d[c]
        p = s.reindex(x.index, method="ffill")
        if p.dropna().empty:
            continue
        t0 = p.first_valid_index()
        cum = pd.Series(0.0, index=x.index)
        for e, v in zip(dv.ex, dv.twd):
            if e > t0:
                cum[cum.index >= e] += v
        out[c] = (p + cum) / float(p[t0]) * 100
    out.index = out.index.strftime("%Y-%m-%d")
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_columns", 40)
    W = windows()
    print(f"這次空頭 {W['peak']:%Y-%m-%d} → {W['low']:%Y-%m-%d} 大盤 {W['bear_m']:+.1%}|前一段多頭 {W['bull0']:%Y-%m-%d} → {W['peak']:%Y-%m-%d} 大盤 {W['bull_m']:+.1%}"
          f"|資料到 {W['last']:%Y-%m-%d}")
    t = table()
    print("歷次空頭大盤:", {k: f"{v:+.1%}" for k, v in t.attrs["mkt"].items()})
    v = t[["code", "name", "cat", "listed", "B1y", "bear", "dn", "bull", "up", "partial", "asym", "n_prior", "n_less"] + PAST].copy()
    v["listed"] = v.listed.dt.strftime("%Y-%m-%d")
    for k in ["B1y", "bear", "bull"] + PAST:
        v[k] = (v[k] * 100).round(1)
    print(v.round(2).sort_values(["cat", "asym"], ascending=[True, False]).to_string(index=False))
    for lab, codes in funnel():
        print(f"{len(codes):>3} 檔  {lab}" + (":" + "、".join(codes) if len(codes) <= 12 else ""))

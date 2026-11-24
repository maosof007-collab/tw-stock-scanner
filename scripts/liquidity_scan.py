# -*- coding: utf-8 -*-
"""
liquidity_scan.py — 「無量跌停鎖死」事件掃描(本機日線 2015 年起)
================================================================
起因(2026-11-23):使用者說「流動性更低 無量跌停股票只能等死」「流動性問題 我們有甚麼經典案子可以學習嗎」。
口徑(和 11/20 那次統計一樣):
  ・跌停:收盤等於當日最低,且收盤比前一日跌 9.45%~10.05%(2015/6/1 以前漲跌幅 7%,用 6.45%~7.05%)。
    本機股價是還原價,沒辦法直接算跌停價;但還原價的「當日漲跌幅」和原始價一樣,跌停價=前收×0.9 往上取到升降單位,
    所以跌停收盤的跌幅一定落在 9.5%~10%。verify() 會抓 FinMind 原始價逐筆核對。
  ・有量能的股票:前 20 個交易日均量 ≥ 500 張(事件前的均量,不含當天)。只看一般個股(四碼、不是 00 開頭)。
  ・鎖死(無量跌停):跌停那天的成交量 < 前 20 日均量的 30%。
  ・一串:連續收跌停的交易日;串裡至少一天是鎖死才算「被鎖住」。
  ・打開日:這一串之後第一個「沒有收在跌停」的交易日。之後的報酬都從打開日收盤起算。
限制:股價檔沒有已下市的公司(樂陞、康友-KY 這類不在裡面),所以「鎖到下市」的案例看不到。
輸出:data/_liquidity_runs.csv(每一串一列)、data/_liquidity_days.csv(每天跌停/鎖死檔數)
用法:python -X utf8 scripts/liquidity_scan.py            # 掃描+印事件摘要
      python -X utf8 scripts/liquidity_scan.py verify     # 抽樣用 FinMind 原始價核對跌停判定(會發幾個請求)
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
D = ROOT / "data"
RUNS, DAYS = D / "_liquidity_runs.csv", D / "_liquidity_days.csv"
MIN_VOL = 500_000            # 前 20 日均量門檻(股)=500 張
DRY = 0.30                   # 量 < 均量的三成=無量
NEW_LIMIT = pd.Timestamp("2015-06-01")      # 這天起漲跌幅 7% → 10%
EVENT_MIN = 15               # 一天鎖死這麼多檔以上才算「事件日」
EVENT_GAP = 6                # 事件日相隔不到這麼多個交易日算同一次


def index_close() -> pd.Series:
    """加權指數日收盤(長歷史接每日更新檔;每日檔後段多了幾欄,只取前兩欄)。"""
    out = {}
    for f in ("_twii_long.csv", "benchmark_TWII.csv"):
        p = D / f
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8-sig").splitlines()[1:]:
            a = ln.split(",")
            try:
                out[pd.Timestamp(a[0])] = float(a[1])
            except Exception:
                continue
    return pd.Series(out).sort_index()


def scan_one(path: str) -> tuple[pd.DataFrame, list[dict]]:
    code = os.path.basename(path).split(".")[0]
    try:
        d = pd.read_csv(path, parse_dates=["Date"]).dropna(subset=["Close"]).drop_duplicates("Date").sort_values("Date")
    except Exception:
        return pd.DataFrame(), []
    if len(d) < 40:
        return pd.DataFrame(), []
    dt = d.Date.to_numpy()
    c, lo, hi, v = (d[k].to_numpy(float) for k in ("Close", "Low", "High", "Volume"))
    r = np.full(len(c), np.nan)
    r[1:] = c[1:] / c[:-1] - 1
    lim = np.where(d.Date < NEW_LIMIT, 0.07, 0.10)
    v20 = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    ld = (r <= -(lim - 0.0055)) & (r >= -(lim + 0.0005)) & (c <= lo * (1 + 1e-9))
    liquid = v20 >= MIN_VOL
    dry = ld & liquid & (v < DRY * v20)
    day = pd.DataFrame({"date": dt, "liquid": liquid, "ld": ld & liquid, "lock": dry, "one": dry & (hi <= lo * (1 + 1e-9))})
    runs, i, n = [], 0, len(c)
    while i < n:
        if not ld[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and ld[j + 1]:
            j += 1
        if dry[i:j + 1].any() and liquid[i]:
            k = j + 1                                    # 打開日
            row = dict(code=code, start=dt[i], end=dt[j], n=j - i + 1, n_dry=int(dry[i:j + 1].sum()),
                       n_one=int((hi[i:j + 1] <= lo[i:j + 1] * (1 + 1e-9)).sum()),
                       min_vr=float(np.nanmin(v[i:j + 1] / v20[i])), pre=c[i - 1], first=c[i], last=c[j], opened=k < n)
            if k < n:
                row.update(open_date=dt[k], open_vr=v[k] / v20[i], open_ret=c[k] / c[j] - 1,
                           open_gap=d.Open.to_numpy(float)[k] / c[j] - 1,
                           wait=c[k] / c[i] - 1,                  # 第一根跌停收盤 → 打開日收盤(被鎖住的人多賠的)
                           total=c[k] / c[i - 1] - 1)             # 跌停前 → 打開日收盤
                for h in (5, 10, 20, 60):
                    row[f"f{h}"] = c[k + h] / c[k] - 1 if k + h < n else np.nan
                # 打開後 20 日內(含打開日)最低收盤,和「最後一根跌停價」比:小於 0=等到打開之後還有更低的價
                row["low_after"] = float(np.nanmin(c[k:k + 21]) / c[j] - 1) if k + 20 < n else np.nan
                seg = c[k + 1:k + 21]
                row["min20"] = float(np.nanmin(seg) / c[k] - 1) if k + 20 < n else np.nan
                row["back60"] = bool(np.nanmax(c[k:k + 61]) >= c[i - 1]) if k + 60 < n else np.nan   # 60 日內收盤回到跌停前
            runs.append(row)
        i = j + 1
    return day, runs


def scan() -> tuple[pd.DataFrame, pd.DataFrame]:
    files = [f for f in glob.glob(str(D / "*.TW.csv")) + glob.glob(str(D / "*.TWO.csv"))
             if (b := os.path.basename(f).split(".")[0]).isdigit() and len(b) == 4 and not b.startswith("00")]
    days, runs = [], []
    for f in files:
        dd, rr = scan_one(f)
        if len(dd):
            days.append(dd[dd.liquid])
        runs += rr
    days = pd.concat(days).groupby("date")[["liquid", "ld", "lock", "one"]].sum().astype(int)
    runs = pd.DataFrame(runs).sort_values(["start", "code"]).reset_index(drop=True)
    days.to_csv(DAYS, encoding="utf-8")
    runs.to_csv(RUNS, index=False, encoding="utf-8")
    return days, runs


def events(days: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """鎖死檔數 ≥ EVENT_MIN 的日子,相近的併成一次事件 → [(第一天, 最後一天)]。"""
    idx = list(days.index)
    hot = [idx.index(d) for d in days.index[days.lock >= EVENT_MIN]]
    out, cur = [], None
    for p in hot:
        if cur and p - cur[1] <= EVENT_GAP:
            cur[1] = p
        else:
            if cur:
                out.append(cur)
            cur = [p, p]
    if cur:
        out.append(cur)
    return [(idx[a], idx[b]) for a, b in out]


def summarize(days: pd.DataFrame, runs: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp, idx: pd.Series) -> dict:
    """一次事件的摘要。事件內的一串=開始日落在 [a 前 3 個交易日, b] 之間。"""
    di = list(days.index)
    a0 = di[max(di.index(a) - 3, 0)]
    x = runs[(runs.start >= a0) & (runs.start <= b)]
    o = x[x.opened.astype(bool)]
    w = days.loc[a0:b]
    ia = idx.index.searchsorted(a)
    seg = idx.iloc[max(ia - 3, 0):ia + 41]                       # 事件前 3 日到之後 40 個交易日
    low_d = seg.idxmin()
    pk = idx.iloc[max(ia - 120, 0):ia + 1].max()

    def med(col):
        s = o[col].dropna().astype(float)
        return float(s.median()) if len(s) else np.nan

    def q(col, p):
        s = o[col].dropna().astype(float)
        return float(s.quantile(p)) if len(s) else np.nan

    def share(col):                                             # noqa: E306
        s = o[col].dropna()
        return float(s.astype(bool).mean()) if len(s) else np.nan
    return dict(a=a, b=b, n=len(x), stocks=x.code.nunique(), peak_lock=int(w.lock.max()), peak_lock_d=w.lock.idxmax(),
                peak_ld=int(w.ld.max()), peak_ld_d=w.ld.idxmax(), liquid=int(w.liquid.max()), peak_one=int(w.one.max()),
                len_med=float(x.n.median()), len_max=int(x.n.max()), len3=float((x.n >= 3).mean()), len1=float((x.n == 1).mean()),
                opened=len(o), open_vr=med("open_vr"), open_ret=med("open_ret"), open_up=float((o.open_ret > 0).mean()) if len(o) else np.nan,
                wait=med("wait"), total=med("total"),
                f5=med("f5"), f10=med("f10"), f20=med("f20"), f60=med("f60"), f20_q1=q("f20", .25), f20_q3=q("f20", .75),
                f20_win=float((o.f20.dropna() > 0).mean()) if o.f20.notna().any() else np.nan, n20=int(o.f20.notna().sum()),
                lower=float((o.low_after.dropna() < 0).mean()) if o.low_after.notna().any() else np.nan,
                low_after=med("low_after"), min20=med("min20"), back60=share("back60"),
                idx_low_d=low_d, idx_low=float(seg.min()), idx_dd=float(seg.min() / pk - 1),
                idx_days=int(idx.index.searchsorted(low_d) - ia), idx_f20=float(idx.iloc[min(idx.index.searchsorted(low_d) + 20, len(idx) - 1)] / seg.min() - 1))


def verify(runs: pd.DataFrame, k: int = 12) -> None:
    """抽樣:用 FinMind 原始價算真正的跌停價,核對我們判成跌停的日子。"""
    import requests
    import ssl_trust
    ssl_trust.ensure()

    def tick(p):
        return 0.01 if p < 10 else 0.05 if p < 50 else 0.1 if p < 100 else 0.5 if p < 500 else 1 if p < 1000 else 5
    smp = runs.sample(k, random_state=7)
    ok = bad = 0
    for _, r in smp.iterrows():
        s, e = pd.Timestamp(r.start), pd.Timestamp(r.end)
        j = requests.get("https://api.finmindtrade.com/api/v4/data", timeout=30, params={
            "dataset": "TaiwanStockPrice", "data_id": r.code, "start_date": f"{s - pd.Timedelta(days=12):%Y-%m-%d}",
            "end_date": f"{e:%Y-%m-%d}"}).json()
        d = pd.DataFrame(j.get("data", []))
        if d.empty:
            print(f"  {r.code} {s:%Y-%m-%d} 查不到原始價")
            continue
        d["date"] = pd.to_datetime(d.date)
        d = d.set_index("date")
        for day in d.loc[s:e].index:
            prev = float(d.close[d.index < day].iloc[-1])
            pct = 0.07 if day < NEW_LIMIT else 0.10
            raw = prev * (1 - pct)
            t = tick(raw)
            lim = np.ceil(round(raw / t, 6)) * t
            hit = abs(float(d.close[day]) - lim) < 1e-6
            ok, bad = ok + hit, bad + (not hit)
            print(f"  {r.code} {day:%Y-%m-%d} 前收 {prev} 跌停價 {lim:.2f} 收盤 {d.close[day]} 量 {d.Trading_Volume[day] / 1000:,.0f} 張 → {'✓' if hit else '✗ 不是跌停'}")
    print(f"核對 {ok + bad} 個跌停日:{ok} 個正確、{bad} 個誤判")


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    pd.set_option("display.max_rows", 400)
    days, runs = scan()
    print(f"個股日線 {days.index.min():%Y-%m-%d} ~ {days.index.max():%Y-%m-%d}|鎖死的串 {len(runs)} 個|"
          f"曾經一天鎖死 ≥{EVENT_MIN} 檔的日子 {(days.lock >= EVENT_MIN).sum()} 天")
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify(runs)
        sys.exit(0)
    idx = index_close()
    rows = [summarize(days, runs, a, b, idx) for a, b in events(days)]
    t = pd.DataFrame(rows)
    for c in ("a", "b", "peak_lock_d", "idx_low_d"):
        t[c] = pd.to_datetime(t[c]).dt.strftime("%Y-%m-%d")
    print(t.round(3).T.to_string())
    print("鎖死檔數最多的 25 天:")
    print(days.sort_values("lock", ascending=False).head(25).to_string())
    print("最長的 20 串:")
    print(runs.sort_values("n", ascending=False).head(20)[["code", "start", "end", "n", "n_dry", "n_one", "total", "f20", "f60"]].round(3).to_string(index=False))

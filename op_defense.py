"""選擇權賣方(SP=賣出賣權)防守地圖:賣權未平倉集中在哪、各履約價離現在多遠、權利金翻倍大約在指數幾點、
歷史上同樣處境再跌多少。全部是機械式計算,不是下單建議。

資料:data/txo/txo_YYYYMMDD.csv(op_paper.fetch_txo 抓的期交所每日行情)、data/_twii_long.csv(加權指數長期收盤)。
CLI:python -X utf8 op_defense.py
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
TXO_DIR = ROOT / "data" / "txo"
PT = 50                     # TXO 每點 50 元
STOP_MULT = 2.0             # 家規(op_paper.default_sl_tp):賣方權利金翻倍停損
TAKE_LEFT = 0.2             # 家規:權利金剩兩成停利


# ------------------------------------------------------------------ 到期日
def _nth_weekday(y: int, m: int, wd: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(days=7 * (n - 1))


def expiry_of(month: str) -> date:
    """202612=當月第三個週三;202611W4=第四個週三;202611F3=第三個週五。"""
    y, m = int(month[:4]), int(month[4:6])
    tail = month[6:]
    if not tail:
        return _nth_weekday(y, m, 2, 3)
    return _nth_weekday(y, m, 2 if tail[0] == "W" else 4, int(tail[1:]))


# ------------------------------------------------------------------ 定價(Black-76,利率當 0)
def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def put_price(F: float, K: float, T: float, v: float) -> float:
    if T <= 0 or v <= 0:
        return max(K - F, 0.0)
    s = v * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * s * s) / s
    return K * _ncdf(-(d1 - s)) - F * _ncdf(-d1)


def put_delta(F: float, K: float, T: float, v: float) -> float:
    if T <= 0 or v <= 0:
        return -1.0 if K > F else 0.0
    s = v * math.sqrt(T)
    return _ncdf((math.log(F / K) + 0.5 * s * s) / s) - 1


def implied_vol(P: float, F: float, K: float, T: float) -> float:
    if P <= max(K - F, 0.0) + 1e-9 or T <= 0:
        return float("nan")
    lo, hi = 0.01, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if put_price(F, K, T, mid) > P:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def level_for_price(target: float, F: float, K: float, T: float, v: float) -> float:
    """波動率不變、當天:期貨跌到幾點,這口賣權會變成 target 點。"""
    lo, hi = K * 0.5, F
    for _ in range(60):
        mid = (lo + hi) / 2
        if put_price(mid, K, T, v) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ------------------------------------------------------------------ 資料
def load_days(n: int = 2) -> list[pd.DataFrame]:
    out = []
    for f in sorted(TXO_DIR.glob("txo_*.csv"))[-n:]:
        d = pd.read_csv(f, dtype={"month": str})
        for c in ("strike", "settle", "Volume", "OpenInterest"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d["Date"] = d["Date"].astype(str)
        out.append(d.dropna(subset=["strike", "settle"]))
    return out


def synth_future(d: pd.DataFrame, month: str) -> float:
    """買賣權平價反推該到期日的期貨價:取買權、賣權價差最小那一檔,F = K + C − P。"""
    m = d[d["month"] == month]
    w = m.pivot_table(index="strike", columns="cp", values="settle").dropna()
    w = w[(w["買權"] > 0) & (w["賣權"] > 0)]
    k = (w["買權"] - w["賣權"]).abs().idxmin()
    return float(k + w.loc[k, "買權"] - w.loc[k, "賣權"])


def chain(month: str, days: list[pd.DataFrame] | None = None, f_now: float | None = None,
          live: pd.DataFrame | None = None, today: date | None = None) -> dict:
    """一個到期日的賣權表。f_now=現在的期貨價(給「離現在多遠」用;沒給就用結算日反推的期貨價)。
    live=live_puts() 的即時報價:有給就用即時權利金、即時期貨、今天的剩餘天數重算(未平倉仍是前一日)。"""
    days = days or load_days(2)
    d = days[-1]
    asof = pd.Timestamp(d["Date"].iloc[0]).date()
    exp = expiry_of(month)
    use_live = live is not None and len(live) > 20 and f_now
    if use_live:
        asof = today or asof
    cal = max((exp - asof).days, 0)
    T = max(cal, 0.5) / 365
    F = float(f_now) if use_live else synth_future(d, month)
    fn = f_now or F
    p = d[(d["month"] == month) & (d["cp"] == "賣權")].set_index("strike").sort_index()
    c = d[(d["month"] == month) & (d["cp"] == "買權")].set_index("strike").sort_index()
    prev = None
    if len(days) > 1:
        q = days[-2]
        prev = q[(q["month"] == month) & (q["cp"] == "賣權")].set_index("strike")["OpenInterest"]
    lp = live.set_index("strike")["權利金"] if use_live else None
    rows = []
    for k, r in p.iterrows():
        P = float(lp[k]) if use_live and k in lp.index else float(r["settle"])
        if use_live and k not in lp.index:
            continue
        iv = implied_vol(P, F, k, T) if k <= F * 1.02 else float("nan")
        row = dict(履約價=int(k), 權利金=P, 昨結算=float(r["settle"]), 未平倉=int(r["OpenInterest"]), 成交量=int(r["Volume"]),
                   未平倉增減=(int(r["OpenInterest"] - prev.get(k, 0)) if prev is not None else np.nan),
                   離結算期貨=k / F - 1, 離現在=k / fn - 1, 波動率=iv,
                   Delta=put_delta(F, k, T, iv) if iv == iv else np.nan,
                   損益兩平=k - P)
        if iv == iv and P >= 1:
            row["翻倍點"] = level_for_price(P * STOP_MULT, F, k, T, iv)
        rows.append(row)
    t = pd.DataFrame(rows)
    atm = float(p.index[np.argmin(np.abs(p.index - F))])
    straddle = float(p.loc[atm, "settle"] + c.loc[atm, "settle"]) if atm in c.index else float("nan")
    oi_p, oi_c = float(p["OpenInterest"].sum()), float(c["OpenInterest"].sum())
    # 最大痛點:到期落在哪個履約價,買方總共拿回最少
    ks = sorted(set(p.index) | set(c.index))
    pk, ck = p.index.to_numpy(float), c.index.to_numpy(float)
    po, co = p["OpenInterest"].to_numpy(float), c["OpenInterest"].to_numpy(float)
    pain = min(ks, key=lambda s: float((np.clip(pk - s, 0, None) * po).sum() + (np.clip(s - ck, 0, None) * co).sum()))
    return dict(month=month, asof=asof, expiry=exp, 剩餘天數=cal, F=F, f_now=fn, 即時=bool(use_live), 價平=atm, 跨式=straddle,
                價平波動率=(float(t.loc[(t["履約價"] - F).abs().idxmin(), "波動率"]) if use_live
                       else implied_vol(float(p.loc[atm, "settle"]), F, atm, T)), 賣權未平倉=oi_p, 買權未平倉=oi_c,
                最大痛點=float(pain), table=t)


def walls(ch: dict, n: int = 5) -> pd.DataFrame:
    """賣權未平倉最大的幾檔(只看價外)=賣方防守線;同時給前一日的增減。"""
    t = ch["table"]
    t = t[t["履約價"] <= ch["F"]]
    return t.sort_values("未平倉", ascending=False).head(n)[["履約價", "未平倉", "未平倉增減", "權利金", "離現在", "波動率"]]


def months_live(days: list[pd.DataFrame] | None = None) -> list[str]:
    d = (days or load_days(1))[-1]
    asof = pd.Timestamp(d["Date"].iloc[0]).date()
    ms = [m for m in d["month"].unique() if expiry_of(m) > asof]
    return sorted(ms, key=expiry_of)


# ------------------------------------------------------------------ 歷史:同樣處境再跌多少
def twii() -> pd.Series:
    s = pd.read_csv(ROOT / "data" / "_twii_long.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    loc = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", parse_dates=["Date"]).set_index("Date")["Close"].dropna()
    s = loc.combine_first(s)            # 近年以本機每日更新的檔為準(長期檔可能少最新一天)
    return s[~s.index.duplicated()].sort_index()


def regime(s: pd.Series | None = None, off_high: float = -0.15) -> pd.Series:
    """壓力處境:收盤在季線下、離 250 日高點至少 15%。"""
    s = twii() if s is None else s
    return (s < s.rolling(60).mean()) & (s / s.rolling(250).max() - 1 <= off_high)


def mae_table(horizons: tuple = (1, 3, 5, 18), cuts: tuple = (-0.03, -0.05, -0.08, -0.10, -0.15)) -> dict:
    """壓力處境下的每一天:之後 k 個交易日內,收盤最低比當天低多少。"""
    s = twii()
    reg = regime(s)
    out = {}
    for k in horizons:
        fmin = pd.concat([s.shift(-i) for i in range(1, k + 1)], axis=1).min(axis=1) / s - 1
        end = s.shift(-k) / s - 1
        ok = reg & fmin.notna() & s.shift(-k).notna()
        x, e = fmin[ok], end[ok]
        out[k] = dict(天數=k, 樣本=len(x), 中位=float(x.median()), 最差一成=float(x.quantile(0.10)), 最差5趴=float(x.quantile(0.05)),
                      最差1趴=float(x.quantile(0.01)), 最差=float(x.min()), 期末中位=float(e.median()),
                      **{f"碰到{int(abs(c) * 100)}": float((x <= c).mean()) for c in cuts})
    yrs = sorted(set(reg[reg].index.year))
    return dict(rows=out, 年份=yrs, 現在在處境內=bool(reg.iloc[-1]), 總天數=int(reg.sum()))


def levels() -> dict:
    s = twii()
    c = float(s.iloc[-1])
    hi = float(s.tail(250).max())
    rv = float(np.log(s).diff().tail(20).std() * math.sqrt(252))
    y = s[str(s.index[-1].year)]
    return dict(日期=s.index[-1].date(), 收盤=c, 季線=float(s.rolling(60).mean().iloc[-1]), 年線=float(s.rolling(240).mean().iloc[-1]),
                高點=hi, 高點日=s.tail(250).idxmax().date(), 離高點=c / hi - 1, 今年低點=float(y.min()), 今年低點日=y.idxmin().date(),
                一年低點=float(s.tail(250).min()), 一年低點日=s.tail(250).idxmin().date(), 近20日實際波動=rv,
                昨日漲跌=float(s.iloc[-1] / s.iloc[-2] - 1))


def trading_days(a: date, b: date) -> int:
    """a 之後到 b(含)的平日數;不扣國定假日。"""
    return int(np.busday_count(a + timedelta(days=1), b + timedelta(days=1)))


def fwd_min(k: int, min_vol: float = 0.0) -> pd.Series:
    """壓力處境的每一天,之後 k 個交易日內最低收盤比當天低多少。min_vol>0 時再要求近 20 日實際波動 ≥ min_vol。"""
    s = twii()
    reg = regime(s)
    if min_vol:
        reg = reg & (np.log(s).diff().rolling(20).std() * math.sqrt(252) >= min_vol)
    fm = pd.concat([s.shift(-i) for i in range(1, k + 1)], axis=1).min(axis=1) / s - 1
    return fm[reg & s.shift(-k).notna()]


def touch_prob(dist: float, k: int, min_vol: float = 0.0) -> tuple[float, int]:
    """歷史上同樣處境,k 個交易日內收盤曾跌到 dist(負數,例 -0.08)以下的比例,和樣本天數。"""
    x = fwd_min(k, min_vol)
    return (float((x <= dist).mean()) if len(x) else float("nan")), len(x)


def bands(ch: dict, step: int = 1000) -> pd.DataFrame:
    """價外賣權未平倉按每 step 點一段加總——單一履約價太分散時看這個。"""
    t = ch["table"]
    t = t[t["履約價"] <= ch["F"]].copy()
    t["段"] = (t["履約價"] // step) * step
    g = t.groupby("段").agg(未平倉=("未平倉", "sum"), 增減=("未平倉增減", "sum"), 成交量=("成交量", "sum"))
    g["占比"] = g["未平倉"] / g["未平倉"].sum()
    return g.sort_index(ascending=False)


def fwd_end(k: int) -> pd.Series:
    """壓力處境的每一天,k 個交易日後的收盤比當天高低多少。"""
    s = twii()
    reg = regime(s)
    e = s.shift(-k) / s - 1
    return e[reg & e.notna()]


def live_future() -> dict:
    """期交所即時行情:臺指期近月。日盤還沒成交就回夜盤收盤。抓不到回 {}。"""
    import json
    import urllib.request

    def q(mkt: str) -> dict:
        body = {"MarketType": mkt, "SymbolType": "F", "KindID": "1", "CID": "TXF", "ExpireMonth": "",
                "RowSize": "全部", "PageNo": "", "SortColumn": "", "AscDesc": "A"}
        req = urllib.request.Request("https://mis.taifex.com.tw/futures/api/getQuoteList", data=json.dumps(body).encode(),
                                     headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
        rows = json.load(urllib.request.urlopen(req, timeout=20))["RtData"]["QuoteList"]
        r = next(x for x in rows if x["SymbolID"].endswith(("-F", "-M")))
        f = lambda k: float(r[k]) if r.get(k) not in ("", None) else float("nan")
        return dict(名稱=r["DispCName"], 最新=f("CLastPrice"), 參考=f("CRefPrice"), 高=f("CHighPrice"), 低=f("CLowPrice"),
                    量=f("CTotalVolume"), 時間=r.get("CTime", ""), 日期=r.get("CDate", ""))
    try:
        day, night = q("0"), q("1")
    except Exception:
        return {}
    use = day if day["最新"] == day["最新"] else night
    return dict(use, 來源="日盤" if use is day else "夜盤收盤", 夜盤收=night["最新"], 夜盤低=night["低"], 夜盤高=night["高"])


def sp_margin(F: float, K: float, P: float, A: float = 187000, B: float = 94000) -> float:
    """賣出賣權一口的原始保證金(元)=權利金市值+MAX(A−價外值, B)。A、B 是期交所公告值(2026-11-20 查到 187,000/94,000)。"""
    return P * PT + max(A - max(F - K, 0) * PT, B)


def live_puts(month: str) -> pd.DataFrame:
    """期交所即時行情:某個月選(6 碼,如 202612)全部賣權的買價、賣價、成交價。抓不到回空表。
    權利金取買賣價中間;只有一邊或沒掛單就用最新成交價。"""
    import json
    import re
    import urllib.request
    body = {"MarketType": "0", "SymbolType": "O", "KindID": "1", "CID": "TXO", "ExpireMonth": month,
            "RowSize": "全部", "PageNo": "", "SortColumn": "", "AscDesc": "A"}
    try:
        req = urllib.request.Request("https://mis.taifex.com.tw/futures/api/getQuoteList", data=json.dumps(body).encode(),
                                     headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
        rows = json.load(urllib.request.urlopen(req, timeout=20))["RtData"]["QuoteList"]
    except Exception:
        return pd.DataFrame()
    out = []
    for r in rows:
        m = re.match(r"TXO(\d+)([A-X])\d-", r.get("SymbolID", ""))
        if not m or m.group(2) < "M":            # A–L 買權、M–X 賣權
            continue
        f = lambda k: float(r[k]) if r.get(k) not in ("", None) else 0.0
        bid, ask, last = f("CBidPrice1"), f("CAskPrice1"), f("CLastPrice")
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 and ask <= bid * 1.5 + 5 else last
        if mid > 0:
            out.append(dict(strike=float(m.group(1)), 買價=bid, 賣價=ask, 成交=last, 權利金=mid, 時間=r.get("CTime", "")))
    return pd.DataFrame(out)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    days = load_days(2)
    print("資料日", days[-1]["Date"].iloc[0], "| 還沒到期:", months_live(days))
    print(levels())
    for m in months_live(days)[:5]:
        ch = chain(m, days)
        print(f"\n== {m} 到期 {ch['expiry']} 剩 {ch['剩餘天數']} 天 期貨 {ch['F']:.0f} 價平 {ch['價平']:.0f} 跨式 {ch['跨式']:.0f} "
              f"價平波動率 {ch['價平波動率']:.0%} 賣權OI {ch['賣權未平倉']:.0f} 買權OI {ch['買權未平倉']:.0f} 最大痛點 {ch['最大痛點']:.0f}")
        print(walls(ch).round(3).to_string())
    m = mae_table()
    print("\n壓力處境", m["總天數"], "天,年份", m["年份"], "現在在內:", m["現在在處境內"])
    print(pd.DataFrame(m["rows"]).T.round(3).to_string())

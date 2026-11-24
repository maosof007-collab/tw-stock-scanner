# -*- coding: utf-8 -*-
"""
margin_break.py — 維持率破底 × 爆量(當沖頁的斷頭賣壓觀察)
=================================================================
「我需要當沖頁面中顯示融資維持率破底 然後成交量忽然增加的股票」(2026-11-18)。
兩段式:
  ・每晚 build() 掃全市場 → data/_margin_break_watch.csv(一檔一列:估算成本、
    近 20/60/120 日維持率最低點、均量)。約 25 秒,不能放在頁面裡算。
  ・盤中頁 42 只讀這個檔,再用證交所 MIS 抓「離破底最近的那批」即時價量:
    現價÷成本÷0.6 跌破前低 = 破底;累積量÷(5日均量×時段曲線)= 量比;
    近 5 分鐘的量÷這 5 分鐘平常該有的量 = 近5分量比(「忽然」看這欄)。
維持率口徑與斷頭雷達個股曲線(margin_alert.maint_series)完全相同——推估值,
成本今天怎麼變要等晚上融資公布,盤中一律用昨晚的成本。
除權息日:現價先用「昨晚收盤 × 今日漲跌幅」換回還原口徑,才不會假破底。
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

import margin_alert as MA
from twtime import now_tw

ROOT = Path(__file__).parent
WATCH = ROOT / "data" / "_margin_break_watch.csv"
SNAP_DIR = ROOT / "data" / "_rt_flow"          # 盤中暫態(gitignore),與頁 42 快照同目錄
VERSION = 4                                     # 頁面用來判斷長駐進程裡是不是舊模組

WINDOWS = (20, 60, 120)     # 「破底」可選的回看天數
SERIES_DAYS = 240           # 與斷頭雷達個股曲線同一個窗(成本路徑才會一樣)
MIN_AMT20 = 10000.0         # 20 日均成交額不到 1 億(萬元)的整個不看——「成交量太低的不用考慮」(2026-11-18)
AMT_CHOICES = (3000.0, 5000.0, 10000.0, 30000.0, 50000.0)   # 頁面可選的門檻(萬元)
LIVE_CAP = 600              # 盤中最多盯幾檔(MIS 一次 100 檔;11/18 實測候選 529 檔、一輪約 9 秒)
BURST = 3.0                 # 近5分量比 ≥ 3 倍 → ⚡
EPS = 0.05                  # 跌破前低至少 0.05% 才算(比一檔跳動小,只擋平盤的進位誤差)
_BATCH = 100

# 量能時段曲線(與 rt_flow 同一組數字;不 import rt_flow,免得夜間建檔時載入整個族群表)
_VC_MIN = [0, 15, 30, 60, 120, 180, 240, 270]
_VC_CUM = [.02, .14, .20, .30, .45, .60, .80, 1.0]


def _frac(minute: float) -> float:
    """開盤後第幾分鐘 → 平常這時候已經成交了全日的幾成。"""
    return float(np.interp(min(max(minute, 1), 270), _VC_MIN, _VC_CUM))


def _mins(hhmmss: str) -> float:
    h, m, s = (int(x) for x in str(hhmmss)[:8].split(":"))
    return (h * 3600 + m * 60 + s - 9 * 3600) / 60


# ─────────────────────────── 每晚建檔 ───────────────────────────
def _price(code: str) -> tuple[pd.DataFrame, str] | None:
    for suf, ex in ((".TW.csv", "tse"), (".TWO.csv", "otc")):
        p = ROOT / "data" / f"{code}{suf}"
        if p.exists():
            try:
                px = pd.read_csv(p, usecols=["Date", "Close", "Volume"], parse_dates=["Date"])
            except Exception:
                return None
            px = px.dropna(subset=["Close"]).set_index("Date")
            return px[~px.index.duplicated(keep="last")].sort_index(), ex
    return None


def build(asof: str | None = None) -> pd.DataFrame:
    """全市場掃一輪,寫 WATCH。一檔一列,資料日=融資與股價都到齊的最新一天。
    asof='YYYY-MM-DD':只用到那天為止的資料重算(驗證用,不寫檔)。"""
    cut = pd.Timestamp(asof) if asof else None
    try:
        sl = pd.read_csv(ROOT / "data" / "stock_list.csv", dtype={"code": str})
        names = dict(zip(sl["code"], sl["name"]))
    except Exception:
        names = {}
    rows = []
    for f in sorted(MA.MARGIN_DIR.glob("*_margin.csv")):
        code = f.name.split("_")[0]
        if not (code.isdigit() and len(code) == 4):
            continue
        m = MA._load_margin(code)
        got = _price(code)
        if m is None or got is None or len(m) < 80:
            continue
        px, ex = got
        if cut is not None:
            m, px = m[m.index <= cut], px[px.index <= cut]
        if len(m) < 80 or len(px) < 30 or px.index[-1] != m.index[-1]:      # 新鮮度:兩邊最新日要一致
            continue
        m = m.tail(SERIES_DAYS + MA.LOOKBACK)
        close = px["Close"].reindex(m.index).ffill()
        bal = m["margin_balance"].astype(float)
        if not (bal.iloc[-2] >= MA.MIN_BAL) or not (close.iloc[-1] >= MA.MIN_PRICE):
            continue
        cost = MA._weighted_cost_arr(bal.values, close.values)
        ratio = pd.Series(close.values / np.where(cost > 0, cost, np.nan) / 0.6 * 100.0,
                          index=m.index).tail(SERIES_DAYS)
        if len(ratio) < 61 or not np.isfinite(ratio.iloc[-1]) or not cost[-1] > 0:
            continue
        prior = ratio.iloc[:-1]                               # 不含資料日
        vol = px["Volume"].astype(float) / 1000.0             # 張
        vol = vol[vol > 0]
        amt = (px["Close"] * px["Volume"]).tail(20).mean() / 1e4   # 萬元
        quota = float(m["margin_quota"].iloc[-1] or 0)
        row = {
            "日期": f"{m.index[-1]:%Y-%m-%d}", "代號": code,
            "名稱": names.get(code, code), "市場": ex,
            "收盤": round(float(close.iloc[-1]), 2),
            "漲跌%": round((float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2),
            "估算成本": round(float(cost[-1]), 3),
            "維持率%": round(float(ratio.iloc[-1]), 4),
            "融資餘額": int(bal.iloc[-1]),
            "日增減%": round((bal.iloc[-1] / bal.iloc[-2] - 1) * 100, 2),
            "使用率%": round(bal.iloc[-1] / quota * 100, 1) if quota > 0 else None,
            "量": round(float(vol.iloc[-1]), 0) if len(vol) else 0.0,
            "均量5前": round(float(vol.iloc[-6:-1].mean()), 1) if len(vol) >= 6 else None,
            "均量5": round(float(vol.tail(5).mean()), 1) if len(vol) else None,
            "均額20": round(float(amt), 0),
        }
        for n in WINDOWS:
            seg = prior.tail(n)
            row[f"低{n}"] = round(float(seg.min()), 4)
            row[f"低{n}日"] = f"{seg.idxmin():%m/%d}"
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["日期"] == df["日期"].max()].reset_index(drop=True)
    if cut is None and len(df) >= 300:      # 檔數太少=資料沒到齊,不蓋掉舊檔
        df.to_csv(WATCH, index=False, encoding="utf-8-sig")
    return df


def refresh() -> str:
    """每晚排程(notify_push)呼叫:融資多了新的一天才重建,否則跳過。看資料日,不看檔案時間。"""
    days = []
    for code in ("2330", "5347"):          # 上市、上櫃各看一檔:兩邊融資公布時間不同
        m, px = MA._load_margin(code), MA._close_series(code)
        if m is None or px is None or m.index[-1] != px.index[-1]:
            return f"{code} 的融資與股價最新日不一致(還沒到齊),跳過"
        days.append(m.index[-1])
    if days[0] != days[1]:
        return "上市與上櫃的融資最新日不一致(還沒到齊),跳過"
    d = f"{days[0]:%Y-%m-%d}"
    old = load()
    if len(old) and old["日期"].max() >= d and (old["市場"] == "otc").sum() >= 100:
        return f"{d} 已建過,跳過"
    df = build()
    if len(df) < 300:
        return f"只掃到 {len(df)} 檔(資料沒到齊),保留舊檔"
    return f"{d}:{len(df)} 檔;收盤破 60 日低 {len(eod_table(df, 60))} 檔,其中爆量 {len(hot(eod_table(df, 60)))} 檔"


def load() -> pd.DataFrame:
    if not WATCH.exists():
        return pd.DataFrame()
    return pd.read_csv(WATCH, dtype={"代號": str})


# ─────────────────────────── 收盤口徑(資料日當天) ───────────────────────────
def eod_table(w: pd.DataFrame, n: int = 60, min_amt: float = MIN_AMT20) -> pd.DataFrame:
    """資料日收盤就跌破前 n 日最低維持率的名單(爆量與否由頁面再篩)。
    20 日均成交額不到 min_amt(萬)的不看。"""
    if w.empty:
        return w
    t = w[w["均額20"] >= min_amt].copy()
    t["前低%"] = t[f"低{n}"]
    t["前低日"] = t[f"低{n}日"]
    t["跌破%"] = (t["維持率%"] / t["前低%"] - 1) * 100
    t = t[t["跌破%"] <= -EPS].copy()
    t["量比"] = t["量"] / t["均量5前"]
    t["成交額(億)"] = t["收盤"] * t["量"] * 1000 / 1e8
    return t.sort_values("量比", ascending=False).reset_index(drop=True)


# ─────────────────────────── 盤中口徑 ───────────────────────────
def candidates(w: pd.DataFrame, n: int = 60, cap: int = LIVE_CAP,
               min_amt: float = MIN_AMT20) -> pd.DataFrame:
    """今天有機會破底的名單。今天的破底線=min(前 n 日最低, 資料日當天)——
    資料日已經是新低的,今天只要再跌就算。跌停(-10%)也到不了的不盯;
    流動性不夠的不盯;還是太多就取離破底線最近的 cap 檔。"""
    if w.empty:
        return w
    t = w.copy()
    t["前低%"] = np.minimum(t[f"低{n}"], t["維持率%"])
    t["前低日"] = np.where(t["維持率%"] < t[f"低{n}"], t["日期"].str[5:].str.replace("-", "/"),
                         t[f"低{n}日"])
    t["破底價"] = t["前低%"] / 100.0 * 0.6 * t["估算成本"]
    t["距破底%"] = (t["收盤"] / t["破底價"] - 1) * 100
    t = t[(t["距破底%"] <= 10.0) & (t["均額20"] >= min_amt) & (t["均量5"] > 0)]
    return t.sort_values(["距破底%", "均額20"], ascending=[True, False]).head(cap).reset_index(drop=True)


_Q: dict = {"key": None, "at": 0.0, "df": None}


def quotes(cand: pd.DataFrame, max_age: float = 50.0) -> pd.DataFrame:
    """MIS 即時價量:代號/price/vol(張)/y/d(YYYYMMDD)/t。50 秒內重複呼叫用上一輪的;
    收盤(13:35 後抓到的)就不再重抓。"""
    import rt_flow as RT
    key = (len(cand), "|".join(cand["代號"].head(5)))
    now = time.time()
    if _Q["df"] is not None and _Q["key"] == key:
        closed = _Q.get("closed") and _Q.get("day") == f"{now_tw():%Y%m%d}"
        if closed or now - _Q["at"] < max_age:
            return _Q["df"]
    items = [f"{ex}_{c}.tw" for c, ex in zip(cand["代號"], cand["市場"])]
    rows = []
    for i in range(0, len(items), _BATCH):
        try:
            for r in RT._mis("|".join(items[i:i + _BATCH])):
                v, y = RT._num(r.get("v")), RT._num(r.get("y"))
                if v is None or not y:
                    continue
                z = RT._num(r.get("z"))
                if not z or z <= 0:          # 最近 5 秒沒成交 → 最佳買賣中點 → 單邊
                    a0 = RT._num(str(r.get("a", "")).split("_")[0])
                    b0 = RT._num(str(r.get("b", "")).split("_")[0])
                    z = (a0 + b0) / 2 if (a0 and b0) else (a0 or b0)
                if not z or z <= 0:
                    continue
                rows.append({"代號": r.get("c"), "price": z, "vol": v, "y": y,
                             "d": str(r.get("d", "")), "t": str(r.get("t", ""))})
        except Exception:
            continue
        time.sleep(0.25)
    df = pd.DataFrame(rows, columns=["代號", "price", "vol", "y", "d", "t"])
    t = now_tw()
    _Q.update(key=key, at=now, df=df, day=f"{t:%Y%m%d}",
              closed=bool(len(df)) and f"{t:%H:%M}" >= "13:35")
    return df


def record(q: pd.DataFrame, day: str) -> None:
    """把這一輪存下來(算近5分量比用)。同一分鐘不重寫。"""
    if q.empty:
        return
    ts = f"{now_tw():%H:%M:%S}"
    if not ("09:00" <= ts[:5] <= "13:35"):
        return
    f = SNAP_DIR / f"_mbreak_{day}.csv"
    try:
        SNAP_DIR.mkdir(exist_ok=True)
        if f.exists():
            last = str(pd.read_csv(f, usecols=["ts"]).ts.iloc[-1])
            if last[:5] == ts[:5]:
                return
        q.assign(ts=ts)[["ts", "代號", "vol"]].to_csv(
            f, mode="a", header=not f.exists(), index=False, encoding="utf-8-sig")
    except Exception:
        pass


def burst(hist: pd.DataFrame, avg5: pd.Series, lookback: float = 5.0) -> pd.Series:
    """近5分量比:最近約 5 分鐘成交的張數 ÷ 這段時間平常該有的張數。
    hist=當日逐分紀錄(ts/代號/vol 累積張);紀錄不滿 3 分鐘回傳空。"""
    if hist is None or hist.empty:
        return pd.Series(dtype=float)
    h = hist.copy()
    h["m"] = h["ts"].map(_mins)
    now_m = h["m"].max()
    old = h[h["m"] <= now_m - lookback + 0.5]
    if old.empty:
        old = h[h["m"] <= now_m - 3]        # 至少要隔 3 分鐘
        if old.empty:
            return pd.Series(dtype=float)
    base_m = old["m"].max()
    v0 = old[old["m"] == base_m].set_index("代號")["vol"]
    v1 = h[h["m"] == now_m].set_index("代號")["vol"]
    expect = avg5 * (_frac(now_m) - _frac(base_m))
    out = (v1 - v0).clip(lower=0) / expect.reindex(v1.index)
    return out.replace([np.inf, -np.inf], np.nan).dropna()


def load_hist(day: str) -> pd.DataFrame:
    f = SNAP_DIR / f"_mbreak_{day}.csv"
    if not f.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(f, dtype={"代號": str})
    except Exception:
        return pd.DataFrame()


def live_table(cand: pd.DataFrame, q: pd.DataFrame, hist: pd.DataFrame | None = None,
               minute: float | None = None) -> pd.DataFrame:
    """候選 × 即時報價 → 今天已經破底的名單(爆量與否由頁面再篩)。
    minute=開盤後第幾分鐘(量比的分母要用);不給就自己判斷:報價是今天的用現在時間,否則當作已收盤。"""
    if minute is None and len(q):
        t0 = now_tw()
        minute = ((t0.hour - 9) * 60 + t0.minute + t0.second / 60
                  if q["d"].max() == f"{t0:%Y%m%d}" else 270.0)
    if cand.empty or q.empty:
        return pd.DataFrame()
    t = cand.merge(q, on="代號")
    if t.empty:
        return t
    t["今漲跌%"] = (t["price"] / t["y"] - 1) * 100
    adj = t["收盤"] * t["price"] / t["y"]            # 還原口徑的現價(除權息日 y≠昨收)
    t["最新"] = t["price"]
    t["維持率%"] = adj / t["估算成本"] / 0.6 * 100
    t["跌破%"] = (t["維持率%"] / t["前低%"] - 1) * 100
    t["量比"] = t["vol"] / (t["均量5"] * _frac(minute))
    b = burst(hist, t.set_index("代號")["均量5"]) if hist is not None else pd.Series(dtype=float)
    t["近5分量比"] = t["代號"].map(b)
    t["成交額(億)"] = t["price"] * t["vol"] * 1000 / 1e8
    t["量"] = t["vol"]
    t = t[t["跌破%"] <= -EPS]
    return t.sort_values("量比", ascending=False).reset_index(drop=True)


def stale_share(cand: pd.DataFrame, q: pd.DataFrame) -> float:
    """報價的昨收和名單的收盤對不上的比例。正常只有除權息的幾檔;很高=名單不是前一個交易日建的。"""
    t = cand.merge(q, on="代號")
    return float(((t["y"] / t["收盤"] - 1).abs() > 0.005).mean()) if len(t) else 0.0


def live_day(q: pd.DataFrame, w: pd.DataFrame) -> str | None:
    """報價是不是比建檔資料日新的一天?是 → 回傳那天(YYYYMMDD),否 → None(用收盤口徑)。"""
    if q.empty or w.empty:
        return None
    d = q["d"].max()
    return d if d > w["日期"].max().replace("-", "") else None


def hot(t: pd.DataFrame, min_vr: float = 1.5) -> pd.DataFrame:
    """破底名單裡「爆量」的:全日量比 ≥ min_vr,或近 5 分鐘 ≥ BURST 倍。
    成交量太低的在 eod_table / candidates 就已經排除(看 20 日均成交額),這裡不再篩。"""
    if t.empty:
        return t
    b = t["近5分量比"] if "近5分量比" in t.columns else pd.Series(np.nan, index=t.index)
    out = t[(t["量比"] >= min_vr) | (b >= BURST)].copy()
    out["爆量"] = np.where(b.reindex(out.index) >= BURST, "⚡ 近5分", "全日")
    return out


if __name__ == "__main__":
    t0 = time.time()
    w = build()
    print(f"建檔 {len(w)} 檔,資料日 {w['日期'].max() if len(w) else '—'},{time.time()-t0:.0f} 秒 → {WATCH.name}")
    for n in WINDOWS:
        e = eod_table(w, n)
        print(f"  破 {n} 日低 {len(e)} 檔|其中爆量(量比≥1.5):{len(hot(e))} 檔|盤中候選 {len(candidates(w, n))} 檔"
              f"(均額20≥{MIN_AMT20/1e4:.0f}億的 {int((w['均額20'] >= MIN_AMT20).sum())} 檔裡)")
    e = hot(eod_table(w, 60))
    if len(e):
        print(e.head(15)[["代號", "名稱", "收盤", "漲跌%", "維持率%", "前低%", "前低日",
                          "量比", "融資餘額", "日增減%"]].to_string(index=False))

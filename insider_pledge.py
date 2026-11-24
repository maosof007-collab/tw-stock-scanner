# -*- coding: utf-8 -*-
"""
insider_pledge.py — 內部人設質事件研究:內部人把股票拿去質押之後,股價多久才動?(2026-11-18)
=================================================================
來源:公開資訊觀測站「內部人設質解質彙總公告」(全市場、逐筆、原始申報)
  https://siis.twse.com.tw/server-java/STAMAK03?step=1&order=1&TYPEK=sii|otc&year=民國&smonth=MM&emonth=MM
  欄位:代號、公司、身份別、姓名、異動日、設質股數、解質股數、累積設質、質權人、申報日
快取:data/insider_pledge.csv.gz(2014 年起;只在手動重跑時抓,一年一次請求、全部約 2 分鐘,之後只重抓今年和去年)
事件:某人「累積設質從 0 變成有」(首次質押或全部解質後再押),且當次質押 ≥ 100 張、市值 ≥ 3,000 萬。
     同一家公司 12 個月內只取第一筆。進場價用「申報日」之後第一個交易日的收盤(公開看得到的那天)。
量測:之後 3/6/12/24 個月報酬、同一天全市場個股中位數(對照組)、第一次漲到 +50% 花多久、那之前最深跌多少。
限制:股價檔是還原價且沒有已下市的公司(下市的事件會被丟掉,結果偏樂觀);質押用途公告不寫。
手動:python -X utf8 insider_pledge.py [--refresh]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = DATA / "insider_pledge.csv.gz"
COLS = ["code", "name", "role", "who", "date", "pledge", "release", "cum", "lender", "note", "filed", "mkt"]
H = {"3m": 63, "6m": 126, "12m": 252, "24m": 504}          # 交易日
TARGET = 1.5                                               # 「發動」= 收盤第一次站上進場價的 1.5 倍


def _year(mk: str, y: int) -> list:
    """一個市場一整年的公告(一次請求約 1 秒)。"""
    import requests
    from bs4 import BeautifulSoup

    import ssl_trust
    u = (f"https://siis.twse.com.tw/server-java/STAMAK03?colorchg=1&step=1&order=1&TYPEK={mk}"
         f"&year={y - 1911}&smonth=01&emonth=12&")
    for _ in range(4):
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=180, verify=str(ssl_trust.build()))
            if r.status_code == 200 and len(r.content) > 500:
                rows = []
                for tr in BeautifulSoup(r.content.decode("big5", errors="replace"), "html.parser").find_all("tr"):
                    c = [x.get_text(" ", strip=True) for x in tr.find_all("td")]
                    if len(c) == 11 and c[0][:4].isdigit():
                        rows.append(c + [mk])
                return rows
        except Exception as ex:
            print(f"{mk} {y} 重試:{ex}")
        time.sleep(15)
    return []


def fetch(refresh: bool = False, since: int = 2014) -> pd.DataFrame:
    """原始公告長表(字串欄位)。有快取就讀;refresh=True 補抓快取沒有的年份,今年和去年一律重抓。"""
    old = pd.read_csv(CACHE, dtype=str).fillna("") if CACHE.exists() else pd.DataFrame(columns=COLS)
    if CACHE.exists() and not refresh:
        return old
    t = now_tw()
    key = (old.mkt + "|" + old.date.str.split("/").str[0]) if len(old) else pd.Series(dtype=str)
    have = set(key)
    todo = [(mk, y) for mk in ("sii", "otc") for y in range(since, t.year + 1)
            if y >= t.year - 1 or f"{mk}|{y - 1911}" not in have]
    rows = old[~key.isin({f"{mk}|{y - 1911}" for mk, y in todo})].values.tolist() if len(old) else []
    for mk, y in todo:
        got = _year(mk, y)
        rows += got
        print(f"質押公告 {mk} {y}:{len(got)} 筆")
        time.sleep(2.5)
    DATA.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=COLS).to_csv(CACHE, index=False, compression="gzip")
    return pd.read_csv(CACHE, dtype=str).fillna("")


def _roc(s: pd.Series) -> pd.Series:
    p = s.str.split("/", expand=True)
    return pd.to_datetime((p[0].astype(int) + 1911).astype(str) + "-" + p[1] + "-" + p[2], errors="coerce")


def load(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    """整理後的逐筆公告:日期轉西元、股數轉數字、身份分組(grp)、是不是自然人本人(self)、質權人種類(lend)。"""
    d = (fetch() if raw is None else raw).copy()
    d = d[d.date.str.match(r"^\d{2,3}/\d\d/\d\d$") & d.filed.str.match(r"^\d{2,3}/\d\d/\d\d$")]
    d["date"], d["filed"] = _roc(d.date), _roc(d.filed)
    for c in ("pledge", "release", "cum"):
        d[c] = pd.to_numeric(d[c].str.replace(",", ""), errors="coerce").fillna(0)
    d["role"] = d.role.str.replace(r"^\S+\s+", "", regex=True)
    who = d.who.str.normalize("NFKC").str.replace(r"\s+", "", regex=True)      # 全形英文、空白先正規化
    corp = who.str.contains(r"公司|基金|有限|協會|法人|信託|銀行|合夥|投資|控股|群島商|香港商|薩摩亞商|開曼|"
                            r"LTD|INC|CORP|LLC|LIMITED|HOLDING|CO\.|EMERGING|L\.P\.", case=False, regex=True)
    d["self"] = d.role.str.endswith("本人") & ~corp
    r = d.role
    d["grp"] = np.select([r.str.contains("董事長|總經理") & ~r.str.contains("副總經理|副董事長"),
                          r.str.contains("大股東"), r.str.contains("董事|監察人")],
                         ["董事長、總經理", "大股東", "董事、監察人"], "其他經理人")
    d["lend"] = np.where(d.lender.str.contains("證券|證金|綜合證|借貸款項"), "證券商、證金", "銀行等")
    d = d.dropna(subset=["date", "filed"]).drop_duplicates(["code", "who", "date", "pledge", "release", "cum"])
    return d.sort_values(["code", "who", "date", "filed"]).reset_index(drop=True)


def closes() -> pd.DataFrame:
    """全市場還原收盤價寬表(日期 × 代號)。讀 data/<代號>.TW(O).csv,約 1 分鐘。"""
    out = {}
    for p in list(DATA.glob("[0-9]*.TW.csv")) + list(DATA.glob("[0-9]*.TWO.csv")):
        code = p.name.split(".")[0]
        if len(code) != 4:
            continue
        try:
            s = pd.read_csv(p, usecols=["Date", "Close"], parse_dates=["Date"]).drop_duplicates("Date").set_index("Date").Close
        except Exception:
            continue
        out[code] = s[s > 0]
    return pd.DataFrame(out).sort_index()


def events(d: pd.DataFrame, px: pd.DataFrame, min_lots: int = 100, min_value: float = 3e7,
           gap: int = 365) -> pd.DataFrame:
    """首次質押事件(累積設質 0 → 有)。回傳一列一事件:code,name,who,role,grp,self,lend,date,filed,lots,value,t0,p0。"""
    e = d[(d.pledge > 0) & ((d.cum - d.pledge + d.release).abs() < 1) & (d.pledge >= min_lots * 1000)].copy()
    e = e[e.code.isin(px.columns) & (e.filed >= px.index[0])]
    idx = px.index
    pos = idx.searchsorted(e.filed.values, side="right")            # 申報日之後第一個交易日
    e = e[pos < len(idx)].assign(i0=pos[pos < len(idx)])
    e["t0"] = idx[e.i0.values]
    e["p0"] = [px.iat[i, px.columns.get_loc(c)] for i, c in zip(e.i0, e.code)]
    e = e.dropna(subset=["p0"])
    e["lots"], e["value"] = e.pledge / 1000, e.pledge * e.p0
    e = e[e.value >= min_value].sort_values(["code", "t0"])
    keep, last = [], {}
    for r in e.itertuples():                                       # 同公司 gap 天內只留第一筆
        if r.code not in last or (r.t0 - last[r.code]).days > gap:
            keep.append(r.Index)
            last[r.code] = r.t0
    return e.loc[keep].reset_index(drop=True)


def study(e: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """每個事件加上:各期間報酬 r_*、同日全市場中位數 b_*、超額 x_*、前 12 個月報酬 pre、
    第一次漲到 +50% 的月數 hit_m(沒到是 NaN)、觀察了幾個月 obs_m、到那之前(最多 24 個月)最深跌幅 dd、
    同日全市場「24 個月內漲到 +50%」的比例 b_hit24。"""
    A = px.values
    col = {c: k for k, c in enumerate(px.columns)}
    n = len(px)
    out = []
    base = {}
    for r in e.itertuples():
        i, k = int(r.i0), col[r.code]
        row = dict(pre=A[i, k] / A[i - 252, k] - 1 if i >= 252 else np.nan)
        if i not in base:
            b = {}
            for nm, h in H.items():
                b[nm] = np.nanmedian(A[i + h] / A[i] - 1) if i + h < n else np.nan
            if i + H["24m"] < n:
                with np.errstate(all="ignore"):
                    b["hit24"] = np.nanmean((np.nanmax(A[i + 1:i + 1 + H["24m"]], axis=0) / A[i] >= TARGET)[~np.isnan(A[i])])
            else:
                b["hit24"] = np.nan
            base[i] = b
        for nm, h in H.items():
            row[f"r_{nm}"] = A[i + h, k] / A[i, k] - 1 if i + h < n else np.nan
            row[f"b_{nm}"] = base[i][nm]
            row[f"x_{nm}"] = row[f"r_{nm}"] - row[f"b_{nm}"]
        row["b_hit24"] = base[i]["hit24"]
        fut = A[i + 1:, k] / A[i, k]
        w = np.where(fut >= TARGET)[0]
        row["hit_m"] = (w[0] + 1) / 21 if len(w) else np.nan
        row["obs_m"] = int((~np.isnan(fut)).sum()) / 21
        end = min(w[0] + 1 if len(w) else len(fut), H["24m"])
        row["dd"] = np.nanmin(fut[:end]) - 1 if end > 0 and not np.all(np.isnan(fut[:end])) else np.nan
        out.append(row)
    return pd.concat([e.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def km_median(hit_m: pd.Series, obs_m: pd.Series) -> float:
    """Kaplan–Meier 中位數:有一半的事件漲到 +50% 要幾個月(還沒到的算「觀察到目前為止」)。到不了一半回傳 NaN。"""
    t = hit_m.fillna(obs_m).values
    ev = hit_m.notna().values
    s = 1.0
    for x in np.sort(np.unique(t[ev])):
        s *= 1 - ((t == x) & ev).sum() / (t >= x).sum()
        if s <= 0.5:
            return float(x)
    return float("nan")


def summary(s: pd.DataFrame) -> dict:
    """一組事件的統計:筆數、各期間報酬中位數/對照/超額/勝率、24 個月內發動比例(對照)、發動中位月數、最深跌幅中位數。"""
    o = dict(n=len(s))
    for nm in H:
        v = s.dropna(subset=[f"r_{nm}"])
        o[f"n_{nm}"] = len(v)
        o[f"r_{nm}"], o[f"b_{nm}"] = v[f"r_{nm}"].median(), v[f"b_{nm}"].median()
        o[f"x_{nm}"] = v[f"x_{nm}"].median()
        o[f"up_{nm}"] = (v[f"r_{nm}"] > 0).mean()
        o[f"win_{nm}"] = (v[f"x_{nm}"] > 0).mean()
    full = s[s.obs_m >= 24]                                   # 觀察滿 24 個月的才算發動比例
    o["n_full"] = len(full)
    o["hit12"] = (full.hit_m <= 12).mean()
    o["hit24"] = (full.hit_m <= 24).mean()
    o["b_hit24"] = full.b_hit24.mean()
    o["km"] = km_median(s.hit_m, s.obs_m)
    o["hit_med"] = s.hit_m.dropna().median()
    o["dd"] = s.dd.median()
    return o


if __name__ == "__main__":
    raw = fetch(refresh="--refresh" in sys.argv)
    d = load(raw)
    px = closes()
    s = study(events(d[d.self], px), px)                       # 主樣本:自然人本人(先篩再去重)
    print(f"公告 {len(d):,} 筆、自然人本人首次質押事件 {len(s):,} 個({s.t0.min():%Y/%m}~{s.t0.max():%Y/%m})")
    for nm, g in [("自然人本人", s)] + [(k, v) for k, v in s.groupby("grp")]:
        o = summary(g)
        print(f"{nm}:n={o['n']} 12m 中位 {o['r_12m']:+.1%}(對照 {o['b_12m']:+.1%}、超額 {o['x_12m']:+.1%}、勝率 {o['win_12m']:.0%})"
              f" 24m 內 +50%:{o['hit24']:.0%}(對照 {o['b_hit24']:.0%}) 發動中位 {o['km']:.0f} 個月")

"""內需/車用/單車/國防 在空頭的表現(海報 make_poster_domestic.py 用)。

三個問題:
  1. fall_table()    歷次大盤下跌,各族群成分股中位數跌多少、比大盤多跌還是少跌
  2. rebound_table() 大盤落底後 60 / 120 個交易日,各族群漲多少、有沒有落後大盤
  3. king_table()    「蠱王」:各產業營收最大那一家,市占 2019 → 現在有沒有上升;股價比同業中位數好還是差
族群:官方產業別(data/stock_list.csv 的 sector)+ 手選的單車、國防名單(代號已用 stock_list 名稱核對)。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"

# (名稱, 大盤高點日, 大盤低點日);最後一段還沒落底,終點=資料最後一天
EPISODES = [("2015", "2015-04-27", "2015-08-24"), ("2018", "2018-10-01", "2019-01-03"), ("2020", "2020-01-14", "2020-03-19"),
            ("2022", "2022-01-04", "2022-10-25"), ("2025", "2025-02-20", "2025-04-09"), ("2026", "2026-10-06", None)]
PAST = [e[0] for e in EPISODES[:-1]]
PREV_LOW = EPISODES[-2][2]                                               # 上一次落底日(2025-04-09)
NOW = EPISODES[-1][0]

SECTORS = {"食品": "食品工業", "貿易百貨": "貿易百貨業", "觀光餐旅": "觀光餐旅", "油電燃氣": "油電燃氣業", "金融": "金融保險業", "車用": "汽車工業"}
TELECOM = ["2412", "3045", "4904"]                                      # 中華電、台灣大、遠傳
BIKE = ["9921", "9914", "5306", "1517", "1526", "8933", "6804"]          # 巨大、美利達、桂盟、利奇、日馳、愛地雅、明係
DEFENSE = ["2634", "8033", "2630", "6753", "2208", "5222"]              # 漢翔、雷虎、亞航、龍德造船(系統軍工組)+台船、全訊
EXPECT = {"2412": "中華電", "3045": "台灣大", "4904": "遠傳", "9921": "巨大", "9914": "美利達", "5306": "桂盟", "1517": "利奇",
          "1526": "日馳", "8933": "愛地雅", "6804": "明係", "2634": "漢翔", "8033": "雷虎", "2630": "亞航", "6753": "龍德造船",
          "2208": "台船", "5222": "全訊"}
KIND = {"食品": "內需", "貿易百貨": "內需", "觀光餐旅": "內需", "油電燃氣": "內需", "金融": "內需", "電信三雄": "內需",
        "車用": "車用", "單車": "單車", "國防": "國防"}
ORDER = list(KIND)


@lru_cache(maxsize=1)
def stock_list() -> pd.DataFrame:
    return pd.read_csv(D / "stock_list.csv", dtype=str)


@lru_cache(maxsize=1)
def groups() -> dict:
    sl = stock_list()
    nm = dict(zip(sl["code"], sl["name"]))
    bad = [f"{c} 應為 {n},名單上是 {nm.get(c)}" for c, n in EXPECT.items() if nm.get(c) != n]
    if bad:                                                             # 代號必先查證:名稱對不上就不算
        raise ValueError("手選名單代號與 stock_list 名稱不符:" + ";".join(bad))
    g = {k: sorted(sl[sl["sector"] == v]["code"]) for k, v in SECTORS.items()}
    g["電信三雄"], g["單車"], g["國防"] = TELECOM, BIKE, DEFENSE
    return {k: g[k] for k in ORDER}


def name(code: str) -> str:
    sl = stock_list()
    return dict(zip(sl["code"], sl["name"])).get(code, code)


@lru_cache(maxsize=4000)
def px(code: str) -> pd.Series:
    for suf in (".TW.csv", ".TWO.csv"):
        f = D / f"{code}{suf}"
        if f.exists():
            d = pd.read_csv(f, usecols=["Date", "Close"], parse_dates=["Date"]).dropna().drop_duplicates("Date")
            return d.set_index("Date")["Close"].sort_index()
    return pd.Series(dtype=float)


@lru_cache(maxsize=1)
def twii() -> pd.Series:
    """加權指數收盤:以每日更新的 benchmark_TWII.csv 為準,較早的日期用 _twii_long.csv 補。"""
    loc = pd.read_csv(D / "benchmark_TWII.csv", parse_dates=["Date"]).set_index("Date")["Close"].dropna()
    f = D / "_twii_long.csv"
    if f.exists():
        loc = loc.combine_first(pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0].dropna())
    return loc.sort_index()


def _ret(s: pd.Series, a, b, min_hist: int = 60) -> float:
    """a 日(含)前最後一筆 → b 日(含)前最後一筆;a 之前不到 min_hist 筆、或 b 附近沒有報價,回 NaN。"""
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    s0, s1 = s[:a], s[:b]
    if len(s0) < min_hist or s1.empty or s1.index[-1] < b - pd.Timedelta(days=10):
        return np.nan
    return float(s1.iloc[-1] / s0.iloc[-1] - 1)


def episodes() -> list:
    last = twii().index[-1]
    return [(n, pd.Timestamp(a), pd.Timestamp(b) if b else last) for n, a, b in EPISODES]


def member_table() -> pd.DataFrame:
    """每檔一列:歷次下跌的漲跌幅、落底後 60/120 日、現在有沒有站上年線、2019 年初至今。"""
    tw = twii()
    rows = []
    for g, codes in groups().items():
        for c in codes:
            s = px(c)
            if s.empty:
                continue
            r = dict(族群=g, 代號=c, 名稱=name(c))
            for n, a, b in episodes():
                r[n] = _ret(s, a, b)
            for n, a, b in episodes()[:-1]:
                i = tw.index.get_loc(b)
                for k in (60, 120):
                    r[f"{n}+{k}"] = _ret(s, b, tw.index[i + k]) if i + k < len(tw) else np.nan
            ma = s.rolling(240).mean()
            r["站上年線"] = bool(s.iloc[-1] > ma.iloc[-1]) if len(s) > 240 else np.nan
            r["2019至今"] = _ret(s, "2019-01-02", s.index[-1])
            r["前波"] = _ret(s, PREV_LOW, EPISODES[-1][1])           # 上一次落底 → 這次大盤高點
            rows.append(r)
    return pd.DataFrame(rows)


def index_row() -> dict:
    tw = twii()
    r = {n: _ret(tw, a, b) for n, a, b in episodes()}
    for n, a, b in episodes()[:-1]:
        i = tw.index.get_loc(b)
        for k in (60, 120):
            r[f"{n}+{k}"] = float(tw.iloc[i + k] / tw.iloc[i] - 1) if i + k < len(tw) else np.nan
    r["2019至今"] = _ret(tw, "2019-01-02", tw.index[-1])
    r["前波"] = _ret(tw, PREV_LOW, EPISODES[-1][1])
    return r


def fall_table(m: pd.DataFrame) -> pd.DataFrame:
    """族群成分股中位數;差距=族群−大盤(百分點,正=跌得比大盤少)。"""
    ix = index_row()
    cols = PAST + [NOW]
    g = m.groupby("族群")[cols].median().reindex(ORDER)
    g.insert(0, "檔數", m.groupby("族群")["代號"].count().reindex(ORDER))
    for c in cols:
        g[f"差{c}"] = g[c] - ix[c]
    g["贏大盤次數"] = sum((g[f"差{c}"] > 0).astype(int) for c in PAST)
    g["過去差距中位"] = g[[f"差{c}" for c in PAST]].median(axis=1)
    g["過去最差差距"] = g[[f"差{c}" for c in PAST]].min(axis=1)
    g["站上年線"] = m.groupby("族群")["站上年線"].mean().reindex(ORDER)
    g["這次收平以上"] = m.groupby("族群")[NOW].apply(lambda s: float((s >= 0).mean())).reindex(ORDER)
    g["前波"] = m.groupby("族群")["前波"].median().reindex(ORDER)
    g["類別"] = [KIND[k] for k in g.index]
    return g


def rebound_table(m: pd.DataFrame) -> pd.DataFrame:
    """大盤落底後 60 / 120 個交易日:族群成分股中位數、和大盤的差距、贏大盤幾次。"""
    ix = index_row()
    out = pd.DataFrame(index=ORDER)
    for k in (60, 120):
        cols = [f"{n}+{k}" for n in PAST]
        g = m.groupby("族群")[cols].median().reindex(ORDER)
        for c in cols:
            out[c] = g[c]
            out[f"差{c}"] = g[c] - ix[c]
        out[f"中位{k}"] = g.median(axis=1)
        out[f"大盤中位{k}"] = float(np.median([ix[c] for c in cols]))
        out[f"贏{k}"] = sum((out[f"差{c}"] > 0).astype(int) for c in cols)
        out[f"差中位{k}"] = out[[f"差{c}" for c in cols]].median(axis=1)
    return out


@lru_cache(maxsize=1)
def _rev() -> pd.DataFrame:
    r = pd.read_csv(D / "_rev_history.csv", dtype={"code": str})
    return r.pivot_table(index="ym", columns="code", values="rev", aggfunc="last").sort_index()


def king_table(m: pd.DataFrame, skip: tuple = ("金融",)) -> pd.DataFrame:
    """蠱王檢定。營收:2019 全年 vs 最近 12 個月;只算兩段都有 12 個月營收的公司(同一批公司才能比市占)。
    龍頭=最近 12 個月營收最大。股價:龍頭 vs 同產業其他公司的中位數。
    金融業的「營收」含保費與投資損益,不能當市占,所以預設不算。
    三項檢定:占比上升(超過 1 個百分點)、六次下跌至少 4 次贏同業、2019 年初至今股價贏同業中位數。"""
    rv = _rev()
    last12 = rv.iloc[-12:]
    y19 = rv.loc["2019-01":"2019-12"]
    ix = index_row()
    rows = []
    for g, codes in groups().items():
        if g in skip:
            continue
        cs = [c for c in codes if c in rv.columns and last12[c].notna().sum() == 12 and y19[c].notna().sum() == 12]
        if len(cs) < 3:
            continue
        now, old = last12[cs].sum(), y19[cs].sum()
        lead, lead19 = now.idxmax(), old.idxmax()
        top3 = list(now.sort_values(ascending=False).index[:3])
        mm = m[m["族群"] == g].set_index("代號")
        peers = mm.drop(index=lead, errors="ignore")
        r = dict(族群=g, 可比檔數=len(cs), 全部檔數=len(codes), 龍頭=lead, 龍頭名稱=name(lead), 龍頭2019=name(lead19),
                 市占2019=float(old[lead] / old.sum()), 市占現在=float(now[lead] / now.sum()),
                 前三市占2019=float(old.sort_values(ascending=False).iloc[:3].sum() / old.sum()), 前三市占現在=float(now[top3].sum() / now.sum()),
                 龍頭營收成長=float(now[lead] / old[lead] - 1), 同業營收成長中位=float((now[cs] / old[cs] - 1).drop(lead).median()),
                 整體營收成長=float(now.sum() / old.sum() - 1),
                 贏的家數比例=float(((now[cs] / old[cs]) > (now.sum() / old.sum())).mean()))
        if lead in mm.index:
            r["龍頭2019至今"] = float(mm.loc[lead, "2019至今"])
            r["同業2019至今"] = float(peers["2019至今"].median())
            r["大盤2019至今"] = ix["2019至今"]
            wins, n = 0, 0
            for e in PAST + [NOW]:
                a, b = mm.loc[lead, e], peers[e].median()
                r[f"龍頭{e}"], r[f"同業{e}"] = a, b
                if a == a and b == b:
                    n += 1
                    wins += int(a > b)
            r["下跌時贏同業"], r["下跌次數"] = wins, n
            r["占比上升"] = bool(r["市占現在"] > r["市占2019"] + 0.01)
            r["下跌抗跌"] = bool(wins >= 4)
            r["長期贏同業"] = bool(r["龍頭2019至今"] > r["同業2019至今"])
            r["中幾項"] = int(r["占比上升"]) + int(r["下跌抗跌"]) + int(r["長期贏同業"])
        rows.append(r)
    return pd.DataFrame(rows).set_index("族群")


def rev_now(m: pd.DataFrame):
    """內需現在夠不夠:最近 3 個月營收合計的年增率,成分股中位數與正成長比例。回傳 (表, 營收最新月份)。"""
    rv = _rev()
    y = rv.iloc[-3:].sum(min_count=3) / rv.iloc[-15:-12].sum(min_count=3) - 1
    rows = []
    for g, codes in groups().items():
        s = y.reindex(codes).dropna()
        rows.append(dict(族群=g, 檔數=len(s), 年增中位=float(s.median()) if len(s) else np.nan,
                         正成長比例=float((s > 0).mean()) if len(s) else np.nan))
    return pd.DataFrame(rows).set_index("族群"), str(rv.index[-1])


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.max_rows", 300)
    m = member_table()
    print({k: len(v) for k, v in groups().items()}, "| 有股價的", len(m))
    print("大盤", {k: round(v, 3) for k, v in index_row().items()})
    f = fall_table(m)
    print(f[["檔數"] + PAST + [NOW] + ["贏大盤次數", "過去差距中位", "過去最差差距", f"差{NOW}", "站上年線", "這次收平以上"]].round(3).to_string())
    r = rebound_table(m)
    print(r[[c for c in r.columns if not c.startswith("差") and "+" in c]].round(3).to_string())
    print(r[["中位60", "大盤中位60", "贏60", "差中位60", "中位120", "大盤中位120", "贏120", "差中位120"]].round(3).to_string())
    k = king_table(m)
    print(k.round(3).T.to_string())
    rn, ym = rev_now(m)
    print(ym)
    print(rn.round(3).to_string())

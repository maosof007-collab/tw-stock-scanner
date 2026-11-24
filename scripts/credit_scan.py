# -*- coding: utf-8 -*-
"""銀行信用鬆緊 vs 大盤(2026-11-23,使用者問「明年銀行停水、借貸更嚴格,對市場的影響」)。

資料:中央銀行統計資料庫公開接口(cpx.cbc.gov.tw,金融統計月報,1987/05 起,每月下旬公布上個月)
  EF27M01 其他貨幣機構(銀行+信合社+郵局等)放款;EF29M01 企業及個人存款;EF01M01 M1B、M2 年增率(日平均);
  EF07M01 股價指數(月底)、退票張數比率、本國銀行逾放比率。
快取 data/_cbc_credit.json(手動抓:python -X utf8 scripts/credit_scan.py fetch;海報只讀快取)。

三個寫死的狀態(每個月底只用「上個月以前」的數字,因為當月數字要到下個月下旬才公布):
  吃緊   = 放款年增率 − 存款年增率 ≥ GAP 點(借得比存得快,銀行的錢不夠用)——2026 年現在是這一種
  降溫   = 民間放款年增率比 6 個月前低 ≥ COOL 點(銀行真的少借了)
  萎縮   = 民間放款年增率 < 0(信用緊縮已經成真)
門檻是看過歷史之後定的,樣本裡真正的信用緊縮只有 1990、1998–2002、2008–09 三段,所以是「歷史上長這樣」,不是保證。
驗證:python -X utf8 scripts/credit_scan.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "_cbc_credit.json"
API = "https://cpx.cbc.gov.tw/API/DataAPI/Get"
# key: (檔名, Table1 名稱, 每個項目幾欄, 第幾欄)
COLS = {
    "loan": ("EF27M01", "放款-計", 2, 0),
    "loan_p": ("EF27M01", "放款-民間部門", 2, 0),
    "dep": ("EF29M01", "企業及個人之存款與貨幣市場共同基金-計", 2, 0),
    "loan_b": ("EF43M01", "放款-計", 2, 0),               # 只看本國銀行(不含郵局、信合社):對照用
    "dep_b": ("EF45M01", "企業及個人存款-計", 2, 0),
    "m1b_y": ("EF01M01", "貨幣總計數-M1B", 4, 1),
    "m2_y": ("EF01M01", "貨幣總計數-M2", 4, 1),
    "idx": ("EF07M01", "股票市場股價指數(民國５５年=１００)(１９６６=１００）", 1, 0),
    "bounce": ("EF07M01", "退票張數比率", 1, 0),
    "npl": ("EF07M01", "本國銀行逾放比率", 1, 0),
}
GAP, COOL = 2.0, 2.0


def fetch() -> dict:
    """只給排程/手動用。四個檔案各一次請求。"""
    import requests

    import ssl_trust
    ssl_trust.ensure()
    from twtime import now_tw
    raw, out = {}, {}
    for fn in sorted({v[0] for v in COLS.values()}):
        for k in range(3):
            try:
                raw[fn] = requests.get(API, params={"FileName": fn}, timeout=40).json()
                break
            except Exception as e:
                print("retry", fn, type(e).__name__, flush=True)
                time.sleep(6)
        time.sleep(1)
    for key, (fn, name, width, k) in COLS.items():
        d = raw[fn]["data"]
        names = [x["data"] for x in d["structure"]["Table1"]]
        i = 1 + names.index(name) * width + k
        out[key] = {r[0]: r[i] for r in d["dataSets"] if r[i] not in ("-", "", None)}
    try:                                                   # 上市融資餘額(金額,億元;FinMind 2001 年起)——股市自己的借錢管道
        j = requests.get("https://api.finmindtrade.com/api/v4/data",
                         params={"dataset": "TaiwanStockTotalMarginPurchaseShortSale", "start_date": "2001-01-01"}, timeout=60).json()
        out["margin"] = {r["date"]: round(r["TodayBalance"] / 1e8, 1) for r in j["data"]
                         if r["name"] == "MarginPurchaseMoney" and r["TodayBalance"] > 0}
    except Exception as e:
        print("融資餘額沒抓到", type(e).__name__, flush=True)
        out["margin"] = load().get("margin", {})
    out["made"] = f"{now_tw():%Y-%m-%d %H:%M}"
    out["updated"] = raw["EF27M01"]["meta"].get("last_updated", "")
    OUT.with_suffix(".tmp").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    OUT.with_suffix(".tmp").replace(OUT)
    return out


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def frame(raw: dict | None = None) -> pd.DataFrame:
    """月資料(Period 索引):原始指標 + 三個狀態。狀態欄已經往後挪一個月(= 當月底真的看得到的)。"""
    raw = raw or load()
    d = pd.DataFrame({k: pd.Series(raw[k], dtype=float) for k in COLS})
    d.index = pd.PeriodIndex([s.replace("M", "-") for s in d.index], freq="M")
    d = d.sort_index()
    d["loan_yoy"] = d.loan.pct_change(12) * 100
    d["loanp_yoy"] = d.loan_p.pct_change(12) * 100
    d["dep_yoy"] = d.dep.pct_change(12) * 100
    d["gap"] = d.loan_yoy - d.dep_yoy                      # 放款年增 − 存款年增
    d["ldr"] = d.loan / d.dep * 100                        # 放款 ÷ 存款
    d["gap_b"] = (d.loan_b.pct_change(12) - d.dep_b.pct_change(12)) * 100   # 本國銀行口徑的差距
    d["m_gap"] = d.m1b_y - d.m2_y
    d["cool"] = d.loanp_yoy - d.loanp_yoy.shift(6)
    # 股價:央行表的月底指數接本機日線月底(本機較新)
    px = d.idx.copy()
    try:
        a = pd.read_csv(ROOT / "data" / "_twii_long.csv", index_col=0, parse_dates=True).Close
        b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0]
        x = pd.concat([a, b[b.index > a.index[-1]]]).sort_index()
        m = x.groupby(x.index.to_period("M")).last()
        px = m.combine_first(px)
    except Exception:
        pass
    d = d.reindex(d.index.union(px.index))
    d["px"] = px
    for k, s in (("tight", d.gap >= GAP), ("cooling", d.cool <= -COOL), ("shrink", d.loanp_yoy < 0), ("m_dead", d.m_gap < 0),
                 ("tight_b", d.gap_b >= GAP)):
        d[k] = s.where(d.gap.notna()).shift(1)             # 上個月的數字,這個月底才用得到
        if pd.isna(d[k].iloc[-1]) and len(d) > 1:          # 這個月還沒到下旬、上個月的數字還沒公布:沿用最後一筆已公布的
            d.loc[d.index[-1], k] = d[k].iloc[-2]
    for h in (6, 12):
        d[f"f{h}"] = d.px.shift(-h) / d.px - 1
    d["dd12"] = pd.Series([d.px.iloc[i + 1:i + 13].min() / d.px.iloc[i] - 1 if i + 1 < len(d) else np.nan
                           for i in range(len(d))], index=d.index)
    return d


def _stat(d: pd.DataFrame, mask: pd.Series, lab: str) -> dict:
    g = d[mask.reindex(d.index).eq(True)]
    a6, a12, dd = g.f6.dropna(), g.f12.dropna(), g.dd12[g.f12.notna()]
    r = lambda x: round(float(x) * 100, 1)
    return {"狀態": lab, "月數": len(a6), "之後 6 個月中位數%": r(a6.median()) if len(a6) else None,
            "6 個月下跌的比例%": round((a6 < 0).mean() * 100) if len(a6) else None,
            "之後 12 個月中位數%": r(a12.median()) if len(a12) else None,
            "12 個月下跌的比例%": round((a12 < 0).mean() * 100) if len(a12) else None,
            "12 個月內最深跌幅中位數%": r(dd.median()) if len(dd) else None, "12 個月最差%": r(a12.min()) if len(a12) else None}


def backtest(d: pd.DataFrame, start: str = "1988-06") -> pd.DataFrame:
    d = d[d.index >= start]
    ok = d.tight.notna()
    T, C, S = (d[k].eq(True) for k in ("tight", "cooling", "shrink"))
    rows = [_stat(d, ok, "全部月份(基準)"),
            _stat(d, ok & ~T & ~C & ~S, "三個狀態都沒有"),
            _stat(d, T, f"吃緊:放款年增比存款年增多 ≥{GAP:.0f} 點"),
            _stat(d, T & ~C, "吃緊,但放款還沒降溫"),
            _stat(d, T & C, "吃緊,而且放款開始降溫"),
            _stat(d, C & ~S, f"降溫:民間放款年增比半年前低 ≥{COOL:.0f} 點(還沒轉負)"),
            _stat(d, S, "萎縮:民間放款年增 < 0"),
            _stat(d, d.m_dead.eq(True), "M1B 年增低於 M2(死亡交叉)"),
            _stat(d, d.tight_b.eq(True), f"(對照)只看本國銀行的吃緊:差距 ≥{GAP:.0f} 點")]
    return pd.DataFrame(rows)


def runs(d: pd.DataFrame, key: str, min_len: int = 4, merge: int = 3) -> pd.DataFrame:
    """某個狀態連續亮的每一段(中斷 ≤ merge 個月併成一段):起訖、期間大盤、起點之後 12 個月。"""
    s = d[key].eq(True)
    idx, segs, cur = list(d.index), [], None
    for i, v in enumerate(s.values):
        if v:
            if cur and i - cur[1] <= merge + 1:
                cur[1] = i
            else:
                cur and segs.append(cur)
                cur = [i, i]
    cur and segs.append(cur)
    rows = []
    for a, b in segs:
        if b - a + 1 < min_len:
            continue
        w = d.iloc[a:b + 1]
        px0 = d.px.iloc[a]
        lo = d.px.iloc[a:min(a + 25, len(d))]
        rows.append({"開始": str(idx[a]), "結束": str(idx[b]) if b < len(d) - 1 else "還在", "幾個月": b - a + 1,
                     "放款年增% 起→訖": f"{d.loanp_yoy.shift(1).iloc[a]:+.1f} → {d.loanp_yoy.shift(1).iloc[a:b + 1].dropna().iloc[-1]:+.1f}",
                     "差距(點)最大": round(float(d.gap.shift(1).iloc[a:b + 1].max()), 1),
                     "開始時大盤": round(float(px0)),
                     "之後 12 個月%": None if pd.isna(d.f12.iloc[a]) else round(float(d.f12.iloc[a]) * 100, 1),
                     "之後 24 個月內最低%": round(float(lo.min() / px0 - 1) * 100, 1),
                     "最低在": str(lo.idxmin())})
    return pd.DataFrame(rows)


def index_daily() -> pd.Series:
    a = pd.read_csv(ROOT / "data" / "_twii_long.csv", index_col=0, parse_dates=True).Close
    b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0]
    return pd.concat([a, b[b.index > a.index[-1]]]).sort_index()


def margin(raw: dict | None = None) -> pd.Series:
    m = pd.Series((raw or load()).get("margin", {}), dtype=float)
    m.index = pd.to_datetime(m.index)
    return m.sort_index()


def margin_cuts(m: pd.Series, cut: float = 0.25) -> pd.DataFrame:
    """融資餘額從前 250 個交易日高點減少 ≥ cut 的每一段:高點→低點減多少、花幾天、同期間大盤、低點之後大盤。"""
    x = index_daily()
    dd = m / m.rolling(250, min_periods=60).max() - 1
    hit, segs = dd[dd <= -cut].index, []
    for d in hit:
        if segs and (d - segs[-1][1]).days <= 120:
            segs[-1][1] = d
        else:
            segs.append([d, d])
    rows = []
    for a, b in segs:
        lo = m[a:b].idxmin()
        w = m[a - pd.Timedelta(days=400):lo]                 # 高點:第一次跌破門檻那天往前 400 天內
        pk = w.idxmax()
        xa, xb = x.asof(pk), x.asof(lo)
        f = lambda n: None if lo + pd.Timedelta(days=n) > x.index[-1] else round(float(x.asof(lo + pd.Timedelta(days=n)) / xb - 1) * 100, 1)
        rows.append({"融資高點": f"{pk:%Y/%m/%d}", "高點(億)": round(float(m[pk])), "融資低點": f"{lo:%Y/%m/%d}", "低點(億)": round(float(m[lo])),
                     "減少%": round(float(m[lo] / m[pk] - 1) * 100, 1), "花幾天": (lo - pk).days,
                     "同期間大盤%": round(float(xb / xa - 1) * 100, 1), "低點後 6 個月大盤%": f(182), "低點後 12 個月大盤%": f(365),
                     "還在進行": bool(lo == m.index[-1])})
    return pd.DataFrame(rows)


def now(d: pd.DataFrame) -> dict:
    x = d[d.gap.notna()].iloc[-1]
    return {"月份": str(x.name), "放款年增%": round(x.loan_yoy, 2), "民間放款年增%": round(x.loanp_yoy, 2), "存款年增%": round(x.dep_yoy, 2),
            "差距(點)": round(x.gap, 2), "本國銀行口徑差距(點)": round(x.gap_b, 2), "放款÷存款%": round(x.ldr, 1), "M1B 年增%": x.m1b_y, "M2 年增%": x.m2_y,
            "民間放款年增比半年前(點)": round(x.cool, 2), "退票張數比率%": x.bounce,
            "逾放比%(最近一筆)": f"{d.npl.dropna().iloc[-1]}({d.npl.dropna().index[-1]})"}


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        R = fetch()
        print("已抓", R["made"], "央行更新日", R["updated"])
    D = frame()
    print("現在", json.dumps(now(D), ensure_ascii=False))
    print(D.loc["2025-09":, ["loan_yoy", "loanp_yoy", "dep_yoy", "gap", "ldr", "m1b_y", "m2_y", "cool", "px"]].round(2).to_string())
    print(backtest(D).to_string(index=False))
    for k, lab in (("tight", "吃緊"), ("cooling", "降溫"), ("shrink", "萎縮")):
        print("\n" + lab)
        print(runs(D, k).to_string(index=False))
    print("\n融資餘額每一次大減")
    print(margin_cuts(margin()).to_string(index=False))

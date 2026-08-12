"""
backtest_news_daytrade.py — 盤前新聞提及股 → 當日當沖(開盤買收盤賣)回測
=================================================================
問題:晨報/盤前新聞點名的股票,當天當沖做多勝率高嗎?
資訊集鐵律:只用「前一交易日 14:00 ~ 當日 08:30」發布的新聞(盤前可知)。
成本:買賣手續費 0.1425%×2 + 當沖證交稅 0.15% ≈ 0.435%/趟。
輸出:整體勝率/期望值、依開盤跳空幅度分組(追高 vs 平開)。
"""
from __future__ import annotations
import sys, glob, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

D = Path(__file__).parent / "data"
COST = 0.00435                       # 當沖全額成本(無手續費折讓)


def load_news() -> pd.DataFrame:
    rows = []
    for f in glob.glob(str(D / "news" / "news_*.csv")):
        try:
            df = pd.read_csv(f, encoding="utf-8-sig", usecols=["title", "published"])
            rows.append(df)
        except Exception:
            continue
    n = pd.concat(rows, ignore_index=True).drop_duplicates(subset=["title"])
    n["published"] = pd.to_datetime(n["published"], errors="coerce")
    return n.dropna(subset=["published"])


def stock_names() -> dict:
    sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    out = {}
    for _, r in sl.iterrows():
        nm = str(r["name"]).strip()
        if len(nm) >= 2 and nm.lower() != "nan":
            out[nm] = str(r["code"]).strip()
    return out


def mentions(news: pd.DataFrame, names: dict) -> pd.DataFrame:
    """每則新聞 → 提及的個股(股名出現在標題)。回傳 (published, code, name, title)。"""
    pat = re.compile("|".join(re.escape(n) for n in
                              sorted(names, key=len, reverse=True)))
    rows = []
    for _, r in news.iterrows():
        t = str(r["title"])
        for nm in set(pat.findall(t)):
            rows.append({"published": r["published"], "code": names[nm],
                         "name": nm, "title": t})
    return pd.DataFrame(rows)


def price_map() -> dict:
    """code → DataFrame(date, Open, Close)"""
    out = {}
    for f in glob.glob(str(D / "*.TW.csv")) + glob.glob(str(D / "*.TWO.csv")):
        code = Path(f).stem.split(".")[0]
        try:
            px = pd.read_csv(f, index_col=0, parse_dates=True,
                             usecols=[0, 1, 4])
            px.columns = ["Open", "Close"]
            px = px.apply(pd.to_numeric, errors="coerce").dropna()
            if len(px) > 5:
                out[code] = px
        except Exception:
            continue
    return out


def run() -> pd.DataFrame:
    news = load_news()
    names = stock_names()
    men = mentions(news, names)
    print(f"新聞 {len(news)} 則(去重),提及個股事件 {len(men)} 筆")
    pxm = price_map()

    trades = []
    for _, r in men.iterrows():
        pub = r["published"]
        # 盤前資訊集:發布於 D-1 14:00 之後、D 08:30 之前 → 交易日 D
        if pub.hour >= 14:
            day = (pub + pd.Timedelta(days=1)).normalize()
        elif (pub.hour, pub.minute) <= (8, 30):
            day = pub.normalize()
        else:
            continue                     # 盤中/收盤前新聞,盤前不可知,不用
        px = pxm.get(r["code"])
        if px is None:
            continue
        after = px[px.index >= day]
        if after.empty or (after.index[0] - day).days > 3:
            continue                     # 週末順延最多3天,再遠=資料缺
        d0 = after.iloc[0]
        prev = px[px.index < after.index[0]]
        if prev.empty or not d0["Open"]:
            continue
        gap = (d0["Open"] / prev["Close"].iloc[-1] - 1) * 100
        ret = (d0["Close"] / d0["Open"] - 1) * 100 - COST * 100
        trades.append({"date": after.index[0], "code": r["code"], "name": r["name"],
                       "gap%": round(gap, 2), "ret%": round(ret, 2)})
    tr = pd.DataFrame(trades).drop_duplicates(subset=["date", "code"])
    if tr.empty:
        print("無可回測樣本")
        return tr

    def stats(df, label):
        wr = (df["ret%"] > 0).mean() * 100
        print(f"{label:24s} 筆數{len(df):4d}  勝率 {wr:5.1f}%  "
              f"平均 {df['ret%'].mean():+.2f}%  中位 {df['ret%'].median():+.2f}%")

    print(f"\n=== 盤前新聞提及 → 當日開盤買/收盤賣(含當沖成本 {COST*100:.2f}%) ===")
    print(f"樣本期間:{tr['date'].min():%Y-%m-%d} ~ {tr['date'].max():%Y-%m-%d}")
    stats(tr, "全部")
    stats(tr[tr["gap%"] <= 1], "平開/小高開(gap≤1%)")
    stats(tr[(tr["gap%"] > 1) & (tr["gap%"] <= 3)], "追高(1%<gap≤3%)")
    stats(tr[tr["gap%"] > 3], "大跳空(gap>3%)")
    tr.to_csv("backtest_results/news_daytrade.csv", index=False, encoding="utf-8-sig")
    return tr


if __name__ == "__main__":
    Path("backtest_results").mkdir(exist_ok=True)
    run()

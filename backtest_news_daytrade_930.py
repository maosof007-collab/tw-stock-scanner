"""
backtest_news_daytrade_930.py — 盤前新聞提及股:開盤買→9:30/10:00/收盤 出場對照
=================================================================
資料:yfinance 30分K(僅回溯~60天,故樣本=近兩個月)。
問題:早盤動能(9:00→9:30)是否比抱到收盤有優勢?
成本同當沖 0.435%/趟。
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd
from backtest_news_daytrade import load_news, stock_names, mentions, COST

D = Path(__file__).parent / "data"


def _suffix(code: str) -> str:
    if (D / f"{code}.TW.csv").exists():
        return f"{code}.TW"
    if (D / f"{code}.TWO.csv").exists():
        return f"{code}.TWO"
    return ""


def fetch_intraday(tickers: list[str]) -> dict:
    """{ticker: DataFrame(30m bars)};分批下載。"""
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 25):
        chunk = tickers[i:i + 25]
        try:
            df = yf.download(chunk, period="60d", interval="30m",
                             group_by="ticker", progress=False, threads=True)
        except Exception:
            continue
        for t in chunk:
            try:
                sub = df[t].dropna(subset=["Open", "Close"]) if len(chunk) > 1 else df.dropna(subset=["Open", "Close"])
                if len(sub):
                    out[t] = sub
            except Exception:
                continue
    return out


def run():
    news = load_news()
    men = mentions(news, stock_names())
    # 指派交易日(同盤前資訊集規則)
    rows = []
    for _, r in men.iterrows():
        pub = r["published"]
        if pub.hour >= 14:
            day = (pub + pd.Timedelta(days=1)).normalize()
        elif (pub.hour, pub.minute) <= (8, 30):
            day = pub.normalize()
        else:
            continue
        rows.append({"day": day, "code": r["code"], "name": r["name"]})
    ev = pd.DataFrame(rows).drop_duplicates(subset=["day", "code"])
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=58)
    ev = ev[ev["day"] >= cutoff]
    ev["tkr"] = ev["code"].map(_suffix)
    ev = ev[ev["tkr"] != ""]
    print(f"近兩個月事件 {len(ev)} 筆,{ev['tkr'].nunique()} 檔 → 下載30分K…")

    bars = fetch_intraday(sorted(ev["tkr"].unique()))
    print(f"取得 {len(bars)} 檔 intraday")

    trades = []
    for _, r in ev.iterrows():
        b = bars.get(r["tkr"])
        if b is None:
            continue
        idx = b.index.tz_localize(None) if b.index.tz is not None else b.index
        dsel = b[(idx >= r["day"]) & (idx < r["day"] + pd.Timedelta(days=1))]
        if len(dsel) < 3:
            continue
        o = float(dsel["Open"].iloc[0])          # 開盤價
        if not o:
            continue
        c930 = float(dsel["Close"].iloc[0])      # 09:00-09:30 bar 收盤
        c1000 = float(dsel["Close"].iloc[1])
        cend = float(dsel["Close"].iloc[-1])
        trades.append({"date": r["day"], "code": r["code"], "name": r["name"],
                       "930%": (c930 / o - 1) * 100 - COST * 100,
                       "1000%": (c1000 / o - 1) * 100 - COST * 100,
                       "close%": (cend / o - 1) * 100 - COST * 100})
    tr = pd.DataFrame(trades)
    if tr.empty:
        print("無樣本")
        return

    print(f"\n=== 開盤買進 → 各時點出場(近兩個月,{len(tr)} 筆,含成本0.435%) ===")
    for col, label in (("930%", "9:30 出場"), ("1000%", "10:00 出場"), ("close%", "收盤出場")):
        s = tr[col]
        print(f"{label:10s} 勝率 {(s>0).mean()*100:5.1f}%  平均 {s.mean():+.2f}%  "
              f"中位 {s.median():+.2f}%  最差 {s.min():+.2f}%")
    tr.to_csv("backtest_results/news_daytrade_930.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    Path("backtest_results").mkdir(exist_ok=True)
    run()

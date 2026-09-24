"""
op_paper.py — 選擇權模擬倉(paper trading,每日用期交所真實結算價洗損益)
=================================================================
資料:期交所 OpenAPI DailyMarketReportOpt(TXO 全履約價結算價,免費)
     快取 data/txo/txo_YYYYMMDD.csv;倉單 data/option_paper.csv。
規則:每腿一列;買方(BC/BP)損益=(現值-進場)×50×口數,賣方(SC/SP)相反。
紀律:開倉必填「矩陣象限+論點」——說不出觀點就不准開(和體檢卡同源)。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
TXO_DIR = ROOT / "data" / "txo"
TXO_DIR.mkdir(parents=True, exist_ok=True)
PAPER = ROOT / "data" / "option_paper.csv"
PT = 50            # TXO 每點 50 元

COLS = ["開倉日", "組合", "腿", "月份", "履約價", "口數", "進場點",
        "停損點", "停利點", "象限", "論點", "狀態", "平倉日", "平倉點",
        "現值點", "損益元", "警示"]


def default_sl_tp(leg: str, entry: float) -> tuple[float, float]:
    """家規預設:買方=虧50%停損/漲1倍停利;賣方=權利金翻倍停損(虧一倍)/剩20%停利(收租八成落袋)。"""
    if leg.upper() in ("BC", "BP"):
        return round(entry * 0.5, 1), round(entry * 2.0, 1)
    return round(entry * 2.0, 1), round(entry * 0.2, 1)


def fetch_txo() -> pd.DataFrame:
    """抓當日 TXO 全表(一般時段,有結算價),存 data/txo/txo_YYYYMMDD.csv。"""
    req = urllib.request.Request("https://openapi.taifex.com.tw/v1/DailyMarketReportOpt",
                                 headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    df = pd.DataFrame(d)
    df = df[(df["Contract"] == "TXO") & (df["TradingSession"] == "一般")].copy()
    df["settle"] = pd.to_numeric(df["SettlementPrice"], errors="coerce")
    df = df.dropna(subset=["settle"])
    df = df.rename(columns={"ContractMonth(Week)": "month", "StrikePrice": "strike",
                            "CallPut": "cp"})
    out = df[["Date", "month", "strike", "cp", "settle", "Volume", "OpenInterest"]]
    if len(out):
        ymd = out["Date"].iloc[0]
        out.to_csv(TXO_DIR / f"txo_{ymd}.csv", index=False, encoding="utf-8-sig")
    return out


def latest_txo() -> pd.DataFrame:
    fs = sorted(TXO_DIR.glob("txo_*.csv"))
    if not fs:
        return fetch_txo()
    return pd.read_csv(fs[-1], dtype={"month": str, "strike": str})


def settle_of(month: str, strike, cp: str) -> float | None:
    """cp: 'C' or 'P'。"""
    q = latest_txo()
    cpz = "買權" if cp.upper() == "C" else "賣權"
    hit = q[(q["month"].astype(str) == str(month))
            & (pd.to_numeric(q["strike"]) == float(strike)) & (q["cp"] == cpz)]
    return float(hit["settle"].iloc[0]) if len(hit) else None


def load() -> pd.DataFrame:
    if PAPER.exists():
        df = pd.read_csv(PAPER, dtype={"月份": str})
        for c in COLS:                     # 舊檔補欄(停損/停利/警示)
            if c not in df.columns:
                df[c] = None
        return df[COLS]
    return pd.DataFrame(columns=COLS)


def save(df: pd.DataFrame):
    df.to_csv(PAPER, index=False, encoding="utf-8-sig")


def add_leg(組合: str, 腿: str, 月份: str, 履約價: float, 口數: int,
            進場點: float, 象限: str, 論點: str,
            停損點: float | None = None, 停利點: float | None = None):
    df = load()
    _sl, _tp = default_sl_tp(腿, float(進場點))
    row = {"開倉日": f"{now_tw():%Y-%m-%d}", "組合": 組合, "腿": 腿.upper(),
           "月份": str(月份), "履約價": 履約價, "口數": int(口數),
           "進場點": float(進場點),
           "停損點": float(停損點) if 停損點 else _sl,
           "停利點": float(停利點) if 停利點 else _tp,
           "象限": 象限, "論點": 論點,
           "狀態": "open", "平倉日": "", "平倉點": None, "現值點": None,
           "損益元": None, "警示": ""}
    row_df = pd.DataFrame([row])
    df = row_df if df.empty else pd.concat([df, row_df], ignore_index=True)
    save(df)


def mark() -> pd.DataFrame:
    """用最新結算價洗 open 腿的現值與損益;closed 腿用平倉點。"""
    df = load()
    if df.empty:
        return df
    for i, r in df.iterrows():
        cp = "C" if r["腿"] in ("BC", "SC") else "P"
        if r["狀態"] == "open":
            now = settle_of(r["月份"], r["履約價"], cp)
            if now is None:
                continue
            df.loc[i, "現值點"] = now
        else:
            now = pd.to_numeric(pd.Series([r["平倉點"]]), errors="coerce").iloc[0]
            if pd.isna(now):
                continue
        sign = 1 if r["腿"] in ("BC", "BP") else -1     # 買方賺漲價,賣方賺跌價
        df.loc[i, "損益元"] = round((now - float(r["進場點"])) * sign * PT * int(r["口數"]))
        # 停損/停利觸發檢查(open 腿;沒設就補預設)
        if r["狀態"] == "open":
            sl = pd.to_numeric(pd.Series([r.get("停損點")]), errors="coerce").iloc[0]
            tp = pd.to_numeric(pd.Series([r.get("停利點")]), errors="coerce").iloc[0]
            if pd.isna(sl) or pd.isna(tp):
                sl, tp = default_sl_tp(r["腿"], float(r["進場點"]))
                df.loc[i, ["停損點", "停利點"]] = [sl, tp]
            buyer = r["腿"] in ("BC", "BP")
            hit_sl = now <= sl if buyer else now >= sl
            hit_tp = now >= tp if buyer else now <= tp
            df.loc[i, "警示"] = ("🛑 停損觸發" if hit_sl else
                                 ("🎯 停利觸發" if hit_tp else ""))
    save(df)
    return df


def alerts() -> pd.DataFrame:
    """觸發中的 open 腿(run_daily / 駕駛艙用)。"""
    df = load()
    if df.empty or "警示" not in df.columns:
        return pd.DataFrame()
    return df[(df["狀態"] == "open") & df["警示"].astype(str).str.contains("觸發", na=False)]


def seed_if_empty() -> bool:
    """最初模擬倉(教學對照組):A=買方保險 BP、B=賣方戴帽熊市信用價差 SC+BC。
    用最新真實結算價當進場點。已有倉單就不動。"""
    if PAPER.exists() and len(load()):
        return False
    legs = [
        ("A-連假保險(買方)", "BP", "202610", 47000,
         "看跌/防跳空+IV事件前", "中秋連假+外資期指深空,買價外Put當保險;體驗Theta天天扣"),
        ("B-戴帽收租(賣方)", "SC", "202610", 48500,
         "中性偏空+IV貴", "熊市信用價差賣腿:賭連假後不過48500;收租但戴帽"),
        ("B-戴帽收租(賣方)", "BC", "202610", 49000,
         "中性偏空+IV貴", "價差買腿=帽子:最多虧(500點差-淨收租)×50,風險封頂"),
    ]
    ok = 0
    for 組合, 腿, m, k, 象限, 論點 in legs:
        cp = "C" if 腿 in ("BC", "SC") else "P"
        px = settle_of(m, k, cp)
        if px is None:
            continue
        add_leg(組合, 腿, m, k, 1, px, 象限, 論點)
        ok += 1
    if ok:
        mark()
    return ok > 0


if __name__ == "__main__":
    print("fetch:", len(fetch_txo()), "rows")
    print("seeded:", seed_if_empty())
    print(mark().to_string(index=False))

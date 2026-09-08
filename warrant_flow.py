"""
warrant_flow.py — 權證資金流管線(權證籌碼 → 現股訊號)
=================================================================
假說(權證小哥方法論的數據化):主力用權證做槓桿佈局,
「某標的的認購權證成交金額異常放大」可能領先現股。
管線:TWSE 權證基本資料(標的對映) + MI_INDEX 0999/0999P 日行情
→ 聚合成「每標的每日 call/put 成交金額」→ 爆量訊號 → 事件研究。
快取:data/warrants/wflow_YYYYMMDD.csv(聚合後,每日一檔,小而永存)。
限制:v1 僅上市權證(TWSE);上櫃權證(TPEX)待接。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent
WDIR = ROOT / "data" / "warrants"
_HDR = {"User-Agent": "Mozilla/5.0"}


# ────────────────────────────────────────
# 權證 → 標的 對映
# ────────────────────────────────────────
def warrant_map(force: bool = False) -> pd.DataFrame:
    """[wcode, kind(call/put), uname, ucode];基本資料快取 20h。"""
    WDIR.mkdir(parents=True, exist_ok=True)
    cache = WDIR / "_warrant_map.csv"
    if cache.exists() and not force and (time.time() - cache.stat().st_mtime) < 20 * 3600:
        return pd.read_csv(cache, dtype=str)
    r = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap37_L",
                     timeout=60, headers=_HDR)
    rows = [{"wcode": x["權證代號"], "kind": "call" if x["權證類型"] == "認購" else "put",
             "uname": x["標的證券/指數"]} for x in r.json()]
    df = pd.DataFrame(rows)
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["name"].str.strip(), sl["code"]))
    df["ucode"] = df["uname"].str.strip().map(nm)
    df = df.dropna(subset=["ucode"])
    df.to_csv(cache, index=False, encoding="utf-8-sig")
    return df


# ────────────────────────────────────────
# 單日抓取 + 聚合
# ────────────────────────────────────────
def fetch_warrant_day(ymd: str, sleep: float = 2.0) -> pd.DataFrame | None:
    """ymd='20260904'。回傳每標的聚合 [date, ucode, call_val, put_val, call_vol](金額百萬/量張);
    非交易日回 None。已快取直接讀。"""
    WDIR.mkdir(parents=True, exist_ok=True)
    cache = WDIR / f"wflow_{ymd}.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"ucode": str})
    frames = []
    for typ, kind in [("0999", "call"), ("0999P", "put")]:
        r = requests.get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
                         f"?date={ymd}&type={typ}&response=json", timeout=60, headers=_HDR)
        time.sleep(sleep)
        j = r.json()
        tbl = next((t for t in j.get("tables", []) if t.get("data")), None)
        if tbl is None:
            return None                                    # 非交易日
        f = tbl["fields"]
        i_code, i_name = f.index("證券代號"), f.index("證券名稱")
        i_vol, i_val = f.index("成交股數"), f.index("成交金額")
        rows = []
        for d in tbl["data"]:
            try:
                rows.append({"wcode": str(d[i_code]).strip(),
                             "wname": str(d[i_name]).strip(),
                             "vol": float(str(d[i_vol]).replace(",", "")),
                             "val": float(str(d[i_val]).replace(",", ""))})
            except Exception:
                continue
        df = pd.DataFrame(rows)
        df["kind"] = kind
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    wm = warrant_map()
    m = raw.merge(wm[["wcode", "ucode", "kind"]], on=["wcode", "kind"], how="left")
    # 已到期權證不在現行基本資料 → 用「權證簡稱前綴=標的名」補歸戶(長名優先)
    miss = m["ucode"].isna()
    if miss.any():
        sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        names = sorted(zip(sl["name"].str.strip(), sl["code"]),
                       key=lambda x: -len(x[0]))
        def _pfx(w):
            for nm_, cd_ in names:
                if len(nm_) >= 2 and w.startswith(nm_):
                    return cd_
            return None
        m.loc[miss, "ucode"] = m.loc[miss, "wname"].map(_pfx)
    m = m.dropna(subset=["ucode"])
    g = (m.groupby(["ucode", "kind"])
         .agg(val=("val", "sum"), vol=("vol", "sum")).reset_index())
    p = g.pivot(index="ucode", columns="kind", values="val").fillna(0)
    out = pd.DataFrame({
        "date": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}",
        "ucode": p.index,
        "call_val": (p.get("call", 0) / 1e6).round(2),
        "put_val": (p.get("put", 0) / 1e6).round(2),
    }).reset_index(drop=True)
    vcall = g[g["kind"] == "call"].set_index("ucode")["vol"]
    out["call_vol"] = (out["ucode"].map(vcall).fillna(0) / 1000).round(0)
    out = out[(out["call_val"] > 0) | (out["put_val"] > 0)]
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    return out


def backfill(days: int = 120, skip_last: int = 0) -> int:
    """從 benchmark 交易日清單回補近 N 個交易日(已有快取自動跳過)。回傳新抓天數。"""
    b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", usecols=["Date"])
    seq = b["Date"].dropna().astype(str)
    if skip_last:
        seq = seq.iloc[:-skip_last]
    dates = [d.replace("-", "") for d in seq.tail(days)]
    n = 0
    for ymd in dates:
        if (WDIR / f"wflow_{ymd}.csv").exists():
            continue
        try:
            r = fetch_warrant_day(ymd)
            if r is not None:
                n += 1
                print(f"[wflow] {ymd} ok ({len(r)} underlyings)")
        except Exception as e:
            print(f"[wflow] {ymd} fail {str(e)[:60]}")
            time.sleep(5)
    return n


# ────────────────────────────────────────
# 面板 / 訊號 / 事件研究
# ────────────────────────────────────────
def build_panel() -> pd.DataFrame:
    fs = sorted(WDIR.glob("wflow_2*.csv"))
    if not fs:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f, dtype={"ucode": str}) for f in fs],
                     ignore_index=True)


def burst_events(panel: pd.DataFrame, mult: float = 3.0,
                 min_val: float = 30.0, win: int = 20) -> pd.DataFrame:
    """認購權證金額爆量事件:call_val ≥ mult×前win日中位 且 ≥ min_val(百萬)。"""
    ev = []
    for c, g in panel.groupby("ucode"):
        g = g.sort_values("date").reset_index(drop=True)
        base = g["call_val"].shift(1).rolling(win, min_periods=10).median()
        hit = (g["call_val"] >= mult * base) & (g["call_val"] >= min_val)
        for i in g.index[hit.fillna(False)]:
            ev.append({"ucode": c, "date": g.loc[i, "date"],
                       "call_val": g.loc[i, "call_val"],
                       "倍數": round(g.loc[i, "call_val"] / base[i], 1) if base[i] else None,
                       "put_val": g.loc[i, "put_val"]})
    return pd.DataFrame(ev)


def event_study(ev: pd.DataFrame) -> pd.DataFrame:
    """每個爆量事件接現股 fwd 1/5/10 日報酬。"""
    rows = []
    for c, g in ev.groupby("ucode"):
        px = None
        for suf in (".TW", ".TWO"):
            p = ROOT / "data" / f"{c}{suf}.csv"
            if p.exists():
                px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
                px["Close"] = pd.to_numeric(px["Close"], errors="coerce")
                px = px.dropna().sort_values("Date").reset_index(drop=True)
                break
        if px is None or len(px) < 30:
            continue
        pos = {d: i for i, d in enumerate(px["Date"])}
        for _, r in g.iterrows():
            i = pos.get(r["date"])
            if i is None or i + 10 >= len(px):
                continue
            c0 = px["Close"].iloc[i]
            rows.append({"ucode": c, "date": r["date"], "call_val": r["call_val"],
                         "倍數": r["倍數"],
                         "f1": round((px["Close"].iloc[i + 1] / c0 - 1) * 100, 2),
                         "f5": round((px["Close"].iloc[i + 5] / c0 - 1) * 100, 2),
                         "f10": round((px["Close"].iloc[i + 10] / c0 - 1) * 100, 2)})
    return pd.DataFrame(rows)


def sustained_flow(code: str) -> dict:
    """佈局持續度指紋:月額序列/連續高於中位天數/近20日vs中位倍數/CP比/價格對照。"""
    panel = build_panel()
    g = panel[panel["ucode"] == code].sort_values("date").reset_index(drop=True)
    if len(g) < 40:
        return {}
    g["ym"] = g["date"].str[:7]
    mo = (g.groupby("ym").agg(call月額=("call_val", "sum"),
                              天數=("call_val", "count")).round(0))
    mo["日均call"] = (mo["call月額"] / mo["天數"]).round(1)
    med = float(g["call_val"].median())
    last20 = g.tail(20)
    streak = 0
    for v in g["call_val"][::-1]:
        if v > med:
            streak += 1
        else:
            break
    # 價格對照(佈局=錢持續進、價還沒噴)
    px_chg = None
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            d = pd.read_csv(p, usecols=["Date", "Close"]).dropna().sort_values("Date")
            cl = pd.to_numeric(d["Close"], errors="coerce").dropna()
            if len(cl) > 40:
                px_chg = round(float(cl.iloc[-1] / cl.iloc[-40] - 1) * 100, 1)
            break
    mult20 = round(float(last20["call_val"].mean()) / med, 2) if med else None
    cp = round(float(last20["call_val"].sum()) / max(float(last20["put_val"].sum()), 0.1), 1)
    if streak >= 15 and (mult20 or 0) >= 1.5:
        verdict = "🔵 佈局進行中(錢持續高檔)"
    elif (mult20 or 0) >= 1.5:
        verdict = "🟡 近期加溫(尚未形成持續)"
    elif (mult20 or 0) <= 0.8:
        verdict = "⚫ 權證錢退潮"
    else:
        verdict = "⚪ 常態水位"
    if px_chg is not None and verdict.startswith("🔵") and px_chg < 5:
        verdict += "|⭐ 錢進價未動=典型吸籌形"
    return {"monthly": mo, "日中位": round(med, 1), "近20日倍數": mult20,
            "連續高於中位天數": streak, "近20日CP比": cp,
            "近40日價格%": px_chg, "verdict": verdict}


def today_board(top: int = 20) -> pd.DataFrame:
    """最新一日的權證資金流榜(call爆量倍數排序,含現股名)。"""
    panel = build_panel()
    if panel.empty:
        return panel
    last = panel["date"].max()
    ev = burst_events(panel, mult=2.0, min_val=20.0)
    ev = ev[ev["date"] == last].sort_values("call_val", ascending=False).head(top)
    try:
        sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        ev = ev.merge(sl[["code", "name"]], left_on="ucode", right_on="code", how="left")
    except Exception:
        pass
    return ev


if __name__ == "__main__":
    import sys
    n = int(sys.argv[sys.argv.index("--backfill") + 1]) if "--backfill" in sys.argv else 120
    print("backfilled:", backfill(n))

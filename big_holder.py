"""
big_holder.py — 大戶籌碼週報引擎(集保股權分散表,仿旺來週報方法論)
=================================================================
資料:data/tdcc/{code}_tdcc.csv(週五快照,level 12-15 = 400張以上)
產出:
  ① 週變化清單:大戶買組(Δ≥+1pp)/大戶賣組(散戶接,Δ≤-1pp)
  ② 回頭車(上週賣→本週買)/下車(上週買→本週賣)+ 本週漲跌 + 融資週增減
  ③ 五週成績單:各週「大戶買組 vs 大戶賣組」的下一週報酬對照(誰在防守)
panel 快取:data/_bigholder_panel.csv(新週出現自動重建;run_daily 掛 rebuild)
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

ROOT = Path(__file__).parent
TDCC = ROOT / "data" / "tdcc"
PANEL = ROOT / "data" / "_bigholder_panel.csv"
BIG_LEVELS = {12, 13, 14, 15}          # 400,001股(400張)以上四級


def build_panel(force: bool = False) -> pd.DataFrame:
    """全市場「400張以上持股比例」週 panel(index=date, columns=code)。"""
    files = glob.glob(str(TDCC / "*_tdcc.csv"))
    if PANEL.exists() and not force:
        newest_src = max((Path(f).stat().st_mtime for f in files), default=0)
        if PANEL.stat().st_mtime >= newest_src:
            df = pd.read_csv(PANEL, index_col=0, parse_dates=True)
            df.columns = [str(c) for c in df.columns]
            return df
    cols = {}
    for f in files:
        code = Path(f).stem.replace("_tdcc", "")
        try:
            d = pd.read_csv(f, dtype={"stock_id": str})
            d = d[d["level"].isin(BIG_LEVELS)]
            s = d.groupby("date")["pct"].sum()
            if len(s) >= 2:
                cols[code] = s
        except Exception:
            continue
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.to_csv(PANEL)
    print(f"[big_holder] panel {df.shape[1]} 檔 × {len(df)} 週")
    return df


def _prices() -> dict:
    out = {}
    for f in glob.glob(str(ROOT / "data" / "*.TW.csv")) + \
             glob.glob(str(ROOT / "data" / "*.TWO.csv")):
        code = Path(f).stem.split(".")[0]
        try:
            s = pd.read_csv(f, index_col=0, parse_dates=True, usecols=[0, 4, 5])
            s.columns = ["Close", "Volume"]
            out[code] = s.apply(pd.to_numeric, errors="coerce").dropna()
        except Exception:
            continue
    return out


def _week_ret(px: pd.DataFrame, d0, d1) -> float | None:
    """d0(五)→d1(五)收盤報酬%(asof 對齊)。"""
    try:
        c0, c1 = float(px["Close"].asof(d0)), float(px["Close"].asof(d1))
        return (c1 / c0 - 1) * 100 if c0 else None
    except Exception:
        return None


def _margin_wchg(code: str, d0, d1) -> float | None:
    p = ROOT / "data" / "margin" / f"{code}_margin.csv"
    if not p.exists():
        return None
    try:
        m = pd.read_csv(p, usecols=["date", "margin_balance"])
        m["date"] = pd.to_datetime(m["date"])
        m = m.set_index("date")["margin_balance"].astype(float)
        b0, b1 = m.asof(d0), m.asof(d1)
        return (b1 / b0 - 1) * 100 if b0 else None
    except Exception:
        return None


def weekly_lists(th: float = 1.0, min_vol_lots: int = 500) -> dict:
    """最新週的 大戶買組/賣組 + 回頭車/下車 + 五週成績單。"""
    panel = build_panel()
    delta = panel.diff()
    dates = list(panel.index)
    if len(dates) < 3:
        return {"error": "TDCC 週數不足(需≥3週)"}
    w, w1 = dates[-1], dates[-2]
    px = _prices()
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))

    liquid = {c for c, p in px.items()
              if len(p) > 20 and p["Volume"].tail(20).mean() >= min_vol_lots * 1000}

    def mk(codes, dw, dw1):
        rows = []
        for c in codes:
            if c not in px:
                continue
            rows.append({"代碼": c, "名稱": nm.get(c, ""),
                         "上週Δpp": round(dw1.get(c, float("nan")), 2),
                         "本週Δpp": round(dw.get(c, float("nan")), 2),
                         "本週漲跌%": round(_week_ret(px[c], w1, w) or 0, 1),
                         "融資週增減%": (round(_margin_wchg(c, w1, w), 1)
                                     if _margin_wchg(c, w1, w) is not None else None)})
        return pd.DataFrame(rows)

    dw = delta.loc[w].dropna()
    dw1 = delta.loc[w1].dropna()
    dw = dw[dw.index.isin(liquid)]
    dw = dw[dw.abs() <= 15]              # |Δ|>15pp=股本事件/資料異常,非籌碼行為
    dw1 = dw1[dw1.abs() <= 15]
    buy = dw[dw >= th].sort_values(ascending=False)
    sell = dw[dw <= -th].sort_values()
    both = dw.index.intersection(dw1.index)
    ret_car = [c for c in both if dw1[c] <= -th * 0.5 and dw[c] >= th * 0.5]
    exit_car = [c for c in both if dw1[c] >= th * 0.5 and dw[c] <= -th * 0.5]
    ret_car.sort(key=lambda c: -dw[c])
    exit_car.sort(key=lambda c: dw[c])

    # 五週成績單:各週 買組/賣組 的「下一週」報酬
    cohort = []
    for i in range(max(1, len(dates) - 7), len(dates) - 1):
        if (dates[i + 1] - dates[i]).days > 10:
            continue                     # 斷週不比(次週報酬會橫跨多週失真)
        d_sig, d_next0, d_next1 = dates[i], dates[i], dates[i + 1]
        dsig = delta.loc[d_sig].dropna()
        dsig = dsig[dsig.index.isin(liquid)]
        dsig = dsig[dsig.abs() <= 15]
        g_buy = dsig[dsig >= th].index
        g_sell = dsig[dsig <= -th].index
        r_buy = pd.Series([_week_ret(px[c], d_next0, d_next1)
                           for c in g_buy if c in px]).dropna()
        r_sell = pd.Series([_week_ret(px[c], d_next0, d_next1)
                            for c in g_sell if c in px]).dropna()
        bm_r = None
        try:
            bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0,
                             parse_dates=True).iloc[:, 0]
            bm_r = (float(bm.asof(d_next1)) / float(bm.asof(d_next0)) - 1) * 100
        except Exception:
            pass
        cohort.append({"名單週": f"{d_sig:%m/%d}", "次週": f"{dates[i+1]:%m/%d}",
                       "大盤%": round(bm_r, 1) if bm_r is not None else None,
                       "大戶買組%": round(r_buy.mean(), 2) if len(r_buy) else None,
                       "買組檔數": len(r_buy),
                       "大戶賣組%": round(r_sell.mean(), 2) if len(r_sell) else None,
                       "賣組檔數": len(r_sell)})
    return {"week": f"{w:%Y-%m-%d}", "prev": f"{w1:%Y-%m-%d}",
            "buy": mk(list(buy.index[:20]), dw, dw1),
            "sell": mk(list(sell.index[:20]), dw, dw1),
            "return_car": mk(ret_car[:15], dw, dw1),
            "exit_car": mk(exit_car[:15], dw, dw1),
            "cohort": pd.DataFrame(cohort)}


if __name__ == "__main__":
    r = weekly_lists()
    if "error" in r:
        print(r["error"])
    else:
        print("資料週:", r["week"], "vs", r["prev"])
        print("\n【五週成績單】"); print(r["cohort"].to_string(index=False))
        print("\n【回頭車】"); print(r["return_car"].head(8).to_string(index=False))
        print("\n【下車】"); print(r["exit_car"].head(8).to_string(index=False))

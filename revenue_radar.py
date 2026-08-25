"""
revenue_radar.py — 營收反轉雷達(基本面 RRG)
=================================================================
MOPS 全市場月營收彙總(上市 sii+上櫃 otc,無限流)→
各官方產業/主題族群的「月中位 YoY」軌跡 → data/revenue_trend.csv(進 git,雲端可讀)。

口徑:成員 YoY 取中位數(不被單一暴衝股扭曲),YoY 截尾 ±100/300。
更新:每月 10 日後營收公布完 → rebuild(run_daily 內建 25 天過期自動重建)。
注意:營收 YoY 分不出「量增」vs「漲價轉嫁」(如記憶體漲價→網通報價虛胖),
     判讀需配法說筆記與毛利率驗證。
"""
from __future__ import annotations
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd
import requests

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "fundamentals"
OUT = ROOT / "data" / "revenue_trend.csv"
from twtime import now_tw


def fetch_bulk_month(mkt: str, roc_year: int, m: int, kind: int = 0) -> pd.DataFrame:
    """單月全市場營收(mkt: sii/otc;kind 0=國內、1=KY外國企業);快取永存。"""
    suffix = f"_{mkt}" if kind == 0 else f"_{mkt}_ky"      # kind=0 沿用舊快取檔名
    p = CACHE / f"bulk_rev_{roc_year}_{m}{suffix}.csv"
    if p.exists():
        return pd.read_csv(p, dtype={"code": str})
    url = f"https://mopsov.twse.com.tw/nas/t21/{mkt}/t21sc03_{roc_year}_{m}_{kind}.html"
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.encoding = "big5"
    rows = []
    for t in pd.read_html(io.StringIO(r.text)):
        if len(t) < 2:
            continue
        t.columns = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c)
                     for c in t.columns]
        cc = [c for c in t.columns if "公司 代號" in c or "公司代號" in c]
        yy = [c for c in t.columns if "去年同月" in c]
        rv = [c for c in t.columns if c.endswith("當月營收") and "累計" not in c]
        if not cc or not yy:
            continue
        for _, r2 in t.iterrows():
            code = str(r2[cc[0]]).strip()
            if not code.isdigit():
                continue
            try:
                rows.append({"code": code, "yoy": float(r2[yy[0]]),
                             "rev": float(r2[rv[0]])})
            except Exception:
                continue
    df = pd.DataFrame(rows)
    if not df.empty:
        CACHE.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)
    time.sleep(1)
    return df


def rebuild(months: int = 8) -> pd.DataFrame:
    """重抓近 N 個月 → 彙整 group×month 中位 YoY → data/revenue_trend.csv"""
    from theme_groups import THEME_GROUPS
    now = now_tw()
    roc = now.year - 1911
    # 本月營收要到次月10日才齊 → 最新完整月 = 上月(10日前=上上月)
    last_m = now.month - 1 if now.day >= 12 else now.month - 2
    ym_list = []
    y, m = roc, last_m
    for _ in range(months):
        if m <= 0:
            y, m = y - 1, m + 12
        ym_list.append((y, m))
        m -= 1
    ym_list.reverse()

    frames = []
    for y, m in ym_list:
        for mkt in ("sii", "otc"):
            for kind in (0, 1):                    # 1=KY外國企業(臻鼎/慧洋等,漏抓過)
                try:
                    d = fetch_bulk_month(mkt, y, m, kind)
                    if not d.empty:
                        d["ym"] = f"{y + 1911}-{m:02d}"
                        frames.append(d)
                except Exception as e:
                    print(f"  {mkt} {y}/{m} k{kind} 失敗:{type(e).__name__}")
    allrev = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["code", "ym"])
    allrev["yoy"] = allrev["yoy"].clip(-100, 300)

    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    sec_map = dict(zip(sl["code"], sl["sector"]))
    allrev["sector"] = allrev["code"].map(sec_map)

    rows = []
    for sec, g in allrev.dropna(subset=["sector"]).groupby("sector"):
        if g["code"].nunique() < 3:
            continue
        for ym, gg in g.groupby("ym"):
            rows.append({"group": sec, "kind": "產業", "ym": ym,
                         "yoy_med": round(gg["yoy"].median(), 1), "n": gg["code"].nunique()})
    for th, codes in THEME_GROUPS.items():
        g = allrev[allrev["code"].isin(codes)]
        if g["code"].nunique() < 3:
            continue
        for ym, gg in g.groupby("ym"):
            rows.append({"group": th, "kind": "族群", "ym": ym,
                         "yoy_med": round(gg["yoy"].median(), 1), "n": gg["code"].nunique()})
    out = pd.DataFrame(rows).sort_values(["group", "ym"])
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"revenue_trend.csv 更新:{out['group'].nunique()} 組 × {out['ym'].nunique()} 月")
    return out


def rebuild_if_stale(max_days: int = 25) -> None:
    """給 run_daily 用:檔案超過 N 天(=新月份營收該出了)自動重建。"""
    import os
    if OUT.exists() and (time.time() - OUT.stat().st_mtime) < max_days * 86400:
        return
    rebuild()


if __name__ == "__main__":
    rebuild()

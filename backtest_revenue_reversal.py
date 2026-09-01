"""
backtest_revenue_reversal.py — 「營收反轉→下季主流」歷史驗證(2019-2026)
=================================================================
問題:營收動能反轉(Q低基期+連續改善)的產業,下一季股價會跑贏大盤嗎?
訊號(同營收雷達口徑):產業成員月YoY中位數,early=前3月均、late=近3月均;
  反轉 = early<10 且 late-early>5pp 且 最新月>3月前。
時序誠實:m 月營收次月10日公布 → 訊號成立後,前瞻報酬取 m+1 月底 → m+4 月底(一季)。
輸出:整體命中率/超額報酬 + 鋼鐵/化學/航運的歷史發作清單。
執行:python backtest_revenue_reversal.py(bulk 快取在 data/fundamentals/)
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import glob
import pandas as pd
from revenue_radar import fetch_bulk_month

ROOT = Path(__file__).parent


def fetch_history(y0: int = 2019, y1: int = 2026, m1_last: int = 7) -> pd.DataFrame:
    frames = []
    for y in range(y0, y1 + 1):
        roc = y - 1911
        for m in range(1, 13):
            if y == y1 and m > m1_last:
                break
            for mkt in ("sii", "otc"):
                try:
                    d = fetch_bulk_month(mkt, roc, m)
                    if not d.empty:
                        d["ym"] = f"{y}-{m:02d}"
                        frames.append(d)
                except Exception as e:
                    print(f"  {mkt} {y}-{m} 失敗:{type(e).__name__}")
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["code", "ym"])
    out["yoy"] = pd.to_numeric(out["yoy"], errors="coerce").clip(-100, 300)
    return out.dropna(subset=["yoy"])


def month_close_panel() -> pd.DataFrame:
    """全市場月底收盤 panel(index=月,columns=code);流動性粗篩由呼叫端做。"""
    cols = {}
    for f in glob.glob(str(ROOT / "data" / "*.TW.csv")) + \
             glob.glob(str(ROOT / "data" / "*.TWO.csv")):
        code = Path(f).stem.split(".")[0]
        try:
            s = pd.read_csv(f, index_col=0, parse_dates=True, usecols=[0, 4]).iloc[:, 0]
            s = pd.to_numeric(s, errors="coerce").dropna()
            if len(s) < 300:
                continue
            # 分割/減資假象剔除
            if (s.pct_change().abs() > 0.35).any():
                continue
            cols[code] = s.resample("ME").last()
        except Exception:
            continue
    return pd.DataFrame(cols)


def run():
    print("① 抓 2019-2026 全市場月營收(快取後續免抓)…")
    rev = fetch_history()
    print(f"   {rev['code'].nunique()} 檔 × {rev['ym'].nunique()} 月")

    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    sec_map = dict(zip(sl["code"], sl["sector"]))
    rev["sector"] = rev["code"].map(sec_map)
    rev = rev.dropna(subset=["sector"])

    print("② 建產業月YoY中位數 panel…")
    sec_yoy = (rev.groupby(["sector", "ym"])["yoy"].median().unstack().T)
    sec_yoy.index = pd.PeriodIndex(sec_yoy.index, freq="M")
    sec_yoy = sec_yoy.sort_index()

    print("③ 建產業月報酬 panel(成員等權)…")
    px = month_close_panel()
    ret = px.pct_change()
    ret.index = ret.index.to_period("M")
    sec_ret = {}
    for sec in sec_yoy.columns:
        members = [c for c, s in sec_map.items() if s == sec and c in ret.columns]
        if len(members) >= 5:
            sec_ret[sec] = ret[members].mean(axis=1)
    sec_ret = pd.DataFrame(sec_ret)
    bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0,
                     parse_dates=True).iloc[:, 0]
    bm_m = bm.resample("ME").last().pct_change()
    bm_m.index = bm_m.index.to_period("M")

    print("④ 訊號→前瞻一季超額報酬…")
    rows = []
    months = [m for m in sec_yoy.index if m >= pd.Period("2019-07", "M")]
    for m in months:
        if m + 4 not in sec_ret.index:
            continue
        fwd_bm = (1 + bm_m.reindex([m + 2, m + 3, m + 4])).prod() - 1
        for sec in sec_yoy.columns:
            if sec not in sec_ret.columns:
                continue
            try:
                early = sec_yoy.loc[m - 5:m - 3, sec].mean()
                late = sec_yoy.loc[m - 2:m, sec].mean()
                cur, prev3 = sec_yoy.loc[m, sec], sec_yoy.loc[m - 3, sec]
            except Exception:
                continue
            if pd.isna(early) or pd.isna(late) or pd.isna(cur):
                continue
            sig = (early < 10) and (late - early > 5) and (cur > prev3)
            fwd = (1 + sec_ret.reindex([m + 2, m + 3, m + 4])[sec]).prod() - 1
            if pd.isna(fwd):
                continue
            rows.append({"m": str(m), "sector": sec, "signal": sig,
                         "excess": (fwd - fwd_bm) * 100})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "backtest_results" / "revenue_reversal_history.csv",
              index=False, encoding="utf-8-sig")

    sig, base = df[df["signal"]], df[~df["signal"]]
    print(f"\n=== 2019-2026 驗證(產業月樣本 {len(df)},反轉訊號 {len(sig)} 次)===")
    print(f"反轉組  下一季超額: 平均 {sig['excess'].mean():+.2f}%  中位 {sig['excess'].median():+.2f}%  勝率 {(sig['excess']>0).mean()*100:.0f}%")
    print(f"無訊號組 下一季超額: 平均 {base['excess'].mean():+.2f}%  中位 {base['excess'].median():+.2f}%  勝率 {(base['excess']>0).mean()*100:.0f}%")
    for yr, g in sig.groupby(sig["m"].str[:4]):
        print(f"  {yr}: n={len(g):3d} 平均超額 {g['excess'].mean():+.2f}%")

    print("\n=== 鋼鐵/化學/航運 歷史發作清單(連續月合併,取首月)===")
    for sec in ("鋼鐵工業", "化學工業", "航運業", "塑膠工業"):
        eps = sig[sig["sector"] == sec].sort_values("m")
        if eps.empty:
            print(f"{sec}: 無發作")
            continue
        keep, last = [], None
        for _, r in eps.iterrows():
            p = pd.Period(r["m"], "M")
            if last is None or (p - last).n > 3:
                keep.append(r)
            last = p
        txt = "  ".join(f"{r['m']}(次季{r['excess']:+.1f}%)" for r in keep)
        print(f"{sec}: {txt}")


if __name__ == "__main__":
    (ROOT / "backtest_results").mkdir(exist_ok=True)
    run()

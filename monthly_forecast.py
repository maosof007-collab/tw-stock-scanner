"""
monthly_forecast.py — 全市場月營收預測(誰這個月會開得不錯)
=================================================================
雙模型(全部盤前可知,無前視):
  A. YoY 動能外推:去年同月 ×(1+近3月YoY中位)
  B. 季節比:上月實際 ×(該股歷年「目標月/前月」MoM 中位,2019-2025)
  預測 = 兩法平均;兩法同向且接近 = 信心高。
疊籌碼確認:法人5日買超 + 大戶週Δ(誰不只會開得好,而且已經有人先卡位)。
榜單自動寫入預實追蹤(來源=月營收預測模型)→ 10日開獎自動對答案
→ 模型每月累積自己的命中率成績單。
執行:python monthly_forecast.py [2026-08]
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
CACHE = ROOT / "data" / "fundamentals"


def _bulk(roc: int, m: int) -> pd.DataFrame:
    frames = []
    for mkt in ("sii", "otc"):
        for suf in (f"_{mkt}", f"_{mkt}_ky"):
            p = CACHE / f"bulk_rev_{roc}_{m}{suf}.csv"
            if p.exists():
                frames.append(pd.read_csv(p, dtype={"code": str}))
    if not frames:
        return pd.DataFrame(columns=["code", "yoy", "rev"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["code"])


def forecast_month(target: str = "2026-08", min_vol_lots: int = 500) -> pd.DataFrame:
    y, m = int(target[:4]), int(target[5:7])
    roc = y - 1911
    prev_m, prev_roc = (m - 1, roc) if m > 1 else (12, roc - 1)

    cur = {}                                   # 2026 各月 rev/yoy per code
    for mm in range(1, m):
        d = _bulk(roc, mm)
        for _, r in d.iterrows():
            cur.setdefault(r["code"], {})[mm] = (float(r["rev"]), float(r["yoy"]))
    base_ly = _bulk(roc - 1, m).set_index("code")["rev"].astype(float)      # 去年同月
    prev = _bulk(prev_roc, prev_m).set_index("code")["rev"].astype(float)   # 上月實際

    # 季節比:歷年 目標月/前月 MoM 中位(2019-2025)
    season = {}
    for yy in range(2019, y):
        r_m = _bulk(yy - 1911, m).set_index("code")["rev"].astype(float)
        r_p = _bulk(yy - 1911, m - 1 if m > 1 else 12).set_index("code")["rev"].astype(float)
        ratio = (r_m / r_p).replace([float("inf")], float("nan")).dropna()
        for c, v in ratio.items():
            if 0.3 < v < 3:
                season.setdefault(c, []).append(v)

    # 流動性 + 名稱
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))
    sec = dict(zip(sl["code"], sl["sector"]))
    vol_ok = set()
    for f in glob.glob(str(ROOT / "data" / "*.TW.csv")) + \
             glob.glob(str(ROOT / "data" / "*.TWO.csv")):
        code = Path(f).stem.split(".")[0]
        try:
            v = pd.read_csv(f, usecols=[0, 5], index_col=0).iloc[:, 0]
            if pd.to_numeric(v, errors="coerce").tail(20).mean() >= min_vol_lots * 1000:
                vol_ok.add(code)
        except Exception:
            continue

    rows = []
    for c, months in cur.items():
        if c not in vol_ok or c not in prev.index:
            continue
        if float(prev[c]) <= 0:
            continue                     # 投資公司負營收等異常,不預測
        yoys = [months[k][1] for k in sorted(months)[-3:] if k in months]
        if len(yoys) < 3:
            continue
        yoy_med3 = float(pd.Series(yoys).median())
        yoys_prev = [months[k][1] for k in sorted(months)[-6:-3] if k in months]
        accel = yoy_med3 - float(pd.Series(yoys_prev).median()) if len(yoys_prev) >= 2 else None
        pred_a = float(base_ly[c]) * (1 + yoy_med3 / 100) if c in base_ly.index else None
        srat = float(pd.Series(season.get(c, [])).median()) if len(season.get(c, [])) >= 4 else None
        pred_b = float(prev[c]) * srat if srat else None
        preds = [p for p in (pred_a, pred_b) if p]
        if not preds:
            continue
        pred = sum(preds) / len(preds)
        pred_yoy = (pred / float(base_ly[c]) - 1) * 100 if c in base_ly.index and base_ly[c] else None
        agree = (abs(pred_a - pred_b) / pred < 0.10) if (pred_a and pred_b) else None
        pred_mom = (pred / float(prev[c]) - 1) * 100
        mkeys = sorted(months)
        last_mom = ((months[mkeys[-1]][0] / months[mkeys[-2]][0] - 1) * 100
                    if len(mkeys) >= 2 and months[mkeys[-2]][0] else None)
        rows.append({"代碼": c, "名稱": nm.get(c, ""), "產業": sec.get(c, ""),
                     "上月實際(百萬)": round(float(prev[c]) / 1000, 1),
                     "上月MoM%": round(last_mom, 1) if last_mom is not None else None,
                     "預測(百萬)": round(pred / 1000, 1),
                     "預測MoM%": round(pred_mom, 1),
                     "預測YoY%": round(pred_yoy, 1) if pred_yoy is not None else None,
                     "近3月YoY中位": round(yoy_med3, 1),
                     "加速度pp": round(accel, 1) if accel is not None else None,
                     "兩法一致": "✅" if agree else ("—" if agree is None else "❌")})
    df = pd.DataFrame(rows)

    # 籌碼偷跑層:法人5日 + 大戶週Δ
    try:
        bp = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv", index_col=0, parse_dates=True)
        bh = (bp.iloc[-1] - bp.iloc[-2]).round(2)
        df["大戶週Δpp"] = df["代碼"].map(bh)
    except Exception:
        pass
    fi5 = {}
    for c in df["代碼"]:
        p = ROOT / "data" / "institutional" / f"{c}_inst.csv"
        try:
            mm2 = pd.read_csv(p, usecols=lambda x: x in
                              ("外陸資買賣超股數(不含外資自營商)", "外資買賣超股數", "it_net"))
            a = pd.to_numeric(mm2.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
            b = pd.to_numeric(mm2.get("外資買賣超股數"), errors="coerce")
            it = pd.to_numeric(mm2.get("it_net"), errors="coerce").fillna(0)
            fi5[c] = round(float((a.fillna(b).fillna(0) + it).tail(5).sum()) / 1000)
        except Exception:
            continue
    df["法人5日(張)"] = df["代碼"].map(fi5)
    return df.sort_values("預測YoY%", ascending=False)


def record_top(df: pd.DataFrame, target: str, n: int = 20) -> int:
    """把榜單前 N 寫入預實追蹤(來源固定)→ 開獎自動對答案,模型累積月度戰績。"""
    from model_track import add_prediction
    cnt = 0
    for _, r in df.head(n).iterrows():
        add_prediction(r["代碼"], "monthly_rev", target, float(r["預測(百萬)"]),
                       f"月營收預測模型({target}榜前{n},預YoY{r['預測YoY%']:+.0f}%)")
        cnt += 1
    return cnt


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    df = forecast_month(target)
    print(f"{target} 預測樣本 {len(df)} 檔;看好榜(預測YoY前15,兩法一致優先):")
    show = df[(df["兩法一致"] != "❌") & (df["預測YoY%"] < 300)].head(15)   # >300%=併購/基期事件另計
    print(show.to_string(index=False))
    n = record_top(df, target)
    print(f"\n已寫入預實追蹤 {n} 筆(開獎自動對答案)")


def score_month(target: str) -> dict | None:
    """開獎後三層評比(需 forecast 時存的全市場預測檔 + 實際 bulk):
      ①數字層:誤差分佈/偏誤/兩法各自準度
      ②排序層:預測YoY vs 實際YoY 的 Spearman IC + 看好榜抓到前20%強股的比例
      ③報酬層:看好榜/偷跑榜 開獎窗(1~12日)報酬 vs 全市場中位
    對照基準:naive=「上月YoY延續」——模型沒贏 naive 就是白做。"""
    y, m = int(target[:4]), int(target[5:7])
    fpath = ROOT / "data" / f"_monthly_forecast_{y}{m:02d}.csv"
    if not fpath.exists():
        return None
    pred = pd.read_csv(fpath, dtype={"代碼": str})
    act = _bulk(y - 1911, m)
    if act.empty:
        return None
    act = act.set_index("code")
    j = pred.set_index("代碼").join(act[["rev", "yoy"]], how="inner").dropna(subset=["rev"])
    if len(j) < 50:
        return None
    j["實際(百萬)"] = j["rev"].astype(float) / 1000
    j["實際YoY%"] = j["yoy"].astype(float)
    j["誤差%"] = (j["實際(百萬)"] / j["預測(百萬)"] - 1) * 100

    out = {"n": len(j)}
    e = j["誤差%"]
    out["數字層"] = {"命中±5%": f"{(e.abs()<=5).mean()*100:.0f}%",
                  "命中±10%": f"{(e.abs()<=10).mean()*100:.0f}%",
                  "中位絕對誤差": f"{e.abs().median():.1f}%",
                  "偏誤(實際-預測)": f"{e.median():+.1f}%(正=系統性低估)"}
    # 排序層:IC + 前20%捕捉率;naive基準=用「近3月YoY中位」以外的最後一個月YoY
    ic = j["預測YoY%"].rank().corr(j["實際YoY%"].rank())
    naive_ic = j["近3月YoY中位"].rank().corr(j["實際YoY%"].rank())
    top_actual = j["實際YoY%"] >= j["實際YoY%"].quantile(0.8)
    top_pred = j.sort_values("預測YoY%", ascending=False).head(30).index
    capture = top_actual.loc[top_pred].mean() * 100
    out["排序層"] = {"IC(預測vs實際排名)": f"{ic:.2f}",
                  "naive基準IC": f"{naive_ic:.2f}",
                  "判定": "模型贏" if ic > naive_ic else "沒贏naive,模型無增量",
                  "看好榜30抓到實際前20%強股": f"{capture:.0f}%(亂猜=20%)"}
    # 報酬層:開獎窗 1日~12日 報酬
    px = {}
    import glob as _g
    codes_need = set(j.index)
    for f in _g.glob(str(ROOT / "data" / "*.TW.csv")) + _g.glob(str(ROOT / "data" / "*.TWO.csv")):
        c = Path(f).stem.split(".")[0]
        if c in codes_need:
            s = pd.read_csv(f, index_col=0, parse_dates=True, usecols=[0, 4]).iloc[:, 0]
            px[c] = pd.to_numeric(s, errors="coerce").dropna()
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    d0, d1 = pd.Timestamp(ny, nm, 1), pd.Timestamp(ny, nm, 12)

    def wret(c):
        s = px.get(c)
        if s is None:
            return None
        try:
            a, b = float(s.asof(d0)), float(s.asof(d1))
            return (b / a - 1) * 100 if a else None
        except Exception:
            return None
    j["開獎窗報酬%"] = [wret(c) for c in j.index]
    mkt_med = j["開獎窗報酬%"].median()
    fav = j.sort_values("預測YoY%", ascending=False).head(30)["開獎窗報酬%"].dropna()
    sneak = j[(j["預測YoY%"] > 30)]
    if "大戶週Δpp" in j.columns:
        sneak = sneak[(sneak["大戶週Δpp"].fillna(0) >= 0.5) |
                      (sneak["法人5日(張)"].fillna(0) >= 500)]
    sk = sneak["開獎窗報酬%"].dropna()
    out["報酬層"] = {"全市場中位": f"{mkt_med:+.1f}%",
                  "看好榜30": f"{fav.mean():+.1f}%(超額 {fav.mean()-mkt_med:+.1f})",
                  "偷跑榜": (f"{sk.mean():+.1f}%(超額 {sk.mean()-mkt_med:+.1f},n={len(sk)})"
                          if len(sk) else "無樣本")}
    out["detail"] = j
    return out


REV_HIST = ROOT / "data" / "_rev_history.csv"


def build_rev_history(force: bool = False) -> pd.DataFrame:
    """全市場月營收長表(code, ym, rev千元, yoy)——由歷年 bulk 快取拼裝,查個股歷史用。"""
    files = glob.glob(str(CACHE / "bulk_rev_*_*.csv"))
    if REV_HIST.exists() and not force:
        newest = max((Path(f).stat().st_mtime for f in files), default=0)
        if REV_HIST.stat().st_mtime >= newest:
            return pd.read_csv(REV_HIST, dtype={"code": str})
    frames = []
    import re
    for f in files:
        mm = re.search(r"bulk_rev_(\d+)_(\d+)_", Path(f).name)
        if not mm:
            continue
        roc, m = int(mm.group(1)), int(mm.group(2))
        d = pd.read_csv(f, dtype={"code": str})
        d["ym"] = f"{roc + 1911}-{m:02d}"
        frames.append(d[["code", "ym", "rev", "yoy"]])
    out = (pd.concat(frames, ignore_index=True)
           .drop_duplicates(subset=["code", "ym"]).sort_values(["code", "ym"]))
    out.to_csv(REV_HIST, index=False, encoding="utf-8-sig")
    return out


def monthly_history(code: str) -> pd.DataFrame:
    """個股月營收史:ym/rev(百萬)/yoy%/mom%/近3、6、12期均線/是否歷史新高。"""
    h = build_rev_history()
    s = h[h["code"] == code].sort_values("ym").copy()
    if s.empty:
        return s
    s["rev_m"] = s["rev"].astype(float) / 1000
    s["mom%"] = (s["rev_m"] / s["rev_m"].shift(1) - 1) * 100
    s["ma3"] = s["rev_m"].rolling(3).mean()
    s["ma6"] = s["rev_m"].rolling(6).mean()
    s["ma12"] = s["rev_m"].rolling(12).mean()
    s["新高"] = s["rev_m"] >= s["rev_m"].cummax()
    return s[["ym", "rev_m", "yoy", "mom%", "ma3", "ma6", "ma12", "新高"]]

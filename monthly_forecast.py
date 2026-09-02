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
        rows.append({"代碼": c, "名稱": nm.get(c, ""), "產業": sec.get(c, ""),
                     "上月實際(百萬)": round(float(prev[c]) / 1000, 1),
                     "預測(百萬)": round(pred / 1000, 1),
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

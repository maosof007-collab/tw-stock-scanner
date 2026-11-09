# -*- coding: utf-8 -*-
"""
weak_board_study.py — 弱勢榜鏡像回測(放空依據驗證)
=================================================================
「弱勢股也要有吧 放空依據 我的問題是 回測可以嗎?」(2026-11-09)。
榜:跌幅≤-3% + 成交額≥1億 + 收位≤30%,每日跌幅最深 Top20(日線重建,2023+)。
空:D+1 開盤空 → 收盤回補(現股當沖);另測持有至 D+5。開盤鎖跌停(gap≤-9.5%)剔除。

結論(2026-11-09 定版):**不做**。弱勢榜鏡像沒有可交易的肉。
  全部          n=15,246  當沖空 +0.30%/55%   5日空 -0.27%/54%
  反彈空 gap≥1%  n= 3,996  當沖空 +0.46%/58%   5日空 -0.83%
  重殺≤-7%+gap≥1 n=1,432  當沖空 +0.54%/56%(最佳切片)
  續殺跳空≤-2%   n= 1,416  當沖空 **-0.45%**/48% ← 追空開低的弱勢股是負期望
  當沖成本 0.435% 一扣,最佳切片只剩 +0.1%,其餘歸零或轉負;年度間無一年淨利可觀。
  對照:強勢榜鏡像(short_watch)跳空≥3% 衰竭空 毛利 +1.21%——空方的錢在強勢股,不在弱勢股。
  交叉驗證:弱勢股 5 日空全面為負(= 做多 +0.3%~+1.9%),大跌股平均反彈;
  外資買超篩選(crash_fi_study)才把這 +0.7% 放大成 +7.9%/76%。
  弱勢池的正確用途是「持股風控警示」(自己的股票上弱勢榜要警覺),不是放空名單。
  盤中分鐘級(rt_flow 快照)2026-10-28 才開始錄,樣本不足,無法回測盤中弱勢池。
  python weak_board_study.py   # 重跑
"""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent / "data"
START = "2023-01-01"
rows = []
files = sorted(glob.glob(str(D / "*.TW.csv"))) + sorted(glob.glob(str(D / "*.TWO.csv")))
for f in files:
    code = Path(f).stem.split(".")[0]
    try:
        p = pd.read_csv(f, usecols=["Date", "Open", "High", "Low", "Close", "Volume"])
    except Exception:
        continue
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce")
    p = p.dropna().reset_index(drop=True)
    if len(p) < 30:
        continue
    c, o, h, l, v = (p[k].astype(float) for k in ["Close", "Open", "High", "Low", "Volume"])
    chg = c.pct_change() * 100
    amt = c * v
    rng = (h - l).replace(0, np.nan)
    pos = ((c - l) / rng * 100).fillna(50)
    vr = v / v.rolling(5).mean().shift(1)
    mask = (chg <= -3) & (amt >= 1e8) & (pos <= 30) & (p["Date"] >= START)
    for i in np.where(mask)[0]:
        if i + 1 >= len(p):
            continue
        o1, c1 = o.iloc[i + 1], c.iloc[i + 1]
        if not o1 or o1 <= 0:
            continue
        gap = (o1 / c.iloc[i] - 1) * 100
        c5 = c.iloc[i + 5] if i + 5 < len(p) else np.nan
        rows.append({"d": str(p["Date"].iloc[i].date()), "code": code,
                     "chg": chg.iloc[i], "vr": vr.iloc[i], "pos": pos.iloc[i],
                     "gap": gap, "r1s": (o1 - c1) / o1 * 100,
                     "r5s": (o1 - c5) / o1 * 100 if np.isfinite(c5) else np.nan})
df = pd.DataFrame(rows)
df = df.sort_values(["d", "chg"]).groupby("d").head(20).reset_index(drop=True)
df["year"] = df["d"].str[:4]
exe = df[df["gap"] > -9.5]


def show(name, g):
    if len(g) < 30:
        print("{:<26} n={} (樣本太少)".format(name, len(g)))
        return
    print("{:<26} n={:>5}  當沖空 {:+.2f}%/勝率{:.0f}%  5日空 {:+.2f}%/勝率{:.0f}%".format(
        name, len(g), g["r1s"].mean(), (g["r1s"] > 0).mean() * 100,
        g["r5s"].mean(), (g["r5s"] > 0).mean() * 100))


if __name__ == "__main__":
    print("=== 弱勢榜 Top20 鏡像(2023+,開盤未鎖死)===")
    show("全部", exe)
    show("量比≥2(爆量殺)", exe[exe["vr"] >= 2])
    show("跳空上彈≥1%(反彈空)", exe[exe["gap"] >= 1])
    show("續殺跳空≤-2%", exe[exe["gap"] <= -2])
    show("跌幅≤-7%+gap≥1(最佳)", exe[(exe["chg"] <= -7) & (exe["gap"] >= 1)])
    for y, g in exe.groupby("year"):
        show(y, g)
    print("鎖死剔除 {} 筆;當沖空最差 {:+.1f}%、p1 {:+.1f}%".format(
        len(df) - len(exe), exe["r1s"].min(), exe["r1s"].quantile(0.01)))

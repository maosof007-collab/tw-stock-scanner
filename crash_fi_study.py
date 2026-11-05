# -*- coding: utf-8 -*-
"""
crash_fi_study.py — 跌停級大跌日 × 外資動向 回放
=================================================================
「我們的策略來驗證了 之前有提到 大跌後外資買」(2026-11-05)。
事件:個股單日跌 ≤ -9% 且成交額 ≥1億(2023 起,上市+上櫃,n≈5,000)。
口徑:隔日開盤買 → 第1/5/20日收盤(同 attention_replay,含跳空成本)。
資料:data/institutional/{code}_inst.csv(fetch_institutional 每晚已在收,
      上市自2015、上櫃自2023,不需要新抓取管線)。
結論(2026-11-05 跑):
  全部大跌日        r5 +2.8%/58%   r20 +6.7%
  外資賣超(對照)    r5 +1.8%/54%   倒貨≥10%量: r5 +1.5%/53%, r20中位 +1.6%
  外資買超          r5 +4.5%/64%
  買超≥10%成交量    r5 +5.7%/70%   r20 +10.8%/72%
  買超≥10%+前日也買 r5 +7.9%/76%   r20 +13.2%(中位 +12.4)/76%  ← 最強切片
  注意:r1 全切片皆負(-0.8~-1.3%,勝率26~35%)——隔日通常還有第二根,
  這條邊從 D+5 才顯現;大跌日群聚(同日多檔相關),有效樣本比 n 小。
  python crash_fi_study.py   # 重跑全量,輸出 data/_crash_fi_study.csv
"""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
D = ROOT / "data"
INST = D / "institutional"
START = "2023-01-01"
rows = []
files = sorted(glob.glob(str(D / "*.TW.csv"))) + sorted(glob.glob(str(D / "*.TWO.csv")))
for f in files:
    code = Path(f).stem.split(".")[0]
    ip = INST / f"{code}_inst.csv"
    if not ip.exists():
        continue
    try:
        p = pd.read_csv(f, usecols=["Date", "Open", "Close", "Volume"])
    except Exception:
        continue
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce")
    p = p.dropna().reset_index(drop=True)
    if len(p) < 30:
        continue
    c = p["Close"].astype(float)
    o = p["Open"].astype(float)
    v = p["Volume"].astype(float)
    chg = c.pct_change() * 100
    amt = c * v
    mask = (chg <= -9) & (amt >= 1e8) & (p["Date"] >= START)
    idx = np.where(mask)[0]
    if len(idx) == 0:
        continue
    try:
        inst = pd.read_csv(ip, usecols=["date", "外陸資買賣超股數(不含外資自營商)"])
    except Exception:
        continue
    fi = dict(zip(inst["date"], inst["外陸資買賣超股數(不含外資自營商)"].astype(float)))
    for i in idx:
        if i + 1 >= len(p):
            continue
        d0 = p["Date"].iloc[i].strftime("%Y-%m-%d")
        net = fi.get(d0)
        if net is None or not np.isfinite(net):
            continue
        e = o.iloc[i + 1]
        if not e or e <= 0:
            continue
        def fwd(k):
            return (c.iloc[i + k] / e - 1) * 100 if i + k < len(p) else np.nan
        # 連兩日買:前一日也買超
        d_1 = p["Date"].iloc[i - 1].strftime("%Y-%m-%d") if i >= 1 else None
        net_1 = fi.get(d_1) if d_1 else None
        rows.append({
            "d": d0, "code": code, "chg": round(chg.iloc[i], 2),
            "fi_net": net, "fi_ratio": net / v.iloc[i] * 100 if v.iloc[i] else np.nan,
            "fi_prev": net_1 if net_1 is not None else np.nan,
            "gap": round((e / c.iloc[i] - 1) * 100, 2),
            "r1": fwd(1), "r5": fwd(5), "r20": fwd(20),
        })
out = pd.DataFrame(rows)
out.to_csv(D / "_crash_fi_study.csv", index=False, encoding="utf-8-sig")
print("樣本", len(out), "事件日範圍", out["d"].min(), "→", out["d"].max())

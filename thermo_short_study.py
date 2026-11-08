# -*- coding: utf-8 -*-
"""
thermo_short_study.py — 溫度計斜率空單 壓測(指數避險劇本)
=================================================================
「這一路向下 我們應該有機會做空」(2026-11-08)檢討產物。
進場:指數收盤 < MA60 且 ratio_real 單日降幅 ≥5pt,且最近 15 日內無投降日 → 隔日開盤空
出場:投降日(全市場融資金額單日 ≤ -3.5%)或收盤站回 MA20 → 次日開盤回補;最長 10 日
ratio_real:2025 起用真值(_market_margin.csv);2020~2024 用 proxy 鏈:
  ratio_t = ratio_{t-1} × (1+大盤漲跌) × (融資金額_{t-1}/融資金額_t),2020-01 以 166 起算。
需要 data/_market_amount.csv 含 2020 起歷史(2026-11-08 已回補,1,661 日)。

壓測結論(2020-01~2026-11,8 筆,平均 +0.61%、勝率 50%、總和 +4.9%):
  賺錢的只有兩種時刻,全是「投降日出場」:2024/8/5 崩盤 +8.1%、2026/11 本波 +6.4%。
  其餘 6 筆 -4.6%~+1.2%(V 彈由站回月線逃命,虧損封頂 ~-4.5%)。
  2022 陰跌熊市只觸發 1 筆(+1.2%)——陰跌沒有單日急落,這訊號抓不到;
  2020/3 COVID 因投降日冷卻期擋住,全程空手(事後看是對的,3/19 就是底)。
定位:**不是獨立賺錢策略,是尾部避險劇本**——持股滿手時它開槓桿對沖,
  每年約 1 次假警報成本 -2~-4.5%,換 2024/8、2026/11 這種瀑布日的 +6~8%。
  平日的空方麵包是個股鏡像(short_watch),不是指數。
  python thermo_short_study.py   # 重跑壓測
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"G:\Stock\tw_backtest\tw_backtest")
D = ROOT / "data"
ENTRY_DROP = 5.0
CAPIT = -3.5
MAX_HOLD = 10

bm = pd.read_csv(D / "benchmark_TWII.csv", parse_dates=["Date"])
bm = bm.rename(columns={"Date": "date"})[["date", "Open", "Close"]]
bm["Open"] = pd.to_numeric(bm["Open"], errors="coerce").replace(0, np.nan).fillna(bm["Close"])
bm = bm.sort_values("date").reset_index(drop=True)
bm["ma60"] = bm["Close"].rolling(60).mean()          # 用完整價格史先算,避免暖機期
bm["ma20"] = bm["Close"].rolling(20).mean()
amt = pd.read_csv(D / "_market_amount.csv", parse_dates=["date"])[["date", "amt_k"]]
df = bm.merge(amt, on="date", how="inner").sort_values("date").reset_index(drop=True)
# 真值 ratio
try:
    mm = pd.read_csv(D / "_market_margin.csv", parse_dates=["date"])[["date", "ratio_real"]]
    df = df.merge(mm, on="date", how="left")
except Exception:
    df["ratio_real"] = np.nan
# proxy 鏈補(從頭鏈到真值出現為止;真值一出現即切換)
r = df["ratio_real"].copy()
proxy = np.nan
for i in range(len(df)):
    if np.isfinite(r.iloc[i]):
        proxy = r.iloc[i]
        continue
    if i == 0 or not np.isfinite(proxy):
        proxy = 166.0
        r.iloc[i] = proxy
        continue
    rt = df["Close"].iloc[i] / df["Close"].iloc[i - 1] - 1
    dd = df["amt_k"].iloc[i - 1] / df["amt_k"].iloc[i] if df["amt_k"].iloc[i] else 1
    proxy = proxy * (1 + rt) * dd
    r.iloc[i] = proxy
df["ratio"] = r
df["d_ratio"] = df["ratio"].diff()
df["debt_chg"] = df["amt_k"].pct_change() * 100

# 回測
COOLDOWN = 15
trades = []
pos = None  # (entry_idx, entry_px)
last_capit = -999
for i in range(61, len(df) - 1):
    row = df.iloc[i]
    if row["debt_chg"] <= CAPIT:
        last_capit = i
    if pos is None:
        if (row["Close"] < row["ma60"] and row["d_ratio"] <= -ENTRY_DROP
                and i - last_capit > COOLDOWN):
            pos = (i + 1, df["Open"].iloc[i + 1])   # 隔日開盤空
    else:
        ei, ep = pos
        held = i - ei
        capit = row["debt_chg"] <= CAPIT and i > ei       # 投降日(盤後得知)
        escape = row["Close"] > row["ma20"]               # 站回月線=彈升逃命
        if capit or escape or held >= MAX_HOLD:
            xp = df["Open"].iloc[i + 1]                   # 次日開盤回補
            why = "投降日" if capit else ("站回月線" if escape else "逾時")
            trades.append({
                "進": str(df['date'].iloc[ei].date()), "出": str(df['date'].iloc[i + 1].date()),
                "進價": round(ep), "出價": round(xp),
                "空單%": round((ep / xp - 1) * 100, 2),
                "天": i + 1 - ei, "出場因": why,
            })
            pos = None
t = pd.DataFrame(trades)
if t.empty:
    print("無交易")
    sys.exit()
t["年"] = t["進"].str[:4]
print(t.to_string(index=False))
print("\n合計 {} 筆,平均 {:+.2f}%,勝率 {:.0f}%,總和 {:+.1f}%".format(
    len(t), t["空單%"].mean(), (t["空單%"] > 0).mean() * 100, t["空單%"].sum()))
for y, g in t.groupby("年"):
    print(" ", y, "n={} 均{:+.2f}% 和{:+.1f}%".format(len(g), g["空單%"].mean(), g["空單%"].sum()))

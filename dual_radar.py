# -*- coding: utf-8 -*-
"""
dual_radar.py — 多空雷達:同一張族群表看兩邊的錢,附兩張已驗證的行動清單
=================================================================
多方(7/30 大跌復盤研究,data/_rebound_study_0730.csv):
  快彈的乾淨因子=營收 YoY(>30% 組快彈率 57% vs 負成長 38%);
  候補=營收YoY>30% + 自身殺幅>10% + 尚未收復失土(吃 recovery_detail.csv)。
空方(2026-11-12 回測,data/_bear_backtest.csv,2024-01~2026-11):
  S1 套牢池反彈空:距250日高<-30% + 5日漲>12% + 爆量(>2x)收黑
                  + 融資餘額/20日均量(張)>4 → 次日開盤空、持有10日
  EV10 +3.10%/勝率 75%/n=76;三年全正。不加大盤濾網(濾網只剩9筆)。
  同場陣亡:S2 反彈失敗空(負EV)、S3 爆量長黑追空(全面賠)
  → 「爆量後禁入」對空單同樣成立:只空瘋狂反彈,不追殺崩跌。
產出:_dual_radar_groups.csv(族群雙溫度)、_dual_radar_stocks.csv(逐檔)、
     _bear_s1_hits.csv(S1命中累積日誌)。推播:S1 命中才推(稀有高價值);
     多方候補不推——失土收復率日報已是多方的濃縮層,頁面才是全表。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"
G_CSV = D / "_dual_radar_groups.csv"
S_CSV = D / "_dual_radar_stocks.csv"
HITS = D / "_bear_s1_hits.csv"
MARK = D / "_dual_radar_sent.txt"

MIN_PRICE, MIN_AMT = 10.0, 0.5e8


def _margin_mult(code: str, v20_lots: float) -> float:
    """融資餘額 ÷ 20日均量(張)=套牢池深度;無資料回 NaN。"""
    p = D / "margin" / f"{code}_margin.csv"
    if not p.exists() or not v20_lots:
        return np.nan
    try:
        m = pd.read_csv(p, usecols=["margin_balance"])
        return float(m["margin_balance"].iloc[-1]) / v20_lots
    except Exception:
        return np.nan


def _scan_one(f: str, days: int = 5) -> dict | None:
    """單檔近況 + 近 days 日 S1 命中。"""
    code = os.path.basename(f).split(".")[0]
    if len(code) != 4:
        return None
    try:
        d = pd.read_csv(f, usecols=["Date", "Open", "High", "Close", "Volume"],
                        parse_dates=["Date"])
    except Exception:
        return None
    d = d.dropna(subset=["Close"])
    if len(d) < 260:
        return None
    c, o, v = d["Close"].to_numpy(float), d["Open"].to_numpy(float), d["Volume"].to_numpy(float)
    v20 = pd.Series(v).rolling(20).mean().to_numpy()
    a20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    ma60 = pd.Series(c).rolling(60).mean().to_numpy()
    hi250 = pd.Series(d["High"]).rolling(250, min_periods=100).max().to_numpy()
    r5 = pd.Series(c).pct_change(5).to_numpy() * 100
    if c[-1] < MIN_PRICE or not a20[-1] or a20[-1] < MIN_AMT:
        return None
    mm = _margin_mult(code, v20[-1] / 1000 if v20[-1] else 0)
    hit_days = []
    for i in range(max(260, len(d) - days), len(d)):
        if (c[i] / hi250[i] - 1 < -0.30 and r5[i] > 12 and c[i] < o[i]
                and v[i] > 2 * v20[i] and mm and not np.isnan(mm) and mm > 4):
            hit_days.append(f"{d['Date'].iloc[i]:%Y-%m-%d}")
    return dict(code=code, date=f"{d['Date'].iloc[-1]:%Y-%m-%d}",
                close=round(c[-1], 2), chg1=round((c[-1] / c[-2] - 1) * 100, 2),
                chg5=round(r5[-1], 1), off_hi=round((c[-1] / hi250[-1] - 1) * 100, 1),
                below_ma60=bool(c[-1] < ma60[-1]),
                vol_mult=round(v[-1] / v20[-1], 2) if v20[-1] else np.nan,
                black=bool(c[-1] < o[-1]),
                margin_mult=round(mm, 1) if mm == mm else np.nan,
                s1_today=bool(hit_days and hit_days[-1] == f"{d['Date'].iloc[-1]:%Y-%m-%d}"),
                s1_hits=",".join(hit_days))


def _recovery_join() -> pd.DataFrame:
    """失土收復明細(多方素材);缺檔或過舊時現場重算一次。"""
    p = D / "recovery_detail.csv"
    try:
        rd = pd.read_csv(p, dtype={"code": str})
    except Exception:
        rd = pd.DataFrame()
    if rd.empty:
        try:
            import recovery_rate
            recovery_rate.compute()
            rd = pd.read_csv(p, dtype={"code": str})
        except Exception:
            return pd.DataFrame()
    rd["flush"] = (rd["bot"] / rd["ref"] - 1) * 100
    return rd[["code", "ref", "bot", "last", "retrace", "full", "flush", "turn"]]


def _rev_map() -> pd.Series:
    r = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    r = r.sort_values("ym")
    return r.groupby("code")["yoy%"].last()


def compute() -> dict:
    from theme_groups import THEME_GROUPS
    from data_provider import stock_name
    rows = []
    for f in glob.glob(str(D / "[1-9]*.TW.csv")) + glob.glob(str(D / "[1-9]*.TWO.csv")):
        r = _scan_one(f)
        if r:
            rows.append(r)
    df = pd.DataFrame(rows)
    df["name"] = df["code"].map(stock_name)
    c2g = {}
    for g, codes in THEME_GROUPS.items():
        for c in codes:
            c2g.setdefault(str(c), g)
    df["group"] = df["code"].map(c2g).fillna("(未分組)")
    # 多方素材:收復狀態+營收
    rec = _recovery_join()
    if not rec.empty:
        df = df.merge(rec, on="code", how="left")
    else:
        for col in ("retrace", "full", "flush"):
            df[col] = np.nan
    df["rev_yoy"] = df["code"].map(_rev_map())
    df["bull_cand"] = (df["rev_yoy"] > 30) & (df["flush"] < -10) & (df["full"] != True)  # noqa: E712
    df.sort_values(["s1_today", "bull_cand", "chg5"], ascending=False).to_csv(
        S_CSV, index=False, encoding="utf-8-sig")

    gd = df[df["group"] != "(未分組)"]
    agg = gd.groupby("group").agg(
        檔數=("code", "count"),
        收復率=("full", "mean"),
        營收加速檔=("bull_cand", "sum"),
        破MA60比=("below_ma60", "mean"),
        套牢倍數中位=("margin_mult", "median"),
        今日收黑比=("black", "mean"),
        五日中位=("chg5", "median"),
        S1命中=("s1_today", "sum"),
    ).round(2)
    agg["多方分"] = (agg["收復率"].fillna(0) * 50 + agg["營收加速檔"] * 5
                   + (1 - agg["破MA60比"]) * 20).round(1)
    agg["空方分"] = (agg["破MA60比"] * 40 + agg["今日收黑比"] * 20
                   + agg["套牢倍數中位"].clip(0, 10) * 3).round(1)
    agg["淨傾向"] = (agg["多方分"] - agg["空方分"]).round(1)
    agg = agg.sort_values("淨傾向", ascending=False)
    agg.to_csv(G_CSV, encoding="utf-8-sig")

    hits = df[df["s1_today"]]
    if len(hits):
        log = hits[["date", "code", "name", "close", "chg5", "off_hi", "margin_mult", "vol_mult"]]
        old = pd.read_csv(HITS, dtype={"code": str}) if HITS.exists() else pd.DataFrame()
        pd.concat([old, log], ignore_index=True).drop_duplicates(["date", "code"]) \
            .to_csv(HITS, index=False, encoding="utf-8-sig")
    return dict(stocks=len(df), hits=hits["code"].tolist() if len(hits) else [],
                bulls=int(df["bull_cand"].sum()), asof=df["date"].max() if len(df) else "")


def push() -> str:
    """S1 命中才推(月均 2-3 筆);多方候補由失土收復率日報濃縮,不另推。"""
    today_s = f"{now_tw():%Y-%m-%d}"
    if MARK.exists() and MARK.read_text() == today_s:
        return "今日已掃過,跳過"
    import line_push
    if not line_push.enabled():
        return "推播未設定,連算都不算"
    res = compute()
    MARK.write_text(today_s)
    if not res["hits"]:
        return f"無 S1 命中(掃 {res['stocks']} 檔),不推"
    from data_provider import stock_name
    names = "、".join(f"{c} {stock_name(c)}" for c in res["hits"][:6])
    txt = (f"🐻 套牢池反彈空命中 {today_s[5:]}\n{names}\n"
           f"規格:距高>30%跌幅+5日漲>12%+爆量收黑+融資/日均量>4\n"
           f"回測 EV10 +3.1%/勝率75%(n76)|次日開盤進、10日時間出場\n"
           f"⚠️ 處置股不可空|確認可券|細節開 App 多空雷達頁")
    r = line_push.push_text(txt)
    return f"命中 {len(res['hits'])} 檔;{r}"


if __name__ == "__main__":
    import sys
    res = compute()
    print(f"掃描 {res['stocks']} 檔(資料日 {res['asof']});"
          f"多方候補 {res['bulls']} 檔;今日 S1 命中:{res['hits'] or '無'}")
    print(pd.read_csv(G_CSV).head(12).to_string(index=False))
    if "--push" in sys.argv:
        print(push())

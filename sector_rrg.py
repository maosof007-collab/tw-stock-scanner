"""
sector_rrg.py — 產業輪動 RRG（相對輪動圖）引擎
=================================================================
把「相對強度 RS」拆成兩軸（都以 100 為中心）畫四象限：
  · RS-Ratio    = RS 相對自身趨勢的位置（>100 走強 / <100 走弱）
  · RS-Momentum = RS-Ratio 的變化動能（>100 動能增強 / <100 減弱）
四象限順時針轉：改善(左上) → 領先(右上) → 弱化(右下) → 落後(左下)

做法（近似 JdK RRG，週線）：
  產業指數 = 成員股歸一化(=100)平均；RS = 產業指數 / 大盤(TWII)；
  RS-Ratio = 100 + zscore(RS, W)；RS-Momentum = 100 + zscore(RS-Ratio 的動能, W)。
資料：data/stock_list.csv(產業別) + data/{code}.csv + benchmark_TWII.csv。
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import data_provider as dp

DATA = Path(__file__).parent / "data"

QUADRANTS = {
    "領先": {"color": "#FF4D6D", "en": "LEADING"},    # 右上：強且動能升
    "改善": {"color": "#00E5FF", "en": "IMPROVING"},  # 左上：弱但動能升
    "落後": {"color": "#B49BFF", "en": "LAGGING"},    # 左下：弱且動能降
    "弱化": {"color": "#FFC857", "en": "WEAKENING"},  # 右下：強但動能降
}


def _quadrant(ratio, mom):
    if ratio >= 100 and mom >= 100:
        return "領先"
    if ratio < 100 and mom >= 100:
        return "改善"
    if ratio < 100 and mom < 100:
        return "落後"
    return "弱化"


def _weekly_close(code, weeks):
    df = dp.get_ohlcv(code, period_days=weeks * 7 + 60)
    if df is None or df.empty:
        return None
    s = df.set_index("date")["close"].dropna()
    return s.resample("W-FRI").last().dropna()


def _bench_weekly(weeks):
    """回傳 (週線收盤, 原始日線最後日期)。"""
    p = DATA / "benchmark_TWII.csv"
    if not p.exists():
        return None, None
    b = pd.read_csv(p)
    b["date"] = pd.to_datetime(b["Date"], errors="coerce")
    b["Close"] = pd.to_numeric(b["Close"], errors="coerce")
    b = b.dropna(subset=["date", "Close"]).set_index("date")["Close"]
    if b.empty:
        return None, None
    return b.resample("W-FRI").last().dropna().tail(weeks + 20), b.index[-1]


def build_rrg(weeks: int = 60, ratio_win: int = 12, tail_weeks: int = 8,
              min_members: int = 5, max_members: int = 40):
    """回傳 (points_df, tails_dict, asof)。
    points_df: 產業/RS-Ratio/RS-Momentum/象限/成員數；
    tails: {產業: DataFrame(date,ratio,mom)}；asof: 大盤日線最後日期。"""
    sl = pd.read_csv(DATA / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    sl["code"] = sl["ticker"].str.replace(".TWO", "", regex=False)\
                             .str.replace(".TW", "", regex=False).str.strip()
    bench, asof = _bench_weekly(weeks)
    if bench is None or len(bench) < ratio_win + tail_weeks + 5:
        return pd.DataFrame(), {}, None

    points, tails = [], {}
    for sector, grp in sl.groupby("sector"):
        codes = grp["code"].dropna().tolist()[:max_members]
        cols = {}
        for c in codes:
            s = _weekly_close(c, weeks)
            if s is not None and len(s) >= ratio_win + tail_weeks + 5:
                cols[c] = s
        if len(cols) < min_members:
            continue
        panel = pd.DataFrame(cols).sort_index()
        panel = panel.ffill().dropna(how="any")
        if len(panel) < ratio_win + tail_weeks + 5:
            panel = pd.DataFrame(cols).sort_index().ffill()
            panel = panel.dropna(how="all")
        # 產業指數 = 各成員歸一化(=100) 後平均
        idx = (panel / panel.iloc[0] * 100).mean(axis=1)
        # 對齊大盤
        df = pd.concat([idx.rename("sec"), bench.rename("bench")], axis=1).dropna()
        if len(df) < ratio_win + tail_weeks + 3:
            continue
        rs = df["sec"] / df["bench"]
        rs = rs / rs.iloc[0] * 100
        # RS-Ratio：RS 相對自身滾動均值的 z 分數，中心 100
        m = rs.rolling(ratio_win).mean()
        sd = rs.rolling(ratio_win).std()
        rs_ratio = 100 + (rs - m) / sd.replace(0, np.nan)
        # RS-Momentum：RS-Ratio 動能(近 roc) 的 z 分數，中心 100
        roc = rs_ratio.diff()
        rm = roc.rolling(ratio_win).mean()
        rsd = roc.rolling(ratio_win).std()
        rs_mom = 100 + (roc - rm) / rsd.replace(0, np.nan)

        both = pd.concat([rs_ratio.rename("ratio"), rs_mom.rename("mom")], axis=1).dropna()
        if both.empty:
            continue
        tail = both.tail(tail_weeks)
        cur = tail.iloc[-1]
        points.append({
            "產業": sector, "RS-Ratio": round(float(cur["ratio"]), 2),
            "RS-Momentum": round(float(cur["mom"]), 2),
            "象限": _quadrant(cur["ratio"], cur["mom"]), "成員數": len(cols),
        })
        tails[sector] = tail.rename_axis("date").reset_index()

    pts = pd.DataFrame(points)
    if not pts.empty:
        order = {"領先": 0, "改善": 1, "弱化": 2, "落後": 3}
        pts["_o"] = pts["象限"].map(order)
        pts = pts.sort_values(["_o", "RS-Ratio"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    return pts, tails, asof

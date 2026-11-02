# -*- coding: utf-8 -*-
"""
attention_replay.py — 強勢資金榜歷史回放 + 每日檢討
=================================================================
「跑 然後每天檢討 我想看的是 有否策略可以生出來」(2026-11-02)。
把頁39 的 EOD 注意力榜(RS/占比倍數/量比/收位 四因子當日百分位均值,Top20)
逐日重算回 2023,記錄「隔日開盤買」的 1/5/20 日報酬 → data/_attention_hist.csv。
口徑與 attention_scan.scan() 一致;占比倍數在排名內等價於 額/自己20日均額
(全市場總額上下約分),故不需逐日總額。
隔日沖=規則版(漲≥8%+量比≥2.5)——迴轉率雷達無歷史檔,回放只能用規則版。
報酬=隔日開盤進場(榜是盤後才知道,誠實口徑,含跳空追價成本)→ 第1/5/20日收盤。

  python attention_replay.py            # 全量回放(2023 起,約數分鐘)
  python attention_replay.py update     # 增量:重算近 40 日+補熟成報酬(每晚檢討用)
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
HIST = D / "_attention_hist.csv"
TOP = 20
MIN_AMT_E8 = 1.0          # 成交額門檻(億),同 scan(min_amount=1e8)
START = "2023-01-01"


def _mkt_chg() -> pd.Series:
    bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
    idx = pd.to_datetime(bm["Date"])
    return pd.Series(bm["Close"].astype(float).values, index=idx).pct_change() * 100


def _stock_frame(f: str, start: pd.Timestamp) -> pd.DataFrame | None:
    """單檔全期日線 → 回放需要的欄位(rolling 先算再裁切,窗口不缺)。"""
    try:
        px = pd.read_csv(f, usecols=["Date", "Open", "High", "Low", "Close", "Volume"])
    except Exception:
        return None
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    px = px.dropna(subset=["Date", "Close", "Volume"]).sort_values("Date")
    if len(px) < 25:
        return None
    c = px["Close"].astype(float).reset_index(drop=True)
    o = px["Open"].astype(float).reset_index(drop=True)
    h = px["High"].astype(float).reset_index(drop=True)
    l = px["Low"].astype(float).reset_index(drop=True)
    v = px["Volume"].astype(float).reset_index(drop=True)
    amt = c * v
    out = pd.DataFrame({
        "日期": px["Date"].values,
        "收盤": c, "開盤": o,
        "漲跌%": c.pct_change() * 100,
        "量比": v / v.rolling(20).mean().shift(1).clip(lower=1),
        "占比倍數": (amt / amt.rolling(20).mean().shift(1).clip(lower=1e-9)).clip(upper=15),
        "收位%": np.where(h > l, (c - l) / (h - l) * 100, 50.0),
        "創20日高": (c >= c.rolling(20).max()).astype(int),
        "額億": amt / 1e8,
    })
    # 隔日開盤進場 → 第1/5/20日收盤(跳空%=追價成本,已含在報酬裡)
    e = out["開盤"].shift(-1)
    out["跳空%"] = (e / out["收盤"] - 1) * 100
    out["1日%"] = (out["收盤"].shift(-1) / e - 1) * 100
    out["5日%"] = (out["收盤"].shift(-5) / e - 1) * 100
    out["20日%"] = (out["收盤"].shift(-20) / e - 1) * 100
    out["代號"] = Path(f).stem.split(".")[0]
    out = out[(out["日期"] >= start) & (out["額億"] >= MIN_AMT_E8)]
    return out if len(out) else None


def _replay(start: str) -> pd.DataFrame:
    """回放主體(不落檔):逐日重排 Top20。"""
    mkt = _mkt_chg()
    t0 = pd.Timestamp(start)
    parts = []
    for f in sorted(glob.glob(str(D / "[0-9]*.csv"))):
        code = Path(f).stem.split(".")[0]
        if not (code.isdigit() and len(code) == 4):
            continue
        fr = _stock_frame(f, t0)
        if fr is not None:
            parts.append(fr)
    if not parts:
        return pd.DataFrame()
    allr = pd.concat(parts, ignore_index=True)
    allr["RS"] = allr["漲跌%"] - allr["日期"].map(mkt)
    allr = allr.dropna(subset=["RS", "量比", "占比倍數", "漲跌%"])

    for col in ("RS", "占比倍數", "量比", "收位%"):
        allr[f"_p{col}"] = allr.groupby("日期")[col].rank(pct=True) * 100
    allr["分數"] = allr[[c for c in allr.columns if c.startswith("_p")]].mean(axis=1)

    top = (allr.sort_values(["日期", "分數"], ascending=[True, False])
               .groupby("日期").head(TOP).copy())
    top["排名"] = top.groupby("日期").cumcount() + 1
    top["隔日沖"] = np.where((top["漲跌%"] >= 8) & (top["量比"] >= 2.5), "⚠", "")

    # 連榜天數(以交易日序號判連續;新面孔=連榜1)
    days = {d: i for i, d in enumerate(sorted(top["日期"].unique()))}
    top["_ord"] = top["日期"].map(days)
    top = top.sort_values(["代號", "_ord"])
    run = (top.groupby("代號")["_ord"].diff() != 1).cumsum()
    top["連榜"] = top.groupby(["代號", run]).cumcount() + 1

    try:
        from symbols import resolve
        names = {c: (resolve(c)[1] or c) for c in top["代號"].unique()}
        top["名稱"] = top["代號"].map(names)
    except Exception:
        top["名稱"] = top["代號"]

    cols = ["日期", "代號", "名稱", "排名", "分數", "漲跌%", "RS", "量比",
            "占比倍數", "收位%", "額億", "創20日高", "連榜", "隔日沖",
            "跳空%", "1日%", "5日%", "20日%"]
    out = top[cols].sort_values(["日期", "排名"]).reset_index(drop=True)
    for c in ("分數", "漲跌%", "RS", "量比", "占比倍數", "收位%", "額億",
              "跳空%", "1日%", "5日%", "20日%"):
        out[c] = out[c].astype(float).round(2)
    out["日期"] = out["日期"].dt.strftime("%Y-%m-%d")
    return out


def build(start: str = START) -> pd.DataFrame:
    """全量回放 → HIST。"""
    out = _replay(start)
    if len(out):
        out.to_csv(HIST, index=False, encoding="utf-8-sig")
    return out


def update() -> pd.DataFrame:
    """每晚增量:重算近 45 交易日(新榜+把未熟成的 1/5/20 日報酬補滿),併回 HIST。
    排名是當日橫斷面,舊日重算結果不變,只有 forward 報酬會長出來。"""
    if not HIST.exists():
        return build()
    old = pd.read_csv(HIST, dtype={"代號": str})
    cut = (pd.Timestamp(old["日期"].max()) - pd.tseries.offsets.BDay(45)).strftime("%Y-%m-%d")
    new = _replay(cut)
    out = pd.concat([old[old["日期"] < cut], new], ignore_index=True)
    out.to_csv(HIST, index=False, encoding="utf-8-sig")
    return out


def _stats(h: pd.DataFrame) -> dict:
    v = h.dropna(subset=["1日%"])
    v20 = h.dropna(subset=["20日%"])
    return {
        "n": len(h),
        "d1": v["1日%"].mean(), "w1": (v["1日%"] > 0).mean() * 100,
        "d20": v20["20日%"].mean(), "w20": (v20["20日%"] > 0).mean() * 100,
    }


def review_line() -> str:
    """LINE 一行檢討:最新已熟成(D+1 有價)的那期榜。"""
    if not HIST.exists():
        return "強勢榜回放檔不存在"
    h = pd.read_csv(HIST, dtype={"代號": str})
    m = h.dropna(subset=["1日%"])
    if m.empty:
        return "強勢榜尚無已熟成榜期"
    d = m["日期"].max()
    b = m[m["日期"] == d]
    bx = b[b["隔日沖"] != "⚠"]
    r60 = m[m["日期"] >= sorted(m["日期"].unique())[-60:][0]]
    s5 = r60.dropna(subset=["5日%"])
    msg = (f"💪 強勢榜檢討 {d[5:]}:榜{len(b)}檔 隔日買 "
           f"平均{b['1日%'].mean():+.1f}%/勝{(b['1日%'] > 0).mean()*100:.0f}%")
    if len(bx):
        msg += f";排除⚠ {bx['1日%'].mean():+.1f}%"
    if len(s5):
        msg += (f"|近60榜 D+5 {s5['5日%'].mean():+.1f}%"
                f"/勝{(s5['5日%'] > 0).mean()*100:.0f}%")
    return msg


SENT = D / "_att_review_sent.json"


def push_review() -> str:
    """每晚檢討:增量回放 → LINE 一行戰績。同一熟成榜日只推一次(多時段防重)。"""
    import json
    update()
    line = review_line()
    h = pd.read_csv(HIST, dtype={"代號": str})
    m = h.dropna(subset=["1日%"])
    if m.empty:
        return line
    d = m["日期"].max()
    try:
        sent = json.loads(SENT.read_text(encoding="utf-8")) if SENT.exists() else {}
    except Exception:
        sent = {}
    if sent.get("date") == d:
        return f"{d} 已推過,跳過"
    try:
        import line_push
        if line_push.enabled():
            line_push.push_text(line)
    except Exception:
        pass
    try:
        SENT.write_text(json.dumps({"date": d}), encoding="utf-8")
    except Exception:
        pass
    return line


if __name__ == "__main__":
    import sys as _s
    if len(_s.argv) > 1 and _s.argv[1] == "update":
        h = update()
    else:
        h = build()
    st = _stats(h)
    print(f"回放 {st['n']:,} 筆(Top{TOP}/日)")
    print(f"  D+1 平均 {st['d1']:+.2f}% 勝率 {st['w1']:.0f}% | "
          f"D+20 平均 {st['d20']:+.2f}% 勝率 {st['w20']:.0f}%")
    print(review_line())

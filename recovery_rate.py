# -*- coding: utf-8 -*-
"""
recovery_rate.py — 失土收復率:大跌週期的收復廣度(市場情緒階段溫度計)
=================================================================
源自 7/30 大跌復盤研究(data/_rebound_study_0730.csv):
  - 快彈股的乾淨因子是「營收 YoY」(>30% 組快彈率 57% vs 負成長組 38%)
  - 貼高點/高動能反而是反指標 → 本指標同時追蹤營收分組的收復差
定義:
  - 週期:TWII 近 200 日高點(前高)→ 之後最低點(落底),回檔 ≥8% 才算
  - 失土線:每檔自己在「前高日」的收盤價
  - 全收復 = 收盤 ≥ 失土線;過半 = 從自身低點回升超過跌幅一半
分層鐵律:逐檔明細落 data/recovery_detail.csv(日誌全收),
推播只有一則濃縮(notify_push 每日一次,marker 防重)。
階段判讀是經驗映射(情緒八階段框架),不是定律——只當溫度計用。
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
HIST = D / "recovery_rate.csv"
DETAIL = D / "recovery_detail.csv"
MARK = D / "_recovery_sent.txt"

MIN_DD = -8.0          # TWII 回檔不到 8% 不算週期(盤整不值得推)
MIN_PRICE = 10.0       # 低價股排除
MIN_TURN = 0.5e8       # 前高日 20 日均額門檻(與 7/30 研究一致)


def _detect_cycle() -> dict | None:
    """從 TWII 偵測進行中的大跌週期;無週期回傳 None。"""
    b = pd.read_csv(D / "benchmark_TWII.csv", parse_dates=["Date"])
    b = b.dropna(subset=["Close"]).tail(200).reset_index(drop=True)
    if len(b) < 30:
        return None
    i_hi = int(b["Close"].idxmax())
    if i_hi >= len(b) - 5:          # 前高就在最近幾天=創高行情,無失土可收
        return None
    seg = b.iloc[i_hi:]
    i_bot = int(seg["Close"].idxmin())
    ref_c, bot_c, last_c = b["Close"].iloc[i_hi], b["Close"].iloc[i_bot], b["Close"].iloc[-1]
    dd = (bot_c / ref_c - 1) * 100
    if dd > MIN_DD:
        return None
    pos = (last_c - bot_c) / (ref_c - bot_c) * 100 if ref_c > bot_c else 100.0
    return dict(ref_date=b["Date"].iloc[i_hi], bot_date=b["Date"].iloc[i_bot],
                twii_dd=dd, twii_pos=pos, complete=last_c >= ref_c)


def _rev_map() -> pd.Series:
    """每檔最新一期月營收 YoY(近 4 個月內,避免下市殭屍)。"""
    r = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    ym_max = r["ym"].max()
    lo = f"{int(ym_max[:4]) - (1 if int(ym_max[5:]) <= 4 else 0)}-{(int(ym_max[5:]) - 4) % 12 + 1:02d}"
    r = r[r["ym"] >= lo].sort_values("ym")
    return r.groupby("code")["yoy%"].last()


def compute(cyc: dict | None = None) -> dict | None:
    cyc = cyc or _detect_cycle()
    if cyc is None:
        return None
    ref_d = cyc["ref_date"]
    rows = []
    for f in glob.glob(str(D / "[1-9]*.TW.csv")) + glob.glob(str(D / "[1-9]*.TWO.csv")):
        code = os.path.basename(f).split(".")[0]
        if len(code) != 4:
            continue
        try:
            d = pd.read_csv(f, usecols=["Date", "Close", "Volume"], parse_dates=["Date"])
        except Exception:
            continue
        d = d.dropna(subset=["Close"])
        if d.empty or d["Date"].iloc[-1] <= ref_d:
            continue
        i_ref = int(d["Date"].searchsorted(ref_d, side="right")) - 1
        # 前高日當天要有價(容忍 7 個日曆日內的最近交易日;長停牌剔除)
        if i_ref < 60 or (ref_d - d["Date"].iloc[i_ref]).days > 7:
            continue
        c = d["Close"].to_numpy(float)
        ref_c = c[i_ref]
        turn = np.nanmean((d["Close"] * d["Volume"]).to_numpy(float)[i_ref - 19:i_ref + 1])
        if ref_c < MIN_PRICE or turn < MIN_TURN:
            continue
        seg = c[i_ref:]
        bot_c = float(np.nanmin(seg))
        last_c, prev_c = float(c[-1]), float(c[-2])
        retr = (last_c - bot_c) / (ref_c - bot_c) if ref_c > bot_c else 1.0
        rows.append(dict(code=code, ref=round(ref_c, 2), bot=round(bot_c, 2),
                         last=round(last_c, 2), retrace=round(min(retr, 9.99), 3),
                         full=last_c >= ref_c, new_full=last_c >= ref_c > prev_c,
                         turn=round(turn / 1e8, 2)))
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["rev_yoy"] = df["code"].map(_rev_map())
    full_pct = df["full"].mean() * 100
    half_pct = (df["retrace"] >= 0.5).mean() * 100
    g_hi = df[df["rev_yoy"] > 30]
    g_lo = df[df["rev_yoy"] <= 0]
    res = dict(
        asof=f"{pd.Timestamp(now_tw().date()):%Y-%m-%d}",
        ref_date=f"{cyc['ref_date']:%Y-%m-%d}", bot_date=f"{cyc['bot_date']:%Y-%m-%d}",
        n=len(df), full_pct=round(full_pct, 1), half_pct=round(half_pct, 1),
        rev30_pct=round(g_hi["full"].mean() * 100, 1) if len(g_hi) > 30 else np.nan,
        revneg_pct=round(g_lo["full"].mean() * 100, 1) if len(g_lo) > 30 else np.nan,
        twii_pos=round(cyc["twii_pos"], 1), twii_dd=round(cyc["twii_dd"], 1),
        complete=cyc["complete"],
        new_full=df[df["new_full"]].sort_values("turn", ascending=False)["code"].tolist(),
    )
    df.sort_values("retrace", ascending=False).to_csv(DETAIL, index=False, encoding="utf-8-sig")
    hist = pd.read_csv(HIST, dtype={"ref_date": str}) if HIST.exists() else pd.DataFrame()
    row = {k: (",".join(v[:20]) if k == "new_full" else v) for k, v in res.items()}
    hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    hist = hist.drop_duplicates(subset=["asof"], keep="last")
    hist.to_csv(HIST, index=False, encoding="utf-8-sig")
    return res


def _stage(full_pct: float, twii_pos: float, delta: float | None) -> str:
    """情緒八階段的經驗映射(溫度計,非定律)。"""
    if full_pct >= 80:
        s = "週期尾聲(多數已收復)"
    elif full_pct >= 50:
        s = "牛市前段(希望→樂觀)"
    elif full_pct >= 25:
        s = "第8階段:回升確認中"
    elif full_pct >= 10:
        s = "第7→8階段:懷疑中回升"
    elif twii_pos < 30:
        s = "第5–6階段:投降/憤怒"
    else:
        s = "第6–7階段:沮喪打底"
    if delta is not None and abs(delta) >= 0.05:
        s += f"(較前日{'+' if delta > 0 else ''}{delta:.1f}pp)"
    return s


def build_text(res: dict) -> str:
    from data_provider import stock_name
    delta = None
    if HIST.exists():
        h = pd.read_csv(HIST)
        h = h[h["asof"] < res["asof"]]
        if len(h):
            delta = res["full_pct"] - float(h["full_pct"].iloc[-1])
    ref_md = res["ref_date"][5:].replace("-", "/")
    lines = [f"🧭 失土收復率 {res['asof'][5:].replace('-', '/')}(失土線={ref_md}前高,n={res['n']})",
             f"全收復 {res['full_pct']}%|過半 {res['half_pct']}%|大盤回升 {res['twii_pos']}%"]
    if not np.isnan(res.get("rev30_pct", np.nan)) and not np.isnan(res.get("revneg_pct", np.nan)):
        lines.append(f"營收>30%組 {res['rev30_pct']}% vs 負成長組 {res['revneg_pct']}%"
                     f"(差距=資金挑基本面的程度)")
    nf = res["new_full"]
    if nf:
        names = "、".join(f"{c}{stock_name(c)}" for c in nf[:6])
        lines.append(f"今日新收復:{names}" + (f" …共{len(nf)}檔" if len(nf) > 6 else ""))
    lines.append(f"階段:{_stage(res['full_pct'], res['twii_pos'], delta)}")
    if res["complete"]:
        lines.append("✅ 大盤已收復失土,本週期觀測進入尾聲")
    return "\n".join(lines)


def push() -> str:
    """每日一則(notify_push 呼叫;marker 防重,先查 marker 再算,省 2000 檔 IO)。"""
    today_s = f"{now_tw():%Y-%m-%d}"
    if MARK.exists() and MARK.read_text() == today_s:
        return "今日已推過,跳過"
    import line_push
    if not line_push.enabled():
        return "推播未設定,連算都不算(省 600 檔 IO)"
    cyc = _detect_cycle()
    if cyc is None:
        return "無進行中大跌週期(TWII 回檔 <8%),不推"
    res = compute(cyc)
    if res is None:
        return "樣本不足,跳過"
    r = line_push.push_text(build_text(res))
    if "成功" in r:
        MARK.write_text(today_s)
    return r


if __name__ == "__main__":
    import sys
    c = _detect_cycle()
    if c is None:
        print("無進行中大跌週期")
    else:
        print(f"週期:前高 {c['ref_date']:%m/%d} → 落底 {c['bot_date']:%m/%d}"
              f"(回檔 {c['twii_dd']:.1f}%,已回升 {c['twii_pos']:.0f}%)")
        r = compute(c)
        print(build_text(r))
        if "--push" in sys.argv:
            print(push())

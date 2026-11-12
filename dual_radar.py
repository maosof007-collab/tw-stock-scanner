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


def _scan_one(f: str, days: int = 5, keep: frozenset = frozenset()) -> dict | None:
    """單檔近況 + 近 days 日 S1 命中。keep=族群成分:不夠流動也要列(但不進策略清單)。"""
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
    liquid = not (c[-1] < MIN_PRICE or not a20[-1] or a20[-1] < MIN_AMT)
    if not liquid and code not in keep:
        return None
    mm = _margin_mult(code, v20[-1] / 1000 if v20[-1] else 0)
    hit_days = []
    for i in range(max(260, len(d) - days), len(d)):
        if (liquid and c[i] / hi250[i] - 1 < -0.30 and r5[i] > 12 and c[i] < o[i]
                and v[i] > 2 * v20[i] and mm and not np.isnan(mm) and mm > 4):
            hit_days.append(f"{d['Date'].iloc[i]:%Y-%m-%d}")
    def _r20(off: int) -> float:              # off 天前的 20 日報酬(族群排名升降用)
        return round((c[-1 - off] / c[-21 - off] - 1) * 100, 2)

    return dict(code=code, date=f"{d['Date'].iloc[-1]:%Y-%m-%d}",
                close=round(c[-1], 2), chg1=round((c[-1] / c[-2] - 1) * 100, 2),
                r20=_r20(0), r20_d1=_r20(1), r20_d5=_r20(5),
                chg5=round(r5[-1], 1), off_hi=round((c[-1] / hi250[-1] - 1) * 100, 1),
                below_ma60=bool(c[-1] < ma60[-1]),
                vol_mult=round(v[-1] / v20[-1], 2) if v20[-1] else np.nan,
                black=bool(c[-1] < o[-1]), liquid=liquid,
                margin_mult=round(mm, 1) if mm == mm else np.nan,
                s1_today=bool(hit_days and hit_days[-1] == f"{d['Date'].iloc[-1]:%Y-%m-%d}"),
                s1_hits=",".join(hit_days))


_FI_COLS = ("外陸資買賣超股數(不含外資自營商)", "外資買賣超股數")


def _inst_lights(code: str) -> dict:
    """外資/投信 近20日與近5日累計淨買賣超(張)。無檔回 NaN。"""
    out = dict(fi20=np.nan, fi5=np.nan, it20=np.nan, it5=np.nan)
    p = D / "institutional" / f"{code}_inst.csv"
    if not p.exists():
        return out
    try:
        head = pd.read_csv(p, nrows=0).columns
        use = [c for c in (*_FI_COLS, "it_net") if c in head]
        t = pd.read_csv(p, usecols=use).tail(20)
        fi = None
        for col in _FI_COLS:                    # 上市/上櫃欄名不同,擇有值者
            if col in t.columns:
                s = pd.to_numeric(t[col], errors="coerce")
                fi = s if fi is None else fi.fillna(s)
        if fi is not None:
            out["fi20"], out["fi5"] = fi.sum() / 1000, fi.tail(5).sum() / 1000
        if "it_net" in t.columns:
            it = pd.to_numeric(t["it_net"], errors="coerce")
            out["it20"], out["it5"] = it.sum() / 1000, it.tail(5).sum() / 1000
    except Exception:
        pass
    return {k: (round(v, 0) if v == v else np.nan) for k, v in out.items()}


def _bigholder_delta() -> pd.DataFrame:
    """400張以上大戶持股比例:最新一週變化 bh1、近4週變化 bh4(pp)。"""
    try:
        b = pd.read_csv(D / "_bigholder_panel.csv").set_index("date").apply(pd.to_numeric, errors="coerce")
        if len(b) < 2:
            return pd.DataFrame()
        last = b.iloc[-1]
        out = pd.DataFrame({"bh1": last - b.iloc[-2], "bh4": last - b.iloc[max(0, len(b) - 5)]}).round(2)
        out.index = out.index.astype(str)
        out.attrs["week"] = str(b.index[-1])
        return out
    except Exception:
        return pd.DataFrame()


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
    memb: dict[str, list[str]] = {}          # 一檔可屬多族群(群聯同時在記憶體與IC設計)
    for g, codes in THEME_GROUPS.items():
        for c in codes:
            memb.setdefault(str(c), []).append(g)
    keep = frozenset(memb)
    rows = []
    for f in glob.glob(str(D / "[1-9]*.TW.csv")) + glob.glob(str(D / "[1-9]*.TWO.csv")):
        r = _scan_one(f, keep=keep)
        if r:
            rows.append(r)
    df = pd.DataFrame(rows)
    df["name"] = df["code"].map(stock_name)
    df["group"] = df["code"].map(lambda c: "|".join(memb.get(c, []))).replace("", "(未分組)")
    # 多方素材:收復狀態+營收
    rec = _recovery_join()
    if not rec.empty:
        df = df.merge(rec, on="code", how="left")
    else:
        for col in ("retrace", "full", "flush"):
            df[col] = np.nan
    df["rev_yoy"] = df["code"].map(_rev_map())
    df["bull_cand"] = ((df["rev_yoy"] > 30) & (df["flush"] < -10) & (df["full"] != True)  # noqa: E712
                       & df["liquid"])

    # 三燈素材(全部都算:候補要「乾淨」才成立,未分組的也得驗法人):外資・投信=法人日檔;大戶=集保週 panel
    lights = pd.DataFrame([{"code": c, **_inst_lights(c)} for c in df["code"]])
    df = df.merge(lights, on="code", how="left")
    bh = _bigholder_delta()
    df["bh1"] = df["code"].map(bh["bh1"]) if len(bh) else np.nan
    df["bh4"] = df["code"].map(bh["bh4"]) if len(bh) else np.nan
    df["big_run"] = df["bh1"] <= -1.0                       # 大戶週報既有門檻:週減 ≥1pp
    df["inst20"] = df[["fi20", "it20"]].sum(axis=1, min_count=1)   # 兩者皆無資料=NaN,不進比例分母
    df["inst_dual_sell"] = (df["fi5"] < 0) & (df["it5"] < 0)
    df["trap"] = df["margin_mult"] > 3
    df["vol_black"] = (df["vol_mult"] > 2) & df["black"]
    # 避開=籌碼行為面的硬傷。破季線不算:未收復的股票幾乎必然在季線下,
    # 算進去會讓「避開」與「候補」永遠同時出現(2026-11-12 使用者指正:避開跟候補一起?)
    df["avoid_n"] = (df["trap"].astype(int) + df["vol_black"].astype(int)
                     + df["inst_dual_sell"].astype(int))
    # 乾淨候補:營收因子成立,且無任何避開理由、大戶沒在跑——兩個標籤互斥
    df["bull_ok"] = df["bull_cand"] & (df["avoid_n"] == 0) & ~df["big_run"]
    df["up"] = df["chg1"] > 0
    df.sort_values(["s1_today", "bull_ok", "chg5"], ascending=False).to_csv(
        S_CSV, index=False, encoding="utf-8-sig")

    gd = df[df["group"] != "(未分組)"].copy()
    gd["group"] = gd["group"].str.split("|")
    gd = gd.explode("group")
    agg = gd.groupby("group").agg(
        檔數=("code", "count"),
        收復率=("full", "mean"),
        營收加速檔=("bull_ok", "sum"),
        破MA60比=("below_ma60", "mean"),
        套牢倍數中位=("margin_mult", "median"),
        今日收黑比=("black", "mean"),
        五日中位=("chg5", "median"),
        S1命中=("s1_today", "sum"),
        上漲檔=("up", "sum"),
        r20中位=("r20", "median"),
        r20_d1=("r20_d1", "median"),
        r20_d5=("r20_d5", "median"),
        大戶跑比=("big_run", "mean"),
        大戶增比=("bh4", lambda s: (s.dropna() > 0).mean() if s.notna().any() else 0.0),
        法人賣比=("inst20", lambda s: (s.dropna() < 0).mean() if s.notna().any() else 0.0),
        法人買比=("inst20", lambda s: (s.dropna() > 0).mean() if s.notna().any() else 0.0),
    ).round(2)
    # 20日排名與升降(正=名次進步);徽章=法人+大戶同向的族群級證據
    agg["排名20"] = agg["r20中位"].rank(ascending=False, method="min").astype(int)
    agg["昨升降"] = (agg["r20_d1"].rank(ascending=False, method="min") - agg["排名20"]).astype(int)
    agg["五日升降"] = (agg["r20_d5"].rank(ascending=False, method="min") - agg["排名20"]).astype(int)
    # 疑似出貨=過半成分大戶週減≥1pp,且法人沒有明顯在接(20日買超檔數不到六成)
    agg["徽章"] = np.where((agg["大戶跑比"] >= 0.5) & (agg["法人買比"] < 0.6), "疑似出貨",
                         np.where((agg["法人買比"] >= 0.6) & (agg["大戶增比"] >= 0.5), "吸籌中", ""))
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
                bulls=int(df["bull_ok"].sum()), asof=df["date"].max() if len(df) else "")


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

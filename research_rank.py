# -*- coding: utf-8 -*-
"""
research_rank.py — 研究名單總排名(我們自己的「M哥指數」)
=================================================================
起因(2026-10-23):「我們找那麼多,應該也要有排名」——所有寫過財經報/快析的
標的,用系統已驗證的維度自動打分、每天重排,研究不再是散落的單篇。
維度(全部來自既有管線,百分位計分後加權):
  ①營收動能(YoY 3月平滑+加速度)     ②獲利品質(毛利率趨勢+營益率,業外≥40%腰斬)
  ③籌碼(外資20日買超天+大戶4週變化)  ④位置(距年高+站60MA)
  ⑤家規扣分(處置/爆量窗/融資≥30%/迴轉率警戒)
產出:data/_research_rank.csv;頁33 頂部排行榜。
名單來源:data/papers/*.html 的代碼 ∪ EXTRAS(快析過的)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"

# 快析過但沒出報的(手動維護;出過報的自動從 papers 抓)
EXTRAS = ["6141", "6202", "4919", "1569", "6609", "3287", "6505", "1314",
          "9933", "1513", "1609", "1605", "2330", "3081", "3234", "6672", "1815"]


def universe() -> list[str]:
    codes = {p.name.split("_")[0] for p in (D / "papers").glob("*.html")}
    codes |= set(EXTRAS)
    return sorted(c for c in codes if c.isdigit() and len(c) == 4)


def _one(code: str, rev: pd.DataFrame, q: pd.DataFrame) -> dict | None:
    import symbols
    row = {"代碼": code}
    try:
        row["名稱"] = symbols.resolve(code)[1] or ""
    except Exception:
        row["名稱"] = ""
    # 價格/位置
    px = None
    for suf in (".TW.csv", ".TWO.csv"):
        p = D / f"{code}{suf}"
        if p.exists():
            px = pd.read_csv(p).dropna(subset=["Close"])
            break
    if px is None or len(px) < 80:
        return None
    c, v = px["Close"].astype(float), px["Volume"].astype(float)
    row["收盤"] = round(c.iloc[-1], 1)
    row["距年高%"] = round((c.iloc[-1] / c.tail(250).max() - 1) * 100, 1)
    row["60日%"] = round((c.iloc[-1] / c.iloc[-61] - 1) * 100, 1)
    row["站60MA"] = c.iloc[-1] > c.tail(60).mean()
    # 營收動能
    r = rev[rev.code == code].tail(6)
    if len(r) >= 6:
        y3 = r["yoy%"].tail(3).mean()
        row["營收YoY3"] = round(y3, 1)
        row["加速度"] = round(y3 - r["yoy%"].head(3).mean(), 1)
    # 獲利品質
    qq = q[q.code == code].tail(4)
    if len(qq) >= 2:
        row["毛利率"] = round(qq["毛利率%"].iloc[-1], 1)
        row["毛利率Δ"] = round(qq["毛利率%"].iloc[-1] - qq["毛利率%"].iloc[-2], 1)
        row["營益率"] = round(qq["營益率%"].iloc[-1], 1)
        ni, op = qq["淨利率%"].iloc[-1], qq["營益率%"].iloc[-1]
        row["業外重"] = bool(pd.notna(ni) and ni > 0 and op / ni < 0.6)
    # 籌碼
    ip = D / "institutional" / f"{code}_inst.csv"
    if ip.exists():
        d2 = pd.read_csv(ip)
        fi = pd.to_numeric(d2.iloc[:, 4], errors="coerce").dropna()
        row["外資天"] = int((fi.tail(20) > 0).sum())
    tp = D / "tdcc" / f"{code}_tdcc.csv"
    if tp.exists():
        try:
            td = pd.read_csv(tp)
            big = td[td.level >= 12].groupby("date")["pct"].sum()
            if len(big) >= 5:
                row["大戶4週Δ"] = round(big.iloc[-1] - big.iloc[-5], 2)
                row["大戶%"] = round(big.iloc[-1], 1)
        except Exception:
            pass
    # 家規扣分
    try:
        import forecast_card as FCX
        fl = FCX.flags(code)
        row["爆量窗"] = bool(fl.get("爆量窗"))
        row["處置"] = bool(fl.get("處置中"))
        row["迴轉警"] = bool(fl.get("迴轉率警戒"))
    except Exception:
        pass
    try:
        import margin_stress
        mr = margin_stress.build(code, days=40)
        row["融資%"] = mr["cards"]["融資使用率%"] if mr else None
    except Exception:
        row["融資%"] = None
    return row


def build() -> pd.DataFrame:
    rev = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    rows = [r for c in universe() if (r := _one(c, rev, q))]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # 百分位計分
    def pct(col, asc=True):
        s = df[col].astype(float)
        return (s.rank(pct=True, ascending=asc) * 100).fillna(50)
    s_rev = (pct("營收YoY3") + pct("加速度")) / 2 if "營收YoY3" in df else 50
    s_prof = (pct("毛利率Δ") + pct("營益率")) / 2
    s_prof = s_prof.where(~df.get("業外重", False), s_prof * 0.5)       # 業外重→腰斬
    s_chip = (pct("外資天") + pct("大戶4週Δ")) / 2
    s_pos = (pct("距年高%") + df["站60MA"].astype(int) * 100) / 2
    df["營收分"] = s_rev.round(0)
    df["獲利分"] = s_prof.round(0)
    df["籌碼分"] = s_chip.round(0)
    df["位置分"] = s_pos.round(0)
    pen = (df.get("處置", False).astype(int) * 10 + df.get("爆量窗", False).astype(int) * 8
           + df.get("迴轉警", False).astype(int) * 5
           + (pd.to_numeric(df.get("融資%"), errors="coerce").fillna(0) >= 30).astype(int) * 8)
    df["扣分"] = pen
    df["總分"] = (s_rev * .3 + s_prof * .3 + s_chip * .25 + s_pos * .15 - pen).round(1)
    df = df.sort_values("總分", ascending=False).reset_index(drop=True)
    df.insert(0, "排名", df.index + 1)
    df.to_csv(D / "_research_rank.csv", index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    d = build()
    cols = ["排名", "代碼", "名稱", "總分", "營收分", "獲利分", "籌碼分", "位置分", "扣分",
            "營收YoY3", "毛利率", "營益率", "外資天", "大戶4週Δ", "距年高%", "融資%"]
    print(d[[c for c in cols if c in d.columns]].to_string(index=False))

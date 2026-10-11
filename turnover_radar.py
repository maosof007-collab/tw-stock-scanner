# -*- coding: utf-8 -*-
"""
turnover_radar.py — 迴轉率雷達(高迴轉榜+隔日沖行為指紋)
=================================================================
起因(2026-10-11):「整理每天高迴轉率股票,列出隔日沖的股票」。
迴轉率 = 當日成交股數 ÷ 集保總股數(TDCC 最新週加總=流通股數,現成資料)。
隔日沖沒有免費逐筆分點 → 用行為指紋(標註為近似):
  🔪 警戒(今日被鎖):漲幅≥8% + 量比≥2.5 + 迴轉率入榜 → 明日有隔日沖賣壓窗
  🩸 昨鎖今倒(事後確認):昨日符合警戒條件 + 今日收跌 → 出貨完成教材
單檔驗證:fetch_branch_days() 抓富邦DJ分點兩日對比,看「昨大買今大賣」的指紋。
家規對接:這頁就是「爆量日+2~3天禁入」的自動名單產生器。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
OUT = D / "_turnover.csv"


def _shares(code: str) -> float | None:
    p = D / "tdcc" / f"{code}_tdcc.csv"
    if not p.exists():
        return None
    try:
        t = pd.read_csv(p)
        w = t[t["date"] == t["date"].max()]
        s = float(w["shares"].sum())
        return s if s > 1e6 else None
    except Exception:
        return None


def scan(min_amount: float = 3e8, top: int = 40) -> pd.DataFrame:
    import glob
    import os
    import symbols
    rows = []
    for f in glob.glob(str(D / "[0-9]*.csv")):
        code = os.path.basename(f).split(".")[0]
        if len(code) != 4:
            continue
        try:
            px = pd.read_csv(f, usecols=["Date", "Close", "Open", "High", "Low", "Volume"]).dropna()
            if len(px) < 25:
                continue
            c = px["Close"].astype(float)
            v = px["Volume"].astype(float)
            amt = v.iloc[-1] * c.iloc[-1]
            if amt < min_amount:
                continue
            sh = _shares(code)
            if not sh:
                continue
            turn = v.iloc[-1] / sh * 100
            v20 = v.iloc[-21:-1].mean()
            vr = v.iloc[-1] / v20 if v20 > 0 else None
            chg = (c.iloc[-1] / c.iloc[-2] - 1) * 100
            chg_y = (c.iloc[-2] / c.iloc[-3] - 1) * 100
            v20_y = v.iloc[-22:-2].mean()
            vr_y = v.iloc[-2] / v20_y if v20_y > 0 else 0
            flag = ""
            if chg >= 8 and (vr or 0) >= 2.5:
                flag = "🔪 警戒:今日鎖量,明日賣壓窗"
            if chg_y >= 8 and vr_y >= 2.5 and chg < 0:
                flag = "🩸 昨鎖今倒(出貨完成)"
            rows.append({"代碼": code, "日期": px["Date"].iloc[-1],
                         "收盤": round(c.iloc[-1], 2), "漲跌%": round(chg, 2),
                         "迴轉率%": round(turn, 2), "量比": round(vr, 2) if vr else None,
                         "成交額(億)": round(amt / 1e8, 2), "隔日沖指紋": flag})
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    hot = df.sort_values("迴轉率%", ascending=False).head(top)
    flagged = df[df["隔日沖指紋"] != ""]
    out = (pd.concat([hot, flagged], ignore_index=True)
             .drop_duplicates(subset=["代碼"])
             .sort_values("迴轉率%", ascending=False))
    out["名稱"] = out["代碼"].map(lambda x: symbols.resolve(x)[1] or "")
    cols = ["代碼", "名稱"] + [c for c in out.columns if c not in ("代碼", "名稱")]
    out = out[cols]
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    return out


def fetch_branch_days(code: str, d1: str, d2: str) -> pd.DataFrame:
    """富邦DJ 分點買賣超,單日查詢×2 → 「昨買超前15在今日的動作」對比(隔日沖驗證)。
    d1/d2 格式 2026-10-9。回傳昨日買超榜+今日該分點買賣超。"""
    import requests
    from bs4 import BeautifulSoup

    def one(day):
        url = f"http://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco.djhtm?a={code}&e={day}&f={day}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(r.content.decode("big5", errors="replace"), "html.parser")
        for s in soup(["script", "style"]):
            s.decompose()
        t = max(soup.find_all("table"), key=lambda x: len(x.find_all("tr")))
        buy, sell = {}, {}
        for tr in t.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) >= 10 and cells[0] and "券商" not in cells[0]:
                try:
                    buy[cells[0]] = float(cells[3].replace(",", ""))
                    sell[cells[5]] = float(cells[8].replace(",", ""))
                except Exception:
                    continue
        return buy, sell

    b1, _ = one(d1)
    b2, s2 = one(d2)
    rows = []
    for br, lots in sorted(b1.items(), key=lambda x: -x[1])[:15]:
        today = -s2.get(br, 0) if br in s2 else b2.get(br, 0)
        verdict = "🩸 隔日沖指紋" if br in s2 and s2[br] >= lots * 0.6 else (
            "✅ 續抱/加碼" if today >= 0 else "部分調節")
        rows.append({"分點": br, f"{d1}買超": lots, f"{d2}動作": today, "判定": verdict})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = scan()
    print(df.head(20).to_string(index=False))
    print("flagged:", (df["隔日沖指紋"] != "").sum())

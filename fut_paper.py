# -*- coding: utf-8 -*-
"""
fut_paper.py — 微台模擬倉(paper trading;期交所真實行情+保證金)
=================================================================
起因(2026-10-27):「期貨教室順便綁進來,開始要做微台」。
資料:期交所 OpenAPI DailyMarketReportFut(TMF 行情)+ IndexFuturesAndOptionsMargining
     (保證金,動態抓——期貨 primer 教案:寫死的保證金數字半年就過期)。
規則:微台 1 點=10 元;損益=(現值-進場)×10×口數(空單反向)。
紀律(與 op_paper/體檢卡同源):
  開倉必填「論點+停損點數」——說不出觀點、算不出風險就不准開
  風險燈 🔴 → 禁開多單(模擬倉也擋,練的就是紀律);空單放行但附警語
倉單:data/fut_paper.csv。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
PAPER = ROOT / "data" / "fut_paper.csv"
FUT_DIR = ROOT / "data" / "fut"
FUT_DIR.mkdir(exist_ok=True)
POINT = 10          # 微台 1 點 = 10 元


def _api(ep: str) -> list[dict]:
    req = urllib.request.Request(f"https://openapi.taifex.com.tw/v1/{ep}",
                                 headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def margin() -> dict | None:
    """微台三級保證金(動態)。"""
    try:
        for r in _api("IndexFuturesAndOptionsMargining"):
            if r.get("Contract") == "微型臺指期貨":
                return {"原始": int(r["InitialMargin"]), "維持": int(r["MaintenanceMargin"]),
                        "結算": int(r["ClearingMargin"]), "日期": r.get("Date", "")}
    except Exception:
        pass
    return None


def quote() -> dict | None:
    """TMF 近月:一般盤結算+最新成交(含盤後)。快取當日。"""
    try:
        rows = [r for r in _api("DailyMarketReportFut") if r.get("Contract") == "TMF"]
        if not rows:
            return None
        pd.DataFrame(rows).to_csv(FUT_DIR / f"tmf_{now_tw():%Y%m%d}.csv",
                                  index=False, encoding="utf-8-sig")
        months = sorted({r["ContractMonth(Week)"] for r in rows
                         if r["ContractMonth(Week)"].isdigit()})
        near = months[0]
        day = next((r for r in rows if r["ContractMonth(Week)"] == near
                    and r.get("TradingSession") == "一般"), None)
        night = next((r for r in rows if r["ContractMonth(Week)"] == near
                      and r.get("TradingSession") == "盤後"), None)
        last = night if (night and str(night.get("Last", "")).replace("-", "").isdigit()) else day
        return {"月份": near, "日期": (day or last).get("Date", ""),
                "結算": float(day["SettlementPrice"]) if day and day.get("SettlementPrice", "NULL") != "NULL" else None,
                "最新": float(last["Last"]) if last and str(last.get("Last", "")).lstrip("-").isdigit() else None,
                "漲跌%": (last or {}).get("%", ""), "OI": (day or {}).get("OpenInterest", ""),
                "時段": (last or {}).get("TradingSession", "")}
    except Exception:
        return None


def load() -> pd.DataFrame:
    if PAPER.exists():
        return pd.read_csv(PAPER)
    return pd.DataFrame(columns=["開倉日", "方向", "口數", "進場價", "停損點", "論點",
                                 "狀態", "平倉日", "平倉價", "損益元", "R"])


def _save(df: pd.DataFrame) -> None:
    df.to_csv(PAPER, index=False, encoding="utf-8-sig")


def open_pos(side: str, lots: int, px: float, stop_pts: float, thesis: str) -> str:
    """開倉。side=多|空;家規:🔴禁多單;必填論點+停損。"""
    if not thesis.strip():
        return "⛔ 沒有論點不准開倉(家規:說不出觀點=沒有交易)"
    if stop_pts <= 0:
        return "⛔ 停損點數必填(算不出風險=沒有交易)"
    if side == "多":
        try:
            lamp = json.loads((ROOT / "data" / "_market_risk.json").read_text(encoding="utf-8"))["lamp"]
            if lamp == "🔴":
                return "⛔ 風險燈 🔴 禁開新多單——模擬倉也一樣,練的就是這個"
        except Exception:
            pass
    df = load()
    df.loc[len(df)] = [f"{now_tw():%Y-%m-%d %H:%M}", side, lots, px, stop_pts,
                       thesis.strip(), "持倉", "", None, None, None]
    _save(df)
    risk = stop_pts * POINT * lots
    return f"✅ 開{side} {lots} 口 @{px:,.0f}|停損 {stop_pts:.0f} 點=風險 {risk:,.0f} 元"


def close_pos(idx: int, px: float) -> str:
    df = load()
    if idx not in df.index or df.loc[idx, "狀態"] != "持倉":
        return "找不到持倉"
    r = df.loc[idx]
    sgn = 1 if r["方向"] == "多" else -1
    pnl = (px - float(r["進場價"])) * sgn * POINT * int(r["口數"])
    risk = float(r["停損點"]) * POINT * int(r["口數"])
    df.loc[idx, ["狀態", "平倉日", "平倉價", "損益元", "R"]] = \
        ["平倉", f"{now_tw():%Y-%m-%d %H:%M}", px, round(pnl), round(pnl / risk, 2) if risk else None]
    _save(df)
    return f"✅ 平倉 @{px:,.0f}|損益 {pnl:+,.0f} 元({pnl/risk:+.2f}R)"


def mark(df: pd.DataFrame, last: float | None) -> pd.DataFrame:
    """未平倉以最新價洗損益。"""
    out = df.copy()
    if last:
        m = out["狀態"] == "持倉"
        sgn = out.loc[m, "方向"].map({"多": 1, "空": -1})
        out.loc[m, "損益元"] = ((last - out.loc[m, "進場價"].astype(float))
                               * sgn * POINT * out.loc[m, "口數"].astype(int)).round()
    return out


if __name__ == "__main__":
    print("保證金:", margin())
    print("行情:", quote())

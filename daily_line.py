# -*- coding: utf-8 -*-
"""
daily_line.py — 日報手機版:一屏讀完的 LINE 摘要(run_daily 跑完自動推)
=================================================================
起因(2026-10-18):「把日報用成手機好讀方式傳到 LINE」。
設計:不是把網頁報告塞進手機,是重新編排——短行、無表格、emoji 分節、
     只放「今天要知道+明天要做」,細節留給 App。長度壓 1500 字內(一屏半)。
與 alert_watch 分工:哨兵推「突發變化」(隨時),這支推「每日總結」(收盤後一則)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"


def _risk() -> list[str]:
    try:
        r = json.loads((D / "_market_risk.json").read_text(encoding="utf-8"))
        lines = [f"🚦 風險燈 {r['lamp']}({r['score']}分)|{r.get('rule','')}"]
        lines += [f"・{x}" for x in r.get("reasons", [])[:4]]
        return lines
    except Exception:
        return []


def _market() -> list[str]:
    out = []
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna().tail(2)
        chg = (bm["Close"].iloc[-1] / bm["Close"].iloc[-2] - 1) * 100
        out.append(f"📈 大盤 {bm['Close'].iloc[-1]:,.0f}({chg:+.2f}%)")
    except Exception:
        pass
    row = []
    for fn, nm in (("SOX", "費半"), ("KS11", "KOSPI"), ("TWD", "台幣")):
        try:
            x = pd.read_csv(D / "us" / f"{fn}.csv").dropna()
            c = (x["Close"].iloc[-1] / x["Close"].iloc[-2] - 1) * 100
            row.append(f"{nm}{c:+.1f}%")
        except Exception:
            continue
    if row:
        out.append("🌏 " + "|".join(row))
    return out


def _stops() -> list[str]:
    try:
        import my_etf
        pt = my_etf.positions_table()
        h = pt[pt["⚠"] == "🛑"] if len(pt) else pt
        if len(h):
            items = [f"{r['名稱']}{r['代碼']}(停損{r['停損價']})" for _, r in h.iterrows()]
            return ["🛑 觸停損:" + "、".join(items[:6]), "　→ 家規:跌破就走,不攤平"]
    except Exception:
        pass
    return []


def _quiet() -> list[str]:
    try:
        q = pd.read_csv(D / "_quiet_accum.csv", dtype={"代碼": str}).head(3)
        if len(q):
            items = [f"{r['代碼']}{r['名稱']}(吸籌{r['吸籌比%']}%)" for _, r in q.iterrows()]
            return ["🤫 還沒發動:" + "、".join(items)]
    except Exception:
        pass
    return []


def _turnover() -> list[str]:
    try:
        t = pd.read_csv(D / "_turnover.csv", dtype=str)
        if "標記" not in t.columns:
            return []
        w = t[t["標記"].fillna("").str.contains("🔪")]
        if len(w):
            names = (w["代碼"] + w.get("名稱", "")).head(5).tolist()
            return [f"🔪 迴轉率警戒 {len(w)} 檔:" + "、".join(names) + "(爆量+2~3天禁入)"]
    except Exception:
        pass
    return []


def _concalls() -> list[str]:
    try:
        c = pd.read_csv(D / "_conf_calendar.csv", dtype=str)
        dcol = next((x for x in c.columns if "date" in x.lower() or "日" in x), None)
        if not dcol:
            return []
        tmr = f"{now_tw() + pd.Timedelta(days=1):%Y-%m-%d}"
        today_s = f"{now_tw():%Y-%m-%d}"
        hit = c[c[dcol].isin([today_s, tmr])]
        if len(hit):
            name_c = next((x for x in c.columns if "name" in x.lower() or "名" in x), c.columns[0])
            return [f"🎤 今明法說:" + "、".join(hit[name_c].head(6).tolist())]
    except Exception:
        pass
    return []


def _events() -> list[str]:
    try:
        ev = pd.read_csv(D / "macro_events.csv", dtype=str)
        tmr = f"{now_tw() + pd.Timedelta(days=1):%Y-%m-%d}"
        today_s = f"{now_tw():%Y-%m-%d}"
        hit = ev[ev["date"].isin([today_s, tmr])]
        return [f"📅 {e['date'][5:]} {e['event']}" for _, e in hit.iterrows()][:3]
    except Exception:
        return []


def build_digest() -> str:
    n = now_tw()
    wd = "一二三四五六日"[n.weekday()]
    parts = [f"📰 tw_backtest 日報 {n:%m/%d}(週{wd})"]
    for sec in (_risk(), _market(), _stops(), _turnover(), _quiet(),
                _concalls(), _events()):
        if sec:
            parts.append("")
            parts.extend(sec)
    parts += ["", "細節開 App:風險燈/體檢卡/今日選股"]
    txt = "\n".join(parts)
    return txt[:3800]


def push(force: bool = False) -> str:
    """一天最多推一則(哨兵推突發,這支推總結)。"""
    mark = D / "_daily_line_sent.txt"
    today_s = f"{now_tw():%Y-%m-%d}"
    if not force and mark.exists() and mark.read_text() == today_s:
        return "今日日報已推過,跳過"
    txt = build_digest()
    try:
        import line_push
        if not line_push.enabled():
            return "LINE 未設定"
        r = line_push.push_text(txt)
        if "成功" in r:
            mark.write_text(today_s)
        return r
    except Exception as e:
        return f"例外:{type(e).__name__}"


if __name__ == "__main__":
    print(build_digest())
    print("---")
    print(push(force=True))

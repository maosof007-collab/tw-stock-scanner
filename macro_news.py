# -*- coding: utf-8 -*-
"""
macro_news.py — 鉅亨總經/國際頭條(2026-10-15)
=================================================================
起因:10/15 風暴日四篇關鍵新聞(CPI爆/CoreWeave股債雙殺/資本配給/台積法說)
全靠使用者手動轉貼——產業新聞掃描(fetch_sector_news)不收總經。
本模組:cnyes 公開 API(headline+國際股)→ 風險關鍵詞標記 → data/_macro_news.json
→ 駕駛艙「今日戰報」引用。run_daily 每日抓。
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "_macro_news.json"
_H = {"User-Agent": "Mozilla/5.0"}
_RISK_KW = ["CPI", "PPI", "聯準會", "Fed", "升息", "降息", "殖利率", "債", "違約",
            "韓股", "KOSPI", "暴跌", "重挫", "崩", "斷頭", "融資", "資本支出",
            "台積", "輝達", "NVIDIA", "記憶體", "關稅", "匯率", "日圓", "美元"]


def fetch(limit: int = 12) -> list[dict]:
    items, seen = [], set()
    for cat in ("headline", "wd_stock"):
        try:
            r = requests.get(
                f"https://api.cnyes.com/media/api/v1/newslist/category/{cat}?limit={limit}",
                headers=_H, timeout=20)
            for it in r.json().get("items", {}).get("data", []):
                nid = it.get("newsId")
                if not nid or nid in seen:
                    continue
                seen.add(nid)
                title = it.get("title", "")
                items.append({
                    "id": nid, "title": title,
                    "time": it.get("publishAt"),
                    "url": f"https://news.cnyes.com/news/id/{nid}",
                    "cat": cat,
                    "risk": any(k in title for k in _RISK_KW)})
        except Exception:
            continue
    items.sort(key=lambda x: x.get("time") or 0, reverse=True)
    out = items[:18]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load() -> list[dict]:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


if __name__ == "__main__":
    for it in fetch():
        print(("⚠️ " if it["risk"] else "   ") + it["title"][:60])

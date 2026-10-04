# -*- coding: utf-8 -*-
"""
advisory_hub.py — 旺來台股情報站 投顧觀點彙整 ingester
=================================================================
起因(2026-10-04):「我沒投顧報告」的解方之一——daily-tw.up.railway.app 收錄
222+ 檔個股的券商觀點摘要(依公開新聞整理,每份標來源),一檔一資料夾累積。
本模組:stocks.json 索引 → 增量抓「觀點彙整.html」→ 萃取純文字存庫 →
快分析/財經報自動引用(與 concall、report_inbox 同一素材地位)。
注意:該站為摘要非券商原始報告;引用時素材層級標「公開新聞整理」。
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DIR = ROOT / "data" / "advisory"
DIR.mkdir(parents=True, exist_ok=True)
BASE = "https://daily-tw.up.railway.app"
_H = {"User-Agent": "Mozilla/5.0"}


def fetch_index() -> list[dict]:
    r = requests.get(f"{BASE}/stocks.json", headers=_H, timeout=30)
    r.raise_for_status()
    stocks = r.json().get("stocks", [])
    (DIR / "_index.json").write_text(json.dumps(stocks, ensure_ascii=False), encoding="utf-8")
    return stocks


def _clean(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    txt = re.sub(r"<[^>]+>", "\n", html)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
    # 正文從警語起算,掐掉頁頭導覽與 JS 殘渣;再砍殘留的 js 樣式行
    i = txt.find("⚠")
    if i > 0:
        txt = txt[i:]
    lines = [ln for ln in txt.splitlines()
             if "history.back" not in ln and not re.match(r"^[\s{}();>\"']*$", ln)]
    return "\n".join(lines)


def fetch_one(stock: dict) -> Path | None:
    """抓一檔的觀點彙整(rec 日期沒變就跳過)。"""
    code, folder, rec = stock.get("code"), stock.get("folder"), stock.get("rec", "")
    if not code or not folder:
        return None
    out = DIR / f"{code}.txt"
    meta = DIR / f"{code}.rec"
    if out.exists() and meta.exists() and meta.read_text() == rec:
        return out
    url = f"{BASE}/" + urllib.parse.quote(f"個股/{folder}/觀點彙整.html")
    try:
        r = requests.get(url, headers=_H, timeout=30)
        if r.status_code != 200 or len(r.text) < 500:
            return None
        out.write_text(_clean(r.text), encoding="utf-8")
        meta.write_text(rec)
        return out
    except Exception:
        return None


def refresh(codes: list[str] | None = None, sleep: float = 0.5) -> int:
    """增量更新:codes=None 時只抓追蹤股∩站上有的;傳清單則抓指定。"""
    stocks = fetch_index()
    by_code = {s["code"]: s for s in stocks if s.get("code")}
    if codes is None:
        try:
            from fundamentals import tracked_codes
            codes = [c for c in tracked_codes() if c in by_code]
        except Exception:
            codes = list(by_code)[:50]
    n = 0
    for c in codes:
        s = by_code.get(c)
        if not s:
            continue
        before = (DIR / f"{c}.rec").read_text() if (DIR / f"{c}.rec").exists() else ""
        p = fetch_one(s)
        if p and s.get("rec", "") != before:
            n += 1
        time.sleep(sleep)
    return n


def latest_text(code: str, cap: int = 6000) -> str:
    """快分析素材接口:該檔投顧觀點彙整純文字(含來源日期標註)。"""
    p = DIR / f"{code}.txt"
    if not p.exists():
        idx = DIR / "_index.json"
        if idx.exists():
            by = {s["code"]: s for s in json.loads(idx.read_text(encoding="utf-8"))
                  if s.get("code")}
            if code in by:
                fetch_one(by[code])
    if not p.exists():
        return ""
    t = p.read_text(encoding="utf-8")
    return f"(投顧觀點彙整|公開新聞整理,非原始報告)\n{t[:cap]}"


def coverage() -> list[str]:
    idx = DIR / "_index.json"
    if not idx.exists():
        return []
    return sorted(s["code"] for s in json.loads(idx.read_text(encoding="utf-8"))
                  if s.get("code"))


if __name__ == "__main__":
    print("index:", len(fetch_index()), "檔")
    print("refreshed:", refresh())

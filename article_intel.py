"""
article_intel.py — 新聞文章解讀（貼網址 → 個股情報卡）
=================================================================
把訂閱電子報/財經網站的深度文章（優分析 uanalyze、鉅亨、財訊…）
變成結構化的「個股情報卡」：

  fetch_article(url)      抓標題+全文（SPA 網站多半仍有 SSR 內文，
                          用「最大文字容器」啟發式，通吃多數新聞站）
  analyze_article(...)    有 ANTHROPIC_API_KEY → Claude 解析出
                          個股/族群/多空/論點/關鍵數字/風險（嚴格 JSON）
                          沒 key → 離線退化版：股名比對 + 詞典情緒
  save/load_articles      存 data/news/articles/*.json，新聞分析頁展示
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
DATA = ROOT / "data"
ART_DIR = DATA / "news" / "articles"
ART_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")}


# ────────────────────────────────────────
# 抓文章
# ────────────────────────────────────────
def fetch_article(url: str) -> dict | None:
    """回傳 {url, title, text, source}；抓不到回 None。"""
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        s = BeautifulSoup(r.text, "lxml")
        for bad in s.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            bad.decompose()
        h1 = s.find("h1")
        title = h1.get_text(strip=True) if h1 else (s.title.get_text(strip=True) if s.title else url)
        # 內文容器＝「純文字多、連結文字少」的節點（readability 啟發式，
        # 避免把側欄相關文章/選單的股名一起吃進來）
        def score(node):
            total = len(node.get_text(strip=True))
            linked = sum(len(a.get_text(strip=True)) for a in node.find_all("a"))
            return total - 2 * linked
        cands = s.find_all(["article", "div", "section"])
        best = max(cands, key=score) if cands else s
        for a in best.find_all("a"):        # 內文裡殘餘連結（延伸閱讀）也拿掉
            a.decompose()
        text = best.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) < 150:
            return None
        source = re.sub(r"^www\.", "", requests.utils.urlparse(url).netloc)
        return {"url": url, "title": title, "text": text[:12000], "source": source}
    except Exception:
        return None


# ────────────────────────────────────────
# 解析（Claude 優先，離線退化）
# ────────────────────────────────────────
_SYS = """你是台股產業分析師。把財經文章解析成嚴格 JSON（不加任何其他文字）：
{
  "one_liner": "一句話講這篇文章對投資人的重點",
  "stocks": [
    {"code": "4位數台股代碼(文中明確提到才填)", "name": "股名",
     "stance": "bull|bear|neutral", "score": -1.0到1.0,
     "summary": "這檔的一句話結論",
     "key_points": ["論點1", "論點2"],
     "numbers": ["關鍵數字1(如 營收28.22億 年增13%)"],
     "risks": ["風險或保留點"]}
  ],
  "groups": ["相關概念族群，如 液冷散熱、人形機器人、矽晶圓"],
  "catalysts": ["後續催化劑/時間點"]
}
規則：只寫文中有依據的內容；stance 依文章語氣判斷；沒提到個股就 stocks 給空陣列。"""


def _get_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        cfg = ROOT / "config.json"
        if cfg.exists():
            try:
                key = json.loads(cfg.read_text(encoding="utf-8")).get("anthropic_api_key", "")
            except Exception:
                pass
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def analyze_article(art: dict) -> dict:
    """回傳解讀結果（含 engine 欄標明 claude / offline）。"""
    key = _get_key()
    if key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=1600,
                system=[{"type": "text", "text": _SYS, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user",
                           "content": f"標題：{art['title']}\n\n{art['text'][:9000]}"}],
            )
            raw = "".join(b.text for b in msg.content if b.type == "text").strip()
            raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
            parsed = json.loads(raw)
            parsed["engine"] = "claude"
            return parsed
        except Exception:
            pass
    return _offline_analyze(art)


def _offline_analyze(art: dict) -> dict:
    """無 API key 的退化版：股名比對 + 詞典情緒。"""
    from news_trend import POS_WORDS, NEG_WORDS
    text = art["title"] + " " + art["text"]
    stocks = []
    try:
        sl = pd.read_csv(DATA / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        seg_pos = sum(text.count(w) for w in POS_WORDS)
        seg_neg = sum(text.count(w) for w in NEG_WORDS)
        stance = "bull" if seg_pos > seg_neg else ("bear" if seg_neg > seg_pos else "neutral")
        for _, r in sl.dropna(subset=["name"]).iterrows():
            nm, code = str(r["name"]).strip(), str(r["code"]).strip()
            if len(nm) < 2 or nm not in text:
                continue
            # 防誤抓（如「三大成長」抓到大成）：股名+代碼同見，或股名出現≥3次
            if not (code in text or text.count(nm) >= 3):
                continue
            stocks.append({"code": code, "name": nm, "stance": stance,
                           "score": 0.0, "summary": "（離線模式：僅偵測到文中提及）",
                           "key_points": [], "numbers": [], "risks": []})
    except Exception:
        pass
    return {"one_liner": art["title"], "stocks": stocks[:10], "groups": [],
            "catalysts": [], "engine": "offline"}


# ────────────────────────────────────────
# 存取
# ────────────────────────────────────────
def ingest(url: str) -> dict | None:
    """抓 + 解析 + 存檔，回傳完整紀錄。同網址重複解讀會覆蓋舊檔。"""
    art = fetch_article(url)
    if art is None:
        return None
    parsed = analyze_article(art)
    rec = {**art, **parsed, "ingested_at": now_tw().strftime("%Y-%m-%d %H:%M")}
    rec.pop("text", None)                      # 全文不落地，省空間
    h = hashlib.md5(url.encode()).hexdigest()[:10]
    out = ART_DIR / f"article_{h}.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def load_articles(limit: int = 30) -> list[dict]:
    files = sorted(ART_DIR.glob("article_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("用法: python article_intel.py <文章網址>")
        sys.exit(1)
    rec = ingest(sys.argv[1])
    print(json.dumps(rec, ensure_ascii=False, indent=1) if rec else "抓取失敗")

"""
fetch_news.py — 台灣財經新聞抓取器
抓取多個台灣財經新聞來源，存入 data/news/ 目錄

來源：
  - Yahoo奇摩財經 RSS
  - Google News RSS（關鍵字搜尋）
  - 鉅亨網 RSS
  - 公開資訊觀測站重大訊息（MOPS）

執行：
  python fetch_news.py                    # 抓最新新聞
  python fetch_news.py --ticker 2330      # 只抓特定股票新聞
  python fetch_news.py --days 3          # 抓最近3天
"""

import sys, re, time, json, logging, hashlib, argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
import pandas as pd

DATA_DIR = Path("data")
NEWS_DIR  = DATA_DIR / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 新聞來源
# ════════════════════════════════════════

def fetch_yahoo_finance_rss(query: str = "台股") -> list[dict]:
    """Yahoo奇摩財經 RSS"""
    items = []
    url = f"https://tw.news.yahoo.com/rss/?q={quote(query)}&l=zh-TW&t=mn&st=rt"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        root = ET.fromstring(r.content)
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            if title:
                items.append({
                    "source": "Yahoo財經",
                    "title":  title,
                    "url":    link,
                    "summary": _clean_html(desc)[:200],
                    "published": _parse_date(pub),
                    "query":  query,
                })
    except Exception as e:
        log.warning(f"Yahoo RSS 抓取失敗 ({query}): {e}")
    return items


def fetch_google_news_rss(query: str) -> list[dict]:
    """Google News RSS"""
    items = []
    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        root = ET.fromstring(r.content)
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            source_el = item.find("{https://news.google.com/rss}source")
            src_name  = source_el.text if source_el is not None else "Google News"
            if title:
                items.append({
                    "source":    src_name,
                    "title":     title,
                    "url":       link,
                    "summary":   "",
                    "published": _parse_date(pub),
                    "query":     query,
                })
    except Exception as e:
        log.warning(f"Google News RSS 抓取失敗 ({query}): {e}")
    return items


def fetch_cnyes_rss() -> list[dict]:
    """鉅亨網財經 RSS"""
    items = []
    feeds = [
        ("https://feeds.cnyes.com/feed/news/tw_stock", "鉅亨-台股"),
        ("https://feeds.cnyes.com/feed/news/headline",  "鉅亨-頭條"),
    ]
    for url, src in feeds:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link  = item.findtext("link", "").strip()
                desc  = item.findtext("description", "").strip()
                pub   = item.findtext("pubDate", "").strip()
                if title:
                    items.append({
                        "source":    src,
                        "title":     title,
                        "url":       link,
                        "summary":   _clean_html(desc)[:200],
                        "published": _parse_date(pub),
                        "query":     "台股",
                    })
        except Exception as e:
            log.warning(f"鉅亨 RSS 抓取失敗 ({src}): {e}")
    return items


def fetch_mops_announcements(stock_codes: list[str] = None) -> list[dict]:
    """
    公開資訊觀測站重大訊息
    https://mops.twse.com.tw/mops/web/t05sr01_1
    """
    items = []
    today = datetime.today()
    date_str = today.strftime("%Y%m%d")

    url = "https://mops.twse.com.tw/mops/web/ajax_t05sr01_1"
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": "all",
        "year": str(today.year - 1911),  # 民國年
        "month": today.strftime("%m"),
        "day": today.strftime("%d"),
        "keyword": "",
    }
    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        # 簡單解析 HTML 表格中的股號和標題
        pattern = re.compile(r'(\d{4})\s*[一-鿿]+.*?<td[^>]*>(.*?)</td>', re.DOTALL)
        for m in pattern.finditer(r.text[:50000]):  # 只看前 5 萬字
            code  = m.group(1)
            title = _clean_html(m.group(2)).strip()
            if stock_codes and code not in stock_codes:
                continue
            if title and len(title) > 5:
                items.append({
                    "source":    "公開資訊觀測站",
                    "title":     f"[{code}] {title}",
                    "url":       "https://mops.twse.com.tw/",
                    "summary":   "",
                    "published": today.strftime("%Y-%m-%d %H:%M"),
                    "query":     code,
                })
    except Exception as e:
        log.warning(f"MOPS 抓取失敗: {e}")
    return items[:50]  # 限制數量


# ════════════════════════════════════════
# 工具函式
# ════════════════════════════════════════

def _clean_html(text: str) -> str:
    """移除 HTML 標籤"""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_date(date_str: str) -> str:
    """嘗試解析各種日期格式"""
    if not date_str:
        return datetime.today().strftime("%Y-%m-%d %H:%M")
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            pass
    return date_str[:16]


def _dedup(items: list[dict]) -> list[dict]:
    """依 title hash 去重"""
    seen = set()
    out  = []
    for it in items:
        h = hashlib.md5(it["title"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(it)
    return out


# ════════════════════════════════════════
# 主流程
# ════════════════════════════════════════

def fetch_all_news(
    tickers: list[str] = None,
    days: int = 1,
) -> pd.DataFrame:
    """
    抓取全市場相關新聞
    tickers: 股票代碼清單（空=抓市場整體）
    days: 只保留最近幾天的新聞
    """
    all_items = []

    # 1. 市場整體新聞
    log.info("抓取市場整體新聞...")
    all_items += fetch_yahoo_finance_rss("台股")
    all_items += fetch_yahoo_finance_rss("半導體 AI")
    all_items += fetch_cnyes_rss()
    time.sleep(0.5)

    # 2. 個股新聞（如有指定）
    if tickers:
        log.info(f"抓取 {len(tickers)} 檔個股新聞...")
        for code in tickers[:20]:  # 限制 20 檔避免過多請求
            all_items += fetch_google_news_rss(f"台股 {code}")
            time.sleep(0.3)

    # 3. MOPS 重大訊息
    log.info("抓取公開資訊觀測站重大訊息...")
    all_items += fetch_mops_announcements(tickers)

    # 去重 + 過濾日期
    all_items = _dedup(all_items)
    cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    all_items = [
        it for it in all_items
        if it["published"][:10] >= cutoff
    ]

    if not all_items:
        log.warning("未抓到任何新聞")
        return pd.DataFrame()

    df = pd.DataFrame(all_items)
    df["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 存檔
    date_str = datetime.today().strftime("%Y%m%d")
    out = NEWS_DIR / f"news_{date_str}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    log.info(f"抓到 {len(df)} 則新聞 → {out}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台灣財經新聞抓取")
    parser.add_argument("--ticker", nargs="*", help="股票代碼")
    parser.add_argument("--days",   type=int, default=1, help="最近幾天")
    args = parser.parse_args()
    fetch_all_news(tickers=args.ticker, days=args.days)

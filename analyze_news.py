"""
analyze_news.py — 新聞情緒分析（Claude API + Prompt Caching）

用 claude-haiku-4-5 批次分析新聞情緒，成本低速度快。
系統提示使用 cache_control 快取，每次請求只傳新聞本身。

執行：
  python analyze_news.py                    # 分析今日新聞
  python analyze_news.py --ticker 2330 3581 # 只分析特定股票相關新聞
  python analyze_news.py --date 20260601    # 分析特定日期

輸出：data/news/sentiment_YYYYMMDD.csv
  ticker, title, sentiment, score, reason, published
"""

import sys, json, time, logging, argparse, os
from pathlib import Path
from datetime import datetime

import pandas as pd
import anthropic

NEWS_DIR = Path("data/news")
NEWS_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# ────────────────────────────────────────
# 系統提示（會被快取）
# ────────────────────────────────────────
SYSTEM_PROMPT = """你是一位專業的台灣股市分析師，專門分析財經新聞對個股或大盤的影響。

分析每則新聞時，請輸出 **嚴格 JSON 格式**（不加任何多餘文字）：
{
  "sentiment": "positive" | "negative" | "neutral",
  "score": <-1.0 到 1.0 之間的浮點數，正值=利多，負值=利空，0=中性>,
  "impact": "high" | "medium" | "low",
  "tickers": ["股票代碼1", "股票代碼2"],
  "reason": "一句話說明判斷原因"
}

判斷準則：
- positive (score > 0.2)：財報優於預期、訂單增加、新產品發布、法人調升目標價、獲利創新高
- negative (score < -0.2)：財報低於預期、訂單取消、法律糾紛、法人調降評等、景氣下行
- neutral (-0.2 ≤ score ≤ 0.2)：人事異動、股權申報、例行說明、一般訊息
- impact high：影響整體市場或大型指標股
- impact medium：影響特定產業或中型股
- impact low：對市場影響有限
- tickers：只填入明確提到的台股代碼（4位數字），無則填空陣列"""


def get_client() -> anthropic.Anthropic:
    """取得 Anthropic client（讀取 API Key）"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # 嘗試從 config.json 讀取
        cfg_path = Path("config.json")
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                key = cfg.get("anthropic_api_key", "")
            except:
                pass
    if not key:
        raise ValueError(
            "找不到 ANTHROPIC_API_KEY。\n"
            "請設定環境變數：set ANTHROPIC_API_KEY=sk-ant-...\n"
            "或在 config.json 中加入 'anthropic_api_key' 欄位"
        )
    return anthropic.Anthropic(api_key=key)


def analyze_one(client: anthropic.Anthropic, title: str, summary: str = "") -> dict:
    """
    分析單則新聞（使用 prompt caching）
    system prompt 會被快取，只有 user message 每次不同
    """
    content = title
    if summary:
        content = f"標題：{title}\n摘要：{summary}"

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # 快取系統提示
        }],
        messages=[{
            "role": "user",
            "content": f"請分析這則新聞：\n{content}",
        }],
    )

    raw = response.content[0].text.strip()
    # 提取 JSON（有時模型會加說明）
    json_match = raw
    if "```" in raw:
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            json_match = m.group(1)
    elif not raw.startswith("{"):
        import re
        m = re.search(r"(\{.*\})", raw, re.DOTALL)
        if m:
            json_match = m.group(1)

    result = json.loads(json_match)
    return {
        "sentiment": result.get("sentiment", "neutral"),
        "score":     float(result.get("score", 0.0)),
        "impact":    result.get("impact", "low"),
        "tickers":   result.get("tickers", []),
        "reason":    result.get("reason", ""),
        "cache_read": response.usage.cache_read_input_tokens or 0,
    }


def analyze_batch(
    news_df: pd.DataFrame,
    max_items: int = 50,
    delay: float = 0.3,
) -> pd.DataFrame:
    """
    批次分析新聞情緒
    max_items: 最多分析幾則（節省 API 費用）
    """
    if news_df.empty:
        return pd.DataFrame()

    client = get_client()

    # 按重要性排序：市場整體 > 個股
    df = news_df.head(max_items).copy()
    results = []
    cache_hits = 0

    log.info(f"開始分析 {len(df)} 則新聞...")

    for i, (_, row) in enumerate(df.iterrows(), 1):
        try:
            res = analyze_one(
                client,
                str(row.get("title", "")),
                str(row.get("summary", "")),
            )
            cache_hits += 1 if res["cache_read"] > 0 else 0
            results.append({
                "source":    row.get("source", ""),
                "title":     row.get("title", ""),
                "url":       row.get("url", ""),
                "published": row.get("published", ""),
                "query":     row.get("query", ""),
                "sentiment": res["sentiment"],
                "score":     res["score"],
                "impact":    res["impact"],
                "tickers":   ",".join(res["tickers"]),
                "reason":    res["reason"],
            })
            sys.stdout.write(
                f"\r  [{i:3d}/{len(df)}] "
                f"快取命中 {cache_hits} 次  "
                f"最新：{row.get('title','')[:30]}..."
            )
            sys.stdout.flush()
            time.sleep(delay)

        except json.JSONDecodeError:
            log.debug(f"  JSON解析失敗，跳過：{row.get('title','')[:40]}")
            results.append({
                "source":    row.get("source", ""),
                "title":     row.get("title", ""),
                "url":       row.get("url", ""),
                "published": row.get("published", ""),
                "query":     row.get("query", ""),
                "sentiment": "neutral",
                "score":     0.0,
                "impact":    "low",
                "tickers":   "",
                "reason":    "解析失敗",
            })
        except Exception as e:
            log.warning(f"\n  分析失敗：{e}")
            time.sleep(1)

    print(f"\n  快取命中率：{cache_hits}/{len(df)} ({cache_hits/max(len(df),1)*100:.0f}%)")
    return pd.DataFrame(results)


def get_ticker_sentiment(
    sentiment_df: pd.DataFrame,
    ticker: str,
) -> dict:
    """
    取得特定股票的情緒摘要
    回傳：avg_score, news_count, recent_news
    """
    if sentiment_df.empty:
        return {"avg_score": 0.0, "count": 0, "recent": []}

    # 從 tickers 欄位找相關新聞
    code = ticker.replace(".TW", "").replace(".TWO", "").strip()
    mask = sentiment_df["tickers"].str.contains(code, na=False)
    # 也找標題中有股號的新聞
    mask |= sentiment_df["title"].str.contains(code, na=False)
    # 也找 query 欄位
    if "query" in sentiment_df.columns:
        mask |= sentiment_df["query"].astype(str) == code

    relevant = sentiment_df[mask]
    if relevant.empty:
        return {"avg_score": 0.0, "count": 0, "recent": []}

    avg_score = float(relevant["score"].mean())
    recent = relevant.nlargest(3, "score")[
        ["title", "sentiment", "score", "reason", "published"]
    ].to_dict("records")

    return {
        "avg_score": round(avg_score, 3),
        "count":     len(relevant),
        "recent":    recent,
        "positive":  int((relevant["score"] > 0.2).sum()),
        "negative":  int((relevant["score"] < -0.2).sum()),
    }


def load_latest_sentiment() -> pd.DataFrame:
    """載入最新的情緒分析結果"""
    csvs = sorted(NEWS_DIR.glob("sentiment_*.csv"), reverse=True)
    if not csvs:
        return pd.DataFrame()
    return pd.read_csv(csvs[0], encoding="utf-8-sig")


def run_daily(max_items: int = 60):
    """每日情緒分析流程"""
    from fetch_news import fetch_all_news

    log.info("=" * 55)
    log.info("  新聞情緒分析")
    log.info("=" * 55)

    # 抓新聞
    news_df = fetch_all_news(days=1)
    if news_df.empty:
        log.warning("無新聞，跳過分析")
        return

    # 分析情緒
    sent_df = analyze_batch(news_df, max_items=max_items)
    if sent_df.empty:
        log.warning("情緒分析結果為空")
        return

    # 存檔
    date_str = datetime.today().strftime("%Y%m%d")
    out = NEWS_DIR / f"sentiment_{date_str}.csv"
    sent_df.to_csv(out, index=False, encoding="utf-8-sig")
    log.info(f"情緒分析完成 → {out}")

    # 摘要
    pos = (sent_df["score"] > 0.2).sum()
    neg = (sent_df["score"] < -0.2).sum()
    neu = len(sent_df) - pos - neg
    avg = sent_df["score"].mean()
    log.info(f"  市場情緒：正面{pos} 負面{neg} 中性{neu}  均分{avg:+.3f}")
    return sent_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="新聞情緒分析")
    parser.add_argument("--ticker",   nargs="*", help="股票代碼")
    parser.add_argument("--date",     default="",    help="日期 YYYYMMDD")
    parser.add_argument("--max",      type=int, default=60, help="最多分析幾則")
    args = parser.parse_args()

    if args.date:
        # 分析已存的特定日期新聞
        csv_path = NEWS_DIR / f"news_{args.date}.csv"
        if not csv_path.exists():
            print(f"找不到 {csv_path}")
            sys.exit(1)
        news_df = pd.read_csv(csv_path, encoding="utf-8-sig")
    else:
        from fetch_news import fetch_all_news
        news_df = fetch_all_news(tickers=args.ticker, days=1)

    sent_df = analyze_batch(news_df, max_items=args.max)
    if not sent_df.empty:
        date_str = args.date or datetime.today().strftime("%Y%m%d")
        out = NEWS_DIR / f"sentiment_{date_str}.csv"
        sent_df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n結果已存：{out}")
        print(sent_df[["title","sentiment","score","reason"]].head(10).to_string(index=False))

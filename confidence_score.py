"""
confidence_score.py — 信心分數引擎
整合三層訊號，輸出每檔股票的綜合信心分數

三層訊號（各佔權重）：
  技術面  (40%)：掃描訊號等級 + RS強度 + 入場時機
  新聞情緒(30%)：近期相關新聞平均情緒分數
  法人報告(30%)：最新評等 + 目標上漲空間

信心分數 0-100：
  80+  → 強力做多（三層共振）
  60-79 → 做多（技術 + 至少一層基本面支持）
  40-59 → 中性觀察
  20-39 → 偏空
  <20  → 避開
"""

import sys, json, math, logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

NEWS_DIR    = Path("data/news")
REPORTS_DIR = Path("data/reports")
SCAN_DIR    = Path("scan_results")

log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 各層分數計算
# ════════════════════════════════════════

def tech_score(signal_row: dict) -> float:
    """
    技術面分數 0-100
    依訊號等級、RS、入場時機計算
    """
    grade    = str(signal_row.get("訊號等級", ""))
    rs       = float(signal_row.get("RS相對強度", 0) or 0)
    risk_pct = float(signal_row.get("風險%", 10) or 10)
    timing   = str(signal_row.get("進場時機", ""))

    # 訊號等級基礎分
    grade_scores = {
        "BUY★★": 90,  # 突破當日
        "BUY★":  75,  # 早期確認
        "BUY":   60,  # 標準確認
    }
    base = grade_scores.get(grade, 50)

    # RS 加分（RS > 1 表示強於大盤）
    rs_bonus = max(-20, min(20, (rs - 1.0) * 30))

    # 風險修正（風險越低越好）
    risk_penalty = max(-15, min(0, (risk_pct - 5) * -1.5))

    score = base + rs_bonus + risk_penalty
    return max(0, min(100, score))


def news_score(ticker: str, sentiment_df: pd.DataFrame) -> float:
    """
    新聞情緒分數 0-100
    50 = 中性，>50 = 正面，<50 = 負面
    """
    if sentiment_df is None or sentiment_df.empty:
        return 50.0  # 無資料 → 中性

    from analyze_news import get_ticker_sentiment
    info = get_ticker_sentiment(sentiment_df, ticker)

    if info["count"] == 0:
        return 50.0

    avg = info["avg_score"]  # -1 ~ 1
    # 轉換到 0-100，再加上 high impact 加權
    base_score = 50 + avg * 40  # -1→10, 0→50, 1→90

    # 如果有高影響力新聞，放大效果
    high_impact = sentiment_df[
        sentiment_df["impact"] == "high"
    ]
    if not high_impact.empty:
        hi_avg = high_impact["score"].mean()
        base_score = base_score * 0.7 + (50 + hi_avg * 50) * 0.3

    return max(0, min(100, base_score))


def report_score(ticker: str, reports: list[dict]) -> float:
    """
    法人報告分數 0-100
    依評等 + 上漲空間計算
    """
    if not reports:
        return 50.0  # 無報告 → 中性

    from parse_report import get_ticker_report
    report = get_ticker_report(ticker, reports)
    if not report:
        return 50.0

    # 評等基礎分
    rating_scores = {
        "Buy":         85,
        "Outperform":  75,
        "Hold":        50,
        "Underperform":30,
        "Sell":        15,
        "NR":          50,
    }
    rating = report.get("rating", "NR")
    base = rating_scores.get(rating, 50)

    # 上漲空間調整
    upside = report.get("upside_pct") or 0
    upside_bonus = max(-20, min(20, upside / 2))

    score = base + upside_bonus
    return max(0, min(100, score))


# ════════════════════════════════════════
# 主函式
# ════════════════════════════════════════

def compute_confidence(
    scan_df: pd.DataFrame,
    sentiment_df: pd.DataFrame = None,
    reports: list[dict] = None,
    weights: tuple = (0.40, 0.30, 0.30),
) -> pd.DataFrame:
    """
    計算每個訊號的綜合信心分數

    weights: (技術面, 新聞情緒, 法人報告)
    """
    if scan_df.empty:
        return pd.DataFrame()

    w_tech, w_news, w_rep = weights
    records = []

    for _, row in scan_df.iterrows():
        ticker = str(row.get("代碼", ""))

        t_score = tech_score(row.to_dict())
        n_score = news_score(ticker, sentiment_df)
        r_score = report_score(ticker, reports or [])

        # 加權平均
        final = t_score * w_tech + n_score * w_news + r_score * w_rep

        # 三層共振加分（如果三層都 > 60，額外加 5 分）
        if t_score > 65 and n_score > 60 and r_score > 60:
            final = min(100, final + 5)

        records.append({
            **row.to_dict(),
            "tech_score":   round(t_score, 1),
            "news_score":   round(n_score, 1),
            "report_score": round(r_score, 1),
            "confidence":   round(final, 1),
            "signal_type":  _classify(final),
        })

    result = pd.DataFrame(records)
    result = result.sort_values("confidence", ascending=False)
    return result


def _classify(score: float) -> str:
    if score >= 80: return "強力做多 ⭐⭐⭐"
    if score >= 65: return "做多 ⭐⭐"
    if score >= 50: return "觀察 ⭐"
    if score >= 35: return "中性"
    return "偏空"


def load_latest_signals() -> pd.DataFrame:
    csvs = sorted(SCAN_DIR.glob("signals_*.csv"), reverse=True)
    if not csvs:
        return pd.DataFrame()
    return pd.read_csv(csvs[0], encoding="utf-8-sig")


def load_latest_sentiment() -> pd.DataFrame:
    try:
        from analyze_news import load_latest_sentiment as _load
        return _load()
    except:
        return pd.DataFrame()


def load_latest_reports() -> list[dict]:
    try:
        from parse_report import load_latest_reports as _load
        return _load()
    except:
        return []


def run_confidence_scoring() -> pd.DataFrame:
    """一鍵計算今日所有訊號的信心分數"""
    log.info("載入訊號、新聞、法人報告...")

    scan_df      = load_latest_signals()
    sentiment_df = load_latest_sentiment()
    reports      = load_latest_reports()

    if scan_df.empty:
        log.warning("無掃描結果，請先執行 scan_signals.py")
        return pd.DataFrame()

    log.info(
        f"  訊號：{len(scan_df)} 筆  "
        f"新聞：{len(sentiment_df) if not sentiment_df.empty else 0} 則  "
        f"法人報告：{len(reports)} 份"
    )

    result = compute_confidence(scan_df, sentiment_df, reports)

    # 存檔
    date_str = datetime.today().strftime("%Y%m%d")
    out = SCAN_DIR / f"confidence_{date_str}.csv"
    result.to_csv(out, index=False, encoding="utf-8-sig")
    log.info(f"信心分數計算完成 → {out}")

    # 印出前10名
    cols = ["代碼", "名稱", "進場時機", "收盤", "confidence",
            "signal_type", "tech_score", "news_score", "report_score"]
    available = [c for c in cols if c in result.columns]
    print("\n" + "="*65)
    print(f"  信心分數排行（前10）")
    print("="*65)
    print(result[available].head(10).to_string(index=False))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_confidence_scoring()

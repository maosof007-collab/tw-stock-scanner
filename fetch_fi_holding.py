"""
fetch_fi_holding.py
爬取台灣證交所「外資持股比例」歷史資料
資料來源：https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS

每檔股票輸出：data/fi_holding/{ticker}_fi_holding.csv
欄位：date, ticker, fi_shares, fi_pct, total_shares
      fi_shares = 外資持股張數
      fi_pct    = 外資持股比例 (%)
      total_shares = 發行張數
"""

import requests
import pandas as pd
import time, logging
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path("data/fi_holding")
LOG_FILE = DATA_DIR / "fetch_log.csv"
DELAY    = 1.5
MAX_RETRY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "fi_holding.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 單月資料抓取
# ════════════════════════════════════════
def fetch_fi_holding_month(ticker: str, year: int, month: int) -> pd.DataFrame:
    """
    抓取單一股票某月的外資持股資料
    TWSE MI_QFIIS 端點：每次查詢回傳該月所有交易日資料
    """
    date_str = f"{year}{month:02d}01"
    url      = "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS"
    params   = {
        "response": "json",
        "stockNo":  ticker.replace(".TW", "").strip(),
        "date":     date_str,
    }

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params,
                                headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            if data.get("stat") != "OK" or "data" not in data:
                return pd.DataFrame()

            fields = data.get("fields", [])
            rows   = data["data"]
            df     = pd.DataFrame(rows, columns=fields)

            # 欄位對應（TWSE 格式偶有變動，做彈性對應）
            col_map = {
                "日期":        "date_str",
                "股票代號":    "ticker_raw",
                "股票名稱":    "name",
                "外資及陸資持有股數": "fi_shares_raw",
                "外資及陸資持股比例": "fi_pct_raw",
                "發行股數":    "total_shares_raw",
                # 舊格式
                "外資持有股數": "fi_shares_raw",
                "持股比例":    "fi_pct_raw",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            if "fi_shares_raw" not in df.columns:
                return pd.DataFrame()

            # 清理數字
            def clean_num(s):
                return pd.to_numeric(
                    s.astype(str).str.replace(",", "").str.replace("%", "").str.strip(),
                    errors="coerce"
                )

            df["fi_shares"]    = clean_num(df["fi_shares_raw"]) / 1000  # 股→張
            df["fi_pct"]       = clean_num(df["fi_pct_raw"])
            df["total_shares"] = clean_num(df.get("total_shares_raw",
                                                    pd.Series(["0"]*len(df)))) / 1000

            # 日期（民國轉西元）
            def roc_to_date(s):
                try:
                    parts = str(s).strip().split("/")
                    if len(parts) == 3:
                        y = int(parts[0]) + 1911
                        return pd.Timestamp(f"{y}-{parts[1]}-{parts[2]}")
                except:
                    pass
                return pd.NaT

            df["date"]   = df["date_str"].apply(roc_to_date)
            df["ticker"] = ticker

            result = df[["date", "ticker", "fi_shares", "fi_pct", "total_shares"]].copy()
            result = result.dropna(subset=["date"])
            return result

        except Exception as e:
            log.warning(f"{ticker} {year}/{month:02d} 第{attempt}次失敗: {e}")
            time.sleep(2 * attempt)

    return pd.DataFrame()


# ════════════════════════════════════════
# 完整歷史 & 增量更新
# ════════════════════════════════════════
def fetch_fi_holding_history(ticker: str,
                              start: str = "2015-01-01") -> pd.DataFrame:
    """
    抓取單一股票完整外資持股歷史
    ticker: "2330.TW" 或 "2330"
    """
    tc       = ticker.replace(".TW", "").strip()
    out_path = DATA_DIR / f"{tc}_fi_holding.csv"
    end_date = datetime.today()

    # 增量：有舊資料則只抓新的月份
    if out_path.exists():
        old      = pd.read_csv(out_path, parse_dates=["date"])
        last_d   = old["date"].max()
        start_dt = last_d - timedelta(days=32)   # 回推一個月確保不漏
        log.info(f"{tc} 增量更新：{start_dt.strftime('%Y-%m')} ~ {end_date.strftime('%Y-%m')}")
    else:
        old      = pd.DataFrame()
        start_dt = pd.Timestamp(start)
        log.info(f"{tc} 首次抓取：{start_dt.strftime('%Y-%m')} ~ {end_date.strftime('%Y-%m')}")

    # 產生月份清單
    months = pd.date_range(
        start=start_dt.replace(day=1),
        end=end_date,
        freq="MS"
    )
    results = []

    for i, m in enumerate(months, 1):
        log.info(f"  [{i}/{len(months)}] {tc} {m.year}/{m.month:02d}")
        df = fetch_fi_holding_month(tc, m.year, m.month)
        if not df.empty:
            results.append(df)
        time.sleep(DELAY)

    if not results:
        log.info(f"  {tc} 無新資料")
        return old

    new_df   = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    combined = pd.concat([old, new_df], ignore_index=True) if not old.empty else new_df
    combined = (combined
                .drop_duplicates(subset=["date"])
                .sort_values("date")
                .reset_index(drop=True))

    combined.to_csv(out_path, index=False, encoding="utf-8-sig")
    log.info(f"  {tc} 儲存 {len(combined)} 筆 → {out_path}")
    return combined


def update_all_fi_holding(tickers: list):
    """批次更新所有股票的外資持股比例"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=" * 50)
    log.info(f"  外資持股比例更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)

    results = []
    for t in tickers:
        tc = t.replace(".TW", "").strip()
        try:
            df = fetch_fi_holding_history(t)
            results.append({"ticker": tc, "rows": len(df), "status": "OK"})
        except Exception as e:
            log.error(f"{tc} 失敗: {e}")
            results.append({"ticker": tc, "rows": 0, "status": "ERROR"})

    log_df = pd.DataFrame(results)
    log_df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if LOG_FILE.exists():
        log_df = pd.concat([pd.read_csv(LOG_FILE), log_df], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    ok = (log_df["status"] == "OK").sum()
    log.info(f"完成！成功 {ok}/{len(results)} 檔")


# ════════════════════════════════════════
# 讀取工具
# ════════════════════════════════════════
def load_fi_holding(ticker: str) -> pd.DataFrame:
    """讀取外資持股比例，index = date"""
    tc   = ticker.replace(".TW", "").strip()
    path = DATA_DIR / f"{tc}_fi_holding.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    return df.set_index("date").sort_index()


if __name__ == "__main__":
    import argparse, glob

    parser = argparse.ArgumentParser(description="外資持股比例爬蟲")
    parser.add_argument("--mode",   choices=["update", "history", "test"],
                        default="update")
    parser.add_argument("--ticker", default="2330", help="測試用股票代碼")
    parser.add_argument("--start",  default="2015-01-01")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "test":
        log.info(f"測試抓取 {args.ticker} ...")
        df = fetch_fi_holding_history(args.ticker, start=args.start)
        print(df.tail(10).to_string())
    else:
        csvs    = sorted(glob.glob("data/*.TW.csv"))
        tickers = [Path(f).stem.replace(".TW", "") for f in csvs]
        if not tickers:
            log.warning("找不到 data/*.TW.csv，請先執行 download_tw_stocks.py")
        else:
            update_all_fi_holding(tickers)

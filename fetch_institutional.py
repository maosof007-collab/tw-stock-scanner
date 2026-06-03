"""
fetch_institutional.py
從台灣證交所抓取三大法人買賣超資料
每天收盤後執行一次，資料存入 data/institutional/

資料來源（公開）：
  - 三大法人每日買賣超：https://www.twse.com.tw/rwd/zh/fund/T86
  - 外資持股比例：https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS

執行方式：
  手動：python fetch_institutional.py
  排程：與 updater.py 一起在每天 18:30 後執行
"""

import requests
import pandas as pd
import time, os, json, logging
from pathlib import Path
from datetime import datetime, timedelta

# ════════════════════════════════════════
# 設定
# ════════════════════════════════════════
DATA_DIR   = Path("data/institutional")
INST_DIR   = DATA_DIR          # 供其他模組 import 使用
LOG_FILE   = DATA_DIR / "fetch_log.csv"
DELAY      = 1.5      # 每次請求間隔（秒），避免被封
MAX_RETRY  = 3
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "fetch.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 1. 三大法人每日買賣超（全市場）
# ════════════════════════════════════════
def fetch_institutional_daily(date_str: str) -> pd.DataFrame:
    """
    抓取指定日期全市場三大法人買賣超
    date_str: "20240101" 格式
    回傳 DataFrame，欄位：
        證券代號, 證券名稱, 外資買進, 外資賣出, 外資淨買, 
        投信買進, 投信賣出, 投信淨買, 自營商淨買, 三大法人合計
    """
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    params = {
        "response": "json",
        "date":     date_str,
        "selectType": "ALL",
    }

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params,
                                headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("stat") != "OK" or "data" not in data:
                log.warning(f"{date_str} 無資料（stat={data.get('stat')}）")
                return pd.DataFrame()

            fields = data["fields"]
            rows   = data["data"]
            df     = pd.DataFrame(rows, columns=fields)

            # 統一欄位名稱
            col_map = {
                "證券代號":           "ticker",
                "證券名稱":           "name",
                "外資及陸資(不含外資自營商)買進股數": "fi_buy",
                "外資及陸資(不含外資自營商)賣出股數": "fi_sell",
                "外資及陸資(不含外資自營商)買賣超股數": "fi_net",
                "外資自營商買進股數": "fi_prop_buy",
                "外資自營商賣出股數": "fi_prop_sell",
                "外資自營商買賣超股數": "fi_prop_net",
                "投信買進股數":        "it_buy",
                "投信賣出股數":        "it_sell",
                "投信買賣超股數":      "it_net",
                "自營商買賣超股數(自行買賣)": "dealer_self_net",
                "自營商買賣超股數(避險)":     "dealer_hedge_net",
                "三大法人買賣超股數":   "total_net",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            df["date"] = pd.to_datetime(date_str, format="%Y%m%d")

            # 數字欄位清理（移除逗號、轉數值）
            num_cols = [c for c in df.columns
                        if c not in ("ticker", "name", "date")]
            for col in num_cols:
                df[col] = (df[col].astype(str)
                               .str.replace(",", "", regex=False)
                               .str.replace("---", "0", regex=False)
                               .str.strip())
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            df["ticker"] = df["ticker"].str.strip()
            return df

        except Exception as e:
            log.warning(f"{date_str} 第{attempt}次失敗: {e}")
            time.sleep(2 * attempt)

    return pd.DataFrame()


# ════════════════════════════════════════
# 2. 抓取區間資料（批次）
# ════════════════════════════════════════
def fetch_range(start_date: str, end_date: str) -> pd.DataFrame:
    """
    抓取日期區間的三大法人資料
    start_date, end_date: "YYYY-MM-DD" 格式
    """
    dates  = pd.bdate_range(start=start_date, end=end_date)
    all_df = []
    total  = len(dates)

    log.info(f"抓取 {start_date} ~ {end_date}，共 {total} 個交易日")

    for i, d in enumerate(dates, 1):
        date_str = d.strftime("%Y%m%d")
        log.info(f"  [{i:3d}/{total}] {date_str}")
        df = fetch_institutional_daily(date_str)
        if not df.empty:
            all_df.append(df)
        time.sleep(DELAY)

    if not all_df:
        return pd.DataFrame()
    return pd.concat(all_df, ignore_index=True) if all_df else pd.DataFrame()


# ════════════════════════════════════════
# 3. 整合存檔（以個股為單位）
# ════════════════════════════════════════
def save_by_ticker(df: pd.DataFrame, out_dir: Path):
    """
    將抓到的資料按個股代碼分別存成 CSV
    檔名：{out_dir}/{ticker}_inst.csv
    """
    if df.empty:
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    for ticker, group in df.groupby("ticker"):
        ticker = str(ticker).strip()
        if not ticker or len(ticker) != 4:
            continue

        out_path = out_dir / f"{ticker}_inst.csv"
        group = group.sort_values("date").reset_index(drop=True)

        if out_path.exists():
            old = pd.read_csv(out_path, parse_dates=["date"])
            merged = pd.concat([old, group]).drop_duplicates(
                subset=["date"], keep="last"
            ).sort_values("date").reset_index(drop=True)
        else:
            merged = group

        merged.to_csv(out_path, index=False, encoding="utf-8-sig")

    log.info(f"  已儲存 {df['ticker'].nunique()} 檔個股籌碼資料 → {out_dir}")


# ════════════════════════════════════════
# 4. 每日增量更新
# ════════════════════════════════════════
def update_institutional(data_dir: Path = DATA_DIR):
    """
    增量更新：只抓最近 5 個交易日
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    end_date   = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    log.info("=" * 50)
    log.info(f"  三大法人資料增量更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"  抓取範圍：{start_date} ~ {end_date}")
    log.info("=" * 50)

    df = fetch_range(start_date, end_date)
    if df.empty:
        log.warning("無資料，跳過")
        return

    save_by_ticker(df, data_dir)

    # 記錄 log
    log_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start":     start_date,
        "end":       end_date,
        "rows":      len(df),
        "tickers":   df["ticker"].nunique(),
    }])
    if LOG_FILE.exists():
        old_log = pd.read_csv(LOG_FILE)
        log_row = pd.concat([old_log, log_row], ignore_index=True)
    log_row.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

    log.info(f"完成！共 {len(df)} 筆，{df['ticker'].nunique()} 檔個股")


# ════════════════════════════════════════
# 5. 讀取個股籌碼（給策略使用）
# ════════════════════════════════════════
def load_institutional(ticker: str,
                       data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    讀取個股籌碼 CSV
    ticker: "2330"（不含 .TW）
    回傳 DataFrame，index = date
    """
    ticker_clean = ticker.replace(".TW", "").strip()
    path = data_dir / f"{ticker_clean}_inst.csv"

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    return df


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="三大法人資料抓取工具")
    parser.add_argument("--mode", choices=["update", "history"],
                        default="update",
                        help="update=增量更新(預設), history=抓歷史區間")
    parser.add_argument("--start", default="2015-01-01",
                        help="歷史模式起始日 YYYY-MM-DD")
    parser.add_argument("--end",   default=datetime.today().strftime("%Y-%m-%d"),
                        help="歷史模式結束日 YYYY-MM-DD")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "history":
        print(f"抓取歷史資料：{args.start} ~ {args.end}")
        print("注意：資料量大，每次請求間隔 1.5 秒，請耐心等候")
        df = fetch_range(args.start, args.end)
        if not df.empty:
            save_by_ticker(df, DATA_DIR)
            print(f"完成！共 {len(df)} 筆")
    else:
        update_institutional(DATA_DIR)

"""
fetch_tdcc.py  v3.0
集保股權分散表爬蟲（正確版）

正確端點：https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5
  - 每週更新一次（週五）
  - 回傳當週全市場所有股票的股權分散表 CSV
  - 只需帶 User-Agent，不需 Selenium、不需 token
  - 每次抓全市場一個 CSV，再過濾出個股

注意：此端點只提供「最新一週」的資料
      歷史資料需透過 FinMind API（免費額度每日有限）
"""

import requests
import pandas as pd
import time, logging, io
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path("data/tdcc")
LOG_FILE = DATA_DIR / "fetch_log.csv"
DELAY    = 1.5

# 正確的官方公開資料端點
TDCC_URL  = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TDCC_URL2 = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"  # 備用

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/39.0.2171.95 Safari/537.36"
    ),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "tdcc.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 核心：抓取當週全市場資料（一次 request 搞定）
# ════════════════════════════════════════
def fetch_latest_all() -> pd.DataFrame:
    """
    抓取當週全市場股權分散表
    回傳標準化 DataFrame：
      date, stock_id, level, holders, shares, pct
    """
    for url in [TDCC_URL, TDCC_URL2]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()

            if not resp.text or len(resp.text) < 100:
                continue

            df = pd.read_csv(
                io.StringIO(resp.text),
                dtype=str,
                on_bad_lines="skip",
            )
            df.columns = [c.strip() for c in df.columns]
            log.info(f"  ✅ 抓到 {len(df)} 筆  欄位：{list(df.columns)}")

            df = _normalize(df)
            if not df.empty:
                return df

        except Exception as e:
            log.warning(f"  {url} 失敗: {e}")
            time.sleep(2)

    return pd.DataFrame()


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """標準化欄位名稱"""
    # 欄位對應（官方格式）
    col_map = {
        # 日期
        "資料日期":           "date_str",
        # 股票代號
        "證券代號":           "stock_id",
        # 持股分級（各種可能的欄位名稱）
        "持股/出資額分級":    "level",
        "持股分級":           "level",       # ← 實際欄位名稱
        "出資額分級":         "level",
        "HoldingSharesLevel": "level",
        # 人數
        "人數":               "holders",     # ← 實際欄位名稱
        "股東人數":           "holders",
        "holders":            "holders",
        # 股數
        "持有股數":           "shares",
        "股數":               "shares",      # ← 實際欄位名稱
        "持有股份/出資額":    "shares",
        # 持股比例
        "占集保庫存數比例%":  "pct",
        "佔集保庫存數比例%":  "pct",         # ← 實際欄位名稱
        "占集保庫存數比例":   "pct",
        "佔集保庫存數比例":   "pct",
        "持股比例":           "pct",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = ["stock_id", "level", "holders", "pct"]
    if not all(c in df.columns for c in required):
        log.warning(f"  缺少欄位，現有：{list(df.columns)}")
        return pd.DataFrame()

    # 日期處理
    if "date_str" in df.columns:
        # 格式通常是 YYYYMMDD
        df["date"] = pd.to_datetime(
            df["date_str"].astype(str).str.strip(),
            format="%Y%m%d", errors="coerce"
        )
    else:
        df["date"] = pd.Timestamp(datetime.today().date())

    # 數值清理
    for col in ["level", "holders", "pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                    .str.replace(",", "")
                    .str.replace("%", "")
                    .str.strip(),
                errors="coerce"
            )

    if "shares" in df.columns:
        df["shares"] = pd.to_numeric(
            df["shares"].astype(str).str.replace(",", ""),
            errors="coerce"
        ).fillna(0)
    else:
        df["shares"] = 0

    df["stock_id"] = df["stock_id"].astype(str).str.strip()

    # 排除非股票（公債 Y 開頭）和合計列（level 16/17）
    df = df[~df["stock_id"].str.startswith("Y")]
    df = df[df["level"].between(1, 15)]

    return df[["date", "stock_id", "level", "holders", "shares", "pct"]].dropna(
        subset=["stock_id", "level", "pct"]
    )


# ════════════════════════════════════════
# 儲存：按個股分檔
# ════════════════════════════════════════
def save_all_tickers(df: pd.DataFrame, out_dir: Path):
    """將全市場資料按股票代號分別存成 CSV"""
    if df.empty:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0

    for stock_id, group in df.groupby("stock_id"):
        stock_id = str(stock_id).strip()
        if not stock_id or len(stock_id) != 4:
            continue

        out_path = out_dir / f"{stock_id}_tdcc.csv"
        group    = group.sort_values("date").reset_index(drop=True)

        if out_path.exists():
            old    = pd.read_csv(out_path, parse_dates=["date"])
            merged = (pd.concat([old, group])
                      .drop_duplicates(subset=["date", "level"], keep="last")
                      .sort_values("date")
                      .reset_index(drop=True))
        else:
            merged = group

        merged.to_csv(out_path, index=False, encoding="utf-8-sig")
        saved += 1

    log.info(f"  儲存 {saved} 檔個股")


# ════════════════════════════════════════
# 歷史資料：FinMind API（免費，有額度限制）
# ════════════════════════════════════════
def fetch_history_via_finmind(stock_id: str,
                               start: str = "2015-01-01",
                               token: str = "") -> pd.DataFrame:
    """
    透過 FinMind API 抓取歷史股權分散表
    免費帳號：每日 600 次請求
    token 填空字串時使用未登入模式（額度更少）

    申請免費 token：https://finmindtrade.com/
    """
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset":   "TaiwanStockHoldingSharesPer",
        "data_id":   stock_id,
        "start_date": start,
        "end_date":   datetime.today().strftime("%Y-%m-%d"),
    }
    if token:
        params["token"] = token

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        data = resp.json()

        if data.get("status") != 200:
            log.warning(f"  FinMind {stock_id}: {data.get('msg','error')}")
            return pd.DataFrame()

        df = pd.DataFrame(data["data"])
        if df.empty:
            return pd.DataFrame()

        # 標準化欄位
        col_map = {
            "date":               "date",
            "stock_id":           "stock_id",
            "HoldingSharesLevel": "level",
            "people":             "holders",
            "unit":               "shares",
            "percent":            "pct",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["date"]  = pd.to_datetime(df["date"])
        df["level"] = pd.to_numeric(df["level"], errors="coerce")
        df = df[df["level"].between(1, 15)]

        return df[["date", "stock_id", "level", "holders", "shares", "pct"]]

    except Exception as e:
        log.error(f"  FinMind {stock_id}: {e}")
        return pd.DataFrame()


# ════════════════════════════════════════
# 每週更新（主要使用）
# ════════════════════════════════════════
def update_all_tdcc(tickers: list[str] = None):
    """
    每週抓一次全市場最新資料（一個 request），存成個股 CSV
    tickers 傳入時只儲存那幾檔（其餘忽略），None 則存全市場
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=" * 50)
    log.info(f"  集保股權分散表更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)

    df = fetch_latest_all()

    if df.empty:
        log.error("  抓取失敗，請確認網路或端點是否可用")
        _log_result("ALL", 0, "ERROR")
        return

    log.info(f"  全市場共 {df['stock_id'].nunique()} 檔，{len(df)} 筆")

    # 若有指定 tickers，只保留那幾檔
    if tickers:
        tc_clean = [t.replace(".TW", "").strip() for t in tickers]
        df       = df[df["stock_id"].isin(tc_clean)]
        log.info(f"  過濾後 {df['stock_id'].nunique()} 檔")

    save_all_tickers(df, DATA_DIR)
    _log_result("ALL", len(df), "OK")
    log.info("  ✅ 完成")


def _log_result(ticker, rows, status):
    row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ticker":    ticker,
        "rows":      rows,
        "status":    status,
    }])
    if LOG_FILE.exists():
        row = pd.concat([pd.read_csv(LOG_FILE), row], ignore_index=True)
    row.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")


# ════════════════════════════════════════
# 讀取工具（給 APP / 策略使用）
# ════════════════════════════════════════
def load_tdcc(ticker: str) -> pd.DataFrame:
    tc   = ticker.replace(".TW", "").strip()
    path = DATA_DIR / f"{tc}_tdcc.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    return df.set_index("date").sort_index()


def calc_shareholder_signals(ticker: str) -> pd.DataFrame:
    """計算股東結構質變訊號"""
    df = load_tdcc(ticker)
    if df.empty:
        return pd.DataFrame()

    pivot = df.reset_index().pivot_table(
        index="date", columns="level",
        values=["holders", "shares", "pct"], aggfunc="first"
    )
    result = pd.DataFrame(index=pivot.index)

    r_cols  = [l for l in range(1, 5)  if l in pivot["pct"].columns]
    m_cols  = [l for l in range(9, 12) if l in pivot["pct"].columns]
    m_hcols = [l for l in range(9, 12) if l in pivot["holders"].columns]
    l_cols  = [l for l in range(12, 16) if l in pivot["pct"].columns]

    result["retail_pct"] = pivot["pct"][r_cols].sum(axis=1)    if r_cols  else 0
    result["mid_pct"]    = pivot["pct"][m_cols].sum(axis=1)    if m_cols  else 0
    result["mid_cnt"]    = pivot["holders"][m_hcols].sum(axis=1) if m_hcols else 0
    result["large_pct"]  = pivot["pct"][l_cols].sum(axis=1)    if l_cols  else 0

    result["retail_d"]  = result["retail_pct"].diff()
    result["mid_d"]     = result["mid_pct"].diff()
    result["mid_cnt_d"] = result["mid_cnt"].diff()

    result["quality_change"] = (
        (result["retail_d"] < 0) & (result["mid_d"] > 0)
    )
    mid_sync = (result["mid_d"] > 0) & (result["mid_cnt_d"] > 0)
    result["smart_money_in"] = mid_sync & mid_sync.shift(1).fillna(False)
    result["retail_ma4"]     = result["retail_pct"].rolling(4).mean()
    result["chips_clean"]    = result["retail_pct"] < result["retail_ma4"]

    return result.dropna(how="all")


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
if __name__ == "__main__":
    import argparse, glob

    parser = argparse.ArgumentParser(description="集保股權分散表爬蟲 v3.0")
    parser.add_argument("--mode",
        choices=["update", "history", "test", "debug"],
        default="update",
        help="update=更新最新週資料, history=FinMind歷史, test=測試單檔, debug=診斷"
    )
    parser.add_argument("--ticker",  default="2330")
    parser.add_argument("--start",   default="2015-01-01")
    parser.add_argument("--token",   default="",
        help="FinMind API token（歷史模式用，空白為未登入）")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "debug":
        print("\n=== 診斷模式 ===")
        print(f"嘗試端點：{TDCC_URL}")
        df = fetch_latest_all()
        if df.empty:
            print("❌ 抓取失敗")
            print(f"\n備用端點：{TDCC_URL2}")
        else:
            print(f"✅ 成功！共 {len(df)} 筆，{df['stock_id'].nunique()} 檔")
            # 顯示指定股票
            tc   = args.ticker
            show = df[df["stock_id"] == tc]
            print(f"\n{tc} 資料（{len(show)} 筆）：")
            print(show.to_string(index=False) if not show.empty else "  此股票無資料")

    elif args.mode == "history":
        print(f"\n透過 FinMind 抓取 {args.ticker} 歷史資料...")
        if not args.token:
            print("⚠️  未提供 token，使用未登入模式（額度有限）")
            print("   申請免費 token：https://finmindtrade.com/")
        df = fetch_history_via_finmind(args.ticker, args.start, args.token)
        if not df.empty:
            tc  = args.ticker.replace(".TW", "").strip()
            out = DATA_DIR / f"{tc}_tdcc.csv"
            df.to_csv(out, index=False, encoding="utf-8-sig")
            print(f"✅ 儲存 {len(df)} 筆 → {out}")
        else:
            print("❌ 無資料")

    elif args.mode == "test":
        update_all_tdcc([args.ticker])
        df = load_tdcc(args.ticker)
        print(df.tail(20).to_string() if not df.empty else "無資料")

    else:   # update
        csvs    = sorted(glob.glob("data/*.TW.csv"))
        tickers = [Path(f).stem for f in csvs]  # 保留 .TW 讓 update_all_tdcc 處理
        update_all_tdcc(tickers if tickers else None)

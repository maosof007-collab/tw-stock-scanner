"""
fetch_margin.py
從台灣證交所抓取個股「融資融券」餘額資料（上市）
每天收盤後執行一次，資料存入 data/margin/

資料來源（公開）：
  融資融券餘額：https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN
  （回傳 JSON 的 tables[1] = 個股明細，單位：張）

逐檔欄位（16 欄）：
  代號, 名稱,
  融資：買進, 賣出, 現金償還, 前日餘額, 今日餘額, 次日限額,
  融券：買進, 賣出, 現券償還, 前日餘額, 今日餘額, 次日限額,
  資券互抵, 註記

註：TWSE 逐檔只公布「融資餘額張數」，不公布逐檔融資金額。
   融資維持率由策略端以「餘額增量 × 當日股價」推估加權平均成本計算。

執行方式：
  增量更新：python fetch_margin.py
  抓歷史：  python fetch_margin.py --mode history --start 2023-01-01 --end 2025-06-08
"""

import requests
import pandas as pd
import sys, time, logging
from pathlib import Path
from datetime import datetime, timedelta
from twtime import now_tw

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ════════════════════════════════════════
# 設定
# ════════════════════════════════════════
DATA_DIR  = Path("data/margin")
LOG_FILE  = DATA_DIR / "fetch_log.csv"
DELAY     = 1.5
MAX_RETRY = 3
HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/",
}
URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"

# 個股明細 16 欄對應（依 TWSE 欄位順序）
COLS = [
    "ticker", "name",
    "margin_buy", "margin_sell", "margin_redeem",
    "margin_prev", "margin_balance", "margin_quota",
    "short_buy", "short_sell", "short_redeem",
    "short_prev", "short_balance", "short_quota",
    "offset", "note",
]
NUM_COLS = [
    "margin_buy", "margin_sell", "margin_redeem", "margin_prev",
    "margin_balance", "margin_quota", "short_buy", "short_sell",
    "short_redeem", "short_prev", "short_balance", "short_quota", "offset",
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
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
# 1. 單日全市場融資融券
# ════════════════════════════════════════
def fetch_margin_daily(date_str: str) -> pd.DataFrame:
    """date_str: 'YYYYMMDD'。回傳個股融資融券 DataFrame（單位：張）"""
    params = {"response": "json", "date": date_str, "selectType": "ALL"}

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(URL, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            j = resp.json()

            if j.get("stat") != "OK" or not j.get("tables"):
                log.warning(f"{date_str} 無資料（stat={j.get('stat')}）")
                return pd.DataFrame()

            # 找出「個股明細」表：欄位數為 16 的那張
            table = next(
                (t for t in j["tables"]
                 if isinstance(t.get("fields"), list) and len(t["fields"]) == 16),
                None
            )
            if table is None or not table.get("data"):
                log.warning(f"{date_str} 找不到個股明細表")
                return pd.DataFrame()

            df = pd.DataFrame(table["data"], columns=COLS)
            df["date"] = pd.to_datetime(date_str, format="%Y%m%d")

            for col in NUM_COLS:
                df[col] = (df[col].astype(str)
                           .str.replace(",", "", regex=False)
                           .str.replace("---", "0", regex=False)
                           .str.strip())
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            df["ticker"] = df["ticker"].astype(str).str.strip()
            df["name"]   = df["name"].astype(str).str.strip()
            return df

        except Exception as e:
            log.warning(f"{date_str} 第{attempt}次失敗: {e}")
            time.sleep(2 * attempt)

    return pd.DataFrame()


# ════════════════════════════════════════
# 1b. 單日上櫃融資（櫃買中心 TPEX）
# ════════════════════════════════════════
TPEX_URL = ("https://www.tpex.org.tw/web/stock/margin_trading/"
            "margin_balance/margin_bal_result.php")
# TPEX 個股明細 20 欄 → 對映到本專案 schema（融資6欄 + 融券6欄）
# 0代號 1名稱 2前資餘額 3資買 4資賣 5現償 6資餘額 7資證金 8資使用率 9資限額
# 10前券餘額 11券賣 12券買 13券償 14券餘額 15券證金 16券使用率 17券限額 18資券相抵 19備註
_TPEX_IDX = {
    "margin_buy": 3, "margin_sell": 4, "margin_redeem": 5, "margin_prev": 2,
    "margin_balance": 6, "margin_quota": 9,
    "short_buy": 12, "short_sell": 11, "short_redeem": 13, "short_prev": 10,
    "short_balance": 14, "short_quota": 17, "offset": 18,
}


def fetch_margin_daily_otc(date_str: str) -> pd.DataFrame:
    """上櫃融資（TPEX），date_str:'YYYYMMDD'。回傳與上市同 schema。"""
    roc = f"{int(date_str[:4]) - 1911}/{date_str[4:6]}/{date_str[6:]}"
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(TPEX_URL,
                                params={"l": "zh-tw", "d": roc, "o": "json"},
                                headers=HEADERS, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            if j.get("stat", "").lower() != "ok" or not j.get("tables"):
                return pd.DataFrame()
            table = next((t for t in j["tables"]
                          if isinstance(t.get("fields"), list) and len(t["fields"]) == 20),
                         None)
            if table is None or not table.get("data"):
                return pd.DataFrame()

            raw = pd.DataFrame(table["data"])
            out = pd.DataFrame()
            out["ticker"] = raw[0].astype(str).str.strip()
            out["name"]   = raw[1].astype(str).str.strip()
            for col, idx in _TPEX_IDX.items():
                out[col] = (raw[idx].astype(str)
                            .str.replace(",", "", regex=False)
                            .str.replace("---", "0", regex=False).str.strip())
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
            out["note"] = ""
            out["date"] = pd.to_datetime(date_str, format="%Y%m%d")
            # 只留 4 碼純數字股票代號
            out = out[out["ticker"].str.fullmatch(r"\d{4}")]
            return out.reindex(columns=COLS + ["date"])
        except Exception as e:
            log.warning(f"{date_str} OTC 第{attempt}次失敗: {e}")
            time.sleep(2 * attempt)
    return pd.DataFrame()


# ════════════════════════════════════════
# 2. 抓區間（上市 TWSE + 上櫃 TPEX）
# ════════════════════════════════════════
def fetch_range(start_date: str, end_date: str) -> pd.DataFrame:
    dates  = pd.bdate_range(start=start_date, end=end_date)
    all_df = []
    total  = len(dates)
    log.info(f"抓取 {start_date} ~ {end_date}，共 {total} 個交易日（上市+上櫃）")

    for i, d in enumerate(dates, 1):
        date_str = d.strftime("%Y%m%d")
        tw  = fetch_margin_daily(date_str)
        time.sleep(DELAY)
        otc = fetch_margin_daily_otc(date_str)
        parts = [x for x in (tw, otc) if not x.empty]
        if parts:
            day = pd.concat(parts, ignore_index=True)
            all_df.append(day)
            log.info(f"  [{i:3d}/{total}] {date_str}  上市{len(tw)}+上櫃{len(otc)} 檔")
        else:
            log.info(f"  [{i:3d}/{total}] {date_str}  （無）")
        time.sleep(DELAY)

    return pd.concat(all_df, ignore_index=True) if all_df else pd.DataFrame()


# ════════════════════════════════════════
# 3. 依個股存檔（增量合併）
# ════════════════════════════════════════
def save_by_ticker(df: pd.DataFrame, out_dir: Path = DATA_DIR):
    if df.empty:
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    for ticker, group in df.groupby("ticker"):
        ticker = str(ticker).strip()
        if not ticker or len(ticker) != 4:
            continue

        out_path = out_dir / f"{ticker}_margin.csv"
        group = group.sort_values("date").reset_index(drop=True)

        if out_path.exists():
            old = pd.read_csv(out_path, parse_dates=["date"])
            merged = (pd.concat([old, group])
                      .drop_duplicates(subset=["date"], keep="last")
                      .sort_values("date").reset_index(drop=True))
        else:
            merged = group

        merged.to_csv(out_path, index=False, encoding="utf-8-sig")

    log.info(f"  已儲存 {df['ticker'].nunique()} 檔個股融資資料 → {out_dir}")


# ════════════════════════════════════════
# 4. 增量更新（缺口感知：從實際最後日期接著抓）
# ════════════════════════════════════════
def _last_data_date(data_dir: Path, ref: str = "2330_margin.csv"):
    """參考檔（台積電）的最後資料日；讀不到回 None"""
    p = data_dir / ref
    if not p.exists():
        return None
    try:
        d = pd.read_csv(p, usecols=["date"])
        return pd.to_datetime(d["date"].iloc[-1])
    except Exception:
        return None


def update_margin(data_dir: Path = DATA_DIR):
    end_date = now_tw().strftime("%Y-%m-%d")
    # 從實際最後資料日+1 接著抓（電腦幾天沒開也不會漏），最多回補 45 天
    last = _last_data_date(data_dir)
    if last is not None:
        start_dt = max(last + timedelta(days=1), now_tw() - timedelta(days=45))
    else:
        start_dt = now_tw() - timedelta(days=7)
    start_date = start_dt.strftime("%Y-%m-%d")

    log.info("=" * 50)
    log.info(f"  融資融券資料增量更新  {now_tw():%Y-%m-%d %H:%M}")
    log.info(f"  範圍：{start_date} ~ {end_date}")
    log.info("=" * 50)

    df = fetch_range(start_date, end_date)
    if df.empty:
        log.warning("無資料，跳過")
        return
    save_by_ticker(df, data_dir)
    _log_run(start_date, end_date, df)
    log.info(f"完成！共 {len(df)} 筆，{df['ticker'].nunique()} 檔")


def _log_run(start, end, df):
    row = pd.DataFrame([{
        "timestamp": now_tw().strftime("%Y-%m-%d %H:%M:%S"),
        "start": start, "end": end,
        "rows": len(df), "tickers": df["ticker"].nunique(),
    }])
    if LOG_FILE.exists():
        row = pd.concat([pd.read_csv(LOG_FILE), row], ignore_index=True)
    row.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")


# ════════════════════════════════════════
# 5. 讀取（給策略使用）
# ════════════════════════════════════════
def load_margin(ticker: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    tc   = ticker.replace(".TWO", "").replace(".TW", "").strip()
    path = data_dir / f"{tc}_margin.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="個股融資融券餘額抓取工具")
    parser.add_argument("--mode", choices=["update", "history"], default="update")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end",   default=now_tw().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    if args.mode == "history":
        log.info(f"抓取歷史：{args.start} ~ {args.end}（每日間隔 {DELAY}s）")
        df = fetch_range(args.start, args.end)
        if not df.empty:
            save_by_ticker(df)
            _log_run(args.start, args.end, df)
            log.info(f"完成！共 {len(df)} 筆，{df['ticker'].nunique()} 檔")
    else:
        update_margin()

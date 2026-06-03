"""
download_all_tw_stocks.py
自動抓取全市場股票清單（上市 + 上櫃）並下載歷史資料

資料來源：
  上市清單：台灣證交所 https://www.twse.com.tw/rwd/zh/listed/TWSE_listed
  上櫃清單：證券櫃買中心 https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes
"""

import requests
import yfinance as yf
import pandas as pd
import time, os, sys, logging, re, io
from pathlib import Path
from datetime import datetime

START_DATE  = "2015-01-01"
END_DATE    = datetime.today().strftime("%Y-%m-%d")
OUTPUT_DIR  = Path("data")
BENCHMARK   = "^TWII"
DELAY       = 0.8
MAX_RETRY   = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    ),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_DIR / "download.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# Step 1：抓全市場股票清單
# ════════════════════════════════════════
def get_listed_stocks() -> dict[str, str]:
    """抓台灣證交所上市股票清單（ISIN公開資料）"""
    try:
        url  = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "cp950"
        tables = pd.read_html(io.StringIO(resp.text))
        df = tables[0]
        stocks = {}
        for val in df[0]:
            m = re.match(r"^(\d{4})[　\s]+(.+)", str(val))
            if m:
                stocks[m.group(1)] = m.group(2).strip()
        log.info(f"  上市股票：{len(stocks)} 檔")
        return stocks
    except Exception as e:
        log.warning(f"  上市清單抓取失敗: {e}")
        return {}


def get_otc_stocks() -> dict[str, str]:
    """抓證券櫃買中心上櫃股票清單"""
    try:
        url  = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        stocks = {}
        for row in data:
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            name = str(row.get("CompanyName", "")).strip()
            if code.isdigit() and len(code) == 4:
                stocks[code] = name
        log.info(f"  上櫃股票：{len(stocks)} 檔")
        return stocks
    except Exception as e:
        log.warning(f"  上櫃清單抓取失敗: {e}")
        return {}


def get_all_stocks() -> tuple[dict[str, str], dict[str, str]]:
    """合併上市 + 上櫃，分別回傳（上市用.TW，上櫃用.TWO）"""
    log.info("抓取全市場股票清單...")
    listed = get_listed_stocks()
    time.sleep(1)
    otc    = get_otc_stocks()
    log.info(f"  合計：{len(listed)+len(otc)} 檔（上市{len(listed)}+上櫃{len(otc)}）")

    # 存清單 CSV（上市.TW，上櫃.TWO）
    rows = []
    for k, v in listed.items():
        rows.append({"ticker": f"{k}.TW",  "code": k, "name": v, "market": "上市"})
    for k, v in otc.items():
        rows.append({"ticker": f"{k}.TWO", "code": k, "name": v, "market": "上櫃"})
    pd.DataFrame(rows).to_csv(OUTPUT_DIR / "stock_list.csv", index=False, encoding="utf-8-sig")
    return listed, otc


# ════════════════════════════════════════
# Step 2：下載歷史資料
# ════════════════════════════════════════
def download_one(code: str, name: str, suffix: str = "TW") -> dict:
    ticker = f"{code}.{suffix}"
    result = {"ticker": ticker, "name": name,
               "status": "", "rows": 0, "note": ""}
    try:
        df = yf.download(
            ticker, start=START_DATE, end=END_DATE,
            progress=False, auto_adjust=True, timeout=15,
        )
        if df.empty:
            result.update({"status": "SKIP", "note": "無資料（可能已下市）"})
            return result

        # 欄位整理（MultiIndex 相容）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        # timezone 相容處理（yfinance 新版 bug）
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)   # 有 tz → 移除
        else:
            df.index = pd.to_datetime(df.index)    # 無 tz → 確保 datetime

        cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
        df   = df[cols]
        if "Close" in df.columns:
            df = df[df["Close"] > 0].dropna(subset=["Close"])

        if len(df) < 100:
            result.update({"status": "SKIP", "note": f"只有{len(df)}筆"})
            return result

        out = OUTPUT_DIR / f"{ticker}.csv"
        df.to_csv(out)
        result.update({"status": "OK", "rows": len(df)})

    except Exception as e:
        err_msg = str(e)
        # 已下市的股票靜默跳過，不算 ERROR
        if any(kw in err_msg for kw in
               ["delisted", "No data", "404", "not found", "timezone"]):
            result.update({"status": "SKIP", "note": err_msg[:60]})
        else:
            result.update({"status": "ERROR", "note": err_msg[:60]})
    return result


def download_benchmark():
    log.info("下載大盤指數...")
    try:
        df = yf.download(BENCHMARK, start=START_DATE, end=END_DATE,
                         progress=False, auto_adjust=True, timeout=15)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        else:
            df.index = pd.to_datetime(df.index)
        df[["Close"]].to_csv(OUTPUT_DIR / "benchmark_TWII.csv")
        log.info(f"  ✅ 大盤 {len(df)} 筆")
    except Exception as e:
        log.error(f"  大盤下載失敗: {e}")


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    log.info("=" * 60)
    log.info("  全市場股票資料下載（上市 + 上櫃）")
    log.info(f"  區間：{START_DATE} → {END_DATE}")
    log.info("=" * 60)

    # 大盤
    download_benchmark()
    time.sleep(1)

    # 取得清單
    listed, otc = get_all_stocks()
    if not listed and not otc:
        log.error("無法取得股票清單，程式終止")
        return

    # 合併成 (code, name, suffix) list
    all_tasks = [(code, name, "TW")  for code, name in listed.items()] + \
                [(code, name, "TWO") for code, name in otc.items()]
    total = len(all_tasks)
    log.info(f"\n開始下載 {total} 檔股票資料（上市.TW / 上櫃.TWO）...")
    log.info("預計需要時間：約 {:.0f} 分鐘".format(total * DELAY / 60))

    logs, ok, skip, err = [], 0, 0, 0
    for i, (code, name, suffix) in enumerate(all_tasks, 1):
        sys.stdout.write(f"\r  [{i:4d}/{total}] {code}.{suffix} {name[:8]}...     ")
        sys.stdout.flush()
        res = download_one(code, name, suffix)
        logs.append(res)
        if   res["status"] == "OK":    ok   += 1
        elif res["status"] == "SKIP":  skip += 1
        else:                          err  += 1
        time.sleep(DELAY)

    # 儲存下載記錄
    pd.DataFrame(logs).to_csv(
        OUTPUT_DIR / "download_log.csv", index=False, encoding="utf-8-sig"
    )
    log.info(f"\n\n{'='*60}")
    log.info(f"  完成！  ✅{ok} 成功  ⏭️{skip} 跳過  ❌{err} 失敗")
    log.info(f"  記錄：{OUTPUT_DIR}/download_log.csv")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()

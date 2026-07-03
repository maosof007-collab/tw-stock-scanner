"""
updater.py
每日增量更新台股資料（只抓最新幾天，不重抓全部）

執行方式：
  手動：python updater.py
  排程：
    Windows → Task Scheduler 每天 18:30 執行
    Mac     → launchd / crontab -e  → "30 18 * * 1-5 cd /path && python updater.py"
    Linux   → crontab -e            → "30 18 * * 1-5 cd /path && python updater.py"
"""

import yfinance as yf
import pandas as pd
import os, sys, time, glob, logging
from pathlib import Path
from datetime import datetime, timedelta

# 主控台改用 UTF-8，避免 ✅ 等 emoji 在 cp950 終端機觸發 UnicodeEncodeError 洗版
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from progress import set_progress

# ════════════════════════════════════════
# 設定
# ════════════════════════════════════════
# 用本檔位置定位 data/，不依賴工作目錄(CWD)；隨身版從上層啟動時 CWD 會跑掉
DATA_DIR    = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)   # 保險：缺資料夾時自建，避免 import 即崩
LOG_FILE    = DATA_DIR / "update_log.csv"
BENCHMARK   = "^TWII"
LOOKBACK    = 7          # 每次抓最近幾天（重疊幾天確保不漏）
DELAY       = 0.8        # 每檔間隔秒數
MAX_RETRY   = 3          # 失敗重試次數

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "updater.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 核心：增量更新單一檔案
# ════════════════════════════════════════
def update_one(ticker: str, csv_path: Path) -> dict:
    result = {
        "ticker":     ticker,
        "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status":     "",
        "old_rows":   0,
        "new_rows":   0,
        "added_rows": 0,
        "last_date":  "",
        "note":       "",
    }

    # ── 讀舊資料 ──────────────────────────
    if csv_path.exists():
        try:
            old_df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            idx = pd.to_datetime(old_df.index)
            old_df.index = idx.tz_convert(None) if idx.tz is not None else idx
            result["old_rows"] = len(old_df)
            last_date = old_df.index[-1].date()
            result["last_date"] = str(last_date)
        except Exception as e:
            log.warning(f"{ticker}: 讀取舊資料失敗，將重新下載 ({e})")
            old_df    = pd.DataFrame()
            last_date = None
    else:
        old_df    = pd.DataFrame()
        last_date = None

    # ── 計算抓取起始日 ─────────────────────
    today = datetime.today().date()
    # 只有「資料已涵蓋最近一個交易日」才跳過
    # （平日=今天；週六/週日=上週五。舊版用 7 天寬限導致股價最多落後一週）
    wd = today.weekday()
    expected = today - timedelta(days=wd - 4) if wd >= 5 else today
    if last_date and last_date >= expected:
        result["status"]   = "SKIP"
        result["note"]     = f"資料已是最新（最後日期: {last_date}）"
        result["new_rows"] = result["old_rows"]
        return result

    start = (
        (last_date - timedelta(days=LOOKBACK)).strftime("%Y-%m-%d")
        if last_date else "2015-01-01"
    )
    end   = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 下載新資料（含重試）────────────────
    new_df = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            raw = yf.download(
                ticker, start=start, end=end,
                progress=False, auto_adjust=True, timeout=15,
            )
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [c[0] for c in raw.columns]
            idx = pd.to_datetime(raw.index)
            raw.index = idx.tz_convert(None) if idx.tz is not None else idx
            raw = raw[[c for c in ["Open","High","Low","Close","Volume"] if c in raw.columns]]
            raw = raw[raw["Close"] > 0]
            if not raw.empty:
                new_df = raw
                break
        except Exception as e:
            log.warning(f"{ticker} 第{attempt}次嘗試失敗: {e}")
            time.sleep(2 * attempt)

    if new_df is None or new_df.empty:
        result["status"] = "ERROR"
        result["note"]   = "下載失敗（重試後仍無資料）"
        return result

    # ── 合併 & 去重 ───────────────────────
    if not old_df.empty:
        combined = pd.concat([old_df, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
    else:
        combined = new_df

    # ── 儲存 ──────────────────────────────
    try:
        combined.to_csv(csv_path)
        added = len(combined) - len(old_df)
        result.update({
            "status":     "OK",
            "new_rows":   len(combined),
            "added_rows": max(added, 0),
            "last_date":  str(combined.index[-1].date()),
        })
    except Exception as e:
        result["status"] = "ERROR"
        result["note"]   = f"寫入失敗: {e}"

    return result


def update_benchmark():
    """更新大盤指數"""
    csv_path = DATA_DIR / "benchmark_TWII.csv"
    log.info(f"更新大盤 {BENCHMARK}...")
    res = update_one(BENCHMARK, csv_path)
    icon = "✅" if res["status"] == "OK" else ("⏭️" if res["status"] == "SKIP" else "❌")
    log.info(f"  {icon} 大盤: {res['status']}  {res.get('note','')}")
    return res


# ════════════════════════════════════════
# 批次更新所有 CSV
# ════════════════════════════════════════
def update_all(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """掃描 data/ 下所有 *.TW.csv，逐一增量更新"""
    DATA_DIR.mkdir(exist_ok=True)

    log.info("=" * 50)
    log.info(f"  台股資料每日更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)

    # 大盤
    bm_res = update_benchmark()
    time.sleep(DELAY)

    # 個股（上市 .TW + 上櫃 .TWO）
    csv_files = sorted(data_dir.glob("*.TW.csv")) + sorted(data_dir.glob("*.TWO.csv"))
    if not csv_files:
        log.warning("找不到任何 CSV，請先執行 download_all_tw_stocks.py")
        return pd.DataFrame()

    log.info(f"找到 {len(csv_files)} 檔個股 CSV（上市+上櫃），開始更新...")
    results = [bm_res]

    total_n = len(csv_files)
    for i, csv_path in enumerate(csv_files, 1):
        ticker = csv_path.stem  # e.g. "2330.TW"
        sys.stdout.write(f"\r  [{i}/{total_n}] {ticker}...    ")
        sys.stdout.flush()
        set_progress("股價更新", i, total_n, ticker)

        res  = update_one(ticker, csv_path)
        icon = "[OK]" if res["status"] == "OK" else ("[skip]" if res["status"] == "SKIP" else "[err]")
        note = (f"+{res['added_rows']} 筆，共{res['new_rows']}筆"
                if res["status"] == "OK" else res.get("note",""))
        log.info(f"  {icon} [{i}/{total_n}] {ticker:12s}  {note}")
        results.append(res)
        # 只有真的有下載（OK/ERROR）才需要限流等待；SKIP 沒碰網路，不必 sleep → 大幅加速
        if res["status"] != "SKIP":
            time.sleep(DELAY)

    set_progress("股價更新", total_n, total_n, "完成", done=True)

    # 儲存本次更新紀錄
    log_df = pd.DataFrame(results)
    if LOG_FILE.exists():
        old_log = pd.read_csv(LOG_FILE)
        log_df  = pd.concat([old_log, log_df], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

    ok   = sum(1 for r in results if r["status"] == "OK")
    skip = sum(1 for r in results if r["status"] == "SKIP")
    err  = sum(1 for r in results if r["status"] == "ERROR")

    log.info("=" * 50)
    log.info(f"  完成！  ✅{ok} 更新  ⏭️{skip} 跳過  ❌{err} 失敗")
    log.info("=" * 50)

    return log_df


# ════════════════════════════════════════
# 排程設定說明（印出給使用者）
# ════════════════════════════════════════
SCHEDULE_HELP = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  每日自動更新排程設定
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【Mac / Linux — crontab】
  1. 終端機輸入：crontab -e
  2. 新增這行（每天 18:30 執行）：
     30 18 * * 1-5 cd /你的專案路徑 && python updater.py >> logs/cron.log 2>&1

【Windows — Task Scheduler】
  1. 開啟「工作排程器」
  2. 建立基本工作 → 觸發程序：每天 18:30
  3. 動作：啟動程式
     程式：python.exe
     引數：/你的專案路徑/updater.py
     起始：/你的專案路徑

【Python APScheduler（APP 內建排程，不需外部工具）】
  pip install apscheduler
  → 在 app.py 加入，開啟 Streamlit 後自動排程
  → 適合一直開著 APP 的使用情境
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="台股資料每日增量更新")
    parser.add_argument("--help-schedule", action="store_true",
                        help="顯示排程設定說明")
    parser.add_argument("--data-dir", default="data",
                        help="資料資料夾路徑（預設: data）")
    args = parser.parse_args()

    if args.help_schedule:
        print(SCHEDULE_HELP)
    else:
        DATA_DIR = Path(args.data_dir)
        update_all(DATA_DIR)

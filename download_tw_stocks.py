"""
台股資料下載器
用途：從 Yahoo Finance 抓取台股歷史日線資料，存成 CSV
用法：python download_tw_stocks.py

輸出：
  data/
    2330.TW.csv
    2317.TW.csv
    ...
    benchmark_TWII.csv
    download_log.csv   ← 下載成功/失敗紀錄
"""

import yfinance as yf
import pandas as pd
import os, time, sys
from datetime import datetime, timedelta

# ════════════════════════════════════════
# 設定區（自由修改）
# ════════════════════════════════════════
START_DATE  = "2015-01-01"   # 回測起始日（越早資料越多）
END_DATE    = datetime.today().strftime("%Y-%m-%d")
OUTPUT_DIR  = "data"         # 輸出資料夾
BENCHMARK   = "^TWII"        # 大盤指數

# 台股清單（可自行新增）
# 格式：{代碼: 名稱}
STOCK_LIST = {
    # ── 半導體 ──
    "2330.TW": "台積電",
    "2303.TW": "聯電",
    "2454.TW": "聯發科",
    "2379.TW": "瑞昱",
    "3711.TW": "日月光投控",
    # ── 電腦/伺服器 ──
    "2317.TW": "鴻海",
    "2382.TW": "廣達",
    "2308.TW": "台達電",
    "2357.TW": "華碩",
    "2353.TW": "宏碁",
    # ── 記憶體/面板 ──
    "2408.TW": "南亞科",
    "3034.TW": "聯詠",
    # ── 金融 ──
    "2891.TW": "中信金",
    "2882.TW": "國泰金",
    "2886.TW": "兆豐金",
    # ── 傳產/其他 ──
    "1301.TW": "台塑",
    "2002.TW": "中鋼",
    "2412.TW": "中華電",
    "3008.TW": "大立光",
    "6505.TW": "台塑化",
}

DELAY_BETWEEN = 0.8   # 每次下載間隔（秒），避免被擋

# ════════════════════════════════════════
# 下載函數
# ════════════════════════════════════════
def download_one(ticker: str, name: str, out_dir: str) -> dict:
    """下載單一股票，回傳狀態 dict"""
    result = {"ticker": ticker, "name": name,
               "status": "", "rows": 0, "start": "", "end": "", "note": ""}
    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=END_DATE,
            progress=False,
            auto_adjust=True,   # 還原股價（除息/除權）
            timeout=15,
        )

        # 欄位整理
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        if df.empty:
            result["status"] = "SKIP"
            result["note"]   = "無資料（可能已下市）"
            return result

        # 只保留需要的欄位
        cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
        df   = df[cols].copy()
        df.index.name = "Date"
        idx = pd.to_datetime(df.index)
        df.index = idx.tz_convert(None) if idx.tz is not None else idx  # 移除時區

        # 移除明顯錯誤（收盤=0）
        df = df[df["Close"] > 0]

        # 儲存
        fname = os.path.join(out_dir, f"{ticker}.csv")
        df.to_csv(fname)

        result.update({
            "status": "OK",
            "rows":   len(df),
            "start":  str(df.index[0].date()),
            "end":    str(df.index[-1].date()),
            "file":   fname,
        })
    except Exception as e:
        result["status"] = "ERROR"
        result["note"]   = str(e)[:80]

    return result


def download_benchmark(out_dir: str):
    """下載大盤指數"""
    print(f"  下載大盤 {BENCHMARK}...")
    try:
        df = yf.download(BENCHMARK, start=START_DATE, end=END_DATE,
                         progress=False, auto_adjust=True, timeout=15)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.index.name = "Date"
        idx = pd.to_datetime(df.index)
        df.index = idx.tz_convert(None) if idx.tz is not None else idx
        df = df[["Close"]].rename(columns={"Close": "TWII"})
        fname = os.path.join(out_dir, "benchmark_TWII.csv")
        df.to_csv(fname)
        print(f"  ✅ 大盤 {len(df)} 筆 → {fname}")
        return fname
    except Exception as e:
        print(f"  ❌ 大盤下載失敗：{e}")
        return None


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 55)
    print("  台股資料下載器")
    print(f"  區間：{START_DATE} → {END_DATE}")
    print(f"  股票數：{len(STOCK_LIST)} 檔")
    print(f"  輸出目錄：{OUTPUT_DIR}/")
    print("=" * 55)

    # 大盤
    download_benchmark(OUTPUT_DIR)
    time.sleep(DELAY_BETWEEN)

    # 個股
    logs = []
    total = len(STOCK_LIST)
    ok_count = 0

    for i, (ticker, name) in enumerate(STOCK_LIST.items(), 1):
        sys.stdout.write(f"\r  [{i:2d}/{total}] {ticker} {name}...          ")
        sys.stdout.flush()

        res = download_one(ticker, name, OUTPUT_DIR)
        logs.append(res)

        icon = "✅" if res["status"] == "OK" else ("⚠️ " if res["status"] == "SKIP" else "❌")
        note = f"{res['rows']} 筆 {res['start']}~{res['end']}" if res["status"] == "OK" else res["note"]
        print(f"\r  {icon} [{i:2d}/{total}] {ticker} {name:6s}  {note}")

        if res["status"] == "OK":
            ok_count += 1

        time.sleep(DELAY_BETWEEN)

    # 儲存下載紀錄
    log_df  = pd.DataFrame(logs)
    log_path = os.path.join(OUTPUT_DIR, "download_log.csv")
    log_df.to_csv(log_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 55)
    print(f"  ✅ 成功：{ok_count} 檔")
    print(f"  ❌ 失敗：{sum(1 for r in logs if r['status']=='ERROR')} 檔")
    print(f"  ⚠️  跳過：{sum(1 for r in logs if r['status']=='SKIP')} 檔")
    print(f"  紀錄檔：{log_path}")
    print("=" * 55)
    print("\n下一步：執行 streamlit run app.py")


if __name__ == "__main__":
    main()

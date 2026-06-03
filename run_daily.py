"""
run_daily.py  ── 每日一鍵執行腳本（最終整合版）

執行順序：
  Step 1  股價 CSV 增量更新            (updater.py)
  Step 2  三大法人買賣超               (fetch_institutional.py)
  Step 3  外資持股比例                 (fetch_fi_holding.py)   ← 新增
  Step 4  集保股權分散表（週四才跑）    (fetch_tdcc.py)         ← 新增
  Step 5  掃描所有策略買入訊號
  Step 6  Line / Email 推播通知

排程建議（Mac/Linux crontab -e）：
  30 18 * * 1-5  cd /你的路徑 && python run_daily.py >> logs/daily.log 2>&1

Windows Task Scheduler：
  程式：python  引數：run_daily.py  起始目錄：/你的路徑
"""

import sys, logging, glob
from pathlib import Path
from datetime import datetime
from itertools import groupby

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

# ── 資料更新模組 ────────────────────────
from updater             import update_all,              DATA_DIR
from fetch_institutional import update_institutional,    INST_DIR
from fetch_fi_holding    import update_all_fi_holding,   DATA_DIR as FI_DIR
from fetch_tdcc          import update_all_tdcc,         DATA_DIR as TDCC_DIR
from notifier            import notify_signals, notify_update_done, load_config

# ════════════════════════════════════════
# 日誌設定
# ════════════════════════════════════════
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            f"logs/daily_{datetime.today().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 工具：掃描所有股票代碼
# ════════════════════════════════════════
def get_tickers() -> list[str]:
    """從 data/*.TW.csv + *.TWO.csv 取得股票清單"""
    tw  = sorted(glob.glob("data/*.TW.csv"))
    two = sorted(glob.glob("data/*.TWO.csv"))
    return [Path(f).stem for f in tw + two]

def get_stocks_map() -> dict[str, str]:
    tw  = sorted(glob.glob("data/*.TW.csv"))
    two = sorted(glob.glob("data/*.TWO.csv"))
    return {Path(f).stem: f for f in tw + two}

def load_benchmark() -> pd.Series:
    p = Path("data/benchmark_TWII.csv")
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    return df.iloc[:, 0]


# ════════════════════════════════════════
# 工具：計算指標（供掃描用）
# ════════════════════════════════════════
def calc_indicators(df: pd.DataFrame, bm_close: pd.Series) -> pd.DataFrame:
    df = df.copy()
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()],
                   axis=1).max(axis=1)
    df["ATR"]    = tr.rolling(14).mean()
    df["Vol_MA"] = df["Volume"].rolling(20).mean()
    bm = bm_close.reindex(df.index).ffill()
    df["RS"]     = (c / c.shift(60)) / (bm / bm.shift(60)).replace(0, np.nan)
    df["RS_MA"]  = df["RS"].rolling(10).mean()
    return df


# ════════════════════════════════════════
# 工具：訊號掃描
# ════════════════════════════════════════
def scan_signals(strategies_map: dict,
                 stocks_map: dict,
                 bm_eq: pd.Series) -> list[dict]:
    """
    對所有股票 × 所有策略掃描最新一根 K 棒的買入訊號
    回傳清單，每項包含：strategy / ticker / close / stop_loss /
                         rs / state / signal_grade / date
    """
    all_signals = []

    for strategy_name, strategy in strategies_map.items():
        # 使用各策略的預設參數掃描
        params = {k: v["default"] for k, v in strategy.get_params().items()}

        for ticker, csv_path in stocks_map.items():
            try:
                df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                idx = pd.to_datetime(df.index)
                df.index = idx.tz_convert(None) if idx.tz is not None else idx
                for col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["Close"])
                if len(df) < 50:
                    continue

                df.attrs["ticker"] = ticker
                bm_s = bm_eq if not bm_eq.empty else pd.Series(1.0, index=df.index)
                df   = calc_indicators(df, bm_s)
                df   = strategy.generate_signals(df, params)

                if "signal" not in df.columns:
                    continue

                last  = df.iloc[-1]
                grade = str(last.get("signal_grade", ""))
                sig   = str(last["signal"])

                # BUY 才推播；PRE-DEF / PRE / SETUP 也記錄但不推播
                if sig == "buy" or grade in ("PRE-DEF", "PRE", "SETUP", "BUY"):
                    sl    = float(last["stop_loss"]) if "stop_loss" in last.index \
                            and not pd.isna(last["stop_loss"]) else 0.0
                    rs    = round(float(last["RS"]), 2) if "RS" in last.index \
                            and not pd.isna(last["RS"]) else 0.0
                    risk  = abs((last["Close"] - sl) / last["Close"] * 100) \
                            if last["Close"] and sl else 0.0
                    all_signals.append({
                        "strategy":     strategy_name,
                        "ticker":       ticker,
                        "close":        round(float(last["Close"]), 1),
                        "stop_loss":    round(sl, 1),
                        "rs":           rs,
                        "risk_pct":     round(risk, 1),
                        "state":        str(last.get("state", "")),
                        "signal_grade": grade if grade else ("BUY" if sig == "buy" else ""),
                        "date":         str(df.index[-1].date()),
                    })
            except Exception as e:
                log.debug(f"  {strategy_name}/{ticker} 掃描失敗: {e}")

    # BUY 等級排最前
    grade_order = {"BUY": 0, "SETUP": 1, "PRE": 2, "PRE-DEF": 3}
    all_signals.sort(key=lambda x: (
        grade_order.get(x["signal_grade"], 9),
        -x["rs"]
    ))
    return all_signals


# ════════════════════════════════════════
# 主流程
# ════════════════════════════════════════
def main():
    today     = datetime.now()
    is_thursday = today.weekday() == 3   # 週四才跑集保

    log.info("=" * 60)
    log.info(f"  每日更新流程  {today.strftime('%Y-%m-%d %H:%M (%A)')}")
    log.info("=" * 60)

    tickers = get_tickers()
    if not tickers:
        log.error("找不到 data/*.TW.csv，請先執行 download_tw_stocks.py")
        return

    log.info(f"  共 {len(tickers)} 檔股票")

    # ── Step 1：股價更新 ──────────────────
    log.info("\n[Step 1/6] 股價增量更新...")
    try:
        price_log = update_all(DATA_DIR)
        ok  = (price_log["status"] == "OK").sum()   if price_log is not None and not price_log.empty else 0
        err = (price_log["status"] == "ERROR").sum() if price_log is not None and not price_log.empty else 0
        log.info(f"  ✅ 成功 {ok}  ❌ 失敗 {err}")
    except Exception as e:
        ok = err = 0
        log.error(f"  股價更新失敗: {e}")

    # ── Step 2：三大法人買賣超 ────────────
    log.info("\n[Step 2/6] 三大法人買賣超...")
    try:
        update_institutional(INST_DIR)
        log.info("  ✅ 完成")
    except Exception as e:
        log.warning(f"  ⚠️  失敗（不影響其他功能）: {e}")

    # ── Step 3：外資持股比例 ──────────────
    log.info("\n[Step 3/6] 外資持股比例...")
    try:
        update_all_fi_holding(tickers)
        log.info("  ✅ 完成")
    except Exception as e:
        log.warning(f"  ⚠️  失敗: {e}")

    # ── Step 4：集保股權分散表（週四限定）──
    if is_thursday:
        log.info("\n[Step 4/6] 集保股權分散表（週四）...")
        try:
            update_all_tdcc(tickers)
            log.info("  ✅ 完成")
        except Exception as e:
            log.warning(f"  ⚠️  失敗: {e}")
    else:
        log.info(f"\n[Step 4/6] 集保資料：今日非週四（{today.strftime('%A')}），跳過")

    # ── Step 5：掃描買入訊號 ──────────────
    log.info("\n[Step 5/6] 掃描策略訊號...")
    signals = []
    try:
        from strategies import load_all_strategies
        strategies_map = load_all_strategies()
        stocks_map     = get_stocks_map()
        bm_eq          = load_benchmark()

        log.info(f"  策略：{list(strategies_map.keys())}")
        signals = scan_signals(strategies_map, stocks_map, bm_eq)

        buy_sigs   = [s for s in signals if s["signal_grade"] == "BUY"]
        setup_sigs = [s for s in signals if s["signal_grade"] == "SETUP"]
        pre_sigs   = [s for s in signals if s["signal_grade"] in ("PRE", "PRE-DEF")]

        log.info(f"  BUY={len(buy_sigs)}  SETUP={len(setup_sigs)}  PRE={len(pre_sigs)}")

        if buy_sigs:
            log.info("  ── 今日 BUY 訊號 ──")
            for s in buy_sigs:
                log.info(
                    f"  [{s['strategy'][:14]}] {s['ticker']:8s} "
                    f"收={s['close']:>8.1f}  停={s['stop_loss']:>8.1f}  "
                    f"風險={s['risk_pct']:>4.1f}%  RS={s['rs']:.2f}  {s['state']}"
                )

    except Exception as e:
        log.error(f"  訊號掃描失敗: {e}")
        import traceback; traceback.print_exc()

    # ── Step 6：推播通知 ──────────────────
    log.info("\n[Step 6/6] 推播通知...")
    try:
        cfg      = load_config()
        line_on  = cfg["line"]["enabled"]  and bool(cfg["line"]["token"])
        email_on = cfg["email"]["enabled"] and bool(cfg["email"]["user"])

        if line_on or email_on:
            # 6a. 更新完成通知
            notify_update_done(ok, err)

            # 6b. BUY 訊號通知（按策略分組）
            buy_only = [s for s in signals if s["signal_grade"] == "BUY"]
            if buy_only:
                for strat_name, grp in groupby(
                    sorted(buy_only, key=lambda x: x["strategy"]),
                    key=lambda x: x["strategy"]
                ):
                    notify_signals(list(grp), strategy_name=strat_name)
                log.info(f"  ✅ 推播 {len(buy_only)} 個 BUY 訊號")
            else:
                log.info("  今日無 BUY 訊號，不推播")
        else:
            log.info("  推播未啟用（在 config.json 設定 Line Token 或 Gmail）")

    except Exception as e:
        log.error(f"  推播失敗: {e}")

    # ── 終端摘要 ─────────────────────────
    buy_count = len([s for s in signals if s["signal_grade"] == "BUY"])

    print("\n" + "=" * 60)
    print(f"  ✅ 每日更新完成  {today.strftime('%Y-%m-%d %H:%M')}")
    print(f"  股價更新 {ok} 檔  |  BUY訊號 {buy_count} 個")
    if signals:
        print(f"\n  {'等級':<8} {'策略':<16} {'代碼':<10} {'收盤':>8} {'停損':>8} {'風險':>6} RS")
        print("  " + "-" * 58)
        for s in signals:
            print(
                f"  {s['signal_grade']:<8} {s['strategy'][:14]:<16} "
                f"{s['ticker']:<10} {s['close']:>8.1f} "
                f"{s['stop_loss']:>8.1f} {s['risk_pct']:>5.1f}% "
                f"{s['rs']:>5.2f}"
            )
    print("=" * 60)


if __name__ == "__main__":
    main()

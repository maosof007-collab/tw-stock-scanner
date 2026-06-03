"""
market_backtest.py
全市場整體勝率回測引擎

功能：
  1. 掃描 data/ 下所有 *.TW.csv（可能 1000+ 檔）
  2. 對每檔跑策略，記錄每一筆交易
  3. 統計「策略整體勝率」、「期望值」、「各條件命中率」
  4. 輸出完整回測報告（CSV + 圖表）

執行：
  python market_backtest.py
  python market_backtest.py --strategy stage2
  python market_backtest.py --strategy abc --workers 4
"""

import sys, glob, argparse, logging, time, warnings
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

warnings.filterwarnings("ignore")

# ── 中文字型 ──
import matplotlib.font_manager as _fm
for _fn in ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DFKai-SB"]:
    if any(_fn == f.name for f in _fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = _fn
        break
matplotlib.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(Path(__file__).parent))
from strategies import load_all_strategies

# ════════════════════════════════════════
# 設定
# ════════════════════════════════════════
DATA_DIR  = Path("data")
OUT_DIR   = Path("backtest_results")
CAPITAL   = 1_000_000
POS_RISK  = 0.02
ATR_PER   = 14
VOL_PER   = 20
RS_PER    = 60

DARK  = "#0d1117"; GRID = "#1e2d3d"; TEXT = "#c9d1d9"
GREEN = "#1D9E75"; RED  = "#E24B4A"; GOLD = "#EF9F27"
BLUE  = "#378ADD"; PAL  = [GREEN, BLUE, GOLD, RED, "#9F77DD"]
GRAY  = "#6e7681"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUT_DIR / "market_backtest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 指標計算
# ════════════════════════════════════════
def calc_indicators(df: pd.DataFrame, bm: pd.Series) -> pd.DataFrame:
    df = df.copy()
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["ATR"]    = tr.rolling(ATR_PER).mean()
    df["Vol_MA"] = df["Volume"].rolling(VOL_PER).mean()
    bm_a = bm.reindex(df.index).ffill()
    df["RS"]    = (c/c.shift(RS_PER)) / (bm_a/bm_a.shift(RS_PER)).replace(0, np.nan)
    df["RS_MA"] = df["RS"].rolling(10).mean()
    return df


# ════════════════════════════════════════
# 單檔回測（供平行處理）
# ════════════════════════════════════════
def backtest_one(args):
    """
    回傳每一筆交易紀錄 list of dict
    args = (ticker, csv_path, bm_series, strategy, params, fee, slip)
    """
    ticker, csv_path, bm_vals, bm_idx, strategy, params, fee, slip = args
    results = []
    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        idx = pd.to_datetime(df.index)
        df.index = idx.tz_convert(None) if idx.tz is not None else idx
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])
        if len(df) < 250:
            return results

        bm = pd.Series(bm_vals, index=pd.DatetimeIndex(bm_idx))
        df.attrs["ticker"] = ticker
        df  = calc_indicators(df, bm)
        df  = strategy.generate_signals(df, params)

        if "signal" not in df.columns:
            return results

        # 回測邏輯
        c   = df["Close"].values
        sig = df["signal"].values
        sl_s = df["stop_loss"].values if "stop_loss" in df.columns else np.full(len(df), np.nan)
        at  = df["ATR"].values if "ATR" in df.columns else c * 0.02
        dt  = df.index
        n   = len(df)

        cash = CAPITAL; pos = ep = sl = 0; ed = None; itr = False

        for i in range(1, n):
            cv = c[i]; sv = sig[i]
            av = at[i] if not np.isnan(at[i]) else cv * 0.02

            if itr:
                exit_reason = None
                if cv <= sl:
                    exit_reason = "停損"
                elif sv == "sell":
                    exit_reason = str(df["exit_reason"].iloc[i]) if "exit_reason" in df.columns else "訊號出場"

                if exit_reason:
                    xp  = cv * (1 - slip - fee)
                    pnl = (xp - ep) * pos
                    ret_pct = (xp - ep) / ep * 100

                    # 判斷是否符合條件
                    grade = str(df["signal_grade"].iloc[ed_i]) if "signal_grade" in df.columns else ""
                    state = str(df["state"].iloc[ed_i])        if "state"        in df.columns else ""
                    rs_val= float(df["RS"].iloc[ed_i])          if "RS"           in df.columns and not np.isnan(df["RS"].iloc[ed_i]) else 0

                    results.append({
                        "ticker":      ticker,
                        "entry_date":  str(dt[ed_i].date()),
                        "exit_date":   str(dt[i].date()),
                        "entry_price": round(ep, 2),
                        "exit_price":  round(xp, 2),
                        "pnl":         round(pnl, 0),
                        "ret_pct":     round(ret_pct, 2),
                        "hold_days":   (dt[i] - dt[ed_i]).days,
                        "exit_reason": exit_reason,
                        "signal_grade":grade,
                        "state":       state,
                        "rs":          round(rs_val, 2),
                        "win":         1 if pnl > 0 else 0,
                    })
                    cash += xp * pos
                    pos = itr = 0
                else:
                    risk = ep - sl
                    if cv >= ep + risk and av > 0:
                        sl = max(sl, cv - av * 1.5)

            elif sv == "buy" and not itr:
                sl_v = sl_s[i] if not np.isnan(sl_s[i]) else cv - av * 1.5
                risk = cv - sl_v
                if risk > 0 and sl_v > 0:
                    shares = int(cash * POS_RISK / risk / 1000) * 1000
                    shares = max(shares, 1000)
                    enp    = cv * (1 + slip + fee)
                    if shares * enp <= cash:
                        cash -= shares * enp
                        pos = shares; ep = enp; sl = sl_v
                        ed = dt[i]; ed_i = i; itr = True

    except Exception as e:
        pass

    return results


# ════════════════════════════════════════
# 統計整體勝率
# ════════════════════════════════════════
def calc_overall_stats(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {}

    wins  = trades_df[trades_df["win"] == 1]
    loses = trades_df[trades_df["win"] == 0]
    n     = len(trades_df)

    win_rate   = len(wins) / n * 100
    avg_win    = wins["ret_pct"].mean()  if len(wins)  else 0
    avg_loss   = loses["ret_pct"].mean() if len(loses) else 0
    # 期望值 = 勝率 × 平均獲利 + 敗率 × 平均虧損
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)
    pf         = (wins["pnl"].sum() / abs(loses["pnl"].sum())
                  if len(loses) > 0 and loses["pnl"].sum() != 0 else 99.0)

    # 按年份分析
    trades_df["year"] = pd.to_datetime(trades_df["entry_date"]).dt.year
    by_year = trades_df.groupby("year").apply(
        lambda g: pd.Series({
            "trades":   len(g),
            "win_rate": round(g["win"].mean() * 100, 1),
            "avg_ret":  round(g["ret_pct"].mean(), 2),
        })
    ).reset_index()

    # 按持倉天數分析
    trades_df["hold_bucket"] = pd.cut(
        trades_df["hold_days"],
        bins=[0, 5, 10, 20, 40, 60, 9999],
        labels=["1-5天", "6-10天", "11-20天", "21-40天", "41-60天", "60天+"]
    )
    by_hold = trades_df.groupby("hold_bucket", observed=True).apply(
        lambda g: pd.Series({
            "trades":   len(g),
            "win_rate": round(g["win"].mean() * 100, 1),
            "avg_ret":  round(g["ret_pct"].mean(), 2),
        })
    ).reset_index()

    # 出場原因分析
    by_exit = trades_df.groupby("exit_reason").apply(
        lambda g: pd.Series({
            "trades":   len(g),
            "win_rate": round(g["win"].mean() * 100, 1),
            "avg_ret":  round(g["ret_pct"].mean(), 2),
            "total_pnl":round(g["pnl"].sum() / 1000, 0),
        })
    ).reset_index()

    # 訊號等級分析
    by_grade = None
    if "signal_grade" in trades_df.columns and trades_df["signal_grade"].notna().any():
        by_grade = trades_df.groupby("signal_grade").apply(
            lambda g: pd.Series({
                "trades":   len(g),
                "win_rate": round(g["win"].mean() * 100, 1),
                "avg_ret":  round(g["ret_pct"].mean(), 2),
            })
        ).reset_index()

    return {
        "total_trades":  n,
        "win_trades":    len(wins),
        "loss_trades":   len(loses),
        "win_rate":      round(win_rate, 2),
        "avg_win_pct":   round(avg_win, 2),
        "avg_loss_pct":  round(avg_loss, 2),
        "expectancy":    round(expectancy, 2),
        "profit_factor": round(min(pf, 99), 2),
        "avg_hold_days": round(trades_df["hold_days"].mean(), 1),
        "total_pnl_k":   round(trades_df["pnl"].sum() / 1000, 0),
        "stocks_traded": trades_df["ticker"].nunique(),
        "by_year":       by_year,
        "by_hold":       by_hold,
        "by_exit":       by_exit,
        "by_grade":      by_grade,
    }


# ════════════════════════════════════════
# 報告圖表
# ════════════════════════════════════════
def plot_report(trades_df: pd.DataFrame, stats: dict, strategy_name: str):
    fig = plt.figure(figsize=(18, 22))
    fig.patch.set_facecolor(DARK)
    gs  = gridspec.GridSpec(4, 2, figure=fig, hspace=0.5, wspace=0.35)

    def sax(ax, title=""):
        ax.set_facecolor(DARK); ax.tick_params(colors=TEXT, labelsize=8)
        ax.grid(True, color=GRID, linewidth=0.4); ax.spines[:].set_color(GRID)
        if title: ax.set_title(title, color=TEXT, fontsize=10, pad=8)

    # ── 1. KPI 文字卡 ──
    ax0 = fig.add_subplot(gs[0, :])
    sax(ax0); ax0.axis("off")

    kpis = [
        ("總交易筆數",     f"{stats['total_trades']:,}"),
        ("整體勝率",        f"{stats['win_rate']:.1f}%"),
        ("平均獲利",        f"+{stats['avg_win_pct']:.2f}%"),
        ("平均虧損",        f"{stats['avg_loss_pct']:.2f}%"),
        ("期望值(每筆)",   f"{stats['expectancy']:.2f}%"),
        ("獲利因子",        f"{stats['profit_factor']:.2f}"),
        ("平均持倉",        f"{stats['avg_hold_days']:.0f}天"),
        ("涵蓋股票",        f"{stats['stocks_traded']} 檔"),
    ]
    for i, (label, val) in enumerate(kpis):
        x = (i % 4) / 4 + 0.05; y = 0.75 if i < 4 else 0.25
        color = GREEN if ("+" in val or "獲利" in label) else (RED if "-" in val else TEXT)
        ax0.text(x, y+0.1, label, color=GRAY, fontsize=9, transform=ax0.transAxes, ha="center")
        ax0.text(x, y-0.1, val,   color=color, fontsize=20, fontweight="bold",
                 transform=ax0.transAxes, ha="center")
    ax0.set_title(f"整體勝率回測報告 — {strategy_name}", color=BLUE,
                  fontsize=13, fontweight="bold", pad=10)

    # ── 2. 逐年勝率長條 ──
    ax1 = fig.add_subplot(gs[1, 0])
    sax(ax1, "逐年勝率 & 交易次數")
    by_year = stats["by_year"]
    if not by_year.empty:
        x = np.arange(len(by_year))
        bars = ax1.bar(x, by_year["win_rate"], color=[
            GREEN if v >= 50 else RED for v in by_year["win_rate"]
        ], alpha=0.85, width=0.6, edgecolor="none")
        ax1.axhline(50, color=GOLD, lw=1.5, ls="--", alpha=0.8, label="50%基準")
        for bar, val in zip(bars, by_year["win_rate"]):
            ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
                     f"{val:.0f}%", ha="center", color=TEXT, fontsize=8)
        ax1.set_xticks(x)
        ax1.set_xticklabels(by_year["year"].astype(str), color=TEXT, fontsize=8)
        ax1.set_ylabel("勝率 (%)", color=TEXT)
        ax1.set_ylim(0, 100)
        ax1.legend(facecolor="#161b22", edgecolor=GRID, labelcolor=TEXT, fontsize=8)

        # 次座標：交易次數
        ax1r = ax1.twinx()
        ax1r.set_facecolor(DARK)
        ax1r.spines[:].set_color(GRID)
        ax1r.plot(x, by_year["trades"], "o--", color=BLUE, lw=1.5, ms=6)
        ax1r.set_ylabel("交易次數", color=BLUE)
        ax1r.tick_params(colors=BLUE, labelsize=7)

    # ── 3. 損益分布直方圖 ──
    ax2 = fig.add_subplot(gs[1, 1])
    sax(ax2, "單筆報酬率分布")
    ret = trades_df["ret_pct"]
    pos_ret = ret[ret >= 0]; neg_ret = ret[ret < 0]
    ax2.hist(pos_ret, bins=40, color=GREEN, alpha=0.75, edgecolor="none", label=f"獲利 {len(pos_ret)}筆")
    ax2.hist(neg_ret, bins=40, color=RED,   alpha=0.75, edgecolor="none", label=f"虧損 {len(neg_ret)}筆")
    ax2.axvline(0,                       color="white", lw=1,   ls="--")
    ax2.axvline(ret.mean(),              color=GOLD,   lw=1.5, ls="--", label=f"均值 {ret.mean():.2f}%")
    ax2.axvline(stats["expectancy"],     color=BLUE,   lw=1.5, ls="-",  label=f"期望值 {stats['expectancy']:.2f}%")
    ax2.set_xlabel("單筆報酬率 (%)", color=TEXT)
    ax2.set_ylabel("筆數", color=TEXT)
    ax2.legend(facecolor="#161b22", edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    # ── 4. 持倉天數 vs 勝率 ──
    ax3 = fig.add_subplot(gs[2, 0])
    sax(ax3, "持倉天數 vs 勝率")
    by_hold = stats["by_hold"]
    if not by_hold.empty:
        x = np.arange(len(by_hold))
        bars = ax3.bar(x, by_hold["win_rate"], color=BLUE, alpha=0.8, width=0.6, edgecolor="none")
        ax3.axhline(50, color=GOLD, lw=1.5, ls="--", alpha=0.8)
        for bar, val, cnt in zip(bars, by_hold["win_rate"], by_hold["trades"]):
            ax3.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
                     f"{val:.0f}%\n({cnt})", ha="center", color=TEXT, fontsize=7.5)
        ax3.set_xticks(x)
        ax3.set_xticklabels(by_hold["hold_bucket"].astype(str), color=TEXT, fontsize=8)
        ax3.set_ylabel("勝率 (%)", color=TEXT)
        ax3.set_ylim(0, 100)

    # ── 5. 出場原因分析 ──
    ax4 = fig.add_subplot(gs[2, 1])
    sax(ax4, "出場原因 vs 平均報酬")
    by_exit = stats["by_exit"].sort_values("avg_ret", ascending=True)
    if not by_exit.empty:
        y = np.arange(len(by_exit))
        colors = [GREEN if v > 0 else RED for v in by_exit["avg_ret"]]
        bars = ax4.barh(y, by_exit["avg_ret"], color=colors, alpha=0.85, edgecolor="none")
        ax4.axvline(0, color="white", lw=1)
        ax4.set_yticks(y)
        ax4.set_yticklabels(by_exit["exit_reason"], color=TEXT, fontsize=8)
        ax4.set_xlabel("平均報酬率 (%)", color=TEXT)
        for bar, val, cnt in zip(bars, by_exit["avg_ret"], by_exit["trades"]):
            x_pos = bar.get_width() + 0.1 if val >= 0 else bar.get_width() - 0.1
            ax4.text(x_pos, bar.get_y()+bar.get_height()/2,
                     f"{val:.1f}%({cnt}筆)", va="center", color=TEXT, fontsize=8)

    # ── 6. 訊號等級分析（若有）──
    ax5 = fig.add_subplot(gs[3, 0])
    sax(ax5, "訊號等級 vs 勝率")
    by_grade = stats.get("by_grade")
    if by_grade is not None and not by_grade.empty:
        x = np.arange(len(by_grade))
        bars = ax5.bar(x, by_grade["win_rate"], color=PAL[:len(by_grade)],
                       alpha=0.85, width=0.5, edgecolor="none")
        ax5.axhline(50, color=GOLD, lw=1.5, ls="--", alpha=0.8)
        for bar, val, cnt in zip(bars, by_grade["win_rate"], by_grade["trades"]):
            ax5.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
                     f"{val:.0f}%\n({cnt}筆)", ha="center", color=TEXT, fontsize=8)
        ax5.set_xticks(x)
        ax5.set_xticklabels(by_grade["signal_grade"], color=TEXT, fontsize=9)
        ax5.set_ylabel("勝率 (%)", color=TEXT)
        ax5.set_ylim(0, 100)
    else:
        ax5.text(0.5, 0.5, "此策略無訊號等級分類", transform=ax5.transAxes,
                 ha="center", va="center", color=GRAY, fontsize=11)

    # ── 7. 月勝率熱圖 ──
    ax6 = fig.add_subplot(gs[3, 1])
    sax(ax6, "月份勝率熱圖")
    trades_df["month"] = pd.to_datetime(trades_df["entry_date"]).dt.month
    trades_df["year2"] = pd.to_datetime(trades_df["entry_date"]).dt.year
    try:
        pivot = trades_df.pivot_table(
            index="year2", columns="month", values="win", aggfunc="mean"
        ) * 100
        im = ax6.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                        vmin=0, vmax=100)
        ax6.set_xticks(range(12))
        ax6.set_xticklabels([f"{m}月" for m in range(1, 13)], color=TEXT, fontsize=7)
        ax6.set_yticks(range(len(pivot.index)))
        ax6.set_yticklabels(pivot.index.astype(str), color=TEXT, fontsize=7)
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                if not np.isnan(val):
                    ax6.text(j, i, f"{val:.0f}", ha="center", va="center",
                             fontsize=6.5, color="black", fontweight="bold")
        plt.colorbar(im, ax=ax6).ax.tick_params(colors=TEXT, labelsize=7)
    except Exception:
        ax6.text(0.5, 0.5, "資料不足以生成熱圖", transform=ax6.transAxes,
                 ha="center", va="center", color=GRAY)

    sname_safe = strategy_name.replace(" ", "_").replace("/", "_")
    out = OUT_DIR / f"market_backtest_{sname_safe}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK)
    plt.close()
    return out


# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="全市場整體勝率回測")
    parser.add_argument("--strategy", default="",
        help="策略名稱（空=全部）")
    parser.add_argument("--workers",  type=int, default=1,
        help="平行工作數（建議 2-4，Windows 用 1）")
    parser.add_argument("--fee",      type=float, default=0.001)
    parser.add_argument("--slip",     type=float, default=0.001)
    parser.add_argument("--start",    default="2015-01-01",
        help="回測起始日")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)

    log.info("=" * 65)
    log.info("  全市場整體勝率回測")
    log.info(f"  起始日：{args.start}  手續費：{args.fee*100:.2f}%  工作數：{args.workers}")
    log.info("=" * 65)

    # 載入策略
    all_strategies = load_all_strategies()
    if not all_strategies:
        log.error("找不到任何策略"); return

    strategies_to_run = (
        {k: v for k, v in all_strategies.items() if args.strategy in k}
        if args.strategy else all_strategies
    )
    log.info(f"策略：{list(strategies_to_run.keys())}")

    # 股票清單
    csvs = sorted(glob.glob(str(DATA_DIR / "*.TW.csv")) + glob.glob(str(DATA_DIR / "*.TWO.csv")))
    if not csvs:
        log.error("找不到 data/*.TW.csv，請先執行 download_all_tw_stocks.py"); return

    # 過濾起始日後有資料的
    log.info(f"共 {len(csvs)} 檔 CSV，過濾資料起始日 {args.start}...")
    stocks_map = {}
    for f in csvs:
        ticker = Path(f).stem
        try:
            df_tmp = pd.read_csv(f, index_col=0, parse_dates=True, nrows=1)
            if not df_tmp.empty:
                stocks_map[ticker] = f
        except:
            pass
    log.info(f"有效股票：{len(stocks_map)} 檔")

    # 大盤
    bm_path = DATA_DIR / "benchmark_TWII.csv"
    if not bm_path.exists():
        log.error("找不到 benchmark_TWII.csv"); return
    bm_df = pd.read_csv(bm_path, index_col=0, parse_dates=True)
    idx = pd.to_datetime(bm_df.index)
    bm_df.index = idx.tz_convert(None) if idx.tz is not None else idx
    bm_series = bm_df.iloc[:, 0]

    # 對每個策略跑全市場回測
    for strategy_name, strategy in strategies_to_run.items():
        log.info(f"\n{'='*65}")
        log.info(f"  策略：{strategy_name}")
        log.info(f"{'='*65}")

        params = {k: v["default"] for k, v in strategy.get_params().items()}

        # 準備工作包
        work_args = [
            (ticker, csv_path,
             bm_series.values.tolist(), bm_series.index.tolist(),
             strategy, params, args.fee, args.slip)
            for ticker, csv_path in stocks_map.items()
        ]

        all_trades = []
        total = len(work_args)
        t0    = time.time()

        if args.workers > 1:
            # 平行處理
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futures = {ex.submit(backtest_one, w): w[0] for w in work_args}
                done = 0
                for future in as_completed(futures):
                    done += 1
                    result = future.result()
                    all_trades.extend(result)
                    elapsed = time.time() - t0
                    eta     = elapsed / done * (total - done)
                    sys.stdout.write(
                        f"\r  進度 [{done:4d}/{total}]  "
                        f"交易筆數 {len(all_trades)}  "
                        f"剩餘 {eta/60:.1f}分"
                    )
                    sys.stdout.flush()
        else:
            # 單線程（Windows 安全）
            for i, w in enumerate(work_args, 1):
                result = backtest_one(w)
                all_trades.extend(result)
                elapsed = time.time() - t0
                eta     = elapsed / i * (total - i) if i > 0 else 0
                sys.stdout.write(
                    f"\r  [{i:4d}/{total}] {w[0]:12s}  "
                    f"累計交易 {len(all_trades):5d}筆  "
                    f"剩餘 {eta/60:.1f}分"
                )
                sys.stdout.flush()

        print()
        elapsed = time.time() - t0
        log.info(f"  回測完成！耗時 {elapsed/60:.1f} 分鐘")

        if not all_trades:
            log.warning("  無任何交易紀錄，請確認資料或策略參數")
            continue

        trades_df = pd.DataFrame(all_trades)

        # 計算統計
        stats = calc_overall_stats(trades_df)

        # 印出核心結果
        log.info(f"\n  【{strategy_name}】整體回測結果")
        log.info(f"  {'─'*50}")
        log.info(f"  總交易筆數 : {stats['total_trades']:,} 筆")
        log.info(f"  涵蓋股票   : {stats['stocks_traded']} 檔")
        log.info(f"  整體勝率   : {stats['win_rate']:.2f}%")
        log.info(f"  平均獲利   : +{stats['avg_win_pct']:.2f}%")
        log.info(f"  平均虧損   : {stats['avg_loss_pct']:.2f}%")
        log.info(f"  期望值     : {stats['expectancy']:.2f}%（每筆平均報酬）")
        log.info(f"  獲利因子   : {stats['profit_factor']:.2f}")
        log.info(f"  平均持倉   : {stats['avg_hold_days']:.0f} 天")

        if "by_year" in stats and not stats["by_year"].empty:
            log.info(f"\n  逐年勝率：")
            for _, row in stats["by_year"].iterrows():
                bar = "█" * int(row["win_rate"] / 5)
                log.info(f"    {int(row['year'])}  {bar:<20}  {row['win_rate']:.1f}%  ({int(row['trades'])}筆)")

        if "by_grade" in stats and stats["by_grade"] is not None:
            log.info(f"\n  訊號等級勝率：")
            for _, row in stats["by_grade"].iterrows():
                log.info(f"    {row['signal_grade']:<10}  {row['win_rate']:.1f}%  ({int(row['trades'])}筆)")

        # 儲存結果
        sname_safe = strategy_name.replace(" ", "_").replace("/", "_")
        csv_out = OUT_DIR / f"market_trades_{sname_safe}.csv"
        trades_df.to_csv(csv_out, index=False, encoding="utf-8-sig")
        log.info(f"\n  交易明細：{csv_out}")

        # 畫圖
        log.info("  繪製報告圖表...")
        img_out = plot_report(trades_df, stats, strategy_name)
        log.info(f"  圖表：{img_out}")

    log.info("\n✅ 全部完成")


if __name__ == "__main__":
    main()

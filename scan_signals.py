"""
scan_signals.py — 今日選股掃描
掃描全市場所有股票，找出當下符合策略訊號的標的

執行：
    python scan_signals.py
    python scan_signals.py --strategy "A+B+C"   # 只跑指定策略
    python scan_signals.py --top 20              # 只顯示前20筆
"""

import sys, glob, argparse, warnings, io, requests
# Windows cp950 stdout 改為 utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp950","cp936","gbk"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib
import matplotlib.font_manager as _fm
for _fn in ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DFKai-SB"]:
    if any(_fn == f.name for f in _fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = _fn
        break
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))

from strategies import load_all_strategies
from market_backtest import calc_indicators

DATA_DIR = Path("data")
OUT_DIR  = Path("scan_results")

ATR_PER = 14
VOL_PER = 20
RS_PER  = 60


def fetch_disposal_stocks() -> set:
    """
    抓取當前處置股代碼（上市 + 上櫃）
    回傳 set of ticker strings，如 {'3581.TWO', '1234.TW'}
    """
    disposal = set()
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # ── 上櫃處置股（TPEx OpenAPI）──
    try:
        r = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_disposal_information",
            headers=HEADERS, timeout=10,
        )
        for row in r.json():
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            if code.isdigit() and len(code) == 4:
                disposal.add(f"{code}.TWO")
    except Exception as e:
        print(f"  [警告] 上櫃處置股抓取失敗: {e}")

    # ── 上市處置股（TWSE HTML 解析）──
    try:
        import re
        r2 = requests.get(
            "https://www.twse.com.tw/rwd/zh/announcement/TWT49U",
            headers=HEADERS, timeout=10,
        )
        r2.encoding = "utf-8"
        # 從 HTML 中找 4 碼股號
        codes = re.findall(r'\b(\d{4})\b', r2.text)
        for code in codes:
            if 1000 <= int(code) <= 9999:
                disposal.add(f"{code}.TW")
    except Exception as e:
        print(f"  [警告] 上市處置股抓取失敗: {e}")

    return disposal


def load_benchmark():
    p = DATA_DIR / "benchmark_TWII.csv"
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    return df.iloc[:, 0]


def load_stock(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"])


def scan_all(strategy_filter: str = "") -> list[dict]:
    all_strategies = load_all_strategies()
    if strategy_filter:
        all_strategies = {k: v for k, v in all_strategies.items()
                          if strategy_filter.lower() in k.lower()}

    # ── 排除處置股 ──────────────────────────
    print("  抓取處置股清單...")
    disposal_set = fetch_disposal_stocks()
    if disposal_set:
        print(f"  排除處置股：{len(disposal_set)} 檔 "
              f"({', '.join(sorted(disposal_set)[:5])}{'...' if len(disposal_set)>5 else ''})")

    bm = load_benchmark()

    csvs = sorted(glob.glob(str(DATA_DIR / "*.TW.csv"))) + \
           sorted(glob.glob(str(DATA_DIR / "*.TWO.csv")))

    total   = len(csvs)
    signals = []

    print(f"\n掃描 {total} 檔股票 × {len(all_strategies)} 個策略...")
    print(f"日期：{datetime.today().strftime('%Y-%m-%d')}\n")

    for i, csv_path in enumerate(csvs, 1):
        ticker = Path(csv_path).stem
        sys.stdout.write(f"\r  [{i:4d}/{total}] {ticker}      ")
        sys.stdout.flush()

        # 排除處置股
        if ticker in disposal_set:
            continue

        try:
            df = load_stock(csv_path)
            if len(df) < 120:
                continue

            df.attrs["ticker"] = ticker
            df = calc_indicators(df, bm)

            for strat_name, strategy in all_strategies.items():
                params = {k: v["default"] for k, v in strategy.get_params().items()}
                df_sig = strategy.generate_signals(df.copy(), params)

                if "signal" not in df_sig.columns:
                    continue

                last  = df_sig.iloc[-1]
                sig   = str(last.get("signal", ""))
                grade = str(last.get("signal_grade", ""))

                if sig != "buy" and grade not in ("BUY", "PRE-DEF", "PRE", "SETUP"):
                    continue

                close = float(last["Close"])
                sl    = float(last["stop_loss"]) if "stop_loss" in last.index \
                        and not pd.isna(last.get("stop_loss")) else 0.0
                rs    = float(last["RS"]) if "RS" in last.index \
                        and not pd.isna(last.get("RS")) else 0.0
                risk  = abs((close - sl) / close * 100) if close and sl else 0.0
                vol   = float(last["Volume"]) if "Volume" in last.index else 0
                vol_ma= float(last["Vol_MA"])  if "Vol_MA"  in last.index else 0
                vol_ratio = round(vol / vol_ma, 1) if vol_ma else 0

                signals.append({
                    "訊號等級":   grade if grade else "BUY",
                    "策略":       strat_name,
                    "代碼":       ticker,
                    "收盤":       round(close, 1),
                    "停損":       round(sl, 1),
                    "風險%":      round(risk, 1),
                    "RS相對強度": round(rs, 2),
                    "量比(vs均)": vol_ratio,
                    "狀態":       str(last.get("state", ""))[:20],
                    "日期":       str(df_sig.index[-1].date()),
                })

        except Exception:
            continue

    print(f"\n\n掃描完成！")
    return signals


def print_report(signals: list[dict], top: int = 50):
    if not signals:
        print("❌ 今日無任何買入訊號")
        return

    df = pd.DataFrame(signals)

    # 排序：BUY > SETUP > PRE > PRE-DEF，同級按 RS 排
    grade_order = {"BUY": 0, "SETUP": 1, "PRE": 2, "PRE-DEF": 3}
    df["_g"] = df["訊號等級"].map(grade_order).fillna(9)
    df = df.sort_values(["_g", "RS相對強度"], ascending=[True, False]).drop("_g", axis=1)

    buy_df   = df[df["訊號等級"] == "BUY"]
    other_df = df[df["訊號等級"] != "BUY"]

    print("=" * 70)
    print(f"  📈 今日選股報告  {datetime.today().strftime('%Y-%m-%d')}")
    print("=" * 70)

    if not buy_df.empty:
        print(f"\n🟢 BUY 訊號（{len(buy_df)} 筆）— 立即進場候選\n")
        print(buy_df[["代碼","策略","收盤","停損","風險%","RS相對強度","量比(vs均)","狀態"]].head(top).to_string(index=False))

    if not other_df.empty:
        print(f"\n🟡 觀察訊號（{len(other_df)} 筆）— 等待進場條件成立\n")
        print(other_df[["代碼","訊號等級","策略","收盤","RS相對強度","狀態"]].head(top).to_string(index=False))

    # 存 CSV
    OUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.today().strftime("%Y%m%d")
    out = OUT_DIR / f"signals_{date_str}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n💾 結果已存：{out}")

    # 畫圖
    if not buy_df.empty:
        _plot_signals(buy_df.head(30), date_str)


def _plot_signals(df: pd.DataFrame, date_str: str):
    DARK = "#0d1117"; TEXT = "#c9d1d9"; GREEN = "#1D9E75"
    GOLD = "#EF9F27"; RED = "#E24B4A"; GRID = "#1e2d3d"
    BLUE = "#378ADD"

    n = len(df)
    row_h = 0.55          # 每列高度（英吋）
    fig_h = max(10, n * row_h + 3)
    fig_w = 22            # 固定寬度，夠寬

    fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(DARK)
    plt.rcParams.update({"font.size": 13})

    def style_ax(ax, title):
        ax.set_facecolor(DARK)
        ax.tick_params(colors=TEXT, labelsize=13)
        ax.grid(True, color=GRID, linewidth=0.5, axis="x")
        ax.spines[:].set_color(GRID)
        ax.set_title(title, color=TEXT, fontsize=15, pad=12, fontweight="bold")

    # ── 左：RS 相對強度 ──
    ax = axes[0]
    style_ax(ax, "RS 相對強度（vs 大盤）")
    sdf = df.sort_values("RS相對強度")
    colors = [GREEN if v >= 1 else GOLD for v in sdf["RS相對強度"]]
    bars = ax.barh(range(n), sdf["RS相對強度"], color=colors,
                   alpha=0.88, height=0.65, edgecolor="none")
    ax.axvline(1.0, color="white", lw=1.5, ls="--", alpha=0.7)
    ax.set_yticks(range(n))
    ax.set_yticklabels(sdf["代碼"], fontsize=13)
    ax.set_xlabel("RS 值", color=TEXT, fontsize=13)
    for bar, val in zip(bars, sdf["RS相對強度"]):
        ax.text(bar.get_width() + 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", color=TEXT, fontsize=12, fontweight="bold")
    ax.set_xlim(0, sdf["RS相對強度"].max() * 1.18)

    # ── 右：風險% ──
    ax = axes[1]
    style_ax(ax, "進場風險%（停損距離）")
    sdf2 = df.sort_values("風險%")
    risk_colors = [RED if v > 10 else BLUE for v in sdf2["風險%"]]
    bars2 = ax.barh(range(n), sdf2["風險%"], color=risk_colors,
                    alpha=0.88, height=0.65, edgecolor="none")
    ax.axvline(5, color=GOLD, lw=1.5, ls="--", alpha=0.7, label="5% 警戒線")
    ax.set_yticks(range(n))
    ax.set_yticklabels(sdf2["代碼"], fontsize=13)
    ax.set_xlabel("風險 %", color=TEXT, fontsize=13)
    for bar, val in zip(bars2, sdf2["風險%"]):
        ax.text(bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", color=TEXT, fontsize=12, fontweight="bold")
    ax.set_xlim(0, max(sdf2["風險%"].max() * 1.2, 10))
    ax.legend(facecolor="#161b22", edgecolor=GRID, labelcolor=TEXT, fontsize=12)

    fig.suptitle(f"今日 BUY 訊號選股  {date_str}  （共 {n} 檔）",
                 color=TEXT, fontsize=17, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0, 0, 1, 1])

    out = OUT_DIR / f"signals_{date_str}.png"
    plt.savefig(out, dpi=130, bbox_inches="tight", facecolor=DARK)
    plt.close()
    print(f"圖表已存：{out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="今日選股掃描")
    parser.add_argument("--strategy", default="", help="策略名稱過濾（空=全部）")
    parser.add_argument("--top",      type=int, default=50, help="顯示前N筆")
    args = parser.parse_args()

    signals = scan_all(args.strategy)
    print_report(signals, args.top)

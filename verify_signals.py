"""
verify_signals.py — 選股訊號獨立查核（防「狀態亂寫」）
=================================================================
掃描產生的每筆訊號，用「原始資料」重新驗證一次，不信策略自己的狀態欄：
  · 共同：股價資料日 vs 訊號日、當日漲跌一致性、跌停檢查
  · 融資類策略：融資檔最後日期不得落後股價 >7 天（過期＝紅牌）
  · 大跌中融資逆勢買：訊號日真的大跌？近5筆融資餘額真的在增加？
  · 量縮整理→出量突破：量比真的有出量？融資近5筆沒大減？
結果寫回 signals CSV 的「檢核」欄（✅ / ❌原因），今日選股頁直接看得到。

執行：
  python verify_signals.py              # 查最新一份 scan_results/signals_*.csv
  python verify_signals.py --file path  # 查指定檔
掃描完自動執行（scan_signals.py 會呼叫）。
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MARGIN_DIR = DATA / "margin"

MARGIN_STRATS = ("大跌中融資逆勢買", "融資維持率創低反彈", "量縮整理→出量突破")
STALE_DAYS = 7          # 融資落後股價超過此天數 = 過期
DROP_PCT = 3.5          # 逆勢策略的大跌門檻（與策略 default 一致）
MARGIN_WINDOW = 5       # 逆勢策略「近N筆融資增」視窗


def _price_tail(ticker: str, n: int = 3):
    p = DATA / f"{ticker}.csv"
    if not p.exists():
        return None
    try:
        d = pd.read_csv(p, usecols=[0, 4])
        d.columns = ["date", "close"]
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d = d.dropna(subset=["close"]).tail(n)
        d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None)
        return d
    except Exception:
        return None


def _margin_tail(ticker: str, n: int = MARGIN_WINDOW + 2):
    code = ticker.replace(".TWO", "").replace(".TW", "").strip()
    p = MARGIN_DIR / f"{code}_margin.csv"
    if not p.exists():
        return None
    try:
        m = pd.read_csv(p, usecols=["date", "margin_balance"])
        m["date"] = pd.to_datetime(m["date"])
        return m.dropna().tail(n)
    except Exception:
        return None


def verify_row(row: pd.Series) -> str:
    """回傳 ""（通過）或以「；」串起的錯誤原因。"""
    ticker = str(row["代碼"]).strip()
    strat = str(row.get("策略", ""))
    errs = []

    px = _price_tail(ticker)
    if px is None or px.empty:
        return "❌ 無股價資料"
    last_px_date = px["date"].iloc[-1]

    # ① 訊號日期應等於股價最後日（用舊資料算的訊號 = 過期訊號）
    sig_date = pd.to_datetime(str(row.get("日期", "")), errors="coerce")
    if pd.notna(sig_date) and (last_px_date - sig_date).days > 5:
        errs.append(f"訊號日過舊({str(sig_date.date())})")

    # ② 當日% 一致性（重算 vs 表格）
    if len(px) >= 2 and "當日%" in row.index and pd.notna(row["當日%"]):
        chg = (px["close"].iloc[-1] / px["close"].iloc[-2] - 1) * 100
        if abs(chg - float(row["當日%"])) > 0.6:
            errs.append(f"當日%不符(實{chg:+.1f})")
        if chg <= -9.4:
            errs.append("當日跌停")

    # ③ 融資類策略：資料新鮮度 + 條件重驗
    if any(k in strat for k in MARGIN_STRATS):
        mg = _margin_tail(ticker)
        if mg is None or mg.empty:
            errs.append("無融資資料")
        else:
            lag = (last_px_date - mg["date"].iloc[-1]).days
            if lag > STALE_DAYS:
                errs.append(f"融資過期(至{mg['date'].iloc[-1].date()})")
            else:
                bal = mg["margin_balance"].astype(float)
                if "大跌中融資逆勢買" in strat:
                    # 條件A：訊號日附近真的大跌（近2日內有 ≤ -DROP_PCT）
                    if len(px) >= 3:
                        chgs = px["close"].pct_change().dropna() * 100
                        if not (chgs <= -DROP_PCT).any():
                            errs.append(f"近2日無大跌(≤-{DROP_PCT}%)")
                    # 條件B：近N筆融資餘額真的在增（用實際資料列，不 ffill）
                    if len(bal) > MARGIN_WINDOW:
                        diff = bal.iloc[-1] - bal.iloc[-1 - MARGIN_WINDOW]
                        if diff <= 0:
                            errs.append(f"融資未增(近{MARGIN_WINDOW}筆{diff:+.0f}張)")
                if "量縮整理" in strat:
                    # 出量檢查（用表格量比欄，寬鬆 2x）＋ 融資沒大逃（近5筆減>5%）
                    vr = row.get("量比(vs均)", None)
                    if vr is not None and pd.notna(vr) and float(vr) < 2.0:
                        errs.append(f"量比不足({vr}x)")
                    if len(bal) > MARGIN_WINDOW:
                        pct = (bal.iloc[-1] / max(bal.iloc[-1 - MARGIN_WINDOW], 1) - 1) * 100
                        if pct < -5:
                            errs.append(f"融資大減({pct:+.0f}%)")

    return "；".join(f"❌{e}" if not e.startswith("❌") else e for e in errs)


def verify_file(path: str | Path, write_back: bool = True) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        print("（空檔，無訊號可查）")
        return df
    df["檢核"] = df.apply(lambda r: verify_row(r) or "✅", axis=1)
    bad = df[df["檢核"] != "✅"]
    print(f"查核 {path.name}：共 {len(df)} 筆，通過 {len(df) - len(bad)}，紅牌 {len(bad)}")
    if not bad.empty:
        cols = [c for c in ["訊號等級", "策略", "代碼", "當日%", "檢核"] if c in bad.columns]
        print(bad[cols].to_string(index=False))
    if write_back:
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"（檢核欄已寫回 {path.name}，今日選股頁會直接顯示）")
    return df


def latest_file():
    files = sorted(glob.glob(str(ROOT / "scan_results" / "signals_*.csv")))
    return files[-1] if files else None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="選股訊號獨立查核")
    ap.add_argument("--file", default=None, help="指定 signals CSV；預設查最新")
    args = ap.parse_args()
    target = args.file or latest_file()
    if not target:
        print("找不到 scan_results/signals_*.csv")
        sys.exit(1)
    verify_file(target)

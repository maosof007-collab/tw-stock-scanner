"""
signal_history.py — 訊號回查(這檔股票,策略以前找到過嗎?)
=================================================================
Key 股號回答三件事:
  ① 歷史掃描出現過嗎?哪幾天、什麼等級、哪個策略(掃描檔 2026-06-03 起)
  ② 有沒有加入過持倉(對照績效追蹤紀錄)
  ③ 為什麼當初沒選到 —— BUY出現過但沒勾?還是只到觀察級卡在哪個條件?
"""
from __future__ import annotations
import glob
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


def scan_history(code: str) -> pd.DataFrame:
    """歷史掃描檔中該股所有出現紀錄。"""
    code = str(code).strip()
    rows = []
    for f in sorted(glob.glob(str(ROOT / "scan_results" / "signals_*.csv"))):
        day = Path(f).stem.split("_")[-1]
        try:
            d = pd.read_csv(f, encoding="utf-8-sig")
            m = d[d["代碼"].astype(str).str.startswith(code)]
            for _, r in m.iterrows():
                rows.append({
                    "掃描日": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                    "等級": str(r.get("訊號等級", "")),
                    "策略": str(r.get("策略", "")),
                    "收盤": r.get("收盤"), "停損": r.get("停損"),
                    "狀態": str(r.get("狀態", "")),
                    "檢核": str(r.get("檢核", "") or ""),
                })
        except Exception:
            continue
    return pd.DataFrame(rows)


def portfolio_history(code: str, user: str = "管理者") -> pd.DataFrame:
    """該股在持倉紀錄(含已出場)中的紀錄。"""
    try:
        from portfolio import load_portfolio
        df = load_portfolio(user)
        if df.empty:
            return pd.DataFrame()
        m = df[df["ticker"].astype(str).str.startswith(str(code))]
        return m[["ticker", "entry_date", "entry_price", "exit_date",
                  "exit_price", "status", "strategy"]].copy()
    except Exception:
        return pd.DataFrame()


def diagnose(code: str, hist: pd.DataFrame, pf: pd.DataFrame,
             scan_start: str = "2026-06-03") -> list[str]:
    """規則式診斷「為什麼當初沒選到」。回傳條列句。"""
    out = []
    if hist.empty:
        out.append(f"掃描紀錄({scan_start} 起)中**從未出現**——所有策略的進場條件都沒觸發過;"
                   "可到頁13看它的月營收/籌碼,或用下方K線看各策略歷史訊號位置。")
        return out
    n_total = len(hist)
    buys = hist[hist["等級"].str.startswith("BUY")]
    days = hist["掃描日"].nunique()
    out.append(f"共出現 **{n_total} 筆**(跨 {days} 個掃描日)。")
    if not buys.empty:
        bdays = buys["掃描日"].tolist()
        strats = "、".join(sorted(set(buys["策略"])))
        out.append(f"其中 **BUY 級 {len(buys)} 次**:{('、'.join(bdays))}(策略:{strats})。")
        if pf.empty:
            out.append("⚠️ **當初沒選到的原因:訊號有出、但沒有加入持倉**——"
                       "BUY 清單一天常有數十檔,這檔被淹沒了。改善方式:用風險上限開關先縮小清單、"
                       "點K線彈窗看「為什麼選它」再決定。")
        else:
            held_dates = set(str(d)[:10] for d in pf["entry_date"])
            missed = [d for d in bdays if d not in held_dates]
            if missed:
                out.append(f"持倉紀錄有加入過,但 {('、'.join(missed))} 這些 BUY 日沒有進場。")
            else:
                out.append("✅ BUY 日都有對應的持倉紀錄——其實有選到。")
    else:
        top_state = hist["狀態"].mode().iloc[0] if not hist["狀態"].empty else ""
        grades = "、".join(sorted(set(hist["等級"])))
        out.append(f"**從未到 BUY 級**(最高只到 {grades})——"
                   f"最常見狀態:「{top_state}」,代表卡在該策略的最後條件;"
                   "它一直在觀察名單、但進場訊號沒成立,不是被漏看。")
    bad = hist[hist["檢核"].str.contains("❌", na=False)]
    if not bad.empty:
        out.append(f"另有 {len(bad)} 筆曾被檢核紅牌(資料/條件不符),屬正確剔除。")
    return out

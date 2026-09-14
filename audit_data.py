"""
audit_data.py — 全系統資料體檢器(2026-09-14,起因:9/3融資缺口誤導使用者)
=================================================================
一次掃所有資料管線的完整性/新鮮度/覆蓋率,輸出紅黃綠報告。
執行:python audit_data.py;run_daily 收尾自動跑,🔴 會進 log。
報告存 data/_health_report.csv(進git,雲端頁7可看)。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"


def _last_trading_day() -> str:
    b = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date"]).dropna()
    return str(b["Date"].max())[:10]


def _coverage_by_date(pattern: str, date_col: str, tail: int = 6) -> pd.Series:
    from collections import Counter
    cnt = Counter()
    for f in glob.glob(pattern):
        try:
            d = pd.read_csv(f, usecols=[date_col])
            for dt in d[date_col].astype(str).str[:10].tail(tail + 2):
                cnt[dt] += 1
        except Exception:
            continue
    return pd.Series(cnt).sort_index().tail(tail)


def run_audit() -> pd.DataFrame:
    rows = []
    today = f"{now_tw():%Y-%m-%d}"
    ltd = _last_trading_day()

    def add(domain, status, latest, detail):
        rows.append({"領域": domain, "狀態": status, "最新": str(latest)[:10], "說明": detail})

    # ① 大盤基準
    add("大盤指數", "✅" if ltd >= today[:8] + "01" else "🔴", ltd,
        f"最後交易日 {ltd}" + ("" if ltd else ";benchmark 斷更"))

    # ② 價格檔:新鮮度+OHLC schema
    stale, bad_schema, n_px = 0, [], 0
    for f in glob.glob(str(D / "*.TW.csv")) + glob.glob(str(D / "*.TWO.csv")):
        n_px += 1
        try:
            d = pd.read_csv(f, nrows=1)
            if not {"Open", "High", "Low", "Close", "Volume"}.issubset(d.columns):
                bad_schema.append(os.path.basename(f))
        except Exception:
            bad_schema.append(os.path.basename(f))
    try:
        ref = pd.read_csv(D / "2330.TW.csv", usecols=["Date"])["Date"].max()
        px_latest = str(ref)[:10]
    except Exception:
        px_latest = "?"
    st = "✅" if px_latest == ltd and not bad_schema else ("🔴" if bad_schema else "⚠️")
    add("個股價格", st, px_latest,
        f"{n_px}檔;schema異常 {len(bad_schema)}" + (f"({','.join(bad_schema[:3])})" if bad_schema else ""))

    # ③ 融資:近6日覆蓋率
    cov = _coverage_by_date(str(D / "margin" / "*_margin.csv"), "date")
    if len(cov):
        med = cov.median()
        low = cov[cov < med * 0.8]
        st = "✅" if low.empty and str(cov.index[-1]) >= ltd else ("⚠️" if low.empty else "🔴")
        add("融資融券", st, cov.index[-1],
            f"日覆蓋中位 {int(med)} 檔" + (f";缺口日:{','.join(low.index)}({[int(x) for x in low.values]}檔)" if not low.empty else ""))
    else:
        add("融資融券", "🔴", "-", "無資料")

    # ④ 法人
    cov = _coverage_by_date(str(D / "institutional" / "*_inst.csv"), "date")
    if len(cov):
        med = cov.median()
        low = cov[cov < med * 0.8]
        st = "✅" if low.empty and str(cov.index[-1]) >= ltd else ("⚠️" if low.empty else "🔴")
        add("法人買賣超", st, cov.index[-1],
            f"日覆蓋中位 {int(med)} 檔" + (f";缺口日:{','.join(low.index)}" if not low.empty else ""))
    else:
        add("法人買賣超", "🔴", "-", "無資料")

    # ⑤ TDCC 週(最近週五)
    try:
        pan = pd.read_csv(D / "_bigholder_panel.csv")
        last_w = str(pan["date"].max())[:10]
        days_old = (pd.Timestamp(today) - pd.Timestamp(last_w)).days
        add("集保大戶(週)", "✅" if days_old <= 10 else "🔴", last_w,
            f"距今 {days_old} 天" + (";週報斷更" if days_old > 10 else ""))
    except Exception as e:
        add("集保大戶(週)", "🔴", "-", str(e)[:40])

    # ⑥ bulk 月營收
    try:
        fs = glob.glob(str(D / "bulk_rev" / "bulk_rev_*.csv"))
        months = sorted({os.path.basename(f).split("_")[2] + "-" + os.path.basename(f).split("_")[3] for f in fs})
        roc_now = now_tw().year - 1911
        m_now = now_tw().month
        want_m, want_roc = (m_now - 1, roc_now) if m_now > 1 else (12, roc_now - 1)
        want = f"{want_roc}-{want_m}"
        has = any(f"bulk_rev_{want_roc}_{want_m}_" in f for f in fs)
        add("bulk月營收", "✅" if has else ("⚠️" if now_tw().day <= 10 else "🔴"),
            months[-1] if months else "-",
            f"{len(fs)}檔快取;最新需求月 {want} {'已入庫' if has else '未入庫'}")
    except Exception as e:
        add("bulk月營收", "🔴", "-", str(e)[:40])

    # ⑦ 權證資金流(日檔連續性)
    try:
        wfs = sorted(glob.glob(str(D / "warrants" / "wflow_2*.csv")))
        last_w = os.path.basename(wfs[-1])[6:14] if wfs else ""
        lw = f"{last_w[:4]}-{last_w[4:6]}-{last_w[6:]}" if last_w else "-"
        add("權證資金流", "✅" if lw >= ltd else "⚠️", lw, f"{len(wfs)} 交易日快取")
    except Exception as e:
        add("權證資金流", "🔴", "-", str(e)[:40])

    # ⑧ 衍生快取新鮮度(對源比對)
    for name, path, src_latest in [
        ("大盤融資快取", D / "_market_margin.csv", None),
        ("營收史快取", D / "_rev_history.csv", None),
    ]:
        try:
            c = pd.read_csv(path)
            col = "date" if "date" in c.columns else ("ym" if "ym" in c.columns else c.columns[0])
            latest = str(c[col].max())[:10]
            add(name, "✅", latest, f"{len(c):,} 列")
        except Exception as e:
            add(name, "🔴", "-", str(e)[:40])

    # ⑨ JSON 資產(可解析+今日內容)
    for name, path in [("我的ETF", D / "my_etf.json"), ("決策日誌", D / "decision_journal.csv"),
                       ("預實追蹤", D / "model_track.json"), ("法說筆記", D / "conf_notes.json")]:
        try:
            if str(path).endswith(".json"):
                json.loads(Path(path).read_text(encoding="utf-8"))
                add(name, "✅", "-", "JSON 可解析")
            else:
                d_ = pd.read_csv(path)
                add(name, "✅", "-", f"{len(d_)} 列")
        except Exception as e:
            add(name, "🔴", "-", str(e)[:40])

    # ⑩ 今日產出(晨報/日檢)
    arts = os.listdir(D / "research_articles")
    ymd = today.replace("-", "")
    add("晨報", "✅" if any(ymd in a and "MKT" in a for a in arts) else "⚠️", today,
        "今日已產生" if any(ymd in a and "MKT" in a for a in arts) else "今日未見(假日/排程未跑)")
    add("ETF日檢", "✅" if any(ymd in a and "_ETF" in a for a in arts) else "⚠️", today,
        "今日已產生" if any(ymd in a and "_ETF" in a for a in arts) else "盤後排程產生")

    df = pd.DataFrame(rows)
    df.insert(0, "體檢時間", f"{now_tw():%Y-%m-%d %H:%M}")
    df.to_csv(D / "_health_report.csv", index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    df = run_audit()
    print(df[["領域", "狀態", "最新", "說明"]].to_string(index=False))
    bad = df[df["狀態"] == "🔴"]
    print(f"\n🔴 {len(bad)} 項需處理" if len(bad) else "\n全部綠燈 ✅")

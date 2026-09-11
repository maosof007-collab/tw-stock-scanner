"""
etf_holdings.py — 主動式 ETF 持倉追蹤(每日快照+加減碼 diff)
=================================================================
來源:MoneyDJ ETF 持股頁(主動式 ETF 每日更新 top10+權重+持股數)。
快照:data/etf_holdings/{etfid}_{YYYYMMDD}.csv;diff=經理人加減碼訊號。
v1 追蹤 top10(權重佔 67%,已覆蓋主要動作);全持股待接 PCF。
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
HDIR = ROOT / "data" / "etf_holdings"
ETFS = ["00981A"]          # 要追蹤的主動式 ETF
_HDR = {"User-Agent": "Mozilla/5.0"}


def fetch_snapshot(etfid: str) -> pd.DataFrame | None:
    """抓當前 top10 持股 → [code, name, weight, shares, asof]。"""
    url = f"https://www.moneydj.com/etf/x/basic/basic0007.xdjhtm?etfid={etfid}.TW"
    r = requests.get(url, timeout=40, headers=_HDR)
    r.encoding = "utf-8"
    html = r.text
    m = re.search(r"資料日期[::]?\s*(\d{4}[/-]\d{2}[/-]\d{2})", html)
    asof = m.group(1).replace("/", "-") if m else f"{now_tw():%Y-%m-%d}"
    best = None
    try:
        for t in pd.read_html(io.StringIO(html)):
            cols = "".join(str(c) for c in t.columns)
            # 持股表特徵:同時有 名稱+比例+股數(排除產業配置表)
            if "名稱" in cols and ("比例" in cols or "權重" in cols) and "股數" in cols:
                best = t
                break
    except Exception:
        return None
    if best is None:
        return None
    best.columns = [str(c) for c in best.columns]
    code_col = next((c for c in best.columns if "名稱" in c), best.columns[0])
    w_col = next((c for c in best.columns if "比例" in c or "權重" in c), None)
    s_col = next((c for c in best.columns if "股數" in c), None)
    rows = []
    for _, r_ in best.iterrows():
        raw = str(r_[code_col])
        cm = re.search(r"\((\d{4,6})[A-Z]?\.TW", raw) or re.search(r"(\d{4,6})", raw)
        if not cm:
            continue
        nm = raw.split("(")[0].strip()
        w = pd.to_numeric(str(r_[w_col]).replace("%", ""), errors="coerce") if w_col else None
        sh = pd.to_numeric(str(r_[s_col]).replace(",", ""), errors="coerce") if s_col else None
        rows.append({"code": cm.group(1), "name": nm, "weight": w,
                     "shares": sh, "asof": asof})
    return pd.DataFrame(rows) if rows else None


def save_daily(etfid: str) -> str:
    """存快照(以資料日期命名,重複自動略過)。回傳狀態字串。"""
    HDIR.mkdir(parents=True, exist_ok=True)
    df = fetch_snapshot(etfid)
    if df is None or df.empty:
        return f"{etfid}: 抓取失敗"
    ymd = df["asof"].iloc[0].replace("-", "")
    p = HDIR / f"{etfid}_{ymd}.csv"
    if p.exists():
        return f"{etfid}: {ymd} 已有快照"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return f"{etfid}: 新快照 {ymd}({len(df)}檔)"


def diff_latest(etfid: str) -> pd.DataFrame:
    """最近兩份快照的加減碼:新進/剔除/張數增減。"""
    fs = sorted(HDIR.glob(f"{etfid}_2*.csv"))
    if len(fs) < 2:
        return pd.DataFrame()
    old = pd.read_csv(fs[-2], dtype={"code": str})
    new = pd.read_csv(fs[-1], dtype={"code": str})
    m = new.merge(old[["code", "weight", "shares"]], on="code",
                  how="outer", suffixes=("", "_前"), indicator=True)
    m["動作"] = m["_merge"].map({"left_only": "🆕 新進榜", "right_only": "🚪 跌出榜",
                                "both": ""})
    m["張數增減"] = ((m["shares"].fillna(0) - m["shares_前"].fillna(0)) / 1000).round(0)
    m.loc[(m["_merge"] == "both") & (m["張數增減"] > 0), "動作"] = "➕ 加碼"
    m.loc[(m["_merge"] == "both") & (m["張數增減"] < 0), "動作"] = "➖ 減碼"
    m["權重Δ"] = (m["weight"].fillna(0) - m["weight_前"].fillna(0)).round(2)
    return m[["code", "name", "weight", "權重Δ", "張數增減", "動作", "asof"]].sort_values(
        "weight", ascending=False)


def who_holds(code: str) -> pd.DataFrame:
    """反查:追蹤中的 ETF 誰持有這檔(最新快照)。"""
    out = []
    for etfid in ETFS:
        fs = sorted(HDIR.glob(f"{etfid}_2*.csv"))
        if not fs:
            continue
        df = pd.read_csv(fs[-1], dtype={"code": str})
        hit = df[df["code"] == code]
        if not hit.empty:
            out.append({"ETF": etfid, "權重%": hit["weight"].iloc[0],
                        "持股(張)": round(float(hit["shares"].iloc[0]) / 1000),
                        "資料日": hit["asof"].iloc[0]})
    return pd.DataFrame(out)


if __name__ == "__main__":
    for e in ETFS:
        print(save_daily(e))
        d = diff_latest(e)
        if not d.empty:
            print(d.to_string(index=False))

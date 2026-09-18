"""
mmap_funnel.py — 籌碼選股地圖(五關串聯漏斗)
=================================================================
①A 長多位階(240MA翻揚+站上) ②B1 大錢進場(大戶連升+戶數降+法人買)
③B2 量縮不跌(賣壓消失) ④確認啟動(量增突破平台) ⑤D/E/F 強化欄。
回測(2016-2026,2,617筆,A+B2+④價量段):60日>30%比率 12.6%(基準7.6%),
2026年 34.8%;虧>20%僅8.2%=右尾不對稱。B1 籌碼層僅能即時應用(TDCC深度限制)。
產出:data/_mmap_pool.csv(每日 run_daily 重掃,雲端可讀)。
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
POOL = ROOT / "data" / "_mmap_pool.csv"


def scan_today(min_lots: int = 200) -> dict:
    """全市場跑五關。回傳 {funnel: 各關檔數, pool: 最終表(含各關✓)}。"""
    # 籌碼層資料(B1/E)
    try:
        pan = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv")
        pan_dates = pan["date"].tolist()
    except Exception:
        pan = pd.DataFrame()
    try:
        dr = pd.read_csv(ROOT / "data" / "inst_dump_rate.csv", dtype={"code": str}) \
               .set_index("code")["dump_rate"]
    except Exception:
        dr = pd.Series(dtype=float)
    try:
        rev = pd.read_csv(ROOT / "data" / "_rev_history.csv", dtype={"code": str})
        rev_last = rev.sort_values("ym").groupby("code").tail(1).set_index("code")
    except Exception:
        rev_last = pd.DataFrame()
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))

    n_all = n_a = n_b1 = n_b2 = 0
    rows = []
    for f in glob.glob(str(ROOT / "data" / "*.TW.csv")) + \
             glob.glob(str(ROOT / "data" / "*.TWO.csv")):
        code = os.path.basename(f).split(".")[0]
        if not code.isdigit():
            continue
        try:
            d = pd.read_csv(f, usecols=["Date", "Close", "Volume"]).dropna().sort_values("Date")
            if len(d) < 300:
                continue
            c = pd.to_numeric(d["Close"], errors="coerce").reset_index(drop=True)
            v = pd.to_numeric(d["Volume"], errors="coerce").reset_index(drop=True)
            if v.tail(20).mean() < min_lots * 1000:
                continue
            n_all += 1
            ma240 = c.rolling(240).mean()
            # ── A 位階:站上240MA 且 240MA 翻揚 ──
            A = bool(c.iloc[-1] > ma240.iloc[-1] and ma240.iloc[-1] > ma240.iloc[-21])
            if not A:
                continue
            n_a += 1
            # ── B1 大錢進場(大戶近3週斜率>0;無資料=None不擋,標註) ──
            b1 = None
            if not pan.empty and code in pan.columns:
                s = pan[code].dropna().tail(4)
                if len(s) >= 3:
                    b1 = bool(s.iloc[-1] > s.iloc[0])
            if b1 is False:
                continue
            n_b1 += 1
            # ── B2 量縮不跌 ──
            mv20 = float(v.tail(20).mean())
            mv60 = float(v.tail(60).mean())
            hi60 = float(c.tail(60).max())
            lo20 = float(c.tail(20).min())
            lo60 = float(c.tail(60).min())
            shrink = mv20 < mv60 * 0.8
            hold = (c.iloc[-1] / hi60 > 0.85) and (lo20 >= lo60)
            B2 = bool(shrink and hold)
            # ── ④ 突破(近3日內:量≥2×前20均 且 破40日平台高) ──
            hi40 = c.shift(1).rolling(40).max()
            br_days = [(v.iloc[i] >= 2 * v.iloc[i - 20:i].mean()) and (c.iloc[i] > hi40.iloc[i])
                       for i in range(len(c) - 3, len(c))]
            BR = any(br_days)
            if not (B2 or BR):
                continue
            n_b2 += 1
            # ── D/E/F 強化欄 ──
            yoy = None
            if code in rev_last.index:
                yoy = round(float(rev_last.loc[code, "yoy"]), 1)
            dump = float(dr.get(code, np.nan))
            big_d = None
            if not pan.empty and code in pan.columns:
                s = pan[code].dropna().tail(4)
                if len(s) >= 2:
                    big_d = round(float(s.iloc[-1] - s.iloc[0]), 2)
            rows.append({
                "代號": code, "名稱": nm.get(code, ""),
                "收盤": round(float(c.iloc[-1]), 1),
                "狀態": "🎯 剛突破" if BR else "⏳ 蓄勢(量縮不跌)",
                "A位階": "✓", "B1大戶": ("✓" if b1 else "?"),
                "B2量縮不跌": "✓" if B2 else "—",
                "④突破": "✓" if BR else "—",
                "距60日高%": round((float(c.iloc[-1]) / hi60 - 1) * 100, 1),
                "量比": round(float(v.iloc[-1]) / mv20, 2) if mv20 else None,
                "催化:最新YoY%": yoy,
                "大戶4週Δpp": big_d,
                "反證:倒貨率%": round(dump) if not np.isnan(dump) else None,
            })
        except Exception:
            continue
    pool = pd.DataFrame(rows)
    if not pool.empty:
        pool = pool.sort_values(["狀態", "距60日高%"], ascending=[True, False])
        pool.insert(0, "掃描日", f"{now_tw():%Y-%m-%d}")
        pool.to_csv(POOL, index=False, encoding="utf-8-sig")
    funnel = {"全市場(流動性過)": n_all, "A 長多位階": n_a,
              "B1 大戶不減": n_b1, "B2/④ 量縮不跌或突破": n_b2}
    try:
        import json
        (ROOT / "data" / "_mmap_funnel.json").write_text(
            json.dumps(funnel, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return {"funnel": funnel, "pool": pool}


def load_funnel() -> dict:
    try:
        import json
        return json.loads((ROOT / "data" / "_mmap_funnel.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_pool() -> pd.DataFrame:
    if POOL.exists():
        return pd.read_csv(POOL, dtype={"代號": str})
    return pd.DataFrame()


if __name__ == "__main__":
    r = scan_today()
    print(r["funnel"])
    print(r["pool"].head(20).to_string(index=False))

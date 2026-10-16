# -*- coding: utf-8 -*-
"""disposal.py — 處置股名單(TWSE API;回測見文章庫 DISPOSAL 筆記:處置股不接刀)。"""
from __future__ import annotations
import re
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "_disposal_now.csv"


def refresh_current() -> pd.DataFrame:
    """抓近45日公告,保留「今天仍在處置期間」者。"""
    t = date.today()
    sd = (t - timedelta(days=45)).strftime("%Y%m%d")
    r = requests.get(
        f"https://www.twse.com.tw/announcement/punish?response=json&startDate={sd}&endDate={t:%Y%m%d}",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    rows = []
    for row in r.json().get("data", []):
        code = str(row[2]).strip()
        if len(code) != 4 or not code.isdigit():
            continue
        m = re.findall(r"(\d{3})/(\d{2})/(\d{2})", str(row[6]))
        if len(m) < 2:
            continue
        e = f"{int(m[1][0])+1911}-{m[1][1]}-{m[1][2]}"
        if e >= f"{t:%Y-%m-%d}":
            rows.append({"code": code, "name": row[3], "end": e, "nth": row[7]})
    df = pd.DataFrame(rows).drop_duplicates(subset=["code"])
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    return df


def current_set() -> set[str]:
    if OUT.exists():
        try:
            return set(pd.read_csv(OUT, dtype=str)["code"])
        except Exception:
            pass
    return set()

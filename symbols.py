"""
symbols.py — 代號/名稱雙向解析(輸入「晶技」=輸入「3042」)
=================================================================
resolve(q) → (code, name) 或 (None, None)。
規則:數字→查名;文字→完全相符 > 開頭相符 > 包含(取第一個)。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


@lru_cache(maxsize=1)
def _table() -> pd.DataFrame:
    try:
        return pd.read_csv(ROOT / "data" / "stock_list.csv",
                           encoding="utf-8-sig", dtype=str)[["code", "name"]]
    except Exception:
        return pd.DataFrame(columns=["code", "name"])


def resolve(q: str) -> tuple[str | None, str | None]:
    q = (q or "").strip()
    if not q:
        return None, None
    t = _table()
    if t.empty:
        return (q, q) if q.isdigit() else (None, None)
    if q.isdigit():
        hit = t[t["code"] == q]
        return (q, hit["name"].iloc[0]) if len(hit) else (q, q)
    for m in (t[t["name"] == q],
              t[t["name"].str.startswith(q, na=False)],
              t[t["name"].str.contains(q, na=False, regex=False)]):
        if len(m):
            return m["code"].iloc[0], m["name"].iloc[0]
    return None, None

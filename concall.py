# -*- coding: utf-8 -*-
"""
concall.py — 法說簡報自動管線(finmoconf 索引 → MOPS PDF → 全文素材)
=================================================================
索引源:finmoconf.diveinvest.net/company/{code}(收錄2000+家歷年法說,直指MOPS PDF)。
fetch_latest(code):下載該股最新中文簡報→data/concalls/{code}_{ymd}.pdf+.txt。
latest_text(code):給快分析/財經報當素材。run_daily 對追蹤股每日增量(已有則跳過)。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DIR = ROOT / "data" / "concalls"
DIR.mkdir(parents=True, exist_ok=True)
_HDR = {"User-Agent": "Mozilla/5.0"}


def fetch_index(code: str) -> list[tuple[str, str]]:
    """[(ymd, pdf_url)] 新到舊(僅中文 M 版)。"""
    r = requests.get(f"https://finmoconf.diveinvest.net/company/{code}",
                     headers=_HDR, timeout=30)
    if r.status_code != 200:
        return []
    urls = re.findall(
        rf"https://mopsov\.twse\.com\.tw/nas/STR/{code}(\d{{8}})M00\d\.pdf", r.text)
    seen, out = set(), []
    for ymd in urls:
        if ymd not in seen:
            seen.add(ymd)
            out.append((ymd, f"https://mopsov.twse.com.tw/nas/STR/{code}{ymd}M001.pdf"))
    out.sort(reverse=True)
    return out


def fetch_latest(code: str) -> Path | None:
    """下載最新一場(已有檔案就直接回傳,不重抓)。"""
    existing = sorted(DIR.glob(f"{code}_*.pdf"), reverse=True)
    idx = fetch_index(code)
    if not idx:
        return existing[0] if existing else None
    ymd, url = idx[0]
    p = DIR / f"{code}_{ymd}.pdf"
    if p.exists():
        return p
    try:
        r = requests.get(url, headers=_HDR, timeout=40)
        if r.status_code == 200 and len(r.content) > 50_000:
            p.write_bytes(r.content)
            _extract(p)
            return p
    except Exception:
        pass
    return existing[0] if existing else None


def _extract(pdf: Path) -> Path:
    import pypdf
    txt = pdf.with_suffix(".txt")
    try:
        r = pypdf.PdfReader(str(pdf))
        pages = [f"=== 頁{i} ===\n" + (pg.extract_text() or "")
                 for i, pg in enumerate(r.pages, 1)]
        txt.write_text("\n\n".join(pages), encoding="utf-8")
    except Exception:
        txt.write_text("", encoding="utf-8")
    return txt


def latest_text(code: str, cap: int = 6000) -> str:
    """最新法說全文(截斷)+場次日期;沒有本地檔就即時抓一次。"""
    p = fetch_latest(code)
    if p is None:
        return ""
    txt = p.with_suffix(".txt")
    if not txt.exists():
        _extract(p)
    body = txt.read_text(encoding="utf-8")[:cap]
    ymd = p.stem.split("_")[-1]
    return f"(法說日期 {ymd[:4]}/{ymd[4:6]}/{ymd[6:]})\n{body}" if body.strip() else ""


def refresh_tracked(sleep: float = 1.0) -> int:
    """追蹤股增量抓最新法說(已有則跳過)。"""
    from fundamentals import tracked_codes
    n = 0
    for c in tracked_codes():
        before = set(DIR.glob(f"{c}_*.pdf"))
        p = fetch_latest(c)
        if p and p not in before:
            n += 1
        time.sleep(sleep)
    return n


if __name__ == "__main__":
    import sys
    c = sys.argv[1] if len(sys.argv) > 1 else "6207"
    print(fetch_index(c)[:3])
    print("latest:", fetch_latest(c))
    print(latest_text(c)[:200])

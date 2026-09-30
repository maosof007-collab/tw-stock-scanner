# -*- coding: utf-8 -*-
"""
report_inbox.py — 投顧報告收件匣(PDF 丟進來,系統自動消化成素材)
=================================================================
用法:把券商 App/投顧網站下載的報告 PDF 丟進 data/reports_inbox/
     (檔名帶代碼最好,如「2464_中信_20260917.pdf」;沒帶也會從內文猜)。
ingest() 抽文字→辨識代碼→建索引;latest_for(code) 給快分析/財經報當素材。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
INBOX = ROOT / "data" / "reports_inbox"
TXT = INBOX / "txt"
INBOX.mkdir(parents=True, exist_ok=True)
TXT.mkdir(exist_ok=True)
INDEX = INBOX / "_index.csv"


def _detect_code(fname: str, text: str) -> str:
    m = re.search(r"(\d{4,6})", fname)
    if m:
        return m.group(1)
    # 內文猜:出現最多次的 (dddd) / dddd.TW / dddd TT
    cands = re.findall(r"[(（](\d{4})[)）]|(\d{4})\.TWO?|(\d{4})\s?TT", text[:5000])
    flat = [x for tup in cands for x in tup if x]
    if flat:
        return max(set(flat), key=flat.count)
    return ""


def ingest() -> int:
    """處理收件匣新 PDF:抽文→索引。回傳新處理件數。"""
    import pypdf
    idx = pd.read_csv(INDEX, dtype=str) if INDEX.exists() else \
        pd.DataFrame(columns=["file", "code", "title", "chars", "mtime"])
    done = set(idx["file"]) if len(idx) else set()
    n = 0
    for p in sorted(INBOX.glob("*.pdf")):
        if p.name in done:
            continue
        try:
            r = pypdf.PdfReader(str(p))
            text = "\n".join((pg.extract_text() or "") for pg in r.pages)
        except Exception:
            text = ""
        code = _detect_code(p.stem, text)
        title = next((ln.strip() for ln in text.splitlines() if len(ln.strip()) > 6), p.stem)
        (TXT / (p.stem + ".txt")).write_text(text, encoding="utf-8")
        idx = pd.concat([idx, pd.DataFrame([{
            "file": p.name, "code": code, "title": title[:80],
            "chars": len(text), "mtime": f"{p.stat().st_mtime:.0f}"}])],
            ignore_index=True)
        n += 1
    if n:
        idx.to_csv(INDEX, index=False, encoding="utf-8-sig")
    return n


def list_reports(code: str | None = None) -> pd.DataFrame:
    if not INDEX.exists():
        return pd.DataFrame(columns=["file", "code", "title", "chars", "mtime"])
    idx = pd.read_csv(INDEX, dtype=str)
    if code:
        idx = idx[idx["code"] == str(code)]
    return idx.sort_values("mtime", ascending=False)


def latest_for(code: str, n: int = 2, cap: int = 6000) -> str:
    """該股最新 n 份報告全文(截斷),給引擎當素材。"""
    idx = list_reports(code).head(n)
    parts = []
    for _, r in idx.iterrows():
        p = TXT / (Path(r["file"]).stem + ".txt")
        if p.exists():
            parts.append(f"◆ 報告《{r['title']}》\n" + p.read_text(encoding="utf-8")[:cap // max(len(idx), 1)])
    return "\n\n".join(parts)


if __name__ == "__main__":
    print("ingested:", ingest())
    print(list_reports().head(10).to_string(index=False))

# -*- coding: utf-8 -*-
"""
newspaper_gen.py — 個股專刊批量產生器(快分析引擎內容 → 報紙版式)
=================================================================
每檔一期:素材=快分析完整管線(價量/體檢/權證/財報/法說全文/收件匣報告/新聞)。
md2html 把引擎的 markdown 轉報紙 HTML;段落自動編 A1..;含家規裁決(規則算,引擎照抄)。
用法:python newspaper_gen.py 6426 3443 ...   (或 --batch 讀內建名單)
"""
from __future__ import annotations

import html as _html
import re
import sys

import pandas as pd

from newspaper import shell, save_issue
from twtime import now_tw


def md2html(md: str) -> tuple[str, list[str]]:
    """markdown → 報紙段落 HTML;回傳 (body, 段落標題list)。"""
    lines = md.splitlines()
    secs: list[tuple[str, list[str]]] = []
    cur_title, cur = "頭版", []
    for ln in lines:
        if ln.startswith("# "):            # 主標併入頭版首行
            cur.append(f'<div class="head1" style="font-size:30px">{_html.escape(ln[2:])}</div>')
        elif ln.startswith("## "):
            if cur:
                secs.append((cur_title, cur))
            cur_title, cur = ln[3:].strip(), []
        else:
            cur.append(ln)
    if cur:
        secs.append((cur_title, cur))

    def block(lines_: list[str]) -> str:
        out, i = [], 0
        while i < len(lines_):
            ln = lines_[i]
            if ln.strip().startswith("|") and i + 1 < len(lines_) \
                    and set(lines_[i + 1].replace("|", "").strip()) <= set("-: "):
                # markdown 表格
                hdr = [c.strip() for c in ln.strip().strip("|").split("|")]
                rows = []
                i += 2
                while i < len(lines_) and lines_[i].strip().startswith("|"):
                    rows.append([c.strip() for c in lines_[i].strip().strip("|").split("|")])
                    i += 1
                t = "<table><tr>" + "".join(f"<th>{_fmt(c)}</th>" for c in hdr) + "</tr>"
                for r in rows:
                    t += "<tr>" + "".join(f"<td>{_fmt(c)}</td>" for c in r) + "</tr>"
                out.append(t + "</table>")
                continue
            if ln.strip().startswith(("<div", "<table", "<p", "<tr")):
                out.append(ln)
            elif ln.strip().startswith(("- ", "* ")):
                out.append(f"<p>• {_fmt(ln.strip()[2:])}</p>")
            elif re.match(r"^\d+\.\s", ln.strip()):
                out.append(f"<p>{_fmt(ln.strip())}</p>")
            elif ln.strip():
                out.append(f"<p>{_fmt(ln.strip())}</p>")
            i += 1
        return "".join(out)

    def _fmt(s: str) -> str:
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return s

    body, titles = [], []
    for i, (t, ls) in enumerate(secs):
        titles.append(t[:6])
        body.append(f'<div class="sect" id="{i}"><div class="slabel">'
                    f'<span class="tag">A{i+1}</span><h2>{_html.escape(t)}</h2></div>'
                    + block(ls) + "</div>")
    return "".join(body), titles


def _ticker(code: str, name: str) -> str:
    try:
        for suf in (".TW", ".TWO"):
            try:
                px = pd.read_csv(f"data/{code}{suf}.csv").dropna(subset=["Close"])
                break
            except Exception:
                px = None
        c = px["Close"]
        import pretrade
        hc = pretrade.health_check(code)
        return (f'<b>{name} {code}</b> <span class="num">{c.iloc[-1]:.1f}</span>'
                f'|20日 <span class="up">{c.iloc[-1]/c.iloc[-21]-1:+.1%}</span>'
                f'|60日 <span class="num">{c.iloc[-1]/c.iloc[-61]-1:+.1%}</span>'
                f'|距年高 <span class="num">{c.iloc[-1]/c.tail(240).max()-1:+.1%}</span>'
                f'|體檢 {hc["verdict"][:12]}')
    except Exception:
        return f"<b>{name} {code}</b>"


def make_stock_issue(code: str) -> str | None:
    from analyst_report import generate_quick_analysis
    from symbols import resolve
    code, name = resolve(code)
    if not code:
        return None
    txt = generate_quick_analysis(code)
    if not txt or txt.startswith("（"):
        return None
    txt = txt.split("\n---\n")[0]                       # 去掉尾註
    body, titles = md2html(txt)
    ymd = f"{now_tw():%Y%m%d}"
    p = save_issue(code, ymd, shell(
        "TW·財經報", f"{name} {code}",
        f"{name}({code})專刊 · {now_tw():%Y/%m/%d}(引擎撰稿·素材含最新法說)",
        titles or ["內文"], _ticker(code, name), body,
        "素材:法說全文/系統籌碼/新聞(自動管線)·引擎撰稿·研究筆記非投資建議 · TW-BACKTEST 財經報"))
    return str(p)


BATCH = ["6426", "4977", "4908", "3234", "4979", "6442", "3363", "3163", "3450",
         "6207", "8027", "8064", "6664",
         "6643", "3443", "6533", "3035", "3661"]

if __name__ == "__main__":
    codes = sys.argv[1:] or BATCH
    if codes and codes[0] == "--batch":
        codes = BATCH
    for c in codes:
        try:
            r = make_stock_issue(c)
            print(c, "->", r or "FAIL")
        except Exception as e:
            print(c, "ERR", str(e)[:80])

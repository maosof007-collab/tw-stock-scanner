# -*- coding: utf-8 -*-
"""
newspaper.py — 財經報專刊引擎(報紙級 HTML 排版)
=================================================================
一期一檔:data/papers/{code}_{date}.html(自包含,st.components 直接渲染/瀏覽器可開)。
版式:報頭+段落導覽(A1..)+行情跑馬燈+頭版兩欄+各版卡片+十題測驗(<details>公布解答)。
本模組提供 CSS 殼與組裝函數;內容由結構化 dict 餵入(素材=法人報告/法說/使用者筆記)。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent
PAPERS = ROOT / "data" / "papers"
PAPERS.mkdir(parents=True, exist_ok=True)

CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#141210;color:#e8e2d6;font-family:'Noto Serif TC','PMingLiU',serif;line-height:1.75}
.wrap{max-width:1080px;margin:0 auto;padding:18px 22px 60px}
.masthead{text-align:center;border-bottom:3px double #6b6154;padding:18px 0 10px}
.masthead h1{font-size:56px;letter-spacing:14px;font-weight:900}
.masthead .sub{color:#b8ad9c;font-size:17px;margin-top:6px;letter-spacing:2px}
.stamp{display:inline-block;border:2.5px solid #c0392b;color:#c0392b;border-radius:8px;
  padding:2px 12px;font-size:20px;font-weight:900;transform:rotate(3deg);margin-left:14px}
.secnav{display:flex;flex-wrap:wrap;gap:2px;border-bottom:2px solid #6b6154;padding:8px 0;justify-content:center}
.secnav a{color:#e8e2d6;text-decoration:none;font-size:15px;padding:3px 10px;font-family:'Microsoft JhengHei',sans-serif}
.secnav a b{color:#d4553f;margin-right:4px}
.ticker{display:flex;gap:26px;overflow-x:auto;border-bottom:1px solid #3a352e;
  padding:10px 4px;font-family:'Microsoft JhengHei',monospace;font-size:15.5px;white-space:nowrap}
.ticker b{color:#fff}.up{color:#e5544a;font-weight:700}
.sect{margin-top:34px}
.slabel{display:flex;align-items:baseline;gap:10px;border-bottom:1px solid #3a352e;padding-bottom:6px}
.slabel .tag{background:#e8e2d6;color:#141210;font-weight:900;padding:1px 10px;font-size:16px;
  font-family:'Microsoft JhengHei',sans-serif}
.slabel h2{font-size:19px;color:#d8cfc0;font-weight:700;font-family:'Microsoft JhengHei',sans-serif}
.slabel .src{margin-left:auto;color:#8d8272;font-size:13px}
.head1{font-size:40px;line-height:1.35;font-weight:900;margin:18px 0 8px}
.deck{border-left:4px solid #d4553f;padding-left:14px;color:#cfc5b4;font-size:18px;margin:10px 0 14px}
.byline{color:#8d8272;font-size:13.5px;margin-bottom:14px}
.cols2{display:grid;grid-template-columns:1.75fr 1fr;gap:30px}
.dropcap::first-letter{font-size:64px;float:left;line-height:.9;padding:6px 10px 0 0;color:#d4553f;font-weight:900}
p{margin:10px 0;font-size:17px}
.sidebar{border-left:1px solid #3a352e;padding-left:22px}
.sidebar h3{border-bottom:2px solid #e8e2d6;padding-bottom:6px;font-size:20px;margin-bottom:10px;
  font-family:'Microsoft JhengHei',sans-serif}
.kv{margin:12px 0}.kv .k{color:#d4553f;font-weight:800;font-size:14.5px;font-family:'Microsoft JhengHei',sans-serif}
.kv .v{font-size:15.5px;color:#d8cfc0}
.card{background:#1d1a16;border:1px solid #3a352e;border-radius:10px;padding:14px 16px;margin:12px 0}
.card h4{color:#e8b64c;font-size:16.5px;margin-bottom:6px;font-family:'Microsoft JhengHei',sans-serif}
table{width:100%;border-collapse:collapse;margin:12px 0;font-family:'Microsoft JhengHei',sans-serif;font-size:15px}
th{border-bottom:2px solid #6b6154;color:#b8ad9c;text-align:left;padding:6px 8px;font-weight:700}
td{border-bottom:1px solid #2c2823;padding:6px 8px}
.num{font-family:'Share Tech Mono',monospace}
.hl{color:#e5544a;font-weight:800}.gd{color:#7fbf7f;font-weight:700}
.bigfact{background:#241f19;border:1px dashed #6b6154;border-radius:12px;padding:16px;text-align:center;margin:14px 0}
.bigfact .n{font-size:34px;color:#e8b64c;font-weight:900;font-family:'Microsoft JhengHei',sans-serif}
details{background:#1d1a16;border:1px solid #3a352e;border-radius:10px;padding:12px 16px;margin:10px 0;
  font-family:'Microsoft JhengHei',sans-serif}
summary{cursor:pointer;font-size:16px;font-weight:700;color:#e8e2d6}
details p{color:#b8ad9c;font-size:15px}
.footer{margin-top:44px;border-top:3px double #6b6154;padding-top:12px;color:#8d8272;
  font-size:13px;text-align:center;font-family:'Microsoft JhengHei',sans-serif}
</style>
"""


def shell(masthead: str, stamp: str, subtitle: str, nav: list[str],
          ticker_html: str, body_html: str, footer: str) -> str:
    nav_html = "".join(f'<a href="#{i}"><b>A{i+1}</b>{t}</a>' for i, t in enumerate(nav))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body>
<div class="wrap">
<div class="masthead"><h1>{masthead}<span class="stamp">{stamp}</span></h1>
<div class="sub">{subtitle}</div></div>
<div class="secnav">{nav_html}</div>
<div class="ticker">{ticker_html}</div>
{body_html}
<div class="footer">{footer}</div>
</div></body></html>"""


def save_issue(code: str, date: str, html: str) -> Path:
    p = PAPERS / f"{code}_{date}.html"
    p.write_text(html, encoding="utf-8")
    return p


def list_issues() -> list[dict]:
    out = []
    for p in sorted(PAPERS.glob("*.html"), reverse=True):
        code, _, date = p.stem.partition("_")
        out.append({"file": p.name, "code": code, "date": date, "path": str(p)})
    return out

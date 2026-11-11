# -*- coding: utf-8 -*-
"""
poster.py — 深度研究總整理「海報」引擎(2026-11-11 使用者指定版式)
=================================================================
範本:台玻(1802)深度研究總整理海報——亮底、密集卡片網格、紅字大數字、
綠勾結論、藍標題列、情境估值表、粉底風險卡。
與 newspaper.py(暗色報紙)並存:報紙=長文閱讀,海報=一屏總覽。
產出同樣進 data/papers/{code}海報_{date}.html,財經報頁同一選單可選。
"""
from __future__ import annotations

from newspaper import save_issue  # 同一儲存與列表機制

CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#dfe4ea;font-family:'Microsoft JhengHei','Noto Sans TC',sans-serif;
  color:#1c2733;line-height:1.5;font-size:14px}
.wrap{max-width:1180px;margin:0 auto;padding:10px}
.hd{background:linear-gradient(100deg,#0d2b52 0%,#123c6e 70%,#1b5fa8 100%);color:#fff;
  border-radius:8px;padding:10px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.hd h1{font-size:25px;font-weight:900;letter-spacing:.5px}
.hd h1 b{color:#ffd84d}
.hd .sub{font-size:13px;margin-top:3px;color:#cfe2ff;font-weight:700}
.hd .brand{text-align:right;font-size:11px;color:#9fc3f0;white-space:nowrap}
.hd .brand .bx{border:2px solid #ffd84d;color:#ffd84d;font-weight:900;font-size:13.5px;
  padding:2px 8px;border-radius:6px;display:inline-block;margin-bottom:2px}
.grid{columns:3 330px;column-gap:8px}
.col{display:contents}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(13,43,82,.2);overflow:hidden;
  break-inside:avoid;margin-bottom:8px}
.card .ct{background:#0d2b52;color:#fff;font-weight:900;font-size:14px;padding:5px 10px;
  display:flex;justify-content:space-between;align-items:baseline}
.card .ct small{color:#9fc3f0;font-weight:400;font-size:10.5px}
.card .cb{padding:8px 10px}
ul.ck{list-style:none}
ul.ck li{padding:4px 0 4px 26px;position:relative;font-size:14px;font-weight:600}
ul.ck li::before{content:"✔";position:absolute;left:2px;color:#15903f;font-weight:900}
ul.ck li.wn::before{content:"⚠";color:#d98400}
ul.ck li.xx::before{content:"✘";color:#c0392b}
ul.ck li b{color:#c0392b}
.bignums{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;text-align:center}
.bn{background:#f2f6fb;border:1px solid #d7e3f2;border-radius:8px;padding:8px 4px}
.bn .k{font-size:12px;color:#456;font-weight:700}
.bn .v{font-size:19px;font-weight:900;color:#c0392b;font-family:Arial,sans-serif;letter-spacing:-.5px}
.bn .d{font-size:11px;color:#567;font-weight:700}
.up2{color:#c0392b;font-weight:800}.dn2{color:#15903f;font-weight:800}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:2px 0}
th{background:#eaf1f9;color:#0d2b52;font-weight:900;padding:5px 7px;text-align:left;border:1px solid #d7e3f2}
td{padding:5px 7px;border:1px solid #e4ebf4;font-weight:600}
td.n{font-family:Arial;font-weight:800}
.rd{color:#c0392b}.gn{color:#15903f}.yl{background:#fff6d6}
.flow{display:flex;flex-direction:column;gap:5px}
.fbox{background:#eaf3ff;border:1.5px solid #8fb7e8;border-radius:8px;padding:6px 10px;
  font-size:13px;font-weight:700;text-align:center;color:#0d2b52}
.fbox small{display:block;color:#567;font-weight:600;font-size:11.5px}
.fbox.hot{background:#fff3f0;border-color:#e8a194;color:#a03022}
.farr{text-align:center;color:#1b5fa8;font-weight:900;line-height:.9}
.donutrow{display:flex;gap:12px;align-items:center}
.donut{width:128px;height:128px;border-radius:50%;flex:none;position:relative}
.donut::after{content:attr(data-c);position:absolute;inset:32px;background:#fff;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;color:#0d2b52;text-align:center}
.lg{font-size:13px;flex:1}
.lg div{display:flex;align-items:center;gap:6px;padding:2.5px 0;font-weight:700}
.lg i{width:11px;height:11px;border-radius:3px;flex:none}
.lg small{color:#567;font-weight:600;margin-left:auto;text-align:right}
.bars{display:flex;gap:16px;align-items:flex-end;height:96px;padding:4px 6px 0;justify-content:center}
.bar{width:52px;text-align:center;font-size:11.5px;font-weight:800;color:#345}
.bar i{display:block;border-radius:4px 4px 0 0}
.bar .pv{color:#c0392b;font-size:13px;font-family:Arial}
.risk{background:#fdf0f2}
.risk .ct{background:#8e2437}
.risk ul.ck li::before{content:"⚠";color:#c0392b}
.note{font-size:11.5px;color:#678;margin-top:4px;line-height:1.45}
.ft{text-align:center;font-size:11.5px;color:#56687e;margin-top:10px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
</style>
"""


def shell(title_html: str, subtitle: str, brand: str, cols: list[str], footer: str) -> str:
    grid = "".join(f'<div class="col">{c}</div>' for c in cols)
    return f"""<title>{subtitle[:20]}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{CSS}
<div class="wrap">
<div class="hd"><div><h1>{title_html}</h1><div class="sub">{subtitle}</div></div>
<div class="brand"><span class="bx">{brand}</span><br>TW·BACKTEST 深度研究</div></div>
<div class="grid">{grid}</div>
<div class="ft">{footer}</div></div>"""


def ud(x: float, txt: str = "") -> str:
    """上升/下降指標:▲紅/▼綠(台股紅漲綠跌);txt 省略時用 x 自己。"""
    t = txt or f"{x:+g}"
    if x > 0:
        return f'<span class="up2">▲{t.lstrip("+")}</span>'
    if x < 0:
        return f'<span class="dn2">▼{t.lstrip("-")}</span>'
    return f"<span>{t}</span>"


def card(title: str, body: str, src: str = "", extra_cls: str = "") -> str:
    s = f"<small>{src}</small>" if src else ""
    return f'<div class="card {extra_cls}"><div class="ct">{title}{s}</div><div class="cb">{body}</div></div>'


def checks(items: list[tuple[str, str]]) -> str:
    """items: [(kind, html)] kind ∈ ok/wn/xx"""
    cls = {"ok": "", "wn": ' class="wn"', "xx": ' class="xx"'}
    return "<ul class='ck'>" + "".join(f"<li{cls[k]}>{t}</li>" for k, t in items) + "</ul>"


def bignums(items: list[tuple[str, str, str]]) -> str:
    """items: [(標題, 大數字, 副註)]"""
    return ('<div class="bignums">'
            + "".join(f'<div class="bn"><div class="k">{k}</div><div class="v">{v}</div>'
                      f'<div class="d">{d}</div></div>' for k, v, d in items) + "</div>")


PAL = ["#2f6db5", "#f0a63a", "#8a63b5", "#4cae6e", "#d16a6a", "#6fc3d4"]


def donut(center: str, parts: list[tuple[str, float, str]]) -> str:
    """parts: [(名稱, 佔比, 註)] → conic-gradient 圓環+圖例"""
    stops, acc = [], 0.0
    for i, (_, pct, _n) in enumerate(parts):
        stops.append(f"{PAL[i % len(PAL)]} {acc}% {acc + pct}%")
        acc += pct
    if acc < 100:
        stops.append(f"#cfd8e3 {acc}% 100%")
    lg = "".join(f'<div><i style="background:{PAL[i % len(PAL)]}"></i>{n} <b>{p:g}%</b>'
                 f'<small>{note}</small></div>' for i, (n, p, note) in enumerate(parts))
    return (f'<div class="donutrow"><div class="donut" data-c="{center}" '
            f'style="background:conic-gradient({",".join(stops)})"></div>'
            f'<div class="lg">{lg}</div></div>')


def bars(items: list[tuple[str, float, str]], unit: str = "%") -> str:
    """items: [(標籤, 數值, 顏色)] 簡易長條圖"""
    mx = max(v for _, v, _ in items) or 1
    return ('<div class="bars">'
            + "".join(f'<div class="bar"><span class="pv">{v:g}{unit}</span>'
                      f'<i style="height:{max(6, v / mx * 64)}px;background:{c}"></i>{k}</div>'
                      for k, v, c in items) + "</div>")


def flow(boxes: list[tuple[str, str, bool]]) -> str:
    """boxes: [(主文, 小註, 是否標紅)]"""
    out = []
    for i, (t, s, hot) in enumerate(boxes):
        if i:
            out.append('<div class="farr">▼</div>')
        out.append(f'<div class="fbox{" hot" if hot else ""}">{t}'
                   + (f"<small>{s}</small>" if s else "") + "</div>")
    return f'<div class="flow">{"".join(out)}</div>'


def save_poster(code: str, date: str, html: str):
    return save_issue(f"{code}海報", date, html)

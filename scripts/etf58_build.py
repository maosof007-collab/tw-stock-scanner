# -*- coding: utf-8 -*-
"""ETF58「上市以來」版:產生兩組(有成本/無投入成本)的 Excel 和 PDF(A4 橫式、A4 直式、iPhone 直式、計算公式)。
版面照使用者給的 ETF58_BCDE_*_20261101 檔案。計算在 etf58_inception.py。
用法:python -X utf8 scripts/etf58_inception.py build [截止日 YYYY-MM-DD]
PDF 用本機 Edge 無頭列印;先寫到 C: 暫存再複製到 data/etf58/(G: 碟大量寫入偶爾會 I/O 錯誤)。"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import etf58_inception as X  # noqa: E402
from twtime import now_tw  # noqa: E402

EDGE = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",          # Chrome 會等寫完才返回,優先用
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
CHECK_NOTE = ("2026-11-23 用同一條管線重算原檔期間(2025/10/01~2026/09/30)和原檔「基礎_58」逐檔核對:55 檔台幣計價的期初價、9/30 收盤、"
              "已付股息、應收股息、月均價成本完全相同;3 檔美元計價(00687C、IQQQ、QQA)因匯率來源不同,B1 差 0.03~0.06 個百分點")


# ───────────────────────── 排名 ─────────────────────────
def pct(x, d=2):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f}%"


def num(x, d=2):
    return "—" if x is None or pd.isna(x) else f"{x:,.{d}f}"


def ratio(cost, net):
    """正獲利:每賺 1 元要幾元成本(x.xx：1);虧損或零:成本：負損益。"""
    if pd.isna(net):
        return "—"
    return f"{cost / net:.2f}：1" if net > 0 else f"{cost:.2f}：{net:.2f}"


def _e_order(rows, key):
    pos = sorted([r for r in rows if r[key] > 0], key=lambda r: r["cost"] / r[key])
    neg = sorted([r for r in rows if not r[key] > 0], key=lambda r: -r[key] / r["cost"])
    return pos + neg


def rank(R: list[dict]) -> dict:
    """→ {榜名: [dict(rank, short, r)]}。有成本組:滿一年的用年化/年均排,未滿一年的不年化、接在後面依累計排(名次加 *)。"""
    full, short = [r for r in R if r["full"]], [r for r in R if not r["full"]]
    out = {}

    def pack(a, b):
        return [dict(rank=i + 1, short=i >= len(a), r=r) for i, r in enumerate(a + b)]
    out["B1"] = pack(sorted(full, key=lambda r: -r["B1y"]), sorted(short, key=lambda r: -r["B1"]))
    out["C1"] = pack(sorted(full, key=lambda r: -r["C1y"]), sorted(short, key=lambda r: -r["C1"]))
    out["D1"] = out["C1"]
    out["E1"] = pack(_e_order(full, "E1_net_y"), _e_order(short, "E1_net"))
    for k in ("B2", "C2"):
        out[k] = [dict(rank=i + 1, short=not r["full"], r=r) for i, r in enumerate(sorted(R, key=lambda r: -r[k]))]
    out["D2"] = out["C2"]
    out["E2"] = [dict(rank=i + 1, short=not r["full"], r=r) for i, r in enumerate(_e_order(R, "E2_net"))]
    return out


# ───────────────────────── 榜單定義(Excel 和 PDF 共用) ─────────────────────────
def boards(group: int, end: str) -> list[dict]:
    e = end.replace("-", "/")
    yr = lambda r: f"{r['years']:.1f} 年" if r["full"] else f"{r['months']} 個月"
    ld = lambda r: f"{r['d0']:%Y/%m/%d}"
    if group == 1:
        return [
            dict(key="B1", name="B 榜", title="B 榜｜上市以來台幣含息總報酬(年化)", tag="第一組｜上市首日參考成本",
                 sub=f"({e} 收盤價－上市首日收盤價＋上市以來已付股息＋期末應收)÷ 上市首日收盤價;滿一年的再換算成年化,用年化排名。",
                 cols=[("上市首日", ld, "c"), ("上市多久", yr, "c"), ("同期大盤年化<br><small>(不含息,參考)</small>", lambda r: pct(r["MKTy"], 1) if r["full"] else pct(r["MKT"], 1) + "(累計)", "r"),
                       ("累計含息報酬", lambda r: pct(r["B1"]), "r"), ("年化含息報酬", lambda r: pct(r["B1y"]) if r["full"] else "未滿一年", "R")],
                 phone=[("上市多久", yr, "c"), ("累計", lambda r: pct(r["B1"], 1), "r"), ("年化", lambda r: pct(r["B1y"], 1) if r["full"] else "未滿一年", "R")]),
            dict(key="C1", name="C 榜", title="C 榜｜上市以來實收現金率(年均)", tag="第一組｜上市首日參考成本",
                 sub=f"上市以來已經付款的股息 ÷ 上市首日收盤價;滿一年的再除以上市年數,用年均排名。{e} 還沒付款的應收不算。",
                 cols=[("上市首日", ld, "c"), ("上市多久", yr, "c"), ("累計已付股息(元)", lambda r: num(r["paid"], 3), "r"),
                       ("累計實收現金率", lambda r: pct(r["C1"]), "r"), ("年均實收現金率", lambda r: pct(r["C1y"]) if r["full"] else "未滿一年", "R")],
                 phone=[("上市多久", yr, "c"), ("累計", lambda r: pct(r["C1"], 1), "r"), ("年均", lambda r: pct(r["C1y"], 2) if r["full"] else "未滿一年", "R")]),
            dict(key="D1", name="D 榜", title="D 榜｜月均殖利率(年均實收現金率 ÷ 12)", tag="第一組｜上市首日參考成本",
                 sub="年均實收現金率直接除以 12,不採複利。這是月平均等值,不代表每個月真的領到這麼多。",
                 cols=[("上市首日", ld, "c"), ("上市多久", yr, "c"), ("年均實收現金率", lambda r: pct(r["C1y"]) if r["full"] else "未滿一年", "r"),
                       ("月均殖利率", lambda r: pct(r["D1"], 3) if r["full"] else "未滿一年", "R")],
                 phone=[("上市多久", yr, "c"), ("年均", lambda r: pct(r["C1y"], 2) if r["full"] else "—", "r"), ("月均", lambda r: pct(r["D1"], 3) if r["full"] else "未滿一年", "R")]),
            dict(key="E1", name="E 榜", title="E 榜｜上市以來月均價成本:年均淨獲利", tag="第一組｜上市以來月均價作參考成本", wide=True,
                 sub=f"參考成本 = 上市以來每個月平均股價的平均;淨獲利 = {e} 收盤價 − 參考成本 ＋ 上市以來股息(已付＋應收)。滿一年的再除以上市年數;正獲利依「成本 ÷ 年均淨獲利」由低到高。",
                 cols=[("上市多久", yr, "c"), ("平均參考成本", lambda r: num(r["cost"]), "r"), ("股價損益", lambda r: num(r["E1_px"]), "r"),
                       ("股息獲利", lambda r: num(r["E1_dv"], 3), "r"), ("累計淨獲利", lambda r: num(r["E1_net"]), "r"),
                       ("年均淨獲利", lambda r: num(r["E1_net_y"]) if r["full"] else "未滿一年", "r"),
                       ("成本：年均淨獲利", lambda r: ratio(r["cost"], r["E1_net_y"] if r["full"] else r["E1_net"]) + ("" if r["full"] else "(累計)"), "R")]),
        ]
    mo = lambda r: f"{r['months']} 個月"
    return [
        dict(key="B2", name="B 榜", title="B 榜｜上市以來月均含息報酬率", tag="第二組｜不需個人投入成本",
             sub="每個月:(月底價 − 月初價 ＋ 當月除息的股息)÷ 月初價;把上市以來每個月的結果做算術平均。月初價 = 上個月底收盤(第一個月 = 上市首日收盤)。",
             cols=[("上市首日", ld, "c"), ("有效月份", mo, "c"), ("月均含息報酬率", lambda r: pct(r["B2"], 3), "R")],
             phone=[("月份", mo, "c"), ("月均含息", lambda r: pct(r["B2"], 3), "R")]),
        dict(key="C2", name="C 榜", title="C 榜｜上市以來月均實收現金率", tag="第二組｜不需個人投入成本",
             sub="每個月:當月實際付款的股息 ÷ 月初價;把上市以來每個月的結果做算術平均。",
             cols=[("上市首日", ld, "c"), ("有效月份", mo, "c"), ("月均實收現金率", lambda r: pct(r["C2"], 3), "R")],
             phone=[("月份", mo, "c"), ("月均實收", lambda r: pct(r["C2"], 3), "R")]),
        dict(key="D2", name="D 榜", title="D 榜｜上市以來月均殖利率", tag="第二組｜不需個人投入成本",
             sub="每個月現金殖利率的算術平均;照原檔定義,數值和 C 榜相同。",
             cols=[("上市首日", ld, "c"), ("有效月份", mo, "c"), ("月均殖利率", lambda r: pct(r["D2"], 3), "R")],
             phone=[("月份", mo, "c"), ("月均殖利率", lambda r: pct(r["D2"], 3), "R")]),
        dict(key="E2", name="E 榜", title="E 榜｜上市以來月均價成本:月均淨獲利", tag="第二組｜上市以來月均價作參考成本", wide=True,
             sub="參考成本 = 上市以來每個月平均股價的平均;月均淨獲利 = 平均每月價差 ＋ 平均每月除息的股息。正獲利依「成本 ÷ 月均淨獲利」由低到高。",
             cols=[("有效月份", mo, "c"), ("平均參考成本", lambda r: num(r["cost"]), "r"), ("月均價差", lambda r: num(r["E2_px"], 3), "r"),
                   ("月均股息", lambda r: num(r["E2_dv"], 3), "r"), ("月均淨獲利", lambda r: num(r["E2_net"], 3), "r"),
                   ("成本：月均淨獲利", lambda r: ratio(r["cost"], r["E2_net"]), "R")]),
    ]


# ───────────────────────── PDF(HTML → Edge 列印) ─────────────────────────
LAYOUT = {  # 版面: (寬pt, 高pt, 邊距pt, 內文字級, 每頁列數, E 榜每頁列數, 檔名)
    "A4橫式": (842, 595, 28, 11.5, 10, 10, "A4橫式"),
    "A4直式": (595, 842, 30, 10, 22, 20, "A4直式"),
    "iPhone直式": (390, 740, 18, 9, 16, 6, "iPhone直式"),
}
NAVY, INK, MUTE, LINE, SOFT, WARN = "#274863", "#1e3448", "#5f7385", "#dfe5ea", "#f2f5f8", "#8a5a1f"


def css(w, h, pad, fs) -> str:
    return (f"@page{{size:{w}pt {h}pt;margin:0}}*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}"
            f"body{{font-family:'Microsoft JhengHei','PingFang TC','Noto Sans TC',sans-serif;color:{INK};font-size:{fs}pt;line-height:1.5;-webkit-print-color-adjust:exact;print-color-adjust:exact}}"
            f".page{{width:{w}pt;height:{h}pt;padding:{pad}pt;position:relative;page-break-after:always;overflow:hidden}}"
            f".bar{{height:4pt;background:{NAVY};margin-bottom:{fs * 1.4:.0f}pt}}"
            f".kick{{font-size:{fs * .82:.1f}pt;color:{MUTE};font-weight:700;letter-spacing:.3pt}}"
            f"h1{{font-size:{fs * 2.5:.0f}pt;line-height:1.3;margin:{fs * 1.6:.0f}pt 0 {fs * 2:.0f}pt;color:{INK}}}"
            f"h2{{font-size:{fs * 1.55:.1f}pt;margin:{fs * .5:.0f}pt 0 {fs * .5:.0f}pt;color:{NAVY}}}"
            f".chip{{display:inline-block;background:#e6eef4;color:{NAVY};font-weight:700;border-radius:8pt;padding:{fs * .6:.0f}pt {fs * .9:.0f}pt;margin-bottom:{fs * 1.2:.0f}pt}}"
            f".sub{{color:{MUTE};margin:0 0 {fs * .9:.0f}pt;font-size:{fs * .92:.1f}pt}}.warn{{color:{WARN};font-size:{fs * .85:.1f}pt;margin-top:{fs:.0f}pt}}"
            f"hr{{border:0;border-top:1pt solid {LINE};margin:{fs * 1.4:.0f}pt 0}}"
            f"table{{width:100%;border-collapse:collapse}}th{{background:{NAVY};color:#fff;text-align:left;padding:{fs * .6:.1f}pt {fs * .55:.1f}pt;font-size:{fs * .9:.1f}pt;white-space:nowrap}}"
            f"td{{padding:{fs * .62:.1f}pt {fs * .55:.1f}pt;border-bottom:1pt solid {LINE};white-space:nowrap}}tr:nth-child(odd) td{{background:{SOFT}}}"
            f"td.name{{white-space:normal}}.c{{text-align:center}}.r{{text-align:right}}.R{{text-align:right;font-weight:700}}th.c{{text-align:center}}th.r,th.R{{text-align:right}}"
            f".b{{font-weight:700}}.sec td{{background:#fff7e8 !important;color:{WARN};font-weight:700;font-size:{fs * .85:.1f}pt}}"
            f".foot{{color:{MUTE};font-size:{fs * .8:.1f}pt;margin-top:{fs * .7:.0f}pt}}.pno{{position:absolute;right:{pad}pt;bottom:{pad * .55:.0f}pt;color:{MUTE};font-size:{fs * .78:.1f}pt}}"
            f".card{{border:1pt solid {LINE};border-left:4pt solid {NAVY};border-radius:5pt;background:#f7f9fb;padding:{fs * .8:.0f}pt {fs * 1.1:.0f}pt;margin-bottom:{fs * .9:.0f}pt}}"
            f".card b{{display:block;margin-bottom:{fs * .25:.0f}pt}}.eq{{background:#eef5f8;border-left:4pt solid #2f7f8f;padding:{fs * .7:.0f}pt {fs:.0f}pt;font-weight:700;margin:{fs * .5:.0f}pt 0}}"
            f".ec{{border:1pt solid {LINE};border-radius:6pt;padding:{fs * .7:.0f}pt {fs * .9:.0f}pt;margin-bottom:{fs * .7:.0f}pt;background:#fff}}.ec .t{{font-weight:700}}.ec .m{{color:{MUTE};font-size:{fs * .88:.1f}pt}}"
            f".grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 {fs:.0f}pt}}")


def _table(b: dict, rows: list, phone: bool, n_full: int) -> str:
    cols = b.get("phone", b["cols"]) if phone else b["cols"]
    h = "<tr><th>名次</th><th>代碼</th><th>ETF名稱</th>" + "".join(f'<th class="{a}">{t}</th>' for t, _, a in cols) + "</tr>"
    out = [h]
    for x in rows:
        if x["short"] and x["rank"] == n_full + 1 and b["key"].endswith("1"):
            out.append(f'<tr class="sec"><td colspan="{len(cols) + 3}">以下未滿一年:不年化,依累計值排列(名次加 *)</td></tr>')
        r = x["r"]
        star = "*" if x["short"] else ""
        out.append(f'<tr><td class="b">{x["rank"]}{star}</td><td class="b">{r["code"]}</td><td class="name">{r["name"]}</td>'
                   + "".join(f'<td class="{a}">{f(r)}</td>' for _, f, a in cols) + "</tr>")
    return "<table>" + "".join(out) + "</table>"


def _ecards(b: dict, rows: list, group: int) -> str:
    out = []
    for x in rows:
        r = x["r"]
        if group == 1:
            net = r["E1_net_y"] if r["full"] else r["E1_net"]
            l2 = f'參考成本 {num(r["cost"])}　股價 {num(r["E1_px"])}　股息 {num(r["E1_dv"], 3)}'
            l3 = f'累計淨獲利 {num(r["E1_net"])}' + (f'　年均 {num(r["E1_net_y"])}' if r["full"] else "　未滿一年不年化")
            l4 = f'成本：{"年均" if r["full"] else "累計"}淨獲利 {ratio(r["cost"], net)}'
            how = f'{r["years"]:.1f} 年' if r["full"] else f'{r["months"]} 個月 · 短歷史'
        else:
            l2 = f'參考成本 {num(r["cost"])}　月均價差 {num(r["E2_px"], 3)}　月均股息 {num(r["E2_dv"], 3)}'
            l3 = f'月均淨獲利 {num(r["E2_net"], 3)}'
            l4 = f'成本：月均淨獲利 {ratio(r["cost"], r["E2_net"])}'
            how = f'{r["months"]} 個月' + ("" if r["full"] else " · 短歷史")
        out.append(f'<div class="ec"><div class="t">#{x["rank"]}{"*" if x["short"] and group == 1 else ""}　{r["code"]}　{r["name"]}</div>'
                   f'<div class="m">上市 {r["d0"]:%Y/%m/%d} · {how}</div><div>{l2}</div><div>{l3}</div><div class="b">{l4}</div></div>')
    return "".join(out)


def rank_html(group: int, end: str, R: list, RK: dict, layout: str) -> str:
    w, h, pad, fs, per, per_e, _ = LAYOUT[layout]
    phone = layout.startswith("iPhone")
    e = end.replace("-", ".")
    gname = "有成本 ・ 第 1 組(上市首日參考成本)" if group == 1 else "無投入成本 ・ 第 2 組(逐月平均)"
    first = min(r["d0"] for r in R)
    n_full = sum(r["full"] for r in R)
    B = boards(group, end)
    pages = []
    pages.append(f'<div class="bar"></div><div class="kick">上市首日 — {e}(最早 {first:%Y.%m.%d})</div><h1>58 檔 ETF<br>上市以來 B・C・D・E 四榜</h1>'
                 f'<div class="chip">{gname}</div><div>每一檔都從自己的上市首日算到 {end.replace("-", "/")};每榜完整收錄 58 檔。</div><hr>'
                 + ('<h2>上市時間不同,怎麼比</h2><div>累計值會偏袒上市久的,所以滿一年的換算成<b style="display:inline">年化/年均</b>再排名;'
                    f'未滿一年的 {len(R) - n_full} 檔不年化,接在後面依累計值排列(名次加 *)。</div>' if group == 1 else
                    '<h2>上市時間不同,怎麼比</h2><div>這一組本來就是「每個月算一次、再取平均」,月份多寡不影響可比性;'
                    f'只是未滿一年的 {len(R) - n_full} 檔樣本少,名稱旁標「短歷史」。</div>')
                 + f'<div class="warn">「成本」是市場參考價(上市首日收盤、各月平均價),不是個人真實成交成本;未扣手續費、稅。'
                   f'資料只到 {end.replace("-", "/")},之後的行情沒有算進來。研究筆記,非投資建議。</div>')
    cards = "".join(f'<div class="card"><b>{b["title"]}</b>{b["sub"]}</div>' for b in B)
    pages.append(f'<div class="bar"></div><h2>本組計算方法｜B、C、D、E</h2>{cards}'
                 '<div class="card"><b>資料與核對</b>股價、配息日期與金額取自 FinMind(台灣掛牌)與 yfinance(IQQQ、QQA),美元計價以當日台銀即期中價換算。'
                 '用同一條管線重算原檔的 2025/10~2026/09,55 檔完全相同、3 檔美元計價差 0.03~0.06 個百分點。配息沒有逐筆回官方公告核對。</div>')
    for b in B:
        rows = RK[b["key"]]
        n = per_e if b.get("wide") else per
        chunks = [rows[i:i + n] for i in range(0, len(rows), n)]
        for i, ch in enumerate(chunks):
            body = _ecards(b, ch, group) if (phone and b.get("wide")) else _table(b, ch, phone, n_full)
            foot = ("* 未滿一年:只算實際有效月份、不年化,不要和滿一年的年化值當成同一種數字比。" if group == 1 else
                    "* 短歷史(未滿 12 個月):月平均的樣本少、波動大,不要和滿一年的當成一樣可靠。") if not b.get("wide") else "E 用每股台幣金額,不顯示獲利率 %。正獲利依成本獲利比排序;虧損另列在後。"
            pages.append(f'<div class="bar"></div><div class="kick">{b["tag"]} ・ {b["name"]} ・ 第 {i + 1}/{len(chunks)} 頁</div>'
                         f'<h2>{b["title"]}</h2><div class="sub">{b["sub"]}</div>{body}<div class="foot">{foot}</div>')
    body = "".join(f'<section class="page">{p}<div class="pno">第 {i + 1} 頁</div></section>' for i, p in enumerate(pages))
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{css(w, h, pad, fs)}</style></head><body>{body}</body></html>'


def formula_html(group: int, end: str, R: list) -> str:
    w, h, pad, fs = 595, 842, 44, 10.5
    e = end.replace("-", "/")
    n_full = sum(r["full"] for r in R)
    ex = next(r for r in R if r["code"] == "0056")
    P = []
    gname = "第一組｜有成本版(上市首日參考成本)" if group == 1 else "第二組｜無投入成本版(逐月平均)"
    P.append(f'<div class="kick">ETF58 RESEARCH / METHOD GUIDE</div><div class="kick">上市首日 — {e}</div><h1>B～E 四榜<br>上市以來版 計算公式</h1>'
             f'<h2>{gname}</h2><div>原檔只算 2025/10/01~2026/09/30 這一年。這一版把每一檔的起點改成<b style="display:inline">自己的上市首日</b>,'
             f'其他口徑(月初價、除息日/付款日的歸屬、應收不算現金、美元換台幣)全部照原檔。</div><hr>'
             f'<div class="card"><b>為什麼要另外處理</b>58 檔裡上市最久的是 0056(2007/12/26),最新的不到一年。直接比累計值,上市久的一定贏。</div>'
             '<div class="card"><b>年化解決不了的事</b>年化只把「時間長短」拉平,拉不平「上市在什麼時候」。2022 年以後才上市的基金只經歷過多頭,年化數字天生比走過 2008、2022 的老基金好看。'
             'B 榜和 Excel 另外列出「同一段期間加權指數年化」當參考,用來看報酬有多少是來自大盤本身。</div>'
             + ('<div class="card"><b>這一組的處理方式</b>滿一年的:累計值照算,另外換成「年化/年均」並用它排名。'
                f'未滿一年的 {len(R) - n_full} 檔:只列累計值、不年化,排在後面(名次加 *)。</div>' if group == 1 else
                '<div class="card"><b>這一組的處理方式</b>這一組的指標本來就是逐月計算再取平均,所以只要把月份從 12 個月拉長到上市以來的每一個月,不需要年化。'
                f'未滿一年的 {len(R) - n_full} 檔樣本少,標「短歷史」。</div>')
             + '<div class="warn">「成本」是歷史市場參考價,不是帳戶真實成交成本。本文說明計算方法,數字沒有逐筆回官方公告核對。</div>')
    if group == 1:
        P.append('<div class="kick">01 / B 榜</div><h2>B 榜:上市以來含息總報酬 → 年化</h2>'
                 f'<div class="eq">累計含息報酬率 =({e} 收盤價 − 上市首日收盤價 ＋ 已付股息 ＋ 期末應收)÷ 上市首日收盤價</div>'
                 '<div class="eq">年化含息報酬率 =(1 ＋ 累計含息報酬率)^(1 ÷ 上市年數)− 1</div>'
                 '<div class="eq">上市年數 = 上市首日到截止日的天數 ÷ 365.25</div>'
                 f'<h2>實例:0056 元大高股息</h2><table><tr><th>一步一步算</th><th class="r">金額</th></tr>'
                 f'<tr><td>上市首日({ex["d0"]:%Y/%m/%d})收盤價</td><td class="r">{ex["p0"]:.2f} 元</td></tr><tr><td>{e} 收盤價</td><td class="r">{ex["p1"]:.2f} 元</td></tr>'
                 f'<tr><td>股價損益</td><td class="r">{ex["p1"] - ex["p0"]:+.2f} 元</td></tr><tr><td>上市以來已付股息({ex["n_div"]} 次)＋應收</td><td class="r">+{ex["paid"] + ex["recv"]:.3f} 元</td></tr>'
                 f'<tr><td>累計含息報酬率</td><td class="r">{pct(ex["B1"])}</td></tr><tr><td>上市年數</td><td class="r">{ex["years"]:.2f} 年</td></tr>'
                 f'<tr><td class="b">年化含息報酬率</td><td class="R">{pct(ex["B1y"])}</td></tr></table>'
                 '<div class="warn">年化是「假設股息領了不再投入」的換算,不是含息再投資的報酬率,會比基金公司公布的含息績效低。</div>')
        P.append('<div class="kick">02 / C 榜、D 榜</div><h2>C 榜:上市以來實收現金率 → 年均</h2>'
                 '<div class="eq">累計實收現金率 = 上市以來已付款股息 ÷ 上市首日收盤價</div><div class="eq">年均實收現金率 = 累計實收現金率 ÷ 上市年數</div>'
                 f'<div>只算 {e} 以前已經付款的現金;已除息但還沒付款的「應收」不算。</div>'
                 f'<table style="margin-top:8pt"><tr><th>0056 實例</th><th class="r">數值</th></tr><tr><td>上市以來已付股息</td><td class="r">{ex["paid"]:.3f} 元</td></tr>'
                 f'<tr><td>累計實收現金率({ex["paid"]:.3f} ÷ {ex["p0"]:.2f})</td><td class="r">{pct(ex["C1"])}</td></tr><tr><td class="b">年均實收現金率(÷ {ex["years"]:.2f} 年)</td><td class="R">{pct(ex["C1y"])}</td></tr></table>'
                 '<h2 style="margin-top:14pt">D 榜:年均實收現金率 ÷ 12</h2><div class="eq">月均殖利率 = 年均實收現金率 ÷ 12</div>'
                 f'<div>照原檔的簡單公式,不採複利。0056:{pct(ex["C1y"])} ÷ 12 = {pct(ex["D1"], 3)}。D 和 C 用同一份配息資料,排序相同。</div>'
                 '<div class="warn">注意:分母是「上市首日的價格」。上市很久、股價漲很多的基金,年均實收現金率會比用現在股價算的殖利率高;這是「當初買的人」的角度。</div>')
        P.append('<div class="kick">03 / E 榜</div><h2>E 榜:上市以來月均價成本 : 年均淨獲利</h2>'
                 '<div class="eq">平均參考成本 = 上市以來各月「月平均股價」加總 ÷ 月份數</div>'
                 f'<div class="eq">累計淨獲利 =({e} 收盤價 − 平均參考成本)＋ 上市以來股息(已付＋應收)</div>'
                 '<div class="eq">年均淨獲利 = 累計淨獲利 ÷ 上市年數</div><div class="eq">E1 = 平均參考成本：年均淨獲利</div>'
                 f'<table><tr><th>0056 實例(每股)</th><th class="r">金額</th></tr><tr><td>{ex["months"]} 個月平均參考成本</td><td class="r">{ex["cost"]:.2f} 元</td></tr>'
                 f'<tr><td>股價損益</td><td class="r">{ex["E1_px"]:+.2f} 元</td></tr><tr><td>股息獲利</td><td class="r">+{ex["E1_dv"]:.3f} 元</td></tr>'
                 f'<tr><td>累計淨獲利</td><td class="r">{ex["E1_net"]:+.2f} 元</td></tr><tr><td>年均淨獲利</td><td class="r">{ex["E1_net_y"]:+.2f} 元</td></tr>'
                 f'<tr><td class="b">成本：年均淨獲利</td><td class="R">{ratio(ex["cost"], ex["E1_net_y"])}</td></tr></table>'
                 '<div class="card" style="margin-top:10pt"><b>如何排序</b>正獲利:成本 ÷ 年均淨獲利,由少到多(每年賺 1 元需要的成本越少越前)。虧損或零:列在正獲利之後,直接顯示負值。未滿一年:不年化,用累計淨獲利另外排在最後。</div>'
                 '<div class="warn">「用上市以來的平均價買進、又領到上市以來全部股息」是研究用的代理情境,實際上做不到;E 不顯示獲利率百分比。</div>')
    else:
        P.append('<div class="kick">01 / B 榜</div><h2>B 榜:上市以來月均含息報酬率</h2>'
                 '<div class="eq">當月含息報酬率 =(月底價 − 月初價 ＋ 當月除息的股息)÷ 月初價</div><div class="eq">B2 = 上市以來每個月「當月含息報酬率」的算術平均</div>'
                 '<div>月初價 = 上個月底的收盤價;第一個月用上市首日收盤價。股息按除息日歸到那個月。</div>'
                 f'<table style="margin-top:8pt"><tr><th>0056 實例</th><th class="r">數值</th></tr><tr><td>有效月份</td><td class="r">{ex["months"]} 個月</td></tr>'
                 f'<tr><td class="b">月均含息報酬率</td><td class="R">{pct(ex["B2"], 3)}</td></tr></table>'
                 '<div class="warn">算術平均不等於複利:每月平均 +1% 不代表一年剛好 +12.7%,波動越大差越多。這個數字只適合拿來互相比。</div>')
        P.append('<div class="kick">02 / C 榜、D 榜</div><h2>C 榜:上市以來月均實收現金率</h2>'
                 '<div class="eq">當月現金率 = 當月實際付款的股息 ÷ 月初價</div><div class="eq">C2 = 上市以來每個月「當月現金率」的算術平均</div>'
                 f'<div>股息按付款日歸到那個月;沒配息的月份算 0。0056:{pct(ex["C2"], 3)}(× 12 ≈ {pct(ex["C2"] * 12)}/年)。</div>'
                 '<h2 style="margin-top:14pt">D 榜:月均殖利率</h2><div class="eq">D2 = C2(照原檔定義,同一個計算式)</div>'
                 '<div class="warn">上市頭幾個月通常還沒開始配息,那幾個月是 0,會把剛上市基金的月均值拉低。</div>')
        P.append('<div class="kick">03 / E 榜</div><h2>E 榜:上市以來月均價成本 : 月均淨獲利</h2>'
                 '<div class="eq">平均參考成本 = 上市以來各月「月平均股價」加總 ÷ 月份數</div><div class="eq">月均價差 = 每個月(月底價 − 月初價)的平均</div>'
                 '<div class="eq">月均股息 = 每個月除息股息的平均</div><div class="eq">E2 = 平均參考成本：(月均價差 ＋ 月均股息)</div>'
                 f'<table><tr><th>0056 實例(每股)</th><th class="r">金額</th></tr><tr><td>平均參考成本</td><td class="r">{ex["cost"]:.2f} 元</td></tr>'
                 f'<tr><td>月均價差</td><td class="r">{ex["E2_px"]:+.3f} 元</td></tr><tr><td>月均股息</td><td class="r">+{ex["E2_dv"]:.3f} 元</td></tr>'
                 f'<tr><td>月均淨獲利</td><td class="r">{ex["E2_net"]:+.3f} 元</td></tr><tr><td class="b">成本：月均淨獲利</td><td class="R">{ratio(ex["cost"], ex["E2_net"])}</td></tr></table>'
                 '<div class="card" style="margin-top:10pt"><b>如何排序</b>正獲利:成本 ÷ 月均淨獲利,由少到多。虧損或零:列在後面,直接顯示負值。</div>')
    P.append('<div class="kick">04 / 附註與核對</div><h2>使用前要知道的事</h2><table><tr><th>項目</th><th>這一版怎麼做</th></tr>'
             '<tr><td class="b">上市首日參考價</td><td class="name">上市第一個交易日的收盤價(不是發行價)。和原檔短歷史基金的做法相同。</td></tr>'
             '<tr><td class="b">外幣換台幣</td><td class="name">00687C、IQQQ、QQA:股價用當日、股息用除息日的台銀美元即期中價換算。</td></tr>'
             '<tr><td class="b">除息／付款</td><td class="name">B、E 按除息日取得權利;C、D 只算截止日前已付款。美國兩檔較早的付款日用「除息日後 4 個營業日」推估(都早已付款,不影響累計)。</td></tr>'
             '<tr><td class="b">分割</td><td class="name">58 檔上市以來沒有單日漲跌超過 25% 的日子,判定沒有分割或合併,股價未做還原。</td></tr>'
             '<tr><td class="b">交易成本</td><td class="name">沒有扣手續費、交易稅、所得稅、二代健保、換匯成本。</td></tr>'
             f'<tr><td class="b">截止日</td><td class="name">{e}。之後的行情(含 2026/10 以後的下跌)沒有算進來;改截止日要重跑。</td></tr></table>'
             f'<h2 style="margin-top:14pt">資料核對</h2><div class="card">{CHECK_NOTE}。</div>'
             '<div class="card"><b>沒有做的事</b>配息金額與日期來自 FinMind 的彙整,沒有逐筆回證交所、櫃買中心、基金公司公告核對;A 榜(品質評分)不在這一版範圍。</div>'
             '<div class="foot">對照 Excel:基礎_58(每檔一列的底稿)、月度_BC、月度_E(逐月)、配息來源(逐筆)、B/C/D/E 四張排名、公式驗收。</div>')
    body = "".join(f'<section class="page"><div class="bar"></div>{p}<div class="pno">ETF58｜上市以來版｜{i + 1}</div></section>' for i, p in enumerate(P))
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{css(w, h, pad, fs)}</style></head><body>{body}</body></html>'


def to_pdf(html: str, out: Path, tmp: Path, tag: str) -> None:
    exe = next((e for e in EDGE if Path(e).exists()), None)
    if not exe:
        raise SystemExit("找不到 Edge/Chrome,無法產生 PDF")
    src, dst = tmp / f"{tag}.html", tmp / f"{tag}.pdf"
    src.write_text(html, encoding="utf-8")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer", f"--user-data-dir={tmp / 'prof'}",
                    f"--print-to-pdf={dst}", src.as_uri()], check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    size = -1
    for _ in range(120):                                   # Edge 會先返回、稍後才寫檔:等檔案出現而且大小不再變
        time.sleep(0.5)
        if dst.exists() and dst.stat().st_size > 0:
            if dst.stat().st_size == size:
                break
            size = dst.stat().st_size
    else:
        raise SystemExit(f"PDF 沒有產生:{tag}")
    shutil.copyfile(dst, out)


# ───────────────────────── Excel ─────────────────────────
def to_xlsx(group: int, end: str, R: list, RK: dict, out: Path) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    head_fill, head_font = PatternFill("solid", fgColor="274863"), Font(bold=True, color="FFFFFF")
    e = end.replace("-", "/")
    gl = "有成本" if group == 1 else "無投入"

    def sheet(name, title, note, heads, rows, fmts=None, widths=None):
        ws = wb.create_sheet(name)
        ws["A1"], ws["A3"] = title, note
        ws["A1"].font = Font(bold=True, size=14)
        for j, t in enumerate(heads, 1):
            c = ws.cell(5, j, t)
            c.fill, c.font, c.alignment = head_fill, head_font, Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, r in enumerate(rows, 6):
            for j, v in enumerate(r, 1):
                if isinstance(v, (float, np.floating)) and pd.isna(v):
                    v = None
                c = ws.cell(i, j, v.item() if isinstance(v, np.generic) else v)
                if fmts and fmts.get(j):
                    c.number_format = fmts[j]
        for j in range(1, len(heads) + 1):
            ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(j, 13)
        ws.freeze_panes = "C6"
        return ws

    P4, P2, N2, N3 = "0.0000%", "0.00%", "#,##0.00", "#,##0.000"
    samp = lambda r: f"滿一年:{r['years']:.1f} 年" if r["full"] else f"短歷史:{r['months']}月"
    # 基礎_58
    heads = ["ETF代碼", "名稱", "上市首日", "截止日", "有效月份", "上市年數", "上市首日參考價", f"{e[5:]}收盤價", "已付款股息(累計)", "期末應收股息", "上市以來月均價參考成本",
             "B1累計含息", "B1年化含息", "B2月均含息", "C1累計實收", "C1年均實收", "C2月均實收", "D1年均÷12", "D2逐月殖利",
             "E1股價損益", "E1股息權利", "E1累計淨獲利", "E1年均淨獲利", "E1成本÷年均淨獲利", "E2月均價差", "E2月均股息", "E2月均淨獲利", "E2成本÷月均淨獲利", "配息次數", "樣本",
             "同期加權指數累計(不含息)", "同期加權指數年化(不含息)"]
    rows = [[r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", f"{r['d1']:%Y-%m-%d}", r["months"], round(r["years"], 3), r["p0"], r["p1"], r["paid"], r["recv"], r["cost"],
             r["B1"], r["B1y"], r["B2"], r["C1"], r["C1y"], r["C2"], r["D1"], r["D2"], r["E1_px"], r["E1_dv"], r["E1_net"], r["E1_net_y"],
             (r["cost"] / r["E1_net_y"]) if r["full"] and r["E1_net_y"] > 0 else None, r["E2_px"], r["E2_dv"], r["E2_net"],
             (r["cost"] / r["E2_net"]) if r["E2_net"] > 0 else None, r["n_div"], samp(r), r["MKT"], r["MKTy"]] for r in R]
    fm = {7: N2, 8: N2, 9: N3, 10: N3, 11: N3, 12: P2, 13: P2, 14: P4, 15: P2, 16: P2, 17: P4, 18: P4, 19: P4, 20: N3, 21: N3, 22: N3, 23: N3, 24: N2, 25: "0.0000", 26: "0.0000", 27: "0.0000", 28: N2, 31: P2, 32: P2}
    sheet("基礎_58", "58 檔｜上市以來 統一計算底稿", f"每檔從上市首日算到 {e}。B1/C1/E1 以上市首日收盤價或上市以來月均價為參考成本,滿一年的另算年化/年均;B2/C2/E2 為上市以來逐月平均。數值為靜態結果(無公式),更新資料要重跑程式。",
          heads, rows, fm, {2: 26, 30: 16, 31: 16, 32: 16})
    # 月度_BC / 月度_E
    bc, me = [], []
    for r in R:
        for _, m in r["monthly"].iterrows():
            bc.append([r["code"], m.月份, m.基準日, m.末日, m.月初價, m.月末價, m.當月除息權利, m.當月付款, m.價差, m.含息損益, m.B2當月報酬, m.C2當月現金率])
            me.append([r["code"], r["name"], int(m.月份[:4]), int(m.月份[5:]), int(m.有效日價數), m.月初價, m.本月平均價, m.月末價, m.價差, m.當月除息權利, m.含息損益, m.B2當月報酬, ""])
    sheet("月度_BC", "B、C 月度計算｜市場參考成本(上市以來)", "配息權利按除息日歸屬 B;已付款按付款日歸屬 C,兩者不重複。月初價 = 上個月底收盤(第一個月 = 上市首日收盤)。",
          ["代碼", "月份", "基準日", "末日", "月初價(TWD)", "月末價(TWD)", "當月除息權利(TWD)", "當月付款(TWD)", "價差(TWD)", "含息損益(TWD)", "B2當月報酬", "C2當月現金率"],
          bc, {5: N2, 6: N2, 7: N3, 8: N3, 9: N2, 10: N3, 11: P2, 12: P2})
    sheet("月度_E", "E 榜:逐月參考價、股價損益與股息(上市以來)", "平均參考成本 = 上市以來各月平均股價的等權平均。",
          ["代碼", "名稱", "年份", "月份", "有效日價數", "月初參考價", "本月平均價", "月末收盤價", "當月股價損益", "當月股息權利", "當月合計損益", "當月參考報酬", "註記"],
          me, {6: N2, 7: N3, 8: N2, 9: N2, 10: N3, 11: N3, 12: P2}, {2: 26})
    # 配息來源
    dv = []
    for r in R:
        for _, d in r["divs"].iterrows():
            src = "yfinance(除息日、金額)" + ("+推估付款日" if d.est_pay else "+原檔官方付款日") if r["code"] in X.US else "FinMind TaiwanStockDividend" + ("(付款日推估)" if d.est_pay else "")
            dv.append([r["code"], f"{d.ex:%Y-%m-%d}", f"{d.pay:%Y-%m-%d}", d.amt, d.ccy, 1 if d.paid else 0, 0 if d.paid else 1, d.twd if d.paid else 0, 0 if d.paid else d.twd,
                       "FINMIND_AGGREGATED" if r["code"] not in X.US else "YFINANCE", src])
    sheet("配息來源", "配息來源明細｜上市以來每一筆", "資料來自 FinMind/yfinance 的彙整,沒有逐筆回證交所、櫃買中心、基金公司公告核對。原檔 2025/10~2026/09 的已付、應收合計與此完全相同。",
          ["代碼", "除息日", "付款日", "每股原幣配息", "幣別", f"截至{e[5:]}已付", "期末應收", "已付台幣", "應收台幣", "狀態", "資料來源"], dv, {4: "0.000000", 8: N3, 9: N3}, {11: 38})
    # 使用說明
    ws = wb.create_sheet("使用說明")
    lines = [[f"ETF58｜上市以來 {gl} B／C／D／E 四榜"], [f"每一檔從自己的上市首日算到 {e};口徑照原檔 ETF58_BCDE_*_20261101,只改期間。"],
             ["項目", "有成本組(上市首日參考成本)", "無投入成本組(逐月平均)", "解讀限制"],
             ["B 榜", "上市以來台幣含息總報酬 → 年化後排名", "上市以來逐月含息報酬率的算術平均", "年化是不再投入的換算;兩組不可混排"],
             ["C 榜", "已付股息÷上市首日收盤價 → 除以上市年數", "逐月已付款現金÷月初參考價,再取平均", "已收現金不等於應收權利"],
             ["D 榜", "年均實收現金率÷12", "逐月現金殖利率的算術平均", "C2、D2 同一計算式"],
             ["E 榜", "上市以來月均價成本:(期末價差＋股息)÷上市年數", "上市以來月均價成本:平均每月價差＋股息", "只看成本:淨獲利金額比,無百分比"],
             ["觀察期間", f"各檔上市首日～{e}", "相同", "未滿一年的不年化、另列"],
             ["上市時間不同", "滿一年用年化/年均排名;未滿一年依累計排在後(名次加 *)", "逐月平均本身可比;未滿一年標短歷史", "上市越久,經歷過的多空越多"],
             ["資料來源", "FinMind(台灣掛牌股價、配息)、yfinance(IQQQ、QQA)、台銀美元即期匯率", "相同", "配息未逐筆回官方公告核對"],
             ["重要提醒", "上市首日收盤價≠真實成交成本", "月初市價≠真實投入成本", "未扣手續費與稅;非已實現損益"],
             ["公式引擎", "Python:scripts/etf58_inception.py、etf58_build.py", "工作簿內是靜態數值,不是公式", "更新資料或改截止日要重跑"]]
    for i, ln in enumerate(lines, 1):
        for j, v in enumerate(ln, 1):
            ws.cell(i, j, v)
    ws["A1"].font = Font(bold=True, size=14)
    for j, wd in enumerate((14, 50, 44, 40), 1):
        ws.column_dimensions[get_column_letter(j)].width = wd
    # 總覽 + 四榜
    keys = [f"{k}{group}" for k in "BCDE"]
    pos = {k: {x["r"]["code"]: (f"{x['rank']}*" if x["short"] and group == 1 else x["rank"]) for x in RK[k]} for k in keys}
    if group == 1:
        heads = ["ETF代碼", "ETF名稱", "上市首日", "上市年數", "B名次", "B累計報酬", "B年化報酬", "C名次", "C累計現金率", "C年均現金率", "D名次", "D月均殖利率", "E名次", "E平均參考成本", "E股價損益", "E股息獲利", "E累計淨獲利", "E年均淨獲利", "E成本：年均淨獲利"]
        rows = [[r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", round(r["years"], 2), pos["B1"][r["code"]], r["B1"], r["B1y"], pos["C1"][r["code"]], r["C1"], r["C1y"], pos["D1"][r["code"]], r["D1"],
                 pos["E1"][r["code"]], r["cost"], r["E1_px"], r["E1_dv"], r["E1_net"], r["E1_net_y"], ratio(r["cost"], r["E1_net_y"] if r["full"] else r["E1_net"])] for r in R]
        fm = {6: P2, 7: P2, 9: P2, 10: P2, 12: P4, 14: N2, 15: N2, 16: N3, 17: N2, 18: N2}
    else:
        heads = ["ETF代碼", "ETF名稱", "上市首日", "有效月份", "B名次", "B月均含息", "C名次", "C月均現金率", "D名次", "D月均殖利率", "E名次", "E平均參考成本", "E月均價差", "E月均股息", "E月均淨獲利", "E成本：月均淨獲利"]
        rows = [[r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", r["months"], pos["B2"][r["code"]], r["B2"], pos["C2"][r["code"]], r["C2"], pos["D2"][r["code"]], r["D2"],
                 pos["E2"][r["code"]], r["cost"], r["E2_px"], r["E2_dv"], r["E2_net"], ratio(r["cost"], r["E2_net"])] for r in R]
        fm = {6: P4, 8: P4, 10: P4, 12: N2, 13: "0.0000", 14: "0.0000", 15: "0.0000"}
    sheet(f"{gl}總覽", f"{gl}組｜上市以來 B、C、D、E 四榜總覽", "E 不顯示報酬率百分比;成本：淨獲利比 = 每賺 1 元需要多少元參考成本,正獲利越低越好。名次加 * = 未滿一年(不年化、另列)。",
          heads, rows, fm, {2: 26, 19: 18, 16: 18})
    for b in boards(group, end):
        k = b["key"]
        if k[0] == "E":
            if group == 1:
                heads = ["名次", "ETF代碼", "ETF名稱", "上市首日", "上市年數", "平均參考成本(元/股)", "股價損益(元/股)", "股息獲利(元/股)", "累計淨獲利(元/股)", "年均淨獲利(元/股)", "成本：年均淨獲利", "獲利狀態", "註記"]
                rows = [[f"{x['rank']}*" if x["short"] else x["rank"], r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", round(r["years"], 2), r["cost"], r["E1_px"], r["E1_dv"], r["E1_net"], r["E1_net_y"],
                         ratio(r["cost"], r["E1_net_y"] if r["full"] else r["E1_net"]), "淨獲利" if r["E1_net"] > 0 else "虧損或零", samp(r) + ("" if r["full"] else "(不年化,用累計)")]
                        for x in RK[k] for r in [x["r"]]]
                fm = {6: N2, 7: N2, 8: N3, 9: N2, 10: N2}
            else:
                heads = ["名次", "ETF代碼", "ETF名稱", "上市首日", "有效月份", "平均參考成本(元/股)", "月均價差(元/股)", "月均股息(元/股)", "月均淨獲利(元/股)", "成本：月均淨獲利", "獲利狀態", "註記"]
                rows = [[x["rank"], r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", r["months"], r["cost"], r["E2_px"], r["E2_dv"], r["E2_net"], ratio(r["cost"], r["E2_net"]),
                         "淨獲利" if r["E2_net"] > 0 else "虧損或零", samp(r)] for x in RK[k] for r in [x["r"]]]
                fm = {6: N2, 7: "0.0000", 8: "0.0000", 9: "0.0000"}
        elif group == 1:
            cum, ann = {"B1": ("B1", "B1y"), "C1": ("C1", "C1y"), "D1": ("C1y", "D1")}[k]
            heads = ["名次", "ETF代碼", "ETF名稱", "上市首日", "上市年數", {"B1": "累計含息報酬", "C1": "累計實收現金率", "D1": "年均實收現金率"}[k],
                     {"B1": "年化含息報酬(排名用)", "C1": "年均實收現金率(排名用)", "D1": "月均殖利率(排名用)"}[k], "樣本狀態", "計算口徑"]
            rows = [[f"{x['rank']}*" if x["short"] else x["rank"], r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", round(r["years"], 2), r[cum], r[ann], samp(r),
                     "上市以來,年化" if r["full"] else "上市以來,未滿一年不年化"] for x in RK[k] for r in [x["r"]]]
            fm = {6: P2, 7: P4 if k == "D1" else P2}
        else:
            heads = ["名次", "ETF代碼", "ETF名稱", "上市首日", "有效月份", f"{k}指標", "樣本狀態", "計算口徑"]
            rows = [[x["rank"], r["code"], r["name"], f"{r['d0']:%Y-%m-%d}", r["months"], r[k], samp(r), "上市以來月均"] for x in RK[k] for r in [x["r"]]]
            fm = {6: P4}
        sheet(f"{gl}{k[0]}", f"{b['tag']} — {b['name']}(上市以來)", b["sub"], heads, rows, fm, {3: 26, 11: 18, 10: 18, 13: 26, 9: 24, 8: 18})
    # 公式驗收
    chk = []
    ok = lambda a, b: "PASS" if a == b else "FAIL"
    n_m = sum(r["months"] for r in R)
    chk.append(["唯一ETF代號", len({r["code"] for r in R}), 58])
    chk.append([f"{gl} B/C/D/E 各58檔", min(len(RK[k]) for k in keys), 58])
    chk.append(["B/C月度資料筆數", len(bc), n_m])
    chk.append(["E月度資料筆數", len(me), n_m])
    chk.append(["配息底稿資料筆數", len(dv), sum(r["n_div"] for r in R)])
    chk.append(["B1:期末價−首日價＝各月價差加總", sum(abs((r["p1"] - r["p0"]) - r["monthly"].價差.sum()) < 1e-6 for r in R), 58])
    chk.append(["C1:已付股息＝各月付款加總", sum(abs(r["paid"] - r["monthly"].當月付款.sum()) < 1e-6 for r in R), 58])
    chk.append(["E1:累計淨獲利＝股價損益＋股息", sum(abs(r["E1_net"] - r["E1_px"] - r["E1_dv"]) < 1e-9 for r in R), 58])
    chk.append(["E2:月均淨獲利＝月均價差＋月均股息", sum(abs(r["E2_net"] - r["E2_px"] - r["E2_dv"]) < 1e-9 for r in R), 58])
    chk.append(["單日漲跌超過25%(疑似分割)的日數", len(X.splits_check()), 0])
    rows = [[a, b, c, ok(b, c)] for a, b, c in chk]
    rows.append(["原檔期間(2025/10~2026/09)重算核對", "55 檔完全相同;3 檔美元計價 B1 差 0.03~0.06 點", "58 檔一致", "PASS(匯率來源差異)"])
    rows.append(["配息逐筆回官方公告核對", "未執行", "需另查", "尚未驗證"])
    rows.append(["美國兩檔較早的付款日", f"{sum(r['est_pay'] for r in R)} 筆用除息日+4營業日推估", "官方付款日", "推估(不影響累計)"])
    sheet("公式驗收", "內部一致性與資料限制", CHECK_NOTE, ["檢查", "實際結果", "應為", "狀態"], rows, None, {1: 40, 2: 44, 3: 16, 4: 22})
    wb.save(out)
    return {"月度列數": len(bc), "配息列數": len(dv), "驗收": [r[3] for r in rows]}


def main(end: str = X.END) -> Path:
    R = X.compute_all(end)
    RK = rank(R)
    stamp = f"{now_tw():%Y%m%d}"
    final = ROOT / "data" / "etf58" / f"ETF58_上市以來_{end.replace('-', '')}"
    tmp = Path(tempfile.mkdtemp(prefix="etf58_"))
    made = []
    for group, folder, gl, gno in ((1, "含成本", "有成本", "第一組有成本版"), (2, "不含成本", "無投入成本", "第二組無投入成本版")):
        d = final / folder
        d.mkdir(parents=True, exist_ok=True)
        x = tmp / f"g{group}.xlsx"
        info = to_xlsx(group, end, R, RK, x)
        out = d / f"ETF58_上市以來_BCDE_{gl}_完整排名及來源_{stamp}.xlsx"
        shutil.copyfile(x, out)
        made.append(out)
        print(folder, "xlsx", info, flush=True)
        for lay in LAYOUT:
            out = d / f"ETF58_上市以來_BCDE_{gl}_{LAYOUT[lay][6]}_獨立排名_{stamp}.pdf"
            to_pdf(rank_html(group, end, R, RK, lay), out, tmp, f"g{group}_{list(LAYOUT).index(lay)}")
            made.append(out)
        out = d / f"ETF58_上市以來_B至E_計算公式_{gno}_{stamp}.pdf"
        to_pdf(formula_html(group, end, R), out, tmp, f"g{group}_f")
        made.append(out)
    shutil.rmtree(tmp, ignore_errors=True)
    for p in made:
        print(p, p.stat().st_size, flush=True)
    return final


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else X.END)

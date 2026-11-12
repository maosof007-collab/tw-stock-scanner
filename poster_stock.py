# -*- coding: utf-8 -*-
"""
poster_stock.py — 個股海報「資料驅動」產生器
=================================================================
系統可算的卡全自動(財報大數+毛利對比圖/營收動能與預估/情境估值/籌碼/價位階梯),
質性卡(結論/營運結構/客戶/題材/風險)由每檔的 dict 餵入。
用法:from poster_stock import stock_poster; stock_poster(cfg)
"""
from __future__ import annotations

import pandas as pd

import deep_report as dr
from poster import shell, card, checks, bignums, bars, flow, save_poster, ud

ROOT = dr.ROOT if hasattr(dr, "ROOT") else None


def _chip_card(ctx, extra_rows: str = "") -> str:
    code = ctx["code"]
    fi = ctx.get("inst30", {}).get("外資張")
    it = ctx.get("inst30", {}).get("投信張")
    rows = ""
    if fi is not None:
        rows += f'<tr><td>外資30日</td><td class="n">{ud(fi, f"{fi:+,} 張")}</td><td>{"買方" if fi>0 else "賣方" if fi<0 else "中性"}</td></tr>'
    if it is not None:
        rows += f'<tr><td>投信30日</td><td class="n">{ud(it, f"{it:+,} 張")}</td><td>{"有機構背書" if it>0 else "缺席"}</td></tr>'
    try:
        m = pd.read_csv(f"data/margin/{code}_margin.csv")
        mg = int(m["margin_balance"].iloc[-1] - m["margin_balance"].iloc[-21])
        mb = int(m["margin_balance"].iloc[-1])
        rows += (f'<tr><td>融資20日</td><td class="n">{ud(mg, f"{mg:+,} 張(餘 {mb:,})")}</td>'
                 f'<td>{"家規紅燈" if mg>500 else "槓桿退場" if mg<-300 else "中性"}</td></tr>')
    except Exception:
        pass
    bh = ctx.get("bigholder")
    if bh is not None and len(bh) >= 9:
        cur, dq = float(bh["大戶%"].iloc[-1]), float(bh["大戶%"].iloc[-1] - bh["大戶%"].iloc[-9])
        rows += (f'<tr><td>大戶>400張</td><td class="n">{cur:.1f}% {ud(round(dq,1), f"8週{dq:+.1f}pp")}</td>'
                 f'<td>{"收籌" if dq>1 else "出貨" if dq<-1 else "持平"}</td></tr>')
    try:
        import warrant_flow as wf
        sc = wf.market_scan().set_index("ucode")
        if code in sc.index and str(sc.loc[code, "動向"]).strip():
            rows += f'<tr><td>權證資金</td><td class="n">{sc.loc[code,"動向"]}</td><td>連續{int(sc.loc[code,"連續天數"])}天高於中位</td></tr>'
    except Exception:
        pass
    return card("籌碼體檢(系統自動)", f"<table><tr><th>指標</th><th>數字</th><th>判讀</th></tr>{rows}{extra_rows}</table>")


def _fin_card(ctx, note: str = "") -> str:
    q = ctx["quarterly"].dropna(subset=["EPS"]).reset_index(drop=True)
    if len(q) < 5:
        return card("最新財報", "<div class='note'>季報資料不足。</div>")
    last, prev = q.iloc[-1], q.iloc[-5]
    rv, rv0 = float(last["營收(億)"]), float(prev["營收(億)"])
    gm, gm0 = float(last["毛利率%"]), float(prev["毛利率%"])
    om, om0 = float(last["營益率%"]), float(prev["營益率%"])
    eps, eps0 = float(last["EPS"]), float(prev["EPS"])
    yoy = (rv / rv0 - 1) * 100 if rv0 else 0
    qname = str(last["季度"])[:7].replace("-", " Q")
    b = bignums([
        ("營收", f"{rv:g} 億", ud(round(yoy), f"年增 {yoy:+.0f}%")),
        ("毛利率", f"{gm:g}%", ud(round(gm - gm0, 1), f"{gm-gm0:+.1f}pp YoY")),
        ("營益率", f"{om:g}%", ud(round(om - om0, 1), f"{om-om0:+.1f}pp YoY")),
        ("EPS", f"{eps:g}", ud(round(eps - eps0, 2), f"去年同期 {eps0:g}")),
    ])
    bb = bars([(f"毛利率 去年", max(gm0, 0), "#8fb7e8"), (f"毛利率 {qname[-2:]}", max(gm, 0), "#2f6db5"),
               (f"營益率 去年", max(om0, 0), "#f3cf8e"), (f"營益率 {qname[-2:]}", max(om, 0), "#f0a63a")])
    return card(f"最新財報({str(last['季度'])[:7]})", b + bb
                + (f'<div class="note">{note}</div>' if note else ""))


def _mom_card(ctx, exam: str) -> str:
    # 近三月一律用 rev_all(每日更新到最新申報月);ctx['monthly'] 另一管線會落後
    ra = pd.read_csv("data/bulk_fin/rev_all.csv.gz", dtype={"code": str})
    mo = ra[ra["code"] == ctx["code"]].tail(3)
    tbl = ""
    for _, r in mo.iterrows():
        y = r.get("yoy%")
        ytxt = ud(round(float(y)), f"{float(y):+.0f}%") if pd.notna(y) else "—"
        tbl += f'<tr><td>{r["ym"]}</td><td class="n">{float(r["revenue"])/100:.2f} 億</td><td class="n">{ytxt}</td></tr>'
    f = ctx["forecast"].head(2)
    a = ctx["assume"]
    latest_ym = str(mo["ym"].max()) if len(mo) else ""
    stale = len(f) and str(f["月份"].iloc[0]) <= latest_ym
    ftbl = ""
    for _, r in f.iterrows():
        ftbl += (f'<tr><td><b>{r["月份"]}</b></td><td class="n">{float(r["去年同月"])/100:.2f} 億</td>'
                 f'<td class="n">{float(r["保守"])/100:.2f}</td><td class="n yl"><b>{float(r["中性"])/100:.2f}</b></td>'
                 f'<td class="n rd">{float(r["樂觀"])/100:.2f}</td></tr>')
    fc_html = ("" if stale else
               f'<table><tr><th>月份</th><th>去年同月</th><th>保守 {a["保守YoY%"]:+g}%</th>'
               f'<th>中性 {a["中性YoY%"]:+g}%</th><th>樂觀 {a["樂觀YoY%"]:+g}%</th></tr>{ftbl}</table>')
    warn = ('<div class="note">⚠ 系統外推視窗落後於最新月營收,三情境預估本檔暫不列,以免誤導。</div>'
            if stale else "")
    return card("營收動能與預估",
        f'<table><tr><th>月份</th><th>億</th><th>YoY</th></tr>{tbl}</table>' + fc_html + warn
        + f'<div class="note">系統三情境(近三月動能外推)。<b>{exam}</b></div>', src="系統預估模型")


def _scn_card(ctx, note: str) -> str:
    px = float(ctx["pstats"]["close"])
    rows = ""
    for _, r in ctx["eps_sc"].iterrows():
        eps = float(r["年化EPS"])
        pe = f"{px/eps:.1f} 倍" if eps > 0 else "—(虧損/無意義)"
        bg = {"保守": 'style="background:#eaf3ff"', "中性": 'class="yl"', "樂觀": 'style="background:#fff3e8"'}.get(str(r["情境"]), "")
        rows += (f'<tr><td {bg}><b>{r["情境"]}</b></td><td class="n">{r["假設淨利率%"]:g}%</td>'
                 f'<td class="n">{eps:g}</td><td class="n">{pe}</td></tr>')
    return card("三種情境估值(年化)",
        f'<table><tr><th>情境</th><th>假設淨利率</th><th>年化 EPS</th><th>現價 {px:g} 隱含 PE</th></tr>{rows}</table>'
        f'<div class="note">{note}</div>', src="系統情境模型")


def _px_card(ctx, extra: str = "") -> str:
    p = ctx["pstats"]
    px, hi, lo = float(p["close"]), float(p["hi252"]), float(p["lo252"])
    code = ctx["code"]
    try:
        import glob
        f = glob.glob(f"data/{code}.*.csv")[0]
        d = pd.read_csv(f)
        ma20 = float(d["Close"].rolling(20).mean().iloc[-1])
    except Exception:
        ma20 = None
    rows = f'<tr><td>{lo:g} 元</td><td class="n">{ud((lo/px-1)*100, f"{(lo/px-1)*100:+.0f}%")}</td><td>年低</td></tr>'
    if ma20:
        tag = "站上,趨勢持有線" if px > ma20 else "<b>站回前只是反彈</b>"
        rows += f'<tr class="yl"><td><b>{ma20:.1f} 元</b></td><td class="n">{ud((ma20/px-1)*100, f"{(ma20/px-1)*100:+.0f}%")}</td><td>MA20:{tag}</td></tr>'
    rows += f'<tr><td>{hi:g} 元</td><td class="n">{ud((hi/px-1)*100, f"{(hi/px-1)*100:+.0f}%")}</td><td>年高(距高 {float(p["off_high"]):+.0f}%)</td></tr>'
    return card("股價檯階", f'<table><tr><th>價位</th><th>相對 {px:g}</th><th>意義</th></tr>{rows}</table>'
                + (f'<div class="note">{extra}</div>' if extra else ""))


def stock_poster(cfg: dict, date: str = "") -> None:
    if not date:
        from twtime import now_tw
        date = f"{now_tw():%Y%m%d}"
    """cfg: code,name,brand,title,subtitle,concl[(kind,html)],struct(html),cust(html),
    cata[(主文,註,紅)],risk[(kind,html)],fin_note,exam,scn_note,px_note,src"""
    ctx = dr.build_deep_context(cfg["code"])
    c_concl = card("投資結論(重點先看)", checks(cfg["concl"]), src=cfg.get("src", ""), extra_cls="grow")
    c_fin = _fin_card(ctx, cfg.get("fin_note", ""))
    c_mom = _mom_card(ctx, cfg.get("exam", "12/10 前後看 11 月營收。"))
    c_struct = card("營運結構", cfg["struct"])
    c_cust = card("客戶與供應鏈位置", cfg["cust"])
    c_cata = card("題材鏈", flow(cfg["cata"]), extra_cls="grow")
    c_chip = _chip_card(ctx)
    c_px = _px_card(ctx, cfg.get("px_note", ""))
    c_scn = _scn_card(ctx, cfg.get("scn_note", "情境=系統淨利率假設年化;估值判讀以隱含 PE 為準,不自創目標價。"))
    c_risk = card("風險與觀察", checks(cfg["risk"]), extra_cls="risk grow")
    cols = [c_concl + c_struct + c_chip,
            c_fin + c_mom + c_cust,
            c_px + c_scn + c_cata + c_risk]
    html = shell(title_html=f'{cfg["name"]}<b>({cfg["code"]})</b>{cfg.get("title","深度研究總整理")}',
                 subtitle=cfg["subtitle"], brand=cfg["brand"], cols=cols,
                 footer=f'素材:{cfg.get("src","系統資料管線")}+系統 2026/11/11 數據 · 本海報為研究筆記非投資建議')
    print("saved:", save_poster(cfg["code"], date, html))

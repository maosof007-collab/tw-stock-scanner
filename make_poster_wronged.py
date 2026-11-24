# -*- coding: utf-8 -*-
"""專題海報:委屈股 — 這一波(10/6 高點起)跌得比大盤多、業績卻還在成長的,有沒有被錯殺?(2026-11-20)
三步篩:①跌 ≥30%、20 日均額 ≥0.5 億 ②10 月營收與 Q3 本業獲利都年增 ≥20%、毛利率沒掉、EPS 年增、不靠業外
③扣掉景氣循環股(現在的獲利是循環高檔,不能拿來判斷)、設備股、股價仍比一年前高 10% 以上的。
循環股判斷兩條:族群(theme_groups+下面 EXTRA 手補)或數據(毛利率歷史擺幅 ≥15 個百分點且現在在頂部 10%)。
每次重跑都讀當下的日線、bulk_fin 月營收與季報;掃描結果存 data/_wronged_scan.csv。
另一張卡反過來看「誰還沒跌」:台積電(2026-11-20 使用者:「流動性不夠,下一個可能要跌的是台積」)——
外資/投信/自營/融資在台積電身上的進出、台積電占全市場成交值、歷次大盤跌破 20% 時台積電最後跌多少。
台積電長歷史存 data/_2330_long.csv(yfinance,到 2026-10),之後接系統日線;ADR 溢價是寫死的快照。
手動重跑:python -X utf8 make_poster_wronged.py"""
import glob
import os

import numpy as np
import pandas as pd

import fin9
import make_poster_2008 as m8
import research_rank as rr
import theme_groups as tg
from poster import bignums, card, checks, save_poster, shell
from twtime import now_tw

PEAK = "2026-10-06"
D = rr.D
CYC = ["記憶體", "PCB", "ABF載板", "封測", "被動元件", "矽晶圓", "晶圓代工", "功率半導體", "石英元件",
       "面板/電子紙", "貨櫃航運", "散裝航運", "鋼鐵", "塑化(大宗)"]
# 系統族群表沒列到、我手補的(憑產業常識,可能有錯)
EXTRA = {"記憶體": ["8271", "5289", "3135", "5386", "6265", "6531"],
         "PCB": ["8358", "6213", "8021", "8155", "3563", "2467", "2493", "3167"],
         "封測": ["6257", "6525", "5285", "2351"],
         "被動元件": ["2375", "3357", "3090", "2472", "6834"],
         "功率半導體": ["5425", "3675"]}
EQUIP = ["6937", "6739", "5443", "6640", "6187", "7734", "7769", "3680", "6223", "6683", "1560", "8091", "3030",
         "8028", "6830", "5434"]
SHOW = {"記憶體": "記憶體(含模組、通路)", "PCB": "PCB(含銅箔基板、銅箔、鑽針、設備)", "ABF載板": "ABF 載板",
        "封測": "封測(含導線架)", "被動元件": "被動元件"}
# 逐檔上網查的結果(2026-11-20;只做了一次搜尋,多數只找到去年的報導)
CHECKED = {"6781": "?2025/12 曾被外資以「競爭壓縮利潤、客戶集中」降評;今年 11 月的消息沒查到",
           "4551": "?11/9 公布 Q3 EPS 2.36、前三季 7.13(年增 96%);沒查到利空",
           "2376": "?11/13 法說:Q3 營收 1,547 億、EPS 12.80,都是新高;沒查到利空",
           "4931": "沒查到今年的報導", "5536": "沒查到今年的報導", "2476": "沒查到今年的報導",
           "8103": "另有單張海報(8103)"}


def scan() -> pd.DataFrame:
    sl = pd.read_csv(D / "stock_list.csv", dtype=str)
    nm, sec = dict(zip(sl.code, sl.name)), dict(zip(sl.code, sl.sector))
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    rev = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    rev["ym"] = rev.ym.astype(str)
    ym_last, q_last = rev.ym.max(), str(q["季度"].max())[:7]
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    rows = []
    for f in glob.glob(str(D / "[0-9][0-9][0-9][0-9].TW*.csv")):
        code = os.path.basename(f)[:4]
        if code not in nm:
            continue
        try:
            d = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        d = d[d.Volume > 0]
        if len(d) < 260 or d.index[-1] < bm.index[-1]:
            continue
        c = d.Close
        r, qq = rev[rev.code == code].tail(15), q[q.code == code].tail(8)
        if len(r) < 7 or len(qq) < 5 or r.ym.iloc[-1] != ym_last or str(qq["季度"].iloc[-1])[:7] != q_last:
            continue
        a, b = qq.iloc[-1], qq.iloc[-5]
        op, op0 = a["營收(億)"] * a["營益率%"] / 100, b["營收(億)"] * b["營益率%"] / 100
        eps4 = qq["EPS"].tail(4).sum()
        rows.append(dict(
            code=code, name=nm[code], sec=sec.get(code, ""), last=float(c.iloc[-1]),
            chg=(c.iloc[-1] / c[:PEAK].iloc[-1] - 1) * 100, y1=(c.iloc[-1] / c.iloc[-251] - 1) * 100,
            amt20=(c * d.Volume).tail(20).mean() / 1e8,
            oct=r["yoy%"].iloc[-1], y3=r["yoy%"].tail(3).mean(),
            acc=r["yoy%"].tail(3).mean() - r["yoy%"].iloc[-6:-3].mean(),
            gm=a["毛利率%"], gm_d=a["毛利率%"] - b["毛利率%"], op0=op0,
            op_yoy=(op / op0 - 1) * 100 if op0 > 0 else np.nan, eps=a["EPS"], eps_ly=b["EPS"],
            pe=c.iloc[-1] / eps4 if eps4 > 0 else np.nan,
            nonop=bool(pd.notna(a["淨利率%"]) and a["淨利率%"] > 0 and a["營益率%"] / a["淨利率%"] < 0.6)))
    return pd.DataFrame(rows)


def gm_hist(code: str) -> tuple:
    """毛利率在自己歷史(fin9 季報,約十年)的最低、最高、現在落在哪(0=最低、1=最高)。"""
    try:
        g = fin9.quarterly_fin(code)["毛利率%"].dropna().astype(float)
    except Exception:
        return np.nan, np.nan, np.nan
    if len(g) < 12 or g.max() <= g.min():
        return np.nan, np.nan, np.nan
    return g.min(), g.max(), (g.iloc[-1] - g.min()) / (g.max() - g.min())


def tsmc_card(bm: pd.Series) -> tuple[str, dict]:
    """反過來看:權值最大的台積電跌得比大盤少,誰在賣、誰在接、歷史上最後有沒有補跌。"""
    loc = pd.read_csv(D / "2330.TW.csv", index_col=0, parse_dates=True)
    old = pd.read_csv(D / "_2330_long.csv", index_col=0, parse_dates=True)["Close"]
    ts = pd.concat([old, loc.Close[loc.index > old.index[-1]]]).dropna()   # 歷史段用未還原價(跟加權指數同口徑),系統日線是還原價
    last = bm.index[-1]
    w = slice(pd.Timestamp(PEAK) + pd.Timedelta(days=1), last)
    chg = (ts[:last].iloc[-1] / ts[:PEAK].iloc[-1] - 1) * 100
    i = pd.read_csv(D / "institutional" / "2330_inst.csv", parse_dates=["date"]).set_index("date").sort_index()
    fi = (i["外陸資買賣超股數(不含外資自營商)"] / 1000)[w]
    it, dh, ds = (i["it_net"] / 1000)[w], (i["dealer_hedge_net"] / 1000)[w], (i["dealer_self_net"] / 1000)[w]
    amt = (fi * loc.Close.reindex(fi.index) * 1000).sum() / 1e8
    mg = pd.read_csv(D / "margin" / "2330_margin.csv", parse_dates=["date"]).set_index("date").sort_index()["margin_balance"]
    mg0, mg1 = mg[:PEAK].iloc[-1], mg[:last].iloc[-1]
    other = -(fi.sum() + it.sum() + dh.sum() + ds.sum()) - (mg1 - mg0)
    # 全市場成交值與台積電占比(各檔收盤×量加總,不含 ETF)
    V = {}
    for f in glob.glob(str(D / "[0-9][0-9][0-9][0-9].TW*.csv")):
        try:
            d = pd.read_csv(f, index_col=0, parse_dates=True, usecols=["Date", "Close", "Volume"])["2026-09-01":]
        except Exception:
            continue
        if len(d):
            V[os.path.basename(f)[:4]] = d.Close * d.Volume / 1e8
    A = pd.DataFrame(V)
    tot, sh = A.sum(axis=1), A["2330"] / A.sum(axis=1) * 100
    mo = sorted({d.strftime("%Y-%m") for d in tot.index})
    e50 = pd.read_csv(D / "0050.TW.csv", index_col=0, parse_dates=True).Volume / 1000
    try:
        import macro
        mm = macro.build_market_margin_series().iloc[-1]
        mr = f"全市場融資維持率 <b>{mm.ratio_real:.1f}%</b>(系統推估,{pd.Timestamp(mm.date).month}/{pd.Timestamp(mm.date).day}),追繳線是 130%"
    except Exception:
        mr = "全市場融資維持率讀不到"
    # 歷次大盤跌破 20%:台積電自己的最大跌幅(大盤高點前 90 天內的高點 → 大盤最低點後 60 天內的低點)
    s = m8.load()
    t_h = "<table><tr><th>大盤跌破 20%</th><th>大盤最大跌幅</th><th>台積電最大跌幅</th><th>跌破後台積電再跌</th></tr>"
    dds = []
    for e in m8.episodes(s):
        if e["peak"].year < 2007:
            continue
        hi = ts[e["peak"] - pd.Timedelta(days=90):e["trig"]].max()
        cur = e["peak"] >= pd.Timestamp(PEAK)
        lo = ts[e["trig"]:e["low_d"] + pd.Timedelta(days=60)].min()
        more = (ts[:e["low_d"]].iloc[-1] / ts[:e["trig"]].iloc[-1] - 1) * 100
        dd = (lo / hi - 1) * 100
        if not cur:
            dds.append(dd)
        lab = "這一次" if cur else f'{e["trig"].year}/{e["trig"].month}'
        t_h += (f'<tr{" class=yl" if cur else ""}><td class="n">{lab}</td>'
                f'<td class="n">{e["dd"]:.1f}%</td><td class="n">{dd:.1f}%</td>'
                f'<td class="n">{"沒再跌" if more >= 0 else f"{more:.1f}%"}</td></tr>')
    t_h += "</table>"
    pk = ts[:PEAK].iloc[-1]
    n_ge = sum(1 for d_, e in zip(dds[-4:], [x for x in m8.episodes(s) if 2007 <= x["peak"].year and x["peak"] < pd.Timestamp(PEAK)][-4:]) if d_ <= e["dd"] + 0.5)
    t_f = ("<table><tr><th>10/7 以來在台積電身上</th><th>張數</th></tr>"
           f'<tr><td>外資(賣超 {int((fi < 0).sum())}/{len(fi)} 天)</td><td class="n gn">{fi.sum():+,.0f}</td></tr>'
           f'<tr><td>投信</td><td class="n rd">{it.sum():+,.0f}</td></tr>'
           f'<tr><td>自營商避險(權證、ETF 造市)</td><td class="n rd">{dh.sum():+,.0f}</td></tr>'
           f'<tr><td>融資增加</td><td class="n rd">{mg1 - mg0:+,.0f}</td></tr>'
           f'<tr><td>其他(散戶現股、政府基金等,資料分不開)</td><td class="n rd">{other:+,.0f}</td></tr></table>')
    body = bignums([
        ("台積電", f"{chg:.1f}%", "10/6 以來"),
        ("大盤", f"{(bm.iloc[-1] / bm[PEAK] - 1) * 100:.1f}%", "同期間"),
        ("外資賣超", f"{-fi.sum() / 1e4:.1f} 萬張", f"約 {-amt:,.0f} 億"),
        ("占全市場成交", f"{sh[mo[-1]].mean():.1f}%", f"{int(mo[0][5:])} 月是 {sh[mo[0]].mean():.1f}%")]) + t_f + checks([
        ("wn", f"<b>成交值沒有變少</b>:全市場(個股加總){int(mo[0][5:])} 月日均 {tot[mo[0]].mean():,.0f} 億、{int(mo[-1][5:])} 月 {tot[mo[-1]].mean():,.0f} 億。"
               f"變的是集中度:台積電占比從 {sh[mo[0]].mean():.1f}% 升到 {sh[mo[-1]].mean():.1f}%,單日最高 {sh.max():.1f}%({sh.idxmax().month}/{sh.idxmax().day})"),
        ("xx", f"<b>外資一路賣、國內一路接</b>:0050 成交量從 9 月日均 {e50['2026-09'].mean() / 1e4:.1f} 萬張放大到近 20 日 {e50.tail(20).mean() / 1e4:.1f} 萬張;"
               f"台積電融資 {mg0:,.0f} → {mg1:,.0f} 張,一年最高是 {mg.tail(250).max():,.0f}"),
        ("wn", "?海外賣得比台灣兇:台積電 ADR 對台股的溢價,10 月平均 14.9%,11/17~18 約 9.5%(yfinance 收盤換算)"),
        ("xx", mr + "。接的人如果被追繳或贖回 ETF,能賣的就是手上最大的那一檔"),
    ]) + t_h + (
        f'<div class="note">●歷史 6 次裡,最近 4 次台積電最後的跌幅有 {n_ge} 次跟大盤一樣或更深;2008、2011 比大盤少。'
        f"照比例換算(高點 {pk:,.0f}):跟大盤現在一樣是 {pk * (1 + (bm.iloc[-1] / bm[PEAK] - 1)):,.0f};"
        f"6 次的範圍 {max(dds):.1f}% ~ {min(dds):.1f}%,是 {pk * (1 + max(dds) / 100):,.0f} ~ {pk * (1 + min(dds) / 100):,.0f}。這是歷史比例,不是預測。"
        "台積電最大跌幅=大盤高點前 90 天內的高點,到大盤最低點後 60 天內的低點。</div>")
    return card("🧊 反過來看:誰還沒跌——台積電", body, f"●至 {last.month}/{last.day} 收盤"), dict(chg=chg, fi=fi.sum(), n_ge=n_ge)


def pc(x, nd=0) -> str:
    return "—" if pd.isna(x) else f'<span class="{"rd" if x > 0 else "gn"}">{x:+.{nd}f}%</span>'


def main() -> str:
    x = scan()
    x.round(2).to_csv(D / "_wronged_scan.csv", index=False, encoding="utf-8-sig")
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    bm_chg = (bm.iloc[-1] / bm[PEAK] - 1) * 100
    md = f"{bm.index[-1].month}/{bm.index[-1].day}"
    date = now_tw().strftime("%Y%m%d")
    c_tsmc, tz = tsmc_card(bm)
    liq = x[x.amt20 >= 0.5]
    deep = liq[liq.chg <= -30]
    ok = ((deep.oct >= 20) & (deep.y3 >= 20) & (deep.eps > 0) & (deep.op0 > 0) & (deep.op_yoy >= 20)
          & (deep.gm_d >= -1) & (~deep.nonop) & (deep.eps > deep.eps_ly))
    good = deep[ok].copy()
    bad = deep[(deep.oct < 0) | (deep.eps <= 0) | (deep.eps < deep.eps_ly)]

    th = {}
    for k, v in tg.THEME_GROUPS.items():
        for c in v:
            th.setdefault(str(c)[:4], []).append(k)
    extra = {c: k for k, v in EXTRA.items() for c in v}

    def grp(c):
        own = [t for t in th.get(c, []) if t in CYC]
        return own[0] if own else extra.get(c, "")
    good["grp"] = good.code.map(grp)
    good["hand"] = good.code.map(lambda c: c in extra and not [t for t in th.get(c, []) if t in CYC])
    good[["gm_lo", "gm_hi", "gm_pos"]] = [gm_hist(c) for c in good.code]
    good["peak_data"] = ((good.gm_hi - good.gm_lo) >= 15) & (good.gm_pos >= 0.9)
    good["equip"] = good.code.isin(EQUIP) | good.code.map(lambda c: "半導體設備" in th.get(c, []))
    cyc = good[good.grp != ""]
    dat = good[(good.grp == "") & good.peak_data & ~good.equip]
    eqp = good[(good.grp == "") & good.equip]
    rest = good[(good.grp == "") & ~good.peak_data & ~good.equip]
    high = rest[rest.y1 > 10]
    fin = rest[(rest.y1 <= 10) & (rest.eps >= 1) & (rest.pe <= 30)].sort_values("y1").copy()
    rev = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    fl = {c: (rr._one(c, rev, q) or {}) for c in fin.code}

    def note(r) -> str:
        t, f = [], fl.get(r.code, {})
        if (f.get("融資%") or 0) >= 30:
            t.append(f'融資使用率 {f["融資%"]:.0f}%')
        if f.get("爆量窗"):
            t.append("爆量窗")
        if r.acc <= -10:
            t.append("營收成長放慢")
        if pd.notna(r.gm_pos) and r.gm_pos >= 0.9:
            t.append("毛利率在自己高點")
        return "、".join(t) or "—"

    # ── 欄 1 ──
    lq = liq.assign(g=pd.qcut(liq.chg, 5, labels=["跌最多", "次多", "中間", "次少", "跌最少"]))
    t_q = "<table><tr><th>依跌幅分五組</th><th>10/6 以來</th><th>Q3 本業獲利年增</th><th>比一年前</th><th>本益比</th></tr>"
    for g, d in lq.groupby("g", observed=True):
        t_q += (f'<tr{" class=yl" if g == "跌最多" else ""}><td>{g}({len(d)} 檔)</td><td class="n">{d.chg.median():.0f}%</td>'
                f'<td class="n">{pc(d.op_yoy.median())}</td><td class="n">{pc(d.y1.median())}</td><td class="n">{d.pe.median():.0f} 倍</td></tr>')
    t_q += "</table>"
    q1 = lq[lq.g == "跌最多"]
    c_concl = card("結論(重點先看)", checks([
        ("wn", f"<b>有,但比表面上少很多</b>。跌超過 30% 的 {len(deep)} 檔裡,{len(good)} 檔的營收和本業獲利都還在成長;"
               f"扣掉循環股、設備股、股價仍明顯高於一年前的,剩 <b>{len(fin)} 檔</b>"),
        ("xx", f"<b>這一波殺的不是業績差的,是漲最多、最貴的</b>:跌最多的那五分之一,Q3 本業獲利年增中位數 "
               f"{q1.op_yoy.median():+.0f}%,股價仍比一年前高 {q1.y1.median():.0f}%,本益比 {q1.pe.median():.0f} 倍"),
        ("xx", f"<b>循環股不能算委屈</b>:記憶體、PCB/ABF、封測、被動元件等 {len(cyc)} 檔,現在的毛利率大多是自己十年來最高。"
               "獲利在循環高點時本益比最低,市場跌的是「之後會掉下來」"),
        ("wn", f"剩下的 {len(fin)} 檔也大多在 AI 供應鏈(備援電池、伺服器、電源、廠務、連接線)。"
               "這一波跌的起因就是懷疑 AI 支出,它們委不委屈,取決於同一件事"),
        ("wn", "「業績成長」是已經公布的 10 月營收和 Q3 財報,是過去的數字;市場在跌的是明年"),
        ("xx", f"<b>反過來,還沒跌夠的是台積電</b>:10/6 以來 {tz['chg']:.1f}%,比大盤少。外資已賣超 {-tz['fi'] / 1e4:.1f} 萬張,"
               f"接的是投信、ETF 和散戶;歷史上最近 4 次有 {tz['n_ge']} 次,台積電最後跌得跟大盤一樣或更深(見下方)"),
        ("xx", "大盤燈號仍是 🔴 禁開新倉。這張表是體檢,不是買單"),
    ]), src=f"●系統數據,價格至 {md}", extra_cls="grow")
    c_all = card(f"全貌:10/6 → {md},大盤 {bm_chg:.1f}%", bignums([
        ("跌超過 30%", f"{len(deep)}", f"有量的 {len(liq)} 檔裡"),
        ("業績還在成長", f"{len(good)}", "營收、本業獲利都年增 ≥20%"),
        ("業績已轉差", f"{len(bad)}", "10 月年減、Q3 虧損或 EPS 年減"),
        ("其餘", f"{len(deep) - len(good) - len(bad)}", "成長但沒過門檻")]) + t_q
        + '<div class="note">●母體:20 日均額 ≥0.5 億、有 10 月營收與 Q3 財報的上市櫃股票。中位數。'
          "本業獲利=營收×營益率。「業績還在成長」的完整條件:10 月與近三月營收年增 ≥20%、Q3 本業獲利年增 ≥20%、"
          "毛利率年減不超過 1 個百分點、EPS 年增、獲利不是靠業外。</div>")

    # ── 欄 2:循環股 ──
    def members(d) -> str:
        return "、".join(f'{r["name"]}{"*" if r.hand else ""}({r.chg:.0f}%)' for _, r in d.sort_values("chg").iterrows())
    t_c = "<table><tr><th>族群</th><th>檔數</th><th>成員(10/6 以來跌幅)</th></tr>"
    for g in sorted(cyc.grp.unique(), key=lambda g: -len(cyc[cyc.grp == g])):
        d = cyc[cyc.grp == g]
        t_c += f'<tr><td><b>{SHOW.get(g, g)}</b></td><td class="n">{len(d)}</td><td><small>{members(d)}</small></td></tr>'
    t_c += "</table>"
    top = cyc[cyc.gm_pos >= 0.9]
    c_cyc = card(f"🔄 循環股 {len(cyc)} 檔:業績最好,但不算委屈", t_c
                 + f'<div class="note">其中 {len(top)} 檔現在的毛利率落在自己歷史最高的一成以內。標 * 的是系統族群表沒列、我手補的分類,可能有錯。</div>',
                 "系統族群表+手補")
    ex = good[good.code.isin(["2408", "2344", "8046", "3037", "8150", "3026"])].sort_values("gm_hi", ascending=False)
    t_e = "<table><tr><th>公司</th><th>毛利率歷史最低</th><th>現在</th><th>本益比</th></tr>"
    for _, r in ex.iterrows():
        t_e += (f'<tr><td><b>{r["name"]}</b> {r.code}</td><td class="n">{r.gm_lo:.1f}%</td>'
                f'<td class="n rd">{r.gm:.1f}%</td><td class="n">{r.pe:.1f} 倍</td></tr>')
    t_e += "</table>"
    c_why = card("為什麼循環股會讓我們誤判", t_e + checks([
        ("xx", "循環股賺最多的時候本益比最低、營收年增最高——剛好全部符合「委屈」的篩選條件"),
        ("xx", "它們的獲利跟著報價走,報價一反轉,毛利率可以從最高掉回負的;上表的歷史最低就是上一次谷底"),
        ("wn", "看這類股票要看報價、庫存、產能利用率的方向,不是看上一季賺多少。這些我這次沒查"),
    ]), "●系統季報")
    t_o = "<table><tr><th>排除原因</th><th>檔數</th><th>成員</th></tr>"
    for nmx, d in ((f"毛利率擺幅 ≥15 個百分點、現在在頂部(數據判斷)", dat), ("設備與耗材(跟著客戶資本支出走)", eqp),
                   ("股價仍比一年前高 10% 以上", high)):
        t_o += f'<tr><td>{nmx}</td><td class="n">{len(d)}</td><td><small>{members(d)}</small></td></tr>'
    t_o += "</table>"
    c_oth = card("其他被我排除的", t_o + '<div class="note">「股價仍比一年前高」那一組:業績好,但跌下來只是吐回漲幅,'
                                    "不符合「業績變好、股價卻回到原點」。</div>")

    # ── 欄 3:名單 ──
    t_f = "<table><tr><th>公司</th><th>10/6 以來</th><th>比一年前</th><th>Q3 本業獲利</th><th>本益比</th><th>註記</th></tr>"
    for _, r in fin.iterrows():
        t_f += (f'<tr><td><b>{r["name"]}</b> {r.code}<br><small>{r.sec}</small></td><td class="n">{r.chg:.0f}%</td>'
                f'<td class="n">{pc(r.y1)}</td><td class="n">{pc(r.op_yoy)}</td><td class="n">{r.pe:.1f}</td>'
                f'<td><small>{note(r)}</small></td></tr>')
    t_f += "</table>"
    c_fin = card(f"📋 篩到最後剩 {len(fin)} 檔", t_f
                 + '<div class="note">條件:非循環、非設備、股價不高於一年前 10%、Q3 單季 EPS ≥1、近四季本益比 ≤30 倍。'
                   "依「比一年前」排序,最上面的是股價比一年前低最多的。排名是體檢,不是買單。</div>", f"●至 {md} 收盤")
    t_n = "<table><tr><th>公司</th><th>查到什麼</th></tr>"
    for _, r in fin.iterrows():
        t_n += f'<tr><td><b>{r["name"]}</b> {r.code}</td><td><small>{CHECKED.get(r.code, "沒查")}</small></td></tr>'
    t_n += "</table>"
    c_news = card("有沒有個股自己的利空", t_n
                  + '<div class="note">查證日 2026/11/20,每檔只做一次網路搜尋,多數只找到去年的報導。'
                    "「沒查到」不等於沒有;法說簡報原檔都沒讀。</div>")
    c_risk = card("⚠️ 這張海報的限制", checks([
        ("wn", "篩選用的是已公布的營收和財報。業績是落後指標,2008 年出口最慘的數字出現在股市最低點之後"),
        ("wn", "循環股分類一部分是我手補的;設備股算不算循環、AI 供應鏈算不算循環,判斷不同名單就不同"),
        ("wn", "本益比用近四季 EPS,沒有扣一次性損益;毛利率歷史用系統季報(約十年)"),
        ("wn", f"價格是 {md} 收盤;今天(11/20)盤中大盤又跌,沒有算進來"),
        ("wn", "這是體檢,不是買賣建議"),
    ]), extra_cls="risk")

    html = shell(
        title_html="這一波下殺,<b>誰委屈了</b>?",
        subtitle=(f"跌超過 30% 的 {len(deep)} 檔裡,{len(good)} 檔業績還在成長;扣掉循環股、設備股和股價仍高於一年前的,"
                  f"剩 {len(fin)} 檔——而且大多還在 AI 供應鏈"),
        brand="委屈股",
        cols=[c_concl + c_all + c_tsmc, c_cyc + c_why + c_oth, c_fin + c_news + c_risk],
        footer=(f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:系統日線、月營收、季報、族群表、融資與爆量旗標;個股消息為網路搜尋 · 體檢非投資建議"))
    return str(save_poster("委屈股", date, html))


if __name__ == "__main__":
    print(main())

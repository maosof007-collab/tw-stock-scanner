# -*- coding: utf-8 -*-
"""族群海報:電子通路 — 股價弱是不是因為 overbooking / 出貨遞延?用財報查。(2026-11-16)
存貨/預收/借款/現金流讀 data/_dist_bs.csv(scripts/dist_bs.py 從公開資訊觀測站抓);
營收、毛利讀 data/bulk_fin;股價即時算。法說內容寫死在下面(●=開過原文、?=只看到摘要)。
手動重跑:python -X utf8 make_poster_dist.py"""
import json

import numpy as np
import pandas as pd

import sector_cluster as sc
from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

Q, Q_PREV, Q_LY = "2026-09", "2026-06", "2025-09"          # 財報季別(換季時改這三個)
QD = {"2026-09": "2026-09-30", "2026-06": "2026-06-30", "2025-09": "2025-09-30"}
M_NOW, M_REF = "2026-10", "2026-07"                        # 季初月比季初月,避開季底衝量


def main() -> str:
    date = now_tw().strftime("%Y%m%d")
    b = pd.read_csv(sc.D / "_dist_bs.csv", dtype={"code": str}).set_index("code")
    fq = pd.read_csv(sc.D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    fq = fq[fq.code.isin(b.index)]
    rv = pd.read_csv(sc.D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    mon = rv[rv.code.isin(b.index)].pivot(index="code", columns="ym", values="revenue") / 100   # 億

    def fin(q, col):
        return fq[fq["季度"] == QD[q]].set_index("code")[col].reindex(b.index)

    rev, rev_p, rev_ly = fin(Q, "營收(億)"), fin(Q_PREV, "營收(億)"), fin(Q_LY, "營收(億)")
    gm, gm_p = fin(Q, "毛利率%"), fin(Q_PREV, "毛利率%")
    col = lambda k, q: b.get(f"{k}_{q}", pd.Series(np.nan, index=b.index))
    inv, inv_p, inv_ly = col("inv", Q), col("inv", Q_PREV), col("inv", Q_LY)
    dio = inv / (rev * (1 - gm / 100)) * 91.25
    dio_p = inv_p / (rev_p * (1 - gm_p / 100)) * 91.25
    pct = lambda a, c: (a / c - 1) * 100
    T = lambda s: float(s.sum())
    gp = T(rev * gm / 100)

    ctx = sc.load()
    P, r1, r20 = ctx["P"], ctx["r1"].iloc[-1], ctx["r20"].iloc[-1]
    cs = [c for c in b.index if c in P.columns]
    hi60 = P[cs].iloc[-60:].max()
    off = (P[cs].iloc[-1] / hi60 - 1) * 100
    below = ctx["below"].iloc[-1][cs]
    md = f"{int(ctx['last'][5:7])}/{int(ctx['last'][8:10])}"
    nm = b["名"]

    try:
        lamp = json.load(open(sc.D / "_market_risk.json", encoding="utf-8"))
        lamp_s = f"大盤燈號 {lamp['lamp']}({lamp['rule']})"
    except Exception:
        lamp_s = "大盤燈號讀不到"

    c_num = card(f"17 家合計:{Q[:4]} 第三季財報", bignums([
        ("存貨", f"{T(inv):,.0f} 億", f"季增 {pct(T(inv), T(inv_p)):+.0f}%、年增 {pct(T(inv), T(inv_ly)):+.0f}%"),
        ("營收", f"{T(rev):,.0f} 億", f"季增 {pct(T(rev), T(rev_p)):+.0f}%、年增 {pct(T(rev), T(rev_ly)):+.0f}%"),
        ("前三季營業現金流", f"{T(b.ocf_9m):+,.0f} 億", f"去年同期 {T(b.ocf_9m_ly):+,.0f} 億"),
    ]))

    w = "3036"   # 文曄:唯一有公司說法的遞延實例
    m_dn = [c for c in b.index if mon.loc[c, M_NOW] < mon.loc[c, M_REF]]
    ex = [c for c in b.index if c != w]
    L = [
        ("xx", f"<b>弱是確定的,而且不是今天才弱</b>:{len(cs)} 檔近 20 日全部下跌({r20[cs].max():+.0f}%~{r20[cs].min():+.0f}%)、"
               f"{int(below.sum())} 檔在季線下;今日中位數 {r1[cs].median():+.1f}%"),
        ("xx", f"<b>存貨漲得比營收快</b>:第三季營收季增 {pct(T(rev), T(rev_p)):+.0f}%,存貨季增 {pct(T(inv), T(inv_p)):+.0f}%"
               f"({T(inv_p):,.0f}→{T(inv):,.0f} 億);一年來營收 {pct(T(rev), T(rev_ly)):+.0f}%、存貨 {pct(T(inv), T(inv_ly)):+.0f}%"),
        ("xx", f"<b>貨是借錢囤的</b>:前三季營業現金流 {T(b.ocf_9m):+,.0f} 億(去年同期 {T(b.ocf_9m_ly):+,.0f} 億),"
               f"短期借款一年 {T(col('stdebt', Q_LY)):,.0f}→{T(col('stdebt', Q)):,.0f} 億"),
        ("wn", f"<b>客戶先付錢搶貨</b>:預收款(合約負債)文曄 {b.loc[w, 'cl_' + Q_LY]:.0f}→{b.loc[w, 'cl_' + Q]:.0f} 億、"
               f"大聯大 {b.loc['3702', 'cl_' + Q_LY]:.0f}→{b.loc['3702', 'cl_' + Q]:.0f} 億、擎亞 {b.loc['8096', 'cl_' + Q_LY]:.0f}→{b.loc['8096', 'cl_' + Q]:.0f} 億;"
               f"通路付給原廠的預付款 {T(col('prepay', Q_LY)):,.0f}→{T(col('prepay', Q)):,.0f} 億。"
               "這是缺貨搶貨的證據,也是重複下單會發生的環境;訂單有沒有重複,財報看不到"),
        ("wn", f"<b>遞延有一個實例</b>:●文曄 11/5 法說「伺服器與資料中心業務第3季雖面臨出貨節奏調整」——"
               f"營收季增 {pct(rev[w], rev_p[w]):+.0f}%、存貨季增 {pct(inv[w], inv_p[w]):+.0f}%({inv_p[w]:,.0f}→{inv[w]:,.0f} 億)。"
               f"公司估第四季營收約 7,500 億(季增 26%);10 月營收 {mon.loc[w, M_NOW]:,.0f} 億、月增 "
               f"{pct(mon.loc[w, M_NOW], mon.loc[w, '2026-09']):+.0f}%,目前照公司說的在出"),
        ("wn", "<b>提前拉貨是公司自己講的</b>:●文曄:汽車、消費性、PC、手機受提前拉貨影響,第四季都季減;"
               "?大聯大 8 月法說:客戶預期漲價與缺貨,第二季底提前拉貨;?大聯大第四季財測 EPS 5.13~5.81 元(第三季 5.96)"),
        ("wn", f"10 月營收比 7 月(季初比季初):17 家合計 {pct(T(mon[M_NOW]), T(mon[M_REF])):+.0f}%,"
               f"扣掉文曄是 {pct(T(mon.loc[ex, M_NOW]), T(mon.loc[ex, M_REF])):+.0f}%;{len(m_dn)} 家比 7 月少"
               f"({'、'.join(nm[c] for c in m_dn)})"),
        ("xx", f"<b>毛利薄,存貨跌價吃得快</b>:17 家單季毛利合計 {gp:,.0f} 億、存貨 {T(inv):,.0f} 億——"
               f"存貨價值每跌 1% 是 {T(inv) / 100:,.0f} 億,等於單季毛利的 {T(inv) / gp:.0f}%"),
        ("xx", f"{lamp_s}"),
    ]
    c_concl = card("結論(重點先看)", checks(L), src="●=開過原文 ?=只看到摘要;其餘為財報與系統計算", extra_cls="grow")

    big = rev.sort_values(ascending=False).index[:11]
    t = ('<table><tr><th>公司</th><th>營收</th><th>存貨</th><th>存貨天數</th><th>預收款</th><th>前三季營業現金流</th></tr>')
    for c in big:
        cl, cl_ly, ocf = b.loc[c, "cl_" + Q], b.loc[c, "cl_" + Q_LY], b.loc[c, "ocf_9m"]
        cl_s = f"{cl:,.0f} 億<br><small>去年 {cl_ly:,.0f}</small>" if pd.notna(cl) else "<small>未列</small>"
        t += (f'<tr><td><b>{nm[c]}</b> {c}<br><small>毛利率 {gm[c]:.1f}%</small></td>'
              f'<td class="n">{rev[c]:,.0f} 億<br><small>季 {pct(rev[c], rev_p[c]):+.0f}%、年 {pct(rev[c], rev_ly[c]):+.0f}%</small></td>'
              f'<td class="n">{inv[c]:,.0f} 億<br><small>季 {pct(inv[c], inv_p[c]):+.0f}%、年 {pct(inv[c], inv_ly[c]):+.0f}%</small></td>'
              f'<td class="n">{dio[c]:.0f} 天<br><small>前季 {dio_p[c]:.0f}</small></td>'
              f'<td class="n">{cl_s}</td>'
              f'<td class="n">{ud(round(ocf), f"{ocf:+,.0f} 億")}'
              f'<br><small>去年 {b.loc[c, "ocf_9m_ly"]:+,.0f}</small></td></tr>')
    c_tab = card(f"逐家:{Q[:4]} 第三季(營收前 11 大)", t + "</table>"
                 + '<div class="note">存貨天數=期末存貨÷當季銷貨成本×91 天(媒體用平均存貨算,數字會比較低)。'
                   "存貨長得比營收快最多的是文曄、大聯大;存貨季減的有至上、擎亞、增你強。</div>",
                 src="公開資訊觀測站")

    p = '<table><tr><th>公司</th><th>今日</th><th>20 日</th><th>距 60 日高</th><th>10 月營收<br>比 7 月</th></tr>'
    for c in r20[cs].sort_values().index:
        p += (f'<tr><td><b>{nm[c]}</b> {c}</td><td class="n">{ud(round(r1[c], 1), f"{r1[c]:+.1f}%")}</td>'
              f'<td class="n">{r20[c]:+.0f}%</td><td class="n">{off[c]:+.0f}%</td>'
              f'<td class="n">{pct(mon.loc[c, M_NOW], mon.loc[c, M_REF]):+.0f}%</td></tr>')
    c_px = card(f"{md} 股價:17 檔依 20 日跌幅排序", p + "</table>")

    c_next = card("接下來看什麼(會改變結論的數字)", checks([
        ("wn", f"12/10 前公布的 11 月營收:文曄第四季要到 7,500 億,11、12 月合計還要約 {7500 - mon.loc[w, M_NOW]:,.0f} 億"),
        ("wn", "大聯大、聯強 11 月營收有沒有回升;10 月各月減三成,但季初本來就會掉(大聯大 7 月也月減 24%)"),
        ("wn", "第四季財報的存貨金額與跌價損失;預收款如果下降而營收沒跟上,就是訂單取消或再遞延"),
        ("wn", f"記憶體報價:至上、擎亞主要代理三星記憶體,第三季營收年增 {pct(rev['8112'], rev_ly['8112']):.0f}%、{pct(rev['8096'], rev_ly['8096']):.0f}%"),
        ("ok", "財報數字重抓:python -X utf8 scripts/dist_bs.py;本海報重產:python -X utf8 make_poster_dist.py"),
    ]), extra_cls="risk grow")

    html = shell(
        title_html="電子<b>通路</b>:存貨與遞延查核",
        subtitle=f"{md} 17 檔 20 日中位數 {r20[cs].median():+.0f}%;存貨一年 {pct(T(inv), T(inv_ly)):+.0f}%、前三季營業現金流 {T(b.ocf_9m):+,.0f} 億",
        brand="族群查核",
        cols=[c_num + c_concl, c_tab, c_px + c_next],
        footer=f"素材:公開資訊觀測站 {Q[:4]} 第三季財報、月營收、系統 {date[:4]}/{date[4:6]}/{date[6:]} 日線 · 本海報為研究筆記非投資建議")
    return str(save_poster("電子通路", date, html))


if __name__ == "__main__":
    print("saved:", main())

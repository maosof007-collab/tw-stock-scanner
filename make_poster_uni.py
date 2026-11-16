# -*- coding: utf-8 -*-
"""族群海報:統一集團 — 集團 8 檔裡,哪幾檔在電子出事時是退路、哪幾檔不是。(2026-11-16)
大跌日/相關係數用 make_poster_fin.haven() 即時算;營收、EPS 讀 data/bulk_fin;
股利與持股是查證資料(●=開過原文或官方表、?=只看到摘要或評論)。
手動重跑:python -X utf8 make_poster_uni.py"""
import glob
import json

import pandas as pd

import make_poster_fin as mf
from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

# (代號, 做什麼, 和統一的關係, 2026 現金股利)
MEM = [
    ("1216", "食品飲料、母公司", "母公司", 3.0),
    ("2912", "7-ELEVEN、康是美、星巴克", "?統一持股 45.40%(2026/5 董監持股,摘要)", 9.0),
    ("1232", "黃豆油、豆粉", "?統一持股 38.5%(評論,沒對年報)", 7.2),
    ("2855", "證券經紀、自營", "●統一以權益法認列", 2.11),
    ("9907", "馬口鐵、包裝", "●統一的包裝事業", 1.18),
    ("1789", "原料藥", "?統一是法人董事(2023 年資料)", 0.29),
    ("2511", "建設", "?統一是法人董事(2023 年資料)", 0.3),
    ("5902", "洋酒、食品代理", "?關係企業,持股我沒查到", 1.65),
]


def main() -> str:
    h = mf.haven()
    X, bm, sl = h["X"], h["bm"], h["sl"]
    CD = X[X["大盤"] <= mf.CRASH]
    last, pk = bm.index[-1], bm.iloc[-120:].idxmax()
    md, pkmd = f"{int(last[5:7])}/{int(last[8:10])}", f"{int(pk[5:7])}/{int(pk[8:10])}"
    date = now_tw().strftime("%Y%m%d")
    fq = pd.read_csv(mf.D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    rv = pd.read_csv(mf.D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    rows = []
    for c, biz, rel, div in MEM:
        raw = pd.read_csv(glob.glob(str(mf.D / f"{c}.TW*.csv"))[0]).dropna(subset=["Close"]).set_index("Date")
        s = raw.Close.reindex(bm.index)
        r = s.pct_change(fill_method=None) * 100
        rc = r[CD.index].dropna()
        y = pd.DataFrame({"e": X["電子"], "s": r}).iloc[-250:]
        q = fq[fq.code == c].sort_values("季度")
        m = rv[rv.code == c].sort_values("ym")
        rec = dict(code=c, name=sl.name[c], biz=biz, rel=rel, div=div, px=s.iloc[-1], d1=r.iloc[-1],
                   d20=(s.iloc[-1] / s.iloc[-21] - 1) * 100, since=(s.iloc[-1] / s[pk] - 1) * 100,
                   yr=(s.iloc[-1] / s.iloc[-240:].mean() - 1) * 100, off=(s.iloc[-1] / s.iloc[-250:].max() - 1) * 100,
                   cavg=rc.mean(), cless=int((rc > CD["大盤"][rc.index]).sum()), cn=len(rc), corr=y.corr().iloc[0, 1],
                   amt=(raw.Close * raw.Volume).iloc[-20:].mean() / 1e8, e9=None, e9ly=None, e4=None,
                   yoy=m["yoy%"].iloc[-1], yoy3=(m.revenue.iloc[-3:].sum() / m.revenue.iloc[-15:-12].sum() - 1) * 100)
        try:
            i = pd.read_csv(mf.D / "institutional" / f"{c}_inst.csv")
            fc = [k for k in i.columns if "外陸資買賣超" in k or "外資買賣超" in k][0]
            rec["fi"] = i[fc].fillna(0).iloc[-20:].sum() * s.iloc[-1] / 1e8 if i.date.iloc[-1] == bm.index[-1] else None
        except Exception:
            rec["fi"] = None
        if len(q) >= 7:
            rec.update(e9=q.EPS.iloc[-3:].sum(), e9ly=q.EPS.iloc[-7:-4].sum(), e4=q.EPS.iloc[-4:].sum())
        rows.append(rec)
    S = pd.DataFrame(rows).set_index("code")
    g = lambda c, k: S.loc[c, k]
    lst = lambda cs, k, f="{:+.1f}%": "、".join(f"{g(c, 'name')} {f.format(g(c, k))}" for c in cs)
    HAVEN, SMALL = ["1216", "2912", "1232"], ["1789", "2511", "5902"]
    try:
        lamp = json.load(open(mf.D / "_market_risk.json", encoding="utf-8"))
        lamp_s = f"大盤燈號 {lamp['lamp']}({lamp['rule']})"
    except Exception:
        lamp_s = "大盤燈號讀不到"

    c_num = card(f"{pkmd} 大盤高點到 {md}(大盤 {(bm.iloc[-1] / bm[pk] - 1) * 100:+.1f}%)", bignums([
        ("統一", f"{g('1216', 'since'):+.1f}%", f"大統益 {g('1232', 'since'):+.1f}%"),
        ("統一超", f"{g('2912', 'since'):+.1f}%", f"離年高 {g('2912', 'off'):+.0f}%"),
        ("統一證", f"{g('2855', 'since'):+.1f}%", f"統一實 {g('9907', 'since'):+.1f}%"),
    ]))

    L = [
        ("ok", f"<b>集團裡抗跌的是三檔</b>:大盤單日跌 {abs(mf.CRASH):.0f}% 以上的 {len(CD)} 天,平均 {lst(HAVEN, 'cavg')}"
               f"(大盤 {CD['大盤'].mean():+.1f}%);和電子的相關係數 {lst(HAVEN, 'corr', '{:+.2f}')}"),
        ("xx", f"<b>統一證不是退路</b>:大跌日平均 {g('2855', 'cavg'):+.1f}%,和大盤一樣;和電子相關 {g('2855', 'corr'):+.2f};"
               f"{pkmd} 以來 {g('2855', 'since'):+.1f}%、10 月營收年減 {abs(g('2855', 'yoy')):.0f}%"),
        ("wn", f"<b>統一實在衰退</b>:前三季 EPS {g('9907', 'e9'):.2f} 元(去年同期 {g('9907', 'e9ly'):.2f});●淨利年減 62.9%,"
               f"原因是美國對馬口鐵反傾銷調查;離年高 {g('9907', 'off'):+.0f}%。現金股利 1.18 元比近四季 EPS {g('9907', 'e4'):.2f} 元還多"),
        ("wn", f"<b>神隆、太子、德記量太小</b>:20 日均額 {lst(SMALL, 'amt', '{:.2f} 億')};"
               f"大跌日平均 {lst(SMALL, 'cavg')}。神隆前三季 EPS {g('1789', 'e9'):+.2f} 元、10 月營收年減 {abs(g('1789', 'yoy')):.0f}%"),
        ("wn", f"<b>統一超抗跌,但今年自己在跌</b>:離年高 {g('2912', 'off'):+.0f}%、在年線下 {abs(g('2912', 'yr')):.0f}%;"
               f"前三季 EPS {g('2912', 'e9'):.2f} 元(去年 {g('2912', 'e9ly'):.2f}),營收年增 {g('2912', 'yoy3'):.0f}%——賺得穩,沒有成長題材"),
        ("wn", "<b>三檔退路不是三個分散的部位</b>:?統一持有統一超 45.40%、大統益 38.5%,統一的獲利裡本來就含這兩家,"
               "也含統一證的權益法收益"),
        ("ok", f"外資近 20 日買超統一 {g('1216', 'fi'):+.0f} 億、統一超 {g('2912', 'fi'):+.0f} 億;"
               f"其餘 6 檔合計 {S.fi.drop(['1216', '2912']).sum():+.1f} 億"),
        ("xx", f"{lamp_s}——不分產業"),
    ]

    t = ('<table><tr><th>公司</th><th>今日</th><th>' + pkmd + ' 以來</th><th>大跌日平均</th><th>和電子相關</th><th>20 日均額</th></tr>')
    for c, x in S.iterrows():
        t += (f'<tr><td><b>{x["name"]}</b> {c}<br><small>{x.biz}</small></td><td class="n">{ud(round(x.d1, 1), f"{x.d1:+.1f}%")}</td>'
              f'<td class="n">{ud(round(x.since, 1), f"{x.since:+.1f}%")}<br><small>20 日 {x.d20:+.0f}%</small></td>'
              f'<td class="n">{x.cavg:+.1f}%<br><small>{x.cless}/{x.cn} 天比大盤少跌</small></td>'
              f'<td class="n">{x["corr"]:+.2f}</td><td class="n">{x.amt:.2f} 億</td></tr>')
    c_px = card(f"{md} 集團 8 檔:跌的時候各自怎麼走", t + "</table>"
                + f'<div class="note">大跌日=2015 年以來大盤單日跌 {abs(mf.CRASH):.0f}% 以上的 {len(CD)} 天(當時大盤平均 {CD["大盤"].mean():+.1f}%、電子 {CD["電子"].mean():+.1f}%);'
                  "相關係數是近 250 日與電子股中位數的日漲跌。</div>")

    f = '<table><tr><th>公司</th><th>前三季 EPS</th><th>10 月營收</th><th>現金殖利率</th><th>本益比</th><th>和統一的關係</th></tr>'
    for c, x in S.iterrows():
        eps = (f'{x.e9:.2f}<br><small>去年 {x.e9ly:.2f}</small>' if pd.notna(x.e9) else "<small>系統無季報</small>")
        pe = f"{x.px / x.e4:.1f} 倍" if pd.notna(x.e4) and x.e4 > 0.3 else "<small>—</small>"
        f += (f'<tr><td><b>{x["name"]}</b><br><small>{x.px:g} 元</small></td><td class="n">{eps}</td>'
              f'<td class="n">{ud(round(x.yoy), f"{x.yoy:+.0f}%")}<br><small>近 3 月 {x.yoy3:+.0f}%</small></td>'
              f'<td class="n">{x["div"] / x.px * 100:.1f}%<br><small>{x["div"]:g} 元</small></td><td class="n">{pe}</td>'
              f'<td><small>{x.rel}</small></td></tr>')
    c_fin = card("基本面:誰在賺、誰在退", f + "</table>"
                 + '<div class="note">●現金股利=2026 年已除息金額(證交所、櫃買除權息表);本益比用近四季 EPS,獲利太低的不列。</div>',
                 src="系統季報、月營收")

    c_read = card("讀這張表要注意", checks([
        ("wn", "集團成員我列了 8 檔:系統原本的集團名單只有統一、統一超、統一實、大統益;統一證、神隆、太子、德記是我加的"),
        ("wn", "統一中控在香港掛牌(0220.HK),系統沒有資料;●前三季淨利人民幣 21.32 億、年增 5.9%"),
        ("wn", "「抗跌」是相對電子:2020 年 1~3 月統一 -15.5%、大統益 -23.3%,系統性崩盤時一起跌"),
        ("ok", "單檔細節看統一 1216、大統益 1232 兩張海報;重產:python -X utf8 make_poster_uni.py"),
    ]), extra_cls="risk grow")

    html = shell(
        title_html="統一<b>集團</b>:8 檔裡誰是退路",
        subtitle=f"{pkmd} 高點以來 統一 {g('1216', 'since'):+.1f}%、大統益 {g('1232', 'since'):+.1f}%、統一超 {g('2912', 'since'):+.1f}%;統一證 {g('2855', 'since'):+.1f}%——同集團兩種走勢",
        brand="退路查核",
        cols=[c_num + card("結論(重點先看)", checks(L), src="●=開過原文或官方表 ?=只看到摘要或評論", extra_cls="grow"), c_px + c_read, c_fin],
        footer=f"素材:系統 {date[:4]}/{date[4:6]}/{date[6:]} 日線、季報、月營收、除權息表 · 本海報為研究筆記非投資建議")
    return str(save_poster("統一集團", date, html))


if __name__ == "__main__":
    print("saved:", main())

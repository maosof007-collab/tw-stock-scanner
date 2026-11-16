# -*- coding: utf-8 -*-
"""族群海報:避險掃描 — 全市場掃一遍,大盤修正時到底有沒有地方躲?(2026-11-16)
掃三層:25 個官方產業、所有 20 日均額 ≥0.2 億的個股、股票以外(反向 ETF/美債/黃金/美元)。
期間=2015 年以來大盤回落超過 12% 的各次(make_poster_fin.haven 定義)。
股票以外的價格用 yfinance 抓,存 data/_haven_assets.csv;抓不到就用上次存的。
手動重跑:python -X utf8 make_poster_scan.py"""
import glob
import json

import numpy as np
import pandas as pd

import make_poster_fin as mf
from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

MIN_AMT = 2e7
ASSETS = [("00632R.TW", "台灣 50 反向 ETF(00632R)"), ("TWD=X", "美元兌台幣"), ("00682U.TW", "美元指數 ETF(00682U)"),
          ("00679B.TWO", "美債 20 年 ETF(00679B)"), ("00635U.TW", "黃金 ETF(00635U)")]
SYS = ["2015-04", "2020-01", "2021-04", "2024-07b"]     # 我認定的系統性修正(各產業一起跌)
DIV = {"2412": 5.2, "3045": 4.744, "4904": 3.809, "2912": 9.0, "9908": 1.2, "1216": 3.0, "1232": 7.2, "2820": 0.9, "2886": 1.75}


def assets(index) -> pd.DataFrame:
    p = mf.D / "_haven_assets.csv"
    try:
        import yfinance as yf
        out = {}
        for t, n in ASSETS:
            s = yf.download(t, start="2015-01-01", progress=False, auto_adjust=True)["Close"].squeeze().dropna()
            s.index = s.index.strftime("%Y-%m-%d")
            out[n] = s
        A = pd.DataFrame(out)
        A.to_csv(p, encoding="utf-8-sig")
    except Exception:
        A = pd.read_csv(p, index_col=0)
    return A.reindex(index).ffill(limit=3)


def main() -> str:
    h = mf.haven()
    X, bm, sl = h["X"], h["bm"], h["sl"]
    eps = h["eps"]
    keys = [a[:7] for a, _ in eps]
    keys = [k + "b" if keys[:i].count(k) else k for i, k in enumerate(keys)]      # 2024-07 有兩段
    CD = X[X["大盤"] <= mf.CRASH]
    last, pk = bm.index[-1], bm.iloc[-120:].idxmax()
    md, pkmd = f"{int(last[5:7])}/{int(last[8:10])}", f"{int(pk[5:7])}/{int(pk[8:10])}"
    date = now_tw().strftime("%Y%m%d")

    P, amt = {}, {}
    for c in sl.index:
        f = glob.glob(str(mf.D / f"{c}.TW*.csv"))
        if not f:
            continue
        d = pd.read_csv(f[0], usecols=["Date", "Close", "Volume"]).dropna().set_index("Date")
        if len(d) < 300 or d.index[-1] != last:
            continue
        a = (d.Close * d.Volume).iloc[-20:].mean()
        if a >= MIN_AMT:
            P[c], amt[c] = d.Close, a / 1e8
    P = pd.DataFrame(P).reindex(bm.index)
    R = P.pct_change(fill_method=None) * 100
    sec = sl.sector.reindex(P.columns)

    # ① 產業
    rows = []
    for s, cs in sec.groupby(sec).groups.items():
        if len(cs) < 5:
            continue
        r = R[list(cs)].median(axis=1)
        ix = (1 + r.fillna(0) / 100).cumprod()
        rec = dict(sec=s, n=len(cs), d1=r.iloc[-1], since=(ix.iloc[-1] / ix[pk] - 1) * 100, cavg=r[CD.index].mean(),
                   **{k: (ix[b] / ix[a] - 1) * 100 for k, (a, b) in zip(keys, eps)})
        rec["worst"], rec["ups"] = min(rec[k] for k in keys), sum(rec[k] > 0 for k in keys)
        rows.append(rec)
    S = pd.DataFrame(rows).set_index("sec").sort_values("cavg", ascending=False)

    # ② 個股
    E = pd.DataFrame({k: (P.loc[b] / P.loc[a] - 1) * 100 for k, (a, b) in zip(keys, eps)})
    up = (E > 0).sum() / E.notna().sum() * 100
    full = E.dropna()
    full = full.assign(worst=full.min(axis=1), ups=(full > 0).sum(axis=1), since=(P.iloc[-1] / P.loc[pk] - 1) * 100).sort_values("worst", ascending=False)
    n10, n15 = int((full.worst > -10).sum()), int((full.worst > -15).sum())
    top = full.head(14)
    red_today = int((R.iloc[-1] > 0).sum())

    # ③ 股票以外
    A = assets(bm.index)
    RA = A.pct_change(fill_method=None) * 100
    ar = []
    for nme in A.columns:
        rc = RA[nme][CD.index].dropna()
        rec = dict(name=nme, cavg=rc.mean(), cup=int((rc > 0).sum()), cn=len(rc), since=(A[nme].iloc[-1] / A[nme][pk] - 1) * 100)
        for k, (a, b) in zip(keys, eps):
            v = (A[nme][b] / A[nme][a] - 1) * 100 if pd.notna(A[nme][a]) and pd.notna(A[nme][b]) else np.nan
            rec[k] = v if abs(v) < 200 else np.nan            # 超過 ±200% 視為分割還原失真
        ar.append(rec)
    AT = pd.DataFrame(ar).set_index("name")
    usd, inv, bond, gold = AT.iloc[1], AT.iloc[0], AT.iloc[3], AT.iloc[4]
    usd_ep = usd[keys].dropna()

    try:
        lamp = json.load(open(mf.D / "_market_risk.json", encoding="utf-8"))
        lamp_s = f"大盤燈號 {lamp['lamp']}({lamp['rule']})"
    except Exception:
        lamp_s = "大盤燈號讀不到"
    nm = lambda cs: "、".join(sl.name[c] for c in cs)
    sysk = [k for k in SYS if k in keys]

    c_num = card(f"大盤每次修正,期間還在漲的股票占幾成({P.shape[1]} 檔)", bignums([
        ("2020 疫情", f"{up['2020-01']:.1f}%", f"2015 年 {up['2015-04']:.1f}%"),
        ("2024/7→2025/4", f"{up['2024-07b']:.1f}%", f"2022 升息 {up['2022-01']:.1f}%"),
        (f"這一波({pkmd} 起)", f"{up[keys[-1]]:.1f}%", f"{md} 當天收紅 {red_today} 檔"),
    ]))

    L = [
        ("xx", f"<b>系統性崩盤時,股票裡幾乎沒有地方躲</b>:{len(keys)} 次修正中,期間上漲的股票 {up.min():.1f}%~{up.max():.1f}%;"
               f"各產業一起跌的那幾次({('、'.join(k[:4] for k in sysk))})只有 {up[sysk].min():.0f}~{up[sysk].max():.0f}%"),
        ("xx", f"<b>沒有一個產業靠得住</b>:{len(S)} 個產業裡,{len(keys)} 次修正上漲次數最多的也只有 {int(S.ups.max())} 次;"
               f"最抗跌的{S.index[0]}、{S.index[1]},2020 年中位數也是 {S['2020-01'].iloc[0]:+.0f}%、{S['2020-01'].iloc[1]:+.0f}%"),
        ("ok", f"<b>逐檔找,每次都撐住的只有電信</b>:{len(full)} 檔 {len(keys)} 次都有資料,最差一次沒跌超過 10% 的只有 {n10} 檔——"
               f"{nm(full.index[:n10])}(最差 {full.worst.iloc[0]:+.0f}%、{full.worst.iloc[1]:+.0f}%);放寬到 15% 是 {n15} 檔,"
               f"多了{nm(full.index[n10:n15])}"),
        ("ok", f"<b>這一波比較好躲</b>:因為是電子自己的問題,{up[keys[-1]]:.0f}% 的股票期間是漲的;"
               f"產業中位數 {pkmd} 以來為正的有 {'、'.join(S.index[S.since > 0])}"),
        ("ok", f"<b>股票以外,最穩定的是美元</b>:{len(usd_ep)} 次修正期間美元兌台幣沒有一次明顯貶值({usd_ep.min():+.1f}%~{usd_ep.max():+.1f}%),"
               f"其中 {int((usd_ep > 1).sum())} 次升值超過 1%;大跌日 {int(usd.cn)} 天有 {int(usd.cup)} 天升"),
        ("ok", f"<b>反向 ETF 在大跌日有用</b>:{int(inv.cn)} 個大跌日 {int(inv.cup)} 天上漲、平均 {inv.cavg:+.1f}%;{pkmd} 以來 {inv.since:+.1f}%。"
               "它每天重設,盤整期會耗損,這是商品設計"),
        ("wn", f"<b>美債和黃金不可靠</b>:美債 20 年 ETF 2020 年 {bond['2020-01']:+.0f}%、這一波 {bond.since:+.0f}%,但 2022 年升息那次 {bond['2022-01']:+.0f}%;"
               f"黃金 ETF 大跌日平均 {gold.cavg:+.1f}%,{int(gold.cn)} 天只有 {int(gold.cup)} 天漲"),
        ("xx", f"{lamp_s};系統規則本身就是答案之一:只出不進,現金不會跌"),
    ]
    c_concl = card("結論(重點先看)", checks(L), src="全部為系統即時計算;股票以外的價格來自 Yahoo", extra_cls="grow")

    t = ("<table><tr><th>產業</th><th>今日</th><th>" + pkmd + " 以來</th><th>大跌日平均</th><th>2020</th><th>2022</th>"
         "<th>2024→25</th><th>最差一次</th></tr>")
    for s, x in S.iterrows():
        t += (f'<tr><td><b>{s}</b> <small>{int(x.n)} 檔</small></td><td class="n">{ud(round(x.d1, 1), f"{x.d1:+.1f}%")}</td>'
              f'<td class="n">{ud(round(x.since, 1), f"{x.since:+.0f}%")}</td><td class="n">{x.cavg:+.1f}%</td>'
              f'<td class="n">{x["2020-01"]:+.0f}%</td><td class="n">{x["2022-01"]:+.0f}%</td><td class="n">{x["2024-07b"]:+.0f}%</td>'
              f'<td class="n">{x.worst:+.0f}%</td></tr>')
    c_sec = card(f"① {len(S)} 個產業:依大跌日平均排序(成分股中位數)", t + "</table>"
                 + f'<div class="note">大跌日=大盤單日跌 {abs(mf.CRASH):.0f}% 以上的 {len(CD)} 天(大盤平均 {CD["大盤"].mean():+.1f}%)。'
                   "不到 5 檔的產業(電信、油電燃氣、貿易百貨等)不列在這裡,看右邊的個股表。</div>")

    p = ("<table><tr><th>公司</th><th>最差一次</th><th>2020</th><th>2022</th><th>2024→25</th><th>" + pkmd + " 以來</th><th>殖利率</th></tr>")
    for c, x in top.iterrows():
        px = P[c].iloc[-1]
        dv = f"{DIV[c] / px * 100:.1f}%" if c in DIV else "<small>—</small>"
        p += (f'<tr><td><b>{sl.name[c]}</b> <small>{c} {sl.sector[c]}</small><br><small>{int(x.ups)}/{len(keys)} 次上漲、均額 {amt[c]:.1f} 億</small></td>'
              f'<td class="n"><b>{x.worst:+.0f}%</b></td><td class="n">{x["2020-01"]:+.0f}%</td><td class="n">{x["2022-01"]:+.0f}%</td>'
              f'<td class="n">{x["2024-07b"]:+.0f}%</td><td class="n">{ud(round(x.since, 1), f"{x.since:+.0f}%")}</td><td class="n">{dv}</td></tr>')
    c_stk = card(f"② 個股:{len(keys)} 次修正裡「最差一次」跌最少的 14 檔", p + "</table>"
                 + f'<div class="note">母體是 {len(full)} 檔({len(keys)} 次都有資料、20 日均額 ≥0.2 億)。●殖利率=2026 年已除息現金股利÷今日收盤。'
                   "這是事後排名:過去沒跌不保證下次不跌。</div>")

    a = ("<table><tr><th>資產</th><th>大跌日平均</th><th>2020</th><th>2022</th><th>" + pkmd + " 以來</th></tr>")
    f2 = lambda v: f"{v:+.0f}%" if pd.notna(v) else "<small>—</small>"
    for nme, x in AT.iterrows():
        a += (f'<tr><td><b>{nme}</b></td><td class="n">{ud(round(x.cavg, 1), f"{x.cavg:+.1f}%")}<br><small>{int(x.cup)}/{int(x.cn)} 天上漲</small></td>'
              f'<td class="n">{f2(x["2020-01"])}</td><td class="n">{f2(x["2022-01"])}</td><td class="n">{ud(round(x.since, 1), f"{x.since:+.1f}%")}</td></tr>')
    c_ast = card("③ 股票以外", a + "</table>"
                 + '<div class="note">ETF 是還原價;美元兌台幣上漲=台幣貶值。資料到各自最後交易日,可能比股票晚一天更新。</div>', src="Yahoo")

    c_read = card("讀這張表要注意", checks([
        ("wn", "「系統性」是我事後依「各產業是不是一起跌」分的,事前分不出來;這一波目前是電子自己的問題"),
        ("wn", "電信、統一超這些每次都撐住的,共同點是營收不看景氣;代價是平常也不太漲"),
        ("wn", "個股表是事後排名,有倖存者偏差:中途下市的不在裡面"),
        ("ok", "單一族群細節看金融、統一集團、統一、大統益四張海報;重產:python -X utf8 make_poster_scan.py"),
    ]), extra_cls="risk grow")

    html = shell(
        title_html="避險<b>掃描</b>:到底有沒有地方躲",
        subtitle=f"系統性崩盤時股票裡只有 {up[sysk].min():.0f}~{up[sysk].max():.0f}% 在漲;每次都撐住的是電信,股票以外是美元與反向 ETF",
        brand="退路查核",
        cols=[c_num + c_concl, c_sec + c_read, c_stk + c_ast],
        footer=f"素材:系統 {date[:4]}/{date[4:6]}/{date[6:]} 日線({P.shape[1]} 檔)、Yahoo(ETF、匯率)、證交所除權息表 · 本海報為研究筆記非投資建議")
    return str(save_poster("避險掃描", date, html))


if __name__ == "__main__":
    print("saved:", main())

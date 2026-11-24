# -*- coding: utf-8 -*-
"""個股海報:中華電 2412 — 和大盤的關聯(2026-11-20 使用者:「看中華電信和大盤相關聯」)
四個角度:①平常的連動(相關係數、beta)②大盤大跌日與歷次修正 ③修正結束後的反彈落後多少
④中華電大幅跑贏大盤(30 個交易日相對漲幅)之後,大盤怎麼走。全部用系統日線即時算(2015 年起,還原價=含息)。
股利 5.2 元沿用避險掃描海報(make_poster_scan.DIV)的數字。
手動重跑:python -X utf8 make_poster_2412.py"""
from pathlib import Path

import numpy as np
import pandas as pd

from poster import bignums, card, checks, save_poster, shell
from twtime import now_tw

D = Path(__file__).parent / "data"
CODE, DIV = "2412", 5.2
EP_DD, REL_N, REL_TH = -0.12, 30, 15.0     # 修正門檻;相對強度看 30 個交易日、跑贏 15 個百分點算一次


def pc(x, nd=1) -> str:
    return "—" if pd.isna(x) else f'<span class="{"rd" if x > 0 else "gn"}">{x:+.{nd}f}%</span>'


def md(d) -> str:
    return f"{d.year}/{d.month}/{d.day}"


def main() -> str:
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    raw = pd.read_csv(D / f"{CODE}.TW.csv", index_col=0, parse_dates=True).dropna(subset=["Close"])
    s = raw.Close.reindex(bm.index).ffill().dropna()
    bm = bm.reindex(s.index)
    r, rb = s.pct_change() * 100, bm.pct_change() * 100
    df = pd.DataFrame({"s": r, "b": rb}).dropna()
    last, date = s.index[-1], now_tw().strftime("%Y%m%d")
    pk = bm.iloc[-120:].idxmax()

    def cb(d):
        return d.s.corr(d.b), np.cov(d.b, d.s)[0, 1] / d.b.var()
    c_all, b_all = cb(df)
    c250, b250 = cb(df.tail(250))
    roll = df.s.rolling(60).corr(df.b).dropna()
    dn2, dn4, up2 = df[df.b <= -2], df[df.b <= -4], df[df.b >= 2]

    # 歷次修正(大盤從高點回落超過 12%,回到距高點 3% 內才算結束)
    dd, eps, on, p0 = bm / bm.cummax() - 1, [], False, None
    for d, v in dd.items():
        if not on and v <= EP_DD:
            on, p0 = True, bm[:d].idxmax()
        if on and v > -0.03:
            eps.append((p0, bm[p0:d].idxmin(), True))
            on = False
    if on:
        eps.append((p0, bm[p0:].idxmin(), False))
    t_e = ("<table><tr><th>大盤高點→低點</th><th>大盤</th><th>中華電</th><th>低點後 60 日:大盤</th><th>中華電</th></tr>")
    n_up, lag = 0, []
    for a, b, done in eps:
        ib, isx = (bm[b] / bm[a] - 1) * 100, (s[b] / s[a] - 1) * 100
        n_up += isx > 0
        f = bm[b:]
        if done and len(f) > 60:
            rb60, rs60 = (f.iloc[60] / f.iloc[0] - 1) * 100, (s[b:].iloc[60] / s[b] - 1) * 100
            lag.append(rs60 - rb60)
        else:
            rb60 = rs60 = np.nan
        t_e += (f'<tr{"" if done else " class=yl"}><td class="n">{a.year}/{a.month}→{b.year}/{b.month}{"" if done else "(進行中)"}</td>'
                f'<td class="n">{ib:.0f}%</td><td class="n">{pc(isx)}</td><td class="n">{pc(rb60, 0)}</td><td class="n">{pc(rs60, 0)}</td></tr>')
    t_e += "</table>"

    # 相對強度:中華電 30 個交易日報酬 − 大盤 30 個交易日報酬
    rel = (s.pct_change(REL_N) - bm.pct_change(REL_N)) * 100
    cur = rel.iloc[-1]
    pctile = (rel.dropna() <= cur).mean() * 100
    ev, lastev = [], None
    for d, v in rel.dropna().items():
        if v >= REL_TH and (lastev is None or (d - lastev).days > 120):
            ev.append(d); lastev = d
    t_r = "<table><tr><th>第一次跑贏 15 個百分點</th><th>當時跑贏</th><th>大盤之後 20 日</th><th>60 日</th><th>120 日</th><th>之後還跌多少</th></tr>"
    f60, more = [], []
    for d in ev:
        f = bm[d:]
        g = lambda k: (f.iloc[k] / f.iloc[0] - 1) * 100 if len(f) > k else np.nan
        low = (f.iloc[:121].min() / f.iloc[0] - 1) * 100
        cur_ev = len(f) <= 20
        more.append(low)
        if not np.isnan(g(60)):
            f60.append(g(60))
        t_r += (f'<tr{" class=yl" if cur_ev else ""}><td class="n">{md(d)}</td><td class="n">+{rel[d]:.0f}</td><td class="n">{pc(g(20), 0)}</td>'
                f'<td class="n">{pc(g(60), 0)}</td><td class="n">{pc(g(120), 0)}</td><td class="n">{low:.0f}%{"(到目前)" if cur_ev else ""}</td></tr>')
    t_r += "</table>"

    # 現況
    px = float(raw.Close.iloc[-1])
    since = (s.iloc[-1] / s[pk] - 1) * 100
    bsince = (bm.iloc[-1] / bm[pk] - 1) * 100
    v9, v20 = raw.Volume["2026-09"].mean() / 1000, raw.Volume.tail(20).mean() / 1000
    i = pd.read_csv(D / "institutional" / f"{CODE}_inst.csv", parse_dates=["date"]).set_index("date").sort_index()
    w = slice(pk + pd.Timedelta(days=1), last)
    fi, it = (i["外陸資買賣超股數(不含外資自營商)"] / 1000)[w].sum(), (i["it_net"] / 1000)[w].sum()
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    qq = q[q.code == CODE].sort_values("季度")
    e4 = qq.EPS.tail(4).sum()
    rev = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    ry = rev[rev.code == CODE]["yoy%"].tail(3)
    hi = raw.Close.tail(250).max()
    mdd = (s / s.cummax() - 1)

    c_concl = card("結論(重點先看)", checks([
        ("ok", f"<b>平常幾乎各走各的</b>:2015 年以來日漲跌的相關係數 {c_all:+.2f}、近 250 日 {c250:+.2f};"
               f"大盤動 1%,中華電平均只動 {b_all:.2f}%。近 60 日相關係數變成 {roll.iloc[-1]:+.2f}:大盤跌、它漲"),
        ("ok", f"<b>大盤大跌日它跌得少</b>:大盤單日跌 2% 以上的 {len(dn2)} 天,中華電平均 {dn2.s.mean():+.2f}%(大盤 {dn2.b.mean():+.2f}%),"
               f"{(dn2.s > 0).mean() * 100:.0f}% 的日子收紅;跌 4% 以上的 {len(dn4)} 天平均 {dn4.s.mean():+.2f}%"),
        ("wn", f"<b>不是每次修正都漲</b>:大盤回落超過 12% 的 {len(eps)} 次,中華電期間上漲的有 {n_up} 次;"
               f"2015 年以來自己最大回落 {mdd.min() * 100:.0f}%({md(mdd.idxmin())})"),
        ("xx", f"<b>代價在反彈</b>:修正結束後 60 個交易日,中華電平均比大盤少漲 {-np.mean(lag):.0f} 個百分點;"
               f"大盤單日漲 2% 以上的 {len(up2)} 天,它平均只漲 {up2.s.mean():+.2f}%"),
        ("xx", f"<b>這一次是 2015 年以來最極端</b>:{pk.month}/{pk.day} 高點以來中華電 {since:+.1f}%、大盤 {bsince:+.1f}%;"
               f"近 30 個交易日跑贏大盤 {cur:.0f} 個百分點,"
               + ("是 2015 年以來最高" if pctile >= 99.9 else f"超過歷史上 {pctile:.1f}% 的日子")),
        ("wn", f"<b>它大幅跑贏,不代表大盤見底</b>:{len(ev)} 次跑贏 15 個百分點之後,有 {sum(1 for v in more if v <= -5)} 次大盤還再跌 "
               f"{-max(v for v in more if v <= -5):.0f}~{-min(more):.0f}%(這一次是 {md(ev[-1])} 出現,之後大盤又跌了 {-more[-1]:.0f}%);"
               f"過去 {len(f60)} 次 60 日後 {sum(1 for v in f60 if v > 0)} 次上漲、{sum(1 for v in f60 if v <= 0)} 次下跌——樣本太少,當不了訊號"),
    ]), src=f"●系統日線,至 {last.month}/{last.day}", extra_cls="grow")

    c_now = card("📍 現在", bignums([
        ("股價", f"{px:g}", f"一年收盤高 {hi:g}"),
        (f"{pk.month}/{pk.day} 以來", f"{since:+.1f}%", f"大盤 {bsince:+.1f}%"),
        ("殖利率", f"{DIV / px * 100:.1f}%", f"現金股利 {DIV} 元"),
        ("本益比", f"{px / e4:.1f} 倍", f"近四季 EPS {e4:.2f}")]) + checks([
        ("wn", f"成交量放大:9 月日均 {v9:,.0f} 張 → 近 20 日 {v20:,.0f} 張"),
        ("wn" if fi < 0 else "ok", f"{pk.month}/{pk.day} 高點之後外資 {fi:+,.0f} 張、投信 {it:+,.0f} 張(同期間外資賣超台積電約 31 萬張)"),
        ("ok", f"近三個月營收年增 {'、'.join(f'{v:+.1f}%' for v in ry)};最新一季 EPS {qq.EPS.iloc[-1]:.2f}"),
        ("wn", f"股價越漲殖利率越低:現在 {DIV / px * 100:.1f}%;漲到 {px * 1.1:.0f} 元會剩 {DIV / (px * 1.1) * 100:.1f}%"),
    ]), f"●至 {last.month}/{last.day} 收盤")

    c_corr = card("① 平常的連動", bignums([
        ("相關係數", f"{c_all:+.2f}", "2015 年起"),
        ("近 250 日", f"{c250:+.2f}", f"近 60 日 {roll.iloc[-1]:+.2f}"),
        ("大盤動 1%", f"{b_all:.2f}%", "它平均動多少"),
        ("60 日相關", f"{roll.min():+.2f}~{roll.max():+.2f}", "歷史範圍")])
        + '<div class="note">相關係數 +1=完全同向、0=無關、−1=完全反向。中華電不是跟大盤反向,是關聯很低:'
          "大盤跌它不太跌,大盤漲它也不太漲。60 日滾動相關係數的中位數是 "
          f"{roll.median():+.2f}。</div>")
    c_eps = card(f"②③ 歷次修正 {len(eps)} 次:跌的時候、反彈的時候", t_e
                 + '<div class="note">●修正=大盤從高點回落超過 12%,回到距高點 3% 以內算結束。還原價(含息)。'
                   "右邊兩欄是低點之後 60 個交易日的漲幅。</div>", "2015 年起")
    c_rel = card("④ 中華電大幅跑贏之後,大盤怎麼走", t_r
                 + f'<div class="note">●跑贏=中華電 {REL_N} 個交易日報酬減大盤同期報酬,第一次超過 {REL_TH:.0f} 個百分點算一次(之後 120 天內不重複算)。'
                   "「之後還跌多少」是訊號出現後 120 個交易日內大盤的最低點。</div>")
    c_risk = card("⚠️ 讀這張要注意", checks([
        ("wn", "資料只有 2015 年起(系統日線),沒有包含 2008 年;當年中華電跌了多少我沒查"),
        ("wn", "它抗跌的前提是獲利和股利穩定;電信資費、頻譜標金、政策變動這些我這次沒查"),
        ("wn", "現在的漲幅有多少是資金躲進來,資金退出時會不會回吐,歷史樣本回答不了"),
        ("wn", "股利 5.2 元沿用避險掃描海報的數字,沒有重新核對"),
        ("xx", "大盤燈號 🔴 時系統規則是禁開新倉,不分產業;這張回答「兩者的關聯」,不是進場訊號"),
    ]), extra_cls="risk")

    html = shell(
        title_html="中華電<b>(2412)</b>和大盤的關聯",
        subtitle=(f"平常相關係數只有 {c_all:+.2f}:大盤跌它不太跌、大盤漲它也不太漲。這一波跑贏大盤 {since - bsince:.0f} 個百分點,"
                  f"是 2015 年以來最極端的一次;修正結束後它平均少漲 {-np.mean(lag):.0f} 個百分點"),
        brand="關聯查核",
        cols=[c_concl + c_now, c_corr + c_eps, c_rel + c_risk],
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:系統日線(還原價)、三大法人、季報、月營收 · 研究筆記,非投資建議")
    return str(save_poster(CODE, date, html))


if __name__ == "__main__":
    print(main())

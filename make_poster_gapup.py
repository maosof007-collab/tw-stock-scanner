# -*- coding: utf-8 -*-
"""事件研究海報:大盤跳空大漲日(期貨夜盤漲停的隔天)——誰買得到、買了之後怎樣、套到下一個交易日(2026-11-23)。
起因:2026-11-23 晚上輝達宣布黃仁勳回任,台指期夜盤漲停;使用者:「夜盤漲停 去分析過去例子 明天還有機會買的股票」。
做法(全部每次重算,只讀本機日線,不發請求):
  1. 事件 = 2015-06(漲跌幅 10%)以來加權指數單日漲 ≥ MIN_UP 的日子。
  2. 每個事件日把個股分七類(一字鎖死/開盤漲停盤中開過/開盤漲停收不住/開盤沒漲停但收漲停/開高 5% 以上沒收漲停/開高不到 5%/開低),
     算「當天開盤買」「當天收盤買」「隔天開盤買」之後 5/20 日報酬中位數與上漲比例。
  3. 規模最像的一次(MAIN,2025-04-10,期貨同樣漲停)再拆:成交值五分位 × 跌幅五分位的開盤漲停率、各產業、沒鎖的開多少。
  4. 套到最新一天:每檔照自己落在哪一格,帶出那一格在 MAIN 當天的開盤漲停率;名單 = 流動性夠、業績還在成長(委屈股海報第二關)。
漲停判定用還原價的當日漲幅(≥9.4%;漲停價要取到檔位,實際漲幅 9.4%~10%)且收在當日最高。
手動重跑:python -X utf8 make_poster_gapup.py        驗證點:印出的事件表、MAIN 分類表 = 海報上的表"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from poster import bignums, card, checks, row, save_poster, shell_flow
from twtime import now_tw

D = Path(__file__).parent / "data"
MIN_UP = 0.04          # 大盤單日漲幅門檻
MAIN = "2025-04-10"    # 規模最像的一次(期貨夜盤同樣漲停)
LIM = 0.094
PEAK = "2026-10-06"    # 這一波下跌的大盤高點
LIQ = 0.5              # 名單的流動性門檻:20 日均成交值(億)
BAND = 0.7             # 同一格在 MAIN 的開盤漲停率低於這個才列進表格,其餘只列名字
# 2026-11-23 晚上的新聞快照(?=媒體報導,沒有對期交所原始資料)
FACTS = dict(fut=40324, fut_chg=3665, when="11/23 夜盤", why="輝達董事會宣布黃仁勳回任執行長,輝達美股開盤漲約三成")
CLS = {"1": "整天鎖死在漲停(一字)", "2": "開盤漲停、盤中打開過、收漲停", "3": "開盤漲停、收不住", "4": "開盤沒漲停、後來拉上漲停",
       "5": "開高 5% 以上、沒收漲停", "6": "開高不到 5%", "7": "開低"}
BUY = {"1": "買不到", "2": "打開時才買得到", "3": "買得到", "4": "買得到", "5": "買得到", "6": "買得到", "7": "買得到"}


def panel() -> dict:
    cols = {k: {} for k in ("Open", "High", "Low", "Close", "Volume")}
    for f in glob.glob(str(D / "*.TW*.csv")):
        code = os.path.basename(f).split(".")[0]
        try:
            d = pd.read_csv(f, index_col=0, parse_dates=True, usecols=["Date", "Open", "High", "Low", "Close", "Volume"])
        except Exception:
            continue
        d = d[(d.Close > 0) & (d.Open > 0)]
        if len(d) < 80:
            continue
        d = d[~d.index.duplicated(keep="last")]
        for k in cols:
            cols[k][code] = d[k]
    return {k: pd.DataFrame(v).sort_index() for k, v in cols.items()}


def feat(P: dict, i: int) -> pd.DataFrame:
    """第 i 天收盤後看得到的:離 60 日高點多遠、20 日均成交值(億)。"""
    C, H, V = P["Close"], P["High"], P["Volume"]
    return pd.DataFrame({"dd60": C.iloc[i] / H.iloc[max(0, i - 59):i + 1].max() - 1,
                         "amt20": (C.iloc[max(0, i - 19):i + 1] * V.iloc[max(0, i - 19):i + 1]).mean() / 1e8})


def q5(s: pd.Series) -> pd.Series:
    return (pd.qcut(s.rank(method="first"), 5, labels=False) + 1).astype(int)


def study(P: dict, sl: pd.DataFrame, day) -> pd.DataFrame:
    O, H, L, C, V = (P[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    i = C.index.get_loc(pd.Timestamp(day))
    t = pd.DataFrame({"pc": C.iloc[i - 1], "o": O.iloc[i], "h": H.iloc[i], "l": L.iloc[i], "c": C.iloc[i], "v": V.iloc[i]}).dropna()
    t = t[t.v > 0]
    t["gap"], t["ret"] = t.o / t.pc - 1, t.c / t.pc - 1
    t["open_lim"] = t.gap >= LIM
    t["close_lim"] = (t.ret >= LIM) & (t.c >= t.h * 0.9999)
    t["locked"] = t.open_lim & (t.l >= t.o * 0.9999) & t.close_lim
    t["cls"] = np.select([t.locked, t.open_lim & t.close_lim, t.open_lim, t.close_lim, t.gap >= 0.05, t.gap >= 0],
                         list("123456"), "7")
    t = t.join(feat(P, i - 1))
    t["sector"], t["name"] = sl.sector.reindex(t.index), sl.name.reindex(t.index)
    n = len(C)
    for k in (5, 10, 20):
        t[f"c{k}"] = C.iloc[i + k].reindex(t.index) if i + k < n else np.nan
    t["o1"] = O.iloc[i + 1].reindex(t.index) if i + 1 < n else np.nan
    t["fo0"] = t.c / t.o - 1
    for k in (5, 10, 20):
        t[f"fo{k}"], t[f"fc{k}"], t[f"fn{k}"] = t[f"c{k}"] / t.o - 1, t[f"c{k}"] / t.c - 1, t[f"c{k}"] / t.o1 - 1
    t["gap1"] = t.o1 / t.c - 1
    return t


def med(x) -> float:
    x = pd.Series(x).dropna()
    return float(x.median()) if len(x) else np.nan


def win(x) -> float:
    x = pd.Series(x).dropna()
    return float((x > 0).mean()) if len(x) else np.nan


def pc(x, d=1) -> str:
    if x is None or pd.isna(x):
        return "—"
    c = "rd" if x > 0 else "gn" if x < 0 else ""
    return f'<span class="{c}">{x * 100:+.{d}f}%</span>'


def sh(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 100:.0f}%"


def chart(paths: dict, main_lab: str, hot: set) -> str:
    """歷次走勢:加權指數,事件前一天收盤 = 100,x = 事件日前 5 天到後 20 天。直接標在線尾。
    橘 = 規模最像的一次(main_lab),藍 = 這一波下跌裡的(hot),其餘灰色。"""
    W, Hh, l, r, tp, b = 640, 250, 34, 118, 10, 24
    vals = [v for s in paths.values() for v in s.dropna()]
    lo, hi = np.floor(min(vals) / 5) * 5, np.ceil(max(vals) / 5) * 5
    X = lambda k: l + (k + 5) / 25 * (W - l - r)                      # noqa: E731
    Y = lambda v: tp + (hi - v) / (hi - lo) * (Hh - tp - b)           # noqa: E731
    g = "".join(f'<line x1="{l}" x2="{W - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#e3e8ee"/>'
                f'<text x="{l - 4}" y="{Y(v) + 4:.1f}" font-size="11" fill="#5b6673" text-anchor="end">{v:.0f}</text>'
                for v in np.arange(lo, hi + 1, 5))
    g += f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{tp}" y2="{Hh - b}" stroke="#8a94a0" stroke-dasharray="3 3"/>'
    g += "".join(f'<text x="{X(k):.1f}" y="{Hh - 8}" font-size="11" fill="#5b6673" text-anchor="middle">{t}</text>'
                 for k, t in ((-5, "前 5 天"), (0, "大漲當天"), (5, "+5"), (10, "+10"), (20, "+20 天")))
    ends, body = [], ""
    for lab, s in paths.items():
        s = s.dropna()
        col, wd = ("#e07b00", 2.8) if lab == main_lab else ("#2f6db5", 2.4) if lab in hot else ("#9aa5b1", 1.3)
        pts = " ".join(f"{X(k):.1f},{Y(v):.1f}" for k, v in s.items())
        body += f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linejoin="round"><title>{lab}</title></polyline>'
        ends.append([Y(s.iloc[-1]), X(s.index[-1]), lab, s.iloc[-1], col])
    ends.sort()
    for j in range(1, len(ends)):                                       # 標籤不重疊
        ends[j][0] = max(ends[j][0], ends[j - 1][0] + 13)
    for y, x, lab, v, col in ends:
        body += f'<text x="{x + 5:.1f}" y="{y + 4:.1f}" font-size="11.5" fill="{col}" font-weight="700">{lab} {v:.0f}</text>'
    return f'<svg viewBox="0 0 {W} {Hh}" style="width:100%;height:auto">{g}{body}</svg>'


def main() -> str:
    P = panel()
    C = P["Close"]
    sl = pd.read_csv(D / "stock_list.csv", dtype=str, encoding="utf-8-sig").set_index("code")
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True)["Close"].dropna()
    last = C.index[-1]
    r = bm.pct_change()
    evs = [d for d in r[(r >= MIN_UP) & (r.index >= "2015-06-01")].index if d in C.index and d < last]

    # ── 歷次 ──
    rows, paths, T = [], {}, {}
    for d in evs:
        t = study(P, sl, d)
        T[d] = t
        j = bm.index.get_loc(d)
        after = lambda k: bm.iloc[j + k] / bm.iloc[j] - 1 if j + k < len(bm) else np.nan      # noqa: E731
        rows.append(dict(d=d, n=len(t), idx=r[d], gap=med(t.gap), ol=t.open_lim.mean(), lk=t.locked.mean(), cl=t.close_lim.mean(),
                         g1=med(t.gap1), g1dn=(t.gap1.dropna() < 0).mean(), fc5=med(t.fc5), fc20=med(t.fc20), w20=win(t.fc20),
                         i5=after(5), i20=after(20), fc10=med(t.fc10), i10=after(10)))
        seg = bm.iloc[max(0, j - 5):j + 21] / bm.iloc[j - 1] * 100
        seg.index = range(-min(5, j), len(seg) - min(5, j))
        paths[f"{d.year}/{d.month}/{d.day}"] = seg
    E = pd.DataFrame(rows).set_index("d")
    nfull = C.shape[1]
    th = ("<table><tr><th>大漲日</th><th>大盤當天</th><th>個股開盤<br>跳空中位</th><th>開盤就<br>漲停</th><th>整天<br>鎖死</th><th>收漲停</th>"
          "<th>隔天開盤<br>(中位)</th><th>收盤買<br>5 日後</th><th>收盤買<br>20 日後</th><th>大盤<br>20 日後</th></tr>")
    for d, e in E.iterrows():
        hole = f"<br><small>只有 {e.n:.0f} 檔有資料</small>" if e.n < nfull * 0.7 else ""
        th += (f'<tr{" class=yl" if str(d.date()) == MAIN else ""}><td class="n"><b>{d:%Y/%m/%d}</b>{hole}</td><td class="n">{pc(e.idx)}</td>'
               f'<td class="n">{pc(e.gap)}</td><td class="n">{sh(e.ol)}</td><td class="n">{sh(e.lk)}</td><td class="n">{sh(e.cl)}</td>'
               f'<td class="n">{pc(e.g1)}</td><td class="n">{pc(e.fc5)}</td><td class="n">{pc(e.fc20)}</td><td class="n">{pc(e.i20)}</td></tr>')
    done = E[E.fc20.notna()]
    th += (f'<tr><td><b>中位數</b>({len(done)} 次有 20 日結果)</td><td class="n">{pc(E.idx.median())}</td><td class="n">{pc(E.gap.median())}</td>'
           f'<td class="n">{sh(E.ol.median())}</td><td class="n">{sh(E.lk.median())}</td><td class="n">{sh(E.cl.median())}</td><td class="n">{pc(E.g1.median())}</td>'
           f'<td class="n">{pc(done.fc5.median())}</td><td class="n">{pc(done.fc20.median())}</td><td class="n">{pc(done.i20.median())}</td></tr></table>')
    fails = E[(E.fc10 < 0) | (E.fc20 < 0)]
    c_hist = card(f"📜 歷次表:2015 年以來大盤單日漲 {MIN_UP * 100:.0f}% 以上的 {len(E)} 天", th
                  + f'<div class="note">個股欄位是全部個股與 ETF 的中位數;「收盤買」=大漲當天收盤價買進。黃底那一天個股開盤跳空中位數 {pc(E.gap[MAIN])},'
                    f"其他幾次都不到 3%——規模相近的只有那一次。"
                    + ("" if fails.empty else "之後 10 或 20 日中位數是負的:" + "、".join(f"{d:%Y/%m/%d}" for d in fails.index) + "。") + "</div>",
                  f"●本機日線至 {last:%m/%d}")
    lab = lambda d: f"{d.year}/{d.month}/{d.day}"                                            # noqa: E731
    c_chart = card("📈 歷次走勢:大漲之後的加權指數", chart(paths, lab(pd.Timestamp(MAIN)), {lab(d) for d in E.index if d >= pd.Timestamp(PEAK)})
                   + '<div class="note">事件前一天收盤 = 100。橘線是規模最像的一次,藍線是這一波下跌(10/6 高點之後)裡的大漲日,灰線是其他幾次。線尾的數字是最後一天的位置。</div>')

    # ── 主例:分類 ──
    t = T[pd.Timestamp(MAIN)]
    md = f"{pd.Timestamp(MAIN):%Y/%m/%d}"
    tc = ("<table><tr><th>當天怎麼走</th><th>檔數</th><th>買得到嗎</th><th>開盤買<br>到收盤</th><th>開盤買<br>5 日後</th><th>開盤買<br>20 日後</th><th>20 日<br>上漲比例</th></tr>")
    G = {k: g for k, g in t.groupby("cls")}
    for k in "1234567":
        g = G.get(k)
        if g is None:
            continue
        tc += (f'<tr{" class=yl" if k == "4" else ""}><td><b>{CLS[k]}</b></td><td class="n">{len(g)}</td><td>{BUY[k]}</td>'
               f'<td class="n">{pc(med(g.fo0))}</td><td class="n">{pc(med(g.fo5))}</td><td class="n">{pc(med(g.fo20))}</td><td class="n">{sh(win(g.fo20))}</td></tr>')
    tc += "</table>"
    weak = t[t.cls.isin(["3", "5"])]
    c_cls = card(f"🔎 {md} 那天,{len(t):,} 檔怎麼走", tc + checks([
        ("ok", f"<b>買得到、後面也有肉的是黃底那一類</b>:開盤沒漲停、盤中被拉上漲停,{len(G['4'])} 檔;開盤買到收盤中位數 {pc(med(G['4'].fo0))}"),
        ("xx", f"<b>開很高卻收不住的 {len(weak)} 檔最差</b>(開盤漲停收不住+開高 5% 以上沒收漲停):開盤買 5 日後中位數 {pc(med(weak.fo5))},只有 {sh(win(weak.fo5))} 上漲"),
        ("wn", "「開盤買」對一字鎖死那一類只是算術(實際買不到);開盤漲停、盤中打開過的那一類,實際買到的價格就是漲停價")]),
        f"●{md} 日線")

    # ── 隔天 ──
    lk = G["1"]
    tn = "<table><tr><th>前一天怎麼走</th><th>隔天開盤<br>(中位)</th><th>隔天開盤<br>比較低的比例</th><th>隔天開盤買<br>5 日後</th><th>隔天開盤買<br>20 日後</th><th>20 日<br>上漲比例</th></tr>"
    for k in "1234567":
        g = G.get(k)
        if g is None:
            continue
        tn += (f'<tr><td><b>{CLS[k]}</b></td><td class="n">{pc(med(g.gap1))}</td><td class="n">{sh((g.gap1.dropna() < 0).mean())}</td>'
               f'<td class="n">{pc(med(g.fn5))}</td><td class="n">{pc(med(g.fn20))}</td><td class="n">{sh(win(g.fn20))}</td></tr>')
    tn += "</table>"
    oth = E.drop(pd.Timestamp(MAIN))
    c_next = card(f"⏭ 隔天({md} 的下一個交易日)", tn + checks([
        ("ok", f"<b>隔天 {sh((t.gap1.dropna() < 0).mean())} 的股票開盤比前一天收盤低</b>(中位數 {pc(med(t.gap1))});前一天整天鎖死的 {len(lk)} 檔,"
               f"隔天又開盤漲停的只有 {int((lk.gap1 >= LIM).sum())} 檔"),
        ("wn", "<b>其他幾次不一定這樣</b>:隔天開盤中位數 " + "、".join(f"{d:%Y/%m/%d} {pc(e.g1)}" for d, e in oth.iterrows()) + ";前一天鎖死的那幾檔,有幾次隔天是繼續跳空往上")]),
        "●隔天開盤價買進")

    # ── 誰被鎖:成交值 × 跌幅 ──
    s = t[t.sector.notna()].copy()
    s["aq"], s["dq"] = q5(s.amt20), q5(s.dd60)
    cell = s.groupby(["aq", "dq"]).apply(lambda g: pd.Series(dict(
        n=len(g), ol=g.open_lim.mean(), lk=g.locked.mean(), c4=(g.cls == "4").mean(), fo20=med(g[~g.open_lim].fo20), fn20=med(g.fn20))), include_groups=False)
    AL, DL = ["最小 20%", "小", "中", "大", "最大 20%"], ["跌最深 20%", "深", "中", "淺", "跌最少 20%"]
    tw = "<table><tr><th>20 日均成交值 ＼ 離 60 日高點</th>" + "".join(f"<th>{x}</th>" for x in DL) + "</tr>"
    for a in range(1, 6):
        tw += f"<tr><td><b>{AL[a - 1]}</b></td>"
        for dq in range(1, 6):
            v = cell.loc[(a, dq)]
            tw += (f'<td class="n" style="background:rgba(224,123,0,{v.ol * 0.75:.2f})" title="{int(v.n)} 檔"><b>{v.ol * 100:.0f}%</b>'
                   f'<br><small>鎖死 {v.lk * 100:.0f}%</small></td>')
        tw += "</tr>"
    tw += "</table>"
    ga, gd = s.groupby("aq"), s.groupby("dq")
    etf = t[t.index.str.startswith("00")]
    c_who = card(f"🔒 {md} 誰開盤就漲停(大字)、誰整天鎖死(小字)", tw + checks([
        ("ok", f"<b>成交值越大越買不到</b>:最大 20% 有 {sh(ga.open_lim.mean()[5])} 開盤就漲停、{sh(ga.locked.mean()[5])} 整天鎖死;最小 20% 是 {sh(ga.open_lim.mean()[1])}、{sh(ga.locked.mean()[1])}"),
        ("ok", f"<b>跌得少的不太鎖,但之後也沒什麼反彈</b>:跌最少 20% 開盤漲停 {sh(gd.open_lim.mean()[5])},當天收盤買 20 日後中位數 {pc(med(s[s.dq == 5].fc20))};"
               f"跌最深 20% 是 {sh(gd.open_lim.mean()[1])}、{pc(med(s[s.dq == 1].fc20))}"),
        ("wn", f"<b>ETF 也一樣</b>:{len(etf)} 檔 ETF 有 {sh(etf.open_lim.mean())} 開盤就漲停、{sh(etf.locked.mean())} 整天鎖死(0050、0056 都是一字鎖死)"),
        ("wn", "也就是說:當天容易買到的,多半是成交值小或沒跌到的;跌深、量大的那一群幾乎開盤就鎖")]),
        f"●{len(s):,} 檔個股,五分位各約 {len(s) // 25} 檔一格")

    # ── 產業 ──
    gs = s.groupby("sector")
    sec = pd.DataFrame({"n": gs.size(), "ol": gs.open_lim.mean(), "lk": gs.locked.mean(), "cl": gs.close_lim.mean(),
                        "fc20": gs.fc20.median(), "fn20": gs.fn20.median()}).sort_values("lk")
    hd = "<table><tr><th>產業</th><th>檔數</th><th>開盤漲停</th><th>整天鎖死</th><th>收漲停</th><th>收盤買<br>20 日後</th><th>隔天開盤買<br>20 日後</th></tr>"
    half = (len(sec) + 1) // 2
    ts = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start">'          # 產業多,拆左右兩半才不會拉出一長條
    for part in (sec.iloc[:half], sec.iloc[half:]):
        ts += hd + "".join(
            f'<tr><td>{k}</td><td class="n">{int(v.n)}</td><td class="n">{sh(v.ol)}</td><td class="n"><b>{sh(v.lk)}</b></td><td class="n">{sh(v.cl)}</td>'
            f'<td class="n">{pc(v.fc20)}</td><td class="n">{pc(v.fn20)}</td></tr>' for k, v in part.iterrows()) + "</table>"
    ts += "</div>"
    c_sec = card(f"🏭 {md} 各產業(依整天鎖死比例由少到多,左半接右半)", ts
                 + '<div class="note">全部產業都列。那一次的起因是關稅暫緩,全市場一起漲;這一次的起因是輝達,哪些產業會鎖不一定跟那次一樣。</div>')

    # ── 沒鎖的:開多少 ──
    u = s[~s.open_lim].copy()
    u["gb"] = pd.cut(u.gap, [-1, 0, 0.03, 0.05, 0.07, LIM], labels=["開低", "開高 0~3%", "開高 3~5%", "開高 5~7%", "開高 7% 以上(沒到漲停)"], right=False)
    tg_ = "<table><tr><th>開盤位置</th><th>檔數</th><th>後來收漲停</th><th>開盤買<br>到收盤</th><th>開盤買<br>5 日後</th><th>開盤買<br>20 日後</th><th>離 60 日高點<br>(中位)</th></tr>"
    for k, g in u.groupby("gb", observed=True):
        tg_ += (f'<tr><td><b>{k}</b></td><td class="n">{len(g)}</td><td class="n">{sh(g.close_lim.mean())}</td><td class="n">{pc(med(g.fo0))}</td>'
                f'<td class="n">{pc(med(g.fo5))}</td><td class="n">{pc(med(g.fo20))}</td><td class="n">{pc(med(g.dd60), 0)}</td></tr>')
    tg_ += "</table>"
    c_gap = card(f"🚪 {md} 開盤沒漲停的 {len(u)} 檔:開在哪裡,後來怎樣", tg_
                 + '<div class="note">開得越接近漲停,後來收漲停的比例越高,但「開盤買到收盤」能賺的也越少(離漲停只剩一點)。</div>')

    # ── 反例 ──
    c_fail = ""
    if not fails.empty:
        fd = fails.index[-1]
        ft = T[fd]
        fe = E.loc[fd]
        c_fail = card(f"⚠️ 反例:{fd:%Y/%m/%d}(同一波空頭裡)", bignums([
            ("大盤當天", f"{fe.idx * 100:+.1f}%", f"收漲停 {int(ft.close_lim.sum())} 檔"),
            ("收盤買 5 日後", f"{fe.fc5 * 100:+.1f}%", "全部個股中位數"),
            ("收盤買 10 日後", f"{fe.fc10 * 100:+.1f}%", f"只有 {sh(win(ft.fc10))} 上漲"),
            ("大盤 10 日後", f"{fe.i10 * 100:+.1f}%", "")]).replace('class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"') + checks([
            ("xx", f"<b>收漲停的 {int(ft.close_lim.sum())} 檔,10 日後中位數 {pc(med(ft[ft.close_lim].fc10))}</b>;前一天鎖死、隔天開盤追進去的 {int(ft.locked.sum())} 檔,5 日後 {pc(med(ft[ft.locked].fn5))}"),
            ("wn", f"滿 20 日的 {len(done)} 次裡,之後 20 日個股中位數是正的有 {int((done.fc20 > 0).sum())} 次;這一次還沒滿 20 日,而且發生在現在這一波下跌裡")]),
            f"●至 {last:%m/%d}")

    # ── 套到最新一天 ──
    i = len(C) - 1
    now = feat(P, i)
    now["c"], now["pc"], now["v"] = C.iloc[i], C.iloc[i - 1], P["Volume"].iloc[i]
    now["h"] = P["High"].iloc[i]
    now["sector"], now["name"] = sl.sector.reindex(now.index), sl.name.reindex(now.index)
    now = now[now.sector.notna() & (now.v > 0) & now.dd60.notna() & now.amt20.notna()].copy()
    now["ret"] = now.c / now.pc - 1
    now["lim_today"] = (now.ret >= LIM) & (now.c >= now.h * 0.9999)
    now["aq"], now["dq"] = q5(now.amt20), q5(now.dd60)
    now = now.join(cell.rename(columns={"ol": "p_ol", "lk": "p_lk", "c4": "p_c4", "fo20": "h_fo20", "fn20": "h_fn20"}).drop(columns="n"), on=["aq", "dq"])
    pk = C.loc[:PEAK].iloc[-1]
    now["chg"] = now.c / pk.reindex(now.index) - 1
    # 業績:委屈股海報的掃描(月營收、季報;每次重讀)
    import make_poster_wronged as mw
    x = mw.scan().set_index("code")
    now = now.join(x[["oct", "y3", "op_yoy", "eps", "eps_ly", "gm_d", "nonop", "op0", "pe"]])
    now["grow"] = ((now.oct >= 20) & (now.y3 >= 20) & (now.eps > 0) & (now.op0 > 0) & (now.op_yoy >= 20) & (now.gm_d >= -1)
                   & (now.nonop == False) & (now.eps > now.eps_ly))                                                    # noqa: E712
    try:
        dis = set(pd.read_csv(D / "_disposal_now.csv", dtype=str).query("end >= @last.strftime('%Y-%m-%d')").code)
    except Exception:
        dis = set()
    now["dis"] = now.index.isin(dis)
    now.round(4).to_csv(D / "_gapup_scan.csv", encoding="utf-8-sig")
    liq = now[now.amt20 >= LIQ]
    g1 = liq[liq.grow & ~liq.dis]
    easy = g1[g1.p_ol < BAND].sort_values(["p_ol", "chg"])
    hard = g1[g1.p_ol >= BAND].sort_values(["p_ol", "amt20"], ascending=False)
    tl = ("<table><tr><th>公司</th><th>產業</th><th>10/6 以來</th><th>20 日均<br>成交值(億)</th><th>同一格在 "
          f"{md}<br>開盤漲停</th><th>整天鎖死</th><th>開盤沒漲停<br>後來拉上漲停</th><th>沒開盤漲停的<br>開盤買 20 日後</th><th>10 月營收<br>年增</th><th>Q3 本業獲利<br>年增</th><th>本益比</th></tr>")
    for k, v in easy.iterrows():
        tl += (f'<tr><td><b>{v["name"]}</b> {k}{" <small>今天已漲停</small>" if v.lim_today else ""}</td><td><small>{v.sector}</small></td><td class="n">{pc(v.chg, 0)}</td>'
               f'<td class="n">{v.amt20:.1f}</td><td class="n"><b>{sh(v.p_ol)}</b></td><td class="n">{sh(v.p_lk)}</td><td class="n">{sh(v.p_c4)}</td><td class="n">{pc(v.h_fo20, 0)}</td>'
               f'<td class="n">{pc(v.oct / 100, 0)}</td><td class="n">{pc(v.op_yoy / 100, 0)}</td><td class="n">{"—" if pd.isna(v.pe) else f"{v.pe:.0f}"}</td></tr>')
    tl += "</table>"
    mem = "、".join(f'{v["name"]} {k}({sh(v.p_ol)})' for k, v in hard.iterrows())
    c_list = card(f"📋 套到 {last:%m/%d} 收盤:業績還在成長的 {len(g1)} 檔,有 {len(hard)} 檔落在「{md} 開盤漲停率 ≥ {BAND * 100:.0f}%」的格子;低於的 {len(easy)} 檔列在下面", tl
                  + f'<div class="note"><b>怎麼篩</b>:①20 日均成交值 ≥ {LIQ} 億、不在處置(剩 {len(liq[~liq.dis]):,} 檔)②10 月營收與近 3 月營收年增 ≥20%、Q3 本業獲利年增 ≥20%、'
                    f"毛利率沒掉、EPS 年增、不靠業外(剩 {len(g1)} 檔)③自己那一格(成交值五分位 × 離 60 日高點五分位)在 {md} 的開盤漲停率 &lt; {BAND * 100:.0f}%(剩 {len(easy)} 檔)。"
                    f"依開盤漲停率由低到高排,全部列出。<b>這是「歷史上同類型有多少比例開盤沒鎖」,不是預測哪一檔明天買得到,更不是買進名單。</b></div>"
                    f'<div class="note"><b>同樣業績成長、但同一格開盤漲停率 ≥ {BAND * 100:.0f}% 的 {len(hard)} 檔</b>(括號是那一格的開盤漲停率):{mem or "無"}</div>',
                  f"●價格至 {last:%m/%d};全部 {len(now):,} 檔的數字在 data/_gapup_scan.csv")

    # ── 現在、家規、限制 ──
    try:
        risk = json.loads((D / "_market_risk.json").read_text(encoding="utf-8"))
    except Exception:
        risk = {}
    imp = FACTS["fut"] / bm.iloc[-1] - 1
    c_now = card("🕘 現在的狀況", bignums([
        ("台指期夜盤", f"{FACTS['fut']:,}", f"?漲停 +{FACTS['fut_chg']:,} 點({FACTS['when']})"),
        (f"現貨 {last:%m/%d} 收盤", f"{bm.iloc[-1]:,.0f}", f"當天 {r.iloc[-1] * 100:+.1f}%"),
        ("期貨比現貨高", f"{imp * 100:+.1f}%", f"{md} 個股開盤跳空中位數 {E.gap[MAIN] * 100:+.1f}%"),
        ("大盤燈號", risk.get("lamp", "?"), risk.get("rule", "")[:12])]).replace('class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"') + checks([
        ("wn", f"?起因:{FACTS['why']}(媒體報導)。公司的獨立調查還在進行"),
        ("wn", f"<b>系統燈號還是 {risk.get('lamp', '?')}:{risk.get('rule', '')}</b>。原因:{'、'.join(risk.get('reasons', []))}。燈號要等下一次收盤後才會重算"),
        ("wn", f"{last:%m/%d} 當天已經收漲停的有 {int(now.lim_today.sum())} 檔")]), "?=媒體報導")
    oos = ""
    alt = [d for d in E.index if str(d.date()) != MAIN and E.ol[d] >= 0.05]
    if alt:
        a2 = T[alt[-1]]
        a2 = a2[a2.sector.notna()].copy()
        a2["aq"], a2["dq"] = q5(a2.amt20), q5(a2.dd60)
        act = a2.groupby(["aq", "dq"]).open_lim.mean()
        rho = float(pd.concat([cell.ol, act], axis=1).corr(method="spearman").iloc[0, 1])
        oos = (f"拿另一次({alt[-1]:%Y/%m/%d},開盤漲停 {sh(E.ol[alt[-1]])},只有 {len(a2)} 檔有資料)對這 25 格的排序,等級相關 {rho:+.2f};"
               "絕對比例差很多,所以表上的百分比只能看高低順序")
    c_lim = card("⚠️ 限制", checks([
        ("wn", f"<b>規模相近的例子只有一次</b>({md})。名單上的百分比是那一天、那一格的實際比例,樣本每格約 {len(s) // 25} 檔"),
        ("wn", oos or "25 格的排序沒有第二次事件可以對"),
        ("wn", "那一次是連三天跌停之後的全面反彈,起因是總體政策;這一次起因是單一公司,AI 供應鏈鎖得比其他產業多或少,資料回答不了"),
        ("wn", "漲停用還原價的漲幅推;個股日線從 2015 年起,沒有已下市的公司。2026/7/31 那天本機只有不到一半的股票有資料"),
        ("wn", "「開盤買」是用開盤價算,實際下單不一定買得到開盤價;沒有扣手續費、交易稅"),
        ("wn", "業績用已公布的月營收與季報(落後指標);沒有逐檔查個股消息"),
        ("wn", "這是歷史統計與體檢,不是買賣建議")]), extra_cls="risk")

    main_e = E.loc[MAIN]
    concl = [
        ("ok", f"<b>規模相近的只有 {md} 一次</b>:{sh(main_e.ol)} 的股票開盤就漲停、{sh(main_e.lk)} 整天鎖死、{sh(main_e.cl)} 收漲停"),
        ("ok", f"<b>那天買得到又有後續的</b>,是開盤沒漲停、後來被拉上漲停的 {len(G['4'])} 檔(多半是成交值中小、跌很深的);成交值最大的 20% 有 {sh(ga.locked.mean()[5])} 整天鎖死"),
        ("ok", f"<b>那一次沒買到的,隔天幾乎都買得到</b>:隔天 {sh(main_e.g1dn)} 的股票開盤比前一天收盤低;前一天鎖死的那群,隔天開盤買 20 日後中位數 {pc(med(lk.fn20))}"),
        ("xx", f"<b>開很高卻收不住的最差</b>:{len(weak)} 檔,開盤買 5 日後中位數 {pc(med(weak.fo5))}"),
        ("xx", ("<b>不是每次大漲都有後續</b>:" + "、".join(f"{d:%Y/%m/%d} 之後 10 日個股中位數 {pc(e.fc10)}" for d, e in fails.iterrows())) if not fails.empty
               else "<b>歷次大漲之後 20 日個股中位數都是正的</b>,但次數很少"),
        ("wn", f"<b>系統燈號目前 {risk.get('lamp', '?')}</b>({risk.get('rule', '')});下面的名單是「歷史上同類型開盤沒鎖的比例」,不是買單"),
    ]
    c_concl = card("📌 結論:夜盤漲停的隔天,還買得到什麼", checks(concl))
    c_big4 = card("🔢 四個數字", bignums([
        ("開盤就漲停", sh(main_e.ol), f"{md},{len(t):,} 檔"),
        ("整天鎖死", sh(main_e.lk), f"成交值最大 20%:{sh(ga.locked.mean()[5])}"),
        ("隔天開盤比較低", sh(main_e.g1dn), f"中位數 {main_e.g1 * 100:+.1f}%"),
        ("之後 20 日是正的", f"{int((done.fc20 > 0).sum())}/{len(done)} 次", "個股中位數,大漲當天收盤買")]).replace(
        'class="bignums"', 'class="bignums" style="grid-template-columns:1fr"'))        # 直排四格,高度才跟左邊的圖差不多

    date = f"{now_tw():%Y%m%d}"
    blocks = [("wide", row([c_chart, c_big4], "21")), c_concl, c_now, ("wide", c_hist), c_cls, c_next, c_who, c_lim, c_gap]
    blocks += ([c_fail] if c_fail else []) + [("wide", c_list), ("wide", c_sec)]
    html = shell_flow(
        title_html="<b>夜盤漲停</b>的隔天,還買得到什麼?",
        subtitle=f"規模相近的只有 {md} 一次:{sh(main_e.ol)} 開盤就漲停、{sh(main_e.lk)} 整天鎖死,成交值越大越買不到;"
                 f"隔天 {sh(main_e.g1dn)} 的股票開盤比前一天收盤低。大漲之後 20 日個股中位數 {int((done.fc20 > 0).sum())}/{len(done)} 次是正的"
                 + ("" if fails.empty else f";最近一次({fails.index[-1]:%m/%d})10 日後是 {fails.fc10.iloc[-1] * 100:+.1f}%"),
        brand="跳空漲停",
        blocks=blocks, kind="event",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:本機個股還原價日線(2015 年起)、加權指數、月營收與季報;期貨夜盤與起因為媒體報導 · ●=本機資料算的 ?=媒體報導 · 研究筆記,非投資建議")
    # 驗證點
    pd.set_option("display.width", 220)
    print(E[["n", "idx", "gap", "ol", "lk", "cl", "g1", "fc5", "fc10", "fc20", "i20"]].round(3).to_string())
    print(pd.DataFrame({k: dict(n=len(g), fo0=med(g.fo0), fo5=med(g.fo5), fo20=med(g.fo20), g1=med(g.gap1), fn20=med(g.fn20)) for k, g in G.items()}).T.round(3).to_string())
    print(f"最新 {last:%Y-%m-%d}|流動性夠 {len(liq)}|業績成長 {len(g1)}|開盤漲停率<{BAND:.0%} {len(easy)}:{'、'.join(easy.name)}")
    return str(save_poster("跳空漲停", date, html))


if __name__ == "__main__":
    print(main())

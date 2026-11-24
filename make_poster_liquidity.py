# -*- coding: utf-8 -*-
"""主題海報:無量跌停只能等死嗎?——流動性凍結的經典案例(2026-11-23)
「流動性更低 無量跌停股票只能等死」「流動性問題 我們有甚麼經典案子可以學習嗎」
兩部分:
  ・自己算的(●):scripts/liquidity_scan.py 掃本機個股日線(2015 年起),找出每一串「無量跌停」——
    幾檔、鎖幾天、打開那天的量、打開之後的報酬;分成「全市場一起鎖」和「個股自己出事」兩種
  ・歷史案例(本機資料沒有的):CASES 那張表是查證後手抄的。●=讀過原文或用本機指數資料驗過,?=只有第三方轉述或搜尋摘要
手動:python -X utf8 make_poster_liquidity.py      (約 20 秒)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from poster import bignums, card, checks, row, save_poster, shell_flow
from twtime import now_tw

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))
import liquidity_scan as L  # noqa: E402

# 鎖死檔數沒到門檻、但使用者點名要對照的大跌日(事件視窗)
FORCED = [("2015-08-24", "2015-08-24"), ("2018-10-11", "2018-10-11"), ("2020-03-19", "2020-03-19"), ("2022-10-11", "2022-10-13")]
# 背景是記憶寫的(沒有逐一查證);2026 年中的三次只知道日期
WHY = {"2015-08": "陸股股災", "2018-10": "美股十月重挫", "2020-03": "新冠疫情", "2021-05": "本土疫情三級警戒", "2022-10": "升息空頭",
       "2024-08": "日圓套利平倉", "2025-04": "美國對等關稅", "2026-11": "這一次"}
LOCK_C, VOL_C = "#e07b00", "#2f6db5"

# 歷史案例:(案例, 凍結多久, 怎麼解凍, 解凍當下/之後, 標記與出處)
CASES = [
    ("台灣 1988<br>證所稅",
     "? 9/24 宣布隔年復徵證所稅,之後連續 19 個交易日無量下跌;加權指數約 8,800 → 5,600 點(約 −36%;各家寫的點數不一:8,814→5,602 或 8,789→5,615)",
     "? 政策退讓(調整課徵內容)加上銀行團進場護盤",
     "? 風暴平息後指數回升。查不到「每天都是跌停」的原始統計,只查得到「無量下跌 19 天」",
     "? 天下、今周刊、遠見的事後整理(搜尋摘要,沒讀到證交所原始資料)"),
    ("台灣 1999/9<br>921 地震",
     "● 9/20 之後休市,9/27 才恢復交易(本機指數資料 9/20 和 9/27 之間沒有交易日)。? 9/27~10/8 跌幅限制 7% → 3.5%",
     "時間:兩週後恢復 7%",
     "● 9/27 開市當天 −2.7%;跌幅減半期間指數 7,972 → 7,553(−5.3%),沒有崩",
     "? 跌幅 3.5% 的起訖日來自證交所大事記的搜尋摘要(原頁面讀不到內文);● 指數是本機資料"),
    ("台灣 2000<br>跌幅減半三次",
     "? 3/20~3/27、10/20~11/7、11/21~年底,三度把跌幅限制縮成 3.5%(漲幅維持 7%)",
     "時間到期自動恢復;2001/1/2 回到 7%",
     "● 10/19 收 5,081,實施首日 +6.4%;但年底前再跌到 4,615(12/27),隔年 10/3 跌到 3,446——比實施前再低 32%",
     "? 日期來自證交所大事記的搜尋摘要;● 指數是本機資料"),
    ("台灣 2008/10<br>跌幅減半+全面禁空",
     "● 10/13~10/17 跌幅限制 7% → 3.5%;全面禁止借券及融券放空展延到 12/31(行政院 97/10/12 新聞稿原文)",
     "? 全面禁空 11/27 提前解除(經理人月刊整理,和新聞稿寫的 12/31 不同);國安基金同期進場",
     "● 那一週指數 5,131 → 4,960,每天跌 1~3%(接近 3.5% 的上限);10/27 單日 −4.65%(代表那時已恢復 7%);11/20 見底 4,090,比實施前再低 20%",
     "● 行政院全球資訊網「穩定當前股市措施」(已讀原文);● 指數是本機資料"),
    ("香港 1987<br>停市四天",
     "? 10/20~10/23 股市、期市停市四天",
     "時間:10/26 復市",
     "? 復市當天恆生指數 −33.3%(−1,120.7 點),四天的賣壓一次出來",
     "? 只有一個第三方來源(搜尋摘要),沒對到港交所原始資料"),
    ("中國 2015/7<br>千股停牌",
     "? 7/8 約 1,300 家公司停牌(約占上市公司一半),7/9 增加到 1,476 家",
     "? 市場回穩後陸續復牌;路透事後報導一半以上的停牌公司已恢復交易",
     "停牌的股票那幾天完全不能賣;? 中國的停牌可以持續數月",
     "? 路透(Fortune 轉載)、財新、美中經濟暨安全審查委員會報告(搜尋摘要)"),
    ("中國 2016/1<br>熔斷四天",
     "? 1/4 上路;1/4、1/7 兩天各觸發兩次,1/7 全天交易不到 30 分鐘",
     "? 政策轉向:1/7 晚上宣布 1/8 起暫停熔斷,前後只實施四天",
     "? 報導的解讀:怕被關在裡面,大家搶在停盤前賣,反而加速下跌",
     "? 多家媒體一致(科技新報、鉅亨、中國證券報;搜尋摘要)"),
    ("美國 2020/3<br>熔斷四次",
     "? 3/9、3/12、3/16、3/18 四度觸發第一級熔斷(S&P 500 跌 7%),每次停 15 分鐘",
     "停 15 分鐘就恢復交易;沒有個股漲跌停,不會鎖死",
     "市場一直有成交,只是價格很難看——和台灣「鎖在跌停價賣不掉」是兩種不同的問題",
     "? 多家媒體一致(NPR、Fortune、Nasdaq;搜尋摘要)"),
    ("樂陞 2016<br>個股",
     "? 8/31 公開收購破局;到 9/8 開盤前連 7 根跌停",
     "? 9/8 兩筆 3,887 張、3,620 張的買單敲開跌停,盤中拉到漲停",
     "? 之後公司撤銷公開發行。爆量打開不是止跌——和下面「個股型、爆量打開」的統計同一個方向",
     "? 鉅亨、科技新報、ETtoday(搜尋摘要)。本機股價檔沒有這檔(已下市)"),
    ("康友-KY 2020<br>個股",
     "● 8/17 第 7 根跌停(跌停價 56.6 元);? 8/7 成交只有 343 張、跌停掛賣 14,663 張",
     "沒有解凍:● 證交所處分 8/18 起停止買賣",
     "? 2021/4/1 下市。最壞的情況不是鎖很久,是鎖到不能交易——7 根跌停之後就沒有賣的機會了",
     "● 中央社 2020/8/17(已讀原文);? 其餘是搜尋摘要。本機股價檔沒有這檔(已下市)"),
]


def pc(x, d=0) -> str:
    if x is None or pd.isna(x):
        return "—"
    c = "rd" if x > 0 else "gn" if x < 0 else ""
    return f'<span class="{c}">{x * 100:+.{d}f}%</span>'


def sh(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 100:.0f}%"


def lockbars(rows: list) -> str:
    """每個大跌日一列:條的長度=跌停檔數占有量能個股的比例,橘=其中無量鎖死、藍=有量的跌停。"""
    grid = "display:grid;grid-template-columns:auto minmax(160px,1fr) auto auto;gap:5px 10px;align-items:center;font-size:13px"
    out = ['<div></div><div style="font-size:11.5px;color:#5b6673">'
           f'<span style="display:inline-block;width:10px;height:10px;background:{LOCK_C};border-radius:2px"></span> 無量鎖死 '
           f'<span style="display:inline-block;width:10px;height:10px;background:{VOL_C};border-radius:2px;margin-left:10px"></span> 跌停但有量(賣得掉)</div>'
           '<div style="font-size:11.5px;color:#5b6673;text-align:right">跌停/鎖死</div>'
           '<div style="font-size:11.5px;color:#5b6673;text-align:right">鎖死占跌停</div>']
    for lab, liquid, ld, lock in rows:
        a, b = lock / liquid * 100, (ld - lock) / liquid * 100
        tip = f"{lab}:有量能的個股 {liquid} 檔,跌停 {ld} 檔,其中無量鎖死 {lock} 檔"
        out.append(f'<div style="white-space:nowrap" title="{tip}"><b>{lab}</b></div>'
                   f'<div title="{tip}" style="display:flex;gap:2px;height:17px;background:#eef1f5;border-radius:4px;overflow:hidden">'
                   f'<span style="width:{a:.1f}%;background:{LOCK_C}"></span><span style="width:{b:.1f}%;background:{VOL_C}"></span></div>'
                   f'<div class="n" style="text-align:right;white-space:nowrap">{ld} / <b>{lock}</b></div>'
                   f'<div class="n" style="text-align:right"><b>{lock / ld * 100:.0f}%</b></div>')
    return f'<div style="{grid}">' + "".join(out) + "</div>"


def agg(g: pd.DataFrame) -> dict:
    o = g[g.opened.astype(bool)]
    f = o[o.f20.notna()]
    b = o.back60.dropna().astype(bool)
    return dict(n=len(g), n20=len(f), wait=o.wait.median(), total=o.total.median(), open_vr=o.open_vr.median(),
                f5=f.f5.median(), f10=f.f10.median(), f20=f.f20.median(), win=(f.f20 > 0).mean() if len(f) else np.nan,
                f60=f.f60.median(), back=b.mean() if len(b) else np.nan, lower=(f.low_after < 0).mean() if len(f) else np.nan)


def main() -> str:
    days, runs = L.scan()
    idx = L.index_close()
    nm = pd.read_csv(ROOT / "data" / "stock_list.csv", dtype=str).set_index("code")["name"].to_dict()
    runs["start"], runs["end"] = pd.to_datetime(runs.start), pd.to_datetime(runs.end)
    last = days.index.max()
    di = list(days.index)

    # 事件型:開始日前後 5 個日曆天內,曾經一天鎖死 ≥ EVENT_MIN 檔
    hot = days.index[days.lock >= L.EVENT_MIN]
    runs["mkt"] = runs.start.map(lambda x: bool(((hot >= x - pd.Timedelta(days=5)) & (hot <= x + pd.Timedelta(days=5))).any()))
    A, M, S = agg(runs), agg(runs[runs.mkt]), agg(runs[~runs.mkt])
    le3 = float((runs[runs.opened.astype(bool)].n <= 3).mean())          # 已經打開的串裡,3 天內打開的比例
    yrs = (last - days.index.min()).days / 365.25

    # ── 主角:歷次大跌日 ──
    y22 = days.loc["2022"].ld.idxmax()
    pick = days[(days.ld >= 150) | (days.lock >= L.EVENT_MIN) | (days.index == y22)]
    c_chart = card("📊 歷次大跌日:跌停幾檔,其中幾檔是「無量鎖死」", lockbars(
        [(f"{d:%Y/%m/%d}", int(x.liquid), int(x.ld), int(x.lock)) for d, x in pick.iterrows()]),
        src="條的長度=跌停檔數占「前 20 日均量 ≥500 張的個股」的比例。跌停=收在最低價且跌 9.5~10%(2015/6 前 7%);無量鎖死=當天量不到前 20 日均量的三成")
    ratio = pick.lock / pick.ld
    r_now = float(days.lock[last] / days.ld[last])
    rank = int((ratio[pick.ld >= 150] > r_now).sum()) + 1

    # ── 事件表 ──
    ev = sorted(set(L.events(days)) | {(pd.Timestamp(a), pd.Timestamp(b)) for a, b in FORCED})
    E = [L.summarize(days, runs, a, b, idx) for a, b in ev]
    t = ("<table><tr><th>事件</th><th>大盤那天</th><th>跌停 / 鎖死<br><small>(一價到底)</small></th><th>連鎖幾天<br><small>中位 / 最長</small></th>"
         "<th>之後每天<br>鎖死檔數</th><th>第一根跌停<br>→打開日</th><th>打開後<br>5 日</th><th>10 日</th><th>20 日</th><th>20 日<br>上漲比例</th>"
         "<th>60 日內回到<br>跌停前</th><th>大盤低點</th></tr>")
    for e in E:
        a = pd.Timestamp(e["a"])
        ia = di.index(a)
        seq = "→".join(str(int(v)) for v in days.lock.iloc[ia:ia + 4])
        few = e["n20"] < 10
        why = WHY.get(f"{a:%Y-%m}", "")
        ir = idx.pct_change().get(pd.Timestamp(e["peak_ld_d"]), np.nan)

        def cell(v, f=pc):
            return "<small>樣本太少</small>" if few and e["n20"] else "—" if not e["n20"] else f(v)
        t += (f'<tr><td><b>{a:%Y/%m/%d}</b><br><small>{why}</small></td><td class="n">{pc(ir, 1)}</td>'
              f'<td class="n">{e["peak_ld"]} / <b>{e["peak_lock"]}</b><br><small>({e["peak_one"]})</small></td>'
              f'<td class="n">{e["len_med"]:.0f} / {e["len_max"]}<br><small>{e["n"]} 串</small></td><td class="n">{seq}</td>'
              f'<td class="n">{cell(e["wait"])}</td><td class="n">{cell(e["f5"])}</td><td class="n">{cell(e["f10"])}</td><td class="n">{cell(e["f20"])}</td>'
              f'<td class="n">{cell(e["f20_win"], sh)}</td><td class="n">{cell(e["back60"], sh)}</td>'
              f'<td class="n">{pd.Timestamp(e["idx_low_d"]):%m/%d}<br><small>{e["idx_low"]:,.0f}</small></td></tr>')
    t += "</table>"
    e25 = next(e for e in E if f"{pd.Timestamp(e['a']):%Y-%m}" == "2025-04")
    e24 = next(e for e in E if f"{pd.Timestamp(e['a']):%Y-%m}" == "2024-08")
    t += checks([
        ("ok", f"<b>2025/4 關稅是唯一一次全市場鎖死</b>:4/7 有量能的 {int(days.liquid['2025-04-07'])} 檔裡 {int(days.ld['2025-04-07'])} 檔跌停、"
               f"{int(days.lock['2025-04-07'])} 檔一價到底。鎖了 3 天(4/7~4/9),4/10 指數 {pc(idx.pct_change()['2025-04-10'], 1)} 當天全部打開;"
               f"被鎖住的人等到打開那天收盤,價位比第一根跌停價 {pc(e25['wait'])}(中位數),之後 20 日 {pc(e25['f20'])}、{sh(e25['f20_win'])} 上漲"),
        ("ok", f"<b>2024/8/5 只鎖一天</b>:{e24['peak_ld']} 檔跌停,鎖死 {e24['peak_lock']} 檔;隔天打開時收盤比跌停價再 {pc(e24['wait'])},之後 20 日 {pc(e24['f20'])}"),
        ("wn", "2015/8/24、2018/10/11、2020/3/19 各有 180~310 檔跌停,但鎖死的只有個位數——那幾次跌停板上都有人接,賣得掉"),
        ("wn", "「大盤低點」是事件前 3 日到之後 40 個交易日內的最低收盤;「之後每天鎖死檔數」從事件第一天起連續四天")])
    c_hist = card("🗂 每一次事件(本機個股日線重算)", t,
                  src="一串=連續收跌停的交易日,串裡至少一天無量才算;打開日=第一個沒收在跌停的交易日,之後的報酬都從打開日收盤起算(還原價)。樣本不到 10 串的不列統計")

    # ── 兩種鎖死 ──
    def trow(lab, g):
        x = agg(g)
        return (f'<tr><td>{lab}</td><td class="n">{x["n20"]}</td><td class="n">{pc(x["wait"])}</td><td class="n">{pc(x["total"])}</td>'
                f'<td class="n">{pc(x["f20"])}</td><td class="n">{sh(x["win"])}</td><td class="n">{pc(x["f60"])}</td><td class="n">{sh(x["back"])}</td></tr>')
    hd = ("<tr><th>連鎖幾天</th><th>串數</th><th>第一根跌停<br>→打開日</th><th>跌停前→<br>打開日</th><th>打開後<br>20 日</th><th>上漲比例</th>"
          "<th>打開後<br>60 日</th><th>60 日內回到<br>跌停前</th></tr>")
    cut = [("1 天", 1, 1), ("2 天", 2, 2), ("3 天", 3, 3), ("4 天", 4, 4), ("5 天以上", 5, 99)]
    t = f"<table><tr><th colspan='8'>全市場一起鎖(事件型)——{M['n']} 串,其中 {M['n20']} 串打開已滿 20 個交易日</th></tr>{hd}"
    t += "".join(trow(k, runs[runs.mkt & runs.n.between(a, b)]) for k, a, b in cut) + trow("<b>全部</b>", runs[runs.mkt]) + "</table>"
    t += f"<table><tr><th colspan='8'>個股自己出事被鎖(個股型)——{S['n']} 串,其中 {S['n20']} 串打開已滿 20 個交易日</th></tr>{hd}"
    t += "".join(trow(k, runs[~runs.mkt & runs.n.between(a, b)]) for k, a, b in cut) + trow("<b>全部</b>", runs[~runs.mkt]) + "</table>"
    s5 = agg(runs[~runs.mkt & (runs.n >= 5)])
    s1 = agg(runs[~runs.mkt & (runs.n == 1)])
    t += checks([
        ("ok", f"<b>全市場一起鎖的,是流動性問題</b>:打開之後 20 日中位數 {pc(M['f20'])}、{sh(M['win'])} 上漲,60 日內 {sh(M['back'])} 收盤回到跌停前"),
        ("wn", f"<b>個股自己被鎖的,是公司的問題</b>:打開之後 20 日 {pc(S['f20'])}、上漲的只有 {sh(S['win'])}(接近丟銅板),60 日 {pc(S['f60'])}"),
        ("wn", f"<b>個股型鎖越多天越回不來</b>:鎖 1 天的 60 日內 {sh(s1['back'])} 回到跌停前,鎖 5 天以上只有 {sh(s5['back'])}({s5['n20']} 串),"
               f"打開日收盤和跌停前比是 {pc(s5['total'])}")])
    c_type = card("🧬 兩種鎖死,結局不一樣", t,
                  src=f"事件型=那一串開始日的前後 5 天內,曾經一天有 {L.EVENT_MIN} 檔以上無量鎖死;其餘是個股型。「第一根跌停→打開日」=鎖住之後一直等到打開那天收盤,價位又變了多少;串數只算打開已滿 20 個交易日的")

    # ── 解凍訊號 ──
    o = runs[runs.opened.astype(bool) & runs.f20.notna()]

    def srow(lab, g):
        x = agg(g)
        return (f'<tr><td>{lab}</td><td class="n">{x["n20"]}</td><td class="n">{pc(x["f20"])}</td><td class="n">{sh(x["win"])}</td>'
                f'<td class="n">{sh(x["back"])}</td><td class="n">{sh(x["lower"])}</td></tr>')
    hd = "<tr><th>打開那天</th><th>串數</th><th>之後 20 日</th><th>上漲比例</th><th>60 日內回到<br>跌停前</th><th>20 日內曾收得比<br>最後跌停價更低</th></tr>"
    vb = [("量不到平常一半", 0, .5), ("平常的 0.5~1 倍", .5, 1), ("1~2 倍", 1, 2), ("2~5 倍(爆量)", 2, 5), ("5 倍以上", 5, 9999)]
    rb = [("收黑", -1, 0), ("小漲 0~5%", 0, .05), ("大漲 5% 以上", .05, 9)]
    t = ""
    for lab, m in (("個股型", o[~o.mkt]), ("事件型", o[o.mkt])):
        t += f"<table><tr><th colspan='6'>{lab}——照打開日的成交量(和鎖住之前的 20 日均量比)</th></tr>{hd}"
        t += "".join(srow(k, m[(m.open_vr > a) & (m.open_vr <= b)]) for k, a, b in vb) + "</table>"
        t += f"<table><tr><th colspan='6'>{lab}——照打開日的漲跌</th></tr>{hd}"
        t += "".join(srow(k, m[(m.open_ret > a) & (m.open_ret <= b)]) for k, a, b in rb) + "</table>"
    sv = agg(o[~o.mkt & (o.open_vr > 2)])
    sq = agg(o[~o.mkt & (o.open_vr <= .5)])
    mu, md = agg(o[o.mkt & (o.open_ret > .05)]), agg(o[o.mkt & (o.open_ret <= 0)])
    t += checks([
        ("ok", "<b>全市場層級的解凍訊號是「鎖死檔數清零」</b>:2025/4 是 568 → 97 → 58 → 0,清零那天就是大盤止跌日;2024/8/5 是 61 → 隔天個位數"),
        ("wn", f"<b>個股型:爆量打開不是好事</b>。打開日的量超過平常 2 倍的 {sv['n20']} 串,60 日內只有 {sh(sv['back'])} 回到跌停前;"
               f"量縮打開的 {sq['n20']} 串是 {sh(sq['back'])}。爆量代表鎖很久、排隊的賣單一次倒出來,不代表有人看好"),
        ("ok", f"<b>事件型:打開那天收紅收黑,後面差不多</b>——大漲打開的之後 20 日 {pc(mu['f20'])},收黑的也有 {pc(md['f20'])};"
               f"差別在收黑的那批 {sh(md['lower'])} 之後還有更低的收盤(多半就是打開後那幾天)")])
    c_sig = card("🔓 什麼時候算開始解凍", t, src="個股層級的訊號都很弱,樣本分下去每格只有幾十到兩百串")

    # ── 個股型最長 ──
    top = runs[~runs.mkt].sort_values(["n", "start"], ascending=[False, True]).head(25)
    t = ("<table><tr><th>個股</th><th>期間</th><th>連幾根</th><th>跌停前→<br>打開日</th><th>打開日量<br>(倍)</th><th>打開後<br>20 日</th>"
         "<th>60 日</th><th>60 日內回到<br>跌停前</th></tr>")
    for _, x in top.iterrows():
        bk = "—" if pd.isna(x.back60) else "有" if bool(x.back60) else "沒有"
        vr = "—" if pd.isna(x.open_vr) else f"{x.open_vr:.1f}"
        t += (f'<tr><td><b>{nm.get(x.code, "?")}</b> {x.code}</td><td class="n">{x.start:%Y/%m/%d}~{x.end:%m/%d}</td><td class="n">{x.n}</td>'
              f'<td class="n">{pc(x.total)}</td><td class="n">{vr}</td><td class="n">{pc(x.f20)}</td><td class="n">{pc(x.f60)}</td><td class="n">{bk}</td></tr>')
    t += "</table>"
    nb = int(top.back60.dropna().astype(bool).sum())
    c_long = card("⛓ 個股型:鎖最久的 25 串", t + checks([
        ("wn", f"這 25 串裡,60 日內收盤回到跌停前的只有 {nb} 串;打開日收盤和跌停前比,中位數 {pc(top.total.median())}"),
        ("wn", "股價檔沒有已下市的公司,樂陞、康友-KY 這種「鎖到下市」的不在裡面——真實情況比這張表更差"),
        ("wn", "光洋科 2016 那一列之後股價不動,是停止交易,不是止跌")]),
        src="全部 25 列;同樣長度的照日期先後。打開日量=和鎖住之前 20 日均量的倍數")

    # ── 這一次 ──
    cur = runs[~runs.opened.astype(bool)].copy()
    cur["drop"] = cur["last"] / cur.pre - 1
    cur = cur.sort_values(["n", "drop"], ascending=[False, True])
    chips = "".join(f'<span style="display:inline-block;margin:2px 10px 2px 0;white-space:nowrap"><b>{nm.get(x.code, "?")}</b> {x.code} '
                    f'<small>{x.n} 根 {x["drop"] * 100:+.0f}% 量 {x.min_vr * 100:.0f}%</small></span>' for _, x in cur.iterrows())
    seq = "、".join(f"{d:%m/%d} {int(x.ld)}/{int(x.lock)}" for d, x in days.loc["2026-11-16":].iterrows())
    n2 = int((cur.n >= 2).sum())
    c_now = card(f"🧭 這一次({last:%m/%d} 收盤)", checks([
        ("wn", f"{last:%m/%d} 有量能的 {int(days.liquid[last])} 檔裡 {int(days.ld[last])} 檔收跌停,其中 <b>{int(days.lock[last])} 檔無量鎖死</b>"
               f"({int(days.one[last])} 檔一價到底),鎖死占跌停 {r_now * 100:.0f}%——在跌停超過 150 檔的日子裡排第 {rank} 高,僅次於 2025/4/7 的 "
               f"{float(days.lock['2025-04-07'] / days.ld['2025-04-07']) * 100:.0f}%"),
        ("wn", f"每天「跌停/鎖死」:{seq}"),
        ("wn", f"還鎖著的 {len(cur)} 檔裡 {n2} 檔已經連兩根以上,從跌停前算起中位數 {pc(cur['drop'].median())};都還沒打開,所以沒有「打開後」的數字"),
        ("ok", f"和 2025/4 不同的地方:那次 97% 的個股一起跌停、三天後因為關稅暫緩一天全開;這次是 {int(days.ld[last]) / int(days.liquid[last]) * 100:.0f}% 跌停、"
               f"一部分鎖死,還看不出是「全市場一起」還是「一部分公司自己的問題」")])
        + f'<div style="font-size:12.5px;line-height:1.7;margin-top:6px"><b>還鎖著的 {len(cur)} 檔(全部)</b>:<br>{chips}</div>',
        src="每檔後面:已連幾根跌停、從跌停前算起的跌幅、鎖死那幾天最低的量占前 20 日均量的比例。這裡的跌停要求收在當日最低價,所以檔數比 11/20 聊天裡講的 297 檔少")

    # ── 歷史案例 ──
    t = "<table><tr><th>案例</th><th>凍結多久</th><th>怎麼解凍</th><th>解凍當下/之後</th><th>出處</th></tr>"
    for a, b, c, d, e in CASES:
        t += f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td><td><small>{e}</small></td></tr>"
    t += "</table>"
    c_cases = card("📚 本機資料沒有的經典案例(查證後手抄)", t + checks([
        ("ok", "<b>共同點一:關門、縮小跌幅都不會讓賣壓消失</b>——香港 1987 停市四天後一天跌 33%;台灣 2000、2008 跌幅減半之後指數又跌了 32%、20%"),
        ("ok", "<b>共同點二:解凍靠的是原因消失或政策轉向</b>(1988 證所稅退讓、2016 熔斷取消、2025 關稅暫緩),不是靠限制交易"),
        ("wn", "<b>共同點三:最壞的是「鎖到不能交易」</b>(康友-KY 7 根跌停後停止買賣)——個股自己出事的,時間不站在持有人這邊")]),
        src="●=讀過原文,或用本機指數資料驗過;?=只有第三方轉述、搜尋摘要或記憶,數字不保證。1988 年和香港 1987 的點數各來源不一致,只能當量級看")

    # ── 被鎖住時,事實上能做的事 ──
    c_live = card("🧰 被鎖住的時候,規則上還有哪些事是做得到的", checks([
        ("ok", "<b>排隊</b>:跌停價的賣單照「時間優先」成交,越早掛越前面;當天沒成交的委託隔天要重掛、重新排"),
        ("ok", "<b>等「鎖死檔數」變少</b>:事件型歷史上 1~3 天打開;每天收盤後看有幾檔還鎖著,比猜底實際"),
        ("ok", "<b>用別的商品對沖</b>:現貨鎖住時,指數期貨、個股期貨、選擇權、反向 ETF 通常還在交易——但它們的價格往往已經把「打開後還要跌多少」算進去了"
               "(逆價差),而且期貨自己也有漲跌停。這次沒有逐一查每個事件當時的價差"),
        ("wn", "<b>融資戶最被動</b>:維持率不足會被追繳,補不出來就斷頭;斷頭的賣單一樣要排隊,賣不掉就繼續欠——系統的 /斷頭雷達 看的就是這個"),
        ("wn", "<b>先分清楚是哪一種</b>:全市場一起鎖(流動性問題)和公司自己出事(基本面問題),上面兩張表的結局差很多"),
        ("wn", "以上是交易規則和歷史統計,不是買賣建議;大盤燈號目前仍是禁開新倉、只出不進")]))

    # ── 結論 ──
    concl = [
        ("ok", f"<b>先看是哪一種鎖死</b>。{yrs:.0f} 年 {A['n']:,} 串無量跌停,已經打開的裡面 {le3 * 100:.0f}% 在 3 天內打開;「等死」說的是其中一種"),
        ("ok", f"<b>全市場一起鎖(流動性凍結)</b>:歷史上鎖 1~3 天,打開後 20 日中位數 {pc(M['f20'])}、{sh(M['win'])} 上漲。代價是等到打開那天,收盤價比第一根跌停價 {pc(M['wait'])}"),
        ("wn", f"<b>個股自己出事被鎖</b>:打開後 20 日 {pc(S['f20'])}、只有 {sh(S['win'])} 上漲;鎖 5 天以上的 60 日內只有 {sh(s5['back'])} 回到跌停前。這一種才是你說的等死"),
        ("wn", f"<b>真正的全市場鎖死 12 年只有一次</b>(2025/4/7,{int(days.lock['2025-04-07'])} 檔一價到底)。其他大跌日跌停幾百檔,鎖死的不到一成"),
        ("wn", f"<b>這次 {last:%m/%d} 鎖死占跌停 {r_now * 100:.0f}%,在 12 年的大跌日裡排第 {rank} 高</b>(只輸 2025/4/7)——你感覺流動性變差,資料支持"),
        ("ok", "<b>解凍的訊號</b>:市場層級看「鎖死檔數清零」;歷史案例裡解凍靠原因消失或政策轉向,限制交易(停市、縮跌幅、禁空)都沒有讓賣壓消失"),
    ]
    c_concl = card("📌 結論:無量跌停只能等死嗎", checks(concl))
    c_big4 = card("🔢 四個數字", bignums([
        ("3 天內打開", f"{le3 * 100:.0f}%", f"{A['n']:,} 串無量跌停"),
        ("事件型 打開後 20 日", f"{M['f20'] * 100:+.0f}%", f"{sh(M['win'])} 上漲({M['n20']} 串)"),
        ("個股型 打開後 20 日", f"{S['f20'] * 100:+.0f}%", f"{sh(S['win'])} 上漲({S['n20']} 串)"),
        (f"{last:%m/%d} 鎖死", f"{int(days.lock[last])} 檔", f"占跌停 {r_now * 100:.0f}%,大跌日裡第 {rank} 高")]).replace(
        'class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"'))
    c_lim = card("⚠️ 限制", checks([
        ("wn", "個股日線從 2015 年起,而且沒有已下市的公司——「鎖到下市」的案例統計裡看不到,個股型的真實結局只會更差"),
        ("wn", "跌停是用還原價的當日跌幅推的(本機沒有原始價);抽 35 個跌停日和 FinMind 原始價核對,34 個正確、1 個是差一檔沒到跌停"),
        ("wn", "事件型的好成績幾乎都來自 2025/4 那一次(五百多串);那次是因為關稅暫緩才一天全開,不能當成每次都會這樣"),
        ("wn", "2026 年 3、6、7 月的三次事件只知道日期,沒有查背景;事件表的「背景」欄是記憶,沒有逐一查證"),
        ("wn", "歷史案例多數只有第三方轉述(標 ?);2008 年跌幅減半 10/17 之後有沒有展延、全面禁空哪一天解除,來源不一致"),
        ("wn", "這次(11/17~11/20)的鎖死都還沒打開,它屬於哪一種、要鎖幾天,資料回答不了")]), extra_cls="risk")

    date = f"{now_tw():%Y%m%d}"
    html = shell_flow(
        title_html="<b>無量跌停</b>只能等死嗎?流動性凍結的經典案例",
        subtitle=f"{yrs:.0f} 年 {A['n']:,} 串無量跌停:{le3 * 100:.0f}% 在 3 天內打開。全市場一起鎖的,打開後 20 日中位數 {M['f20'] * 100:+.0f}%、{sh(M['win'])} 上漲;"
                 f"個股自己出事被鎖的 {S['f20'] * 100:+.0f}%、只有 {sh(S['win'])} 上漲",
        brand="流動性凍結",
        blocks=[("wide", row([c_chart, c_big4], "21")), c_concl, c_now, ("wide", c_hist), c_type, c_sig, ("wide", c_cases), c_long, c_live, c_lim],
        kind="event",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:本機個股還原價 2015 年起(scripts/liquidity_scan.py)、加權指數 1997 年起;"
               "歷史案例:行政院新聞稿、中央社(已讀原文)與媒體整理(搜尋摘要)· ●=原始出處 ?=第三方轉述 · 研究筆記,非投資建議")
    print({k: round(float(v), 3) for k, v in A.items()}, "\n事件型", {k: round(float(v), 3) for k, v in M.items()},
          "\n個股型", {k: round(float(v), 3) for k, v in S.items()})
    print(f"3 天內打開 {le3:.3f}|{last:%m/%d} 鎖死/跌停 {int(days.lock[last])}/{int(days.ld[last])}={r_now:.3f} 排第 {rank}|還鎖著 {len(cur)} 檔")
    return str(save_poster("流動性凍結", date, html))


if __name__ == "__main__":
    print(main())

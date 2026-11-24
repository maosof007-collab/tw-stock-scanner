# -*- coding: utf-8 -*-
"""專題海報:金融海嘯對照 — 2008 年複習+歷次跌破 20% 之後的一年+六種場景(2026-11-18)
加權指數長歷史存 data/_twii_long.csv(yfinance ^TWII,1997-07 起),之後的日子接 data/benchmark_TWII.csv。
表格(逐段走勢、歷次跌破 20%、國安基金進場後、跌幅對照價位)每次重跑都重算;
美國信用指標是 2026-11-17 從 FRED 抄下來的快照,要更新得手動改 IND。
●=原始數據或開過原文、?=憑記憶或只看到新聞摘要。
手動重跑:python -X utf8 make_poster_2008.py"""
from pathlib import Path

import numpy as np
import pandas as pd

from poster import bignums, card, checks, flow, save_poster, shell
from twtime import now_tw

D = Path(__file__).parent / "data"
# 國安基金歷次進場(第一個護盤交易日;●TechNews 2025/4/8 整理,第 9、10 次為新聞)
NSF = [("2000-03-16", "政黨輪替"), ("2000-10-03", "網路泡沫"), ("2004-05-20", "319 槍擊"), ("2008-09-19", "金融海嘯"),
       ("2011-12-21", "歐債"), ("2015-08-25", "全球股災"), ("2020-03-20", "疫情"), ("2022-07-13", "升息通膨"),
       ("2025-04-09", "對等關稅"), ("2026-11-09", "這一次")]
KIND = {"1999": "v", "2015": "v", "2020": "v", "2024": "v", "2004": "b", "2011": "b", "2022": "b",
        "1997": "x", "2000": "x", "2002": "x", "2007": "x"}
KNAME = {"v": "V 型", "b": "打底", "x": "大空頭"}
# 指標快照:(名稱, 2000/2 高點, 2007/10 高點, 2008/1/22, 2008/9/12 雷曼前, 2008/11/20 最低點, 2026/11/17)
IND = [("公司債利差", 1.75, 1.98, 2.98, 3.43, 5.92, 1.50),
       ("金融情勢指數", -0.20, 0.03, 0.44, 1.25, 3.01, -0.46),
       ("恐慌指數 VIX", 23.2, 19.9, 31.0, 25.7, 80.9, 22.9),
       ("美國失業率%", 4.1, 4.7, 5.0, 6.1, 6.8, 4.1),
       ("美國基準利率%", 5.66, 4.84, 3.68, 2.10, 0.49, 3.88)]


def load() -> pd.Series:
    s = pd.read_csv(D / "_twii_long.csv", parse_dates=["Date"]).set_index("Date")["Close"]
    b = pd.read_csv(D / "benchmark_TWII.csv", parse_dates=["Date"]).set_index("Date")["Close"]
    return pd.concat([s, b[b.index > s.index[-1]]]).dropna()


def zigzag(x: pd.Series, th: float) -> list:
    """收盤價轉折點:反向走超過 th 才算一段。"""
    piv, up = [], None
    hi_d = lo_d = x.index[0]
    hi = lo = x.iloc[0]
    for dt, v in x.items():
        if up is None:
            if v > hi:
                hi, hi_d = v, dt
            if v < lo:
                lo, lo_d = v, dt
            if v <= hi * (1 - th):
                piv.append((hi_d, hi)); up = False; lo, lo_d = v, dt
            elif v >= lo * (1 + th):
                piv.append((lo_d, lo)); up = True; hi, hi_d = v, dt
        elif up:
            if v > hi:
                hi, hi_d = v, dt
            elif v <= hi * (1 - th):
                piv.append((hi_d, hi)); up = False; lo, lo_d = v, dt
        else:
            if v < lo:
                lo, lo_d = v, dt
            elif v >= lo * (1 + th):
                piv.append((lo_d, lo)); up = True; hi, hi_d = v, dt
    piv.append((hi_d, hi) if up else (lo_d, lo))
    return piv


def episodes(s: pd.Series) -> list[dict]:
    """收盤價第一次比一年內高點低 20% 算一次;要再創一年新高才會重新計算下一次。"""
    hi = s.rolling(250, min_periods=120).max()
    eps, armed = [], True
    for i in range(len(s)):
        if armed and s.iloc[i] / hi.iloc[i] - 1 <= -0.20:
            pk = s[:s.index[i]][s[:s.index[i]] >= hi.iloc[i] * 0.99999].index[-1]
            eps.append(dict(peak=pk, pkv=hi.iloc[i], trig=s.index[i], trigv=s.iloc[i], end=s.index[-1]))
            armed = False
        elif not armed and s.iloc[i] >= hi.iloc[i] * 0.99999:
            eps[-1]["end"] = s.index[i]
            armed = True
    for e in eps:
        w, f = s[e["trig"]:e["end"]], s[e["trig"]:]
        e["low_d"], e["low"] = w.idxmin(), w.min()
        e["dd"] = (e["low"] / e["pkv"] - 1) * 100
        e["more"] = (e["low"] / e["trigv"] - 1) * 100
        e["days"] = (e["low_d"] - e["trig"]).days
        e["speed"] = len(s[e["peak"]:e["trig"]]) - 1
        e["y1"] = (f.iloc[250] / f.iloc[0] - 1) * 100 if len(f) > 250 else np.nan
        rec = s[e["low_d"]:][s[e["low_d"]:] >= e["pkv"]]
        e["rec_m"] = (rec.index[0] - e["peak"]).days / 30.4 if len(rec) else np.nan
    return eps


def pc(x: float, nd: int = 1) -> str:
    if pd.isna(x):
        return "—"
    return f'<span class="{"rd" if x > 0 else "gn"}">{x:+.{nd}f}%</span>'


def ym(d) -> str:
    return f"{d.year}/{d.month}/{d.day}"


def main() -> str:
    s = load()
    date = now_tw().strftime("%Y%m%d")
    last, lastd = s.iloc[-1], s.index[-1]
    eps = episodes(s)
    cur, past = eps[-1], eps[:-1]
    pkv, pkd = cur["pkv"], cur["peak"]
    r = s.pct_change() * 100
    up = [e for e in past if e["y1"] > 0]
    deep = [e for e in past if e["dd"] <= -40]
    post09 = [e for e in past if e["peak"].year >= 2009]

    # ── 欄 1:2008 複習 ──
    seg = s["2007-10-29":"2009-12-31"]
    pv = zigzag(seg, 0.10)
    t1 = "<table><tr><th>期間</th><th>指數</th><th>漲跌</th><th>交易日</th></tr>"
    for (a, av), (b, bv) in zip(pv[:-1], pv[1:]):
        hot = ' class="yl"' if abs(bv / av - 1) >= 0.2 else ""
        t1 += (f'<tr{hot}><td class="n">{a.year % 100:02d}/{a.month}/{a.day}→{b.year % 100:02d}/{b.month}/{b.day}</td>'
               f'<td class="n">{av:,.0f}→{bv:,.0f}</td><td class="n">{pc((bv / av - 1) * 100)}</td><td class="n">{len(seg[a:b]) - 1}</td></tr>')
    t1 += "</table>"
    e08 = next(e for e in past if e["peak"].year == 2007)
    c_path = card("📉 2008 年不是一路跌下去的", t1
                  + f'<div class="note">●加權指數收盤價,反向走超過 10% 才算一段。從最高 9,810 到最低 4,090 共跌 {-e08["dd"]:.1f}%、歷時 388 天;'
                    "中間那段 74 天的反彈漲了 25.5%,離高點只差 5%。</div>", "2007/10 → 2009/12")
    c_time = card("🗓 當時發生的事", flow([
        ("2007/10/29 最高收盤 9,809", "?美國次級房貸問題已經浮現,聯準會 9 月開始降息", False),
        ("2008/1/22 單日跌 6.51%", "●第一段 61 個交易日跌 24.5%", False),
        ("3/22 總統大選 → 5/19 反彈到 9,295", "●74 個交易日漲 25.5%;?3 月美國貝爾斯登被收購", False),
        ("9/15 雷曼兄弟倒閉", "?前一個交易日指數 6,310,已經比高點低 36%", True),
        ("9/19 國安基金進場", "●前一日收 5,642;?9/22 起 150 檔平盤下禁空、10/1 全面禁空、跌幅限制縮到 3.5%", False),
        ("11/20 最低收盤 4,089", "●國安基金進場後第 62 天,比進場前再低 27.5%;當天恐慌指數 80.9", True),
        ("2008/12 出口年減約 42%", "?2008 第四季經濟成長率初估 −8.36%;央行 12 月一次降息 3 碼到 2%", False),
        ("2009/1/20 回測 4,243 沒破前低", "●之後到 6/1 漲 63.9%;2009 全年漲 78.3%", False),
        ("2009/8 失業率 6.13% 創新高", "?這時指數已經從低點漲了六成多", False)]),
        "台股與全球")
    c_less = card("📝 從這一段學到的", checks([
        ("xx", f'從第一次跌破 20%({ym(e08["trig"])})到最低點,又過了 <b>{e08["days"]} 天</b>、再跌 <b>{-e08["more"]:.1f}%</b>'),
        ("wn", "最壞的經濟數字(出口年減四成、失業率最高)都出現在股市最低點<b>之後</b>"),
        ("wn", "見底那天是恐慌最高的一天:恐慌指數 80.9、公司債利差 5.92"),
        ("ok", "最低點後一年漲 87.9%;但回到 9,809 要等到 2015 年 4 月,<b>七年半</b>"),
        ("ok", "台積電跌 49%(72.3→36.6),比大盤少,2010 年 12 月回到原高"),
        ("wn", f'2008 全年跌 3% 以上有 {int((r["2008"] <= -3).sum())} 天、漲 3% 以上 {int((r["2008"] >= 3).sum())} 天;'
               f'最近 30 個交易日是 {int((r.iloc[-30:] <= -3).sum())} 天和 {int((r.iloc[-30:] >= 3).sum())} 天')]),
        "●指數數據")

    # ── 欄 2:現在+歷史樣本 ──
    c_now = card("📍 現在在哪裡", bignums([
        ("高點", f"{pkv:,.0f}", f"{pkd.month}/{pkd.day} 收盤"),
        ("現在", f"{last:,.0f}", f"{lastd.month}/{lastd.day} · {(last / pkv - 1) * 100:.1f}%"),
        ("跌破 20% 花了", f'{cur["speed"]} 天', "1997 年以來最快"),
        ("一年前", f"{s.iloc[-251]:,.0f}", f"現在仍高 {(last / s.iloc[-251] - 1) * 100:.0f}%")])
        + checks([
            ("wn", f'●最低收盤 {cur["low"]:,.0f}({cur["low_d"].month}/{cur["low_d"].day});之後 3 天彈 11.5%、又 4 天跌 9.4%'),
            ("wn", "●費城半導體指數 6/22 見高後已跌 34.1%;那斯達克 −11.9%、標普 500 −6.1%、台積電 −16.1%"),
            ("ok", "●台積電 10 月營收年增 59.7%、鴻海 45.7%、廣達 104%——營收還在成長"),
            ("wn", "●全市場融資維持率 144.9%(系統推估);系統燈號 🔴 禁開新倉"),
            ("wn", "?起因:11/3 美國期中選舉後市場擔心 AI 監管(11/5 費半單日跌 12%)、輝達執行長異動"),
            ("ok", "?國安基金 11/6 授權第 10 次進場(5,000 億)、金管會 11/9 起限空")]),
        f"●至 {lastd.month}/{lastd.day} 收盤")

    order = {"v": 0, "b": 1, "x": 2}
    t2 = "<table><tr><th>跌破 20%</th><th>類型</th><th>最大跌幅</th><th>破 20% 後再跌</th><th>幾天見底</th><th>一年後</th></tr>"
    for e in sorted(past, key=lambda e: (order[KIND[str(e["peak"].year)]], e["peak"])):
        k = KIND[str(e["peak"].year)]
        t2 += (f'<tr{" class=yl" if k == "x" else ""}><td class="n">{e["trig"].year}/{e["trig"].month}</td><td>{KNAME[k]}</td>'
               f'<td class="n">{e["dd"]:.1f}%</td><td class="n">{e["more"]:.1f}%</td><td class="n">{e["days"]}</td><td class="n">{pc(e["y1"])}</td></tr>')
    t2 += (f'<tr><td class="n">{cur["trig"].year}/{cur["trig"].month}</td><td>這一次</td><td class="n">{cur["dd"]:.1f}%</td>'
           f'<td class="n">{cur["more"]:.1f}%</td><td class="n">?</td><td class="n">?</td></tr></table>')
    c_eps = card(f"📚 歷史上 {len(past)} 次跌破 20%,之後的一年", t2
                 + f'<div class="note">●收盤價第一次比一年內高點低 20% 算一次(第一欄是那一天的年月),「一年後」從那天起算 250 個交易日。'
                   f'<b>{len(up)} 次一年後更高、{len(past) - len(up)} 次更低</b>;跌超過四成的 {len(deep)} 次都在 2009 年以前,'
                   f'2009 年以後的 {len(post09)} 次最深 {min(e["dd"] for e in post09):.1f}%。'
                   f'跌破 20% 的速度分不出類型:以前最快的三次是 1999(32 天,V 型)、2007(35 天,金融海嘯)、2020(36 天,V 型)。</div>',
                 "1997 年起")

    t3 = "<table><tr><th>進場日</th><th>事件</th><th>之後最低</th><th>幾天見底</th><th>一年後</th></tr>"
    n_bad = 0
    for d0, nm in NSF:
        f = s[d0:]
        if not len(f):
            continue
        base = s[s.index < d0].iloc[-1]
        y = f.iloc[:251]
        lowp = (y.min() / base - 1) * 100
        y1 = (f.iloc[250] / base - 1) * 100 if len(f) > 250 else np.nan
        cur_row = nm == "這一次"
        n_bad += (lowp <= -25) and not cur_row
        t3 += (f'<tr{" class=yl" if lowp <= -25 else ""}><td class="n">{d0[:4]}/{int(d0[5:7])}/{int(d0[8:])}</td><td>{nm}</td>'
               f'<td class="n">{"?" if cur_row else ("沒再破" if lowp >= 0 else f"{lowp:.1f}%")}</td>'
               f'<td class="n">{"?" if cur_row else ("—" if lowp >= 0 else (y.idxmin() - f.index[0]).days)}</td>'
               f'<td class="n">{pc(y1)}</td></tr>')
    t3 += "</table>"
    c_nsf = card("🛡 國安基金進場之後", t3
                 + f'<div class="note">●以進場前一個交易日收盤為基準,看之後一年。9 次裡有 <b>{n_bad} 次</b>進場後還再跌四分之一以上'
                   "(2000 年兩次、2008 年),其餘 6 次進場時離低點都不到一成。進場日期取自 TechNews 2025/4/8 整理。</div>",
                 "9 次+這一次")

    lv = [(cur["dd"], "已經到過", f'{cur["low_d"].month}/{cur["low_d"].day} 收盤'),
          (-24.4, "打底型最淺(2004)", ""), (-28.7, "V 型最深(2020、2025)", ""), (-31.6, "打底型最深(2022)", ""),
          (-40.4, "2002", ""), (-45.9, "1997–98", ""), (-58.3, "2008 金融海嘯", ""), (-66.2, "2000 科技泡沫", "")]
    t5 = "<table><tr><th>從高點跌</th><th>換算指數</th><th>歷史樣本</th><th>上次在這價位</th></tr>"
    for p, nm, when in lv:
        v = pkv * (1 + p / 100)
        below = s[s < v]
        w = when or (f"{below.index[-1].year}/{below.index[-1].month}" if len(below) else "—")
        t5 += f'<tr><td class="n">{p:.1f}%</td><td class="n">{v:,.0f}</td><td>{nm}</td><td class="n">{w}</td></tr>'
    t5 += "</table>"
    c_lv = card("📏 照歷史跌幅換算是多少點", t5
                + '<div class="note">這是把歷史的跌幅比例套到這次高點,不是預測。指數一年多漲了很多,所以連 2008 那種跌幅,'
                  "換算下來也只是回到 2025 年中的價位。</div>", f"高點 {pkv:,.0f}")

    # ── 欄 3:場景+判別 ──
    def sc(title, sample, after, need, now, hot=False):
        return (f'<div class="fbox{" hot" if hot else ""}" style="text-align:left">{title}'
                f'<small>歷史:{sample}</small><small>之後:{after}</small><small>條件:{need}</small><small>現在:{now}</small></div>')
    v = lambda p: f"{pkv * (1 + p / 100):,.0f}"
    scn = '<div class="flow">' + "".join([
        sc("① V 型:跌破 20% 幾天內就是底", "1999/8、2015/8、2020/3、2025/4(11 次裡 4 次)",
           "最大跌幅 21~29%;一年後 +17% ~ +93%", "單一事件引起、政策很快轉向;低點都出現在跌破 20% 後 3 天內",
           f'跌破 20% 已過 {len(s[cur["trig"]:]) - 1} 個交易日,收盤低點 {cur["low"]:,.0f} 還沒破;破了就不是這一型'),
        sc("② 打底型:再跌一成、磨三四個月", "2004、2011、2022(11 次裡 3 次)",
           f"最大跌幅 24~32%(換算 {v(-24.4)} ~ {v(-31.6)});79~119 天見底;一年後 +2% ~ +19%",
           "景氣放慢、利率或庫存調整,但沒有金融機構出事", "信用指標平靜、營收仍成長,符合「沒有金融機構出事」"),
        sc("③ 科技泡沫型(2000–2001)", "2000/2 高點 10,202 → 2001/10 最低 3,446",
           f"跌 66%(換算 {v(-66.2)});跌破 20% 後再跌 58%、歷時 461 天;17 年後才回到高點",
           "科技支出反轉、訂單與營收衰退;起跌時信用指標是平靜的",
           "費半高點是 2022 低點的 6.8 倍(2000 年是 1998 低點的 7.0 倍)、已跌 34%;但營收還沒轉弱", True),
        sc("④ 金融海嘯型(2008)", "2007/10 高點 9,809 → 2008/11 最低 4,089",
           f"跌 58%(換算 {v(-58.3)});跌破 20% 後再跌 48%、歷時 339 天;一年後 −40%",
           "信用市場先出事:公司債利差升到 3 以上、金融情勢指數轉正、大型金融機構倒閉",
           "公司債利差 1.50、金融情勢指數 −0.46,都沒有訊號", True),
        sc("⑤ 匯率/區域金融風暴型(1997–1998)", "1997/8 高點 10,116 → 1999/2 最低 5,474",
           f"跌 46%(換算 {v(-45.9)});跌破 20% 後再跌 32%、歷時 403 天;一年後 −23%",
           "資金外逃、匯率急貶、本土企業與金融機構接連出事", "美元兌台幣 10/6 以來 31.75 → 32.9,六週貶約 3.5%"),
        sc("⑥ 空頭第二段(2002)", "2001/10 見底反彈 87% 後,2002/4 → 10 再跌 40%",
           f"換算 {v(-40.4)};跌破 20% 後再跌 25%、107 天;一年後 −5%",
           "大空頭見底後的反彈結束、景氣二次探底", "要先走完 ③ 或 ④ 才輪得到")]) + "</div>"
    c_scn = card("🎬 六種場景:歷史上出現過的全部走法", scn, "●指數數據")

    t4 = ("<table><tr><th>指標</th><th>2000/2 高點</th><th>2007/10 高點</th><th>2008/1</th><th>雷曼前</th><th>2008 最低</th><th>現在</th></tr>"
          + "".join(f'<tr><td>{n}</td>' + "".join(f'<td class="n">{x:g}</td>' for x in xs[:-1])
                    + f'<td class="n yl">{xs[-1]:g}</td></tr>' for n, *xs in IND) + "</table>")
    c_ind = card("🔎 用哪些數字分辨是哪一種", t4 + checks([
        ("ok", "<b>公司債利差</b>(美國 Baa 級公司債殖利率減 10 年公債):企業借錢比政府貴多少。升到 3 以上才是 2008 那條路,現在 1.50"),
        ("ok", "<b>金融情勢指數</b>(芝加哥聯準銀行編):正值代表資金變緊。2008/1 已經轉正,現在 −0.46"),
        ("wn", "這兩個數字只能排除 2008 型。2000 年起跌時兩個都很平靜,所以<b>排除不了科技泡沫型</b>"),
        ("wn", "分辨科技泡沫型要看營收:台積電與 AI 伺服器廠的月營收年增率有沒有掉下來(每月 10 日前公布)"),
        ("wn", f'分辨 V 型要看 {cur["low"]:,.0f}(11/6 收盤低點)有沒有被收盤跌破')]),
        "●FRED,至 11/17")

    c_cmp = card("⚖️ 跟 2008 比", checks([
        ("ok", "不一樣:2008 是房貸與銀行出事,這次是 AI/半導體股與政治事件,信用市場沒有反應"),
        ("ok", "不一樣:2008 年出口年減四成;現在台積電月營收年增五成以上"),
        ("xx", f'一樣:政府同樣出手護盤。2008 年國安基金進場後 62 天才見底,又跌了 27.5%'),
        ("xx", "一樣:急跌之後有很強的反彈。2008 年那段反彈漲了 25.5% 才開始主跌段"),
        ("wn", f'更快:2008 年第一段花 61 個交易日跌 24.5%,這次 {cur["speed"]} 個交易日跌 {-cur["dd"]:.1f}%')]))

    c_risk = card("⚠️ 這張海報的限制", checks([
        ("wn", "樣本只有 11 次(1997 年 7 月起);1990 年 12,682 → 2,485 那一次不在資料裡"),
        ("wn", "標 ? 的事件日期與數字(雷曼、禁空、降息、出口、失業率、這次起因、國安基金)來自記憶或新聞摘要,沒有逐條開原文"),
        ("wn", "沒查:美國私募信貸與 AI 資本支出的舉債狀況、台灣銀行與壽險的曝險、2008 年的融資餘額與外資賣超金額"),
        ("wn", "高收益債利差 FRED 只提供近三年,2008 的對照改用 Baa 公司債利差"),
        ("wn", "這是歷史對照,不是預測,也不是買賣建議")]), extra_cls="risk")

    html = shell(
        title_html="金融海嘯<b>對照</b>:接下來一年會不會像 2008?",
        subtitle=(f"2008 是信用市場先出事,現在那些數字沒有動;比較像的是 2000 年科技泡沫,而它用信用指標排除不了。"
                  f"歷史上 {len(past)} 次跌破 20%,一年後 {len(up)} 次更高、{len(past) - len(up)} 次更低"),
        brand="2008 複習",
        cols=[c_path + c_time + c_less, c_now + c_eps + c_nsf + c_lv, c_scn + c_ind + c_cmp + c_risk],
        footer=(f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:加權指數(yfinance ^TWII+系統 benchmark)、FRED(BAA10Y、NFCI、VIXCLS、UNRATE、DFF)、"
                "系統月營收與融資維持率、TechNews 國安基金整理 · 歷史對照,非預測、非投資建議"))
    p = save_poster("金融海嘯對照", date, html)
    return str(p)


if __name__ == "__main__":
    print(main())

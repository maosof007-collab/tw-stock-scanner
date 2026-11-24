# -*- coding: utf-8 -*-
"""主題海報:內部人把股票拿去質押,是看好嗎?之後多久才發動?(2026-11-18)
全部數字由 insider_pledge 重算(全市場 2015 年起、自然人本人「首次質押」事件),沒有手寫的統計。
手動:python -X utf8 make_poster_pledge.py      (加 --refresh 重抓今年和去年的公告,約 10 秒)"""
import sys
import warnings

import numpy as np
import pandas as pd

import insider_pledge as ip
from poster import bignums, card, checks, hbars, save_poster, shell_flow
from poster import row as prow
from twtime import now_tw

NAMED = ["3661", "2330", "4566"]          # 使用者點名的:世芯-KY、台積電;加上起因的時碩
HN = {"3m": "3 個月", "6m": "6 個月", "12m": "12 個月", "24m": "24 個月"}


def pc(x, sign=True) -> str:
    if x is None or pd.isna(x):
        return "—"
    c = "rd" if x > 0 else "gn" if x < 0 else ""
    return f'<span class="{c}">{x * 100:+.0f}%</span>' if sign else f"{x * 100:.0f}%"


def mo(x) -> str:
    return "還沒到" if pd.isna(x) else f"{x:.0f} 個月" if x >= 1 else "不到 1 個月"


def ev_table(g: pd.DataFrame) -> str:
    t = ("<table><tr><th>申報日</th><th>公司</th><th>誰</th><th>質押</th><th>12 個月</th><th>24 個月</th>"
         "<th>漲到 +50%</th><th>那之前最深</th></tr>")
    for r in g.itertuples():
        t += (f'<tr><td class="n">{r.filed:%Y/%m/%d}</td><td>{r.name}<br><small>{r.code}</small></td>'
              f"<td>{r.who}<br><small>{r.role.replace('本人', '')}</small></td>"
              f'<td class="n">{r.lots:,.0f} 張<br><small>{r.value / 1e8:.1f} 億</small></td>'
              f'<td class="n">{pc(r.r_12m)}</td><td class="n">{pc(r.r_24m)}</td>'
              f'<td class="n">{mo(r.hit_m)}</td><td class="n">{pc(r.dd)}</td></tr>')
    return t + "</table>"


def main(refresh: bool = False) -> str:
    warnings.filterwarnings("ignore")
    raw = ip.fetch(refresh=refresh)
    d = ip.load(raw)
    px = ip.closes()
    s = ip.study(ip.events(d[d.self], px), px)
    o = ip.summary(s)
    date = now_tw().strftime("%Y%m%d")
    span = f"{s.t0.min():%Y/%m}~{s.t0.max():%Y/%m}"
    v12 = s.dropna(subset=["r_12m"])

    # ── 各期間 ──
    t1 = ("<table><tr><th>之後</th><th>質押事件<br>中位數</th><th>同一天<br>一般股票</th><th>差距</th>"
          "<th>贏過一般<br>股票的比例</th><th>上漲的<br>比例</th><th>筆數</th></tr>")
    for nm in ip.H:
        t1 += (f'<tr{" class=yl" if nm == "12m" else ""}><td>{HN[nm]}</td><td class="n">{pc(o[f"r_{nm}"])}</td>'
               f'<td class="n">{pc(o[f"b_{nm}"])}</td><td class="n">{pc(o[f"x_{nm}"])}</td>'
               f'<td class="n">{pc(o[f"win_{nm}"], False)}</td><td class="n">{pc(o[f"up_{nm}"], False)}</td>'
               f'<td class="n">{o[f"n_{nm}"]}</td></tr>')
    t1 += "</table>"
    q = v12.r_12m.quantile([.1, .25, .75, .9]).values
    rng = np.random.default_rng(0)                              # 12 個月差距中位數的 95% 區間(重抽 2,000 次)
    ci = np.percentile([np.median(rng.choice(v12.x_12m.values, len(v12))) for _ in range(2000)], [2.5, 97.5])
    ci_txt = "整段都在 0 以下" if ci[1] < 0 else "整段都在 0 以上" if ci[0] > 0 else "跨過 0,不能說有差"
    c_ret = card("📊 質押之後的報酬", t1
                 + f'<div class="note">「一般股票」= 同一天全市場個股往後同樣期間的報酬中位數;「差距」是每個事件各自減掉對照後取中位數。'
                   f"12 個月差距的 95% 區間是 {ci[0] * 100:+.0f}% ~ {ci[1] * 100:+.0f}%(重抽 2,000 次),{ci_txt}。"
                   f"12 個月報酬:最差一成 {q[0] * 100:+.0f}% 以下、四分之一在 {q[1] * 100:+.0f}% 以下、四分之一在 {q[2] * 100:+.0f}% 以上、"
                   f"最好一成 {q[3] * 100:+.0f}% 以上;<b>平均 {v12.r_12m.mean() * 100:+.0f}%</b> 比中位數高很多,是少數大漲的拉上去的。</div>",
                 f"{len(s)} 個事件")

    # ── 多久才發動 ──
    c_hit = card("⏱ 多久才發動(收盤第一次漲到 +50%)", "<table>"
                 f'<tr><td>12 個月內漲到 +50%</td><td class="n">{pc(o["hit12"], False)}</td></tr>'
                 f'<tr class=yl><td>24 個月內漲到 +50%</td><td class="n">{pc(o["hit24"], False)}</td></tr>'
                 f'<tr><td>同一天一般股票,24 個月內漲到 +50%</td><td class="n">{pc(o["b_hit24"], False)}</td></tr>'
                 f'<tr class=yl><td><b>一半的事件漲到 +50% 要多久</b></td><td class="n"><b>{mo(o["km"])}</b></td></tr>'
                 f'<tr><td>有漲到的那些,中位數花多久</td><td class="n">{mo(o["hit_med"])}</td></tr>'
                 f'<tr><td>漲到之前(最多看 24 個月)最深跌幅,中位數</td><td class="n">{pc(o["dd"])}</td></tr></table>'
                 f'<div class="note">比例只算觀察滿 24 個月的 {o["n_full"]} 個事件。「一半要多久」把還沒漲到的也算進去'
                 "(Kaplan–Meier),所以比「有漲到的中位數」長。</div>")

    # ── 分組 ──
    groups = [(k, s[s.grp == k]) for k in ("董事長、總經理", "董事、監察人", "大股東", "其他經理人")]
    groups += [("質權人是證券商、證金", s[s.lend == "證券商、證金"]), ("質權人是銀行等", s[s.lend != "證券商、證金"]),
               ("質押前 12 個月股價漲", s[s.pre > 0]), ("質押前 12 個月股價跌", s[s.pre <= 0]),
               ("質押金額 3 億以上", s[s.value >= 3e8]), ("質押金額 1 億以下", s[s.value < 1e8])]
    t3 = ("<table><tr><th>分組</th><th>筆數</th><th>12 個月<br>中位數</th><th>和一般<br>股票差</th><th>贏的<br>比例</th>"
          "<th>24 個月內<br>+50%</th><th>一半要<br>多久</th></tr>")
    gs = {}
    for k, g in groups:
        gs[k] = x = ip.summary(g)
        t3 += (f'<tr><td>{k}</td><td class="n">{x["n"]}</td><td class="n">{pc(x["r_12m"])}</td><td class="n">{pc(x["x_12m"])}</td>'
               f'<td class="n">{pc(x["win_12m"], False)}</td><td class="n">{pc(x["hit24"], False)}'
               f'<small>(對照 {pc(x["b_hit24"], False)})</small></td><td class="n">{mo(x["km"])}</td></tr>')
    t3 += "</table>"
    c_grp = card("👥 分組看", t3 + '<div class="note">「其他經理人」是副總、協理、財會主管等。筆數少的組(幾十筆)差幾個百分點不代表什麼。</div>')

    # ── 例子 ──
    cols = ["filed", "code", "name", "who", "role", "lots", "value", "r_12m", "r_24m", "hit_m", "dd"]
    named = s[s.code.isin(NAMED)].sort_values(["code", "filed"])[cols]
    c_named = card("🗣 你提到的世芯、台積電,和起因的時碩", ev_table(named)
                   + '<div class="note">同一家公司 12 個月內只取第一筆,所以世芯 2025/7 總經理林志堅那筆(在副總張政淵之後兩個月)沒有另外列。</div>')
    full = s[s.obs_m >= 24]
    c_big = card("💰 質押金額最大的 10 個", ev_table(full.sort_values("value", ascending=False).head(10)[cols])
                 + '<div class="note">只照金額排、不看結果挑,而且都已經觀察滿 24 個月。</div>')
    c_best = card("🚀 12 個月漲最多的 10 個", ev_table(v12.sort_values("r_12m", ascending=False).head(10)[cols]))
    c_worst = card("💥 12 個月跌最多的 10 個", ev_table(v12.sort_values("r_12m").head(10)[cols]), extra_cls="risk")

    # ── 結論(數字全部取自上面的統計) ──
    ceo, mgr, bigh = gs["董事長、總經理"], gs["其他經理人"], gs["大股東"]
    me = s[(s.code == "4566") & (s.who == "丁凌全")]
    concl = [
        ("xx", f"<b>質押本身不是看好的訊號</b>:{len(s)} 個事件,質押後 12 個月報酬中位數 {pc(o['r_12m'])},"
               f"同一天的一般股票是 {pc(o['b_12m'])};贏過一般股票的只有 {pc(o['win_12m'], False)}"),
        ("xx", f"<b>董事長、總經理本人質押的最差</b>({ceo['n']} 筆):12 個月中位數 {pc(ceo['r_12m'])},"
               f"比一般股票少 {abs(ceo['x_12m']) * 100:.0f} 個百分點,贏的比例 {pc(ceo['win_12m'], False)}"),
        ("wn", f"<b>多久才發動</b>:24 個月內漲到 +50% 的有 {pc(o['hit24'], False)},一般股票同期是 {pc(o['b_hit24'], False)}——沒有比較快。"
               f"一半的事件要等 {mo(o['km'])};有漲到的那些,中位數是 {mo(o['hit_med'])}"),
        ("wn", f"<b>等的過程不好受</b>:漲到 +50% 之前(或 24 個月內)最深跌幅的中位數是 {pc(o['dd'])};"
               f"12 個月內跌超過 30% 的有 {pc((v12.r_12m <= -0.3).mean(), False)},漲超過 50% 的有 {pc((v12.r_12m >= 0.5).mean(), False)}"),
        ("ok", f"<b>你記得的世芯、台積電,屬於結果最好的那一組</b>:副總這類經理人質押({mgr['n']} 筆),"
               f"24 個月報酬中位數 {pc(mgr['r_24m'])}、贏過一般股票的比例 {pc(mgr['win_24m'], False)}。筆數少,而且會被記得的本來就是後來大漲的"),
        ("wn", f"<b>大股東本人質押</b>({bigh['n']} 筆,時碩丁凌全這一類):12 個月中位數 {pc(bigh['r_12m'])},"
               f"24 個月內漲到 +50% 的 {pc(bigh['hit24'], False)},一半要等 {mo(bigh['km'])}"
               + (f"。丁凌全 2021/1 首次質押後 12 個月 {pc(me.r_12m.iloc[0])},{mo(me.hit_m.iloc[0])}後才漲到 +50%" if len(me) else "")),
    ]
    c_concl = card("📌 結論", checks(concl))
    c_big4 = card("🔢 四個數字", bignums([
        ("事件數", f"{len(s):,}", span),
        ("12 個月報酬中位數", f"{o['r_12m'] * 100:+.0f}%", f"一般股票 {o['b_12m'] * 100:+.0f}%"),
        ("贏過一般股票", f"{o['win_12m'] * 100:.0f}%", "12 個月"),
        ("一半漲到 +50%", mo(o["km"]).replace(" 個月", "個月"), f"24 個月內 {o['hit24'] * 100:.0f}%")]))
    lost = d[d.self & (d.pledge > 0) & ~d.code.isin(px.columns)].code.nunique()
    c_how = card("📏 怎麼算的", checks([
        ("ok", f"來源:公開資訊觀測站「內部人設質解質彙總公告」,上市+上櫃 2014 年起逐筆原始申報,共 {len(d):,} 筆"),
        ("ok", "事件:自然人本人「累積設質從 0 變成有」(第一次質押,或全部解質後再押),當次 100 張以上且市值 3,000 萬以上;"
               "同一家公司 12 個月內只取第一筆"),
        ("ok", "進場價:申報日之後第一個交易日的收盤(公告出來、看得到的那一天);報酬用還原價,表上的質押金額也用還原價估,早年的會偏低"),
        ("ok", "對照:同一天全市場每一檔個股往後同樣期間的報酬,取中位數")]))
    c_risk = card("⚠️ 限制", checks([
        ("wn", f"股價檔沒有已下市的公司,這類事件被丟掉了(有質押紀錄但沒股價的公司 {lost} 家)——質押後出事下市的不在裡面,實際結果只會更差"),
        ("wn", "公告不寫質押的用途(買股、繳稅、周轉都有),也不寫借款成數與追繳價位"),
        ("wn", "只看「首次質押」。像時碩那樣已經押了又繼續加押的,這裡只算最早那一筆"),
        ("wn", "事件集中在某些年份時彼此不獨立(同一段行情),贏的比例差幾個百分點不要當成定論"),
        ("wn", "研究筆記,不是買賣建議")]), extra_cls="risk")

    # 事件研究類:主角=事件之後的走勢(這裡是各期間報酬中位數,質押事件對一般股票)
    c_hero = card("📊 質押之後,和一般股票比(報酬中位數)",
                  '<div class="lgd"><span><i style="background:#27303b"></i>內部人首次質押的股票</span>'
                  '<span><i style="background:#e07b00"></i>同一天的一般股票</span><span>灰色=負值</span></div>'
                  + hbars([x for nm in ("3m", "6m", "12m", "24m") for x in
                           ((HN[nm], round(o[f"r_{nm}"] * 100, 1), "#27303b"), ("", round(o[f"b_{nm}"] * 100, 1), "#e07b00"))]),
                  src="事件=自然人內部人累積設質從 0 變成有;進場價=申報日後第一個交易日收盤;一般股票=同一天全市場個股同期間報酬的中位數")
    html = shell_flow(
        title_html="內部人<b>質押</b>之後,股價多久才動?",
        subtitle=f"全市場 {len(s):,} 個自然人內部人首次質押事件({span}):12 個月報酬中位數 {o['r_12m'] * 100:+.0f}%、"
                 f"一般股票 {o['b_12m'] * 100:+.0f}%;一半的事件要 {mo(o['km'])}才漲到 +50%——質押不是看好的訊號",
        brand="內部人質押",
        blocks=[("wide", prow([c_hero, c_big4 + c_concl], "12")), c_ret, c_hit, c_grp, c_named, c_big, c_best, c_worst, c_how, c_risk],
        kind="event",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:公開資訊觀測站內部人設質解質彙總公告(2014 年起)、系統還原股價 · 研究筆記,非投資建議")
    return str(save_poster("內部人質押", date, html))


if __name__ == "__main__":
    print(main(refresh="--refresh" in sys.argv))

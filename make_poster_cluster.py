# -*- coding: utf-8 -*-
"""族群海報:族群強弱 — 不靠手寫族群,用官方產業別+theme_groups 算今天誰逆勢、誰最弱。
數字讀當下的日線即時算(sector_cluster.py);每日流程自動重產,只留最新一份。
手動重跑:python -X utf8 make_poster_cluster.py"""
import json

import pandas as pd

import sector_cluster as sc
from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

PAPERS = sc.D / "papers"
# 2026-11-09 起的限空措施(查證日 11/16);解除後把這行清空
SHORT_RULE = ("●放空有限制:11/9 起借券賣出上限從日均量 30% 降到 3%、融券保證金 90%→130%;"
              "沒有禁止平盤下放空,期限未定(查證日 11/16)")


def t_strong(df) -> str:
    out = '<table><tr><th>產業</th><th>今日</th><th>收紅比</th><th>創 20 日高</th><th>5 日領先</th></tr>'
    for k, x in df.iterrows():
        out += (f'<tr><td><b>{k}</b><br><small>{int(x.n)} 檔、20 日 {x.r20:+.0f}%</small></td>'
                f'<td class="n">{ud(x.d1, f"{x.d1:+.1f}%")}</td><td class="n">{x.up:.0f}%</td>'
                f'<td class="n">{x.nh:.0f}%<br><small>近 5 日 {int(x.top3)} 天前三</small></td>'
                f'<td><small>{x["names"]}</small></td></tr>')
    return out + "</table>"


def t_weak(df) -> str:
    out = '<table><tr><th>族群</th><th>今日</th><th>跌停比</th><th>創 20 日低</th><th>20 日最弱</th></tr>'
    for k, x in df.iterrows():
        out += (f'<tr><td><b>{k}</b><br><small>{int(x.n)} 檔、20 日 {x.r20:+.0f}%</small></td>'
                f'<td class="n">{ud(x.d1, f"{x.d1:+.1f}%")}</td><td class="n">{x.ld:.0f}%</td>'
                f'<td class="n">{x.lo:.0f}%<br><small>破季線 {x.ma:.0f}%</small></td>'
                f'<td><small>{x["names"]}</small></td></tr>')
    return out + "</table>"


def main(res: dict | None = None) -> str:
    res = res or sc.compute()
    ctx, strong, alerts = res["ctx"], res["strong"], res["alerts"]
    P, sec, nm, bm = ctx["P"], ctx["sec"], ctx["nm"], ctx["bm"]
    date = now_tw().strftime("%Y%m%d")
    md = f"{int(ctx['last'][5:7])}/{int(ctx['last'][8:10])}"
    d1 = ctx["r1"].iloc[-1]
    bm1, bm20 = (bm.iloc[-1] / bm.iloc[-2] - 1) * 100, (bm.iloc[-1] / bm.iloc[-21] - 1) * 100
    n_up, n_all, n_ld = int((d1 > 0).sum()), P.shape[1], int((d1 <= -9.5).sum())
    below = ctx["below"].iloc[-1].mean() * 100
    rising = strong[(strong.r20 > 0) & (strong.nh >= sc.NH_MIN)]
    weak_thm, weak_off = res["weak_thm"], res["weak_off"]
    try:
        lamp = json.load(open(sc.D / "_market_risk.json", encoding="utf-8"))
        lamp_s = f"大盤燈號 {lamp['lamp']}({lamp['rule']})"
    except Exception:
        lamp_s = "大盤燈號讀不到"

    c_num = card(f"{md} 收盤:{n_all} 檔(20 日均額 ≥0.2 億)", bignums([
        ("收紅", f"{n_up}", f"占 {n_up / n_all * 100:.0f}%"),
        ("跌幅 ≥9.5%", f"{n_ld}", f"占 {n_ld / n_all * 100:.0f}%"),
        ("破季線", f"{below:.0f}%", f"大盤今日 {bm1:+.2f}%、20 日 {bm20:+.1f}%"),
    ]))

    if alerts:
        al = "".join(f'<tr><td><b>{a["group"]}</b><br><small>{a["n"]} 檔、今日 {a["d1"]:+.1f}%</small></td>'
                     f'<td>{"<br>".join(a["rules"])}</td><td><small>{a["att_names"] or a["names"]}</small></td></tr>'
                     for a in alerts)
        al = f'<table><tr><th>產業</th><th>亮燈原因</th><th>上榜/領先個股</th></tr>{al}</table>'
    else:
        al = '<div class="note">今天沒有產業亮燈。</div>'
    att_note = "" if res["att_day"] == ctx["last"] else f'(注意力榜只到 {res["att_day"] or "無資料"},規則 A 用的是那天)'
    c_alert = card(f"🧲 聚集亮燈({len(alerts)} 個產業)", al
                   + f'<div class="note">規則:A 注意力榜前 20 名同一產業 ≥{sc.ATT_MIN} 檔且是產業比重的 {sc.ATT_LIFT:.0f} 倍以上;'
                     f'B 創 20 日新高比例連 {sc.STREAK} 天全市場第一且 ≥{sc.NH_MIN:.0f}%。{att_note}'
                     '出現新的亮燈產業才會推播。</div>')

    L = []
    if len(rising):
        k, x = rising.index[0], rising.iloc[0]
        L.append(("ok", f"<b>在漲的族群 {len(rising)} 個,最強 {k}</b>:今日中位數 {x.d1:+.1f}%(大盤 {bm1:+.2f}%)、"
                        f"{x.up:.0f}% 收紅、{x.nh:.0f}% 創 20 日新高、20 日 {x.r20:+.0f}%"))
        rest = strong.drop(rising.index).head(4)
    else:
        L.append(("xx", f"<b>沒有在漲的族群</b>:沒有任何產業同時符合「20 日中位數為正、創高比例 ≥{sc.NH_MIN:.0f}%」"))
        rest = strong.head(4)
    L.append(("wn", f"排在後面的 {'、'.join(rest.index)}:創高比例 {rest.nh.min():.0f}~{rest.nh.max():.0f}%、"
                    f"20 日中位數 {rest.r20.min():+.0f}~{rest.r20.max():+.0f}%——20 日是負的就只是跌得少,不是在漲"))
    if len(weak_thm):
        w = weak_thm.head(3)
        L.append(("xx", f"最弱的手寫族群:{'、'.join(w.index)}——創 20 日新低比例 {w.lo.min():.0f}~{w.lo.max():.0f}%、"
                        f"20 日 {w.r20.min():+.0f}~{w.r20.max():+.0f}%"))
    if SHORT_RULE:
        L.append(("wn", SHORT_RULE))
    L.append(("xx", f"{lamp_s};系統的空方規則 S1 是「套牢池反彈爆量收黑才空」,不是破底追空"))
    c_concl = card("結論(重點先看)", checks(L), src="●=開過原文;其餘為系統即時計算", extra_cls="grow")

    c_strong = card("逆勢:官方產業依「創 20 日新高比例」排序", t_strong(strong.head(8)))
    both = res["both_up"]
    if both:
        by = pd.Series({c: sec[c] for c in both})
        rows = "".join(f"<tr><td><b>{k}</b></td><td>{'、'.join(nm[c] for c in v.index)}</td></tr>"
                       for k, v in by.groupby(by))
        c_both = card(f"近 20 日的崩盤日({'、'.join(d[5:].replace('-', '/') for d in res['crash_days'])})都收紅的 {len(both)} 檔",
                      f"<table><tr><th>產業</th><th>個股</th></tr>{rows}</table>"
                      '<div class="note">崩盤日=大盤單日跌 ≥4%。每次大跌都有人買的名單。</div>')
    else:
        c_both = ""

    c_weak_t = card("最弱:手寫族群依「創 20 日新低比例」排序", t_weak(weak_thm.head(10))) if len(weak_thm) else ""
    c_weak_o = card("最弱:官方產業", t_weak(weak_off.head(6)))
    c_read = card("讀這張表要注意", checks([
        ("wn", "這是價格廣度,不含法人與融資;也不知道「為什麼」,題材要另外查"),
        ("wn", "官方產業很粗(半導體一類就一百多檔),細題材會被平均掉;手寫族群只有 30 個,新題材不在裡面"),
        ("wn", "亮燈代表「這一群在聚集」,不代表可以進場:爆量後禁入、大盤燈號等家規照舊"),
        ("ok", "每日收盤流程自動重產,只留最新一份;算法在 sector_cluster.py"),
    ]), extra_cls="risk grow")

    head = (f"在漲的只有{rising.index[0]}" if len(rising) == 1 else
            f"在漲的有{'、'.join(rising.index[:3])}" if len(rising) else "沒有在漲的族群")
    tail = f";最弱是{'、'.join(weak_thm.index[:3])}" if len(weak_thm) else ""
    html = shell(
        title_html="族群<b>強弱</b>總覽",
        subtitle=f"{md} 大盤 {bm1:+.2f}%:{head}{tail}",
        brand="族群雷達",
        cols=[c_num + c_alert + c_concl, c_strong + c_both, c_weak_t + c_weak_o + c_read],
        footer=f"素材:系統 {date[:4]}/{date[4:6]}/{date[6:]} 日線即時計算(sector_cluster.py) · 本海報為研究筆記非投資建議")
    for old in PAPERS.glob("族群強弱海報_*.html"):          # 每日重產,只留最新一份;先刪再存,總覽才不會連到被刪的檔
        if old.name != f"族群強弱海報_{date}.html":
            old.unlink()
    return str(save_poster("族群強弱", date, html))


if __name__ == "__main__":
    print("saved:", main())

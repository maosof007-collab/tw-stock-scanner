# -*- coding: utf-8 -*-
"""族群海報:崩盤錯殺那一批的現況 — 策略「崩盤錯殺V轉(收復失土)」最新事件的候選,現在還站不站得住。
每次執行都重跑 scripts/crash_scan.py、scripts/crash_rank.py(讀當下的日線),查證筆記讀 crash_notes_1116*.py。"""
import glob
import json
import subprocess
import sys

import pandas as pd

from crash_notes_1116 import NOTES
from crash_notes_1116b import NOTES_B
from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

DATE = now_tw().strftime("%Y%m%d")
CANDS, RANKED = "data/_crash_cands.csv", "data/_crash_ranked.csv"
for script, args in (("scripts/crash_scan.py", [CANDS]), ("scripts/crash_rank.py", [CANDS, RANKED])):
    subprocess.run([sys.executable, "-X", "utf8", script, *args], check=True, stdout=subprocess.DEVNULL)

N = {**NOTES, **NOTES_B}
# 查證後的分類(2026-11-16 逐檔上網查):有沒有個股自己的利空
OWN_BAD = {"3006": "10 月營收連兩個月月減", "6456": "11/6 盤後公布 Q3 每股虧 2.17"}
WEAK = {"6715": "前三季 EPS 1.12", "2340": "還在虧損", "6742": "還在虧損", "3311": "營收暴增是併表"}

c0 = pd.read_csv(CANDS, dtype={"code": str})
r = pd.read_csv(RANKED, dtype={"code": str, "代碼": str}).drop(columns=["hit"])
r = r.merge(c0[["code", "E", "hit", "last_date", "vol20"]], on="code", how="left")
r["hit_day"] = r.hit.where(r.hit.notna(), "")
r["hit"] = r.hit.notna()


def d1(code) -> float:
    d = pd.read_csv(glob.glob(f"data/{code}.TW*.csv")[0]).dropna(subset=["Close"]).tail(2)
    return (d.Close.iloc[-1] / d.Close.iloc[-2] - 1) * 100


r["d1"] = r.code.map(d1)
LAST = r.last_date.max()
MD = f"{int(LAST[:2])}/{int(LAST[3:5])}"
EV = r.E.iloc[0]
bm = pd.read_csv("data/benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
BM1 = (bm.iloc[-1] / bm.iloc[-2] - 1) * 100
BM2 = (bm.iloc[-1] / bm.iloc[-3] - 1) * 100
NEXT_LINE = bm.iloc[-2] * 0.95          # 下個交易日收在這之下 → 兩日跌幅 ≥5%,成為新事件
risk = json.load(open("data/_market_risk.json", encoding="utf-8"))

alive = r[r.hit & (r.gap > 0)].sort_values("總分", ascending=False)
fell = r[r.hit & (r.gap <= 0)]
never = r[~r.hit]
n_all, n_hit = len(r), int(r.hit.sum())


def tag(x) -> str:
    t = []
    if bool(x["爆量窗"]):
        t.append("爆量窗")
    if float(x["融資%"]) >= 30:
        t.append(f'融資 {float(x["融資%"]):.0f}%')
    if x.code in OWN_BAD:
        t.append("有個股利空")
    if x.code in WEAK:
        t.append("基本面弱")
    return "、".join(t) or "—"


def rows(df) -> str:
    out = '<table><tr><th>公司</th><th>跌前價→收盤</th><th>今日</th><th>總分</th><th>註記</th></tr>'
    for _, x in df.iterrows():
        out += (f'<tr><td><b>{x["名稱"]}</b> {x.code}</td>'
                f'<td class="n">{x.ref:g}→{x["收盤"]:g}<br><small>{x.gap:+.1f}%</small></td>'
                f'<td class="n">{ud(round(x.d1, 1), f"{x.d1:+.1f}%")}</td>'
                f'<td class="n">{x["總分"]:.0f}</td><td><small>{tag(x)}</small></td></tr>')
    return out + "</table>"


c_num = card(f"{EV} 事件的 {n_all} 檔,到 {MD} 收盤", bignums([
    ("曾收復跌前價", f"{n_hit}", f"占 {n_hit / n_all * 100:.0f}%"),
    ("現在還站在上面", f"{len(alive)}", f"{MD} 一天少了 {len(fell)} 檔"),
    (f"{MD} 中位數", f"{r.d1.median():+.1f}%", f"大盤 {BM1:+.2f}%"),
]) + f'<div class="note">母體:大盤兩日跌 ≥5% 的事件日({EV}),同兩日個股跌 ≥10%、20 日均量 ≥500 張。'
     f'{MD} 跌幅 ≥9.5% 的有 {int((r.d1 <= -9.5).sum())} 檔,收紅 {int((r.d1 > 0).sum())} 檔。</div>')

c_concl = card("結論(重點先看)", checks([
    ("xx", f"<b>收復的大多守不住</b>:{n_hit} 檔曾收復跌前價,{MD} 收盤只剩 <b>{len(alive)} 檔</b>還在上面,"
           f"{len(fell)} 檔又跌破"),
    ("xx", f"這一批是 {MD} 被賣最兇的:中位數 {r.d1.median():+.1f}%,大盤 {BM1:+.2f}%——"
           "跌深反彈最快的,第二次殺的時候也跌最多"),
    ("wn", f"{MD} <b>還不算新事件</b>:大盤兩日 {BM2:+.2f}%,沒到 −5%。下一個交易日若收在 "
           f"<b>{NEXT_LINE:,.0f}</b> 以下就會成立,跌前價改用 {MD} 前一日收盤,整份名單重算"),
    ("xx", f"大盤燈號 {risk['lamp']}:{risk['rule']}"),
    ("wn", "系統評分只看營收、獲利、籌碼、位置,<b>看不出個股自己有沒有利空</b>——右邊那張表是逐檔上網查的"),
    ("ok", "策略規則是「收復跌前價才進場」,不是跌深就接;今天又跌破的那些,規則上等下一次收復"),
]), src="策略:strategies/crash_recovery.py", extra_cls="grow")

top = alive[alive.amt20 >= 0.5]
c_alive = card(f"還站在跌前價之上({len(alive)} 檔;列 20 日均額 ≥0.5 億的 {len(top)} 檔)", rows(top)
               + '<div class="note">總分=營收 30%+獲利 30%+籌碼 25%+位置 15%−扣分(處置、爆量窗、融資 ≥30%、迴轉警)。'
                 '排名是體檢,不是買單。</div>')

res = r[r.code.isin(N)].sort_values("總分", ascending=False)


def status(x) -> str:
    if x.hit and x.gap > 0:
        return "還站著"
    return "又跌破" if x.hit else "沒收復過"


def news_rows(df) -> str:
    out = '<table><tr><th>公司</th><th>現況</th><th>查證結果</th></tr>'
    for _, x in df.iterrows():
        if x.code in OWN_BAD:
            v = f'<span class="bd">有自己的利空</span>:{OWN_BAD[x.code]}'
        elif x.code in WEAK:
            v = f'基本面本來就弱:{WEAK[x.code]}'
        else:
            v = "查無個股利空,跌勢和大盤同步"
        out += (f'<tr><td><b>{x["名稱"]}</b> {x.code}</td>'
                f'<td>{status(x)}<br><small>{x.gap:+.1f}%、今日 {x.d1:+.1f}%</small></td><td><small>{v}</small></td></tr>')
    return out + "</table>"


c_news = card(f"逐檔查過的 {len(res)} 檔:跌是不是只因為大盤", news_rows(res)
              + '<div class="note">查證日 2026/11/16,來源多為法說整理稿與媒體,不是簡報原檔。'
                '這 17 檔是 11/13 資料下「已收復、均額 ≥0.5 億、總分 ≥65」的名單,加上弘憶股。</div>')

c_fell = card(f"收復後又跌破的 {len(fell)} 檔(總分前 12)",
              rows(fell.sort_values("總分", ascending=False).head(12)))

c_read = card("讀這張表要注意", checks([
    ("wn", f"價格是 {MD} 收盤;籌碼分用的法人與融資資料是前一個交易日(盤後才公布)"),
    ("wn", "「查無個股利空」只代表我沒查到,不代表沒有"),
    ("wn", "瀧澤科是 CNC 車床廠,不是 PCB 設備;閎暉的營收成長來自併入 FDK"),
    ("ok", "單張海報:弘憶股、台玻、愛普在同一個選單裡"),
]), extra_cls="risk grow")

html = shell(
    title_html=f"崩盤錯殺<b>{EV} 那一批</b>現況",
    subtitle=f"{n_hit} 檔曾收復跌前價,{MD} 一天之內 {len(fell)} 檔又跌破——還站著的剩 {len(alive)} 檔",
    brand="錯殺 V 轉",
    cols=[c_num + c_concl, c_alive, c_news + c_fell + c_read],
    footer=f"素材:系統 {DATE[:4]}/{DATE[4:6]}/{DATE[6:]} 日線+策略回測規則+逐檔上網查證 · 本海報為研究筆記非投資建議")
print("saved:", save_poster("錯殺", DATE, html))

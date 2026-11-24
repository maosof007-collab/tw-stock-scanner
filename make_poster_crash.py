# -*- coding: utf-8 -*-
"""族群海報:崩盤錯殺的現況 — 策略「崩盤錯殺V轉(收復失土)」最新事件那一批收復了沒,加上前一批現在還站不站得住。
每次執行都重跑 scripts/crash_scan.py、scripts/crash_rank.py(讀當下的日線),事件日自動抓最新的;
查證筆記讀 crash_notes_1116*.py(2026-11-16 查的,對象是 11/06 那一批)。"""
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
CANDS, UNIQ, RANKED = "data/_crash_cands.csv", "data/_crash_cands_uniq.csv", "data/_crash_ranked.csv"
WINDOW = 10                 # 事件後幾個交易日內收復才算(同 scripts/crash_scan.py)
NOTE_EV = "2026-11-06"      # 查證筆記對應的事件
NEAR_N = 12


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, "-X", "utf8", script, *args], check=True, stdout=subprocess.DEVNULL)


def d1(code: str) -> float:
    d = pd.read_csv(glob.glob(f"data/{code}.TW*.csv")[0]).dropna(subset=["Close"]).tail(2)
    return (d.Close.iloc[-1] / d.Close.iloc[-2] - 1) * 100


run("scripts/crash_scan.py", CANDS)
c0 = pd.read_csv(CANDS, dtype={"code": str, "hit": str}).fillna({"hit": ""})
c0 = c0[c0.vol20 >= 500]
if c0.empty:
    raise SystemExit("沒有候選(20 日均量 ≥500 張的一檔都沒有),不產生海報")
# 同一檔會出現在好幾個事件;評分只跟個股有關,每檔算一次
c0.sort_values("Ed").drop_duplicates("code", keep="last").to_csv(UNIQ, index=False, encoding="utf-8-sig")
run("scripts/crash_rank.py", UNIQ, RANKED)
sc = pd.read_csv(RANKED, dtype={"code": str})[["code", "總分", "爆量窗", "融資%"]]
sc["融資%"] = pd.to_numeric(sc["融資%"], errors="coerce")
c0 = c0.merge(sc, on="code", how="left")
c0["d1"] = c0.code.map({c: d1(c) for c in c0.code.unique()})
c0["hit_b"] = c0.hit != ""

N = {**NOTES, **NOTES_B}
# 查證後的分類(2026-11-16 逐檔上網查):有沒有個股自己的利空
OWN_BAD = {"3006": "10 月營收連兩個月月減", "6456": "11/6 盤後公布 Q3 每股虧 2.17"}
WEAK = {"6715": "前三季 EPS 1.12", "2340": "還在虧損", "6742": "還在虧損", "3311": "營收暴增是併表"}

bm = pd.read_csv("data/benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
bm2 = bm.pct_change(2) * 100
MD = f"{bm.index[-1].month}/{bm.index[-1].day}"
_SD = c0.last_date.max()                # 個股日線的最後一天(MM/DD)
if (int(_SD[:2]), int(_SD[3:5])) != (bm.index[-1].month, bm.index[-1].day):
    raise SystemExit(f"大盤檔到 {MD}、個股日線到 {_SD},兩邊不是同一天,先把資料更新齊再產生海報")
BM1 = (bm.iloc[-1] / bm.iloc[-2] - 1) * 100
BM2 = float(bm2.iloc[-1])
NEXT_LINE = bm.iloc[-2] * 0.95          # 下個交易日收在這之下 → 兩日跌幅 ≥5%,成為新事件
risk = json.load(open("data/_market_risk.json", encoding="utf-8"))

def universe() -> int:
    """全市場 20 日均量 ≥500 張的檔數(和候選同一個門檻),用來看候選占了多少。"""
    n, listed = 0, set(pd.read_csv("data/stock_list.csv", dtype=str).code)
    for f in glob.glob("data/[0-9][0-9][0-9][0-9].TW*.csv"):
        if f.replace("\\", "/").split("/")[-1][:4] not in listed:
            continue
        v = pd.read_csv(f, usecols=["Volume"]).Volume
        v = v[v > 0]
        n += len(v) >= 80 and v.tail(20).mean() >= 500_000
    return int(n)


UNI = universe()
EDS = sorted(c0.Ed.unique())
cur = c0[c0.Ed == EDS[-1]]
prev = c0[c0.Ed == EDS[-2]] if len(EDS) > 1 else None
EV = cur.E.iloc[0]


def stat(b: pd.DataFrame) -> dict:
    hit = b[b.hit_b]
    return dict(n=len(b), hit=len(hit), alive=int((hit.gap > 0).sum()), fell=int((hit.gap <= 0).sum()),
                gap=float(b.gap.median()), left=int(b.left.median()))


def tag(x) -> str:
    t = []
    if x["爆量窗"] == True:  # noqa: E712  (左併後可能是 NaN)
        t.append("爆量窗")
    if x["融資%"] >= 30:
        t.append(f'融資 {x["融資%"]:.0f}%')
    if x.code in OWN_BAD:
        t.append("有個股利空")
    if x.code in WEAK:
        t.append("基本面弱")
    return "、".join(t) or "—"


def rows(df: pd.DataFrame) -> str:
    out = f'<table><tr><th>公司</th><th>跌前價→收盤</th><th>{MD} 當日</th><th>總分</th><th>註記</th></tr>'
    for _, x in df.iterrows():
        score = "—" if pd.isna(x["總分"]) else f'{x["總分"]:.0f}'
        out += (f'<tr><td><b>{x["name"]}</b> {x.code}</td>'
                f'<td class="n">{x.ref:g}→{x["last"]:g}<br><small>{x.gap:+.1f}%</small></td>'
                f'<td class="n">{ud(round(x.d1, 1), f"{x.d1:+.1f}%")}</td>'
                f'<td class="n">{score}</td><td><small>{tag(x)}</small></td></tr>')
    return out + "</table>"


s = stat(cur)
passed = WINDOW - s["left"]
alive = cur[cur.hit_b & (cur.gap > 0)].sort_values("總分", ascending=False)
wait = cur[~cur.hit_b]

WHEN = "事件當天,收復從下一個交易日起算" if passed == 0 else f"事件後第 {passed} 個交易日"
c_num = card(f"{EV} 事件的 {s['n']} 檔,到 {MD} 收盤({WHEN})", bignums([
    ("曾收復跌前價", f"{s['hit']}", f"占 {s['hit'] / s['n'] * 100:.0f}%"),
    ("現在還站在上面", f"{s['alive']}", f"收復後又跌破 {s['fell']} 檔"),
    ("離跌前價(中位數)", f"{s['gap']:+.1f}%", f"{MD} 當日 {cur.d1.median():+.1f}%,大盤 {BM1:+.2f}%"),
]) + f'<div class="note">母體:大盤兩日跌 ≥5% 的事件日({EV},兩日 {bm2[EDS[-1]]:+.1f}%),同兩日個股跌 ≥10%、20 日均量 ≥500 張。'
     f'全市場均量過門檻的有 {UNI:,} 檔,這批占 <b>{s["n"] / UNI * 100:.0f}%</b>。跌前價=事件日往前數兩個交易日的收盤。{MD} 跌幅 ≥9.5% 的有 {int((cur.d1 <= -9.5).sum())} 檔,收紅 {int((cur.d1 > 0).sum())} 檔。</div>')

ev_tb = ('<table><tr><th>事件日</th><th>大盤兩日</th><th>候選</th><th>曾收復</th><th>還站著</th>'
         '<th>離跌前價<br>中位數</th><th>收復期限</th></tr>')
for ed in EDS:
    b = c0[c0.Ed == ed]
    t = stat(b)
    ev_tb += (f'<tr><td><b>{b.E.iloc[0]}</b></td><td class="n">{bm2[ed]:+.1f}%</td><td class="n">{t["n"]}</td>'
              f'<td class="n">{t["hit"]}</td><td class="n"><b>{t["alive"]}</b></td><td class="n">{t["gap"]:+.1f}%</td>'
              f'<td>{"剩 " + str(t["left"]) + " 個交易日" if t["left"] > 0 else "已過"}</td></tr>')
c_ev = card("10 月以來的事件,各自那一批現在怎樣", ev_tb + "</table>"
            + f'<div class="note">收復期限=事件後 {WINDOW} 個交易日內收盤站回跌前價才算(策略定義)。數字都是 {MD} 收盤。</div>')

concl = []
share = s["n"] / UNI * 100
if passed == 0:
    concl.append(("xx", f"<b>{EV} 是新的事件日</b>:大盤兩日 {BM2:+.1f}%,同兩日跌 ≥10% 的有 <b>{s['n']} 檔</b>,"
                        f"占全市場均量過門檻個股的 {share:.0f}%;跌前價改用 {bm.index[-3].month}/{bm.index[-3].day} 收盤,"
                        "收復從下一個交易日開始算"))
elif s["hit"] == 0:
    concl.append(("xx", f"<b>{EV} 這一批還沒有任何一檔收復跌前價</b>:{s['n']} 檔,事件後過了 {passed} 個交易日,"
                        f"中位數離跌前價還有 {abs(s['gap']):.1f}%"))
else:
    concl.append(("wn" if s["alive"] else "xx",
                  f"{EV} 這一批 {s['n']} 檔,{s['hit']} 檔曾收復跌前價,{MD} 收盤還站在上面的 <b>{s['alive']} 檔</b>"
                  + (f",{s['fell']} 檔又跌破" if s["fell"] else "")))
if share >= 30:
    concl.append(("wn", f"名單占了全市場的 {share:.0f}%——這已經不是「少數被錯殺」,是整個市場一起跌;名單本身分不出誰被錯殺"))
OLD = [(ed, c0[c0.Ed == ed]) for ed in reversed(EDS[:-1])]          # 更早的每一批,新的在前
for ed, b in OLD:
    p, pe = stat(b), b.E.iloc[0]
    if p["hit"] == 0:
        concl.append(("xx", f"<b>{pe} 那一批一檔都沒收復過</b>:{p['n']} 檔,{MD} 收盤中位數離跌前價 {p['gap']:+.1f}%"
                            + (f",期限剩 {p['left']} 個交易日" if p["left"] > 0 else ",期限已過")))
    else:
        weak = p["alive"] * 2 < p["hit"]
        concl.append(("xx" if weak else "wn",
                      f"<b>{pe} 那一批{'收復的大多守不住' if weak else '的現況'}</b>:{p['n']} 檔裡 {p['hit']} 檔曾收復跌前價,"
                      f"{MD} 收盤{'只剩' if weak else '還有'} <b>{p['alive']} 檔</b>在上面,{p['fell']} 檔又跌破"))
if prev is not None:
    PEV = prev.E.iloc[0]
    n_both = int(prev.code.isin(cur.code).sum())
    again = n_both / len(prev) * 100
    concl.append(("xx" if again > 50 else "wn",
                  f"{PEV} 那一批 {len(prev)} 檔裡有 <b>{n_both} 檔</b>({again:.0f}%)這次又在名單上"
                  + ("——同一群股票,連續兩次都是跌最多的" if again > 50 else "")))
d_prev = f"{bm.index[-2].month}/{bm.index[-2].day}"
room = (NEXT_LINE / bm.iloc[-1] - 1) * 100
how = (f"比 {MD} 收盤再跌 {abs(room):.1f}% 就到" if room < 0
       else f"{MD} 收盤已經在這條線下面 {room:.1f}%,下個交易日沒漲回去就成立")
lead = (f"<b>下一個交易日可能又是新事件</b>" if BM2 <= -5            # 事件當天的說明已經在第一條
        else f"{MD} <b>還不算新事件</b>:大盤兩日 {BM2:+.2f}%,沒到 −5%")
concl.append(("wn", f"{lead}:收在 <b>{NEXT_LINE:,.0f}</b> 以下({how})就會成立,跌前價改用 {d_prev} 收盤,整份名單重算"))
concl += [
    ("xx", f"大盤燈號 {risk['lamp']}:{risk['rule']}"),
    ("wn", "系統評分只看營收、獲利、籌碼、位置,<b>看不出個股自己有沒有利空</b>"),
    ("ok", "策略規則是「收復跌前價才進場」,不是跌深就接;還沒收復、或收復後又跌破的,規則上都是等"),
]
c_concl = card("結論(重點先看)", checks(concl), src="策略:strategies/crash_recovery.py", extra_cls="grow")

NOTE_SCORE = ('<div class="note">總分=營收 30%+獲利 30%+籌碼 25%+位置 15%−扣分(處置、爆量窗、融資 ≥30%、迴轉警),'
              '是這幾批候選之間的相對排名。排名是體檢,不是買單。</div>')
col2 = c_ev
if len(alive):
    top = alive[alive.amt20 >= 0.5]
    col2 += card(f"{EV} 這一批還站在跌前價之上({len(alive)} 檔;列 20 日均額 ≥0.5 億的 {len(top)} 檔)", rows(top) + NOTE_SCORE)
near = wait[wait.amt20 >= 0.5].sort_values("gap", ascending=False)
ttl = (f"{EV} 這一批 {len(wait)} 檔:兩日跌最少的 {min(NEAR_N, len(near))} 檔" if passed == 0
       else f"{EV} 這一批還沒收復的 {len(wait)} 檔:離跌前價最近的 {min(NEAR_N, len(near))} 檔")
col2 += card(ttl, rows(near.head(NEAR_N))
             + f'<div class="note">只列 20 日均額 ≥0.5 億的({len(near)} 檔)裡最接近的,含 ETF;完整名單在 {CANDS}。'
               '離得近只代表跌得少,不代表會收復。</div>' + ("" if len(alive) else NOTE_SCORE))
for ed, b in OLD:
    b_alive = b[b.hit_b & (b.gap > 0)].sort_values("總分", ascending=False)
    col2 += card(f"{b.E.iloc[0]} 那一批還站在跌前價之上的 {len(b_alive)} 檔", rows(b_alive) if len(b_alive) else "一檔都沒有。")

res = c0[(c0.Ed == NOTE_EV) & c0.code.isin(N)].sort_values("gap", ascending=False)


def status(x) -> str:
    if x.hit_b and x.gap > 0:
        return "還站著"
    return "又跌破" if x.hit_b else "沒收復過"


def news_rows(df: pd.DataFrame) -> str:
    out = f'<table><tr><th>公司</th><th>現況(對 {NOTE_EV[5:7]}/{NOTE_EV[8:]} 跌前價)</th><th>11/16 查證結果</th></tr>'
    for _, x in df.iterrows():
        if x.code in OWN_BAD:
            v = f'<span class="bd">有自己的利空</span>:{OWN_BAD[x.code]}'
        elif x.code in WEAK:
            v = f'基本面本來就弱:{WEAK[x.code]}'
        else:
            v = "查無個股利空,跌勢和大盤同步"
        out += (f'<tr><td><b>{x["name"]}</b> {x.code}</td>'
                f'<td>{status(x)}<br><small>{x.gap:+.1f}%、{MD} 當日 {x.d1:+.1f}%</small></td><td><small>{v}</small></td></tr>')
    return out + "</table>"


n_ok = int((res.hit_b & (res.gap > 0)).sum())
c_news = card(f"11/16 逐檔查過的 {len(res)} 檔,現在還站著的 {n_ok} 檔", news_rows(res)
              + '<div class="note">查證日 2026/11/16,之後沒有重查;來源多為法說整理稿與媒體,不是簡報原檔。'
                '這些是 11/13 資料下「已收復、均額 ≥0.5 億、總分 ≥65」的名單,加上弘憶股。</div>')

c_read = card("讀這張表要注意", checks([
    ("wn", f"價格是 {MD} 收盤,不含之後的盤中;籌碼分用的法人與融資資料是前一個交易日(盤後才公布)"),
    ("wn", "「查無個股利空」只代表我 11/16 沒查到,不代表沒有,也不代表之後沒有新的"),
    ("wn", "瀧澤科是 CNC 車床廠,不是 PCB 設備;閎暉的營收成長來自併入 FDK"),
    ("ok", "想看「跌很多但本業還在成長」的另一種篩法,在同一個選單的委屈股海報"),
]), extra_cls="risk grow")

sub = (f"{s['n']} 檔在 {MD} 當天進名單,占全市場 {share:.0f}%" if passed == 0
       else f"{s['n']} 檔到 {MD} 收盤,收復跌前價的 {s['hit']} 檔")
for ed, b in OLD:
    p = stat(b)
    sub += (f";{b.E.iloc[0]} 那批 {p['n']} 檔一檔都沒收復" if p["hit"] == 0
            else f";{b.E.iloc[0]} 那批 {p['hit']} 檔曾收復、還站著的剩 {p['alive']} 檔")
html = shell(
    title_html=f"崩盤錯殺<b>{EV} 那一批</b>現況",
    subtitle=sub,
    brand="錯殺 V 轉",
    cols=[c_num + c_concl, col2, c_news + c_read],
    footer=f"素材:系統日線(到 {MD} 收盤)+策略回測規則+11/16 逐檔上網查證 · 產生於 {DATE[:4]}/{DATE[4:6]}/{DATE[6:]} · 本海報為研究筆記非投資建議")
print("saved:", save_poster("錯殺", DATE, html))

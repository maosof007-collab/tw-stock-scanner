# -*- coding: utf-8 -*-
"""事件研究海報:季節性 + 展覽行事曆——哪些族群在哪個月份常比別人強、2027 年各展覽對應哪些族群、展前展後歷史上怎麼走。
起因:2026-11-24 使用者:「另外一個想法 季節性 有辦法看季節流行的股票 然後明年各個展覽 對應股票族群」。
全部每次重算,只讀本機檔案,不發請求。三塊:
  1. 股價的月份季節性:族群(theme_groups 手寫族群 + 官方產業)每個月的等權報酬,減掉「全部個股等權平均」(不是加權指數,
     避免把「小型股 2 月比大盤強」算成每個族群的季節性)。2015-02 起只用完整月份。每格=那個月贏過全體的年數/年數。
     驗證:前半段(2015–2020)常贏或常輸的格子,後半段(2021 起)還一樣嗎。個股層級另算「幾乎每年都贏」的檔數和純運氣的期望值。
  2. 營收的旺季:月營收 ÷ 置中 12 個月平均=季節指數(資料只有 2023-05 起,每個月份只有 2~3 個樣本)。
     列各產業的月份指數,和接下來三個月是旺季的個股。
  0. 年曆樹(2026-11-24 使用者:「一條線旁邊有分支 我可以再點進去 然後對應」):時間主幹 + 每月分支(展覽/常贏/常輸/營收旺),
     點分支在右邊展開族群的 12 個月習性、對應展覽、全部成員股。資料內嵌在海報的 JSON 裡,不發請求。
  3. 展覽:EXPO 是手寫的行事曆(日期來源見每筆的 src;● 有查到、? 沒查到或憑記憶)。每個展覽 × 對應族群,
     算歷年開展前 PRE 個交易日、開展後 POST 個交易日相對全部個股等權的超額報酬。
族群成員是現在的名單(事後挑的),所以「全年平均贏率」本身就偏高;看的是同一個族群不同月份之間的差別。
手動重跑:python -X utf8 make_poster_season.py      驗證點:印出的「驗證」「展覽彙總」= 海報上的數字"""
from __future__ import annotations

from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

import make_poster_gapup as gp
import theme_groups as tg
from poster import bignums, card, checks, row, save_poster, shell_flow, slink
from twtime import now_tw

D = Path(__file__).parent / "data"
SPLIT = 2020            # 驗證:≤ SPLIT 是前半段,之後是後半段
HOT, COLD = 0.8, 0.2    # 前半段贏率門檻
MINY = 8                # 熱圖上色至少要幾年資料
PRE, POST = 20, 20      # 展覽前後看幾個交易日
LIQ = 0.5
HOTSI, HOTLO = 1.10, 1.03   # 營收旺季個股:接下來三個月合計的季節指數,各年平均 ≥ HOTSI,而且每一年都 ≥ HOTLO
T, S = "T", "S"         # 手寫族群 / 官方產業

# ── 展覽行事曆(手寫;2026-11-24 請代理逐一查主辦單位網站、維基百科、新聞整理。dates=歷年實體展的開展日,d27=2027 起訖)──
# 只有線上的年份和停辦的年份不放;延期的照實際日期。較舊的日期有一部分來自展覽彙整網站(可能是原訂日期)。
EXPO: list[dict] = [
    dict(name="CES", where="拉斯維加斯", d27="1/6~1/9", mark="●", note="主辦單位 2026/11 新聞稿",
         groups=[(T, "AI伺服器"), (T, "IC設計"), (T, "光學鏡頭"), (T, "面板/電子紙"), (T, "機器人自動化")],
         dates={2016: "2016-01-06", 2017: "2017-01-05", 2018: "2018-01-09", 2019: "2019-01-08", 2020: "2020-01-07", 2022: "2022-01-05",
                2023: "2023-01-05", 2024: "2024-01-09", 2025: "2025-01-07", 2026: "2026-01-06"}),          # 2021 只有線上,不算
    dict(name="台北國際電玩展", where="台北", d27="1/21~1/24", mark="●", note="聯合新聞網 2026/7 引主辦單位",
         groups=[(S, "文化創意業")],
         dates={2016: "2016-01-29", 2017: "2017-01-20", 2018: "2018-01-25", 2019: "2019-01-25", 2021: "2021-01-28", 2022: "2022-01-22",
                2023: "2023-02-02", 2024: "2024-01-25", 2025: "2025-01-23", 2026: "2026-01-29"}),          # 2020 停辦
    dict(name="MWC 世界行動通訊大會", where="巴塞隆納", d27="3/1~3/4", mark="●", note="主辦單位網站",
         groups=[(T, "網通"), (S, "通信網路業")],
         dates={2016: "2016-02-22", 2017: "2017-02-27", 2018: "2018-02-26", 2019: "2019-02-25", 2021: "2021-06-28", 2022: "2022-02-28",
                2023: "2023-02-27", 2024: "2024-02-26", 2025: "2025-03-03", 2026: "2026-03-02"}),          # 2020 停辦;2021 延到 6 月
    dict(name="TIMTOS 台北工具機展", where="台北(單數年)", d27="3/2~3/6", mark="●", note="主辦單位網站",
         groups=[(T, "機器人自動化"), (S, "電機機械")],
         dates={2017: "2017-03-07", 2019: "2019-03-04", 2022: "2022-02-21", 2023: "2023-03-06", 2025: "2025-03-03"}),   # 2021 改線上,2022 補辦
    dict(name="OFC 光纖通訊展", where="洛杉磯", d27="3/9~3/11", mark="●", note="主辦單位網站;會議 3/7 開始",
         groups=[(T, "光通訊CPO")],
         dates={2018: "2018-03-13", 2019: "2019-03-05", 2020: "2020-03-10", 2022: "2022-03-08", 2024: "2024-03-26", 2025: "2025-04-01",
                2026: "2026-03-17"}),                                                                      # 2016、2017、2023 展覽首日沒查到;2021 線上
    dict(name="NVIDIA GTC", where="聖荷西", d27="3/15~3/18", mark="●", note="官網首頁;同站另一頁寫 3/14 開始",
         groups=[(T, "AI伺服器"), (T, "散熱"), (T, "光通訊CPO"), (T, "電源"), (T, "PCB")],
         dates={2016: "2016-04-04", 2017: "2017-05-08", 2018: "2018-03-26", 2019: "2019-03-17", 2023: "2023-03-20", 2024: "2024-03-18",
                2025: "2025-03-17", 2026: "2026-03-16"}),                                                  # 2020~2022 線上,不算
    dict(name="台北國際自行車展", where="台北", d27="3/24~3/27", mark="●", note="主辦單位網站",
         groups=[(S, "運動休閒")],
         dates={2016: "2016-03-02", 2017: "2017-03-22", 2018: "2018-10-31", 2019: "2019-03-27", 2022: "2022-03-09", 2023: "2023-03-22",
                2024: "2024-03-06", 2025: "2025-03-26", 2026: "2026-03-25"}),                              # 2020 停辦、2021 線上
    dict(name="Touch Taiwan 智慧顯示展", where="台北", d27="4/21~4/23", mark="●", note="主辦單位網站",
         groups=[(T, "面板/電子紙"), (T, "玻璃基板TGV"), (S, "光電業")],
         dates={2016: "2016-08-24", 2017: "2017-09-20", 2018: "2018-08-29", 2019: "2019-08-28", 2021: "2021-04-21", 2022: "2022-04-27",
                2023: "2023-04-19", 2024: "2024-04-24", 2025: "2025-04-16", 2026: "2026-04-08"}),          # 2020 沒辦;2021 起從 8 月改到 4 月
    dict(name="COMPUTEX 台北國際電腦展", where="台北", d27="6/1~6/4", mark="●", note="中央社 2026/9 引主辦單位",
         groups=[(T, "AI伺服器"), (T, "散熱"), (T, "IC設計"), (T, "電源"), (S, "電腦及週邊設備業")],
         dates={2016: "2016-05-31", 2017: "2017-05-30", 2018: "2018-06-05", 2019: "2019-05-28", 2022: "2022-05-24", 2023: "2023-05-30",
                2024: "2024-06-04", 2025: "2025-05-20", 2026: "2026-06-02"}),                              # 2020 停辦、2021 線上
    dict(name="BIO Asia–Taiwan 亞洲生技大展", where="台北", d27="7/27~7/31", mark="●", note="主辦單位網站",
         groups=[(T, "生技新藥"), (S, "生技醫療業")],
         dates={2019: "2019-07-25", 2020: "2020-07-23", 2021: "2021-11-04", 2022: "2022-07-28", 2024: "2024-07-26", 2025: "2025-07-24",
                2026: "2026-07-16"}),                                                                      # 2023 展覽首日沒查到
    dict(name="SEMICON Taiwan 國際半導體展", where="台北", d27="8/18~8/20", mark="●", note="Focus Taiwan 2026/9 引 SEMI;比往年早約三週",
         groups=[(T, "半導體設備"), (T, "封測"), (T, "晶圓代工"), (T, "矽晶圓"), (T, "電子特化")],
         dates={2016: "2016-09-07", 2017: "2017-09-13", 2018: "2018-09-05", 2019: "2019-09-18", 2020: "2020-09-23", 2021: "2021-12-28",
                2022: "2022-09-14", 2023: "2023-09-06", 2024: "2024-09-04", 2025: "2025-09-10", 2026: "2026-09-02"}),
    dict(name="TADTE 台北航太暨國防工業展", where="台北(單數年)", d27="9/23~9/25", mark="●", note="中央社 2026/10 引外貿協會",
         groups=[(T, "軍工航太")],
         dates={2017: "2017-08-17", 2019: "2019-08-15", 2023: "2023-09-14", 2025: "2025-09-18"}),         # 2021 停辦
    dict(name="OCP 全球峰會", where="舊金山(原聖荷西)", d27="10/4~10/7", mark="●", note="主辦單位 2026/9 公告,改到舊金山",
         groups=[(T, "AI伺服器"), (T, "散熱"), (T, "電源"), (T, "光通訊CPO")],
         dates={2016: "2016-03-09", 2017: "2017-03-08", 2018: "2018-03-20", 2019: "2019-03-14", 2021: "2021-11-09", 2022: "2022-10-18",
                2023: "2023-10-17", 2024: "2024-10-15", 2025: "2025-10-13", 2026: "2026-10-12"}),          # 2020 線上;2021 起改到秋天
    dict(name="TPCA Show 電路板展", where="台北", d27="", mark="?", note="還沒公布;往年在 10 月下旬",
         groups=[(T, "PCB"), (T, "ABF載板")],
         dates={2016: "2016-10-26", 2017: "2017-10-25", 2018: "2018-10-24", 2019: "2019-10-23", 2020: "2020-10-21", 2021: "2021-12-21",
                2022: "2022-10-26", 2023: "2023-10-25", 2024: "2024-10-23", 2025: "2025-10-22", 2026: "2026-10-20"}),
    dict(name="Energy Taiwan 智慧能源週", where="台北", d27="10/27~10/29", mark="●", note="主辦單位網站",
         groups=[(T, "重電"), (S, "綠能環保")],
         dates={2018: "2018-09-19", 2019: "2019-10-16", 2020: "2020-10-14", 2021: "2021-12-08", 2022: "2022-10-19", 2023: "2023-10-18",
                2024: "2024-10-04", 2025: "2025-10-29", 2026: "2026-10-14"}),                              # 2016、2017 沒查到
]


def monthly(C: pd.DataFrame, sl: pd.DataFrame):
    last = C.index[-1]
    mR = C.resample("ME").last().pct_change(fill_method=None)
    full = mR.index[(mR.index >= "2015-02-01") & (mR.index < last.to_period("M").to_timestamp())]
    mR = mR.loc[full]
    stocks = [c for c in mR.columns if c in sl.index and pd.notna(sl.sector[c])]
    return mR[stocks], mR[stocks].mean(axis=1)


def members(sl: pd.DataFrame, cols) -> dict:
    g = {(T, k): [c for c in dict.fromkeys(v) if c in cols] for k, v in tg.THEME_GROUPS.items()}
    for k, v in sl[sl.index.isin(cols) & sl.sector.notna()].groupby("sector"):
        g[(S, k)] = list(v.index)
    return {k: v for k, v in g.items() if len(v) >= 3}


def season_price(mR: pd.DataFrame, ew: pd.Series, mem: dict) -> pd.DataFrame:
    rows = []
    for k, v in mem.items():
        x = (mR[v].mean(axis=1).where(mR[v].notna().sum(axis=1) >= 3) - ew).dropna()
        for m in range(1, 13):
            s = x[x.index.month == m]
            a, b = s[s.index.year <= SPLIT], s[s.index.year > SPLIT]
            ly = x.index.year.max()
            p0, c0 = s[s.index.year < ly], s[s.index.year == ly]          # 最新一年單獨拿出來:用之前的年份定「常贏/常輸」,看最新一年對不對
            rows.append(dict(kind=k[0], g=k[1], m=m, n=len(s), win=int((s > 0).sum()), avg=s.mean(),
                             pn=len(p0), pw=int((p0 > 0).sum()), cn=len(c0), cw=int((c0 > 0).sum()), ca=c0.mean() if len(c0) else np.nan,
                             n1=len(a), w1=int((a > 0).sum()), n2=len(b), w2=int((b > 0).sum()), a2=b.mean()))
    return pd.DataFrame(rows)


def season_rev() -> tuple[pd.DataFrame, str, pd.DataFrame]:
    rv = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    R = rv.pivot_table(index="ym", columns="code", values="revenue", aggfunc="last").sort_index()
    R.index = pd.PeriodIndex(R.index, freq="M")
    ma = R.rolling(12, min_periods=12).mean()
    si = R / ((ma + ma.shift(-1)) / 2).shift(-5)        # 置中 12 個月平均
    si = si.where((R > 0) & si.notna())
    g = si.groupby(si.index.month)
    out = pd.concat({"mean": g.mean(), "min": g.min(), "cnt": g.count()}, axis=1)     # index=月份;欄=(統計, 代號)
    return out, f"{si.dropna(how='all').index[0]}~{si.dropna(how='all').index[-1]}", si


def expo_study(C: pd.DataFrame, stocks: list, mem: dict) -> pd.DataFrame:
    Cs = C[stocks]
    rows = []
    for e in EXPO:
        for y, d in e["dates"].items():
            i = int(np.searchsorted(C.index.values, np.datetime64(pd.Timestamp(d)), side="left"))
            if i - PRE - 1 < 0 or i + POST - 1 >= len(C):
                continue
            pre_all = Cs.iloc[i - 1] / Cs.iloc[i - 1 - PRE] - 1
            post_all = Cs.iloc[i - 1 + POST] / Cs.iloc[i - 1] - 1
            for k in e["groups"]:
                v = mem.get(k)
                if not v:
                    continue
                a, b = pre_all[v].dropna(), post_all[v].dropna()
                if len(a) < 3 or len(b) < 3:
                    continue
                rows.append(dict(expo=e["name"], kind=k[0], g=k[1], y=int(y), pre=a.mean() - pre_all.mean(), post=b.mean() - post_all.mean()))
    return pd.DataFrame(rows)


def pc(x, d=1) -> str:
    return gp.pc(x, d)


def heat(Sd: pd.DataFrame, nxt: list, kind: str) -> str:
    d = Sd[Sd.kind == kind]
    base = d.groupby("g").apply(lambda z: z.win.sum() / z.n.sum(), include_groups=False)
    order = base.sort_values(ascending=False).index
    s = ('<table style="font-size:12.5px;text-align:center"><tr><th style="text-align:left">族群</th>'
         + "".join(f'<th style="text-align:center{";background:#ffe7a8" if m in nxt else ""}">{m} 月</th>' for m in range(1, 13))
         + '<th style="text-align:center">全年</th></tr>')
    for g in order:
        s += f'<tr><td style="text-align:left;white-space:nowrap"><b>{g}</b></td>'
        for m in range(1, 13):
            r = d[(d.g == g) & (d.m == m)].iloc[0]
            if r.n == 0:
                s += "<td>—</td>"
                continue
            wr = r.win / r.n
            bg = "" if r.n < MINY else ("background:#f8c9c2" if wr >= 0.75 else "background:#c5e8cf" if wr <= 0.25 else "")
            s += f'<td class="n" style="{bg}{";color:#9aa" if r.n < MINY else ""}">{r.win}/{r.n}</td>'
        s += f'<td class="n">{base[g] * 100:.0f}%</td></tr>'
    return s + "</table>"


TREE_CSS = """<style>
.card.tree,.card.tree .cb{overflow:visible}
.szw{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px;align-items:start}
@media (max-width:900px){.szw{grid-template-columns:1fr}}
.tl{position:relative;margin-left:74px;border-left:4px solid #27303b;padding:2px 0 2px 0}
.mo{position:relative;padding:5px 0 9px 0}
.mo .ml{position:absolute;left:-82px;top:3px;width:66px;text-align:right;font-weight:900;font-size:14px;line-height:1.15;color:#27303b}
.mo .ml small{display:block;font-weight:700;font-size:10.5px;color:#789}
.mo::before{content:"";position:absolute;left:-11px;top:6px;width:14px;height:14px;border-radius:50%;background:#fff;border:4px solid #27303b}
.mo.nx::before{background:#ffb74d}
.mk{margin:0 0 3px 22px;font-size:11.5px;color:#567;font-weight:700}
.br{position:relative;margin:4px 0 4px 0;padding-left:22px;display:flex;flex-wrap:wrap;gap:4px 5px;align-items:center}
.br::before{content:"";position:absolute;left:0;top:13px;width:18px;border-top:2px solid #9aa7b5}
.br .lab{font-weight:900;font-size:12px;min-width:58px;color:#345}
.chip{cursor:pointer;border-radius:13px;padding:2px 9px;font-size:12.5px;font-weight:800;border:1.5px solid;white-space:nowrap;user-select:none}
.chip small{font-weight:700;opacity:.8}
.chip.ex{background:#fff3d6;border-color:#d9a400;color:#6b4a12}
.chip.hot{background:#fde3df;border-color:#e08a7c;color:#8e2437}
.chip.cold{background:#dff3e5;border-color:#7cc594;color:#17603a}
.chip.rev{background:#e3eefc;border-color:#8fb7e8;color:#0d2b52}
.chip:hover{filter:brightness(.95)}
.chip.sel{box-shadow:0 0 0 3px #27303b}
.szp{position:sticky;top:8px;max-height:1340px;overflow:auto;background:#f6f8fb;border:1.5px solid #cfd8e3;border-radius:8px;padding:10px 12px}
.szp h3{font-size:17px;font-weight:900;color:#27303b;margin-bottom:2px}
.szp h4{font-size:13px;font-weight:900;color:#27303b;margin:9px 0 3px}
.szp .tag{display:inline-block;font-size:11px;font-weight:800;border-radius:4px;padding:0 6px;background:#27303b;color:#fff;margin-left:6px;vertical-align:middle}
.szp table{font-size:12.5px;background:#fff}
.szp .st{table-layout:fixed;width:100%}
.szp .st td,.szp .st th{text-align:center;padding:3px 0;font-size:11px;overflow:hidden}
.szp .lk{cursor:pointer;color:#1b5fa8;text-decoration:underline}
.szp .hint{color:#678;font-size:12.5px;font-weight:700}
.lg2{display:flex;flex-wrap:wrap;gap:4px 10px;font-size:12px;font-weight:700;color:#456;margin-bottom:6px}
</style>"""

TREE_JS = """<script>
(function(){
  var el=document.getElementById('szdata'); if(!el) return;
  var D=JSON.parse(el.textContent), P=document.getElementById('szpanel');
  function pc(x,d){ if(x===null||x===undefined) return '—'; var c=x>0?'rd':(x<0?'gn':''); return '<span class="'+c+'">'+(x>0?'+':'')+x.toFixed(d===undefined?1:d)+'%</span>'; }
  function bg(w,n){ if(!n||n<D.miny) return 'color:#9aa'; var r=w/n; return r>=0.75?'background:#f8c9c2':(r<=0.25?'background:#c5e8cf':''); }
  function strip(g,m){
    var h='<table class="st"><tr>',r='<tr>',a='<tr>';
    for(var i=0;i<12;i++){ var on=(i+1===m)?';outline:2.5px solid #27303b;outline-offset:-2px':'';
      h+='<th style="'+(D.nxt.indexOf(i+1)>=0?'background:#ffe7a8':'')+'">'+(i+1)+'</th>';
      r+='<td class="n" style="'+bg(g.w[i],g.y[i])+on+'">'+(g.y[i]?g.w[i]+'/'+g.y[i]:'—')+'</td>';
      a+='<td class="n" style="font-size:10px">'+pc(g.a[i],0)+'</td>'; }
    return h+'</tr>'+r+'</tr>'+a+'</tr></table>';
  }
  function showG(key,m){
    var g=D.G[key]; if(!g) return;
    var h='<h3>'+g.n+'<span class="tag">'+g.k+'</span><span class="tag" style="background:#789">成員 '+g.mem.length+' 檔</span></h3>';
    if(m){ var i=m-1; h+='<div class="hint">'+m+' 月:'+(g.y[i]?('贏過全部個股平均 <b>'+g.w[i]+'/'+g.y[i]+'</b> 年,平均超額 '+pc(g.a[i])+';2015–'+D.split+' 是 '+g.w1[i]+'/'+g.n1[i]+',之後 '+g.w2[i]+'/'+g.n2[i]):'資料不足')+'</div>'; }
    h+='<h4>12 個月的習性(上:贏的年數/年數;下:平均超額)</h4>'+strip(g,m);
    if(g.rev){ h+='<h4>營收季節指數(100=全年平均,產業內個股中位數)</h4><table class="st"><tr>';
      for(var i=0;i<12;i++) h+='<th>'+(i+1)+'</th>'; h+='</tr><tr>';
      for(var i=0;i<12;i++){ var x=g.rev[i]; h+='<td class="n" style="'+(x>=108?'background:#f8c9c2':(x<=92?'background:#c5e8cf':''))+'">'+(x===null?'—':x)+'</td>'; } h+='</tr></table>'; }
    var es=[]; D.E.forEach(function(e,j){ e.gs.forEach(function(q){ if(q.key===key) es.push([j,e,q]); }); });
    if(es.length){ h+='<h4>對應的展覽(點展覽名稱看細節)</h4><table><tr><th>展覽</th><th>2027</th><th>展前'+D.pre+'日</th><th>展後'+D.post+'日</th></tr>';
      es.forEach(function(t){ h+='<tr><td><span class="lk" data-e="'+t[0]+'">'+t[1].name+'</span></td><td class="n">'+t[1].mark+(t[1].d27||'未公布')+'</td><td class="n">'+pc(t[2].pre)+' <small>'+t[2].prew+'/'+t[2].n+'</small></td><td class="n">'+pc(t[2].post)+' <small>'+t[2].postw+'/'+t[2].n+'</small></td></tr>'; });
      h+='</table>'; }
    h+='<h4>成員(依 20 日均成交值排序,全部列出;點名稱開個股頁)</h4><table><tr><th>代號 名稱</th><th>收盤</th><th>近 20 日</th><th>成交值(億)</th></tr>';
    g.mem.forEach(function(r){ h+='<tr><td><a class="sl" target="_blank" rel="noopener" href="/個股?code='+r[0]+'"><b>'+r[0]+'</b> '+r[1]+'</a></td><td class="n">'+(r[2]===null?'—':r[2])+'</td><td class="n">'+pc(r[3],0)+'</td><td class="n">'+(r[4]===null?'—':r[4].toFixed(2))+'</td></tr>'; });
    P.innerHTML=h+'</table>'; P.scrollTop=0;
  }
  function showE(j){
    var e=D.E[j]; if(!e) return;
    var h='<h3>'+e.name+'<span class="tag">'+e.where+'</span></h3><div class="hint">2027 年:'+e.mark+(e.d27||'還沒公布')+'|'+e.note+'|歷年樣本 '+e.ny+' 次</div>';
    h+='<h4>對應族群(點族群名稱看成員)</h4><table><tr><th>族群</th><th>樣本</th><th>展前'+D.pre+'日超額(中位)</th><th>贏的年數</th><th>展後'+D.post+'日超額(中位)</th><th>贏的年數</th></tr>';
    e.gs.forEach(function(q){ h+='<tr><td><span class="lk" data-k="'+q.key+'"><b>'+D.G[q.key].n+'</b></span></td><td class="n">'+q.n+'</td><td class="n">'+pc(q.pre)+'</td><td class="n">'+q.prew+'/'+q.n+'</td><td class="n">'+pc(q.post)+'</td><td class="n">'+q.postw+'/'+q.n+'</td></tr>'; });
    h+='</table><div class="hint" style="margin-top:6px">超額=族群等權報酬−全部個股等權報酬。對應族群是我配的,不是主辦單位的分類。</div>';
    P.innerHTML=h; P.scrollTop=0;
  }
  function pick(c){
    document.querySelectorAll('.chip.sel').forEach(function(x){x.classList.remove('sel');});
    if(c.classList.contains('chip')) c.classList.add('sel');
    if(c.dataset.e!==undefined) showE(+c.dataset.e); else showG(c.dataset.k, c.dataset.m?+c.dataset.m:0);
  }
  document.addEventListener('click',function(ev){ var c=ev.target.closest('[data-k],[data-e]'); if(c) pick(c); });
  var first=document.querySelector('.tl .chip'); if(first) pick(first);
})();
</script>"""


def tree_card(Sd, mem, sl, ev, secm, MK, nxt, last, Cf, amt20) -> str:
    """年曆樹:一條時間主幹,每個月長出分支(展覽/常贏/常輸/營收旺季),點分支在右邊展開對應的族群與成員股。"""
    import json

    def num(x, d=1, mul=1.0):
        return None if x is None or pd.isna(x) else round(float(x) * mul, d)
    kname = {T: "手寫族群", S: "官方產業"}
    r20 = Cf.iloc[-1] / Cf.iloc[-21] - 1
    G = {}
    for k, v in mem.items():
        d = Sd[(Sd.kind == k[0]) & (Sd.g == k[1])].set_index("m").reindex(range(1, 13))
        ms = sorted(v, key=lambda c: -(amt20.get(c, 0) if pd.notna(amt20.get(c, np.nan)) else 0))
        G[f"{k[0]}|{k[1]}"] = dict(
            n=k[1], k=kname[k[0]], w=[int(x) for x in d.win], y=[int(x) for x in d.n], a=[num(x, 1, 100) for x in d.avg],
            w1=[int(x) for x in d.w1], n1=[int(x) for x in d.n1], w2=[int(x) for x in d.w2], n2=[int(x) for x in d.n2],
            rev=[num(secm.loc[k[1], m], 0, 100) for m in range(1, 13)] if (k[0] == S and k[1] in secm.index) else None,
            mem=[[c, str(sl.name.get(c, "")), num(Cf.iloc[-1].get(c), 2), num(r20.get(c), 0, 100), num(amt20.get(c), 2)] for c in ms])
    E = []
    for e in EXPO:
        gs = []
        for k in e["groups"]:
            x = ev[(ev.expo == e["name"]) & (ev.kind == k[0]) & (ev.g == k[1])] if len(ev) else []
            if len(x):
                gs.append(dict(key=f"{k[0]}|{k[1]}", n=len(x), pre=num(x.pre.median(), 1, 100), prew=int((x.pre > 0).sum()),
                               post=num(x.post.median(), 1, 100), postw=int((x.post > 0).sum())))
        mth = int(e["d27"].split("/")[0]) if e.get("d27") else pd.Timestamp(max(e["dates"].values())).month
        E.append(dict(name=e["name"], where=e["where"], d27=e.get("d27", ""), mark=e["mark"], note=e["note"], ny=len(e["dates"]), gs=gs, m=mth))
    hotc = Sd[(Sd.n >= MINY) & (Sd.win / Sd.n >= 0.75)]
    coldc = Sd[(Sd.n >= MINY) & (Sd.win / Sd.n <= 0.25)]
    out = ""
    for j in range(1, 14):
        t = last + pd.DateOffset(months=j)
        m, y = t.month, t.year
        up, n, avg, eww, ewn = MK[m]
        out += (f'<div class="mo{" nx" if j <= 3 else ""}"><div class="ml">{m} 月<small>{y}</small></div>'
                f'<div class="mk">大盤習性:加權指數上漲 {up}/{n} 年(平均 {avg * 100:+.1f}%);中小型股贏指數 {eww}/{ewn} 年</div>')
        ex = [(i, e) for i, e in enumerate(E) if e["m"] == m and y == 2027]
        if ex:
            out += '<div class="br"><span class="lab">🎪 展覽</span>' + "".join(
                f'<span class="chip ex" data-e="{i}">{e["name"]} <small>{e["mark"]}{e["d27"] or "未公布"}</small></span>' for i, e in ex) + "</div>"
        for cls, lab, d in (("hot", "📈 常贏", hotc), ("cold", "📉 常輸", coldc)):
            dd = d[d.m == m].assign(wr=lambda z: z.win / z.n).sort_values(["wr", "avg"], ascending=[cls == "cold", cls == "cold"])
            if len(dd):
                out += f'<div class="br"><span class="lab">{lab}</span>' + "".join(
                    f'<span class="chip {cls}" data-k="{r.kind}|{r.g}" data-m="{m}">{r.g} <small>{r.win}/{r.n}</small></span>' for r in dd.itertuples()) + "</div>"
        rv = secm[m][secm[m] >= 1.08].sort_values(ascending=False)
        if len(rv):
            out += '<div class="br"><span class="lab">🛍 營收旺</span>' + "".join(
                f'<span class="chip rev" data-k="S|{g}" data-m="{m}">{g} <small>{x * 100:.0f}</small></span>' for g, x in rv.items() if f"S|{g}" in G) + "</div>"
        out += "</div>"
    data = json.dumps(dict(G=G, E=E, nxt=nxt, miny=MINY, split=SPLIT, pre=PRE, post=POST), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    legend = ('<div class="lg2"><span><span class="chip ex">展覽</span> 2027 年日期(●有來源、?未公布)</span>'
              '<span><span class="chip hot">常贏</span> 那個月贏過全部個股平均的年數 ≥ 75%</span>'
              '<span><span class="chip cold">常輸</span> ≤ 25%</span>'
              '<span><span class="chip rev">營收旺</span> 產業營收季節指數 ≥ 108</span>'
              '<span>橘色圓點=接下來三個月</span></div>')
    body = (TREE_CSS + legend + '<div class="szw"><div class="tl">' + out + '</div>'
            '<div class="szp" id="szpanel"><div class="hint">點左邊任何一個分支,這裡會列出對應的族群、12 個月習性、相關展覽和全部成員股。</div></div></div>'
            f'<script type="application/json" id="szdata">{data}</script>' + TREE_JS
            + f'<div class="note">●主幹是時間,從下個月排到 2027 年 12 月;每個月的分支是那個月的展覽、歷史上常贏/常輸的族群、營收旺季的產業。'
              f"族群後面的數字=贏的年數/有資料的年數(至少 {MINY} 年才列);營收旺後面的數字=季節指數。點分支→右邊展開;右邊表格裡有底線的名稱可以再點進去。"
              "習性是 2015 年以來的統計,樣本只有十一二年,不是預測。</div>")
    return card("🌿 年曆樹:每個月有什麼展覽、哪些族群常贏常輸、哪些產業是營收旺季(點分支看對應的股票)", body, f"至 {last:%m/%d} 收盤", extra_cls="tree")


def main() -> str:
    P = gp.panel()
    C, V = P["Close"], P["Volume"]
    last = C.index[-1]
    sl = pd.read_csv(D / "stock_list.csv", dtype=str, encoding="utf-8-sig").drop_duplicates("code").set_index("code")
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    mR, ew = monthly(C, sl)
    stocks = list(mR.columns)
    mem = members(sl, set(stocks))
    Sd = season_price(mR, ew, mem)
    nxt = [((last.month + k - 1) % 12) + 1 for k in (1, 2, 3)]      # 接下來三個月份
    y0, y1 = mR.index[0], mR.index[-1]

    # ── 驗證 ──
    v = Sd[(Sd.n1 >= 5) & (Sd.n2 >= 5)]
    hot, cold = v[v.w1 / v.n1 >= HOT], v[v.w1 / v.n1 <= COLD]
    r_hot, r_cold, r_all = hot.w2.sum() / hot.n2.sum(), cold.w2.sum() / cold.n2.sum(), v.w2.sum() / v.n2.sum()
    a_hot, a_cold = float(hot.a2.mean()), float(cold.a2.mean())
    # 只看最新一年:用更早的年份定常贏/常輸,最新一年實際贏幾成
    ty = int(mR.index.year.max())
    vy = Sd[(Sd.pn >= MINY) & (Sd.cn == 1)]
    yh, yc = vy[vy.pw / vy.pn >= 0.75], vy[vy.pw / vy.pn <= 0.25]
    ty_hot, ty_cold, ty_all = yh.cw.sum() / max(1, len(yh)), yc.cw.sum() / max(1, len(yc)), vy.cw.sum() / max(1, len(vy))
    # 個股:幾乎每年都贏(≥ n-1 次)的檔數 vs 純運氣
    XR = mR.sub(ew, axis=0)
    act = exp = 0.0
    for m in range(1, 13):
        s = XR[XR.index.month == m]
        n, w = s.notna().sum(), (s > 0).sum()
        okk = n >= 11
        act += int(((w >= n - 1) & okk).sum())
        exp += float(sum((comb(int(k), int(k) - 1) + 1) / 2 ** int(k) for k in n[okk]))
    # 大盤與小型股
    mB = bm.resample("ME").last().pct_change().reindex(mR.index)
    tm = "<table style=\"text-align:center\"><tr><th style=\"text-align:left\">月份</th>" + "".join(
        f'<th style="text-align:center{";background:#ffe7a8" if m in nxt else ""}">{m}</th>' for m in range(1, 13)) + "</tr>"
    r1 = r2 = r3 = ""
    MK = {}
    for m in range(1, 13):
        b, e = mB[mB.index.month == m].dropna(), (ew - mB)[mB.index.month == m].dropna()
        MK[m] = (int((b > 0).sum()), len(b), float(b.mean()), int((e > 0).sum()), len(e))
        r1 += f'<td class="n">{int((b > 0).sum())}/{len(b)}</td>'
        r2 += f'<td class="n">{pc(b.mean())}</td>'
        r3 += f'<td class="n">{int((e > 0).sum())}/{len(e)}</td>'
    tm += (f'<tr><td style="text-align:left">加權指數上漲的年數</td>{r1}</tr><tr><td style="text-align:left">加權指數平均漲跌</td>{r2}</tr>'
           f'<tr><td style="text-align:left">全部個股等權平均贏過加權指數的年數</td>{r3}</tr></table>')
    c_mkt = card("📅 先看大盤自己:每個月份的習性", tm
                 + f'<div class="note">●{y0:%Y/%m}~{y1:%Y/%m} 的完整月份,黃底是接下來三個月。第三列看的是中小型股相對大型股:'
                   "年數少的月份(例如 1 月)代表那個月通常是大型股帶指數、多數個股輸給指數。這也是後面族群表改用「全部個股等權平均」當基準的原因。</div>",
                 "系統日線")

    # ── 接下來三個月最常贏的族群 ──
    up = Sd[Sd.m.isin(nxt) & (Sd.n >= MINY)].copy()
    up["wr"] = up.win / up.n
    top = up[up.wr >= 0.75].sort_values(["m", "wr", "avg"], ascending=[True, False, False])
    top = pd.concat([top[top.m == m] for m in nxt])
    bot = up[up.wr <= 0.25]
    bot = pd.concat([bot[bot.m == m].sort_values("wr") for m in nxt])

    def tlist(d):
        s = '<table style="font-size:12.5px"><tr><th>月份</th><th>族群</th><th>習性</th><th>贏過全體</th><th>平均超額</th><th>2015–2020</th><th>2021 起</th></tr>'
        for _, r in d.iterrows():
            s += (f'<tr><td class="n">{r.m} 月</td><td><b>{r.g}</b><br><small>{"手寫族群" if r.kind == T else "官方產業"}</small></td><td>{"<span class=rd>常贏</span>" if r.wr >= 0.75 else "<span class=gn>常輸</span>"}</td><td class="n">{r.win}/{r.n}</td>'
                  f'<td class="n">{pc(r.avg)}</td><td class="n">{r.w1}/{r.n1}</td><td class="n">{r.w2}/{r.n2}</td></tr>')
        return s + "</table>"
    mtxt = "、".join(f"{m} 月" for m in nxt)
    both = pd.concat([pd.concat([top[top.m == m], bot[bot.m == m]]) for m in nxt])       # 依月份排,同一個月先常贏再常輸;左右兩半接著讀
    half = (len(both) + 1) // 2
    c_next = card(f"🔜 接下來三個月({mtxt}):歷史上常贏的 {len(top)} 格、常輸的 {len(bot)} 格",
                  '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:start">'
                  + f"<div>{tlist(both.iloc[:half])}</div><div>{tlist(both.iloc[half:])}</div></div>"
                  + f'<div class="note">●贏過全體=那個月族群的等權報酬高於全部個股等權平均的年數;只列有 {MINY} 年以上資料、贏率 ≥ 75% 或 ≤ 25% 的格子,全部列出。'
                    "右邊兩欄把樣本拆成前後兩段,兩段都偏同一邊的比較可信。</div>")

    c_ht = card(f"🌡 手寫族群 × 月份:那個月贏過全部個股平均的年數({y0:%Y}~{y1:%Y})", heat(Sd, nxt, T)
                + f'<div class="note">●紅底=贏的年數 ≥ 75%、綠底=≤ 25%(至少 {MINY} 年資料才上色;灰字=資料不足)。黃底欄是接下來三個月。'
                  "「全年」=所有月份合計的贏率:族群成員是現在的名單(事後挑的贏家),所以很多族群全年都高於 50%,要看的是同一列裡月份之間的差別。依全年贏率排序。</div>")
    c_hs = card("🌡 官方產業 × 月份", heat(Sd, nxt, S)
                + '<div class="note">●算法同上。官方產業的成員不是事後挑的,全年贏率比較接近 50%。</div>')

    # ── 營收旺季 ──
    sv, span, si_raw = season_rev()
    sec = sl.sector.reindex(sv["mean"].columns)
    ok2 = (sv["cnt"] >= 2).all(axis=0)
    ms = sv["mean"].loc[:, ok2]
    secm = ms.T.groupby(sec[ok2]).median()
    secn = ms.T.groupby(sec[ok2]).size()
    secm = secm[secn >= 8]
    amp = (secm.max(axis=1) - secm.min(axis=1)).sort_values(ascending=False)
    tr_ = ('<table style="font-size:12.5px;text-align:center"><tr><th style="text-align:left">產業</th>'
           + "".join(f'<th style="text-align:center{";background:#ffe7a8" if m in nxt else ""}">{m} 月</th>' for m in range(1, 13))
           + '<th style="text-align:center">旺季月份</th></tr>')
    for g in amp.index:
        tr_ += f'<tr><td style="text-align:left;white-space:nowrap"><b>{g}</b> <small>{int(secn[g])} 檔</small></td>'
        for m in range(1, 13):
            x = secm.loc[g, m]
            bg = "background:#f8c9c2" if x >= 1.08 else "background:#c5e8cf" if x <= 0.92 else ""
            tr_ += f'<td class="n" style="{bg}">{x * 100:.0f}</td>'
        tr_ += f'<td class="n">{int(secm.loc[g].idxmax())} 月</td></tr>'
    c_rev = card("🧾 營收的旺季:各產業每個月的營收季節指數(100=全年平均)", tr_ + "</table>"
                 + f'<div class="note">●季節指數=當月營收 ÷ 前後 12 個月平均,取每個月份的平均;表上是產業內個股的中位數。紅底 ≥ 108、綠底 ≤ 92。依淡旺季落差排序。'
                   f"月營收資料只有 2023/05 起,能算指數的月份是 {span},每個月份只有 2~3 個樣本,只能當參考。2 月偏低主要是農曆年工作天數少。</div>",
                 "系統月營收")
    Cf = C.ffill(limit=5)
    amt20 = (C.iloc[-20:] * V.iloc[-20:]).mean() / 1e8
    cand = pd.DataFrame({"name": sl.name, "sector": sl.sector}).reindex(ms.columns)
    r3 = si_raw.rolling(3, min_periods=3).mean()
    r3 = r3[r3.index.month == nxt[-1]]                      # 每一年「這三個月」的平均指數(2 月單月偏低是工作天數,所以看三個月合計)
    cand["si"] = r3.mean().reindex(cand.index)
    cand["lo"] = r3.min().reindex(cand.index)
    cand["ns"] = r3.notna().sum().reindex(cand.index)
    for m in nxt:
        cand[f"m{m}"] = ms.loc[m]
    cand["peak"] = ms.idxmax()
    cand["amt20"] = amt20.reindex(cand.index)
    cand["px"] = Cf.iloc[-1].reindex(cand.index)
    cand["r60"] = (Cf.iloc[-1] / Cf.iloc[-61] - 1).reindex(cand.index)
    hotrev = cand[(cand.si >= HOTSI) & (cand.lo >= HOTLO) & (cand.ns >= 2) & (cand.amt20 >= LIQ) & cand.sector.notna() & (cand.sector != "建材營造業")].sort_values("si", ascending=False)
    cand.round(4).to_csv(D / "_season_rev.csv", encoding="utf-8-sig")
    th = ('<table style="font-size:12.5px"><tr><th>代號 名稱</th>' + "".join(f"<th>{m} 月指數</th>" for m in nxt)
          + "<th>三個月平均</th><th>最低的一年</th><th>全年最旺</th><th>收盤</th><th>近 60 日</th><th>成交值(億)</th></tr>")
    for c, r in hotrev.iterrows():
        th += (f'<tr><td style="white-space:nowrap"><b>{slink(c, c + " " + r["name"])}</b><br><small>{r.sector}</small></td>'
               + "".join(f'<td class="n">{r[f"m{m}"] * 100:.0f}</td>' for m in nxt)
               + f'<td class="n"><b>{r.si * 100:.0f}</b></td><td class="n">{r.lo * 100:.0f}</td><td class="n">{int(r.peak)} 月</td>'
                 f'<td class="n">{r.px:g}</td><td class="n">{pc(r.r60, 0)}</td><td class="n">{r.amt20:.2f}</td></tr>')
    c_hot = card(f"🛍 接下來三個月({mtxt})是營收旺季的個股:{len(hotrev)} 檔", th + "</table>"
                 + f'<div class="note">●條件:這三個月合計的季節指數,各年平均 ≥ {HOTSI * 100:.0f}、每一年都 ≥ {HOTLO * 100:.0f}(至少兩年樣本)、20 日均成交值 ≥ {LIQ} 億;建材營造(完工入帳)不列。全部列出,依指數排序。'
                   "樣本只有 2~3 年;營收旺季不等於股價會漲,這張表沒有驗證股價。全部個股的指數在 data/_season_rev.csv。</div>")

    # ── 展覽 ──
    ev = expo_study(C, stocks, mem)
    te = ("<table style=\"font-size:12.5px\"><tr><th>展覽</th><th>2027 年日期</th><th>對應族群</th><th>樣本年數</th>"
          f"<th>展前 {PRE} 日超額(中位)</th><th>展前贏的年數</th><th>展後 {POST} 日超額(中位)</th><th>展後贏的年數</th></tr>")
    summ = []
    for e in EXPO:
        gs = [k for k in e["groups"] if k in mem]
        d27 = e.get("d27") or "尚未公布"
        ny = len(e["dates"])
        for j, k in enumerate(gs):
            x = ev[(ev.expo == e["name"]) & (ev.g == k[1]) & (ev.kind == k[0])] if len(ev) else pd.DataFrame()
            head = (f'<td rowspan="{len(gs)}" style="white-space:nowrap"><b>{e["name"]}</b><br><small>{e["where"]}</small></td>'
                    f'<td rowspan="{len(gs)}">{e["mark"]}{d27}<br><small>{e["note"]}</small></td>') if j == 0 else ""
            if len(x) == 0:
                te += f'<tr>{head}<td>{k[1]}</td><td colspan="5">沒有可用的歷年日期</td></tr>'
                continue
            summ.append(dict(expo=e["name"], g=k[1], n=len(x), pre=x.pre.median(), prew=int((x.pre > 0).sum()), post=x.post.median(), postw=int((x.post > 0).sum())))
            te += (f'<tr>{head}<td><b>{k[1]}</b></td><td class="n">{len(x)}</td><td class="n">{pc(x.pre.median())}</td><td class="n">{int((x.pre > 0).sum())}/{len(x)}</td>'
                   f'<td class="n">{pc(x.post.median())}</td><td class="n">{int((x.post > 0).sum())}/{len(x)}</td></tr>')
    te += "</table>"
    SM = pd.DataFrame(summ)
    n_ev = len(ev)
    pre_w, post_w = (float((ev.pre > 0).mean()), float((ev.post > 0).mean())) if n_ev else (np.nan, np.nan)
    pre_m, post_m = (float(ev.pre.median()), float(ev.post.median())) if n_ev else (np.nan, np.nan)
    c_expo = card(f"🎪 2027 年展覽行事曆 × 對應族群:歷年展前 {PRE} 日、展後 {POST} 日相對全部個股的表現", te
                  + f'<div class="note">超額=族群等權報酬 − 全部個股等權報酬。展前=開展前 {PRE} 個交易日到開展前一天;展後=開展前一天到之後第 {POST} 個交易日。'
                    "●=日期在主辦單位或新聞頁面查到;?=沒查到或尚未公布。對應族群是我配的(系統的手寫族群與官方產業),不是主辦單位的分類。"
                    "停辦或改線上的年份照實際日期算;族群成員是現在的名單。</div>", "日期:2026/11/24 網路查詢")

    c_tree = tree_card(Sd, mem, sl, ev, secm, MK, nxt, last, Cf, amt20)

    # ── 結論 ──
    lamp = ""
    try:
        import json
        lamp = json.load(open(D / "_market_risk.json", encoding="utf-8")).get("lamp", "")
    except Exception:
        pass
    best = SM.sort_values("prew", ascending=False).head(3) if len(SM) else SM
    c_concl = card("📌 結論(重點先看)", checks([
        ("ok", f"<b>族群的月份習性有一點延續性,但不強</b>:前半段(2015–{SPLIT})贏率 ≥ {HOT * 100:.0f}% 的 {len(hot)} 格,後半段贏率 {r_hot * 100:.0f}%"
               f"(全部格子 {r_all * 100:.0f}%);前半段 ≤ {COLD * 100:.0f}% 的 {len(cold)} 格,後半段 {r_cold * 100:.0f}%"),
        ("wn", f"<b>只看 {ty} 年</b>(1~{int(mR.index[-1].month)} 月):用更早年份定出的常贏格子 {len(yh)} 個,今年實際贏的有 {ty_hot * 100:.0f}%;"
               f"常輸格子 {len(yc)} 個,今年贏的 {ty_cold * 100:.0f}%(全部格子 {ty_all * 100:.0f}%)。回測期間是 {y0:%Y/%m}~{y1:%Y/%m},每個月份只有 {int(Sd.n.max()) - 1}~{int(Sd.n.max())} 個樣本"),
        ("xx", f"<b>個股層級是雜訊</b>:某個月份「幾乎每年都贏」的個股有 {act:.0f} 檔次,純靠運氣就該有 {exp:.0f} 檔次。挑「每年 X 月都漲」的個股沒有意義,要看族群"),
        ("wn" if n_ev else "xx", (f"<b>展覽行情整體看不出來</b>:{len(EXPO)} 個展覽、{n_ev} 個「展覽×族群×年」樣本,展前 {PRE} 日贏過全體的比例 {pre_w * 100:.0f}%(中位超額 {pre_m * 100:+.1f}%),"
                                  f"展後 {POST} 日 {post_w * 100:.0f}%(中位 {post_m * 100:+.1f}%)") if n_ev else "展覽日期還沒填"),
        ("ok", f"<b>接下來三個月({mtxt})</b>:歷史上常贏的有 {len(top)} 格、常輸的 {len(bot)} 格(見下表);"
               f"營收旺季落在這三個月的個股 {len(hotrev)} 檔"),
        ("wn", "大盤自己的習性比族群明顯:哪幾個月大型股帶指數、哪幾個月中小型股比較強,看「大盤自己」那張表"),
        ("xx", f"大盤燈號 {lamp or '—'}:系統規則是禁開新倉。季節性是機率上的習性,不是進場訊號"),
    ]), src=f"●系統日線、月營收,至 {last:%m/%d}", extra_cls="grow")
    c_num = card("🔢 驗證的數字", bignums([
        ("前半段常贏的格子", f"{r_hot * 100:.0f}%", f"後半段贏率;超額 {a_hot * 100:+.1f}%/月"),
        ("前半段常輸的格子", f"{r_cold * 100:.0f}%", f"後半段贏率;超額 {a_cold * 100:+.1f}%/月"),
        ("個股幾乎每年都贏", f"{act:.0f} 檔次", f"純運氣期望 {exp:.0f}"),
        ("展前贏過全體", "—" if not n_ev else f"{pre_w * 100:.0f}%", "—" if not n_ev else f"展後 {post_w * 100:.0f}%")]))
    c_lim = card("⚠️ 讀這張要注意", checks([
        ("wn", f"樣本只有 {y1.year - y0.year + 1} 年:一格「9/12」和「6/12」的差別,有不小的機率只是運氣;表上有 {len(Sd[Sd.n >= MINY])} 格,光靠運氣也會出現一些很紅很綠的格子"),
        ("wn", "手寫族群的成員是現在挑的(裡面多半是後來漲上來的公司),全年贏率偏高;已下市的公司不在資料裡"),
        ("wn", "營收季節指數只有 2~3 年樣本;農曆年落在 1 月或 2 月會讓這兩個月的指數互相移動"),
        ("wn", "展覽對應的族群是我配的;展覽日期標 ? 的沒有查到來源。展覽前後的漲跌也可能只是當時大盤或財報的影響"),
        ("wn", "全部用收盤價、等權平均,沒有扣交易成本;小型股的等權報酬實際上不一定買得到"),
    ]), extra_cls="risk")

    html = shell_flow(
        title_html="季節性與展覽:<b>哪個月份、哪個族群</b>",
        subtitle=(f"族群的月份習性有一點延續性(前半段常贏的格子,後半段贏率 {r_hot * 100:.0f}% 對全體 {r_all * 100:.0f}%);個股層級是雜訊。"
                  + (f"{len(EXPO)} 個展覽的展前 {PRE} 日,對應族群贏過全體的比例 {pre_w * 100:.0f}%、展後 {post_w * 100:.0f}%" if n_ev else "")),
        brand="季節×展覽",
        blocks=[("wide", c_tree), ("wide", row([c_concl, c_num + c_lim])), ("wide", c_expo), ("wide", c_next), ("wide", c_mkt), ("wide", c_ht), ("wide", c_hs),
                ("wide", c_rev), ("wide", c_hot)],
        footer=f"{now_tw():%Y/%m/%d} · 資料:系統日線(到 {last:%m/%d})、月營收;展覽日期為 2026/11/24 網路查詢 · 研究筆記,非投資建議",
        kind="event")
    pd.set_option("display.width", 250, "display.max_rows", 300, "display.max_columns", 40)
    print("== 驗證 ==", dict(cells=len(v), hot=len(hot), r_hot=round(r_hot, 3), cold=len(cold), r_cold=round(r_cold, 3), r_all=round(r_all, 3),
                           a_hot=round(a_hot, 4), a_cold=round(a_cold, 4), stock_act=act, stock_exp=round(exp, 1)))
    print("== 只看最新一年 ==", ty, dict(hot_n=len(yh), hot=round(ty_hot, 3), cold_n=len(yc), cold=round(ty_cold, 3), all=round(ty_all, 3)))
    print("== 接下來三個月 ==", nxt)
    print(top[["kind", "g", "m", "n", "win", "avg", "w1", "n1", "w2", "n2"]].round(3).to_string(index=False))
    print(bot[["kind", "g", "m", "n", "win", "avg", "w1", "n1", "w2", "n2"]].round(3).to_string(index=False))
    print("== 營收旺季個股 ==", len(hotrev))
    print(hotrev[["name", "sector", "si", "lo", "peak", "amt20", "r60"]].round(2).to_string())
    print("== 展覽彙總 ==", dict(n=n_ev, pre_w=round(pre_w, 3), post_w=round(post_w, 3), pre_m=round(pre_m, 4), post_m=round(post_m, 4)))
    if len(SM):
        print(SM.round(3).to_string(index=False))
    return str(save_poster("季節與展覽", f"{now_tw():%Y%m%d}", html))


if __name__ == "__main__":
    print(main())

# -*- coding: utf-8 -*-
"""每日掃描海報:轉虧為盈 + 三率三升——誰開始賺錢、股價還沒動。
起因:2026-11-24 使用者:「我這邊有三率三升的資訊嗎 誰是開始賺錢股價卻一直沒動(應該換句話說 誰準備轉虧為盈)」。
系統原本只有季報資料(data/bulk_fin/fin_q_all.csv.gz:毛利率、營益率、淨利率、EPS),沒有這張榜;這支把它做出來。
全部每次重算,只讀本機檔案,不發請求。定義(「本業」= 營益率,避開業外一次性):
  A 剛轉盈   :最新一季營益率 > 0、EPS > 0;上一季營益率 ≤ 0;再往前四季至少三季營益率 ≤ 0
  B 轉盈第二季:最近兩季營益率 > 0、最新 EPS > 0;再往前四季至少三季營益率 ≤ 0(第三季前那一季必須是虧)
  C 準備轉盈 :最新一季營益率 < 0,但連兩季收斂、單季營收年增,而且「再改善一次同樣幅度就過零」
  S 三率三升 :毛利率、營益率、淨利率三個都比上一季高、也比去年同季高
  股價沒動   :近 FLAT_N 個交易日漲幅 ≤ FLAT_TH
  濃縮名單   :A/B/C + 股價沒動 + 20 日均成交值 ≥ LIQ 億 + 沒被處置 + 最新月營收年增 > 0
金融保險(沒有毛利率概念)和建材營造(完工入帳,單季盈虧跳動不代表轉機)不列入。
歷史驗證:2024 Q2 起每一季,財報截止日後第一個交易日收盤買進,看之後 60 個交易日,和全部個股同期中位數比。
2026-11-24 使用者追問:「另外是族群? 族群整個對應上你剛才說的嗎? 還有一個問題 不是單次的吧」→ 加三塊:
  族群彙總:官方產業 + theme_groups 的手寫族群,各算「合計三率」(成員營收加權)和「個股三率三升比例」;兩個都成立才算整個族群對得上
  是不是只賺一季:歷史上各類「下一季營益率還是正的」比例,和全部賺錢/虧錢公司對照;個股另標「2023 起賺了又虧幾次」
  景氣循環(同日追問「族群看到了 一堆景氣循環」):族群表標出循環族群,並列合計毛利率在 2023 Q1 以來各季排第幾高
  不是做一次就放著:run_daily Step 5.8621 每天在 bulk 財報更新後重產,只留最新一份
手動重跑:python -X utf8 make_poster_turnaround.py      驗證點:印出的「歷史驗證表」「濃縮名單」= 海報上的兩張表"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import make_poster_gapup as gp
from poster import bignums, card, checks, row, save_poster, shell_flow, slink
from twtime import now_tw

D = Path(__file__).parent / "data"
EXC = {"金融保險業", "建材營造業"}
FLAT_N, FLAT_TH = 120, 0.10
LIQ = 0.5
HOLD = 60
GMIN, GTOP = 8, 5      # 歷史驗證的族群:成員 ≥ GMIN 檔的官方產業裡,三率三升比例最高的 GTOP 個
# 景氣循環族群:手寫族群沿用錯殺海報(make_poster_wronged.CYC)的清單;官方產業是我憑產業常識挑的,可能有錯
CYC = {"記憶體", "PCB", "ABF載板", "封測", "被動元件", "矽晶圓", "晶圓代工", "功率半導體", "石英元件",
       "面板/電子紙", "貨櫃航運", "散裝航運", "鋼鐵", "塑化(大宗)",
       "航運業", "鋼鐵工業", "塑膠工業", "水泥工業", "造紙工業", "玻璃陶瓷", "橡膠工業", "化學工業"}
GN = {"A": "剛轉盈", "B": "轉盈第二季", "C": "準備轉盈", "S": "三率三升"}


def qlab(qe: str) -> str:
    return f"{qe[:4]} Q{int(qe[5:7]) // 3}"


def deadline(qe: str) -> pd.Timestamp:
    y, m = int(qe[:4]), int(qe[5:7])
    return pd.Timestamp({3: f"{y}-05-15", 6: f"{y}-08-14", 9: f"{y}-11-14", 12: f"{y + 1}-03-31"}[m])


def load_fin():
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    q.columns = ["code", "q", "rev", "gm", "om", "nm", "eps"]
    sl = pd.read_csv(D / "stock_list.csv", dtype=str, encoding="utf-8-sig").drop_duplicates("code").set_index("code")
    F = {k: q.pivot_table(index="code", columns="q", values=k, aggfunc="last") for k in ["rev", "gm", "om", "nm", "eps"]}
    qs = sorted(q.q.unique())
    ok = [c for c in F["om"].index if c in sl.index and pd.notna(sl.sector[c]) and sl.sector[c] not in EXC]
    return F, qs, sl, ok


def flags(F: dict, qs: list, ok: list, j: int) -> pd.DataFrame:
    """第 j 季(qs[j])公布後看得到的分類。"""
    def g(k, b):
        return F[k][qs[j - b]].reindex(ok) if j - b >= 0 else pd.Series(np.nan, index=ok)
    om = [g("om", b) for b in range(6)]
    loss14 = sum((om[b] <= 0).astype(int) for b in (1, 2, 3, 4))
    loss25 = sum((om[b] <= 0).astype(int) for b in (2, 3, 4, 5))
    a = (om[0] > 0) & (g("eps", 0) > 0) & (om[1] <= 0) & (loss14 >= 3)
    b = (om[0] > 0) & (om[1] > 0) & (g("eps", 0) > 0) & (om[2] <= 0) & (loss25 >= 3)
    c = (om[0] < 0) & (om[0] > om[1]) & (om[1] > om[2]) & (g("rev", 0) > g("rev", 4)) & (om[0] + (om[0] - om[1]) >= 0)
    s = pd.Series(True, index=ok)
    for k in ("gm", "om", "nm"):
        s &= (g(k, 0) > g(k, 1)) & (g(k, 0) > g(k, 4))
    return pd.DataFrame({"A": a, "B": b, "C": c, "S": s})


def history(F, qs, ok, C: pd.DataFrame, sec: pd.Series) -> pd.DataFrame:
    rows = []
    for j in range(5, len(qs) - 1):
        f = flags(F, qs, ok, j)
        i = int(np.searchsorted(C.index.values, np.datetime64(deadline(qs[j])), side="right"))
        if i + HOLD >= len(C):
            continue
        r = (C.iloc[i + HOLD] / C.iloc[i] - 1).reindex(ok)
        pre = (C.iloc[i] / C.iloc[i - FLAT_N] - 1).reindex(ok)
        rec = dict(q=qs[j], buy=C.index[i], allmed=r.median())
        for k in "ABCS":
            x, xf = r[f[k]].dropna(), r[f[k] & (pre <= FLAT_TH)].dropna()
            rec.update({k + "_n": len(x), k + "_med": x.median(), k + "_fn": len(xf), k + "_fmed": xf.median()})
        sh = f.S.groupby(sec).agg(["mean", "size"])
        top = sh[sh["size"] >= GMIN].sort_values("mean", ascending=False).head(GTOP).index
        x = r[sec.isin(top)].dropna()
        rec.update(G_n=len(x), G_med=x.median(), G_top="、".join(top))
        rows.append(rec)
    return pd.DataFrame(rows)


def persist(F, qs, ok) -> pd.DataFrame:
    """是不是只賺一季:歷史上每一類,下一季(n1/p1)和連續兩季(n2/p2)營益率是正的檔數。賺/虧=當季本業賺、虧的全部個股(對照組)。"""
    rows = []
    for j in range(5, len(qs) - 1):
        f = flags(F, qs, ok, j)
        om0, n1 = F["om"][qs[j]].reindex(ok), F["om"][qs[j + 1]].reindex(ok)
        n2 = F["om"][qs[j + 2]].reindex(ok) if j + 2 < len(qs) else None
        for k, m in {"A": f.A, "B": f.B, "C": f.C, "賺": om0 > 0, "虧": om0 <= 0}.items():
            m1 = m & n1.notna()
            rec = dict(grp=k, n1=int(m1.sum()), p1=int((n1[m1] > 0).sum()), n2=0, p2=0)
            if n2 is not None:
                m2 = m1 & n2.notna()
                rec.update(n2=int(m2.sum()), p2=int(((n1 > 0) & (n2 > 0))[m2].sum()))
            rows.append(rec)
    return pd.DataFrame(rows).groupby("grp")[["n1", "p1", "n2", "p2"]].sum()


def group_table(t: pd.DataFrame, members: dict, F: dict, qs: list) -> pd.DataFrame:
    """族群彙總:合計三率=成員營收加權;hit=合計三率三升 且 過半成員個股也三率三升。
    gm_rank=最新一季的合計毛利率在有資料的各季裡排第幾高(1=最高),用來看循環股是不是在自己的高檔。"""
    need = [k + b for k in ("rev", "gm", "om", "nm") for b in "014"]
    rows = []
    for g, ms in members.items():
        d = t.loc[[c for c in dict.fromkeys(ms) if c in t.index]]
        d = d[d[need].notna().all(axis=1)]
        if len(d) < 3:
            continue
        ag = {k + b: float((d["rev" + b] * d[k + b]).sum() / d["rev" + b].sum()) for k in ("gm", "om", "nm") for b in "014"}
        up = all(ag[k + "0"] > ag[k + "1"] and ag[k + "0"] > ag[k + "4"] for k in ("gm", "om", "nm"))
        hist = {}
        for q_ in qs:
            r_, g_ = F["rev"][q_].reindex(d.index), F["gm"][q_].reindex(d.index)
            m_ = r_.notna() & g_.notna() & (r_ > 0)
            if m_.sum() >= max(2, len(d) // 2):
                hist[q_] = float((r_[m_] * g_[m_]).sum() / r_[m_].sum())
        hs = pd.Series(hist)
        rows.append(dict(g=g, n=len(d), **ag, up=up, cyc=g in CYC, gm_rank=int((hs > hs.iloc[-1]).sum()) + 1, gm_nq=len(hs),
                         gm_lo=float(hs.min()), gm_md=float(hs.median()), nS=int(d.S.sum()), sS=float(d.S.mean()), nT=int((d.grp != "").sum()),
                         turn=bool(ag["om0"] > 0 and (ag["om1"] <= 0 or ag["om4"] <= 0)), r120=float(d.r120.median()),
                         names="、".join(d[d.S]["name"]), tnames="、".join(d[d.grp != ""]["name"])))
    G = pd.DataFrame(rows)
    G["hit"] = G.up & (G.sS >= 0.5)
    return G.sort_values(["hit", "sS", "n"], ascending=[False, False, False]).reset_index(drop=True)


def pc(x, d=0) -> str:
    return gp.pc(x, d)


def px(x) -> str:
    return "—" if pd.isna(x) else f"{x:g}"


def amt(x) -> str:
    return "—" if pd.isna(x) else f"{x:.2f}"


def seq(vals) -> str:
    out = []
    for i, v in enumerate(vals):
        t = "—" if pd.isna(v) else (f"{v:.0f}" if abs(v) >= 100 else f"{v:.1f}")
        cls = "" if pd.isna(v) else ("gn" if v < 0 else "rd")
        t = f'<span class="{cls}">{t}</span>'
        out.append(f"<b>{t}</b>" if i == len(vals) - 1 else t)
    return "/".join(out)


def main(quiet: bool = False) -> str:
    F, qs, sl, ok = load_fin()
    P = gp.panel()
    C, H, V = P["Close"], P["High"], P["Volume"]
    last = C.index[-1]
    L = len(qs) - 1
    f = flags(F, qs, ok, L)
    # ── 現況表 ──
    t = pd.DataFrame({"name": sl.name.reindex(ok), "sector": sl.sector.reindex(ok)})
    for k in ("om", "eps", "rev", "gm", "nm"):
        for b in range(5):
            t[f"{k}{b}"] = F[k][qs[L - b]].reindex(ok)
    Cf = C.ffill(limit=5)
    t["px"] = Cf.iloc[-1].reindex(ok)
    t["r60"] = (Cf.iloc[-1] / Cf.iloc[-61] - 1).reindex(ok)
    t["r120"] = (Cf.iloc[-1] / Cf.iloc[-1 - FLAT_N] - 1).reindex(ok)
    t["offhi"] = (Cf.iloc[-1] / H.iloc[-252:].max() - 1).reindex(ok)
    t["amt20"] = ((C.iloc[-20:] * V.iloc[-20:]).mean() / 1e8).reindex(ok)
    t["rev_yoy"] = t.rev0 / t.rev4 - 1
    rv = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    ym = rv.ym.max()
    t["m_yoy"] = rv[rv.ym == ym].drop_duplicates("code").set_index("code")["yoy%"].reindex(ok) / 100
    try:
        dis = set(pd.read_csv(D / "_disposal_now.csv", dtype=str).query("end >= @last.strftime('%Y-%m-%d')").code)
    except Exception:
        dis = set()
    t["dis"] = t.index.isin(dis)
    t = t.join(f)
    t["grp"] = np.select([t.A, t.B, t.C], ["A", "B", "C"], "")
    t["flat"] = t.r120 <= FLAT_TH
    t["liq"] = t.amt20 >= LIQ
    t["pick"] = (t.grp != "") & t.flat & t.liq & ~t.dis & (t.m_yoy > 0) & t.px.notna()
    # 三率三升:另外看是不是連兩季(上一季也比上上季高)
    t["S2"] = t.S & (t.gm1 > t.gm2) & (t.om1 > t.om2) & (t.nm1 > t.nm2)
    om_all = F["om"].reindex(ok)[qs[:L + 1]].values
    t["flip"] = ((om_all[:, :-1] > 0) & (om_all[:, 1:] <= 0)).sum(axis=1)      # 2023 Q1 起「本業賺了、下一季又虧」的次數
    t["spick"] = t.S2 & t.flat & t.liq & ~t.dis & (t.m_yoy > 0) & (t.eps0 > t.eps4) & (t.eps0 > 0) & t.px.notna()
    t.round(4).to_csv(D / "_turnaround_scan.csv", encoding="utf-8-sig")
    mth = int(ym[5:7])

    def note(r) -> str:
        n = []
        if pd.isna(r.px):
            return "本機沒有這檔的日線"
        if r.dis:
            n.append("處置中")
        if pd.notna(r.r120) and r.r120 > FLAT_TH:
            n.append(f"已漲 {r.r120 * 100:+.0f}%")
        if not r.liq:
            n.append("成交值不足")
        if pd.notna(r.m_yoy) and r.m_yoy <= 0:
            n.append(f"{mth} 月營收年減")
        if r.grp in ("A", "B") and r.om4 > 0:
            n.append("去年同季也賺")
        if r.grp in ("A", "B") and r.eps0 < 0.1:
            n.append("EPS 不到 0.1")
        if r.grp == "C" and r.eps0 > 0:
            n.append("EPS 是正的(靠業外)")
        if r.flip >= 1:
            n.append(f"之前賺了又虧 {int(r.flip)} 次")
        return "、".join(n)

    TB = '<table style="font-size:12.5px">'
    HEAD = ("<tr><th>代號 名稱</th><th>營益率近 5 季(%)</th><th>EPS 上季→最新</th><th>季營收年增</th>"
            f"<th>{mth} 月營收年增</th><th>收盤</th><th>60 日</th><th>{FLAT_N} 日</th><th>離年高</th><th>成交值(億)</th>")

    def tr(c, r, extra="", hl=False) -> str:
        return (f'<tr{" class=yl" if hl else ""}><td style="white-space:nowrap"><b>{slink(c, c + " " + r["name"])}</b><br><small>{r.sector}</small></td>'
                f'<td class="n">{seq([r.om4, r.om3, r.om2, r.om1, r.om0])}</td>'
                f'<td class="n">{r.eps1:.2f} → <b>{r.eps0:.2f}</b></td><td class="n">{pc(r.rev_yoy)}</td><td class="n">{pc(r.m_yoy)}</td>'
                f'<td class="n">{px(r.px)}</td><td class="n">{pc(r.r60)}</td><td class="n">{pc(r.r120)}</td><td class="n">{pc(r.offhi)}</td>'
                f'<td class="n">{amt(r.amt20)}</td>{extra}</tr>')

    pick = t[t.pick].sort_values(["grp", "amt20"], ascending=[True, False])
    th = TB + HEAD + "<th>類型</th><th>之前賺了又虧</th></tr>"
    for c, r in pick.iterrows():
        th += tr(c, r, f'<td>{GN[r.grp]}</td><td class="n">{int(r.flip)} 次</td>')
    th += "</table>"
    n_grp = {k: int((t.grp == k).sum()) for k in "ABC"}
    c_hero = card(f"📋 濃縮名單:轉盈或準備轉盈的 {sum(n_grp.values())} 檔裡,股價沒動、有成交量、營收還在增的 {len(pick)} 檔", th
                  + f'<div class="note">●條件:A/B/C 三類之一 + 近 {FLAT_N} 個交易日漲幅 ≤ {FLAT_TH * 100:.0f}% + 20 日均成交值 ≥ {LIQ} 億 + 沒被處置 + {mth} 月營收年增 &gt; 0。'
                    f"營益率五個數字由舊到新,最右邊粗體是最新一季;成交值是 20 日平均。依類型、成交值排序,不是推薦順序。營益率和 EPS 是系統季報(到 {qlab(qs[L])}),股價到 {last:%m/%d} 收盤。"
                    "「之前賺了又虧」= 2023 Q1 以來本業賺了、下一季又轉虧的次數,次數多的代表以前也轉盈過但沒撐住。"
                    "我沒有逐檔查轉盈的原因(一次性收入、匯兌、認列時點都可能造成單季轉正)。</div>",
                  f"至 {last:%m/%d} 收盤")

    def full(k: str, title: str, rule: str) -> str:
        d = t[t.grp == k].sort_values(["pick", "amt20"], ascending=[False, False])
        s = TB + HEAD + "<th>沒進濃縮名單的原因/註記</th></tr>"
        for c, r in d.iterrows():
            s += tr(c, r, f"<td>{note(r) or ('—' if r.pick else '')}</td>", hl=bool(r.pick))
        return card(f"{title}:{len(d)} 檔(黃底 {int(d.pick.sum())} 檔在濃縮名單)", s + f'</table><div class="note">●{rule} 依「是否在濃縮名單、成交值」排序,全部列出。</div>')

    c_a = full("A", "🅰 剛轉盈", "最新一季營益率 > 0、EPS > 0;上一季營益率 ≤ 0;再往前四季至少三季營益率 ≤ 0。")
    c_b = full("B", "🅱 轉盈第二季", "最近兩季營益率 > 0、最新 EPS > 0;再往前四季至少三季營益率 ≤ 0。")
    c_c = full("C", "🅲 準備轉盈(還在虧)", "最新一季營益率 < 0,連兩季收斂、單季營收年增,而且再改善一次同樣幅度就過零——這是外推,不是公司說的。")

    # ── 歷史驗證 ──
    h = history(F, qs, ok, C, sl.sector.reindex(ok))
    tv = (TB + "<tr><th>財報季</th><th>買進日</th><th>全部個股</th>" + "".join(f"<th>{GN[k]}</th>" for k in "ABCS")
          + f"<th>三率三升比例最高的 {GTOP} 個產業(全部成員)</th></tr>")
    for _, r in h.iterrows():
        tv += (f'<tr><td class="n">{qlab(r.q)}</td><td class="n">{r.buy:%Y/%m/%d}</td><td class="n">{pc(r.allmed, 1)}</td>'
               + "".join(f'<td class="n">{pc(r[k + "_med"], 1)}<br><small>{int(r[k + "_n"])} 檔</small></td>' for k in "ABCS")
               + f'<td>{pc(r.G_med, 1)}<br><small>{r.G_top}</small></td></tr>')
    beat = {k: int((h[k + "_med"] > h.allmed).sum()) for k in "ABCSG"}
    fbeat = {k: int((h[k + "_fmed"] > h.allmed).sum()) for k in "ABCS"}
    edge = {k: float((h[k + "_med"] - h.allmed).median()) for k in "ABCSG"}
    fedge = {k: float((h[k + "_fmed"] - h.allmed).median()) for k in "ABCS"}
    nq = len(h)
    tv += (f'<tr class="yl"><td colspan="3"><b>{nq} 季裡,中位數贏過全部個股的季數</b></td>'
           + "".join(f'<td class="n"><b>{beat[k]} 季</b><br><small>差距中位 {edge[k] * 100:+.1f} 點</small></td>' for k in "ABCSG") + "</tr>"
           f'<tr><td colspan="3">只算「財報前 {FLAT_N} 日漲不到 {FLAT_TH * 100:.0f}%」的</td>'
           + "".join(f'<td class="n">{fbeat[k]} 季<br><small>{fedge[k] * 100:+.1f} 點</small></td>' for k in "ABCS") + "<td>—</td></tr></table>")
    c_hist = card(f"🧪 過去 {nq} 季驗證:財報出來後買進,{HOLD} 個交易日後", tv
                  + f'<div class="note">●每格是那一類股票 {HOLD} 個交易日報酬的中位數。買進日=財報截止日(5/15、8/14、11/14、3/31)後第一個交易日收盤。'
                    f"最右欄=成員 {GMIN} 檔以上的官方產業裡,那一季個股三率三升比例最高的 {GTOP} 個產業,買進全部成員(不管個股自己有沒有三率三升)。"
                    "季報資料從 2023 Q1 開始,分類要往前看六季,所以只能從 2024 Q2 驗起。用的是現在還在的股票和現在存的季報數字,沒有扣手續費和稅。</div>",
                  "系統季報+日線")

    # ── 三率三升 ──
    nS, nS2 = int(t.S.sum()), int(t.S2.sum())
    sp = t[t.spick].sort_values("amt20", ascending=False)
    ts = (TB + "<tr><th>代號 名稱</th><th>毛利率(%)去年同季→最新</th><th>營益率(%)</th><th>淨利率(%)</th><th>EPS 去年同季→最新</th>"
          f"<th>{mth} 月營收年增</th><th>收盤</th><th>{FLAT_N} 日</th><th>離年高</th><th>成交值(億)</th></tr>")
    for c, r in sp.iterrows():
        ts += (f'<tr><td style="white-space:nowrap"><b>{slink(c, c + " " + r["name"])}</b><br><small>{r.sector}</small></td>'
               f'<td class="n">{r.gm4:.1f}→<b>{r.gm0:.1f}</b></td><td class="n">{r.om4:.1f}→<b>{r.om0:.1f}</b></td>'
               f'<td class="n">{r.nm4:.1f}→<b>{r.nm0:.1f}</b></td><td class="n">{r.eps4:.2f}→<b>{r.eps0:.2f}</b></td>'
               f'<td class="n">{pc(r.m_yoy)}</td><td class="n">{px(r.px)}</td><td class="n">{pc(r.r120)}</td><td class="n">{pc(r.offhi)}</td><td class="n">{amt(r.amt20)}</td></tr>')
    ts += "</table>"
    c_s = card(f"📈 三率三升:{qlab(qs[L])} 有 {nS} 檔,連兩季的 {nS2} 檔;其中股價沒動、有量、營收和 EPS 都年增的 {len(sp)} 檔", ts
               + f'<div class="note">●三率三升=毛利率、營益率、淨利率都比上一季高、也比去年同季高;連兩季=上一季對上上季也是三個都升。'
                 f"這張表的條件:連兩季三率三升 + 近 {FLAT_N} 日漲幅 ≤ {FLAT_TH * 100:.0f}% + 20 日均成交值 ≥ {LIQ} 億 + 沒被處置 + {mth} 月營收年增 &gt; 0 + EPS 高於去年同季。"
                 f"依成交值排序。全部 {nS} 檔在 data/_turnaround_scan.csv(S 欄)。</div>")

    # ── 族群彙總 ──
    import theme_groups as tg
    secs = {k: list(v.index) for k, v in t.groupby("sector")}
    GT, GS = group_table(t, tg.THEME_GROUPS, F, qs[:L + 1]), group_table(t, secs, F, qs[:L + 1])
    pd.concat([GT.assign(kind="手寫族群"), GS.assign(kind="官方產業")]).round(4).to_csv(D / "_turnaround_groups.csv", encoding="utf-8-sig", index=False)

    def gcard(G: pd.DataFrame, title: str, names: bool, extra: str) -> str:
        s = (TB + "<tr><th>族群</th><th>檔數</th><th>合計毛利率(%)去年同季→上季→最新</th><th>合計營益率(%)</th><th>合計淨利率(%)</th>"
             "<th>毛利率在自己歷史的位置</th>"
             f"<th>合計三率</th><th>個股三率三升</th><th>轉盈類</th><th>{FLAT_N} 日中位</th>" + ("<th>三率三升的成員</th>" if names else "<th>轉盈類的成員</th>") + "</tr>")
        for _, r in G.iterrows():
            f3 = lambda k: f'{r[k + "4"]:.1f}→{r[k + "1"]:.1f}→<b>{r[k + "0"]:.1f}</b>'
            mark = "✔ 三升" if r.up else ("由虧轉盈" if r.turn else "—")
            s += (f'<tr{" class=yl" if r.hit else ""}><td style="white-space:nowrap"><b>{r.g}</b>{"<br><small>景氣循環</small>" if r.cyc else ""}</td><td class="n">{r.n}</td><td class="n">{f3("gm")}</td><td class="n">{f3("om")}</td>'
                  f'<td class="n">{f3("nm")}</td><td>{"<b>" + str(r.gm_nq) + " 季最高</b>" if r.gm_rank == 1 else f"第 {r.gm_rank} 高"}<br><small>最低 {r.gm_lo:.0f}、中位 {r.gm_md:.0f}</small></td><td>{mark}</td><td class="n">{r.nS}/{r.n}({r.sS * 100:.0f}%)</td><td class="n">{r.nT}</td>'
                  f'<td class="n">{pc(r.r120)}</td><td><small>{(r.names if names else r.tnames) or "—"}</small></td></tr>')
        return card(f"{title}:{len(G)} 個裡,整個族群對得上的 {int(G.hit.sum())} 個(黃底)", s + f'</table><div class="note">●{extra}</div>')

    rule_g = ("合計三率=成員營收加權(整個族群的毛利、營業利益、淨利 ÷ 整個族群的營收),所以會被最大的那一家帶著走;"
              "「合計三率 ✔ 三升」=合計的三個比率都高於上季和去年同季。"
              "「毛利率在自己歷史的位置」=最新一季的合計毛利率在 2023 Q1 以來各季裡排第幾高;標「景氣循環」的族群,毛利率跟著報價走,排在最高時要當成循環位置的提醒。黃底=合計三升,而且過半成員自己也三率三升。依個股三率三升比例排序,全部列出。")
    c_gt = gcard(GT, "🧩 族群(系統手寫的題材族群)", True, rule_g + f"族群成員來自 theme_groups.py({len(tg.THEME_GROUPS)} 個,有季報的成員不到 3 檔的不列)。")
    c_gs = gcard(GS, "🏭 官方產業", False, rule_g + "金融保險、建材營造不列入。")
    hitT, hitS = list(GT[GT.hit].g), list(GS[GS.hit].g)
    turnG = list(GT[GT.turn].g) + list(GS[GS.turn].g)
    GH = pd.concat([GT[GT.hit], GS[GS.hit]])
    n_cyc, n_top = int(GH.cyc.sum()), int((GH.gm_rank == 1).sum())

    # ── 是不是只賺一季 ──
    ps = persist(F, qs, ok)
    rate = lambda k, a, b: (ps.loc[k, a] / ps.loc[k, b]) if ps.loc[k, b] else np.nan
    LAB = [("A", "剛轉盈"), ("B", "轉盈第二季"), ("C", "準備轉盈(下一季真的轉正)"), ("賺", "對照:當季本業賺的全部個股"), ("虧", "對照:當季本業虧的全部個股")]
    tp = "<table><tr><th>當季的分類</th><th>下一季營益率是正的</th><th>連續兩季都是正的</th></tr>"
    for k, lab in LAB:
        tp += (f'<tr><td>{lab}</td><td class="n"><b>{gp.sh(rate(k, "p1", "n1"))}</b> <small>({int(ps.loc[k, "p1"])}/{int(ps.loc[k, "n1"])})</small></td>'
               f'<td class="n">{gp.sh(rate(k, "p2", "n2"))} <small>({int(ps.loc[k, "p2"])}/{int(ps.loc[k, "n2"])})</small></td></tr>')
    nflip = int((t[t.grp.isin(["A", "B"])].flip >= 2).sum())
    c_pers = card("🔁 是不是只賺一季?", tp + "</table>"
                  + f'<div class="note">●2024 Q2~{qlab(qs[L - 1])} 各季的轉盈股合併計算,看它之後一季、兩季的營益率。'
                    f"這一季剛轉盈、轉盈第二季的 {n_grp['A'] + n_grp['B']} 檔裡,2023 年以來已經「賺了又虧」兩次以上的有 {nflip} 檔(各表的註記欄有標)。</div>")

    # ── 沒列入的 ──
    ex = t[(t.grp != "") & ~t.pick]
    why = {"已經漲過(近 %d 日超過 %+.0f%%)" % (FLAT_N, FLAT_TH * 100): int((~ex.flat).sum()), "成交值不到 %.1f 億" % LIQ: int((~ex.liq).sum()),
           f"{mth} 月營收年減": int((ex.m_yoy <= 0).sum()), "處置中": int(ex.dis.sum())}
    med_all = float(t.r120.median())
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    bm120 = float(bm.iloc[-1] / bm.iloc[-1 - FLAT_N] - 1)
    lamp = ""
    try:
        import json
        lamp = json.load(open(D / "_market_risk.json", encoding="utf-8")).get("lamp", "")
    except Exception:
        pass
    c_concl = card("📌 結論(重點先看)", checks([
        ("ok", f"<b>系統原本沒有三率三升榜</b>,只有季報資料(毛利率、營益率、淨利率、EPS,{len(t):,} 檔,到 {qlab(qs[L])})。這張把它算出來:"
               f"三率三升 {nS} 檔、連兩季 {nS2} 檔"),
        ("ok", f"<b>轉虧為盈</b>(看本業營益率,不看業外):剛轉盈 {n_grp['A']} 檔、轉盈第二季 {n_grp['B']} 檔、還在虧但快過零的 {n_grp['C']} 檔,"
               f"合計 {sum(n_grp.values())} 檔;過完四個條件剩 <b>{len(pick)} 檔</b>"),
        ("xx", f"<b>過去 {nq} 季,轉盈之後股價沒有比較好</b>:財報出來後買進抱 {HOLD} 個交易日,剛轉盈只有 {beat['A']} 季贏過全部個股的中位數、"
               f"轉盈第二季 {beat['B']} 季、準備轉盈 {beat['C']} 季;差距中位數 {edge['A'] * 100:+.1f}、{edge['B'] * 100:+.1f}、{edge['C'] * 100:+.1f} 個百分點"),
        ("wn", f"<b>「股價還沒動」也沒有加分</b>:只算財報前 {FLAT_N} 日漲不到 {FLAT_TH * 100:.0f}% 的,剛轉盈 {fbeat['A']} 季贏、轉盈第二季 {fbeat['B']} 季、準備轉盈 {fbeat['C']} 季"),
        ("ok" if beat["S"] > nq / 2 else "wn",
         f"<b>三率三升比較穩,但差距小</b>:{nq} 季裡 {beat['S']} 季贏過全部個股,差距中位數只有 {edge['S'] * 100:+.1f} 個百分點"),
        ("wn", f"<b>不是都能撐住</b>:過去剛轉盈的,下一季本業還賺的只有 {gp.sh(rate('A', 'p1', 'n1'))}、連兩季都賺的 {gp.sh(rate('A', 'p2', 'n2'))};"
               f"已經轉盈兩季的,第三季還賺的 {gp.sh(rate('B', 'p1', 'n1'))}(一般賺錢公司是 {gp.sh(rate('賺', 'p1', 'n1'))})"),
        ("ok" if hitT or hitS else "wn",
         "<b>整個族群對得上的</b>(合計三率三升,而且過半成員自己也三率三升):"
         + ("、".join(hitT + hitS) if hitT or hitS else "沒有") + ";整個族群合計由虧轉盈的:" + ("、".join(turnG) if turnG else "沒有")),
        ("xx" if len(GH) and n_cyc >= len(GH) / 2 else "wn",
         f"<b>對得上的 {len(GH)} 個族群裡 {n_cyc} 個是景氣循環</b>,其中 {n_top} 個的合計毛利率是 2023 年以來最高。"
         "循環股在報價上漲時三率三升最漂亮,這張表分不出是剛起漲還是高峰;要配報價、庫存、資本支出這些領先指標看"),
        ("wn", f"<b>挑族群也沒有比較準</b>:每季買三率三升比例最高的 {GTOP} 個產業的全部成員,{nq} 季裡 {beat['G']} 季贏過全部個股,差距中位數 {edge['G'] * 100:+.1f} 個百分點"),
        ("wn", f"現在「沒動」的門檻很鬆:大盤近 {FLAT_N} 日 {bm120 * 100:+.0f}%、全部個股中位數 {med_all * 100:+.0f}%,"
               f"所以名單裡多數是跟著大盤跌,不是市場還沒發現"),
    ]), src=f"●系統季報、月營收、日線,至 {last:%m/%d}", extra_cls="grow")
    c_num = card("🔢 這一季的數量", bignums([
        ("剛轉盈", f"{n_grp['A']} 檔", f"濃縮後 {int((pick.grp == 'A').sum())} 檔"),
        ("轉盈第二季", f"{n_grp['B']} 檔", f"濃縮後 {int((pick.grp == 'B').sum())} 檔"),
        ("準備轉盈", f"{n_grp['C']} 檔", f"濃縮後 {int((pick.grp == 'C').sum())} 檔"),
        ("三率三升", f"{nS} 檔", f"連兩季 {nS2} 檔")])
        + "<table><tr><th>轉盈三類沒進濃縮名單的原因(可重複)</th><th>檔數</th></tr>"
        + "".join(f'<tr><td>{k}</td><td class="n">{v}</td></tr>' for k, v in why.items()) + "</table>")
    c_lim = card("⚠️ 讀這張要注意", checks([
        ("wn", "單季營益率轉正的原因我沒有逐檔查:一次性認列、匯率、淡旺季都會讓單季轉正,下一季再轉負。表上「去年同季也賺」的要特別看是不是季節性"),
        ("wn", "「準備轉盈」是把上一季的改善幅度再外推一次,不是公司的預估;營益率是比率,營收小的公司跳動很大"),
        ("wn", f"驗證只有 {nq} 季(2024 Q2 起),而且這段期間大盤先大漲後大跌;每一類每季只有十幾到幾十檔"),
        ("wn", "金融保險、建材營造不列入;季報用的是系統現在存的數字,公司事後重編的話會和當時公布的不同"),
        ("wn", "轉盈的公司多半很小:沒進濃縮名單的主要原因是成交值不足,進出的量大一點就會動到價格"),
        ("xx", f"大盤燈號 {lamp or '—'}:系統規則是禁開新倉、只出不進。這張是體檢,不是買進名單"),
    ]), extra_cls="risk")

    n_pick = len(pick)
    html = shell_flow(
        title_html="誰開始賺錢、股價還沒動?<b>轉虧為盈 + 三率三升</b>",
        subtitle=(f"{qlab(qs[L])} 本業轉盈或快轉盈的 {sum(n_grp.values())} 檔,過完「股價沒動、有量、營收年增、沒處置」剩 {n_pick} 檔;三率三升 {nS} 檔。"
                  f"但過去 {nq} 季驗證:轉盈之後 {HOLD} 日,只有 {beat['A']}/{nq} 季贏過全部個股"),
        brand="轉盈掃描",
        blocks=[("wide", c_hero), ("wide", row([c_concl, c_num + c_pers + c_lim])), ("wide", c_hist), ("wide", c_gt), ("wide", c_gs),
                ("wide", c_s), ("wide", c_a), ("wide", c_b), ("wide", c_c)],
        footer=f"{now_tw():%Y/%m/%d} · 資料:系統季報(到 {qlab(qs[L])})、月營收(到 {ym})、日線(到 {last:%m/%d}) · 完整數字 data/_turnaround_scan.csv、_turnaround_groups.csv · 每日排程自動重產 · 研究筆記,非投資建議",
        kind="scan")
    date = f"{now_tw():%Y%m%d}"
    for old in (D / "papers").glob("轉虧為盈海報_*.html"):       # 每日重產,只留最新一份;先刪再存,總覽才不會連到被刪的檔
        if old.name != f"轉虧為盈海報_{date}.html":
            old.unlink()
    out = str(save_poster("轉虧為盈", date, html))
    if quiet:
        return out
    # ── 驗證用輸出 ──
    pd.set_option("display.width", 250, "display.max_rows", 300, "display.max_columns", 40)
    print("== 歷史驗證表 ==")
    print(h.assign(q=h.q.map(qlab))[["q", "buy", "allmed"] + [k + s for k in "ABCS" for s in ("_n", "_med")] + ["G_n", "G_med", "G_top"]].round(3).to_string(index=False))
    print("== 是不是只賺一季 ==")
    print(ps.assign(r1=(ps.p1 / ps.n1).round(3), r2=(ps.p2 / ps.n2).round(3)).to_string())
    print("== 族群 ==")
    gc = ["g", "cyc", "gm_rank", "gm_nq", "n", "gm4", "gm1", "gm0", "om4", "om1", "om0", "nm4", "nm1", "nm0", "up", "turn", "nS", "sS", "nT", "r120", "hit"]
    print(GT[gc].round(2).to_string(index=False))
    print(GS[gc].round(2).to_string(index=False))
    print("贏的季數", beat, "沒動的", fbeat, "差距中位", {k: round(v, 3) for k, v in edge.items()})
    print("== 濃縮名單 ==")
    print(pick[["name", "sector", "grp", "om4", "om3", "om2", "om1", "om0", "eps1", "eps0", "rev_yoy", "m_yoy", "px", "r60", "r120", "offhi", "amt20"]].round(3).to_string())
    print("== 三率三升濃縮 ==", nS, nS2, len(sp))
    print(sp[["name", "sector", "gm4", "gm1", "gm0", "om4", "om1", "om0", "eps4", "eps0", "m_yoy", "r120", "amt20"]].round(2).to_string())
    print("沒進名單原因", why)
    return out


if __name__ == "__main__":
    print(main())

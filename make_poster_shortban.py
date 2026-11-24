# -*- coding: utf-8 -*-
"""主題海報:限空令之後,市場多久恢復正常?指數回來了,個股有沒有回來?(2026-11-19)
「今天再次禁空令 分析以往 然後大概要多久 市場才恢復正常」「我們如何在空方市場找到生存之道」
「指數可能會回來 但個股不會」——三句話各對一組統計,全部由這支腳本重算:
  ・加權指數 1997 年起(Yahoo ^TWII,快取 data/_twii_long.csv)× 歷次限空令日期
  ・季線規則(收盤在 60 日線上才持有)在每一次空頭的表現
  ・個股還原價 2015 年起(本機 data/*.csv)——指數回到前高時,個股回到自己前高的比例
手動:python -X utf8 make_poster_shortban.py      (約 2 分鐘,大部分時間在讀個股成交額)"""
import glob
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import insider_pledge as ip
from poster import bignums, card, checks, row, save_poster, shell_flow
from twtime import now_tw

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "_twii_long.csv"
for _k in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    os.environ.setdefault(_k, str(ROOT / "_ca_bundle.pem"))

# (年, 第一項措施生效日, 最重措施解除日, 措施, 背景)。日期來源:經理人月刊整理(沒對金管會原文);2026 為中央社報導
EVENTS = [
    ("1998", "1998-09-04", None, "平盤下不得融券賣出;融券保證金 70→90%", "亞洲金融風暴"),
    ("2000", "2000-10-19", None, "融券保證金 90→120%;10 元以下個股暫停融券", "網路泡沫"),
    ("2008", "2008-09-22", "2008-11-27", "9/22 150 檔平盤下禁空→10/1 全面禁止放空", "金融海嘯"),
    ("2015", "2015-08-24", "2015-09-21", "平盤下禁空;融券保證金 90→120%", "陸股股災"),
    ("2020", "2020-03-19", "2020-06-09", "借券賣出 30→10%;跌 3.5% 隔日平盤下禁空", "新冠疫情"),
    ("2022", "2022-10-03", "2023-02-23", "10/1 借券 20%→10/12 借券 10%→10/21 跌 3.5% 隔日禁空", "升息、俄烏戰爭"),
    ("2025", "2025-04-07", "2025-05-23", "借券賣出 30→3%;融券保證金 90→130%", "美國對等關稅"),
    ("2026", "2026-11-09", None, "11/9 借券 3%、保證金 130%→11/20 借券 1%、跌 3.5% 隔日禁空", "美國科技股走弱"),
]
STOCK_EV = ["2015", "2020", "2022", "2025"]          # 個股資料 2015 年起,只能看這四次
COST = 0.004                                        # 季線規則每次「出場再進場」的來回成本(手續費+ETF 證交稅,約 0.4%)


def pc(x, d=0) -> str:
    if x is None or pd.isna(x):
        return "—"
    c = "rd" if x > 0 else "gn" if x < 0 else ""
    return f'<span class="{c}">{x * 100:+.{d}f}%</span>'


def dy(x) -> str:
    """交易日 → 「N 日(約 M 個月)」"""
    if x is None or pd.isna(x):
        return "還沒"
    x = int(x)
    return f"{x} 日" if x < 15 else f"{x} 日<br><small>約 {x / 21:.0f} 個月</small>" if x < 500 else f"{x} 日<br><small>約 {x / 252:.1f} 年</small>"


def twii() -> pd.Series:
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        d = yf.download("^TWII", start="1997-01-01", auto_adjust=False, progress=False)
        s = d["Close"].squeeze().dropna()
        if len(s) > 7000:
            s.rename("Close").to_csv(CACHE, encoding="utf-8-sig")
    except Exception:
        s = pd.Series(dtype=float)
    if len(s) < 7000:
        s = pd.read_csv(CACHE, index_col=0, parse_dates=True)["Close"]
    loc = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", parse_dates=["Date"]).set_index("Date")["Close"]
    return loc.combine_first(s).sort_index()         # 近年以本機檔為準(兩者 2015 年後完全相同)


def event_stats(s: pd.Series) -> pd.DataFrame:
    ma60, ma240 = s.rolling(60).mean(), s.rolling(240).mean()
    on5 = (s > ma60).astype(int).rolling(5).sum() == 5
    rows = []
    for name, d0, d1, what, why in EVENTS:
        i0 = s.index.searchsorted(pd.Timestamp(d0))
        base = s.iloc[i0 - 1]                                 # 生效前一天收盤
        pk = s.iloc[max(0, i0 - 250):i0].idxmax()
        fw = s.iloc[i0:i0 + 375]
        lo = fw.idxmin()
        ilo = s.index.get_loc(lo)

        def first(mask):
            m = mask.iloc[ilo:]
            m = m[m]
            return s.index.get_loc(m.index[0]) - i0 + 1 if len(m) else np.nan
        r = {"年": name, "t0": s.index[i0], "what": what, "why": why, "base": base, "peak": pk, "low": lo,
             "pre": base / s[pk] - 1, "more": fw.min() / base - 1, "to_low": ilo - i0 + 1, "full": fw.min() / s[pk] - 1,
             "ma60": first(on5), "back": first(s >= base), "high": first(s >= s[pk]),
             "slope": ma240.iloc[i0 - 1] / ma240.iloc[i0 - 21] - 1, "above240": bool(base > ma240.iloc[i0 - 1])}
        for k, n in (("m1", 21), ("m3", 63), ("m6", 126), ("m12", 252)):
            r[k] = s.iloc[i0 - 1 + n] / base - 1 if i0 - 1 + n < len(s) else np.nan
        r["lift"] = s.index.searchsorted(pd.Timestamp(d1)) - i0 + 1 if d1 else np.nan
        rows.append(r)
    return pd.DataFrame(rows).set_index("年")


def ma_rule(s: pd.Series, ev: pd.DataFrame) -> dict:
    ma60 = s.rolling(60).mean()
    pos = (s > ma60).shift(1, fill_value=False)
    r = s.pct_change().fillna(0)
    start = s.index[240]
    flips = pos.astype(int).diff().abs().fillna(0)
    out = {}
    for lab, x in (("bh", r), ("rule", r * pos), ("rule_c", r * pos - flips * COST / 2)):
        x = x[x.index >= start]
        eq = (1 + x).cumprod()
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        out[lab] = (eq.iloc[-1] ** (1 / yrs) - 1, (eq / eq.cummax() - 1).min())
    out["in"] = pos[pos.index >= start].mean()
    out["trips"] = int(flips[flips.index >= start].sum() / 2)
    out["years"] = (s.index[-1] - start).days / 365.25
    below = s < ma60
    ep = {}
    for name, e in ev.iterrows():
        seg = slice(e.peak, e.low)
        bh = (1 + r[seg].iloc[1:]).prod() - 1
        ru = (1 + (r * pos)[seg].iloc[1:]).prod() - 1
        x = below[e.peak:e.t0]
        x = x[x & ~below.shift(1).reindex(x.index).fillna(False)]
        ex = x.index[-1] if len(x) else None
        a = (s > ma60)[e.low:]
        re = a[a].index[0] if a.any() and e.low != s.index[-1] else None
        ep[name] = {"bh": bh, "rule": ru, "exit": ex,
                    "exit_dd": s[ex] / s[e.peak] - 1 if ex is not None else np.nan,
                    "exit_lead": s.index.get_loc(e.t0) - s.index.get_loc(ex) if ex is not None else np.nan,
                    "re": re, "re_days": s.index.get_loc(re) - s.index.get_loc(e.low) if re is not None else np.nan,
                    "re_up": s[re] / s[e.low] - 1 if re is not None else np.nan}
    out["ep"] = ep
    return out


def amt_panel(index) -> pd.DataFrame:
    out = {}
    for f in glob.glob(str(ROOT / "data" / "*.TW.csv")) + glob.glob(str(ROOT / "data" / "*.TWO.csv")):
        c = os.path.basename(f).split(".")[0]
        if not (c.isdigit() and len(c) == 4):
            continue
        try:
            d = pd.read_csv(f, usecols=["Date", "Close", "Volume"], parse_dates=["Date"]).drop_duplicates("Date").set_index("Date")
            out[c] = (d["Close"] * d["Volume"]).rolling(20).mean()
        except Exception:
            pass
    return pd.DataFrame(out).reindex(index)


def stock_recovery(px: pd.DataFrame, am: pd.DataFrame, ev: pd.DataFrame) -> dict:
    res = {}
    for name in STOCK_EV:
        e = ev.loc[name]
        i0 = px.index.searchsorted(e.t0)
        win = px.iloc[max(0, i0 - 250):i0]
        hi, c0 = win.max(), px.iloc[i0 - 1]
        ok = hi.notna() & c0.notna() & (c0 > 10) & (win.notna().sum() > 0.8 * min(250, i0))
        ids = ok[ok].index
        k_lo = px.index.searchsorted(e.low)
        d_rec = px.index[min(i0 - 1 + int(e.high), len(px) - 1)] if e.high == e.high else None

        def got(k_end):
            return (px.iloc[k_lo:k_end + 1].max() >= hi)[ids]
        end1 = min(i0 + 252, len(px) - 1)
        g1 = got(end1)
        f12 = (px.iloc[end1] / c0 - 1)[ids]
        k_rec = px.index.searchsorted(d_rec)
        dd = (c0 / hi - 1)[ids]
        r12 = (c0 / win.iloc[0] - 1)[ids].dropna()
        tier = pd.cut(am.iloc[i0 - 1][ids].rank(ascending=False), [0, 50, 200, 1e9], labels=["成交額前 50", "51~200", "其餘"])
        q_dd = pd.qcut(dd, 5, labels=["跌最深", "2", "3", "4", "跌最淺"])
        q_st = pd.qcut(r12, 5, labels=["原本最弱", "2", "3", "4", "原本最強"])
        res[name] = {
            "n": len(ids), "idx_days": e.high, "idx_m12": e.m12,
            "at_idx": got(k_rec).mean(), "lvl_idx": (px.iloc[k_rec] / hi - 1)[ids].median(),
            "y1": g1.mean(), "y2": got(i0 + 504).mean() if i0 + 504 < len(px) else np.nan,
            "now_below": ((px.iloc[-1] / hi - 1)[ids].dropna() < 0).mean(),
            "m12_med": f12.median(), "m12_win": (f12 > 0).mean(),
            "by_dd": g1.groupby(q_dd, observed=False).mean(), "ret_dd": f12.groupby(q_dd, observed=False).median(),
            "by_st": g1.reindex(q_st.index).groupby(q_st, observed=False).mean(),
            "by_tier": g1.groupby(tier, observed=False).mean(), "ret_tier": f12.groupby(tier, observed=False).median(),
        }
    return res


def breadth(px: pd.DataFrame, s: pd.Series, peak) -> dict:
    ma240, ma60 = px.rolling(240).mean(), px.rolling(60).mean()
    p240 = (px > ma240).where(ma240.notna() & px.notna()).mean(axis=1)
    p60 = (px > ma60).where(ma60.notna() & px.notna()).mean(axis=1)
    ew = (1 + px.pct_change(fill_method=None).clip(-0.11, 0.11).mean(axis=1).fillna(0)).cumprod()
    tw = s.reindex(px.index).ffill()
    w = px.loc[:peak].iloc[-250:]
    ew_pk = ew[ew.index >= peak - pd.DateOffset(months=9)].idxmax()
    lo25 = pd.Timestamp("2025-04-09")
    return {"p240": p240, "p60": p60, "ew": ew, "tw": tw, "ew_peak": ew_pk,
            "at_peak_gap": float((px.loc[peak] / w.max() - 1).median()),
            "at_peak_newhigh": float((w.iloc[-20:].max() >= w.max() * 0.999).mean()),
            "since_peak": float((px.iloc[-1] / px.loc[peak] - 1).dropna().median()),
            "ew_25": ew.iloc[-1] / ew[lo25] - 1, "tw_25": tw.iloc[-1] / tw[lo25] - 1}


def path_chart(s: pd.Series, ev: pd.DataFrame) -> str:
    """主視覺:每一次限空令生效前 20 日到之後 250 個交易日的指數走勢(生效前一天=100)。
    顏色只分三種——年線上升的、年線下彎的、這一次;哪一年直接標在線尾。"""
    W, H, L, R, T, B = 760, 380, 44, 62, 14, 34
    x0, x1, y0, y1 = -20, 250, 55, 190
    X = lambda d: L + (d - x0) / (x1 - x0) * (W - L - R)
    Y = lambda v: T + (y1 - v) / (y1 - y0) * (H - T - B)
    col = {"up": "#2f6db5", "dn": "#8a94a3", "now": "#e07b00"}
    g = ['<svg class="ch" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" font-family="Arial,sans-serif">' % (W, H)]
    for v in range(60, 181, 20):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{"#7b8794" if v == 100 else "#e4ebf4"}" stroke-width="1"/>'
                 f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" font-size="11" fill="#567" text-anchor="end">{v}</text>')
    for d, lab in ((0, "生效"), (21, "1 個月"), (63, "3 個月"), (126, "6 個月"), (189, "9 個月"), (250, "12 個月")):
        dash = ' stroke-dasharray="3 3"' if d == 0 else ""
        g.append(f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{T}" y2="{H - B}" stroke="{"#7b8794" if d == 0 else "#eef2f7"}" stroke-width="1"{dash}/>'
                 f'<text x="{X(d):.1f}" y="{H - B + 15}" font-size="11" fill="#567" text-anchor="middle">{lab}</text>')
    ends = []
    for name, e in ev.iterrows():
        i0 = s.index.get_loc(e.t0)
        seg = s.iloc[i0 - 21:i0 + 250] / e.base * 100
        kind = "now" if name == "2026" else ("up" if e.slope > 0 else "dn")
        pts = " ".join(f"{X(k - 20):.1f},{Y(min(max(v, y0), y1)):.1f}" for k, v in enumerate(seg.values))
        g.append(f'<polyline points="{pts}" fill="none" stroke="{col[kind]}" stroke-width="{3 if kind == "now" else 2}" '
                 f'stroke-linejoin="round" stroke-linecap="round" opacity="{1 if kind != "dn" else .85}"/>')
        ends.append([name, X(len(seg) - 21), Y(min(max(seg.iloc[-1], y0), y1)), kind, seg.iloc[-1]])
    ends.sort(key=lambda z: z[2])
    for k in range(1, len(ends)):                      # 線尾標籤互相讓開
        if ends[k][1] > X(200) and ends[k - 1][1] > X(200) and ends[k][2] - ends[k - 1][2] < 13:
            ends[k].append(ends[k - 1][-1] + 13 if len(ends[k - 1]) > 5 else ends[k - 1][2] + 13)
    for z in ends:
        ly = z[5] if len(z) > 5 else z[2]
        g.append(f'<circle cx="{z[1]:.1f}" cy="{z[2]:.1f}" r="3.5" fill="{col[z[3]]}" stroke="#fff" stroke-width="1.5"/>'
                 f'<text x="{z[1] + 7:.1f}" y="{ly + 4:.1f}" font-size="12" font-weight="700" fill="#1c2733">{z[0]}'
                 f'<tspan font-size="11" font-weight="400" fill="#567"> {z[4]:.0f}</tspan></text>')
    g.append("</svg>")
    lg = ('<div class="lgd"><span><i style="background:#2f6db5"></i>生效時年線還在上升(2020、2025)</span>'
          '<span><i style="background:#8a94a3"></i>年線已下彎(1998、2000、2008、2015、2022)</span>'
          '<span><i style="background:#e07b00"></i>這一次(2026)</span></div>')
    return lg + "".join(g)


def main() -> str:
    s = twii()
    ev = event_stats(s)
    done = ev.drop("2026")
    now = ev.loc["2026"]
    rule = ma_rule(s, ev)
    px = ip.closes()
    rec = stock_recovery(px, amt_panel(px.index), ev)
    br = breadth(px, s, now.peak)
    ma60, ma240 = s.rolling(60).mean().iloc[-1], s.rolling(240).mean().iloc[-1]
    slope_now = s.rolling(240).mean().iloc[-1] / s.rolling(240).mean().iloc[-21] - 1
    dd_now = s.iloc[-1] / s[now.peak] - 1
    try:
        lamp = json.loads((ROOT / "data" / "_market_risk.json").read_text(encoding="utf-8"))
    except Exception:
        lamp = {}
    up, dn = done[done.slope > 0], done[done.slope <= 0]
    med = done[["more", "to_low", "ma60", "back", "high", "lift", "m1", "m3", "m6", "m12"]].median()
    n_more = int((done.to_low > 3).sum())
    last = s.index[-1]

    # ── 歷次表 ──
    t = ("<table><tr><th>年</th><th>背景/措施</th><th>生效前<br>已跌</th><th>之後<br>再跌</th><th>幾日<br>見底</th>"
         "<th>站回季線<br>(連 5 日)</th><th>回到生效<br>前價位</th><th>回到<br>前高</th><th>措施<br>解除</th></tr>")
    for name, e in ev.iterrows():
        cur = name == "2026"
        t += (f'<tr><td><b>{name}</b><br><small>{e.t0:%m/%d}</small></td><td>{e.why}<br><small>{e.what}</small></td>'
              f'<td class="n">{pc(e.pre)}</td><td class="n">{pc(e.more)}{"<br><small>到目前</small>" if cur else ""}</td>'
              f'<td class="n">{"?" if cur else dy(e.to_low)}</td><td class="n">{dy(e.ma60)}</td><td class="n">{dy(e.back)}</td>'
              f'<td class="n">{dy(e.high)}</td><td class="n">{"未定" if cur else dy(e.lift) if e.lift == e.lift else "—"}</td></tr>')
    t += (f'<tr><td colspan="2"><b>前 7 次中位數</b></td><td class="n">{pc(done.pre.median())}</td><td class="n">{pc(med.more)}</td>'
          f'<td class="n">{dy(med.to_low)}</td><td class="n">{dy(med.ma60)}</td><td class="n">{dy(med.back)}</td>'
          f'<td class="n">{dy(med.high)}</td><td class="n">{dy(med.lift)}</td></tr></table>')
    c_hist = card("📜 歷次限空令之後,加權指數怎麼走", t,
                  src="日=交易日,從第一項措施生效日起算;「再跌」從生效前一天收盤算到之後一年半內的最低收盤。日期:經理人月刊整理 ?、2026 為中央社報導")

    t = "<table><tr><th>年</th><th>1 個月</th><th>3 個月</th><th>6 個月</th><th>12 個月</th><th>生效時年線</th></tr>"
    for name, e in done.iterrows():
        t += (f'<tr><td><b>{name}</b></td><td class="n">{pc(e.m1)}</td><td class="n">{pc(e.m3)}</td><td class="n">{pc(e.m6)}</td>'
              f'<td class="n">{pc(e.m12)}</td><td class="n">{"上升" if e.slope > 0 else "下彎"} {pc(e.slope, 1)}</td></tr>')
    t += (f'<tr><td><b>中位數</b></td><td class="n">{pc(med.m1)}</td><td class="n">{pc(med.m3)}</td><td class="n">{pc(med.m6)}</td>'
          f'<td class="n">{pc(med.m12)}</td><td></td></tr>'
          f'<tr><td><b>2026</b></td><td colspan="4">進行中</td><td class="n">上升 {pc(now.slope, 1)}</td></tr></table>')
    t += checks([
        ("ok", f"<b>年線還在上升的 {len(up)} 次({'、'.join(up.index)})</b>:{dy(up.to_low.max()).split('<')[0]}內見底,"
               f"{up.ma60.min():.0f}~{up.ma60.max():.0f} 日站回季線,{up.high.min():.0f}~{up.high.max():.0f} 日回到前高"),
        ("wn", f"<b>年線已經下彎的 {len(dn)} 次({'、'.join(dn.index)})</b>:見底中位數 {dn.to_low.median():.0f} 日、"
               f"之後再跌中位數 {pc(dn.more.median())},站回季線中位數 {dn.ma60.median():.0f} 日,回到前高中位數 {dn.high.median() / 252:.1f} 年"),
        ("wn", f"這次年線仍在上升({pc(slope_now, 1)}/20 日),但上升組只有 {len(up)} 個樣本,不能當成定論")])
    c_ret = card("📈 生效後報酬,和「年線方向」的差別", t, src="報酬從生效前一天收盤起算;年線方向=240 日均線近 20 日的變化")

    # ── 季線規則 ──
    t = ("<table><tr><th>年</th><th>高點→谷底<br>抱著不動</th><th>季線上<br>才持有</th><th>跌破季線<br>那天</th><th>谷底後幾日<br>才站回</th><th>那時已比<br>谷底高</th></tr>")
    for name, e in ev.iterrows():
        p = rule["ep"][name]
        re_txt = "還沒" if p["re"] is None else f"{p['re_days']:.0f} 日"
        ex = "—" if p["exit"] is None else f'{p["exit"]:%Y/%m/%d}<br><small>離高點 {p["exit_dd"] * 100:+.0f}%,限空令前 {p["exit_lead"]:.0f} 日</small>'
        t += (f'<tr><td><b>{name}</b></td><td class="n">{pc(p["bh"])}</td><td class="n">{pc(p["rule"])}</td><td class="n">{ex}</td>'
              f'<td class="n">{re_txt}</td><td class="n">{pc(p["re_up"])}</td></tr>')
    t += "</table>" + checks([
        ("ok", f"{rule['years']:.0f} 年全期(不含股息):抱著不動年化 {pc(rule['bh'][0], 1)}、最大回檔 {pc(rule['bh'][1])};"
               f"季線上才持有 年化 {pc(rule['rule'][0], 1)}、最大回檔 {pc(rule['rule'][1])},在場時間 {rule['in'] * 100:.0f}%"),
        ("wn", f"代價:{rule['years']:.0f} 年進出 {rule['trips']} 次(一年約 {rule['trips'] / rule['years']:.0f} 次),"
               f"每次來回算 {COST * 100:.1f}% 成本後年化降到 {pc(rule['rule_c'][0], 1)};而且每次都買在比谷底高一到兩成的地方"),
        ("wn", "這條規則的用處是「少跌」不是「多賺」;抱著不動那一邊還有股息沒算進去")])
    c_rule = card("🧪 測系統:家規「大盤破季線不開新倉」在每次空頭的表現", t, src="用加權指數模擬:收盤在 60 日線上,隔天持有;跌破隔天出場")

    # ── 個股 ──
    t = ("<table><tr><th>年</th><th>指數回到<br>前高</th><th>那天個股<br>已回到自己前高</th><th>那天個股離<br>自己前高(中位)</th>"
         "<th>1 年內<br>回到</th><th>2 年內<br>回到</th><th>今天仍低於<br>當時前高</th></tr>")
    for name in STOCK_EV:
        x = rec[name]
        y2 = "—" if pd.isna(x["y2"]) else f"{x['y2'] * 100:.0f}%"
        t += (f'<tr><td><b>{name}</b><br><small>{x["n"]:,} 檔</small></td><td class="n">{dy(x["idx_days"])}</td>'
              f'<td class="n">{x["at_idx"] * 100:.0f}%</td><td class="n">{pc(x["lvl_idx"])}</td><td class="n">{x["y1"] * 100:.0f}%</td>'
              f'<td class="n">{y2}</td><td class="n">{x["now_below"] * 100:.0f}%</td></tr>')
    t += "</table>" + checks([
        ("wn", f"<b>2025 年最明顯</b>:限空令後 12 個月指數 {pc(rec['2025']['idx_m12'])},個股中位數 {pc(rec['2025']['m12_med'])}、"
               f"上漲的只有 {rec['2025']['m12_win'] * 100:.0f}%。從 2025/4/9 低點到今天,加權指數 {pc(br['tw_25'])},個股等權平均只有 {pc(br['ew_25'])}"),
        ("ok", f"2015、2020、2022 沒那麼極端:指數回到前高時有 {min(rec[k]['at_idx'] for k in ('2015', '2020', '2022')) * 100:.0f}~"
               f"{max(rec[k]['at_idx'] for k in ('2015', '2020', '2022')) * 100:.0f}% 個股也回去了,2 年內 "
               f"{min(rec[k]['y2'] for k in ('2015', '2020', '2022')) * 100:.0f}~{max(rec[k]['y2'] for k in ('2015', '2020', '2022')) * 100:.0f}%")])
    c_stock = card("🏚 指數回來了,個股有沒有回來", t, src="個股前高=限空令前 250 個交易日的最高收盤(還原價);只算當時股價 10 元以上的")

    def grp(key, labels):
        h = "<tr><th>年</th>" + "".join(f"<th>{x}</th>" for x in labels) + "</tr>"
        for name in STOCK_EV:
            h += f"<tr><td><b>{name}</b></td>" + "".join(f'<td class="n">{rec[name][key][x] * 100:.0f}%</td>' for x in labels) + "</tr>"
        return h
    t = ("<table><tr><th colspan='6'>1 年內回到自己前高的比例——照「限空令當時已經跌多深」分五組</th></tr>"
         + grp("by_dd", ["跌最深", "2", "3", "4", "跌最淺"]) + "</table>"
         "<table><tr><th colspan='6'>照「之前一年漲幅」分五組</th></tr>" + grp("by_st", ["原本最弱", "2", "3", "4", "原本最強"]) + "</table>"
         "<table><tr><th colspan='4'>照成交額大小</th></tr>" + grp("by_tier", ["成交額前 50", "51~200", "其餘"]) + "</table>")
    d15, d20 = rec["2015"]["ret_dd"], rec["2020"]["ret_dd"]
    t += checks([
        ("ok", "<b>四次都一樣:跌得淺、原本強的回得來;跌最深的大多回不去</b>"),
        ("wn", f"但「反彈幅度」是另一回事:2015、2020 跌最深那組之後 12 個月中位數 {pc(d15['跌最深'])}、{pc(d20['跌最深'])},"
               f"比跌最淺的({pc(d15['跌最淺'])}、{pc(d20['跌最淺'])})高——搶到的是反彈,不是解套;2022、2025 連這個差別都沒有"),
        ("wn", f"大型股不是保證:成交額前 50 在 2020、2025 回得最多({rec['2020']['by_tier']['成交額前 50'] * 100:.0f}%、"
               f"{rec['2025']['by_tier']['成交額前 50'] * 100:.0f}%),2015、2022 沒有比較好")])
    c_who = card("🧬 哪一種個股回得來", t)

    p = br["p240"]

    def at(d):
        return float(p.iloc[min(p.index.searchsorted(pd.Timestamp(d)), len(p) - 1)])
    t = checks([
        ("wn", f"指數 {now.peak:%m/%d} 創高那天,個股站在年線上的只有 {at(now.peak) * 100:.0f}%;個股離自己一年高點的中位數是 {pc(br['at_peak_gap'])},"
               f"前 20 日內創一年新高的只有 {br['at_peak_newhigh'] * 100:.0f}%"),
        ("wn", f"個股等權平均的高點在 {br['ew_peak']:%Y/%m/%d},比指數早 {len(p[br['ew_peak']:now.peak]) - 1} 個交易日"),
        ("wn", f"現在({last:%m/%d}):站在年線上 {float(p.iloc[-1]) * 100:.0f}%、季線上 {float(br['p60'].iloc[-1]) * 100:.0f}%;"
               f"指數高點以來個股中位數 {pc(br['since_peak'])}"),
        ("ok", "年線上個股比例:" + "、".join(f"{d[2:7].replace('-', '/')} {at(d) * 100:.0f}%" for d in
                                       ("2025-04-09", "2025-08-18", "2026-03-31", "2026-07-06", "2026-09-01"))
               + f"、{now.peak:%y/%m} {at(now.peak) * 100:.0f}%、現在 {float(p.iloc[-1]) * 100:.0f}%")])
    c_br = card("📉 這一次:指數創高時,個股早就走弱了", t, src="本機 1,969 檔還原價;年線=240 日均線")

    # ── 現在 ──
    c_now = card("🧭 現在在哪", checks([
        ("wn", f"加權指數 {now.peak:%m/%d} 高點 {s[now.peak]:,.0f} → {last:%m/%d} 收 {s.iloc[-1]:,.0f},{len(s[now.peak:]) - 1} 個交易日跌 {pc(dd_now)};"
               f"季線 {ma60:,.0f}、年線 {ma240:,.0f},{last:%m/%d} 剛跌破年線"),
        ("wn", "限空令兩波:11/6 宣布、11/9 生效(借券賣出上限 30→3%、融券保證金 90→130%);"
               "11/19 宣布、11/20 生效(借券 1%、跌 3.5% 個股隔日不得平盤下放空)。結束日期未定"),
        ("wn", f"系統大盤燈號 {lamp.get('lamp', '?')}({lamp.get('score', '?')} 分):" + ";".join(lamp.get("reasons", [])[:5])),
        ("ok", f"和前 7 次不同的地方:第一波生效時指數還在年線之上、年線還在上升;前 7 次生效時全部已經在年線之下")]))

    concl = [
        ("wn", f"<b>限空令不是見底訊號</b>:前 7 次裡有 {n_more} 次之後還有更低點;之後再跌的中位數 {pc(med.more)},最慘 {pc(done.more.min())}(2000 年)"),
        ("ok", f"<b>多久恢復</b>(中位數):{med.to_low:.0f} 個交易日見底、{med.back:.0f} 日回到生效前價位、{med.ma60:.0f} 日站回季線、"
               f"{med.lift:.0f} 日措施解除;回到前高要 {med.high:.0f} 日(約 {med.high / 252:.1f} 年)。範圍很大:見底從當天到 {done.to_low.max():.0f} 日都有"),
        ("ok", f"<b>快或慢,看年線</b>:年線還在上升的兩次一個半月站回季線;年線下彎的 {len(dn)} 次,站回季線中位數 {dn.ma60.median():.0f} 日(約 {dn.ma60.median() / 21:.0f} 個月)"),
        ("wn", f"<b>你說的對一大半:指數回來,個股不一定</b>。指數回到前高那天,個股回到自己前高的只有 "
               f"{min(x['at_idx'] for x in rec.values()) * 100:.0f}~{max(x['at_idx'] for x in rec.values()) * 100:.0f}%;"
               f"2025 年那次到今天還有 {rec['2025']['now_below'] * 100:.0f}% 的個股沒回去"),
        ("ok", "<b>回得來的是跌得淺、原本強的</b>;跌最深的 1 年內回到前高只有 "
               f"{min(x['by_dd']['跌最深'] for x in rec.values()) * 100:.0f}~{max(x['by_dd']['跌最深'] for x in rec.values()) * 100:.0f}%"),
        ("ok", f"<b>系統的季線規則有用在「少跌」</b>:7 次空頭抱著不動跌 {pc(max(rule['ep'][k]['bh'] for k in done.index))} 到 "
               f"{pc(min(rule['ep'][k]['bh'] for k in done.index))},照規則是 {pc(max(rule['ep'][k]['rule'] for k in done.index))} 到 "
               f"{pc(min(rule['ep'][k]['rule'] for k in done.index))}。這次它在 {rule['ep']['2026']['exit']:%m/%d} 就出場了(離高點 {pc(rule['ep']['2026']['exit_dd'])})"),
    ]
    c_concl = card("📌 結論", checks(concl))
    c_concl2 = card("⏱ 一句話", checks([
        ("wn", f"限空令不是底:7 次有 {n_more} 次之後更低"),
        ("ok", f"站回季線中位數 {med.ma60:.0f} 日;年線下彎時 {dn.ma60.median():.0f} 日"),
        ("wn", "指數回來,個股不一定回來"),
        ("ok", f"這次第 {int(now.to_low)} 個交易日,指數離生效前 {pc(s.iloc[-1] / now.base - 1)}")]))
    c_chart = card("📊 歷次限空令之後的加權指數(生效前一天=100)", path_chart(s, ev),
                   src="橫軸=交易日。線尾數字=一年後的位置(這一次是目前位置)。年線方向=240 日均線近 20 日的變化")
    c_big4 = card("🔢 四個數字", bignums([
        ("限空後見底", f"{med.to_low:.0f} 日", f"中位數;範圍 1~{done.to_low.max():.0f} 日"),
        ("站回季線", f"{med.ma60:.0f} 日", f"約 {med.ma60 / 21:.1f} 個月;最久 {done.ma60.max():.0f} 日"),
        ("指數回前高時", f"{np.median([x['at_idx'] for x in rec.values()]) * 100:.0f}%", "個股也回到自己前高(4 次中位)"),
        ("現在年線上個股", f"{float(p.iloc[-1]) * 100:.0f}%", f"指數創高那天 {at(now.peak) * 100:.0f}%")]).replace(
        'class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"'))
    c_live = card("🛟 生存之道:資料支持的幾件事", checks([
        ("ok", "<b>政府出手不等於可以進場</b>。等的是「站回季線」這種看得到的事實,不是公告"),
        ("ok", "<b>先分清楚是哪一種</b>:年線上升中的急跌,一個半月;年線下彎的空頭,以季、以年計。年線方向每天看得到"),
        ("ok", "<b>大盤破季線就不開新倉</b>——這條家規在 7 次空頭都把跌幅壓到一兩成以內,代價是買回來時已經比谷底高一到兩成"),
        ("ok", "<b>不要等套牢的個股解套</b>:跌最深的那一組多數回不到原價;指數創高也救不了它"),
        ("ok", "<b>反彈要換股,不是抱原來的</b>:回得來的是跌得淺、原本就強的"),
        ("wn", "<b>看廣度,不要只看指數</b>:這次指數創高時只有四成個股在年線上——系統的燈號目前沒有這一項(只看單日漲跌家數),值得補"),
        ("wn", "以上是歷史統計與系統規則的機械結果,不是買賣建議;燈號目前仍是禁開新倉、只出不進")]))
    c_lim = card("⚠️ 限制", checks([
        ("wn", "限空令只有 7 次,年線上升組只有 2 次;每次的背景完全不同,中位數只能當量尺"),
        ("wn", "個股只看得到 2015 年以後的 4 次,而且股價檔沒有已下市的公司——實際「回不來」的比例只會更高"),
        ("wn", "季線規則用指數模擬,不含股息;個股上實際執行的成本與滑價會更大"),
        ("wn", "歷次限空令日期來自媒體整理,沒有逐一對金管會新聞稿;同一年有好幾波措施時,用第一項生效日當起點"),
        ("wn", "這次是否已見底、何時解除,資料回答不了")]), extra_cls="risk")

    date = f"{now_tw():%Y%m%d}"
    html = shell_flow(
        title_html="<b>限空令</b>之後:多久恢復?個股回得來嗎?",
        subtitle=f"前 7 次限空令:中位數 {med.to_low:.0f} 個交易日見底、{med.ma60:.0f} 日站回季線,但 {n_more} 次之後還有更低;"
                 f"指數回到前高時,個股回到自己前高的只有 {min(x['at_idx'] for x in rec.values()) * 100:.0f}~{max(x['at_idx'] for x in rec.values()) * 100:.0f}%",
        brand="限空令",
        blocks=[("wide", row([c_chart, c_big4 + c_concl2], "21")), c_concl, c_now, ("wide", c_hist),
                c_ret, c_rule, c_stock, c_who, c_br, c_live, c_lim], kind="event",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:加權指數 1997 年起(Yahoo Finance)、本機個股還原價 2015 年起、歷次措施日期(經理人月刊、中央社)· 研究筆記,非投資建議")
    print(ev[["t0", "pre", "more", "to_low", "ma60", "back", "high", "lift", "m3", "m12", "slope"]].round(3).to_string())
    print({k: {a: round(float(b), 3) for a, b in v.items() if isinstance(b, (float, np.floating))} for k, v in rec.items()})
    print({k: round(float(v[0]), 4) for k, v in rule.items() if isinstance(v, tuple)}, rule["trips"], round(rule["in"], 3))
    return str(save_poster("限空令", date, html))


if __name__ == "__main__":
    print(main())

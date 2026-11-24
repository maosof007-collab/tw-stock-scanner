# -*- coding: utf-8 -*-
"""主題海報:資安 ETF 有哪些、怎麼比(2026-11-19「資安ETF有哪些 幫我評估」)
價格、規模、費用、前十大持股都在執行時從 Yahoo Finance 抓(yfinance),報酬/波動/回檔由還原價重算。
00875 的費率與持股 Yahoo 沒有,用台灣網站的數字,表上標「?」。
手動:python -X utf8 make_poster_cyber_etf.py"""
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from poster import bignums, card, checks, hbars, save_poster, shell_flow
from poster import row as prow
from twtime import now_tw

_CA = str(Path(__file__).parent / "_ca_bundle.pem")
for _k in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    os.environ.setdefault(_k, _CA)

US = ["CIBR", "HACK", "BUG", "IHAK", "WCBR", "PSWD"]
TW = "00875.TW"
BENCH = {"QQQ": "那斯達克 100", "SPY": "標普 500", "IGV": "美國軟體股"}
# 發行商 / 追蹤指數 / 指數怎麼選。●=Yahoo 的基金說明或證交所頁面寫的;?=我記得的或第三方整理,沒對到原始文件
FUND = {
    "CIBR": ("First Trust", "Nasdaq CTA Cybersecurity ●", "消費科技協會(CTA)認定的資安公司;大型股權重高,含思科、博通"),
    "HACK": ("Amplify", "Nasdaq ISE Cyber Security Select ?", "資安軟硬體+服務;前十大含國防承包商"),
    "BUG": ("Global X", "Indxx Cybersecurity ?", "資安營收占一半以上才收 ?——最純"),
    "IHAK": ("iShares", "NYSE FactSet Global Cyber Security ?", "全球資安與相關科技;含政府 IT 服務商"),
    "WCBR": ("WisdomTree", "WisdomTree Team8 Cybersecurity ?", "資安營收+營收成長快的 ●——偏中小型成長股"),
    "PSWD": ("Xtrackers", "Solactive Cyber Security Focus ●", "資安業務公司;含政府顧問公司"),
    TW: ("國泰投信", "納斯達克 ISE 全球網路資安 ●", "台幣計價、不配息 ●;持股較平均 ?"),
}
# 前十大裡「本業不是資安」的(我的分類:網通/晶片大廠、國防與政府顧問、內容傳遞與媒體)
NOT_PURE = {"CSCO", "AVGO", "FFIV", "NOC", "GD", "SAIC", "CACI", "BAH", "LDOS", "FSLY", "ZD", "INFY", "AKAM"}
SHORT = {"CRWD": "CrowdStrike", "PANW": "Palo Alto", "CSCO": "思科", "AVGO": "博通", "FTNT": "Fortinet",
         "OKTA": "Okta", "ZS": "Zscaler", "NET": "Cloudflare", "RBRK": "Rubrik", "FFIV": "F5", "NTSK": "Netskope",
         "NOC": "諾斯洛普", "GD": "通用動力", "QLYS": "Qualys", "TENB": "Tenable", "VRNS": "Varonis",
         "S": "SentinelOne", "SAIC": "SAIC", "4704.T": "趨勢科技", "SAIL": "SailPoint", "RPD": "Rapid7",
         "CACI": "CACI", "BAH": "Booz Allen", "CHKP": "Check Point", "FSLY": "Fastly", "ZD": "Ziff Davis"}
# 00875:Yahoo 沒有持股與費率 → 口袋學堂 2026/9/15 文章(持股資料日未標示)
TW_TOP = [("QLYS", 5.08), ("NTSK", 4.50), ("FSLY", 4.49), ("NET", 4.39), ("S", 4.39),
          ("PANW", 4.26), ("CRWD", 4.14), ("RBRK", 4.09), ("ZD", 4.08), ("FTNT", 3.96)]
# 台灣資安股(名單與「資安占營收、毛利率」取自 11/16 的資安族群海報,那張是逐家查證過的)
TW_STK = [("7765", "中華資安", "純資安服務", "約 100%", "43%"), ("6690", "安碁資訊", "純資安服務", "本業即資安", "42%"),
          ("8272", "全景軟體", "自有資安軟體", "約八成 ?", "68%"), ("3564", "其陽", "資安設備代工", "86%", "31%"),
          ("6416", "瑞祺電通", "資安設備代工", "74% ?", "24%"), ("6245", "立端", "資安設備代工", "約 74% ?", "28%"),
          ("3029", "零壹", "代理", "48%", "11%"), ("6214", "精誠", "資訊服務", "未揭露", "—"), ("2480", "敦陽科", "系統整合", "未揭露", "—")]
TW_FEE, TW_TER, TW_AUM_YI = 0.90, 1.57, 10.9      # 經理費 ?、總費用率 ?、規模(億台幣,證交所頁 2026/11/19)●


def pc(x, d=0) -> str:
    if x is None or pd.isna(x):
        return "—"
    c = "rd" if x > 0 else "gn" if x < 0 else ""
    return f'<span class="{c}">{x * 100:+.{d}f}%</span>'


def fetch():
    import yfinance as yf
    warnings.filterwarnings("ignore")
    names = US + [TW] + list(BENCH)
    px = yf.download(names, start="2019-01-01", auto_adjust=True, progress=False)["Close"]
    today = pd.Timestamp(f"{now_tw():%Y-%m-%d}")
    px.loc[px.index >= today, [c for c in px.columns if c != TW]] = np.nan   # 美股當天還沒收盤,不算
    meta = {}
    for t in US + [TW]:
        tk = yf.Ticker(t)
        i = tk.info
        top = []
        if t != TW:
            th = tk.funds_data.top_holdings.reset_index()
            top = [(str(r.iloc[0]), float(r.iloc[-1]) * 100) for _, r in th.iterrows()]
        meta[t] = {"aum": i.get("totalAssets"), "fee": i.get("netExpenseRatio"),
                   "vol": i.get("averageVolume"), "px": i.get("regularMarketPrice"),
                   "nav": i.get("navPrice"), "since": pd.to_datetime(i.get("fundInceptionDate"), unit="s"),
                   "top": top}
    meta[TW]["top"] = TW_TOP
    return px, meta


def tw_close(code: str) -> pd.Series:
    for suf in (".TW.csv", ".TWO.csv"):
        f = Path(__file__).parent / "data" / f"{code}{suf}"
        if f.exists():
            d = pd.read_csv(f, usecols=["Date", "Close"], parse_dates=["Date"]).dropna().drop_duplicates("Date")
            return d.set_index("Date")["Close"].sort_index()
    return pd.Series(dtype=float)


def stats(s: pd.Series) -> dict:
    s = s.dropna()
    end = s.index[-1]

    def ret(start):
        b = s[s.index <= start]
        return s.iloc[-1] / b.iloc[-1] - 1 if len(b) else np.nan

    def ann(k):
        r = ret(end - pd.DateOffset(years=k))
        return (1 + r) ** (1 / k) - 1 if r == r else np.nan
    r = s.pct_change().dropna()
    dd = s / s.cummax() - 1
    low = dd.idxmin()
    peak = s[:low].idxmax()
    rec = s[low:]
    rec = rec[rec >= s[peak]]
    return {"end": end, "ytd": ret(pd.Timestamp(end.year - 1, 12, 31)), "y1": ret(end - pd.DateOffset(years=1)),
            "y3": ann(3), "y5": ann(5),
            "vol": r[r.index > end - pd.DateOffset(years=3)].std() * np.sqrt(252),
            "mdd": dd.min(), "peak": peak, "low": low,
            "rec_m": round((rec.index[0] - peak).days / 30.4) if len(rec) else np.nan,
            "off": dd.iloc[-1], "d1": r.iloc[-1], "last": s.iloc[-1]}


def main() -> str:
    px, meta = fetch()
    funds = US + [TW]
    st = {c: stats(px[c]) for c in funds + list(BENCH)}
    us_end = st["CIBR"]["end"]
    wk = px.resample("W-FRI").last().pct_change(fill_method=None)
    wk = wk[wk.index > us_end - pd.DateOffset(years=3)]
    beta = wk.cov()["QQQ"] / wk["QQQ"].var()
    common = px[[c for c in funds if c != "PSWD"] + list(BENCH)].dropna()
    cagr = (common.iloc[-1] / common.iloc[0]) ** (252 / len(common)) - 1
    yr = px.resample("YE").last().pct_change(fill_method=None)
    yr = yr[yr.index.year >= 2021]

    def nm(c):
        return "00875" if c == TW else c

    def impure(c):
        return sum(w for t, w in meta[c]["top"] if t in NOT_PURE)

    def top10(c):
        return sum(w for _, w in meta[c]["top"])

    cibr_top = {t for t, _ in meta["CIBR"]["top"]}
    aum_us = {c: meta[c]["aum"] / 1e8 for c in US}                       # 億美元
    turn = {c: meta[c]["vol"] * meta[c]["px"] / 1e8 for c in funds}      # 日均成交(億,各自幣別)
    best1y = max(funds, key=lambda c: st[c]["y1"])
    worst_dd = min(funds, key=lambda c: st[c]["mdd"] if c != "PSWD" else 0)
    rng_ytd = (min(st[c]["ytd"] for c in funds), max(st[c]["ytd"] for c in funds))
    rng_5y = (min(st[c]["y5"] for c in funds if c != "PSWD"), max(st[c]["y5"] for c in funds if c != "PSWD"))
    rng_dd = (max(st[c]["mdd"] for c in funds if c != "PSWD"), min(st[c]["mdd"] for c in funds if c != "PSWD"))
    rng_rec = (min(st[c]["rec_m"] for c in funds if c != "PSWD"), max(st[c]["rec_m"] for c in funds if c != "PSWD"))
    d1 = (min(st[c]["d1"] for c in US), max(st[c]["d1"] for c in US))

    concl = [
        ("ok", f"<b>台股掛牌的只有 00875 國泰網路資安一檔</b>;美股有 6 檔:CIBR、HACK、BUG、IHAK、WCBR、PSWD。"
               "七檔買的都是美國為主的資安公司,台股的資安代理商不在裡面"),
        ("ok", f"<b>規模差很多</b>:CIBR {aum_us['CIBR']:.0f} 億美元,是第二名 HACK({aum_us['HACK']:.0f} 億)的 "
               f"{aum_us['CIBR'] / aum_us['HACK']:.0f} 倍;PSWD 只有 {meta['PSWD']['aum'] / 1e4:,.0f} 萬美元、"
               f"一天成交約 {meta['PSWD']['vol']:,.0f} 股"),
        ("ok", f"<b>純度</b>:BUG 的前十大全部是資安本業;CIBR 前十大裡思科、博通、F5 合計 {impure('CIBR'):.0f}%,"
               f"HACK 有博通、思科和兩家國防承包商合計 {impure('HACK'):.0f}%"),
        ("wn", f"<b>今年漲很多,但拉長看和大盤差不多</b>:今年以來七檔 {pc(rng_ytd[0])} 到 {pc(rng_ytd[1])}"
               f"(那斯達克 100 {pc(st['QQQ']['ytd'])});5 年年化只有 {pc(rng_5y[0])} 到 {pc(rng_5y[1])},"
               f"那斯達克 100 是 {pc(st['QQQ']['y5'])}"),
        ("wn", f"<b>跌起來很深</b>:2021/11 高點到 2022–23 谷底,六檔跌 {pc(rng_dd[0])} 到 {pc(rng_dd[1])},"
               f"花了 {rng_rec[0]:.0f} 到 {rng_rec[1]:.0f} 個月才回到原價"),
        ("wn", f"<b>00875 最貴</b>:經理費 {TW_FEE:.1f}%、總費用率約 {TW_TER:.2f}% ?,美股六檔是 0.20% 到 0.60%;"
               f"規模 {TW_AUM_YI} 億台幣,一天成交約 {meta[TW]['vol'] / 1000:,.0f} 張"),
    ]
    c_concl = card("📌 結論", checks(concl))
    order = sorted(funds, key=lambda c: -st[c]["ytd"])
    c_bar = card("📊 今年大漲,拉長看普通", '<div class="lgd"><span><i style="background:#16868c"></i>今年以來</span>'
                 '<span><i style="background:#9cc9cc"></i>5 年年化</span></div>'
                 + hbars([x for c in order + ["QQQ"] for x in
                          ((("那斯達克 100" if c == "QQQ" else nm(c)), round(st[c]["ytd"] * 100), "#16868c"),
                           ("", round(st[c]["y5"] * 100) if st[c]["y5"] == st[c]["y5"] else 0, "#9cc9cc"))]),
                 src="PSWD 2023 年才成立,沒有 5 年年化(畫 0)")
    c_big4 = card("🔢 四個數字", bignums([
        ("資安 ETF", "7 檔", "台股 1、美股 6"),
        ("今年以來", f"{rng_ytd[0] * 100:+.0f}~{rng_ytd[1] * 100:+.0f}%", f"那斯達克 100 {st['QQQ']['ytd'] * 100:+.0f}%"),
        ("5 年年化", f"{rng_5y[0] * 100:+.0f}~{rng_5y[1] * 100:+.0f}%", f"那斯達克 100 {st['QQQ']['y5'] * 100:+.0f}%"),
        ("上次大跌", f"{rng_dd[1] * 100:.0f}~{rng_dd[0] * 100:.0f}%", f"{rng_rec[0]:.0f}~{rng_rec[1]:.0f} 個月回本")]))
    c_news = card("📰 這兩天怎麼了", checks([
        ("ok", f"{us_end:%m/%d} 美股六檔資安 ETF 單日 {pc(d1[0], 1)} 到 {pc(d1[1], 1)} ●;"
               f"00875 隔天({st[TW]['end']:%m/%d})在台股 {pc(st[TW]['d1'], 1)} ●"),
        ("wn", "新聞把這波歸因於 Palo Alto Networks 財報:單季營收 34.5 億美元、年增 39%,全年營收預估上修到 "
               "145.2–145.7 億美元,並宣布以 45 億美元收購 AI 新創 Applied Compute ?(第三方報導,財報原文與公布時間我沒有核對)"),
        ("wn", f"漲完之後,七檔離自己的歷史高點還有 {pc(max(st[c]['off'] for c in funds))} 到 {pc(min(st[c]['off'] for c in funds))}")]))

    t = ("<table><tr><th>代號</th><th>發行</th><th>規模</th><th>費用率</th><th>日均成交</th><th>成立</th>"
         "<th>追蹤指數</th><th>怎麼選股</th></tr>")
    for c in funds:
        m = meta[c]
        aum = f"{TW_AUM_YI} 億台幣" if c == TW else (f"{aum_us[c]:.0f} 億美元" if aum_us[c] >= 1 else f"{m['aum'] / 1e4:,.0f} 萬美元")
        fee = f"{TW_TER:.2f}% ?" if c == TW else f"{m['fee']:.2f}%"
        tv = f"{turn[c] * 1e4:,.0f} 萬台幣" if c == TW else (f"{turn[c]:.1f} 億美元" if turn[c] >= 0.1 else f"{turn[c] * 1e4:,.0f} 萬美元")
        t += (f'<tr><td><b>{nm(c)}</b></td><td>{FUND[c][0]}</td><td class="n">{aum}</td><td class="n">{fee}</td>'
              f'<td class="n">{tv}</td><td class="n">{m["since"]:%Y/%m}</td><td>{FUND[c][1]}</td><td>{FUND[c][2]}</td></tr>')
    c_list = card("📋 七檔總表", t + "</table>", src=f"規模、費用率、成交量:Yahoo Finance {now_tw():%m/%d};00875 規模為證交所頁面")

    def row(c, label=None):
        s = st[c]
        return (f'<tr><td><b>{label or nm(c)}</b></td><td class="n">{pc(s["ytd"])}</td><td class="n">{pc(s["y1"])}</td>'
                f'<td class="n">{pc(s["y3"])}</td><td class="n">{pc(s["y5"])}</td>'
                f'<td class="n">{pc(cagr.get(c, np.nan))}</td></tr>')
    t = ("<table><tr><th></th><th>今年以來</th><th>近 1 年</th><th>3 年年化</th><th>5 年年化</th>"
         f"<th>{common.index[0]:%Y/%m} 起年化</th></tr>")
    t += "".join(row(c) for c in funds) + "".join(row(c, n) for c, n in BENCH.items()) + "</table>"
    c_ret = card("📈 報酬(含息還原)", t, src=f"美股算到 {us_end:%m/%d} 收盤;00875 算到 {st[TW]['end']:%m/%d}、台幣計價(含匯率)")

    t = ("<table><tr><th></th><th>年化波動</th><th>最大回檔</th><th>從哪到哪</th><th>回本</th><th>現在離高點</th>"
         "<th>大盤漲 1% 它動</th></tr>")
    for c in funds + list(BENCH):
        s = st[c]
        rec = "還沒" if pd.isna(s["rec_m"]) else f"{s['rec_m']:.0f} 個月"
        t += (f'<tr><td><b>{BENCH.get(c, nm(c))}</b></td><td class="n">{s["vol"] * 100:.0f}%</td>'
              f'<td class="n">{pc(s["mdd"])}</td><td class="n">{s["peak"]:%Y/%m}→{s["low"]:%Y/%m}</td>'
              f'<td class="n">{rec}</td><td class="n">{pc(s["off"])}</td><td class="n">{beta[c]:.2f}%</td></tr>')
    c_risk = card("📉 風險", t + "</table>",
                  src="波動、對大盤敏感度用近 3 年;大盤=那斯達克 100、用週報酬算。00875 因為和美股差一天、又含匯率,敏感度會偏低,不能直接比")

    t = "<table><tr><th></th>" + "".join(f"<th>{y}</th>" for y in yr.index.year) + "</tr>"
    for c in funds + list(BENCH):
        t += f"<tr><td><b>{BENCH.get(c, nm(c))}</b></td>" + "".join(f'<td class="n">{pc(v)}</td>' for v in yr[c]) + "</tr>"
    c_year = card("📅 每年報酬", t + "</table>", src=f"{yr.index.year[-1]} 年算到最新收盤")

    t = "<table><tr><th>代號</th><th>前十大持股(權重 %)</th><th>前十大合計</th><th>非資安本業</th><th>和 CIBR 重複</th></tr>"
    for c in funds:
        hold = "、".join(f"{SHORT.get(tk, tk)} {w:.1f}" for tk, w in meta[c]["top"])
        same = sum(1 for tk, _ in meta[c]["top"] if tk in cibr_top)
        t += (f'<tr><td><b>{nm(c)}{" ?" if c == TW else ""}</b></td><td>{hold}</td><td class="n">{top10(c):.0f}%</td>'
              f'<td class="n">{impure(c):.0f}%</td><td class="n">{"—" if c == "CIBR" else f"{same} 檔"}</td></tr>')
    c_hold = card("🧩 裡面裝什麼", t + "</table>",
                  src="美股六檔:Yahoo Finance 最新公布;00875:口袋學堂 2026/9/15 文章(資料日未標示)。「非資安本業」是我的分類:網通與晶片大廠、國防與政府顧問、內容傳遞與媒體")

    # ── 台灣資安股 vs 美股資安 ──
    cw = px["CIBR"].resample("W-FRI").last().pct_change(fill_method=None)
    t = ("<table><tr><th>公司</th><th>做什麼</th><th>資安占營收</th><th>毛利率</th><th>今年以來</th><th>近 1 年</th><th>3 年年化</th>"
         "<th>最大回檔</th><th>和 CIBR 的週相關</th></tr>")
    tws = {}
    for code, name_, what, share, gm in TW_STK:
        c_ = tw_close(code)
        if len(c_) < 60:
            continue
        z = stats(c_)
        w_ = c_.resample("W-FRI").last().pct_change(fill_method=None)
        j = pd.concat([w_, cw], axis=1).dropna()
        j = j[j.index > j.index[-1] - pd.DateOffset(years=3)]
        z["corr"] = j.corr().iloc[0, 1] if len(j) > 30 else np.nan
        z["yrs"] = (c_.index[-1] - c_.index[0]).days / 365.25
        tws[code] = z
        t += (f'<tr><td><b>{name_}</b> {code}</td><td>{what}</td><td>{share}</td><td class="n">{gm}</td>'
              f'<td class="n">{pc(z["ytd"])}</td><td class="n">{pc(z["y1"]) if z["yrs"] > 1 else "—"}</td>'
              f'<td class="n">{pc(z["y3"]) if z["yrs"] > 3 else "—"}</td><td class="n">{pc(z["mdd"])}</td>'
              f'<td class="n">{z["corr"]:.2f}</td></tr>')
    t += (f'<tr><td><b>CIBR</b>(美股資安 ETF)</td><td>美國資安大廠</td><td>—</td><td class="n">原廠 75~82%</td>'
          f'<td class="n">{pc(st["CIBR"]["ytd"])}</td><td class="n">{pc(st["CIBR"]["y1"])}</td><td class="n">{pc(st["CIBR"]["y3"])}</td>'
          f'<td class="n">{pc(st["CIBR"]["mdd"])}</td><td class="n">1.00</td></tr></table>')
    cors = [z["corr"] for z in tws.values() if z["corr"] == z["corr"]]
    pure = [tws[c] for c in ("7765", "6690", "8272") if c in tws]
    t += checks([
        ("wn", f"<b>台灣資安股和美股資安幾乎不連動</b>:九檔和 CIBR 的週報酬相關只有 {min(cors):.2f} 到 {max(cors):.2f}"
               "(美股六檔彼此 0.93 以上)。買台灣資安股,買到的不是「全球資安需求」,是台灣的政府標案、法規和當下的題材"),
        ("wn", "<b>生意不一樣</b>:美國原廠賣自己的軟體,毛利 75~82%;台灣純資安是人力型服務(毛利 42~43%),代工 24~31%,代理約 11%。"
               "規模也差很多:安碁一年營收約 24 億台幣,Fortinet 一季就 20.8 億美元"),
        ("wn", "<b>近期的漲是評價在動,不是營收</b>:11/16 資安族群海報查到的近 3 月營收年增——中華資安 23%、安碁 8%、全景 9%,同期股價 20 日漲 26%~93%"),
        ("ok", "所以想要的如果是「全球資安產業」的曝險,數字上對應的是美股那幾檔或 00875;台灣資安股是另一種東西——"
               "不是做假的(純資安三家有真實營收與四成毛利),但它跟美股資安不是同一個題目")])
    c_twstk = card("🇹🇼 台灣資安股是不是「做爽的」?和美股資安比", t,
                   src="價格:本機還原價到最新收盤;資安占營收與毛利率:11/16 資安族群海報(逐家查證,? 為只看到摘要);相關係數用近 3 年週報酬,上市未滿 3 年的用全部期間")

    prem = meta[TW]["px"] / meta[TW]["nav"] - 1 if meta[TW].get("nav") else np.nan
    c_tw = card("🇹🇼 00875 要注意的", checks([
        ("ok", "台股帳戶直接買、台幣計價、不配息 ●。追蹤的是納斯達克 ISE 全球網路資安指數 ●,和美股那幾檔不是同一個指數"),
        ("wn", f"<b>隔一天才反映</b>:持股在美國交易,台股開盤時美股已收盤。美股 {us_end:%m/%d} 大漲,00875 是 {st[TW]['end']:%m/%d} 才跳 {pc(st[TW]['d1'], 1)}"),
        ("wn", f"<b>折溢價要看盤中預估淨值</b>:Yahoo 上的淨值 {meta[TW]['nav']:.2f} 是前一天的,拿來和今天收盤 {meta[TW]['px']:.2f} 比會差 {pc(prem, 1)},"
               "這個數字大部分是時間差,不是真的溢價;實際溢價我沒查到(國泰投信網站擋爬蟲)"),
        ("wn", f"<b>費用</b>:經理費 {TW_FEE:.1f}%、總費用率約 {TW_TER:.2f}% ?,比 CIBR 的 {meta['CIBR']['fee']:.2f}% 高約 1 個百分點,每年都扣"),
        ("wn", f"<b>規模小</b>:{TW_AUM_YI} 億台幣 ●,一天成交約 {meta[TW]['vol'] / 1000:,.0f} 張、{turn[TW] * 1e4:,.0f} 萬台幣;大單進出要看掛單"),
        ("wn", "報酬含美元兌台幣的匯率變動,台幣升值時會吃掉一部分")]))

    c_pick = card("🧭 照你在意的看哪一欄", checks([
        ("ok", f"<b>規模最大、最好進出</b>:CIBR({aum_us['CIBR']:.0f} 億美元、日均成交 {turn['CIBR']:.1f} 億美元)"),
        ("ok", f"<b>最純的資安</b>:BUG(前十大非資安本業 {impure('BUG'):.0f}%),但前十大合計 {top10('BUG'):.0f}%、最集中,上次回檔 {pc(st['BUG']['mdd'])}"),
        ("ok", f"<b>近 1 年漲最多</b>:{nm(best1y)} {pc(st[best1y]['y1'])};<b>上次跌最深</b>:{nm(worst_dd)} {pc(st[worst_dd]['mdd'])}"),
        ("ok", f"<b>費用最低</b>:PSWD {meta['PSWD']['fee']:.2f}%,但規模太小,買賣價差可能比省下的費用還多"),
        ("ok", "<b>不想開複委託</b>:只有 00875,代價是費用和上面那幾點"),
        ("wn", f"六檔美股彼此週報酬相關 0.93 以上,買兩檔分散不了什麼")]))
    c_lim = card("⚠️ 限制", checks([
        ("wn", "標 ? 的是第三方整理或我記得的內容,沒有對到發行商原始文件:00875 的費率與持股、各指數的選股規則"),
        ("wn", "沒有比本益比:資安公司很多還在虧損,ETF 的本益比數字通常不含虧損公司,會失真"),
        ("wn", "只列台股與美股掛牌的;歐洲掛牌(UCITS)的資安 ETF 沒列"),
        ("wn", "台灣資安股那張表只有 9 檔、而且是今年題材正熱時看的;相關係數低不代表未來不會一起跌(大盤崩跌時什麼都跌)"),
        ("wn", "過去報酬不代表未來;這是比較表,不是買賣建議")]), extra_cls="risk")

    date = f"{now_tw():%Y%m%d}"
    html = shell_flow(
        title_html="<b>資安 ETF</b> 有哪些、怎麼比",
        subtitle=f"台股 1 檔(00875)、美股 6 檔;今年以來 {rng_ytd[0] * 100:+.0f}% 到 {rng_ytd[1] * 100:+.0f}%,"
                 f"5 年年化 {rng_5y[0] * 100:+.0f}% 到 {rng_5y[1] * 100:+.0f}%、和那斯達克 100({st['QQQ']['y5'] * 100:+.0f}%)差不多;"
                 f"上次大跌 {rng_dd[1] * 100:.0f}% 到 {rng_dd[0] * 100:.0f}%",
        brand="資安 ETF",
        blocks=[("wide", c_list), ("wide", prow([c_bar, c_big4 + c_concl], "12")), c_ret, c_risk, ("wide", c_hold),
                ("wide", c_twstk), c_year, c_tw, c_news, c_pick, c_lim], kind="compare",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:Yahoo Finance(價格、規模、費用、持股)、證交所 ETF 頁(00875)· ●=原始來源 ?=第三方或未核對 · 比較表,非投資建議")
    print({nm(c): {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else str(v)[:10])
                   for k, v in st[c].items() if k in ("ytd", "y1", "y3", "y5", "mdd", "rec_m", "off", "d1")} for c in funds})
    print({nm(c): (round(top10(c)), round(impure(c)), round(turn[c], 3)) for c in funds})
    return str(save_poster("資安ETF", date, html))


if __name__ == "__main__":
    print(main())

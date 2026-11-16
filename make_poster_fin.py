# -*- coding: utf-8 -*-
"""族群海報:金融 — 電子有問題時,金融股是不是退路?(2026-11-16)
用 2015 年以來的日線算:大盤大跌日、歷次修正期間,金融(銀行/壽險金控/證券)對電子跌多少。
股價、外資每次重產即時算;獲利與股利是查證資料(寫死在下面,●=開過原文、?=只看到摘要)。
haven() 也給 make_poster_1216.py 用。手動重跑:python -X utf8 make_poster_fin.py"""
import glob
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from poster import bignums, card, checks, save_poster, shell, ud
from twtime import now_tw

D = Path(__file__).parent / "data"
ELE = ["半導體業", "電腦及週邊設備業", "電子零組件業", "光電業", "通信網路業", "其他電子業", "電子通路業"]
# 我自己分的類(金控看主要獲利來源);沒列到的小型保險、票券不進三類
LIFE = ["2881", "2882", "2883", "2887"]                                     # 壽險比重高的金控
BANK = ["2891", "2886", "2884", "2892", "2880", "5880", "2890", "2801", "5876", "2834", "2812", "2845", "2838", "2836", "2849", "2897"]
SEC = ["2885", "2855", "6005", "5864", "6016", "6015", "6021", "6020", "6026"]
KIND = {**{c: "壽險金控" for c in LIFE}, **{c: "銀行" for c in BANK}, **{c: "證券" for c in SEC}}
# 2026 年除息的現金股利(證交所除權息計算結果表,●);權息並發的只列現金不好拆,先不列
DIV = {"2881": 4.25, "2882": 3.5, "2883": 1.0, "2884": 1.4, "2885": 1.8, "2886": 1.75, "2891": 2.5, "2892": 1.3,
       "2855": 2.11, "2849": 0.51, "2897": 0.52, "2820": 0.9, "2816": 1.5, "2832": 3.5, "2850": 7.27, "2851": 2.2, "2852": 1.66}
MIX = {"2838", "2887", "2890", "5876", "2836", "6024", "2812", "2834", "2801", "5880", "6005", "2880", "2889", "2845"}   # 配股配息並發
CRASH = -4.0          # 大盤單日跌幅門檻(%)
EP_DD = -0.12         # 大盤從高點回落多少算一次修正


def _close(code):
    f = glob.glob(str(D / f"{code}.TW*.csv"))
    if not f:
        return None
    return pd.read_csv(f[0], usecols=["Date", "Close"]).dropna().set_index("Date").Close


@lru_cache(maxsize=1)
def haven() -> dict:
    """回傳 X(每日報酬%:大盤/電子/金融/銀行/壽險金控/證券/食品/統一)、idx(各自的累積指數)、eps(歷次修正的高低點)"""
    sl = pd.read_csv(D / "stock_list.csv", dtype=str, encoding="utf-8-sig").set_index("code")
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0).iloc[:, 0].dropna()

    def panel(codes):
        out = {c: s for c in codes if (s := _close(c)) is not None and len(s) > 300 and s.index[-1] == bm.index[-1]}
        return pd.DataFrame(out).reindex(bm.index)

    by = lambda secs: [c for c in sl.index if sl.sector[c] in secs]
    PF, PE, PD = panel(by(["金融保險業"])), panel(by(ELE)), panel(by(["食品工業"]))
    rF = PF.pct_change(fill_method=None)
    med = lambda r, cs=None: (r[[c for c in cs if c in r.columns]] if cs else r).median(axis=1)
    X = pd.DataFrame({"大盤": bm.pct_change(fill_method=None), "電子": med(PE.pct_change(fill_method=None)), "金融": med(rF), "銀行": med(rF, BANK),
                      "壽險金控": med(rF, LIFE), "證券": med(rF, SEC), "食品": med(PD.pct_change(fill_method=None)),
                      "統一": PD["1216"].pct_change(fill_method=None)}) * 100
    idx = (1 + X.drop(columns=["大盤", "統一"]).fillna(0) / 100).cumprod()
    idx["大盤"], idx["統一"] = bm, PD["1216"]
    dd, eps, on, pk = bm / bm.cummax() - 1, [], False, None
    for d, v in dd.items():
        if not on and v <= EP_DD:
            on, pk = True, bm[:d].idxmax()
        if on and v > -0.03:
            eps.append((pk, bm[pk:d].idxmin()))
            on = False
    if on:
        eps.append((pk, bm[pk:].idxmin()))
    return dict(X=X, idx=idx, eps=eps, PF=PF, PD=PD, sl=sl, bm=bm)


def ep_table(h, cols) -> pd.DataFrame:
    return pd.DataFrame([{"高點": a, "低點": b, **{c: (h["idx"][c][b] / h["idx"][c][a] - 1) * 100 for c in cols}}
                         for a, b in h["eps"]])


def main() -> str:
    h = haven()
    X, idx, PF, sl, bm = h["X"], h["idx"], h["PF"], h["sl"], h["bm"]
    date = now_tw().strftime("%Y%m%d")
    last = bm.index[-1]
    md = f"{int(last[5:7])}/{int(last[8:10])}"
    cd = X[X["大盤"] <= CRASH]
    n = len(cd)
    less = lambda c: int((cd[c] > cd["大盤"]).sum())
    ret = lambda c, k: (idx[c].iloc[-1] / idx[c].iloc[-1 - k] - 1) * 100
    pk = bm.iloc[-120:].idxmax()
    since = lambda c: (idx[c].iloc[-1] / idx[c][pk] - 1) * 100
    pkmd = f"{int(pk[5:7])}/{int(pk[8:10])}"
    ep = ep_table(h, ["大盤", "電子", "銀行", "壽險金控", "證券"])
    try:
        lamp = json.load(open(D / "_market_risk.json", encoding="utf-8"))
        lamp_s = f"大盤燈號 {lamp['lamp']}({lamp['rule']})"
    except Exception:
        lamp_s = "大盤燈號讀不到"

    # 個股:20 日均額前 14 大
    rows = []
    for c in PF.columns:
        raw = pd.read_csv(glob.glob(str(D / f"{c}.TW*.csv"))[0]).dropna(subset=["Close"])
        cl = raw.Close
        rr = PF[c].pct_change(fill_method=None)[cd.index].dropna() * 100
        rec = dict(code=c, name=sl.name[c], px=cl.iloc[-1], amt=(cl * raw.Volume).iloc[-20:].mean() / 1e8,
                   cavg=rr.mean(), cless=int((rr > cd["大盤"][rr.index]).sum()), cn=len(rr), since=(PF[c].iloc[-1] / PF[c][pk] - 1) * 100,
                   d1=(cl.iloc[-1] / cl.iloc[-2] - 1) * 100, d20=(cl.iloc[-1] / cl.iloc[-21] - 1) * 100,
                   d60=(cl.iloc[-1] / cl.iloc[-61] - 1) * 100, yr=(cl.iloc[-1] / cl.iloc[-240:].mean() - 1) * 100, fi20=None, fi1=None)
        try:
            i = pd.read_csv(D / "institutional" / f"{c}_inst.csv")
            fi = i[[x for x in i.columns if "外陸資買賣超" in x][0]].fillna(0)
            if i.date.iloc[-1] == last:
                rec["fi20"], rec["fi1"] = fi.iloc[-20:].sum() * cl.iloc[-1] / 1e8, fi.iloc[-1] * cl.iloc[-1] / 1e8
        except Exception:
            pass
        rows.append(rec)
    S = pd.DataFrame(rows).set_index("code").sort_values("amt", ascending=False)
    fi20, fi1 = S.fi20.sum(), S.fi1.sum()
    top = S.dropna(subset=["fi20"]).sort_values("fi20")
    nm2 = lambda r: "、".join(f"{x['name']} {x.fi20:+.0f} 億" for _, x in r.iterrows())
    hi_yr = S.head(14).sort_values("yr", ascending=False).head(4)

    try:                                        # 借錢的那一端:電子通路 17 家(make_poster_dist 的資料)
        db = pd.read_csv(D / "_dist_bs.csv")
        lend_s = (f"對照借錢的一方:17 家電子通路商短期借款一年 {db['stdebt_2025-09'].sum():,.0f}→{db['stdebt_2026-09'].sum():,.0f} 億、"
                  f"前三季營業現金流 {db.ocf_9m.sum():+,.0f} 億——放款收緊,先痛的是借錢囤貨的人;銀行這邊要看的是壞帳")
    except Exception:
        lend_s = ""

    c_num = card(f"大盤單日跌 {abs(CRASH):.0f}% 以上的 {n} 天(2015 起),平均跌多少", bignums([
        ("電子", f"{cd['電子'].mean():.1f}%", f"大盤 {cd['大盤'].mean():.1f}%"),
        ("銀行", f"{cd['銀行'].mean():.1f}%", f"{less('銀行')} 天跌得比大盤少"),
        ("壽險金控", f"{cd['壽險金控'].mean():.1f}%", f"證券 {cd['證券'].mean():.1f}%"),
    ]))

    L = [
        ("ok", f"<b>電子自己出問題時,金融跌得少</b>:這一波從 {pkmd} 高點到 {md},大盤 {since('大盤'):+.1f}%、電子 {since('電子'):+.1f}%、"
               f"銀行 {since('銀行'):+.1f}%、壽險金控 {since('壽險金控'):+.1f}%、證券 {since('證券'):+.1f}%"),
        ("xx", "<b>整個市場一起崩的時候躲不掉</b>:2020 年 1~3 月(疫情)銀行 "
               f"{ep.loc[ep['高點'].str.startswith('2020'), '銀行'].iloc[0]:+.0f}%、壽險金控 {ep.loc[ep['高點'].str.startswith('2020'), '壽險金控'].iloc[0]:+.0f}%,"
               f"和大盤差不多;2025/4/7(關稅)金融單日中位數 {X.loc['2025-04-07', '金融']:+.1f}%,和電子一樣"),
        ("wn", f"<b>三種金融要分開看</b>:{md} 銀行 {X['銀行'].iloc[-1]:+.1f}%、壽險金控 {X['壽險金控'].iloc[-1]:+.1f}%、證券 {X['證券'].iloc[-1]:+.1f}%。"
               f"2022 年升息那次也一樣:銀行 {ep.loc[ep['高點'].str.startswith('2022'), '銀行'].iloc[0]:+.0f}%、"
               f"壽險金控 {ep.loc[ep['高點'].str.startswith('2022'), '壽險金控'].iloc[0]:+.0f}%、證券 {ep.loc[ep['高點'].str.startswith('2022'), '證券'].iloc[0]:+.0f}%"),
        ("wn", "<b>壽險的獲利直接吃股市</b>:?6 大壽險 10 月合計虧 48 億(台股 10 月跌 5.7%);?富邦金 10 月轉虧 7.5 億、"
               "國泰金單月賺 90.9 億;13 家金控 10 月獲利月減 32%。11 月的數字 12 月上旬才公布"),
        ("wn", f"<b>已經有人先躲進來</b>:近 60 日銀行 {ret('銀行', 60):+.1f}%、電子 {ret('電子', 60):+.1f}%;"
               f"{'、'.join(hi_yr['name'])}在年線上 {hi_yr.yr.min():.0f}~{hi_yr.yr.max():.0f}%。"
               f"現金殖利率剩 3% 上下(兆豐金 1.75 元 ÷ {S.px['2886']:.1f} = {1.75 / S.px['2886'] * 100:.1f}%)"),
        ("wn", "<b>銀行對科技業的放款在降溫</b>:?國銀五大信賴產業放款 9 月底 5 兆 785 億,9 月只月增 66.76 億,是 4 月以來最低;"
               "?外電:銀行為守流動性覆蓋率,企業借款利率調高 50~90 基點。" + lend_s),
        ("ok", f"外資近 20 日買超金融股合計 {fi20:+,.0f} 億({md} 當天 {fi1:+,.0f} 億):買最多 {nm2(top.tail(3).iloc[::-1])};"
               f"賣最多 {nm2(top.head(3))}"),
        ("xx", f"{lamp_s}——這個燈號不分產業"),
    ]
    c_concl = card("結論(重點先看)", checks(L), src="●=開過原文 ?=只看到摘要;其餘為系統即時計算", extra_cls="grow")

    t = "<table><tr><th>大盤高點→低點</th><th>大盤</th><th>電子</th><th>銀行</th><th>壽險金控</th><th>證券</th></tr>"
    for _, r in ep.iterrows():
        t += (f'<tr><td><b>{r["高點"][:7].replace("-", "/")}</b>→{r["低點"][:7].replace("-", "/")}</td>'
              + "".join(f'<td class="n">{r[c]:+.0f}%</td>' for c in ["大盤", "電子", "銀行", "壽險金控", "證券"]) + "</tr>")
    c_ep = card(f"2015 年以來大盤回落超過 {abs(EP_DD) * 100:.0f}% 的 {len(ep)} 次", t + "</table>"
                + '<div class="note">各類取成分股每日漲跌的中位數累積;「電子」是 7 個電子產業合併。'
                  f"銀行在 {len(ep)} 次裡有 {int((ep['銀行'] > ep['大盤'] / 2).sum())} 次跌幅不到大盤一半;壽險金控和證券大多跟著大盤。</div>")

    def stock_table(codes) -> str:
        out = ('<table><tr><th>公司</th><th>今日</th><th>' + pkmd + ' 以來</th><th>大跌日平均</th><th>距年線</th>'
               '<th>外資 20 日</th><th>殖利率</th><th>均額</th></tr>')
        for c, x in S.loc[[k for k in S.index if k in codes]].iterrows():
            dv = (f"{DIV[c] / x.px * 100:.1f}%" if c in DIV else "<small>配股配息</small>" if c in MIX else "<small>—</small>")
            fi = ud(round(x.fi20, 1), f"{x.fi20:+.1f} 億") if pd.notna(x.fi20) else "<small>—</small>"
            out += (f'<tr><td><b>{x["name"]}</b> <small>{c}</small></td><td class="n">{ud(round(x.d1, 1), f"{x.d1:+.1f}%")}</td>'
                    f'<td class="n">{ud(round(x.since, 1), f"{x.since:+.0f}%")}</td>'
                    f'<td class="n">{x.cavg:+.1f}%<br><small>{x.cless}/{x.cn} 天少跌</small></td>'
                    f'<td class="n">{x.yr:+.0f}%</td><td class="n">{fi}</td><td class="n">{dv}</td><td class="n">{x.amt:.1f} 億</td></tr>')
        return out + "</table>"

    oth = [c for c in S.index if c not in KIND]
    note = (f'<div class="note">大跌日=2015 年以來大盤單日跌 {abs(CRASH):.0f}% 以上的 {n} 天(大盤平均 {cd["大盤"].mean():+.1f}%),'
            "「少跌」是比大盤跌得少的天數;依 20 日均額排序。●殖利率=2026 年已除息現金股利÷今日收盤,配股配息並發的不拆。</div>")
    c_bank = card(f"銀行 {len([c for c in S.index if c in BANK])} 檔(含銀行為主的金控)", stock_table(BANK) + note)
    c_life = card("壽險比重高的金控", stock_table(LIFE))
    c_sec = card(f"證券 {len([c for c in S.index if c in SEC])} 檔", stock_table(SEC))
    c_oth = card(f"產險、再保、票券、期貨 {len(oth)} 檔", stock_table(oth))

    c_read = card("讀這張表要注意", checks([
        ("wn", "「跌得少」是相對電子,不是不會跌:大盤大跌日金融平均還是跌 "
               f"{abs(cd['金融'].mean()):.1f}%,{n} 天裡只有 {int((cd['金融'] > 0).sum())} 天收紅"),
        ("wn", "分類是我依主要獲利來源分的:中信金、永豐金歸銀行,台新新光金歸壽險金控,元大金歸證券"),
        ("wn", "金控獲利是公司自結數;我沒逐家查股票部位大小與放在損益表的比例"),
        ("wn", "如果電子的問題擴大成信用或流動性事件(融資斷頭、違約),銀行也會被波及——2020/3 就是"),
        ("ok", "接下來看:12 月上旬的 11 月金控自結獲利;外資對銀行股是不是還在買"),
    ]), extra_cls="risk grow")

    html = shell(
        title_html="金融股:電子出事時的<b>退路</b>?",
        subtitle=f"{pkmd} 高點以來 電子 {since('電子'):+.0f}%、銀行 {since('銀行'):+.0f}%、壽險金控 {since('壽險金控'):+.0f}%、證券 {since('證券'):+.0f}%——躲得掉的是銀行",
        brand="退路查核",
        cols=[c_num + c_concl + c_ep, c_bank + c_read, c_life + c_sec + c_oth],
        footer=f"素材:系統 {date[:4]}/{date[4:6]}/{date[6:]} 日線與三大法人、證交所除權息表、金控自結獲利報導 · 本海報為研究筆記非投資建議")
    return str(save_poster("金融", date, html))


if __name__ == "__main__":
    print("saved:", main())

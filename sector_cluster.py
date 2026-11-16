# -*- coding: utf-8 -*-
"""
sector_cluster.py — 族群聚集雷達(不靠手寫族群)
=================================================================
起因(2026-11-16):資安/資服從 10/22 起就有 6~9 檔擠進注意力榜 Top20,但 theme_groups 沒有這一群、
榜單也不顯示產業,沒人看出是同一群;11/16 大盤 -6% 當天整群漲停才發現。
做法:用官方產業別(stock_list.sector)對全市場算價格廣度,再疊上注意力榜的產業分布。
亮燈規則(兩條任一):
  A 注意力榜 Top20 同一官方產業 ≥ ATT_MIN 檔,且占榜比例 ≥ 該產業占全市場比例的 ATT_LIFT 倍
    (半導體、電子零組件各一百多檔,上榜 4 檔是常態,不加倍數門檻會天天響)
  B 該產業「創 20 日新高比例」連 STREAK 天全市場第一,且當天 ≥ NH_MIN %
產出:data/_sector_cluster.csv(當日全表)+族群強弱海報(make_poster_cluster)
推播:只在「出現新的亮燈產業」那天推一則文字(稀有才推,不佔每日額度)。
排程:run_daily Step 4.59906(緊接在強勢資金之後,才讀得到當日注意力榜)。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
OUT = D / "_sector_cluster.csv"
STATE = D / "_sector_cluster_state.json"      # {"date": 最近一次執行日, "groups": 當日亮燈產業}

MIN_AMT = 2e7       # 20 日均額門檻(0.2 億):太冷的不算進廣度
MIN_UNIVERSE = 300      # 更新到最新日的股票少於這個數,視為資料沒更新齊
MIN_N = 8           # 官方產業至少幾檔才排名
ATT_MIN = 4         # 規則 A:上榜檔數
ATT_LIFT = 3.0      # 規則 A:占榜比例 ÷ 產業占全市場比例
STREAK = 3          # 規則 B
NH_MIN = 15.0       # 規則 B:新高比例下限(%)
TAIL = 70


def load() -> dict:
    """讀全市場日線 → 價格面板與衍生指標。只收最後一天=大盤最後一天的股票(避免混到舊資料)。"""
    sl = pd.read_csv(D / "stock_list.csv", dtype=str)
    sec, nm = dict(zip(sl.code, sl.sector)), dict(zip(sl.code, sl.name))
    bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    last = f"{bm.index[-1]:%Y-%m-%d}"
    px = {}
    for f in glob.glob(str(D / "*.TW*.csv")):
        c = os.path.basename(f).split(".")[0]
        if c not in sec or len(c) != 4 or c.startswith("00") or not isinstance(sec[c], str):
            continue
        try:
            d = pd.read_csv(f, usecols=["Date", "Close", "Volume"]).dropna().tail(TAIL)
        except Exception:
            continue
        if len(d) < TAIL or str(d.Date.iloc[-1])[:10] != last:
            continue
        if (d.Close * d.Volume).tail(20).mean() < MIN_AMT:
            continue
        px[c] = pd.Series(d.Close.values, index=d.Date.astype(str).str[:10])
    P = pd.DataFrame(px).sort_index()
    if P.shape[1] < MIN_UNIVERSE:        # 日線還沒更新齊(只有少數檔到最新日)→ 不算,免得用殘缺母體亮燈、推播
        raise RuntimeError(f"資料日 {last} 只有 {P.shape[1]} 檔更新到位(門檻 {MIN_UNIVERSE}),本次不計算")
    bmr = bm.pct_change() * 100
    bmr.index = bmr.index.strftime("%Y-%m-%d")
    return dict(P=P, sec=sec, nm=nm, bm=bm, bmr=bmr, last=last,
                r1=P.pct_change(1, fill_method=None) * 100,
                r5=P.pct_change(5, fill_method=None) * 100,
                r20=P.pct_change(20, fill_method=None) * 100,
                hi=P >= P.rolling(20).max(), lo=P <= P.rolling(20).min(),
                below=P < P.rolling(60, min_periods=40).mean())


def _members(S: pd.Series, P: pd.DataFrame, min_n: int) -> tuple[pd.Series, pd.Series]:
    S = S[S.index.isin(P.columns)]
    cnt = S.value_counts()
    return S[S.isin(cnt[cnt >= min_n].index)], cnt[cnt >= min_n]


def _streak(flag: pd.DataFrame) -> pd.Series:
    """每欄到最後一天為止連續 True 的天數"""
    out = {}
    for c in flag.columns:
        n = 0
        for v in flag[c].values[::-1]:
            if not v:
                break
            n += 1
        out[c] = n
    return pd.Series(out)


def nh_panel(ctx: dict, S: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(各日各群創 20 日新高比例%, 名次);前 20 天沒有 rolling 值,丟掉"""
    nh = (ctx["hi"][S.index].T.groupby(S).mean().T * 100).iloc[20:]
    return nh, nh.rank(axis=1, ascending=False, method="min")


def strong_table(ctx: dict, S: pd.Series, min_n: int = MIN_N) -> pd.DataFrame:
    P, r1, r5, r20, nm = ctx["P"], ctx["r1"], ctx["r5"], ctx["r20"], ctx["nm"]
    S, cnt = _members(S, P, min_n)
    med = lambda df: df[S.index].iloc[-1].groupby(S).median()
    nh, rk = nh_panel(ctx, S)
    t = pd.DataFrame({
        "n": cnt, "d1": med(r1), "up": (r1[S.index].iloc[-1] > 0).groupby(S).mean() * 100,
        "r5": med(r5), "r20": med(r20), "nh": nh.iloc[-1], "nh_rk": rk.iloc[-1],
        "top3": (rk.tail(5) <= 3).sum(), "first_streak": _streak((rk == 1) & (nh >= NH_MIN)),
    }).round(1)
    t["names"] = [" ".join(f"{nm[c]}{r5[c].iloc[-1]:+.0f}"
                           for c in r5.iloc[-1][S.index[S == k]].sort_values(ascending=False).head(6).index)
                  for k in t.index]
    return t.sort_values(["nh", "r5"], ascending=False)


def weak_table(ctx: dict, S: pd.Series, min_n: int) -> pd.DataFrame:
    P, nm = ctx["P"], ctx["nm"]
    S, cnt = _members(S, P, min_n)
    d1, r20 = ctx["r1"].iloc[-1], ctx["r20"].iloc[-1]
    g = lambda s: s[S.index].groupby(S)
    t = pd.DataFrame({"n": cnt, "d1": g(d1).median(), "ld": g(d1 <= -9.5).mean() * 100,
                      "r20": g(r20).median(), "lo": g(ctx["lo"].iloc[-1]).mean() * 100,
                      "ma": g(ctx["below"].iloc[-1]).mean() * 100}).round(1)
    t["names"] = ["、".join(nm[c] for c in r20[S.index[S == k]].sort_values().head(4).index) for k in t.index]
    return t.sort_values(["lo", "r20"], ascending=[False, True])


def attention_by_sector(ctx: dict) -> tuple[str, pd.DataFrame]:
    """注意力榜最新一天的產業分布 → (日期, DataFrame[產業, n, names]);沒有檔案回空表"""
    f = D / "_attention_hist.csv"
    if not f.exists():
        return "", pd.DataFrame(columns=["n", "names"])
    h = pd.read_csv(f, dtype={"代號": str})
    day = h["日期"].max()
    h = h[h["日期"] == day].assign(sec=lambda x: x["代號"].map(ctx["sec"]))
    g = h.groupby("sec").agg(n=("代號", "size"), names=("名稱", lambda s: "、".join(s)))
    return day, g.sort_values("n", ascending=False)


def alerts(ctx: dict, strong: pd.DataFrame, att: pd.DataFrame) -> list[dict]:
    out = []
    total, top_n = ctx["P"].shape[1], max(int(att.n.sum()), 1) if len(att) else 20
    for k, x in strong.iterrows():
        rules = []
        an = int(att.n.get(k, 0)) if len(att) else 0
        lift = (an / top_n) / (x.n / total)
        if an >= ATT_MIN and lift >= ATT_LIFT:
            rules.append(f"注意力榜 {an} 檔(是產業比重的 {lift:.0f} 倍)")
        if x.first_streak >= STREAK:
            rules.append(f"新高比例 {x.nh:.0f}% 連 {int(x.first_streak)} 天第一")
        if rules:
            out.append(dict(group=k, rules=rules, n=int(x.n), d1=float(x.d1), r5=float(x.r5), nh=float(x.nh),
                            att_names=att.names.get(k, "") if len(att) else "", names=x["names"]))
    return out


def compute() -> dict:
    ctx = load()
    S_off = pd.Series(ctx["sec"])
    strong = strong_table(ctx, S_off)
    att_day, att = attention_by_sector(ctx)
    att_rule = att if att_day == ctx["last"] else att.iloc[0:0]    # 注意力榜不是今天的 → 規則 A 當作沒資料(海報仍顯示舊榜日期)
    try:
        from theme_groups import THEME_GROUPS as G
        weak_thm = weak_table(ctx, pd.Series({c: k for k, cs in G.items() for c in cs}), 3)
    except Exception as e:
        print(f"[sector_cluster] 手寫族群表讀不到,最弱族群那段略過: {e}")
        weak_thm = pd.DataFrame()
    crash = [d for d in ctx["bmr"].tail(20)[ctx["bmr"].tail(20) <= -4].index if d in ctx["r1"].index]
    both = (ctx["r1"].loc[crash] > 0).all() if len(crash) >= 2 else pd.Series(False, index=ctx["P"].columns)
    return dict(ctx=ctx, strong=strong, weak_off=weak_table(ctx, S_off, MIN_N), weak_thm=weak_thm,
                att_day=att_day, att=att, alerts=alerts(ctx, strong, att_rule),
                crash_days=crash, both_up=list(both[both].index))


def line_text(res: dict, new: list[str]) -> str:
    ctx = res["ctx"]
    L = [f"🧲 族群聚集 {ctx['last'][5:]}(大盤 {ctx['bmr'].iloc[-1]:+.1f}%)", "新亮燈:" + "、".join(new)]
    for a in res["alerts"]:
        L.append(f"・{a['group']}({a['n']}檔,今日中位 {a['d1']:+.1f}%):" + ";".join(a["rules"]))
        L.append("  " + (a["att_names"] or a["names"]))
    if len(res["weak_thm"]):
        L.append("最弱:" + "、".join(res["weak_thm"].index[:3]))
    L.append("完整:App → 財經報 → 海報 → 族群強弱|只看價格廣度,非投資建議")
    return "\n".join(L)


def run_daily_step(push: bool = True) -> str:
    """每日一步:算表 → 存檔 → 海報 → (有新亮燈產業才)推播。push=False 時不推也不動狀態檔(手動測試用)。"""
    res = compute()
    res["strong"].to_csv(OUT, encoding="utf-8-sig")
    msg = [f"{len(res['strong'])} 個產業", f"亮燈 {len(res['alerts'])}"]
    try:
        import make_poster_cluster
        msg.append(Path(make_poster_cluster.main(res)).name)
    except Exception as e:
        msg.append(f"海報失敗:{e}")
    if not push:
        return "|".join(msg) + "|未推播(測試)"
    # 狀態以「資料日」為準:base=上一個資料日亮過的,pushed=這個資料日已推過的。
    # 同一天跑幾次都行——早上資料不全沒亮、晚上才亮,晚上那次照樣會推;推播失敗不記帳,下次重試。
    day = res["ctx"]["last"]
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if st.get("date") != day:
        st = {"date": day, "base": st.get("groups", []), "pushed": [], "groups": []}
    cur = [a["group"] for a in res["alerts"]]
    new = [g for g in cur if g not in st.get("base", []) and g not in st.get("pushed", [])]
    if new:
        try:
            import line_push
            if line_push.enabled():
                msg.append("推播:" + str(line_push.push_text(line_text(res, new))))
                st["pushed"] = st.get("pushed", []) + new
            else:
                msg.append("推播:LINE未設定")
        except Exception as e:
            msg.append(f"推播失敗:{e}")
    st["groups"] = sorted(set(st.get("groups", [])) | set(cur))
    STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    return "|".join(msg) + (f"|新亮燈 {'、'.join(new)}" if new else "")


def history(days: int = 30) -> pd.DataFrame:
    """回算:過去 days 天每天哪些產業會亮燈(驗證規則用,不寫檔)。"""
    ctx = load()
    S, _ = _members(pd.Series(ctx["sec"]), ctx["P"], MIN_N)
    nh, rk = nh_panel(ctx, S)
    first = (rk == 1) & (nh >= NH_MIN)
    ruleB = first.rolling(STREAK).sum() == STREAK
    rows = []
    f = D / "_attention_hist.csv"
    att = pd.read_csv(f, dtype={"代號": str}) if f.exists() else pd.DataFrame(columns=["日期", "代號"])
    att = att.assign(sec=att["代號"].map(ctx["sec"])).groupby(["日期", "sec"]).size()
    share = S.value_counts() / ctx["P"].shape[1]
    for day in nh.index[-days:]:
        b = set(ruleB.columns[ruleB.loc[day]])
        a = set()
        if day in att.index.get_level_values(0):
            x = att[day]
            a = {k for k, v in x.items() if k in share.index and v >= ATT_MIN and (v / x.sum()) / share[k] >= ATT_LIFT}
        for k in sorted(a | b):
            rows.append(dict(date=day, group=k, A=k in a, B=k in b, nh=round(nh.loc[day, k], 0) if k in nh else None))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    r = compute()
    print("資料日", r["ctx"]["last"], "| 注意力榜日", r["att_day"], "| 檔數", r["ctx"]["P"].shape[1])
    print(r["strong"].head(10).drop(columns="names").to_string())
    print("亮燈:", [(a["group"], a["rules"]) for a in r["alerts"]])
    print(history().to_string(index=False))

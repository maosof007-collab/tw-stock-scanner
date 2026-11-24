# -*- coding: utf-8 -*-
"""
ai_capex_exposure.py — 各族群「股價跑在獲利前面多少」(2026-11-20)
=================================================================
起因:SemiAnalysis 11/13 把 2027–2030 年 AI 加速器支出預估大砍(2028 年 -28%),
使用者問「PCB/封測還有哪些族群都有可能是高估」「我們的模型是否要改善」。
做法(全部用本機資料,不用任何外部預估):
  ・股價:2024 年底 → 2026/10/6 高點 → 現在(還原價)
  ・獲利:2024 全年 EPS → 最近四季 EPS;營收:2024 全年 → 最近 12 個月
  ・本益比:現在、2024 年底、近 3 年月底中位數(和估值前瞻頁 forecast_card.pe_band 同口徑:季報公布後 45 天才算已知)
  ・獲利位置:最近一季營益率 vs 近 3 年中位數(是不是在高峰)
一檔一列 stock_table(),族群彙總 group_table()(取中位數;成分股全部列出)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from theme_groups import THEME_GROUPS

ROOT = Path(__file__).parent
D = ROOT / "data"
PEAK = "2026-10-06"          # 加權指數高點
BASE = "2024-12-31"
# 和 AI 資料中心資本支出直接相關的族群(我的分類;其餘當對照組)
AI_GROUPS = ["晶圓代工", "封測", "IC設計", "記憶體", "半導體設備", "ABF載板", "PCB", "散熱", "AI伺服器", "電源",
             "玻璃基板TGV", "光通訊CPO", "網通", "電子特化", "重電", "AIDC基建資服", "矽晶圓", "被動元件"]


def _px(code: str) -> pd.Series:
    for suf in (".TW.csv", ".TWO.csv"):
        f = D / f"{code}{suf}"
        if f.exists():
            d = pd.read_csv(f, usecols=["Date", "Close"], parse_dates=["Date"]).dropna().drop_duplicates("Date")
            return d.set_index("Date")["Close"].sort_index()
    return pd.Series(dtype=float)


def stock_table() -> pd.DataFrame:
    import fundamentals
    fin = fundamentals.bulk_q_all().copy()          # 單季 EPS 可疑的(股本變動那一季)已設成空值,例:緯穎 2026Q3
    fin["季度"] = pd.to_datetime(fin["季度"])
    rev = pd.read_csv(D / "_rev_history.csv", dtype={"code": str})
    try:
        names = pd.read_csv(D / "stock_list.csv", dtype={"code": str}).set_index("code")["name"].to_dict()
    except Exception:
        names = {}
    rows = []
    for grp, codes in THEME_GROUPS.items():
        for code in codes:
            px = _px(code)
            q = fin[fin["code"] == code].dropna(subset=["EPS"]).sort_values("季度")
            r = rev[rev["code"] == code].sort_values("ym")
            if len(px) < 300 or len(q) < 6:
                continue
            now = float(px.iloc[-1])
            p_base = float(px[:BASE].iloc[-1]) if len(px[:BASE]) else np.nan
            p_peak = float(px[:PEAK].iloc[-1])
            q = q.assign(ttm=q["EPS"].rolling(4).sum())
            eps24 = float(q[q["季度"].dt.year == 2024]["EPS"].sum()) if (q["季度"].dt.year == 2024).sum() == 4 else np.nan
            ttm = float(q["ttm"].iloc[-1])
            rr = r.set_index("ym")["rev"].astype(float)
            rev24 = rr[rr.index.str.startswith("2024")].sum() if rr.index.str.startswith("2024").sum() == 12 else np.nan
            rev12 = rr.tail(12).sum() if len(rr) >= 12 else np.nan
            # 近 3 年月底本益比(季報 +45 天才算已知)
            known = q.dropna(subset=["ttm"]).assign(ok=lambda d: d["季度"] + pd.Timedelta(days=45))
            me = px[px.index >= px.index[-1] - pd.Timedelta(days=365 * 3)].resample("ME").last().dropna()
            pes = []
            for d, c in me.items():
                k = known[known["ok"] <= d]
                if len(k) and k["ttm"].iloc[-1] > 0 and 0 < c / k["ttm"].iloc[-1] < 150:
                    pes.append(c / k["ttm"].iloc[-1])
            pe50 = float(np.median(pes)) if len(pes) >= 6 else np.nan
            om = q["營益率%"].astype(float)
            rows.append({
                "族群": grp, "代號": code, "名稱": names.get(code, code), "現價": now,
                "股價_基期到高點": p_peak / p_base - 1, "股價_高點到現在": now / p_peak - 1, "股價_基期到現在": now / p_base - 1,
                "EPS2024": eps24, "EPS近四季": ttm,
                "獲利成長": ttm / eps24 - 1 if eps24 == eps24 and eps24 > 0 and ttm > 0 else np.nan,
                "營收成長": rev12 / rev24 - 1 if rev24 == rev24 and rev24 > 0 else np.nan,
                "本益比": now / ttm if ttm > 0 else np.nan,
                "高點本益比": p_peak / ttm if ttm > 0 else np.nan,
                "基期本益比": p_base / eps24 if eps24 == eps24 and eps24 > 0 else np.nan,
                "本益比中位": pe50,
                "用2024獲利算": now / eps24 if eps24 == eps24 and eps24 > 0 else np.nan,
                "營益率": float(om.iloc[-1]), "營益率中位": float(om.tail(12).median()),
                "毛利率": float(q["毛利率%"].astype(float).iloc[-1]),
                "季別": f"{q['季度'].iloc[-1]:%Y-%m}", "營收月": r["ym"].iloc[-1] if len(r) else "",
            })
    t = pd.DataFrame(rows)
    t["評價變化"] = t["本益比"] / t["基期本益比"] - 1
    t["回到中位"] = t["本益比中位"] / t["本益比"] - 1                     # 本益比回到近 3 年中位數,股價要動多少
    t["回到中位且獲利減兩成"] = 0.8 * t["本益比中位"] / t["本益比"] - 1
    t["營益率差"] = t["營益率"] - t["營益率中位"]
    # 營業槓桿:營收少 1%,營業利益大約少幾 %(假設成本跟著量走、費用不動)。營益率太低的不算,上限 6 倍
    t["槓桿"] = np.where(t["營益率"] >= 3, (t["毛利率"] / t["營益率"]).clip(upper=6), np.nan)
    return t


def group_table(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby("族群", sort=False)
    out = g.agg(檔數=("代號", "size"), 股價_基期到高點=("股價_基期到高點", "median"), 股價_高點到現在=("股價_高點到現在", "median"),
                股價_基期到現在=("股價_基期到現在", "median"), 獲利成長=("獲利成長", "median"), 營收成長=("營收成長", "median"),
                本益比=("本益比", "median"), 高點本益比=("高點本益比", "median"), 基期本益比=("基期本益比", "median"),
                本益比中位=("本益比中位", "median"), 用2024獲利算=("用2024獲利算", "median"),
                回到中位=("回到中位", "median"), 回到中位且獲利減兩成=("回到中位且獲利減兩成", "median"),
                營益率差=("營益率差", "median"), 虧損檔數=("本益比", lambda s: int(s.isna().sum())),
                毛利率=("毛利率", "median"), 營益率=("營益率", "median"), 槓桿=("槓桿", "median"))
    out["跑在前面"] = (1 + out["股價_基期到現在"]) / (1 + out["獲利成長"]) - 1      # 股價漲幅超過獲利成長的部分
    out["高點時跑在前面"] = (1 + out["股價_基期到高點"]) / (1 + out["獲利成長"]) - 1
    out["AI"] = out.index.isin(AI_GROUPS)
    out["成分"] = [("、".join(f"{r.名稱} {r.代號}" for r in t[t["族群"] == k].itertuples())) for k in out.index]
    return out


def _rev() -> pd.DataFrame:
    r = pd.read_csv(D / "_rev_history.csv", dtype={"code": str})
    r["m"] = pd.PeriodIndex(r["ym"], freq="M")
    return r


def cycle_lead(start: str = "2020-07", end: str = "2023-06", min_fall: float = 0.30) -> pd.DataFrame:
    """上一輪循環:每檔股價高點 vs 營收(近 3 月平均)高點,誰先到。
    只收「高點後 18 個月內至少跌 min_fall」的股票;營收高點在股價高點前 6 個月~後 24 個月內找。"""
    rev = _rev()
    rows = []
    for grp, codes in THEME_GROUPS.items():
        for c in codes:
            c = str(c)
            p = _px(c)
            r = rev[rev["code"] == c].set_index("m")["rev"].sort_index()
            if len(p) < 1500 or len(r) < 80 or r.index.min() > pd.Period("2019-06"):
                continue
            w = p[start:end]
            if w.empty:
                continue
            d0, pk = w.idxmax(), w.max()
            after = p[d0:d0 + pd.Timedelta(days=550)]
            fall = after.min() / pk - 1
            if fall > -min_fall:
                continue
            m0 = d0.to_period("M")
            r3 = r.rolling(3).mean()
            win = r3[m0 - 6:m0 + 24]
            if win.dropna().empty:
                continue
            rm = win.idxmax()
            y3 = r3 / r3.shift(12) - 1
            neg = y3[m0:][y3[m0:] < 0]
            pm = p.groupby(p.index.to_period("M")).last()
            trm = after.idxmin().to_period("M")
            rw = r3[rm:rm + 30]
            rtr = rw.idxmin()
            rows.append(dict(族群=grp, 代號=c, 股價高點=str(m0), 之後最大跌幅=fall, 營收高點=str(rm), 領先月數=(rm - m0).n,
                             高點時營收年增=y3.get(m0, np.nan), 年增轉負月數=(neg.index[0] - m0).n if len(neg) else np.nan,
                             營收高點時股價已跌=pm.get(rm, np.nan) / pk - 1, 股價低點=str(trm), 營收低點=str(rtr),
                             低點領先月數=(rtr - trm).n, 營收高到低=r3[rtr] / r3[rm] - 1))
    t = pd.DataFrame(rows)
    t["AI"] = t["族群"].isin(AI_GROUPS)
    return t


def lead_summary(d: pd.DataFrame) -> dict:
    return dict(檔數=len(d), 股價先見頂=float((d["領先月數"] > 0).mean()), 領先月數=float(d["領先月數"].median()),
                高點時營收年增=float(d["高點時營收年增"].median()), 高點時年增為正=float((d["高點時營收年增"] > 0).mean()),
                年增轉負月數=float(d["年增轉負月數"].median()), 營收高點時股價已跌=float(d["營收高點時股價已跌"].median()),
                最大跌幅=float(d["之後最大跌幅"].median()), 低點領先月數=float(d["低點領先月數"].median()),
                營收高到低=float(d["營收高到低"].median()))


def now_state() -> pd.DataFrame:
    """這一輪走到哪:每檔 2026 年自己的股價高點、到現在跌多少;營收(近 3 月平均)是不是還在創高、年增有沒有在減速。"""
    rev = _rev()
    rows = []
    for grp in AI_GROUPS:
        for c in THEME_GROUPS.get(grp, []):
            c = str(c)
            p = _px(c)
            r = rev[rev["code"] == c].set_index("m")["rev"].sort_index()
            if len(p) < 300 or len(r) < 16:
                continue
            w = p["2026-01-01":]
            d0, pk = w.idxmax(), w.max()
            r3 = r.rolling(3).mean()
            y3 = r3 / r3.shift(12) - 1
            last = r.index[-1]
            hi = r3.iloc[-12:].idxmax()
            rows.append(dict(族群=grp, 代號=c, 股價高點日=d0, 從高點=p.iloc[-1] / pk - 1, 營收月=str(last),
                             營收創高=bool(hi == last), 營收高點月=str(hi), 離營收高點=r3.iloc[-1] / r3.iloc[-12:].max() - 1,
                             年增現在=y3.iloc[-1], 年增三個月前=y3.iloc[-4] if len(y3) > 4 else np.nan,
                             近三月比前三月=r3.iloc[-1] / r3.iloc[-4] - 1 if len(r3) > 4 else np.nan,
                             前三月比再前三月=r3.iloc[-4] / r3.iloc[-7] - 1 if len(r3) > 7 else np.nan))
    return pd.DataFrame(rows)


def now_groups(n: pd.DataFrame) -> pd.DataFrame:
    g = n.groupby("族群").agg(檔數=("代號", "count"), 從高點=("從高點", "median"), 營收仍創高=("營收創高", "mean"),
                            年增現在=("年增現在", "median"), 年增三個月前=("年增三個月前", "median"),
                            近三月比前三月=("近三月比前三月", "median"), 前三月比再前三月=("前三月比再前三月", "median"))
    g["年增減速"] = g["年增現在"] < g["年增三個月前"]
    g["季增減速"] = g["近三月比前三月"] < g["前三月比再前三月"]
    return g


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    t = stock_table()
    g = group_table(t)
    print(f"{len(t)} 檔、{len(g)} 個族群;季報到 {t['季別'].max()}、營收到 {t['營收月'].max()}")
    show = g.sort_values("高點時跑在前面", ascending=False)[["檔數", "AI", "股價_基期到高點", "股價_高點到現在", "股價_基期到現在", "獲利成長", "營收成長",
                                                       "高點時跑在前面", "跑在前面", "本益比", "本益比中位", "用2024獲利算", "回到中位", "營益率差", "虧損檔數"]]
    print(show.round(2).to_string())

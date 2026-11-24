# -*- coding: utf-8 -*-
"""
chip_cycle.py — 半導體庫存循環燈號(台積電的客戶有沒有在堆貨、買氣有沒有降溫)
================================================================================
起因(2026-11-23):使用者問「台積會不會像 2022 一樣,明年庫存增?不是要你當先知,有沒有指標能先慢慢看到,
指標出現我就慢慢出場」。
回測結論(2013 年起):台積電自己的營收和存貨是**最後**才轉弱的(2022 年股價 1 月見高,營收年增到 2023/04 才轉負);
先動的是它的下游——記憶體和 IC 設計的月營收年增開始降溫、IC 設計的存貨增加得比營收快。所以燈號看的是下游,不是台積電本身。

六顆燈(全部是寫死的規則,只用當時已經公布的資料;月營收隔月 10 日、季報 Q1~Q3 +45 天、年報 +90 天才算已知):
  客戶端三顆(回測有用,CORE):
    ① IC 設計營收降溫   ② IC 設計存貨堆高(存貨年增 − 營收年增 ≥ 30 點)   ③ 系統組裝存貨堆高(≥ 20 點)
  參考三顆(回測沒有用,留著是為了看順序):
    ④ 記憶體營收降溫(高點前常先亮,但亮著的月份之後報酬和沒亮一樣)
    ⑤ 二線代工營收降溫  ⑥ 台積電營收降溫(都是落後指標:亮的時候股價多半已經跌完)
  「降溫」= 近 3 個月營收年增率,比近 12 個月的高點掉了四成以上(高點要 ≥20%)、而且比 3 個月前低;
            或年增率已經轉負、而且還在往下。年增率回頭往上,燈就熄。
另外測過「川湖股價、銅價」當訊號(使用者 11/23 提的):川湖常比台積電早見高,但「台積電在高點、川湖沒跟」之後的報酬
和平常一樣;銅只弱一點。兩個都不亮燈,只在頁面列出回測(others_peaks / others_backtest)。
門檻是看過歷史之後定的,真正的庫存修正只有 2015、2022 兩次,所以這是「歷史上長這樣」,不是保證。

資料:FinMind 免費端點(月營收 2005 起、資產負債表 2012 起);美國大客戶近 5 季用 yfinance(沒有長歷史,只列現況不亮燈)。
      請求只在 `python -X utf8 chip_cycle.py fetch` 發(每日排程);頁面只讀 data/chip_cycle.json。
用法:python -X utf8 chip_cycle.py           # 印目前燈號、歷次修正前後的亮燈順序、回測
      python -X utf8 chip_cycle.py fetch     # 抓資料、重建 data/chip_cycle.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from fundamentals import FM_URL, FUND_DIR
from twtime import now_tw

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "chip_cycle.json"
DS = {"bs": "TaiwanStockBalanceSheet", "is": "TaiwanStockFinancialStatements", "rev": "TaiwanStockMonthRevenue"}
GROUPS = {                                   # 代號都在 fetch 時用 data_provider.stock_name 對過名稱,存進 JSON
    "tsmc": ("台積電", ["2330"]),
    "design": ("IC 設計", ["2454", "3034", "2379", "3443", "3661", "5274", "6415", "5269", "8299", "4966", "3035"]),
    "system": ("系統組裝", ["2317", "2382", "3231", "6669", "2356", "2376", "2357", "4938"]),
    "memory": ("記憶體", ["2408", "2344", "2337"]),
    "foundry2": ("二線代工", ["2303", "5347"]),
}
US = ["NVDA", "AMD", "AVGO", "QCOM", "AAPL", "MRVL"]      # 台積電的美國大客戶(只有近 5 季)
LIGHTS = [                                   # key, 名稱, 族群, 種類, 門檻
    ("m_design", "① IC 設計營收降溫", "design", "rev", None),
    ("i_design", "② IC 設計存貨堆高", "design", "inv", 30),
    ("i_system", "③ 系統組裝存貨堆高", "system", "inv", 20),
    ("m_memory", "④ 記憶體營收降溫", "memory", "rev", None),
    ("m_foundry2", "⑤ 二線代工營收降溫", "foundry2", "rev", None),
    ("m_tsmc", "⑥ 台積電營收降溫", "tsmc", "rev", None),
]
CORE = ("m_design", "i_design", "i_system")  # 客戶端三顆:回測裡亮著的月份,台積電之後 6 個月下跌的比例是沒亮時的兩倍
BOOM, DROP, LOOK = 20.0, 0.6, 3              # 降溫:高點要 ≥20%、掉到高點的六成以下、比 3 個月前低
DD_MIN = 0.20                                # 台積電從歷史高點跌超過兩成才算一次「修正」
PAUSE = 0.6


# ══════════════════════════════════════════════════════════════ 抓資料(只有排程/手動會跑)
def _fm(code: str, tag: str, max_age_h: float) -> list[dict]:
    p = FUND_DIR / f"{code}_cyc_{tag}.json"

    def old() -> list[dict]:
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        except Exception:
            return []

    if p.exists() and time.time() - p.stat().st_mtime < max_age_h * 3600:
        got = old()
        if got:
            return got
    for _ in range(3):
        try:
            j = requests.get(FM_URL, params={"dataset": DS[tag], "data_id": code, "start_date": "2005-01-01"},
                             timeout=40).json()
            time.sleep(PAUSE)
            data = j.get("data", []) if j.get("status") == 200 else []
            if data:
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data
            break                                           # 限流或空回應:不重打,用舊的
        except Exception:
            time.sleep(8)
    return old()


def _us() -> dict:
    """美國大客戶近 5 季的存貨/營收/銷貨成本(yfinance)。抓不到就回空,頁面會少一張表。"""
    out = {}
    try:
        import yfinance as yf
    except Exception:
        return out
    for t in US:
        try:
            k = yf.Ticker(t)
            b, i = k.quarterly_balance_sheet, k.quarterly_income_stmt
            rows = []
            for d, inv in b.loc["Inventory"].dropna().items():
                if d in i.columns:
                    rows.append({"date": str(d)[:10], "inv": float(inv), "rev": float(i.loc["Total Revenue", d]),
                                 "cogs": float(i.loc["Cost Of Revenue", d])})
            if rows:
                out[t] = sorted(rows, key=lambda r: r["date"])
        except Exception:
            continue
    return out


def fetch() -> dict:
    import ssl_trust
    ssl_trust.ensure()
    from data_provider import stock_name
    day = now_tw().day
    rev_age = 20 if day <= 16 else 24 * 12                  # 月營收 10 日前公布:月中以前每天看一次,之後不用
    names, q, m = {}, {}, {}
    for _, codes in GROUPS.values():
        for c in codes:
            names[c] = stock_name(c)
            b, i = pd.DataFrame(_fm(c, "bs", 24 * 6)), pd.DataFrame(_fm(c, "is", 24 * 6))
            r = pd.DataFrame(_fm(c, "rev", rev_age))
            if not b.empty and not i.empty:
                inv = b[b.type == "Inventories"].set_index("date").value
                p = i.pivot_table(index="date", columns="type", values="value", aggfunc="first")
                x = pd.DataFrame({"inv": inv, "rev": p.get("Revenue"), "cogs": p.get("CostOfGoodsSold")}).dropna(subset=["inv", "rev"])
                q[c] = [[d, float(v.inv), float(v.rev), (None if pd.isna(v.cogs) else float(v.cogs))] for d, v in x.iterrows()]
            if not r.empty:
                r["ym"] = r.revenue_year.astype(int).astype(str) + "-" + r.revenue_month.astype(int).astype(str).str.zfill(2)
                r = r.drop_duplicates("ym", keep="last")
                m[c] = dict(zip(r.ym, r.revenue.astype(float)))
    px = {}
    try:                                                     # 台積電未還原收盤(和本益比河流圖共用快取)
        import pe_river
        d = pd.DataFrame(pe_river._get("TaiwanStockPrice", "2330", "2005-01-01", "px"))
        px = dict(zip(d.date.astype(str), d.close.astype(float)))
    except Exception:
        pass
    old = load_raw()
    us = _us() or old.get("us", {})
    px2, cu = {}, {}
    try:                                                     # 川湖(伺服器滑軌)未還原收盤、銅期貨(HG=F):只拿來回測,不亮燈
        d = pd.DataFrame(pe_river._get("TaiwanStockPrice", "2059", "2005-01-01", "px"))
        px2 = dict(zip(d.date.astype(str), d.close.astype(float)))
        names["2059"] = stock_name("2059")
    except Exception:
        pass
    try:
        import yfinance as yf
        h = yf.Ticker("HG=F").history(start="2005-01-01", auto_adjust=False).Close.dropna()
        cu = {str(k)[:10]: float(v) for k, v in h.items()}
    except Exception:
        pass
    out = dict(made=f"{now_tw():%Y-%m-%d %H:%M}", names=names, q=q, m=m, px=px or old.get("px", {}), us=us,
               px2059=px2 or old.get("px2059", {}), copper=cu or old.get("copper", {}))
    miss = [c for _, cs in GROUPS.values() for c in cs if c not in q or c not in m]
    if miss and old:                                         # 這次有缺(限流):缺的沿用舊檔,不讓族群合計少一塊
        for c in miss:
            out["q"].setdefault(c, old.get("q", {}).get(c, []))
            out["m"].setdefault(c, old.get("m", {}).get(c, {}))
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT)
    print(f"chip_cycle:{len(q)} 檔季報、{len(m)} 檔月營收、美股 {len(us)} 檔、台積電股價 {len(out['px'])} 天"
          + (f"|這次沒抓到:{','.join(miss)}" if miss else ""))
    return out


# ══════════════════════════════════════════════════════════════ 讀快取、算指標(頁面用)
def load_raw() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _known_q(d: pd.Timestamp) -> pd.Timestamp:
    """季報哪一天才算已知:Q1~Q3 +45 天、年報 +90 天。"""
    return d + pd.Timedelta(days=90 if d.month == 12 else 45)


def _known_m(p: pd.Period) -> pd.Timestamp:
    """月營收隔月 10 日公布。"""
    return (p + 1).to_timestamp() + pd.Timedelta(days=9)


def monthly(raw: dict) -> pd.DataFrame:
    """各族群近 3 個月營收年增率(%),index=月份 Period。成分股那個月還沒上市的,前後兩年都不算(同一批公司比)。"""
    out = {}
    for g, (_, codes) in GROUPS.items():
        d = pd.DataFrame({c: pd.Series(raw["m"].get(c, {}), dtype=float) for c in codes})
        d.index = pd.PeriodIndex(d.index, freq="M")
        d = d.sort_index()
        d = d.reindex(pd.period_range(d.index[0], d.index[-1], freq="M"))
        s3, s3p = d.rolling(3).sum(), d.rolling(3).sum().shift(12)
        ok = s3.notna() & s3p.notna()
        out[g] = (s3.where(ok).sum(axis=1, min_count=1) / s3p.where(ok).sum(axis=1, min_count=1) - 1) * 100
    return pd.DataFrame(out)


def _qframe(raw: dict, code: str) -> pd.DataFrame:
    x = pd.DataFrame(raw["q"].get(code, []), columns=["date", "inv", "rev", "cogs"])
    x["date"] = pd.to_datetime(x.date)
    return x.set_index("date").astype(float).sort_index()


def quarterly(raw: dict) -> dict[str, pd.DataFrame]:
    """各族群每季:存貨天數、存貨年增 − 營收年增(百分點)。同一批公司比(去年同季沒有資料的不算)。"""
    out = {}
    for g, (_, codes) in GROUPS.items():
        fr = {c: _qframe(raw, c) for c in codes}
        idx = sorted(set().union(*[f.index for f in fr.values()]))
        inv, rev, cogs = (pd.DataFrame({c: f[k] for c, f in fr.items()}, index=idx) for k in ("inv", "rev", "cogs"))
        ok = inv.notna() & inv.shift(4).notna() & rev.notna() & rev.shift(4).notna()
        iy = inv.where(ok).sum(axis=1, min_count=1) / inv.shift(4).where(ok).sum(axis=1, min_count=1) - 1
        ry = rev.where(ok).sum(axis=1, min_count=1) / rev.shift(4).where(ok).sum(axis=1, min_count=1) - 1
        okd = inv.notna() & cogs.notna() & (cogs > 0)
        out[g] = pd.DataFrame({"days": inv.where(okd).sum(axis=1, min_count=1) / cogs.where(okd).sum(axis=1, min_count=1) * 91,
                               "inv_yoy": iy * 100, "rev_yoy": ry * 100, "spread": (iy - ry) * 100,
                               "known": [_known_q(d) for d in idx]}, index=idx)
    return out


def seq_growth(raw: dict, g: str) -> float:
    """族群近 3 個月營收合計比前 3 個月(%)。年增率很高時會被去年基期拉著掉,這個數字不受基期影響(但有季節性)。"""
    d = pd.DataFrame({c: pd.Series(raw["m"].get(c, {}), dtype=float) for c in GROUPS[g][1]}).sort_index().dropna()
    return float((d.iloc[-3:].sum().sum() / d.iloc[-6:-3].sum().sum() - 1) * 100)


def cooling(y: pd.Series) -> pd.Series:
    """營收年增率「降溫」的布林序列(規則見檔頭)。"""
    hi = y.rolling(12, min_periods=6).max()
    prev = y.shift(LOOK)
    return (((hi >= BOOM) & (y <= DROP * hi)) | (y < 0)) & (y < prev)


def panel(raw: dict) -> pd.DataFrame:
    """每個月底、只用當時已知的資料,六顆燈亮不亮 + 台積電月底收盤。index=月底 Timestamp。"""
    mm, qq = monthly(raw), quarterly(raw)
    px = pd.Series(raw["px"], dtype=float)
    px.index = pd.to_datetime(px.index)
    px = px.sort_index()
    ends = px.groupby(px.index.to_period("M")).apply(lambda s: s.index[-1])
    ends = ends[ends >= pd.Timestamp("2013-06-01")]
    d = pd.DataFrame({"close": px.reindex(ends.values).values}, index=pd.DatetimeIndex(ends.values))
    per = d.index.to_period("M") - 1                       # 月底時已知的最新月營收=上個月(隔月 10 日公布)
    for key, _, g, kind, th in LIGHTS:
        if kind == "rev":
            y = mm[g]
            d[key] = cooling(y).reindex(per).fillna(False).astype(bool).values   # rolling 只用過去的月份,整條算一次就好
            d[key + "_v"] = y.reindex(per).values
        else:
            k = qq[g].dropna(subset=["spread"]).sort_values("known")
            v = pd.merge_asof(pd.DataFrame({"t": d.index}), k[["known", "spread"]], left_on="t", right_on="known").spread
            d[key] = (v >= th).fillna(False).values
            d[key + "_v"] = v.values
    d["n"] = d[[k for k, *_ in LIGHTS]].sum(axis=1).astype(int)
    d["core"] = d[list(CORE)].sum(axis=1).astype(int)
    return d


def now(raw: dict, pan: pd.DataFrame | None = None) -> pd.DataFrame:
    """目前六顆燈:亮不亮、現在的數字、從哪個月開始連續亮。"""
    pan = panel(raw) if pan is None else pan
    mm, qq = monthly(raw), quarterly(raw)
    rows = []
    for key, name, g, kind, th in LIGHTS:
        lit = bool(pan[key].iloc[-1])
        since = ""
        if lit:
            off = pan.index[~pan[key].astype(bool)]
            first = pan.index[pan.index > off[-1]][0] if len(off) else pan.index[0]
            since = f"{first:%Y/%m}"
        if kind == "rev":
            y = mm[g].dropna()
            hi = y.iloc[-12:].max()
            seq = seq_growth(raw, g)
            val = (f"近 3 月年增 {y.iloc[-1]:+.0f}%(近 12 月高點 {hi:+.0f}%,3 個月前 {y.iloc[-1 - LOOK]:+.0f}%)"
                   f"|近 3 月比前 3 月 {seq:+.0f}%")
            rule = f"掉到高點的六成以下({hi * DROP:+.0f}%)且比 3 個月前低"
            asof = y.index[-1].strftime("%Y/%m") + " 營收"
        else:
            s = qq[g].dropna(subset=["spread"]).iloc[-1]
            val = f"存貨年增 {s.inv_yoy:+.0f}% − 營收年增 {s.rev_yoy:+.0f}% = {s.spread:+.0f} 點|存貨 {s.days:.0f} 天"
            rule = f"差距 ≥ {th} 點"
            asof = f"{s.name:%Y}Q{(s.name.month - 1) // 3 + 1} 季報"
        rows.append({"燈": "🔴 亮" if lit else "⚪ 沒亮", "類別": "客戶端" if key in CORE else "參考", "指標": name, "現在": val, "亮燈條件": rule, "資料到": asof, "連續亮起自": since})
    return pd.DataFrame(rows)


def episodes(raw: dict, pan: pd.DataFrame | None = None) -> pd.DataFrame:
    """台積電每一次從歷史高點跌超過兩成:高點前 12 個月到低點之間,每顆燈第一次亮是哪個月、比股價高點早或晚幾個月。"""
    pan = panel(raw) if pan is None else pan
    px = pd.Series(raw["px"], dtype=float)
    px.index = pd.to_datetime(px.index)
    px = px.sort_index()[lambda s: s.index >= "2013-06-01"]
    rows, peak_d, peak, low_d, low, on = [], px.index[0], px.iloc[0], None, None, False
    eps = []
    for d, v in px.items():
        if v >= peak:
            if on:
                eps.append((peak_d, peak, low_d, low, d))
                on = False
            peak_d, peak, low_d, low = d, v, d, v
        elif v < (low if low is not None else peak):
            low_d, low = d, v
            if v <= peak * (1 - DD_MIN):
                on = True
    if on:
        eps.append((peak_d, peak, low_d, low, None))
    for pk_d, pk, lo_d, lo, back in eps:
        row = {"股價高點": f"{pk_d:%Y/%m/%d}", "高點": pk, "低點": f"{lo_d:%Y/%m/%d}", "跌幅%": round((lo / pk - 1) * 100, 1),
               "回到高點": f"{back:%Y/%m/%d}" if back is not None else "還沒"}
        before = pan[pan.index < pk_d]                                  # 高點之前最後一個月底:當時真的看得到的
        after = pan[(pan.index >= pk_d) & (pan.index <= lo_d + pd.offsets.MonthEnd(0))]
        row["高點前客戶端亮幾顆"] = int(before.core.iloc[-1]) if len(before) else 0
        for key, name, *_ in LIGHTS:
            if len(before) and bool(before[key].iloc[-1]):
                off = before.index[~before[key].astype(bool)]
                first = before.index[before.index > off[-1]][0] if len(off) else before.index[0]
                row[name] = f"高點前就亮(自 {first:%Y/%m},早 {(pk_d.to_period('M') - first.to_period('M')).n} 個月)"
            else:
                lit = after.index[after[key].astype(bool)]
                row[name] = (f"高點後 {(lit[0].to_period('M') - pk_d.to_period('M')).n} 個月才亮({lit[0]:%Y/%m})"
                             if len(lit) else "沒亮")
        rows.append(row)
    return pd.DataFrame(rows)


def each_light(raw: dict, pan: pd.DataFrame | None = None) -> pd.DataFrame:
    """每顆燈單獨看:亮著的月份 vs 沒亮的月份,台積電之後 6 個月的報酬。用來分辨哪顆燈有用、哪顆只是雜訊。"""
    pan = panel(raw) if pan is None else pan
    f6 = pan.close.shift(-6) / pan.close - 1
    rows = []
    for key, name, *_ in LIGHTS:
        on, off = f6[pan[key].astype(bool)].dropna(), f6[~pan[key].astype(bool)].dropna()
        rows.append({"指標": name, "亮的月數": len(on), "亮時:之後 6 個月中位數%": round(on.median() * 100, 1) if len(on) else None,
                     "亮時:下跌比例%": round((on < 0).mean() * 100) if len(on) else None,
                     "亮時:最差%": round(on.min() * 100, 1) if len(on) else None,
                     "沒亮時:之後 6 個月中位數%": round(off.median() * 100, 1), "沒亮時:下跌比例%": round((off < 0).mean() * 100)})
    return pd.DataFrame(rows)


def backtest(raw: dict, pan: pd.DataFrame | None = None) -> pd.DataFrame:
    """每個月底依客戶端三顆燈亮幾顆分組,看台積電之後 6 個月、12 個月的報酬(未還原,不含股息)。月份彼此重疊,樣本不獨立。"""
    pan = panel(raw) if pan is None else pan
    c = pan.close
    f6, f12 = c.shift(-6) / c - 1, c.shift(-12) / c - 1
    lo6 = pd.Series([c.iloc[i + 1:i + 7].min() / c.iloc[i] - 1 if i + 6 < len(c) else float("nan") for i in range(len(c))], index=c.index)
    rows = []
    for lab, mask in (("0 顆", pan.core == 0), ("1 顆", pan.core == 1), ("2 顆", pan.core == 2), ("3 顆", pan.core == 3)):
        a, b, l = f6[mask].dropna(), f12[mask].dropna(), lo6[mask].dropna()
        if not len(a):
            continue
        rows.append({"客戶端亮燈": lab, "月數": int(mask.sum()), "之後 6 個月中位數%": round(a.median() * 100, 1),
                     "6 個月下跌的比例%": round((a < 0).mean() * 100), "6 個月內最深跌幅中位數%": round(l.median() * 100, 1),
                     "6 個月最差%": round(a.min() * 100, 1), "之後 12 個月中位數%": round(b.median() * 100, 1) if len(b) else None,
                     "12 個月下跌的比例%": round((b < 0).mean() * 100) if len(b) else None})
    return pd.DataFrame(rows)


def _others(raw: dict) -> dict[str, pd.Series]:
    out = {}
    for nm, key in (("台積電", "px"), ("川湖", "px2059"), ("銅", "copper")):
        s = pd.Series(raw.get(key, {}), dtype=float)
        s.index = pd.to_datetime(s.index)
        out[nm] = s.sort_index()
    return out


def others_peaks(raw: dict, pan: pd.DataFrame | None = None) -> pd.DataFrame:
    """台積電每次修正:川湖、銅自己的高點比台積電早或晚幾天(高點前 12 個月到低點之間找),台積電見高那天它們離自己高點多遠。"""
    o, rows = _others(raw), []
    if o["川湖"].empty or o["銅"].empty:
        return pd.DataFrame()
    for _, e in episodes(raw, pan).iterrows():
        pk, lo = pd.Timestamp(e["股價高點"]), pd.Timestamp(e["低點"])
        row = {"台積電高點": e["股價高點"], "台積電跌幅%": e["跌幅%"]}
        for nm in ("川湖", "銅"):
            s = o[nm]
            w = s[(s.index >= pk - pd.DateOffset(months=12)) & (s.index <= lo)]
            pre = s[(s.index >= pk - pd.DateOffset(months=12)) & (s.index <= pk)]
            if len(w) < 50 or pre.empty:
                row[nm + "高點"] = "沒資料"
                continue
            lead = (w.idxmax() - pk).days
            row[nm + "高點"] = f"{w.idxmax():%Y/%m/%d}({'早' if lead < 0 else '晚'} {abs(lead)} 天)" if lead else f"{w.idxmax():%Y/%m/%d}(同一天)"
            row[f"台積電見高當天{nm}離自己高點%"] = round((pre.iloc[-1] / pre.max() - 1) * 100)
        rows.append(row)
    return pd.DataFrame(rows)


def others_backtest(raw: dict) -> pd.DataFrame:
    """2010 年起每個月底:台積電離一年高點 5% 以內時,川湖/銅有沒有跟上,之後 6 個月台積電的報酬。"""
    o = _others(raw)
    t, k = o["台積電"], o["川湖"]
    if t.empty or k.empty or o["銅"].empty:
        return pd.DataFrame()
    cu = o["銅"].reindex(t.index, method="ffill")
    ends = t.groupby(t.index.to_period("M")).apply(lambda s: s.index[-1])
    ends = ends[ends >= pd.Timestamp("2010-01-01")].values
    off = lambda s: (s / s.rolling(250, min_periods=120).max() - 1).reindex(ends, method="ffill")
    T, K, C = off(t), off(k), off(cu)
    tm = t.reindex(ends)
    f6 = tm.shift(-6) / tm - 1
    near, rows = T >= -0.05, []
    for lab, mask in (("台積電離一年高點 5% 以內(基準)", near),
                      ("…而且川湖離自己高點 ≥15%", near & (K <= -0.15)),
                      ("…而且川湖也在高點附近(<10%)", near & (K > -0.10)),
                      ("…而且銅離自己高點 ≥15%", near & (C <= -0.15)),
                      ("…川湖和銅都離高點 ≥10%", near & (K <= -0.10) & (C <= -0.10))):
        a = f6[mask.fillna(False).astype(bool)].dropna()
        rows.append({"情況": lab, "月數": len(a), "之後 6 個月中位數%": round(a.median() * 100, 1),
                     "下跌的比例%": round((a < 0).mean() * 100), "最差%": round(a.min() * 100, 1)})
    return pd.DataFrame(rows)


def members(raw: dict, g: str) -> pd.DataFrame:
    """族群每一檔:存貨現在和一年前、存貨年增 vs 營收年增、存貨天數(現在/一年前/2022Q1~2023Q2 的最高)。全部列出。"""
    rows = []
    for c in GROUPS[g][1]:
        x = _qframe(raw, c)
        if len(x) < 5:
            continue
        d = x.inv / x.cogs * 91
        pk = d[(d.index >= "2022-03-31") & (d.index <= "2023-06-30")]
        a, b = x.iloc[-1], x.iloc[-5]
        rows.append({"代號": c, "名稱": raw["names"].get(c, ""), "季別": f"{x.index[-1]:%Y}Q{(x.index[-1].month - 1) // 3 + 1}",
                     "存貨(億)": round(a.inv / 1e8), "一年前(億)": round(b.inv / 1e8),
                     "存貨年增%": round((a.inv / b.inv - 1) * 100), "營收年增%": round((a.rev / b.rev - 1) * 100),
                     "差距(點)": round((a.inv / b.inv - a.rev / b.rev) * 100),
                     "存貨天數": round(d.iloc[-1]), "一年前天數": round(d.iloc[-5]),
                     "2022~23 最高天數": round(pk.max()) if len(pk) else None})
    return pd.DataFrame(rows).sort_values("差距(點)", ascending=False).reset_index(drop=True)


def us_table(raw: dict) -> pd.DataFrame:
    rows = []
    for t, r in raw.get("us", {}).items():
        x = pd.DataFrame(r)
        if len(x) < 5:
            continue
        a, b = x.iloc[-1], x.iloc[-5]
        rows.append({"代號": t, "季底": a.date, "存貨(億美元)": round(a.inv / 1e8), "一年前(億美元)": round(b.inv / 1e8),
                     "存貨年增%": round((a.inv / b.inv - 1) * 100), "營收年增%": round((a.rev / b.rev - 1) * 100),
                     "差距(點)": round((a.inv / b.inv - a.rev / b.rev) * 100),
                     "存貨天數": round(a.inv / a.cogs * 91), "一年前天數": round(b.inv / b.cogs * 91)})
    return pd.DataFrame(rows)


def figure(raw: dict, pan: pd.DataFrame | None = None):
    """上:台積電月底收盤(對數);下:六顆燈每個月亮不亮(只用當時已知的資料)。"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    import ui_theme as T
    pan = panel(raw) if pan is None else pan
    keys, names = [k for k, *_ in LIGHTS], [n for _, n, *_ in LIGHTS]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.56, 0.44], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=pan.index, y=pan.close, mode="lines", line=dict(width=2, color=T.TEXT), name="台積電月底收盤",
                             customdata=pan.core, hovertemplate="%{x|%Y/%m} 收 %{y:,.0f}|客戶端亮 %{customdata} 顆<extra></extra>"), row=1, col=1)
    z = [[1 if v else 0 for v in pan[k]] for k in keys][::-1]
    fig.add_trace(go.Heatmap(x=pan.index, y=names[::-1], z=z, zmin=0, zmax=1, showscale=False, xgap=1, ygap=3,
                             colorscale=[[0, "rgba(148,163,184,0.14)"], [1, "#DC2626"]],
                             hovertemplate="%{x|%Y/%m} %{y}:%{z}<extra></extra>"), row=2, col=1)
    fig.update_yaxes(type="log", title="元(對數)", gridcolor=T.GRID, row=1, col=1)
    fig.update_yaxes(tickfont=dict(size=12), row=2, col=1)
    fig.update_xaxes(gridcolor=T.GRID)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=44, b=10), showlegend=False, hovermode="x",
                      title="台積電股價 vs 六顆庫存循環燈(紅=那個月底亮著,只用當時已經公布的資料)",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=T.TEXT))
    return fig


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
        sys.exit(0)
    R = load_raw()
    if not R:
        sys.exit("沒有 data/chip_cycle.json,先跑:python -X utf8 chip_cycle.py fetch")
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 60)
    P = panel(R)
    print(f"資料建立 {R['made']}|台積電 {P.index[-1]:%Y-%m-%d} 收 {P.close.iloc[-1]:,.0f}|客戶端三顆現在亮 {P.core.iloc[-1]} 顆(六顆共亮 {P.n.iloc[-1]})")
    print(now(R, P).to_string(index=False))
    print("\n歷次修正(從歷史高點跌超過兩成)前後的亮燈順序")
    print(episodes(R, P).T.to_string())
    print("\n依亮燈顆數看之後的報酬")
    print(backtest(R, P).to_string(index=False))
    print("\n每顆燈單獨看")
    print(each_light(R, P).to_string(index=False))
    for g in ("design", "system"):
        print(f"\n{GROUPS[g][0]} 成分股")
        print(members(R, g).to_string(index=False))
    print("\n美國大客戶")
    print(us_table(R).to_string(index=False))
    print("\n川湖、銅(測過、不亮燈)")
    print(others_peaks(R, P).T.to_string())
    print(others_backtest(R).to_string(index=False))

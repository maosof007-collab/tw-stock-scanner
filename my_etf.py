"""
my_etf.py — 我的 ETF(自組模擬基金,對標 00981A 概念)
=================================================================
00981A 選股指紋(2026-09-11 逆向工程):前300大 × 營收YoY>30% × AI題材集中
× 波段動能;50檔、top10佔67%。本模組=用系統訊號自組一籃,每日算淨值
對比大盤,持股進出全記錄(像經理人一樣寫決策)。
存檔:data/my_etf.json;淨值=固定權重日報酬加權(改組=再平衡)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
STORE = ROOT / "data" / "my_etf.json"


def load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"name": "我的ETF", "inception": f"{now_tw():%Y-%m-%d}",
            "constituents": [], "log": []}


def save(d: dict) -> None:
    STORE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def set_constituents(rows: list[dict], note: str = "") -> dict:
    """rows=[{code,name,weight,thesis}];權重自動正規化;變動寫進 log。"""
    d = load()
    tot = sum(float(r.get("weight", 0)) for r in rows) or 1.0
    for r in rows:
        r["weight"] = round(float(r.get("weight", 0)) / tot * 100, 2)
    d["log"].append({"date": f"{now_tw():%Y-%m-%d}",
                     "note": note or "改組",
                     "constituents": [f"{r['code']}×{r['weight']}%" for r in rows]})
    d["constituents"] = rows
    save(d)
    return d


def _px(code: str) -> pd.Series | None:
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            df = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
            s = pd.Series(pd.to_numeric(df["Close"], errors="coerce").values,
                          index=df["Date"].astype(str))
            return s[~s.index.duplicated()].sort_index()
    return None


def nav_series(since: str | None = None) -> pd.DataFrame:
    """淨值(基期100)vs 大盤。固定權重(每日再平衡近似)。"""
    d = load()
    cons = d["constituents"]
    if not cons:
        return pd.DataFrame()
    since = since or d.get("inception")
    b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
    bench = pd.Series(pd.to_numeric(b["Close"], errors="coerce").values,
                      index=b["Date"].astype(str)).sort_index()
    bench = bench[bench.index >= since]
    if bench.empty:
        return pd.DataFrame()
    rets = pd.DataFrame(index=bench.index)
    for c in cons:
        s = _px(c["code"])
        if s is None:
            continue
        s = s.reindex(bench.index).ffill()
        rets[c["code"]] = s.pct_change().fillna(0) * (c["weight"] / 100)
    port_ret = rets.sum(axis=1)
    out = pd.DataFrame({
        "date": bench.index,
        "我的ETF": (1 + port_ret).cumprod() * 100,
        "大盤": bench / bench.iloc[0] * 100,
    }).reset_index(drop=True)
    return out


def stats(nav: pd.DataFrame) -> dict:
    if nav.empty or len(nav) < 2:
        return {}
    me, bm = nav["我的ETF"], nav["大盤"]
    dd = (me / me.cummax() - 1).min() * 100
    return {"報酬%": round(float(me.iloc[-1]) - 100, 1),
            "大盤%": round(float(bm.iloc[-1]) - 100, 1),
            "超額pp": round(float(me.iloc[-1] - bm.iloc[-1]), 1),
            "最大回撤%": round(float(dd), 1),
            "天數": len(nav)}


# 00981A top10(2026-09-11 口袋證券)— 對照用
ETF_00981A_TOP10 = [("2330", "台積電", 10.24), ("2383", "台光電", 8.99),
                    ("2454", "聯發科", 8.62), ("3017", "奇鋐", 7.25),
                    ("3037", "欣興", 7.11), ("6669", "緯穎", 5.36),
                    ("3653", "健策", 5.05), ("6223", "旺矽", 5.04),
                    ("2327", "國巨", 5.03), ("2303", "聯電", 4.47)]


def candidates() -> pd.DataFrame:
    """建倉候選池=系統三訊號交集:①營收YoY>30%(00981A指紋)②權證佈局中/體檢卡不紅。"""
    rows = []
    try:
        h = pd.read_csv(ROOT / "data" / "_rev_history.csv", dtype={"code": str})
        last = h.sort_values("ym").groupby("code").tail(1)
        strong = last[last["yoy"] > 30]
        import warrant_flow as wf
        sc = wf.market_scan(min_med=3.0)
        blue = set(sc[sc["動向"].isin(["🔵 佈局中", "🔥 近5日湧入"])]["ucode"])
        import pretrade
        sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        nm = dict(zip(sl["code"], sl["name"]))
        for c in strong[strong["code"].isin(blue)]["code"].head(15):
            hc = pretrade.health_check(c)
            reds = sum(1 for x in hc["rows"] if x["燈"] == "🔴")
            yoy = float(strong[strong["code"] == c]["yoy"].iloc[0])
            rows.append({"代號": c, "名稱": nm.get(c, ""), "最新YoY%": round(yoy, 1),
                         "權證資金": "🔵/🔥", "體檢": hc["verdict"].split("(")[0],
                         "紅燈": reds})
    except Exception as e:
        rows.append({"代號": f"(候選池計算失敗:{e})"})
    return pd.DataFrame(rows)


def swap_alerts() -> list[str]:
    """換股提醒(頁面頂部橫幅用):①自建倉落後大盤≥10pp ②體檢紅燈≥2
    ③權證轉⚫退潮 ④距20日高≤-15%(超出天量統計常態洗盤)。"""
    d = load()
    if not d["constituents"]:
        return []
    since = d.get("inception")
    b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
    tw = pd.Series(pd.to_numeric(b["Close"], errors="coerce").values,
                   index=b["Date"].astype(str)).sort_index()
    tw = tw[tw.index >= since]
    tw_ret = float(tw.iloc[-1] / tw.iloc[0] - 1) * 100 if len(tw) > 1 else 0.0
    alerts = []
    for c in d["constituents"]:
        code = c["code"]
        if code == "CASH":
            continue
        s = _px(code)
        if s is None or s.empty:
            continue
        win = s[s.index >= since]
        if len(win) > 1:
            ret = float(win.iloc[-1] / win.iloc[0] - 1) * 100
            if ret - tw_ret <= -10:
                alerts.append(f"🔻 {code} {c['name']}:建倉以來 {ret:+.1f}% 落後大盤 "
                              f"{ret - tw_ret:.1f}pp——**該檢討換股**")
        hi20 = float(s.tail(20).max())
        off = float(s.iloc[-1] / hi20 - 1) * 100
        if off <= -15:
            alerts.append(f"🔻 {code} {c['name']}:距20日高 {off:.1f}%,超出常態洗盤(-11%)——查論點")
        try:
            import pretrade
            hc = pretrade.health_check(code)
            reds = sum(1 for x in hc["rows"] if x["燈"] == "🔴")
            if reds >= 2:
                alerts.append(f"🟥 {code} {c['name']}:體檢紅燈 {reds}——列入換股檢視")
        except Exception:
            pass
        try:
            import warrant_flow as wf
            sf = wf.sustained_flow(code)
            if sf and str(sf.get("verdict", "")).startswith("⚫"):
                alerts.append(f"⚫ {code} {c['name']}:權證錢退潮——抬轎資金離場中")
        except Exception:
            pass
    return alerts


def daily_review() -> str:
    """每日 ETF 檢討(規則式):淨值/每檔動態/家規警示/00981A 對照。存進文章庫。"""
    import pretrade
    d = load()
    if not d["constituents"]:
        return ""
    nav = nav_series()
    s = stats(nav) if not nav.empty else {}
    L = [f"# 我的ETF 日檢 {now_tw():%Y-%m-%d}", ""]
    if s:
        L.append(f"**淨值**:{100 + s['報酬%']:.1f}(報酬 {s['報酬%']:+.1f}% vs 大盤 "
                 f"{s['大盤%']:+.1f}%,超額 {s['超額pp']:+.1f}pp;最大回撤 {s['最大回撤%']}%)")
    L.append("")
    L.append("## 成分股檢視")
    alerts = []
    for c in d["constituents"]:
        code = c["code"]
        if code == "CASH":
            L.append(f"- 現金 {c['weight']}%:乾火藥待命")
            continue
        px = _px(code)
        day = None
        if px is not None and len(px) > 1:
            day = round(float(px.iloc[-1] / px.iloc[-2] - 1) * 100, 1)
        reds = None
        try:
            hc = pretrade.health_check(code)
            reds = sum(1 for x in hc["rows"] if x["燈"] == "🔴")
        except Exception:
            pass
        line = (f"- **{code} {c['name']}**({c['weight']}%):日{day:+.1f}%"
                if day is not None else f"- **{code} {c['name']}**({c['weight']}%)")
        if reds is not None:
            line += f"|體檢紅燈 {reds}"
        L.append(line)
        if day is not None and day <= -5:
            alerts.append(f"{code} 單日 {day:+.1f}%——查原因;論點未破則屬統計常態洗盤")
        if reds is not None and reds >= 2:
            alerts.append(f"{code} 體檢紅燈 {reds}——列入改組檢視")
    if alerts:
        L.append("")
        L.append("## ⚠️ 家規警示")
        L += [f"- {a}" for a in alerts]
    try:
        import etf_holdings as eh
        diff = eh.diff_latest("00981A")
        moves = diff[diff["動作"] != ""] if not diff.empty else diff
        if not moves.empty:
            L.append("")
            L.append("## 🆚 00981A 今日動作(對照)")
            for _, r in moves.iterrows():
                L.append(f"- {r['code']} {r['name']}:{r['動作']}({r['張數增減']:+,.0f}張)")
    except Exception:
        pass
    L.append("")
    L.append("*每日自動產生;改組請上頁24並寫備註。非投資建議。*")
    content = "\n".join(L)
    from analyst_report import save_article
    fn = save_article("ETF", "我的ETF", "ETF日檢", content)
    print(f"[my_etf] 日檢 {fn}")
    return fn

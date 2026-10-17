# -*- coding: utf-8 -*-
"""
forecast_card.py — 估值前瞻引擎(三情境EPS×PE帶×我們的全套檢查)
=================================================================
起因(2026-10-17):用戶看到外部「個股估值前瞻」卡(三情境EPS+機率、機構共識、
總經傳導路徑、護城河證據分級、最沒把握的地方),要求融合進本系統並掛上自家功能。
融合點(外部卡沒有、我們有的):
  業外剝離 core EPS(頁28 教案 2436)/法說庫對接/券商觀點對接/家規前置檢查
  (爆量窗·迴轉率警戒·處置)/風險燈傳導/同業毛利率排名(全市場季報算的,不是抄的)
錨定邏輯(照外部卡的正確做法):今年已公布季 EPS 鎖下檔,剩餘季用 run-rate 外推三情境。
素材層級:法說>投顧>新聞——tp_radar 是 FactSet 新聞流,非全量共識,頁面必須標註。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"
FC = D / "forecasts"
FC.mkdir(exist_ok=True)


# ---------------------------------------------------------------- 錨與三情境
def anchor(code: str) -> dict:
    """已實現EPS錨+三情境全年EPS預設值。全部欄位可被頁面覆寫——這是預設不是聖旨。"""
    import fundamentals as F
    q = F.quarterly_fin(code, years=4)
    out = {"ok": False}
    if q is None or q.empty or "EPS" not in q:
        return out
    qq = q.dropna(subset=["EPS"]).copy()
    qq["dt"] = pd.to_datetime(qq["季度"])
    qq = qq.sort_values("dt")
    yr = now_tw().year
    cur = qq[qq["dt"].dt.year == yr]
    realized = float(cur["EPS"].sum())
    n_left = 4 - len(cur)
    e4 = float(qq["EPS"].tail(4).mean())
    e2 = float(qq["EPS"].tail(2).mean())
    base = realized + n_left * e2
    cons = realized + n_left * min(e4, e2 * 0.85)
    opt = realized + n_left * e2 * 1.15
    # 業外剝離(頁28 同法):淨利率>營益率過多=業外撐的 EPS,估值要打折
    core, nonop = [], []
    for _, r in qq.tail(4).iterrows():
        ni, op, e = r.get("淨利率%"), r.get("營益率%"), float(r["EPS"])
        if pd.notna(ni) and pd.notna(op) and float(ni) > 0:
            core.append(e * max(0.0, min(float(op) / float(ni), 1.2)))
            nonop.append(max(0.0, 1 - float(op) / float(ni)))
        else:
            core.append(e); nonop.append(0.0)
    ttm = float(qq["EPS"].tail(4).sum())
    # 完整年度 EPS 均值(近5年)——循環股偵測用:TTM 遠低於歷史均值=獲利谷底,PE 帶失真
    yr_eps = [float(g["EPS"].sum()) for y, g in qq.groupby(qq["dt"].dt.year)
              if len(g) == 4 and y < yr]
    yr_avg = round(sum(yr_eps[-5:]) / len(yr_eps[-5:]), 2) if yr_eps else None
    out.update(ok=True, realized=round(realized, 2), n_done=len(cur), n_left=n_left,
               yr_avg_eps=yr_avg,
               ttm=round(ttm, 2), ttm_core=round(float(sum(core)), 2),
               nonop_pct=round(float(sum(nonop) / len(nonop)) * 100) if nonop else 0,
               scen={"保守": round(cons, 2), "基準": round(base, 2), "樂觀": round(opt, 2)},
               q=qq, year=yr)
    return out


def pe_band(code: str, qq: pd.DataFrame) -> dict | None:
    """近3年歷史PE P25/P50/P75(月末價÷當時已知TTM;季報+45天為可得日)。"""
    for suf in (".TW", ".TWO"):
        p = D / f"{code}{suf}.csv"
        if p.exists():
            px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
            break
    else:
        return None
    px["Date"] = pd.to_datetime(px["Date"])
    close = float(px["Close"].iloc[-1])
    px = px[px["Date"] >= pd.Timestamp(now_tw().date()) - pd.Timedelta(days=365 * 3)]
    a = qq.copy()
    a["ttm"] = a["EPS"].rolling(4).sum()
    a = a.dropna(subset=["ttm"])
    a["ok"] = a["dt"] + pd.Timedelta(days=45)
    me = px.groupby(px["Date"].dt.to_period("M")).last()
    pes = []
    for _, r in me.iterrows():
        known = a[a["ok"] <= r["Date"]]
        if not known.empty and known["ttm"].iloc[-1] > 0:
            pe = r["Close"] / known["ttm"].iloc[-1]
            if 0 < pe < 150:
                pes.append(pe)
    if len(pes) < 6:
        return None
    s = pd.Series(pes)
    return {"P25": round(float(s.quantile(.25)), 1), "P50": round(float(s.quantile(.5)), 1),
            "P75": round(float(s.quantile(.75)), 1), "close": close}


# ---------------------------------------------------------------- 同業(有數字的護城河)
def peer_rank(code: str) -> dict | None:
    """所屬 theme_groups 族群內,最新季毛利率/營益率排名——「依據」欄自動生成。"""
    try:
        from theme_groups import THEME_GROUPS
        import symbols
    except Exception:
        return None
    grp = next(((t, c) for t, c in THEME_GROUPS.items() if code in c), None)
    if not grp:
        return None
    theme, codes = grp
    try:
        q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    except Exception:
        return None
    last = (q[q.code.isin(codes)].sort_values("季度")
             .groupby("code").tail(1).dropna(subset=["毛利率%"]))
    if last.empty or code not in set(last.code):
        return None
    rows = []
    for _, r in last.iterrows():
        try:
            nm = symbols.resolve(r.code)[1] or r.code
        except Exception:
            nm = r.code
        rows.append({"代碼": r.code, "名稱": nm, "毛利率%": round(r["毛利率%"], 2),
                     "營益率%": round(r.get("營益率%", float("nan")), 2),
                     "EPS": r.get("EPS")})
    df = pd.DataFrame(rows).sort_values("毛利率%", ascending=False).reset_index(drop=True)
    rank = int(df.index[df["代碼"] == code][0]) + 1
    return {"族群": theme, "排名": rank, "共": len(df), "表": df}


# ---------------------------------------------------------------- 家規/籌碼/素材旗標
def flags(code: str) -> dict:
    f = {}
    try:                                           # 處置
        from disposal import current_set
        f["處置中"] = code in current_set()
    except Exception:
        f["處置中"] = None
    try:                                           # 迴轉率警戒
        t = pd.read_csv(D / "_turnover.csv", dtype={"代碼": str})
        hit = t[t["代碼"] == code]
        f["迴轉率警戒"] = bool(len(hit)) and ("🔪" in str(hit.iloc[0].get("標記", "")))
    except Exception:
        f["迴轉率警戒"] = None
    try:                                           # 爆量窗(家規:近2日量>2.3×20日均)
        for suf in (".TW", ".TWO"):
            p = D / f"{code}{suf}.csv"
            if p.exists():
                px = pd.read_csv(p, usecols=["Volume"]).dropna()
                v = px["Volume"].astype(float)
                m = v.shift(1).rolling(20).mean()
                f["爆量窗"] = bool((v.tail(2) > m.tail(2) * 2.3).any())
                break
    except Exception:
        f["爆量窗"] = None
    try:                                           # 外資 20 日
        d = pd.read_csv(D / "institutional" / f"{code}_inst.csv")
        fi = pd.to_numeric(d.iloc[:, 4], errors="coerce").dropna()
        f["外資買超天(20日)"] = int((fi.tail(20) > 0).sum())
        f["外資累計(張)"] = round(float(fi.tail(20).sum()) / 1000)
    except Exception:
        pass
    decks = sorted((D / "concalls").glob(f"{code}_*.pdf"))   # 法說庫(只讀不抓)
    f["法說"] = decks[-1].stem.split("_")[1] if decks else None
    f["券商觀點"] = (D / "advisory" / code).exists() or bool(
        list((D / "advisory").glob(f"*{code}*"))) if (D / "advisory").exists() else None
    return f


def macro_block() -> dict:
    """風險燈+固定傳導三行(利率→PE、匯率→毛利、AI資本支出→營收)。"""
    out = {"傳導路徑": "美國利率經折現率影響PE評價;美元經匯率影響毛利;AI資本支出經訂單影響營收。"}
    try:
        out["risk"] = json.loads((D / "_market_risk.json").read_text(encoding="utf-8"))
    except Exception:
        out["risk"] = None
    return out


# 匯率傳導:產業別 → 強美元/台幣貶對「這檔」是順風還是成本
_FX_COST = ("塑膠", "化學", "鋼鐵", "水泥", "航運", "油電", "造紙", "橡膠", "食品")   # 進口原料美元計價
_FX_NEUTRAL = ("金融", "營建", "觀光", "貿易百貨", "生技")                            # 內需為主


def _beta(code: str) -> float | None:
    """250日 beta vs 加權指數——風險燈🔴時,高beta=優先縮手的那批。"""
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
        for suf in (".TW", ".TWO"):
            p = D / f"{code}{suf}.csv"
            if p.exists():
                px = pd.read_csv(p, usecols=["Date", "Close"]).dropna()
                break
        else:
            return None
        m = bm.merge(px, on="Date", suffixes=("_bm", "_s")).tail(250)
        rb = m["Close_bm"].pct_change().dropna()
        rs = m["Close_s"].pct_change().dropna()
        if len(rb) < 60:
            return None
        return round(float(rs.cov(rb) / rb.var()), 2)
    except Exception:
        return None


def macro_for(code: str, pe: float | None) -> list[dict]:
    """個股版總經傳導:同一個總經,不同股票的受力點不一樣——這是外部卡的精髓。"""
    rows = []
    # ① 利率→PE(久期):PE 越高,折現率升一碼砍得越痛
    if pe and pe > 0:
        lv = "高" if pe > 30 else ("中" if pe > 12 else "低")
        note = {"高": f"TTM {pe:.0f} 倍=長久期,利率上行時估值端最先挨刀",
                "中": f"TTM {pe:.0f} 倍,利率敏感度中等",
                "低": f"TTM {pe:.0f} 倍,估值已趴在地上,利率傷害有限"}[lv]
        rows.append({"路徑": "利率→PE", "敏感度": lv, "讀法": note})
    b = _beta(code)
    if b is not None:
        rows.append({"路徑": "大盤β", "敏感度": f"{b}",
                     "讀法": ("高β:風險燈🔴時優先縮手的那批" if b > 1.2 else
                              "低β:大盤級風暴中相對抗震" if b < 0.8 else "隨盤")})
    # ② 匯率→毛利:產業別定方向
    sector = ""
    try:
        sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        h = sl[sl["code"] == code]
        sector = h["sector"].iloc[0] if not h.empty else ""
    except Exception:
        pass
    if any(k in sector for k in _FX_COST):
        fx = ("逆風", f"{sector}:原料多為美元計價——強美元/台幣貶=成本上升")
    elif any(k in sector for k in _FX_NEUTRAL):
        fx = ("中性", f"{sector}:內需為主,匯率傳導弱")
    else:
        fx = ("順風", f"{sector or '電子'}:美元收入+台幣成本——台幣貶值=毛利/匯兌順風")
    rows.append({"路徑": "匯率→毛利", "敏感度": fx[0], "讀法": fx[1]})
    # ③ AI資本支出→營收:族群歸屬定連動
    ai_tag = ""
    try:
        from quiet_accum import _ai_tag
        ai_tag = _ai_tag(code)
    except Exception:
        pass
    if not ai_tag:
        try:
            sc = json.loads((D / "supply_chain.json").read_text(encoding="utf-8"))
            for chain, info in sc.items():
                members = info if isinstance(info, list) else info.get("members", [])
                if any(code == str(m).split()[0] or code in str(m) for m in members):
                    ai_tag = chain
                    break
        except Exception:
            pass
    if ai_tag:
        rows.append({"路徑": "AI資本支出→營收", "敏感度": "直接",
                     "讀法": f"屬「{ai_tag}」——CSP資本支出上修=順風;留意資本配給收緊的反面"})
    else:
        rows.append({"路徑": "AI資本支出→營收", "敏感度": "間接/排擠",
                     "讀法": "非AI鏈:當前市場的資本排擠受害端;AI降溫反而是資金回流的受益方"})
    return rows


# ---------------------------------------------------------------- 最沒把握的地方(自動候選)
def uncertainty(code: str, A: dict) -> str:
    cands = []
    s = A.get("scen", {})
    if s and s.get("基準"):
        spread = (s["樂觀"] - s["保守"]) / abs(s["基準"]) * 100
        if spread > 25:
            cands.append((spread, f"三情境 EPS 價差達 {spread:.0f}%(保守 {s['保守']} vs 樂觀 {s['樂觀']})"
                                  "——剩餘季的獲利動能假設直接決定估值落點。"))
    if A.get("nonop_pct", 0) >= 40:
        cands.append((90, f"近4季獲利約 {A['nonop_pct']}% 來自業外——本業 TTM 僅 {A['ttm_core']},"
                          "估值用哪個 EPS,結論差一倍。"))
    try:
        qq = A["q"].tail(4)
        gm = qq["毛利率%"].dropna()
        rev = qq["營收(億)"].dropna()
        if len(gm) >= 3 and gm.iloc[-1] < gm.iloc[0] - 2 and rev.iloc[-1] > rev.iloc[0]:
            cands.append((70, f"營收升、毛利率連降({gm.iloc[0]:.1f}%→{gm.iloc[-1]:.1f}%)"
                              "——以價換量還是結構轉差,下一季毛利率見真章。"))
    except Exception:
        pass
    try:
        import fundamentals as F
        mon = F.monthly_revenue(code, 2).dropna(subset=["yoy%"])
        if len(mon) >= 2 and mon["yoy%"].iloc[-1] < mon["yoy%"].iloc[-2] - 10:
            cands.append((60, f"月營收年增降速({mon['yoy%'].iloc[-2]:+.1f}%→{mon['yoy%'].iloc[-1]:+.1f}%)"
                              "——是基期墊高還是動能熄火,需要再一個月驗證。"))
    except Exception:
        pass
    if not cands:
        return "三情境假設本身:剩餘季 run-rate 外推沒有考慮產業事件,法說/財報日前後要重估。"
    return sorted(cands, reverse=True)[0][1]


# ---------------------------------------------------------------- 機構共識(yfinance/FactSet)
def consensus(code: str) -> dict | None:
    """全量券商共識(yfinance 轉 FactSet):目標價均/中/高/低+家數+評等+forward EPS。
    tp_radar 是新聞流(只有最近被報導的股票),這個才是逐檔都查得到的共識庫。"""
    try:
        import yfinance as yf
        suf = ".TW" if (D / f"{code}.TW.csv").exists() else ".TWO"
        t = yf.Ticker(f"{code}{suf}")
        pt = t.analyst_price_targets or {}
        if not pt.get("mean"):
            return None
        out = {k: round(float(v), 1) for k, v in pt.items() if v is not None}
        try:
            info = t.info
            out["家數"] = info.get("numberOfAnalystOpinions")
            out["評等"] = info.get("recommendationKey")
            out["forwardEPS"] = info.get("forwardEps")
        except Exception:
            pass
        return out
    except Exception:
        return None


# ---------------------------------------------------------------- 存取查詢紀錄
def save_card(code: str, payload: dict) -> Path:
    p = FC / f"{code}.json"
    hist = []
    if p.exists():
        try:
            hist = json.loads(p.read_text(encoding="utf-8")).get("history", [])
        except Exception:
            hist = []
    payload["ts"] = now_tw().strftime("%Y-%m-%d %H:%M")
    hist.append(payload)
    p.write_text(json.dumps({"history": hist[-20:]}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def recent_cards(n: int = 10) -> list[dict]:
    rows = []
    for p in FC.glob("*.json"):
        try:
            h = json.loads(p.read_text(encoding="utf-8"))["history"]
            if h:
                rows.append({"code": p.stem, **h[-1]})
        except Exception:
            continue
    return sorted(rows, key=lambda r: r.get("ts", ""), reverse=True)[:n]

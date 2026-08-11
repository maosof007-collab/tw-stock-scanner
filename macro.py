"""
macro.py — 總經/總體環境指標
=================================================
大盤融資維持率（推估）：市場槓桿風險溫度計。
公式：維持率% = 100 × Σ(現值) / (融資成數 × Σ(推估成本))
  · 現值   = 個股收盤 × 融資餘額(張)
  · 成本   = 個股 MA60（融資平均買進成本推估）× 融資餘額(張)
  · 融資成數 = 0.6（上市），故剛買進(現值=成本)時 ≈ 1/0.6 = 166.7%
  · 越低＝槓桿壓力越大、越接近追繳(130%)/斷頭(120%)
資料：data/margin/*.csv（融資餘額，張）+ data/{code}.csv（收盤）。維持率為推估。
"""
from __future__ import annotations
import glob, os
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
CACHE = DATA / "_market_margin.csv"
MARGIN_RATE = 0.6     # 融資成數（上市）
COST_MA = 60          # 融資平均成本以 MA60 推估


def _price(code: str):
    for suf in (".TW", ".TWO"):
        p = DATA / f"{code}{suf}.csv"
        if p.exists():
            df = pd.read_csv(p)
            df.columns = [c.lower() for c in df.columns]
            dc = "date" if "date" in df.columns else df.columns[0]
            df = df.rename(columns={dc: "date"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            return df[["date", "close"]].dropna()
    return None


def cache_is_stale() -> bool:
    """快取最後日 < 融資參考檔(2330)最後日 → 過期。無快取=過期。"""
    try:
        ref = pd.read_csv(DATA / "margin" / "2330_margin.csv", usecols=["date"])
        ref_last = str(ref["date"].iloc[-1])[:10]
        c = pd.read_csv(CACHE, usecols=["date"])
        return str(c["date"].iloc[-1])[:10] < ref_last
    except Exception:
        return True


def build_market_margin_series(window_days: int = 500, rebuild: bool = False) -> pd.DataFrame:
    """回傳 DataFrame(date, ratio, margin_lots, twii)。當日算一次，快取到 data/_market_margin.csv。"""
    if CACHE.exists() and not rebuild:
        try:
            c = pd.read_csv(CACHE, parse_dates=["date"])
            if not c.empty:
                return c.tail(window_days).reset_index(drop=True)
        except Exception:
            pass

    files = glob.glob(str(DATA / "margin" / "*.csv"))
    parts = []
    for f in files:
        code = os.path.basename(f).replace("_margin.csv", "")
        try:
            mg = pd.read_csv(f, usecols=["date", "margin_balance", "short_balance"])
            if mg.empty:
                continue
            mg["date"] = pd.to_datetime(mg["date"], errors="coerce")
            mg["margin_balance"] = pd.to_numeric(mg["margin_balance"], errors="coerce")
            mg["short_balance"] = pd.to_numeric(mg["short_balance"], errors="coerce").fillna(0)
            mg = mg.dropna(subset=["date", "margin_balance"])
            mg = mg[mg["margin_balance"] > 0]
            if mg.empty:
                continue
            px = _price(code)
            if px is None or len(px) < COST_MA:
                continue
            px = px.sort_values("date")
            px["ma"] = px["close"].rolling(COST_MA).mean()
            m = mg.merge(px, on="date", how="inner").dropna(subset=["close", "ma"])
            if m.empty:
                continue
            m["numer"] = m["close"] * m["margin_balance"]
            m["cost"] = m["ma"] * m["margin_balance"]
            parts.append(m[["date", "numer", "cost", "margin_balance", "short_balance"]])
        except Exception:
            pass

    if not parts:
        return pd.DataFrame(columns=["date", "ratio", "margin_lots", "twii"])

    allm = pd.concat(parts, ignore_index=True)
    g = allm.groupby("date", as_index=False).sum()
    g["ratio"] = 100 * g["numer"] / (MARGIN_RATE * g["cost"])
    s = g[["date", "ratio", "margin_balance", "short_balance"]].rename(
        columns={"margin_balance": "margin_lots", "short_balance": "short_lots"})
    s = s.sort_values("date").reset_index(drop=True)

    # 併大盤指數
    try:
        bm = pd.read_csv(DATA / "benchmark_TWII.csv")
        bm["date"] = pd.to_datetime(bm["Date"], errors="coerce")
        bm = bm[["date", "Close"]].rename(columns={"Close": "twii"})
        s = s.merge(bm, on="date", how="left")
    except Exception:
        s["twii"] = np.nan

    try:
        s.to_csv(CACHE, index=False)
    except Exception:
        pass
    return s.tail(window_days).reset_index(drop=True)


def seasonal_window() -> dict | None:
    """七/八月神秘窗口（FinLab 提出）：七月前10交易日 + 八月後7交易日。
    用 TWII 實測歷年報酬/勝率，並判斷「今天是否在強勢窗口內」。"""
    p = DATA / "benchmark_TWII.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
    df["y"] = df["Date"].dt.year
    df["m"] = df["Date"].dt.month

    def _wret(sub, n, side):
        s = sub.sort_values("Date").reset_index(drop=True)
        if len(s) < n:
            return None
        if side == "first":
            return (s["Close"].iloc[n - 1] / s["Close"].iloc[0] - 1) * 100
        return (s["Close"].iloc[-1] / s["Close"].iloc[-n] - 1) * 100

    rows = []
    for y in sorted(df["y"].unique()):
        rj = _wret(df[(df.y == y) & (df.m == 7)], 10, "first")
        ra = _wret(df[(df.y == y) & (df.m == 8)], 7, "last")
        if rj is None or ra is None:
            continue
        combo = (1 + rj / 100) * (1 + ra / 100) * 100 - 100
        rows.append({"年": int(y), "七月前10日%": round(rj, 2),
                     "八月後7日%": round(ra, 2), "合併%": round(combo, 2)})
    tbl = pd.DataFrame(rows)
    if tbl.empty:
        return None

    def _agg(c):
        v = tbl[c]
        return {"avg": float(v.mean()), "win": float((v > 0).mean() * 100), "worst": float(v.min())}
    stats = {"jul": _agg("七月前10日%"), "aug": _agg("八月後7日%"), "combo": _agg("合併%")}

    # 目前位置（以最新資料日為準）
    today = df["Date"].iloc[-1]
    m = int(today.month)
    if m == 7:
        tdidx = int((df[(df.y == today.year) & (df.m == 7) & (df.Date <= today)]).shape[0])
        if tdidx <= 10:
            cur = ("🟢 七月強勢窗口", "up", f"第 {tdidx}/10 交易日，續抱到約第 10 日")
        else:
            cur = ("⚪ 七月後半（原地踏步）", "muted", "強勢段已過，等八月底")
    elif m == 8:
        tdidx = int((df[(df.y == today.year) & (df.m == 8) & (df.Date <= today)]).shape[0])
        if tdidx <= 3:
            cur = ("🔴 八月月初偏弱", "down", "月初平均下跌、勝率低，觀望")
        elif tdidx >= 16:
            cur = ("🟢 八月強勢窗口（最後7日）", "up", "接近月底強勢段")
        else:
            cur = ("⚪ 八月月中（陰跌）", "muted", "等最後 7 個交易日")
    else:
        cur = ("⚪ 窗口外", "muted", "非七月前段／八月末段")

    return {"table": tbl, "stats": stats, "current": cur, "as_of": str(today.date())}


def market_margin_table(days: int = 20) -> pd.DataFrame:
    """大盤融資融券日表(最新在上):日期/加權指數/融資餘額/增減/維持率/融券餘額/增減。"""
    s = build_market_margin_series(window_days=days + 5)
    if s.empty:
        return pd.DataFrame()
    t = s.tail(days + 1).copy()
    t["融資增減"] = t["margin_lots"].diff()
    if "short_lots" in t.columns:
        t["融券增減"] = t["short_lots"].diff()
    t = t.tail(days)
    out = pd.DataFrame({
        "日期": pd.to_datetime(t["date"]).dt.strftime("%Y-%m-%d"),
        "加權指數": t["twii"].round(0) if "twii" in t.columns else np.nan,
        "融資餘額(張)": t["margin_lots"].round(0),
        "融資增減": t["融資增減"].round(0),
        "維持率(推估)%": t["ratio"].round(1),
    })
    if "short_lots" in t.columns:
        out["融券餘額(張)"] = t["short_lots"].round(0)
        out["融券增減"] = t["融券增減"].round(0)
    return out.iloc[::-1].reset_index(drop=True)


def market_margin_conclusion(tbl: pd.DataFrame) -> list[str]:
    """大盤融資融券每日結論(白話,含台指期結算對應)。"""
    if tbl.empty or len(tbl) < 6:
        return ["資料不足,無法下結論。"]
    t = tbl.iloc[::-1].reset_index(drop=True)          # 舊→新
    out = []
    mb = t["融資餘額(張)"].astype(float)
    d5 = mb.iloc[-1] - mb.iloc[-6]
    pct5 = d5 / max(mb.iloc[-6], 1) * 100
    mr = float(t["維持率(推估)%"].iloc[-1])
    # ① 融資
    if pct5 < -3:
        out.append(f"🔻 **全市場融資近5日大減 {d5:+,.0f} 張({pct5:+.1f}%)**——散戶槓桿快速退場:"
                   "若指數同步止穩=籌碼沉澱、浮額清洗(偏正面);若指數續跌=多殺多退潮進行中。")
    elif pct5 > 3:
        out.append(f"🔺 **全市場融資近5日大增 {d5:+,.0f} 張({pct5:+.1f}%)**——散戶槓桿追價,"
                   "行情火熱但籌碼轉浮動,拉回時融資多殺多會放大跌幅。")
    else:
        out.append(f"➖ 全市場融資近5日 {d5:+,.0f} 張({pct5:+.1f}%),槓桿變化平穩。")
    # ② 維持率
    if mr < 130:
        out.append(f"🚨 **大盤維持率推估 {mr:.1f}%,跌破追繳線(130)**——全市場融資戶進入追繳/斷頭區,"
                   "強制賣壓與跌深反彈會劇烈交錯,槓桿者先降倉。")
    elif mr < 140:
        out.append(f"⚠️ **大盤維持率推估 {mr:.1f}%(130~140 高壓區)**——距追繳線僅"
                   f" {mr-130:.1f} 個百分點,指數再跌 {max((1-130/mr)*100,0):.0f}% 就見系統性斷頭潮,"
                   "此區歷史上常出現急殺與 V 彈並存。")
    elif mr < 150:
        out.append(f"🟡 大盤維持率推估 {mr:.1f}%(警戒區)——融資普遍套牢,反彈到解套區賣壓重。")
    elif mr >= 166:
        out.append(f"🟢 大盤維持率推估 {mr:.1f}%(≥166 健康)——融資結構乾淨,槓桿風險低。")
    else:
        out.append(f"⚪ 大盤維持率推估 {mr:.1f}%,正常範圍。")
    # ③ 融券
    if "融券餘額(張)" in t.columns:
        sb = t["融券餘額(張)"].astype(float)
        d5s = sb.iloc[-1] - sb.iloc[-6]
        px_up = float(t["加權指數"].iloc[-1]) > float(t["加權指數"].iloc[-6]) \
            if "加權指數" in t.columns and pd.notna(t["加權指數"].iloc[-1]) else False
        if d5s < 0 and px_up:
            out.append(f"🧯 **全市場融券近5日回補 {d5s:+,.0f} 張且指數上漲=軋空行情**,"
                       "空單燃料續燒前不宜逆勢摸頭。")
        elif d5s < 0:
            out.append(f"🧯 全市場融券近5日回補 {d5s:+,.0f} 張,空方退場。")
        elif d5s > 0:
            out.append(f"🩳 全市場融券近5日 +{d5s:,.0f} 張,空方布局增加"
                       + ("(指數仍漲=空單持續累積軋空燃料)。" if px_up else "。"))
    # ④ 期貨結算
    try:
        from analyst_report import next_futures_settlement
        sdate, dleft = next_futures_settlement()
        if dleft <= 2:
            out.append(f"⏰ **台指期結算日 {sdate:%m/%d}(剩 {dleft} 天)**——結算前融券強制回補、"
                       "期現套利平倉放大指數波動;結算日的融資融券變化屬技術性進出,隔日再解讀。")
        elif dleft <= 7:
            out.append(f"📅 進入台指期結算週(結算日 {sdate:%m/%d})——高融券+指數撐高檔=結算前軋空常見;"
                       "高融資+指數轉弱=壓低結算風險,留意期現價差方向。")
        else:
            out.append(f"📅 下次台指期結算日 {sdate:%m/%d}(約 {dleft} 天後),非結算干擾期,籌碼可照常解讀。")
    except Exception:
        pass
    return out


def margin_status(ratio: float, warn: float = 150.0) -> tuple[str, str]:
    """回傳 (狀態文字, 顏色鍵)。130 追繳、120 斷頭。"""
    if ratio is None or np.isnan(ratio):
        return "無資料", "muted"
    if ratio < 130:
        return "⚠️ 接近追繳/斷頭", "down"
    if ratio < warn:
        return "警戒（槓桿偏高）", "ma30"
    if ratio >= 175:
        return "安全（槓桿寬鬆）", "up"
    return "正常", "text"

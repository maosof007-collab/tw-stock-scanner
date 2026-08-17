"""
us_peers.py — 族群對應的美股同業對照(給批次報告縫進推論)
=================================================================
台股很多族群跟著美股同業走(CPO 跟 AXT/Lumentum/Coherent 財報與指引):
抓近四季營收+YoY、毛利率、近20日股價,織成文字數據包。
來源 yfinance;20小時快取,失敗退回舊快取。
"""
from __future__ import annotations
import json
import time
from pathlib import Path

FUND_DIR = Path(__file__).parent / "data" / "fundamentals"
FUND_DIR.mkdir(parents=True, exist_ok=True)
CACHE_HOURS = 20

# 族群 → 美股同業(對照觀察標的,不是持股建議)
US_PEERS = {
    "光通訊CPO": ["AXTI", "LITE", "COHR", "AAOI", "FN", "CRDO"],
    # AXT(磷化銦/砷化鎵基板)/Lumentum/Coherent/Applied Opto/Fabrinet/Credo
    "封測":      ["AMKR"],                 # Amkor
    "晶圓代工":  ["GFS", "INTC"],          # GlobalFoundries/Intel
    "矽晶圓":    ["ONTO"],
    "記憶體":    ["MU"],
    "AI伺服器":  ["SMCI", "DELL"],
    "散熱":      ["VRT"],
    "貨櫃航運":  ["ZIM", "MATX"],          # 以星航運/美森——貨櫃運價景氣溫度計
    "散裝航運":  ["BDRY", "GOGL", "SBLK"], # BDRY=乾散裝運價期貨ETF(≈BDI代理)
}


def _one(tkr: str) -> str:
    import yfinance as yf
    t = yf.Ticker(tkr)
    parts = [tkr]
    try:
        h = t.history(period="3mo")["Close"].dropna()
        if len(h) > 20:
            parts.append(f"股價 {h.iloc[-1]:.1f} 美元(近20日 {(h.iloc[-1]/h.iloc[-21]-1)*100:+.1f}%)")
    except Exception:
        pass
    try:
        q = t.quarterly_income_stmt
        rev = q.loc["Total Revenue"].dropna() / 1e6
        if len(rev):
            newest = rev.index[0]
            line = f"最新季({str(newest)[:10]})營收 {rev.iloc[0]:,.0f} 百萬美元"
            if len(rev) >= 5 and rev.iloc[4]:
                line += f",YoY {(rev.iloc[0]/rev.iloc[4]-1)*100:+.1f}%"
            parts.append(line)
            if "Gross Profit" in q.index:
                gp = q.loc["Gross Profit"].dropna() / 1e6
                if len(gp) and rev.iloc[0]:
                    parts.append(f"毛利率 {gp.iloc[0]/rev.iloc[0]*100:.1f}%")
    except Exception:
        pass
    return "、".join(parts) if len(parts) > 1 else f"{tkr}(抓取失敗)"


def us_digest(gname: str) -> str:
    """族群的美股同業文字數據包;無對應族群回空字串。"""
    tickers = US_PEERS.get(gname)
    if not tickers:
        return ""
    cache = FUND_DIR / f"us_{gname}.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < CACHE_HOURS * 3600:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    lines = [_one(t) for t in tickers]
    ok = [ln for ln in lines if "抓取失敗" not in ln]
    if not ok and cache.exists():          # 全滅 → 舊快取
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    out = "\n".join(f"- {ln}" for ln in lines)
    if ok:
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out

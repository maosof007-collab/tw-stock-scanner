"""
us_events.py — 美股重要事件行事曆(晨報提醒用)
=================================================================
① FOMC 決議日:Fed 公布的 2026 官方時程(寫死,一年八次)
② CPI 發布日:BLS 2026 預定時程(寫死;偶有異動,標「預定」)
③ 非農 NFP:規則=每月第一個週五
④ 重點美股財報日:yfinance 動態抓(NVDA/台股供應鏈對照組),20h 快取
時間換算:美東盤前數據 08:30 ET ≈ 台灣 20:30(夏令)/21:30(冬令);
FOMC 聲明 14:00 ET ≈ 台灣隔日凌晨 02:00(夏令)。
"""
from __future__ import annotations
import json
import time
from datetime import date, timedelta
from pathlib import Path

FUND_DIR = Path(__file__).parent / "data" / "fundamentals"
FUND_DIR.mkdir(parents=True, exist_ok=True)

# Fed 官方 2026 FOMC 時程(決議日=第二天,美東)
FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
             "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]

# BLS 2026 CPI 發布預定日(美東 08:30)
CPI_2026 = ["2026-01-13", "2026-02-11", "2026-03-11", "2026-04-10",
            "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
            "2026-09-10", "2026-10-13", "2026-11-12", "2026-12-10"]

# 財報觀察名單:美股權值+台股供應鏈對照(CPO/封測/記憶體/AI伺服器)
EARNINGS_WATCH = ["NVDA", "AAPL", "MSFT", "AMD", "AVGO", "MU", "TSM",
                  "LITE", "COHR", "AAOI", "AXTI", "CRDO", "FN", "AMKR", "SMCI", "DELL"]


def _dst(d: date) -> bool:
    """美國夏令時間粗判(3月第二個週日~11月第一個週日)。"""
    return date(d.year, 3, 8) <= d <= date(d.year, 11, 7)


def _first_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def upcoming_macro(today: date, days: int = 8) -> list[str]:
    """未來 N 天內的美國總經事件提醒(台灣時間口徑)。"""
    notes = []
    horizon = today + timedelta(days=days)

    def _tw_time(d: date) -> str:
        return "20:30" if _dst(d) else "21:30"

    for s in CPI_2026:
        d = date.fromisoformat(s)
        if today <= d <= horizon:
            tag = "今晚" if d == today else f"{d:%m/%d}"
            notes.append(f"🇺🇸 {tag} 美國 CPI(台灣時間 {_tw_time(d)},BLS預定)——"
                         f"通膨數據直接牽動降息預期,今晚美股波動會反映在明日台股開盤")
    for s in FOMC_2026:
        d = date.fromisoformat(s)
        if today <= d <= horizon:
            dd = (d - today).days
            when = "今晚(台灣時間隔日凌晨2:00聲明)" if dd == 0 else f"{d:%m/%d}(倒數{dd}天)"
            notes.append(f"🇺🇸 FOMC 利率決議 {when}——決議前市場常縮手觀望,決議後開盤跳空機率高")
    nfp = _first_friday(today.year, today.month)
    if nfp < today:
        nm = today.month % 12 + 1
        nfp = _first_friday(today.year + (1 if nm == 1 else 0), nm)
    if today <= nfp <= horizon:
        tag = "今晚" if nfp == today else f"{nfp:%m/%d}"
        notes.append(f"🇺🇸 {tag} 美國非農就業(台灣時間 {_tw_time(nfp)})——勞動市場強弱牽動利率路徑")
    return notes


def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    d = date(y, m, 1)
    off = (weekday - d.weekday()) % 7
    return d + timedelta(days=off + 7 * (n - 1))


def expo_events(today: date, days: int = 14) -> list[str]:
    """台股題材展覽(近似日期,以官網為準)。附五年事件回測結論提醒。"""
    y = today.year
    expos = []
    for yy in (y, y + 1):
        expos += [
            (_nth_weekday(yy, 8, 2, 3), "台北自動化展(含機器人展)",
             "機器人族群五年回測:展前並無拉升(超額-3.2%),行情集中展期(+1.2%),"
             "**展後5-20日利多出盡平均-3.4%(2025年-10.4%)**——持有者留意展後減碼窗"),
            (_nth_weekday(yy, 9, 2, 2), "SEMICON Taiwan 半導體展",
             "半導體設備/材料題材曝光週"),
            (_nth_weekday(yy, 6, 1, 1), "COMPUTEX 台北電腦展",
             "AI伺服器/PC供應鏈題材曝光週"),
            (date(yy, 1, 6), "CES 消費電子展",
             "年度AI/消費電子題材定調"),
        ]
    notes = []
    horizon = today + timedelta(days=days)
    for d, name, hint in sorted(expos):
        if today <= d <= horizon:
            tag = "今天開展" if d == today else f"{d:%m/%d}(約{(d-today).days}天後)"
            notes.append(f"🎪 {tag} {name}(日期為慣例推估,以官網為準)——{hint}")
    return notes


def upcoming_earnings(today: date, days: int = 10) -> list[str]:
    """觀察名單未來 N 天的財報日(yfinance,20h 快取,失敗退舊快取)。"""
    cache = FUND_DIR / "us_earnings_dates.json"
    data = {}
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 20 * 3600:
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not data:
        try:
            import yfinance as yf
            for t in EARNINGS_WATCH:
                try:
                    cal = yf.Ticker(t).calendar
                    ds = cal.get("Earnings Date") if isinstance(cal, dict) else None
                    if ds:
                        data[t] = [str(x) for x in ds][:2]
                except Exception:
                    continue
            if data:
                cache.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass
        if not data and cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
            except Exception:
                data = {}
    notes = []
    horizon = today + timedelta(days=days)
    for t, ds in sorted(data.items()):
        for s in ds:
            try:
                d = date.fromisoformat(s[:10])
            except Exception:
                continue
            if today <= d <= horizon:
                notes.append(f"🇺🇸 {d:%m/%d} {t} 財報——台股對應供應鏈隔日常有連動")
                break
    return notes

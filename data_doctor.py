# -*- coding: utf-8 -*-
"""
data_doctor.py — 資料新鮮度看門狗:到點沒更新就自己補抓、補不回來就喊人
=================================================================
起因(2026-11-12 使用者:「檢查一下更新吧,出現很多次了」)。四次同型事故:
  10/27-28 管線中途陣亡、11/6 榜單卡前日、11/9 舊價搶跑、11/12 融資卡 11-11。
共同根因:排程單一觸發器+IgnoreNew,長任務一卡後面時段全跳過;
出錯時沒人喊,都是使用者看到舊畫面才發現。
本腳本每個排程時段跑(daily_task.bat 裡 notify_push 之前):
  每條資料線有「該到的時間」;到點還沒到 → 跑對應抓取器補救 → 再驗 →
  補不回來的才推播告警(一天一次,不重複吵)。全程寫 data/_doctor_log.csv。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

import ssl_trust
ssl_trust.ensure()                      # AVG TLS:子行程抓取器也會繼承

from twtime import now_tw
from check_data_current import latest_expected_trading_day

ROOT = Path(__file__).parent
D = ROOT / "data"
LOG = D / "_doctor_log.csv"
ALERTED = D / "_doctor_alerted.json"
PY = sys.executable


def _csv_last_date(p: Path, col: str = "date") -> str:
    try:
        df = pd.read_csv(p, usecols=[col])
        return str(df[col].max())[:10]
    except Exception:
        return ""


def _fix_market_margin() -> None:
    import macro
    macro.build_market_margin_series()   # 自癒:源比快取新就重建


def _fix_margin_log() -> None:
    """斷頭雷達的衍生日誌:源(data/margin)已新但夜間掃描被卡時,補掃+補寫。"""
    import margin_alert as ma
    ma._log_append(ma.scan())


def _fix_warrants() -> None:
    import warrant_flow as wf
    ymd = f"{latest_expected_trading_day():%Y%m%d}"
    if wf.fetch_warrant_day(ymd) is not None:
        wf.whale_today(); wf.board_log()


def _fix_revenue() -> None:
    """月營收兩個衍生快取:revenue_trend.csv(產業輪動/族群儀表板)+ _rev_history.csv(戰情室/籌碼地圖)。"""
    import revenue_radar as rr
    rr.rebuild_if_stale()
    import monthly_forecast as mf
    mf.build_rev_history(force=True)


def _probe_revenue(exp_s: str) -> str:
    try:
        import revenue_radar as rr
        want = rr.expected_latest_ym()
        hist = str(pd.read_csv(D / "_rev_history.csv", usecols=["ym"])["ym"].max())
        return exp_s if (rr.latest_ym_in_file() >= want and hist >= want) else ""
    except Exception:
        return ""


def _probe_recovery(exp_s: str) -> str:
    """無進行中大跌週期時本來就不產出,視為新鮮。"""
    try:
        import recovery_rate as rc
        if rc._detect_cycle() is None:
            return exp_s
    except Exception:
        return exp_s
    return _csv_last_date(D / "recovery_rate.csv", "asof")


def _fresh_within(p: Path, days: float, exp_s: str) -> str:
    import time
    return exp_s if p.exists() and time.time() - p.stat().st_mtime < days * 86400 else ""


def _call(mod: str, fn: str, *a):
    """延遲 import 的 fixer 工廠(避免 doctor 啟動就載入全部模組)。"""
    def run_():
        import importlib
        getattr(importlib.import_module(mod), fn)(*a)
    return run_


# (名稱, 到點時刻HHMM, probe()->本地最新日 'YYYY-MM-DD' 或 ''=無, fixer[, quiet])
# fixer: list=子行程腳本;callable=行程內函式。到點且 probe < 應到日才動手。
# quiet=True:來源本來就晚更新(期交所 OpenAPI 晚間/隔日才換日)→ 照樣補抓,但補不回來不告警。
def _rules():
    exp = latest_expected_trading_day()
    exp_s = f"{exp:%Y-%m-%d}"
    return exp_s, [
        ("月營收快取", 0, lambda: _probe_revenue(exp_s), _fix_revenue),
        ("失土收復率", 1600, lambda: _probe_recovery(exp_s), _call("recovery_rate", "compute")),
        ("期貨法人", 1700, lambda: _csv_last_date(D / "_taifex_fi.csv"),
         _call("taifex_flow", "fetch_fi_futures"), True),
        ("選擇權日檔", 1700,
         lambda: exp_s if (D / "txo" / f"txo_{exp:%Y%m%d}.csv").exists() else "",
         _call("op_paper", "fetch_txo"), True),
        ("多空雷達", 1800, lambda: _csv_last_date(D / "_dual_radar_stocks.csv"),
         _call("dual_radar", "compute")),
        ("投降日回溯", 2200, lambda: _fresh_within(D / "_margin_capit_hist.csv", 4, exp_s),
         _call("margin_alert", "backfill")),
        ("個股價格", 1540,
         lambda: _csv_last_date(D / "2330.TW.csv", "Date"),
         [PY, "fetch_daily_official.py"]),
        ("台指tick囤檔", 1530,
         lambda: exp_s if (D / "taifex_raw" / f"Daily_{exp:%Y_%m_%d}.zip").exists() else "",
         [PY, "fetch_taifex_ticks.py"]),
        ("注意力榜", 1630,
         lambda: exp_s if (D / "attention" / f"att_{exp:%Y%m%d}.html").exists() else "",
         [PY, "refresh_attention.py"]),
        ("法人買賣超", 1740,
         lambda: _csv_last_date(D / "institutional" / "2330_inst.csv"),
         [PY, "fetch_institutional.py", "--mode", "update"]),
        ("權證資金流", 1900,
         lambda: exp_s if (D / "warrants" / f"wflow_{exp:%Y%m%d}.csv").exists() else "",
         _fix_warrants),
        ("融資融券", 2140,
         lambda: _csv_last_date(D / "margin" / "2330_margin.csv"),
         [PY, "fetch_margin.py", "--mode", "update"]),
        ("大盤融資快取", 2150,
         lambda: _csv_last_date(D / "_market_margin.csv"),
         _fix_market_margin),
        ("斷頭雷達日誌", 2155,
         lambda: _csv_last_date(D / "_margin_alert_log.csv", "日期"),
         _fix_margin_log),
    ]


def _append_log(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(LOG, mode="a", header=not LOG.exists(), index=False, encoding="utf-8-sig")


def run() -> str:
    t = now_tw()
    hhmm = t.hour * 100 + t.minute
    exp_s, rules = _rules()
    fixed, broken, rows = [], [], []
    for name, due, probe, fixer, *opt in rules:
        quiet = bool(opt and opt[0])
        if hhmm < due:
            continue
        if probe() >= exp_s:
            continue                                   # 新鮮,不動
        try:                                           # 到點還沒到 → 補救
            if callable(fixer):
                fixer()
            else:
                subprocess.run(fixer, cwd=ROOT, timeout=900,
                               capture_output=True)
        except Exception:
            pass
        ok = probe() >= exp_s
        if ok:
            fixed.append(name)
        elif not quiet:
            broken.append(name)
        rows.append({"時間": f"{t:%Y-%m-%d %H:%M}", "項目": name,
                     "結果": "自動補回 ✅" if ok else ("來源未更新(晚點再試)" if quiet else "補不回來 🔴"),
                     "應到日": exp_s})
        print(f"[doctor] {name}:{'補回' if ok else ('來源未更新' if quiet else '仍缺')}(應到 {exp_s})")
    if rows:
        _append_log(rows)
    # 告警:補不回來的才推,一天同項目只吵一次
    if broken:
        try:
            st = json.loads(ALERTED.read_text(encoding="utf-8"))
        except Exception:
            st = {}
        today_s = f"{t:%Y-%m-%d}"
        if st.get("date") != today_s:
            st = {"date": today_s, "rules": []}
        new = [b for b in broken if b not in st["rules"]]
        if new:
            import line_push
            if line_push.enabled():
                line_push.push_text(f"🩺 資料看門狗 {t:%m/%d %H:%M}\n"
                                    f"補不回來:{'、'.join(new)}(應到 {exp_s})\n"
                                    "來源可能延遲或網路異常——晚一點的時段會再試;"
                                    "連兩個時段都紅就要手動看 logs/daily_task.log")
            st["rules"] += new
            ALERTED.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    if not fixed and not broken:
        return "全部新鮮,無事"
    return f"補回 {len(fixed)} 項" + (f";仍缺 {len(broken)}:{'、'.join(broken)}" if broken else "")


if __name__ == "__main__":
    print("[doctor]", run())

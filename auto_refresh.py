"""
auto_refresh.py — App 內建自動更新（網站開著就一直更新，不用跑 PowerShell）

由 ui_theme.inject_css() 在任何頁面載入時啟動（每個 Streamlit 行程只啟動一條）：
  · 交易日盤中（09:00–13:45）：每 5 分鐘更新「持倉股票」股價（檔數少，幾秒完成）
  · 交易日收盤後（>=14:30）：自動觸發「全市場更新 + 掃描」背景子行程，一天一次
    （進度可在「⏱️ 更新進度」頁觀看；以 data/_last_full_update.txt 防止重複觸發）
"""
import sys, time, threading, subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

ROOT   = Path(__file__).parent
MARKER = ROOT / "data" / "_last_full_update.txt"
UPDLOG = ROOT / "data" / "_auto_update.log"

_THREAD_NAME = "tw-auto-refresh"


# ────────────────────────────────────────
def _held_tickers() -> list[str]:
    """所有使用者的持倉股票（去重）"""
    try:
        from portfolio import all_users, load_portfolio
        tks = set()
        for u in all_users():
            df = load_portfolio(u)
            if not df.empty:
                act = df[df["status"] != "已出場"]["ticker"].astype(str).str.strip()
                tks.update(act.tolist())
        return list(tks)
    except Exception:
        return []


def update_held_now(progress_cb=None) -> list[str]:
    """
    同步更新所有持倉股價（給頁面按鈕用）。回傳失敗清單。
    progress_cb(i, total, ticker)：每檔更新前回呼，供 UI 畫進度條。
    """
    from updater import update_one
    fails = []
    tks = _held_tickers()
    for i, tk in enumerate(tks, 1):
        if progress_cb:
            try:
                progress_cb(i, len(tks), tk)
            except Exception:
                pass
        try:
            r = update_one(tk, ROOT / "data" / f"{tk}.csv")
            if r.get("status") == "ERROR":
                fails.append(tk)
        except Exception:
            fails.append(tk)
    return fails


def _full_done_today() -> bool:
    try:
        return MARKER.read_text(encoding="utf-8").strip() == str(date.today())
    except Exception:
        return False


def _mark_full_done():
    try:
        MARKER.write_text(str(date.today()), encoding="utf-8")
    except Exception:
        pass


def _last_trading_close_date() -> date:
    """最近一個『已收盤』的交易日（忽略國定假日，頂多多跑一次無害）"""
    d = datetime.now()
    if d.weekday() < 5 and (d.hour * 60 + d.minute) >= 14 * 60 + 30:
        return d.date()                       # 今天是交易日且已收盤
    dd = d.date() - timedelta(days=1)
    while dd.weekday() >= 5:                   # 往前跳過週末
        dd -= timedelta(days=1)
    return dd


def _last_price_date():
    """權值股 2330 的最新價格日，當作全庫資料新鮮度基準"""
    p = ROOT / "data" / "2330.TW.csv"
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(p)
        dc = next((c for c in df.columns if c.lower() == "date"), df.columns[0])
        return pd.to_datetime(df[dc].iloc[-1]).date()
    except Exception:
        return None


def _data_behind() -> bool:
    """資料是否落後於最近已收盤交易日 → 一開 App 就能自動補，不必守收盤"""
    lpd = _last_price_date()
    return lpd is None or lpd < _last_trading_close_date()


def trigger_full_update():
    """背景觸發全市場更新+掃描（進度頁可看；輸出寫 data/_auto_update.log 便於除錯）"""
    try:
        f = open(UPDLOG, "a", encoding="utf-8", errors="replace")
        f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} 觸發全市場更新+掃描 =====\n")
        f.flush()
    except Exception:
        f = subprocess.DEVNULL
    subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess,sys;"
         "subprocess.run([sys.executable,'updater.py']);"
         "subprocess.run([sys.executable,'scan_signals.py'])"],
        cwd=str(ROOT),
        stdout=f, stderr=subprocess.STDOUT,
    )


# ────────────────────────────────────────
def _loop():
    time.sleep(20)                      # 等 App 完全啟動
    while True:
        try:
            now = datetime.now()
            hm = now.hour * 60 + now.minute
            is_weekday = now.weekday() < 5
            if is_weekday and 9 * 60 <= hm <= 13 * 60 + 45:
                update_held_now()               # 盤中：持倉跟盤（輕量，只跟持倉）
                _auto_stop()                     # 更新後檢查停損自動出場
            elif auto_update_enabled() and _data_behind() and not _full_done_today():
                # 只在「自動更新開啟 且 資料真的落後」才補；今天已有資料 → 不動
                trigger_full_update()
                _mark_full_done()
                _auto_stop()
        except Exception:
            pass                        # 自動更新絕不能弄掛網站
        time.sleep(300)                 # 每 5 分鐘一輪


def _auto_stop():
    """若開啟自動停損（預設開），所有使用者收盤跌破停損就自動出場並記錄+通知"""
    if not auto_stop_enabled():
        return
    try:
        from portfolio import auto_stop_exit_all
        auto_stop_exit_all()
    except Exception:
        pass


# ── 自動停損開關（存 data/_auto_stop.flag，預設開）──
_FLAG = ROOT / "data" / "_auto_stop.flag"


def auto_stop_enabled() -> bool:
    try:
        return _FLAG.read_text(encoding="utf-8").strip() != "off"
    except Exception:
        return True   # 預設開


def set_auto_stop(on: bool):
    try:
        _FLAG.parent.mkdir(parents=True, exist_ok=True)
        _FLAG.write_text("on" if on else "off", encoding="utf-8")
    except Exception:
        pass


# ── 自動更新開關（存 data/_auto_update.flag，預設開）──
# 關閉後：開 App／資料落後都不自動抓，只有按「更新」才更新（全手動）。
_UPFLAG = ROOT / "data" / "_auto_update.flag"


def auto_update_enabled() -> bool:
    try:
        return _UPFLAG.read_text(encoding="utf-8").strip() != "off"
    except Exception:
        return True   # 預設開（但只在資料落後時才會真的更新）


def set_auto_update(on: bool):
    try:
        _UPFLAG.parent.mkdir(parents=True, exist_ok=True)
        _UPFLAG.write_text("on" if on else "off", encoding="utf-8")
    except Exception:
        pass


def ensure_started():
    """啟動背景自動更新（行程內只會有一條執行緒）"""
    if any(t.name == _THREAD_NAME for t in threading.enumerate()):
        return
    t = threading.Thread(target=_loop, daemon=True, name=_THREAD_NAME)
    t.start()

"""
auto_update.py — 每日自動更新排程
在背景執行，每分鐘檢查一次，台灣收盤後（14:30）自動：
  1. 下載今日股價
  2. 更新外資籌碼
  3. 執行全市場掃描

執行方式（背景常駐）：
  python auto_update.py

或加到 Windows 工作排程器（開機自動啟動）：
  pythonw auto_update.py
"""

import sys, time, subprocess, logging
from pathlib import Path
from datetime import datetime, date

ROOT = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(ROOT / "logs" / "auto_update.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── 設定 ──────────────────────────────────
UPDATE_HOUR   = 14   # 幾點後開始更新（台灣收盤約 13:30，14:00 確保資料齊）
UPDATE_MINUTE = 30
CHECK_INTERVAL = 60  # 每幾秒檢查一次

DONE_FILE = ROOT / "logs" / ".last_update"   # 記錄今日是否已更新


def already_updated_today() -> bool:
    """今天是否已經更新過"""
    if not DONE_FILE.exists():
        return False
    try:
        last = DONE_FILE.read_text().strip()
        return last == date.today().strftime("%Y-%m-%d")
    except:
        return False


def mark_updated():
    DONE_FILE.parent.mkdir(exist_ok=True)
    DONE_FILE.write_text(date.today().strftime("%Y-%m-%d"))


def is_trading_day() -> bool:
    """今天是否是交易日（週一~週五）"""
    return datetime.today().weekday() < 5   # 0=Mon, 4=Fri


def is_after_close() -> bool:
    """現在是否已過收盤更新時間"""
    now = datetime.now()
    return (now.hour > UPDATE_HOUR or
            (now.hour == UPDATE_HOUR and now.minute >= UPDATE_MINUTE))


def run_step(script: str, *args) -> bool:
    """執行一個更新步驟"""
    cmd = [sys.executable, str(ROOT / script)] + list(args)
    log.info(f"執行：{' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=1800,   # 最多等 30 分鐘
        )
        if result.returncode == 0:
            log.info(f"完成：{script}")
            return True
        else:
            log.error(f"失敗：{script}\n{result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        log.error(f"逾時：{script}")
        return False
    except Exception as e:
        log.error(f"例外：{script} → {e}")
        return False


def do_daily_update():
    """執行每日更新流程"""
    log.info("=" * 55)
    log.info("  開始每日自動更新")
    log.info("=" * 55)

    # Step 1：更新股價
    ok1 = run_step("download_all_tw_stocks.py")

    # Step 2：更新外資籌碼（增量）
    ok2 = run_step("fetch_institutional.py", "--mode", "update")

    # Step 3：掃描今日訊號
    ok3 = run_step("scan_signals.py")

    mark_updated()
    log.info(f"完成！股價:{ok1}  籌碼:{ok2}  掃描:{ok3}")


def main():
    log.info("自動更新守護程式已啟動")
    log.info(f"每日 {UPDATE_HOUR:02d}:{UPDATE_MINUTE:02d} 後自動更新（週一至週五）")

    while True:
        try:
            now = datetime.now()
            if (is_trading_day() and
                is_after_close() and
                not already_updated_today()):

                log.info(f"觸發每日更新 [{now.strftime('%Y-%m-%d %H:%M')}]")
                do_daily_update()
            else:
                # 顯示下次更新時間
                if not is_trading_day():
                    status = "週末，等待下一個交易日"
                elif already_updated_today():
                    status = f"今日已更新（{date.today()}）"
                else:
                    mins_left = (UPDATE_HOUR * 60 + UPDATE_MINUTE) - (now.hour * 60 + now.minute)
                    status = f"等待收盤更新，剩約 {mins_left} 分鐘"
                log.debug(status)

        except Exception as e:
            log.error(f"主迴圈例外：{e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    main()

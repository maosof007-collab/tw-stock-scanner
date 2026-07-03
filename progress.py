"""
progress.py — 共用進度回報
管線（updater / scan_signals / fetch_margin）執行時把進度寫到
data/_progress.json，App 的「更新進度」頁每秒讀取顯示進度條。

用法：
    from progress import set_progress, read_progress, clear_progress
    set_progress("股價更新", i, total, ticker)        # 迴圈中
    set_progress("掃描訊號", n, total, done=True)      # 完成
"""
import json, os, time
from pathlib import Path

PROGRESS_FILE = Path("data/_progress.json")


def set_progress(phase: str, current: int, total: int,
                 msg: str = "", done: bool = False):
    """寫入目前進度（原子寫入，避免讀到半個檔）"""
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "phase":   phase,
            "current": int(current),
            "total":   int(total),
            "msg":     str(msg),
            "done":    bool(done),
            "ts":      time.time(),
        }
        tmp = PROGRESS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, PROGRESS_FILE)
    except Exception:
        pass  # 進度回報失敗絕不影響主流程


def read_progress() -> dict | None:
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_progress():
    try:
        PROGRESS_FILE.unlink()
    except Exception:
        pass

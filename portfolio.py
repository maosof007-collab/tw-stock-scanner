"""
portfolio.py — 持倉追蹤共用存取（多使用者版）
每位使用者各自一份 data/portfolio_{使用者}.csv，互不干擾。
今日選股頁（勾選加入）與績效追蹤頁共用同一份（依登入者）。
"""
import glob
import json
from pathlib import Path
from datetime import datetime, date

import pandas as pd

ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "data"

COLUMNS = ["id", "ticker", "name", "entry_date", "entry_price",
           "shares", "stop_loss", "strategy", "note",
           "exit_date", "exit_price", "status"]


def _safe(user: str) -> str:
    return "".join(c for c in str(user) if c.isalnum() or c in "._-") or "default"


def track_file(user: str) -> Path:
    return DATA_DIR / f"portfolio_{_safe(user)}.csv"


def notify_file(user: str) -> Path:
    return DATA_DIR / f"notify_{_safe(user)}.json"


# ════════════════════════════════════════
# 持倉
# ════════════════════════════════════════
def _sheets():
    """雲端有設定 Google 試算表就回傳模組，否則 None（本機用 CSV）。"""
    try:
        import sheets_store
        return sheets_store if sheets_store.enabled() else None
    except Exception:
        return None


def load_portfolio(user: str) -> pd.DataFrame:
    ss = _sheets()
    if ss is not None:
        df = ss.load_portfolio(user, COLUMNS)
        if df is not None:                      # 雲端讀到（含空表）→ 用它
            return _as_object(df)
    p = track_file(user)                        # 本機 / 雲端讀失敗 → CSV
    if not p.exists():
        return pd.DataFrame(columns=COLUMNS)
    return _as_object(pd.read_csv(p, encoding="utf-8-sig"))


def _as_object(df: pd.DataFrame) -> pd.DataFrame:
    """統一成 object 欄位，避免新版 pandas(arrow string)在後續指派數字時報 TypeError。"""
    try:
        return df.astype(object)
    except Exception:
        return df


def save_portfolio(df: pd.DataFrame, user: str):
    ss = _sheets()
    if ss is not None and ss.save_portfolio(df, user):
        return                                  # 存進 Google 試算表成功
    DATA_DIR.mkdir(exist_ok=True)               # 本機 / 雲端寫失敗 → CSV
    df.to_csv(track_file(user), index=False, encoding="utf-8-sig")


def add_position(user: str, ticker: str, name: str = "", entry_price: float = 0.0,
                 stop_loss: float = 0.0, strategy: str = "",
                 shares: int = 1, note: str = "", entry_date: str = "",
                 allow_add: bool = False) -> str:
    """加入一筆持倉到該使用者。回傳 'added' / 'duplicate'。
    allow_add=True → 允許同股再加一筆（第2次進場/加碼，各自一列、各自移動停利）。"""
    ticker = str(ticker).strip().upper()
    df = load_portfolio(user)
    if not df.empty and not allow_add:
        dup = df[(df["ticker"].astype(str).str.upper() == ticker) &
                 (df["status"] == "持倉中")]
        if not dup.empty:
            return "duplicate"
    row = pd.DataFrame([{
        "id": int(datetime.now().timestamp() * 1000), "ticker": ticker, "name": name,
        "entry_date": entry_date or str(date.today()), "entry_price": float(entry_price),
        "shares": int(shares), "stop_loss": float(stop_loss), "strategy": strategy,
        "note": note, "exit_date": "", "exit_price": "", "status": "持倉中",
    }])
    save_portfolio(pd.concat([df, row], ignore_index=True), user)
    return "added"


def add_positions(user: str, rows: list[dict], allow_add: bool = False) -> tuple[list, list]:
    """批次加入多筆持倉:一次讀+一次存。回傳 (added_tickers, dup_tickers)。
    修正:逐筆 add_position 在雲端(Google Sheets)有寫後讀回延遲,
    第二筆會用舊資料覆蓋第一筆 → 勾四檔只存活一兩檔。"""
    df = load_portfolio(user)
    held = set()
    if not df.empty:
        held = set(df[df["status"] == "持倉中"]["ticker"].astype(str).str.upper())
    added, dup, new_rows = [], [], []
    base_id = int(datetime.now().timestamp() * 1000)
    for i, r in enumerate(rows):
        tk = str(r.get("ticker", "")).strip().upper()
        if not tk:
            continue
        if tk in held and not allow_add:
            dup.append(tk)
            continue
        new_rows.append({
            "id": base_id + i, "ticker": tk, "name": r.get("name", ""),
            "entry_date": r.get("entry_date") or str(date.today()),
            "entry_price": float(r.get("entry_price", 0) or 0),
            "shares": int(r.get("shares", 1) or 1),
            "stop_loss": float(r.get("stop_loss", 0) or 0),
            "strategy": r.get("strategy", ""), "note": r.get("note", ""),
            "exit_date": "", "exit_price": "", "status": "持倉中",
        })
        held.add(tk)
        added.append(tk)
    if new_rows:
        save_portfolio(pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True), user)
    return added, dup


def all_users() -> list[str]:
    """有持倉的所有使用者（給背景守護掃描）"""
    ss = _sheets()
    if ss is not None:
        us = ss.all_users()
        if us:
            return us
    out = []
    for f in glob.glob(str(DATA_DIR / "portfolio_*.csv")):
        out.append(Path(f).stem.replace("portfolio_", "", 1))
    return out


# ════════════════════════════════════════
# 每人通知設定（Email）
# ════════════════════════════════════════
_NOTIFY_DEFAULT = {"email": {"enabled": False, "smtp": "smtp.gmail.com", "port": 587,
                             "user": "", "password": "", "to": ""}}


def load_notify(user: str) -> dict:
    ss = _sheets()
    if ss is not None:
        cfg = ss.load_notify(user)
        if cfg is not None:
            return cfg or _NOTIFY_DEFAULT
    p = notify_file(user)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(_NOTIFY_DEFAULT)


def save_notify(user: str, cfg: dict):
    ss = _sheets()
    if ss is not None and ss.save_notify(user, cfg):
        return
    DATA_DIR.mkdir(exist_ok=True)
    notify_file(user).write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


# ════════════════════════════════════════
# 自動停損出場（可指定使用者，或全部使用者）
# ════════════════════════════════════════
def _latest_close(ticker: str):
    code = str(ticker).replace(".TWO", "").replace(".TW", "").strip()
    for suf in (".TW", ".TWO"):
        p = DATA_DIR / f"{code}{suf}.csv"
        if p.exists():
            try:
                d = pd.read_csv(p, usecols=[4])
                s = pd.to_numeric(d.iloc[:, 0], errors="coerce").dropna()
                return float(s.iloc[-1]) if len(s) else None
            except Exception:
                pass
    return None


def auto_stop_exit(user: str, price_fn=None, notify: bool = True) -> list[dict]:
    """單一使用者：持倉收盤 <= 停損 → 記錄出場並移除。回傳出場明細。"""
    df = load_portfolio(user)
    if df.empty:
        return []
    today = str(date.today())
    exited = []
    for i, r in df[df["status"] == "持倉中"].iterrows():
        sl_init = float(r.get("stop_loss") or 0)
        tk = str(r["ticker"]).strip()
        ent = float(r.get("entry_price") or 0)
        # 移動停利：以進場/初始停損回放到最新K，得動態停損（保本→鎖利）；打到才出場
        try:
            import trailing
            sl = float(trailing.trailing_stop(tk, ent, r.get("entry_date", ""),
                                              sl_init)["stop"])
        except Exception:
            sl = sl_init
        if sl <= 0:
            continue
        cp = price_fn(tk) if price_fn else _latest_close(tk)
        if cp and cp <= sl:
            df.loc[i, "exit_date"]  = today
            df.loc[i, "exit_price"] = round(float(cp), 2)
            df.loc[i, "status"]     = "已出場"
            note = str(df.loc[i, "note"] or "")
            df.loc[i, "note"] = (note + " ｜移動停利出場").strip("｜ ")
            exited.append({"ticker": tk, "name": str(r.get("name", "") or ""),
                           "exit_price": round(float(cp), 2), "stop_loss": round(sl, 2),
                           "pnl_pct": round((cp - ent) / ent * 100, 2) if ent else None})
    if exited:
        save_portfolio(df, user)
        if notify:
            try:
                from notifier import notify_stop_exit
                notify_stop_exit(exited, load_notify(user))
            except Exception:
                pass
    return exited


def auto_stop_exit_all() -> dict:
    """所有使用者跑一次自動停損（給背景守護）。回傳 {user: [出場明細]}"""
    result = {}
    for u in all_users():
        ex = auto_stop_exit(u)
        if ex:
            result[u] = ex
    return result

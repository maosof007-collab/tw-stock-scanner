"""
notifier.py
推播通知模組 — 支援 Line Notify / Email
當偵測到買入訊號時，自動發送通知

Line Notify 設定步驟：
  1. 前往 https://notify-bot.line.me/
  2. 登入 → 個人頁面 → 發行存取權杖
  3. 複製 Token，填入下方 LINE_TOKEN
  4. 開啟 Line，加入「LINE Notify」好友
"""

import smtplib, requests, json, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

# ════════════════════════════════════════
# 設定檔（存在 config.json，不寫死在程式碼）
# ════════════════════════════════════════
CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "line": {
        "enabled": False,
        "token":   ""          # 舊版 Line Notify（已停用，保留相容）
    },
    "line_messaging": {        # ★ 現行可用：LINE Messaging API（官方帳號）
        "enabled": False,
        "channel_access_token": "",  # LINE Developers → Messaging API → Channel access token
        "to_id":   ""                # 你的 userId 或 群組 groupId（推播目標）
    },
    "email": {
        "enabled":  False,
        "smtp":     "smtp.gmail.com",
        "port":     587,
        "user":     "",        # Gmail 帳號
        "password": "",        # Gmail 應用程式密碼
        "to":       ""         # 收件人
    }
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # 第一次執行：建立預設設定檔
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════
# Line Notify
# ════════════════════════════════════════
def send_line(token: str, message: str) -> bool:
    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("Line Notify 發送成功")
            return True
        else:
            log.warning(f"Line Notify 失敗: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        log.error(f"Line Notify 例外: {e}")
        return False


# ════════════════════════════════════════
# LINE Messaging API（現行可用：推播 push）
# ════════════════════════════════════════
def send_line_push(channel_access_token: str, to_id: str, message: str) -> bool:
    try:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {channel_access_token}",
                     "Content-Type": "application/json"},
            json={"to": to_id, "messages": [{"type": "text", "text": message}]},
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("LINE Messaging push 發送成功")
            return True
        log.warning(f"LINE push 失敗: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        log.error(f"LINE push 例外: {e}")
        return False


def _push_line(cfg: dict, message: str) -> bool:
    """依設定推播：優先用 Messaging API，相容舊 Notify。"""
    lm = cfg.get("line_messaging", {})
    if lm.get("enabled") and lm.get("channel_access_token") and lm.get("to_id"):
        return send_line_push(lm["channel_access_token"], lm["to_id"], message)
    ln = cfg.get("line", {})
    if ln.get("enabled") and ln.get("token"):
        return send_line(ln["token"], message)
    return False


# ════════════════════════════════════════
# 自動停損出場通知
# ════════════════════════════════════════
def notify_stop_exit(rows: list[dict], cfg: dict = None) -> bool:
    """
    rows: [{ticker, name, exit_price, stop_loss, pnl_pct}, ...]
    cfg : 通知設定（多使用者版傳入該使用者的設定）；None 則用全域 config.json。
    觸發自動停損出場時推播 LINE / Email。
    """
    if not rows:
        return False
    if cfg is None:
        cfg = load_config()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"🛑 自動停損出場 {now}", "─" * 18]
    for r in rows:
        pnl = r.get("pnl_pct")
        pnl_s = f"  損益 {pnl:+.1f}%" if pnl is not None else ""
        lines.append(
            f"▶ {r.get('ticker','')} {r.get('name','')}"
            f"\n  出場 {r.get('exit_price',0):.1f}（跌破停損 {r.get('stop_loss',0):.1f}）{pnl_s}"
        )
    lines.append("─" * 18)
    lines.append("已記錄到出場紀錄")
    msg = "\n".join(lines)

    sent = False
    # LINE（若有設定）
    if _push_line(cfg, msg):
        sent = True
    # Email（若有設定）
    em = cfg.get("email", {})
    if em.get("enabled") and em.get("user") and em.get("to"):
        subject = f"🛑 自動停損出場（{len(rows)} 檔）{now}"
        if send_email(em, subject, msg):
            sent = True
    return sent


# ════════════════════════════════════════
# Email
# ════════════════════════════════════════
def send_email(cfg: dict, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"]    = cfg["user"]
        msg["To"]      = cfg["to"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(cfg["smtp"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)

        log.info(f"Email 發送成功 → {cfg['to']}")
        return True
    except Exception as e:
        log.error(f"Email 發送失敗: {e}")
        return False


# ════════════════════════════════════════
# 主要發送函數
# ════════════════════════════════════════
def notify_signals(signals: list[dict], strategy_name: str = ""):
    """
    signals: 買入訊號列表，每項為 dict：
        { ticker, close, stop_loss, state, rs, strategy }
    """
    if not signals:
        return

    cfg = load_config()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 組成訊息 ─────────────────────────
    lines = [
        f"📈 台股買入訊號 {now}",
        f"策略：{strategy_name}" if strategy_name else "",
        "─" * 20,
    ]
    for s in signals:
        ticker    = s.get("ticker", "")
        close     = s.get("close", 0)
        stop_loss = s.get("stop_loss", 0)
        state     = s.get("state", "")
        risk_pct  = abs((close - stop_loss) / close * 100) if close and stop_loss else 0
        lines.append(
            f"▶ {ticker}  收盤 {close:.1f}"
            f"\n  停損 {stop_loss:.1f}  風險 {risk_pct:.1f}%"
            f"\n  狀態: {state}"
        )
    lines.append("─" * 20)
    lines.append("⚠️ 僅供參考，請自行判斷風險")

    message = "\n".join(l for l in lines if l)

    # ── Line Notify ──────────────────────
    if cfg["line"]["enabled"] and cfg["line"]["token"]:
        send_line(cfg["line"]["token"], "\n" + message)
    elif cfg["line"]["enabled"]:
        log.warning("Line Notify 已啟用但 Token 未設定")

    # ── Email ─────────────────────────────
    if cfg["email"]["enabled"] and cfg["email"]["user"]:
        subject = f"台股買入訊號 {now}（{len(signals)} 檔）"
        send_email(cfg["email"], subject, message)
    elif cfg["email"]["enabled"]:
        log.warning("Email 已啟用但帳號未設定")

    return message


def notify_update_done(ok: int, err: int):
    """資料更新完成通知"""
    cfg = load_config()
    if not cfg["line"]["enabled"] and not cfg["email"]["enabled"]:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"\n✅ 台股資料更新完成 {now}\n成功 {ok} 檔  失敗 {err} 檔"
    if cfg["line"]["enabled"] and cfg["line"]["token"]:
        send_line(cfg["line"]["token"], msg)


# ════════════════════════════════════════
# 測試用
# ════════════════════════════════════════
if __name__ == "__main__":
    print("=== 通知測試 ===")
    cfg = load_config()
    print(f"設定檔：{CONFIG_PATH}")
    print(f"Line: {'已啟用' if cfg['line']['enabled'] else '未啟用'}")
    print(f"Email: {'已啟用' if cfg['email']['enabled'] else '未啟用'}")

    test_signals = [
        {"ticker": "2330.TW", "close": 950.0, "stop_loss": 912.0,
         "state": "A+B+C全部成立", "rs": 1.24},
        {"ticker": "2382.TW", "close": 265.0, "stop_loss": 248.0,
         "state": "A+B+C全部成立", "rs": 1.18},
    ]
    msg = notify_signals(test_signals, strategy_name="A+B+C 籌碼趨勢")
    print("\n測試訊息預覽：")
    print(msg)

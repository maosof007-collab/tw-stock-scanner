# -*- coding: utf-8 -*-
"""
tg_push.py — Telegram Bot 推播(取代 LINE,免費無月額度上限)
=================================================================
一次性設定(約 3 分鐘):
  1. Telegram 搜 @BotFather → /newbot → 取名 → 拿到 bot token
  2. config.json(已在 .gitignore)加:
       "telegram_bot_token": "123456:ABC-xxxx"
  3. 在 Telegram 跟你的 bot 說一句話(隨便傳個「hi」)
  4. 跑 `python tg_push.py setup` → 自動抓 chat_id 寫回 config.json
  5. 跑 `python tg_push.py test` → 手機收到測試訊息即完成

訊息上限 4096 字/則;無月額度限制(API 速率 ~30 則/秒,遠超需求)。
line_push.py 的 push_text/push_markdown/push_flex 會自動轉發到這裡。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CFG = ROOT / "config.json"


def _cfg() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def enabled() -> bool:
    c = _cfg()
    return bool(c.get("telegram_bot_token") and c.get("telegram_chat_id"))


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{_cfg().get('telegram_bot_token','')}/{method}"


def push_text(text: str) -> str:
    """推一則純文字。回傳結果說明(不丟例外,呼叫端 best-effort)。"""
    c = _cfg()
    if not c.get("telegram_bot_token"):
        return "未設定 telegram_bot_token(config.json),略過"
    if not c.get("telegram_chat_id"):
        return "未設定 telegram_chat_id(先跑 python tg_push.py setup),略過"
    try:
        r = requests.post(_api("sendMessage"), timeout=20, json={
            "chat_id": c["telegram_chat_id"],
            "text": text[:4096],
            "disable_web_page_preview": True,
        })
        if r.status_code == 200:
            return "Telegram 推播成功 ✅"
        return f"Telegram 推播失敗 {r.status_code}:{r.text[:120]}"
    except Exception as e:
        return f"Telegram 推播例外:{type(e).__name__}"


def flex_to_text(alt_text: str, contents: dict) -> str:
    """LINE Flex JSON → 純文字:遞迴收集 text 節點,保留大致行序。"""
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and node.get("text"):
                t = str(node["text"]).strip()
                if t:
                    big = str(node.get("size", "")) in ("lg", "xl", "xxl") or node.get("weight") == "bold"
                    out.append(f"▍{t}" if big else t)
            for k in ("header", "hero", "body", "footer", "contents"):
                if k in node:
                    walk(node[k])
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(contents)
    seen, lines = set(), []
    for t in out:
        if t not in seen or len(t) <= 2:
            lines.append(t)
            seen.add(t)
    body = "\n".join(lines)
    return (alt_text + "\n" + body) if alt_text and alt_text not in body else body


def push_flex(alt_text: str, contents: dict) -> str:
    return push_text(flex_to_text(alt_text, contents))


def setup() -> None:
    """抓 chat_id 寫回 config.json(先跟 bot 說過話才抓得到)。"""
    c = _cfg()
    if not c.get("telegram_bot_token"):
        print("先把 telegram_bot_token 填進 config.json(找 @BotFather /newbot)")
        return
    r = requests.get(_api("getUpdates"), timeout=20)
    ups = r.json().get("result", [])
    cands = {}
    for u in ups:
        msg = u.get("message") or u.get("channel_post") or {}
        ch = msg.get("chat", {})
        if ch.get("id"):
            who = ch.get("title") or ch.get("username") or ch.get("first_name") or "?"
            cands[ch["id"]] = f'{who}({ch.get("type")})'
    if not cands:
        print("抓不到 chat:先在 Telegram 跟 bot 說一句話(或把 bot 拉進群組發言)再跑一次")
        return
    cid = list(cands)[-1]
    print("找到 chat:", {k: v for k, v in cands.items()}, "→ 使用", cid, cands[cid])
    c["telegram_chat_id"] = cid
    CFG.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已寫入 config.json → 跑 python tg_push.py test 驗證")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        setup()
    elif cmd == "test":
        print(push_text("📡 tw_backtest → Telegram 通道測試成功。LINE 已退役,本頻道無月額度上限。"))
    else:
        print("用法:python tg_push.py setup|test")

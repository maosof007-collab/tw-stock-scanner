"""
line_push.py — 把晨報/日誌推到 LINE 群組(Messaging API)
=================================================================
前置(一次性,見使用說明):
  1. https://developers.line.biz → 建 Provider → 建 Messaging API channel
  2. 取得 Channel access token(long-lived)
  3. 把機器人帳號拉進目標群組(官方帳號設定裡開「允許加入群組」)
  4. 取得群組 ID(把 webhook 暫時指向 https://webhook.site 產生的網址,
     在群組發一句話,webhook payload 裡的 source.groupId 就是;取完可關 webhook)
  5. 寫進 config.json(已在 .gitignore,金鑰不會進 git):
     {"line_channel_token": "xxx", "line_group_id": "Cxxxx..."}
     沒填 group_id 則改用 broadcast(推給所有加官方帳號好友的人)。

免費方案每月 200 則推播;推群組一則算一則(不論群內人數)。
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).parent
API_PUSH = "https://api.line.me/v2/bot/message/push"
API_BROADCAST = "https://api.line.me/v2/bot/message/broadcast"


def _cfg() -> dict:
    try:
        return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def enabled() -> bool:
    return bool(_cfg().get("line_channel_token"))


def _md_to_plain(md: str, max_len: int = 3800) -> str:
    """markdown → LINE 純文字:去記號、去表格框線、砍連結區。"""
    txt = md.split("## 📎")[0]                           # 新聞連結區太長,群組不推
    txt = re.sub(r"^#{1,3}\s*", "▍", txt, flags=re.M)    # 標題 → ▍
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
    txt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", txt)   # [文字](url) → 文字
    txt = re.sub(r"^\|[-| ]+\|$", "", txt, flags=re.M)   # 表格分隔線
    txt = txt.replace("|", " ")
    txt = re.sub(r"^>\s*", "", txt, flags=re.M)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    if len(txt) > max_len:
        txt = txt[:max_len] + "\n…(完整版見 App)"
    return txt


def push_text(text: str) -> str:
    """推一則文字。回傳結果說明(不丟例外,呼叫端 best-effort)。"""
    cfg = _cfg()
    token = cfg.get("line_channel_token")
    if not token:
        return "未設定 line_channel_token(config.json),略過"
    gid = cfg.get("line_group_id")
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    body = {"messages": [{"type": "text", "text": text[:4900]}]}
    try:
        if gid:
            body["to"] = gid
            r = requests.post(API_PUSH, headers=headers, json=body, timeout=20)
        else:
            r = requests.post(API_BROADCAST, headers=headers, json=body, timeout=20)
        if r.status_code == 200:
            return "LINE 推播成功 ✅"
        return f"LINE 推播失敗 {r.status_code}:{r.text[:120]}"
    except Exception as e:
        return f"LINE 推播例外:{type(e).__name__}"


def push_markdown(md: str) -> str:
    return push_text(_md_to_plain(md))

"""
apikey.py — Anthropic API Key 統一讀取與檢查
=================================================================
所有要用 Claude 的模組（新聞情緒 analyze_news、日報潤稿 daily_report、
文章解讀 article_intel、法人報告 parse_report）一律經由這裡拿 key，
使用者只要在「任一個」位置放好 key，全系統自動升級：

  ① 環境變數  ANTHROPIC_API_KEY
  ② config.json 裡的 "anthropic_api_key"（本機最簡單：加一行即可）
  ③ .streamlit/secrets.toml 的 ANTHROPIC_API_KEY（雲端用 App secrets）

key_status() 回報在哪找到；test_key() 實際打一次 API 驗證能用。
"""
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent


def get_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    cfg = ROOT / "config.json"
    if cfg.exists():
        try:
            key = json.loads(cfg.read_text(encoding="utf-8")).get("anthropic_api_key", "")
            if key:
                return key
        except Exception:
            pass
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def key_status() -> dict:
    """{found: bool, source: 說明, masked: sk-...xxxx}"""
    if os.environ.get("ANTHROPIC_API_KEY", ""):
        k = os.environ["ANTHROPIC_API_KEY"]
        return {"found": True, "source": "環境變數 ANTHROPIC_API_KEY", "masked": f"sk-...{k[-4:]}"}
    cfg = ROOT / "config.json"
    if cfg.exists():
        try:
            k = json.loads(cfg.read_text(encoding="utf-8")).get("anthropic_api_key", "")
            if k:
                return {"found": True, "source": "config.json", "masked": f"sk-...{k[-4:]}"}
        except Exception:
            pass
    try:
        import streamlit as st
        k = st.secrets.get("ANTHROPIC_API_KEY", "")
        if k:
            return {"found": True, "source": "Streamlit secrets", "masked": f"sk-...{k[-4:]}"}
    except Exception:
        pass
    return {"found": False, "source": "", "masked": ""}


def test_key() -> tuple[bool, str]:
    """實際打一次最小 API 請求。回 (成功?, 訊息)。"""
    key = get_key()
    if not key:
        return False, "找不到 key（環境變數 / config.json / secrets 都沒有）"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=8,
            messages=[{"role": "user", "content": "回覆 OK 兩字即可"}])
        txt = "".join(b.text for b in msg.content if b.type == "text").strip()
        return True, f"連線成功（模型回覆：{txt[:10]}）"
    except anthropic.AuthenticationError:
        return False, "key 無效（AuthenticationError）——請確認貼的是完整的 sk-ant- 開頭金鑰"
    except Exception as e:
        return False, f"連線失敗：{type(e).__name__}: {str(e)[:120]}"

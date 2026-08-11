"""
llm.py — 文字生成統一入口（三層自動降級）
=================================================================
  ① Anthropic API（有 ANTHROPIC_API_KEY 時，最快）
  ② Claude Code CLI 無頭模式（本機已登入 Claude 訂閱即可用，免 API 付款；
     官方 headless：claude -p "..." --output-format text）
  ③ None（呼叫端自行退化為離線版）

用法：
    from llm import generate, engine_status
    out = generate(system_text, user_text)   # None = 兩種引擎都不可用
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
from pathlib import Path

_CLI_CANDIDATES = [
    shutil.which("claude") or "",
    str(Path.home() / ".local" / "bin" / "claude.exe"),
    str(Path.home() / ".local" / "bin" / "claude"),
]


def _cli_path() -> str:
    for p in _CLI_CANDIDATES:
        if p and Path(p).exists():
            return p
    return ""


def _api_generate(system: str, user: str, max_tokens: int) -> str | None:
    from apikey import get_key
    key = get_key()
    if not key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        out = "".join(b.text for b in msg.content if b.type == "text").strip()
        return out or None
    except Exception:
        return None


LAST_ERROR = ""       # 最近一次 generate 失敗原因(給呼叫端顯示,別再只回「無引擎」)


def _cli_generate(system: str, user: str) -> str | None:
    global LAST_ERROR
    exe = _cli_path()
    if not exe:
        LAST_ERROR = "本機沒有 Claude CLI(雲端環境或未安裝)"
        return None
    prompt = f"{system}\n\n=== 以下是要處理的內容 ===\n{user}"
    try:
        r = subprocess.run(
            [exe, "-p", prompt, "--output-format", "text", "--model", "haiku"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        out = (r.stdout or "").strip()
        if "Not logged in" in out or "/login" in out[:80]:
            LAST_ERROR = "Claude CLI 未登入(終端機執行 claude → /login)"
            return None
        if r.returncode != 0 or not out:
            LAST_ERROR = f"Claude CLI 執行失敗(exit {r.returncode}):{(r.stderr or out)[:120]}"
            return None
        LAST_ERROR = ""
        return out
    except subprocess.TimeoutExpired:
        LAST_ERROR = "Claude CLI 逾時(300秒)——內容太長或系統忙,重試一次通常會過"
        return None
    except Exception as e:
        LAST_ERROR = f"Claude CLI 例外:{type(e).__name__}"
        return None


def generate(system: str, user: str, max_tokens: int = 2000) -> str | None:
    """依序嘗試 API → CLI；都不行回 None（呼叫端走離線退化，原因看 fail_reason()）。"""
    global LAST_ERROR
    out = _api_generate(system, user, max_tokens)
    if out:
        LAST_ERROR = ""
        return out
    return _cli_generate(system, user)


def fail_reason() -> str:
    """最近一次生成失敗的白話原因（頁面顯示用）。"""
    return LAST_ERROR or "無 API 金鑰、無可用 Claude CLI（離線模式）"


def generate_json(system: str, user: str, max_tokens: int = 2000) -> str | None:
    """給要求嚴格 JSON 的呼叫端；會剝掉 CLI/模型偶爾包的 ```json 圍欄。"""
    out = generate(system, user, max_tokens)
    if not out:
        return None
    return re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip()


def engine_status() -> dict:
    """{engine: 'api'|'cli'|'none', detail: 說明}（頁面顯示用）"""
    from apikey import get_key
    if get_key():
        return {"engine": "api", "detail": "Anthropic API（金鑰已設定）"}
    exe = _cli_path()
    if exe:
        try:
            r = subprocess.run([exe, "-p", "回覆OK", "--output-format", "text",
                                "--model", "haiku"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=90)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "Not logged in" not in out:
                return {"engine": "cli", "detail": "Claude Code CLI（本機訂閱登入）"}
            return {"engine": "none",
                    "detail": "找到 Claude Code CLI 但未登入——終端機執行 claude 後輸入 /login 即可"}
        except Exception:
            pass
    return {"engine": "none", "detail": "無 API 金鑰、無可用 Claude CLI（離線模式）"}

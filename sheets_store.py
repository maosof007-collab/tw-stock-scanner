"""
sheets_store.py — 雲端持久化到 Google 試算表
=================================================================
問題：Streamlit Cloud 硬碟是暫存的，重開會清空 → 本機檔案存的持倉會不見。
解法：設定好 Google 服務帳號後，持倉/通知改存一份 Google 試算表，重開也留著。

啟用條件（雲端 secrets 設好才啟用；本機沒設 → 不啟用，portfolio 仍用本機 CSV）：
  st.secrets["gcp_service_account"]  # 服務帳號 JSON（整包）
  st.secrets["gsheet_id"]            # 試算表 ID

試算表結構（自動建立）：
  分頁 portfolio：欄位 user + 持倉欄位（所有人的持倉都在這，用 user 欄分）
  分頁 notify   ：欄位 user, config(JSON)
"""
from __future__ import annotations
import json
import pandas as pd

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
           "https://www.googleapis.com/auth/drive"]
_cache: dict = {}

PF_HEADER = ["user", "id", "ticker", "name", "entry_date", "entry_price", "shares",
             "stop_loss", "strategy", "note", "exit_date", "exit_price", "status"]


def enabled() -> bool:
    try:
        import streamlit as st
        return bool(st.secrets.get("gcp_service_account") and st.secrets.get("gsheet_id"))
    except Exception:
        return False


def _spreadsheet():
    if "ss" in _cache:
        return _cache["ss"]
    import streamlit as st
    import gspread
    from google.oauth2.service_account import Credentials
    sa = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa, scopes=_SCOPES)
    ss = gspread.authorize(creds).open_by_key(str(st.secrets["gsheet_id"]))
    _cache["ss"] = ss
    return ss


def _ws(name: str, header: list):
    ss = _spreadsheet()
    try:
        return ss.worksheet(name)
    except Exception:
        ws = ss.add_worksheet(title=name, rows=200, cols=max(4, len(header)))
        ws.update([header])
        return ws


# ── 持倉 ──────────────────────────────────────
def load_portfolio(user: str, columns: list):
    """回傳該 user 的持倉 DataFrame；失敗回 None（讓呼叫端 fallback 本機）。"""
    try:
        ws = _ws("portfolio", PF_HEADER)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=columns)
        df = df[df["user"].astype(str) == str(user)]
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        return df[columns].reset_index(drop=True)
    except Exception:
        return None


def save_portfolio(df: pd.DataFrame, user: str) -> bool:
    try:
        ws = _ws("portfolio", PF_HEADER)
        alldf = pd.DataFrame(ws.get_all_records())
        if not alldf.empty and "user" in alldf.columns:
            alldf = alldf[alldf["user"].astype(str) != str(user)]
        mine = df.copy()
        mine["user"] = str(user)
        for c in PF_HEADER:
            if c not in mine.columns:
                mine[c] = ""
        parts = [d for d in (alldf, mine[PF_HEADER]) if not d.empty]
        out = pd.concat(parts, ignore_index=True) if parts else mine[PF_HEADER]
        ws.clear()
        ws.update([PF_HEADER] + out.astype(str).values.tolist())
        return True
    except Exception:
        return False


def all_users() -> list:
    try:
        ws = _ws("portfolio", PF_HEADER)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty or "user" not in df.columns:
            return []
        return sorted(df["user"].astype(str).unique().tolist())
    except Exception:
        return []


# ── 通知設定 ──────────────────────────────────
def load_notify(user: str):
    try:
        ws = _ws("notify", ["user", "config"])
        for rec in ws.get_all_records():
            if str(rec.get("user")) == str(user):
                return json.loads(rec.get("config") or "{}")
        return {}
    except Exception:
        return None


def save_notify(user: str, cfg: dict) -> bool:
    try:
        ws = _ws("notify", ["user", "config"])
        rows = [[str(r.get("user")), r.get("config", "")]
                for r in ws.get_all_records() if str(r.get("user")) != str(user)]
        rows.append([str(user), json.dumps(cfg, ensure_ascii=False)])
        ws.clear()
        ws.update([["user", "config"]] + rows)
        return True
    except Exception:
        return False

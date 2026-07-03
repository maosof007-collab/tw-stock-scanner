"""
cloud_bootstrap.py — 雲端資料自舉
=================================================
在 Streamlit Cloud 上，repo 不含 878MB 行情資料。開機時若發現 data/ 沒有
價格檔，就從資料包網址（DATA_PACK_URL）下載並解壓；本機（已有資料）則完全不動作。

資料包 = 把整個 data/ 夾壓成 zip（內含 data/ 這層），放 GitHub Release/雲端。
網址來源：st.secrets["DATA_PACK_URL"] → 環境變數 DATA_PACK_URL。
每個行程只跑一次。缺網址或失敗都不會讓 App 掛掉（頁面本來就能容忍無資料）。
"""
from __future__ import annotations
import io
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
_done = False


def _pack_url() -> str:
    try:
        import streamlit as st
        u = st.secrets.get("DATA_PACK_URL", "")
        if u:
            return str(u)
    except Exception:
        pass
    return os.environ.get("DATA_PACK_URL", "")


def _has_price_data() -> bool:
    try:
        return any(DATA.glob("*.TW.csv")) or any(DATA.glob("*.TWO.csv"))
    except Exception:
        return False


def ensure_data(force: bool = False) -> str:
    """需要時下載資料包。回傳狀態字串（供顯示/除錯）。"""
    global _done
    if _done and not force:
        return "skip"
    _done = True
    if _has_price_data() and not force:
        return "local"                       # 本機已有資料 → 不動作
    url = _pack_url()
    if not url:
        return "no-url"                      # 雲端但尚未設定資料包網址
    try:
        import requests
        DATA.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            # 資料包內含 data/ 這層 → 解到專案根；否則解到 data/
            top = z.namelist()[0] if z.namelist() else ""
            z.extractall(ROOT if top.startswith("data/") else DATA)
        return "downloaded"
    except Exception as e:
        return f"error:{e}"

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


# 版本標記：排程每天更新 repo 的 .last_data_update；本地下載後把它抄到 _pack_stamp。
# 兩者不一致 = Release 有新資料包 → 即使檔案還在也要重新下載（修「雲端一直用舊資料」）。
_MARKER = ROOT / ".last_data_update"        # 來自 repo（git pull 會更新）
_STAMP  = DATA / "_pack_stamp.txt"          # 上次下載時的標記副本


def _pack_outdated() -> bool:
    try:
        if not _MARKER.exists():
            return False                     # 尚無標記（排程還沒跑過新版）→ 沿用舊行為
        marker = _MARKER.read_text(encoding="utf-8", errors="replace").strip()
        stamp = _STAMP.read_text(encoding="utf-8", errors="replace").strip() \
            if _STAMP.exists() else ""
        return marker != stamp
    except Exception:
        return False


def ensure_data(force: bool = False) -> str:
    """需要時下載資料包。回傳狀態字串（供顯示/除錯）。
    版本比對每次都做（很便宜，讀兩個小檔）——soft update 不重啟行程，
    _done 旗標會殘留，若先看旗標就永遠不會抓新包。"""
    global _done
    outdated = _pack_outdated()
    if _done and not force and not outdated:
        return "skip"
    _done = True
    if _has_price_data() and not force and not outdated:
        return "local"                       # 檔案在且版本沒變 → 不動作
    if _has_price_data() and outdated:
        print("[cloud_bootstrap] 偵測到新資料包版本 → 重新下載", flush=True)
    url = _pack_url()
    if not url:
        print("[cloud_bootstrap] 無 DATA_PACK_URL，略過（本機或未設定）", flush=True)
        return "no-url"                      # 雲端但尚未設定資料包網址
    try:
        import requests
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = ROOT / "_data_pack.zip"
        print(f"[cloud_bootstrap] 開始下載資料包 … {url[:80]}", flush=True)
        # 串流寫檔（低記憶體），避免雲端免費版被大檔一次載入吃爆
        n = 0
        with requests.get(url, timeout=900, stream=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk); n += len(chunk)
        print(f"[cloud_bootstrap] 下載完成 {n/1048576:.0f} MB，解壓中 …", flush=True)
        with zipfile.ZipFile(tmp) as z:
            top = z.namelist()[0] if z.namelist() else ""
            z.extractall(ROOT if top.startswith("data/") else DATA)
        try:
            tmp.unlink()
        except Exception:
            pass
        cnt = len(list(DATA.glob("*.TW.csv"))) + len(list(DATA.glob("*.TWO.csv")))
        print(f"[cloud_bootstrap] 解壓完成，價格檔 {cnt} 個 ✅", flush=True)
        try:                                  # 記住這版標記，之後版本沒變就不重下
            if _MARKER.exists():
                _STAMP.write_text(_MARKER.read_text(encoding="utf-8", errors="replace"),
                                  encoding="utf-8")
        except Exception:
            pass
        return "downloaded"
    except Exception as e:
        print(f"[cloud_bootstrap] 失敗：{e}", flush=True)
        return f"error:{e}"

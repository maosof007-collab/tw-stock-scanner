"""
twtime.py — 台灣標準時間（UTC+8）
=================================================================
所有「顯示給使用者的時間」「寫進 log 的 timestamp」「盤中/收盤排程判斷」
一律用 now_tw()，不用 datetime.now()——
本機（台灣）兩者相同；雲端（Streamlit Cloud / GitHub Action 都是 UTC）
datetime.now() 會差 8 小時，造成「最後更新 11:20」其實是台灣 19:20。
台灣無日光節約時間，固定 UTC+8 即可。
"""
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8), name="Asia/Taipei")


def now_tw() -> datetime:
    """台灣現在時間（回傳 naive datetime，方便與既有 strftime/比較邏輯相容）"""
    return datetime.now(TW_TZ).replace(tzinfo=None)

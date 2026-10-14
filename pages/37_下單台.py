# -*- coding: utf-8 -*-
"""
pages/37_下單台.py — Nova API 下單台(台新×Fugle)
=================================================================
預設全模擬(dry-run);實單需 config nova_live=true+頁面開關,雙重確認。
每筆(模擬/實單/被家規攔截)都記 data/trade_log.csv。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="下單台", page_icon="🧾", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("Nova 下單台", "ORDER DESK", "🧾")

import nova_trade as nt

s = nt.status()
c1, c2, c3 = st.columns(3)
c1.metric("SDK", "✅ 已安裝" if s["sdk"] else "❌ 未安裝")
c2.metric("憑證設定", "✅ 完整" if s["config"] else "❌ 未填")
c3.metric("實單開關", "🔴 LIVE" if s["live"] else "🟢 模擬(dry-run)")
if s["hint"]:
    st.warning(s["hint"])

with st.expander("📋 事前準備清單(只有你本人能做的四件事)", expanded=not (s["sdk"] and s["config"])):
    st.markdown("""
1. **台新證券帳戶**(已有可跳過)→ 官網線上開戶
2. **憑證 e 管家**申請並匯出 `.pfx` 憑證檔(「憑證快遞」不支援 API)
3. **線上簽署 API 風險聲明書** —— 簽完**隔一天**才生效
4. **下載 SDK wheel**([官方下載頁](https://ml-fugle-api.tssco.com.tw/FugleSDK/docs/download/download-sdk))→
   `pip install taishin_sdk-<版本>-cp37-abi3-win_amd64.whl` → 首次執行 `register_api_auth`
5. 在本機 `config.json`(已 gitignore,永不入庫)新增:
```json
"nova": {"id": "身分證字號", "pwd": "登入密碼",
          "cert_path": "C:/路徑/憑證.pfx", "cert_pwd": "憑證密碼",
          "nova_live": false}
```
""")

st.markdown("---")
st.markdown("### 🎫 下單票(家規內建:買單自動過爆量窗/迴轉率警戒檢查)")
f1, f2, f3, f4 = st.columns([1.5, 1, 1, 1])
_q = f1.text_input("代碼/名稱", key="nt_q")
_side = f2.radio("方向", ["Buy", "Sell"], horizontal=True, key="nt_side")
_lots = f3.number_input("張數", 1, 500, 1, key="nt_lots")
_px = f4.number_input("限價", 0.0, step=0.5, key="nt_px")
_live_ok = s["live"]
_go_live = st.checkbox("⚠️ 送出實單(需 config nova_live=true;未勾=模擬)",
                       value=False, disabled=not _live_ok, key="nt_live")
if st.button("送出", type="primary", key="nt_go") and _q.strip() and _px > 0:
    from symbols import resolve as _rs
    code, nm = _rs(_q.strip())
    if not code:
        st.error("代碼解析失敗")
    else:
        rec = nt.place(code, int(_lots), _side, float(_px), live=bool(_go_live))
        badge = {"SIMULATED": "🟢 模擬單已記錄", "SENT": "🔴 實單已送出",
                 "BLOCKED": "⛔ 家規攔截", "REJECT": "❌ 退回", "ERROR": "⚠️ 錯誤"}
        st.markdown(f"**{badge.get(rec['status'], rec['status'])}**|{nm} {code} "
                    f"{_side} {_lots} 張 @ {_px}|{rec['note']}")

st.markdown("### 📜 交易日誌(模擬+實單+攔截全記)")
if nt.LOG.exists():
    st.dataframe(pd.read_csv(nt.LOG, dtype=str).tail(30).iloc[::-1],
                 hide_index=True, width="stretch")
else:
    st.info("尚無紀錄——第一筆模擬單就會出現在這裡。")

if s["sdk"] and s["config"]:
    if st.button("🔍 查今日委託(需登入)", key="nt_or"):
        try:
            st.dataframe(nt.order_results(), hide_index=True, width="stretch")
        except Exception as e:
            st.warning(f"查詢失敗:{e}")

st.caption(f"<span style='color:{MUTED}'>鐵律:憑證密碼只存本機 config(gitignored);"
           f"預設 dry-run;實單=config 開關+頁面勾選雙重確認;每筆留痕。"
           f"v1 僅限價現股,當沖/零股/市價後續再開。</span>", unsafe_allow_html=True)

"""
gate.py — 私用登入門（5 人內自己人測）
  · 共用密碼門：擋外人
  · 選使用者：每人各自的持倉/通知（阿原/王媽/翔老師/黑哥/珊）
  · 首次進站投資免責聲明

用法：每頁 set_page_config 之後呼叫
    from gate import require_login
    user = require_login()
"""
import os
import streamlit as st

USERS = ["阿原", "王媽", "翔老師", "黑哥", "珊"]
ADMIN_USER = "管理者"


def _password() -> str:
    """朋友共用密碼：.streamlit/secrets.toml [auth] password → 環境變數 → 預設"""
    try:
        return st.secrets["auth"]["password"]
    except Exception:
        return os.environ.get("APP_PASSWORD", "tw2026")


def _admin_password() -> str:
    """管理者專屬密碼（與朋友分開）：secrets [auth] admin_password → 環境變數 → 預設"""
    try:
        return st.secrets["auth"]["admin_password"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "boss2026")


DISCLAIMER = (
    "本站為個人量化研究與數據分析工具，所有選股、訊號、回測**僅供參考，"
    "不構成任何投資建議**。股市有風險，依此操作之盈虧由使用者自行負責。"
)


def require_login() -> str:
    """登入門。回傳目前使用者名稱；未完成則 st.stop()。"""
    # ⓪ 雲端首次開機：若無行情資料，從資料包網址下載（本機有資料則略過）
    try:
        from cloud_bootstrap import ensure_data
        ensure_data()
    except Exception:
        pass

    # ① 密碼（管理者密碼 → 直接以管理者身分登入；朋友密碼 → 進選人流程）
    if not st.session_state.get("authed"):
        st.markdown("## 🔒 台股策略系統 · 登入")
        pw = st.text_input("密碼", type="password")
        if st.button("進入", type="primary"):
            if pw == _admin_password():
                st.session_state.authed = True
                st.session_state.is_admin = True
                st.session_state.user = ADMIN_USER      # 管理者專屬身分/持倉
                st.rerun()
            elif pw == _password():
                st.session_state.authed = True
                st.session_state.is_admin = False
                st.rerun()
            else:
                st.error("密碼錯誤")
        st.caption("自己人測試版，請向管理者索取密碼")
        st.stop()

    # ② 選使用者（管理者已有身分，跳過）
    if not st.session_state.get("user"):
        st.markdown("## 👤 你是哪位？")
        u = st.selectbox("選擇使用者（各自獨立持倉與通知）", USERS)
        if st.button("確認", type="primary"):
            st.session_state.user = u
            st.rerun()
        st.stop()

    # ③ 首次免責同意
    if not st.session_state.get("agreed"):
        st.markdown("## ⚠️ 使用前請確認")
        st.warning(DISCLAIMER)
        if st.button("我了解並同意", type="primary"):
            st.session_state.agreed = True
            st.rerun()
        st.stop()

    return st.session_state.user


def current_user() -> str:
    return st.session_state.get("user", "")


def is_admin() -> bool:
    """是否為管理者（獨立密碼登入）。可用來顯示管理功能。"""
    return bool(st.session_state.get("is_admin", False))


def logout_button():
    """側欄登出（換人或重登）"""
    u = st.session_state.get("user", "")
    tag = "👑 管理者" if is_admin() else u
    if st.sidebar.button(f"🔓 登出（目前：{tag}）", use_container_width=True):
        for k in ("authed", "user", "agreed", "is_admin"):
            st.session_state.pop(k, None)
        st.rerun()

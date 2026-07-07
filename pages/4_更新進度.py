"""
pages/4_更新進度.py — 資料更新 / 掃描 即時進度
可一鍵啟動「更新股價＋掃描」或「只掃描」，並即時觀看進度條。
進度由管線寫入 data/_progress.json，本頁每 2 秒自動刷新讀取。
"""
import sys, subprocess, time
from pathlib import Path
from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from progress import read_progress, clear_progress
from ui_theme import (DARK, CARD, BORDER, TEXT, MUTED, GREEN, RED, GOLD,
                      BLUE, CYAN, inject_css, page_header)

st.set_page_config(page_title="更新進度", page_icon="⏱️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("資料更新 / 掃描進度", "PIPELINE MONITOR", "⏱️")


# ── 啟動管線（背景子行程，不阻塞 UI）─────────────
def launch(cmd: list[str], label: str):
    clear_progress()
    subprocess.Popen(
        cmd, cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    st.session_state["launched"] = label
    st.session_state["launched_at"] = time.time()


def _is_cloud():
    try:
        from auto_refresh import _pack_mode
        return _pack_mode()
    except Exception:
        return False

if _is_cloud():
    # 雲端：資料由每日排程自動更新，不提供手動按鈕（避免混淆 + 暫存不留存）
    st.success("☁️ **雲端版：資料每天自動更新（台灣 17:00），你不用手動做任何事。**")
    st.caption("每天由 GitHub 排程更新股價+掃描、重壓資料包，隔天自動生效。這一頁在雲端只是說明用。")
else:
    c1, c2, c3 = st.columns([2, 2, 6])
    with c1:
        if st.button("🔄 更新股價 ＋ 掃描", type="primary", use_container_width=True):
            launch([sys.executable, "-c",
                    "import subprocess,sys;"
                    "subprocess.run([sys.executable,'updater.py']);"
                    "subprocess.run([sys.executable,'scan_signals.py'])"],
                   "更新股價＋掃描")
            st.rerun()
    with c2:
        if st.button("📡 只掃描訊號", use_container_width=True):
            launch([sys.executable, "scan_signals.py"], "只掃描訊號")
            st.rerun()
    with c3:
        from auto_refresh import auto_update_enabled, set_auto_update
        _au = st.toggle("背景自動更新（關閉＝只有按上面按鈕才更新）",
                        value=auto_update_enabled())
        if _au != auto_update_enabled():
            set_auto_update(_au)
            st.toast("背景自動更新已" + ("開啟" if _au else "關閉（全手動）"))
        st.caption("開啟時：僅在『資料落後』才會自動補；今天已有資料 → 不會自動更新。")

st.markdown("---")

# ── 自動刷新（每 2 秒）─────────────────────────
st_autorefresh(interval=2000, key="progress_refresh")

prog = read_progress()
now  = time.time()

if prog is None:
    st.info("目前沒有進行中的工作。點上方按鈕啟動更新／掃描，這裡會即時顯示進度。")
else:
    phase   = prog.get("phase", "")
    cur     = int(prog.get("current", 0))
    total   = int(prog.get("total", 1)) or 1
    msg     = prog.get("msg", "")
    done    = prog.get("done", False)
    ts      = float(prog.get("ts", now))
    pct     = min(max(cur / total, 0.0), 1.0)
    age     = now - ts            # 距上次更新秒數

    # 階段標題
    st.markdown(f"### {phase}")

    # 進度條
    st.progress(pct, text=f"{cur} / {total}　（{pct*100:.1f}%）")

    # 狀態列
    k1, k2, k3 = st.columns(3)
    k1.metric("已完成", f"{cur:,} / {total:,}")
    k2.metric("進度", f"{pct*100:.1f}%")
    # 估計剩餘時間（用啟動至今平均速度）
    launched_at = st.session_state.get("launched_at")
    if launched_at and cur > 0 and not done:
        elapsed = now - launched_at
        rate    = cur / elapsed if elapsed > 0 else 0
        eta     = (total - cur) / rate if rate > 0 else 0
        k3.metric("預估剩餘", f"{eta/60:.1f} 分" if eta >= 60 else f"{eta:.0f} 秒")
    else:
        k3.metric("預估剩餘", "—")

    if msg:
        st.caption(f"目前：{msg}")

    # 完成 / 卡住 判斷
    if done:
        st.success(f"✅ {phase} 已完成！")
        if "掃描" in phase:
            st.caption("可到「今日選股」頁查看最新訊號（資料已用最新股價重算）。")
    elif age > 90:
        st.error(
            f"⚠️ 進度已 {age:.0f} 秒沒有更新，工作可能卡住或已結束。"
            f"（yfinance 偶有暫時性逾時，可重新啟動）"
        )
    elif age > 20:
        st.warning(f"⏳ 進度 {age:.0f} 秒未更新，可能正在等待某檔下載…")

st.markdown(
    f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
    f"進度檔：{ROOT/'data'/'_progress.json'}　·　每 2 秒自動刷新</p>",
    unsafe_allow_html=True,
)

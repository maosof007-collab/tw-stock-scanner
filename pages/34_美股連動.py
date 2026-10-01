"""
pages/34_美股連動.py — 美股連動雷達(美股族群領先 ↔ 台股受惠/客戶鏈)
=================================================================
教案:2026/09/30 夜資安全族創高(PANW/CRWD/OKTA...)→ 台股資安服務鏈次日對照。
🔥=美股領先(20日≥+10%且有成員貼近高點)而台股對應落後 ≥8pp——「該去查」名單。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="美股連動", page_icon="🦅", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("美股連動雷達", "US-TW LINKAGE", "🦅")

import us_link


@st.cache_data(ttl=3600, show_spinner="更新美股資料+掃描…")
def _scan(ver: int = 1):
    p = ROOT / "data" / "us" / "_us_scan.csv"
    if p.exists():
        import time
        if time.time() - p.stat().st_mtime < 3600 * 8:
            return pd.read_csv(p, dtype={"代碼": str})
    us_link.fetch_us()
    return us_link.scan()


df = _scan()
if df.empty:
    st.warning("尚無資料——本機執行 `python us_link.py`。")
    st.stop()

st.caption("**為什麼看這個**:美股族群「整族轉強」常領先台股對應鏈;配對同時就是客戶鏈"
           "(NVDA/雲端巨頭/Starlink=台廠的終端客戶)。🔥=美股領先而台股落後——"
           "是「該去查」名單,查完照樣過體檢卡。對照表 data/us_pairs.json 可增修。")

hot = df[df["燈號"].astype(str).str.contains("🔥", na=False)]
if len(hot):
    st.error("🔥 美股領先·台股待跟:" + "、".join(
        f"{r['名稱']}{r['代碼']}" for _, r in hot.iterrows()))

for theme, g in df.groupby("主題", sort=False):
    note = next((p.get("note", "") for p in us_link.pairs() if p["theme"] == theme), "")
    with st.expander(f"**{theme}**|🇺🇸 " + "、".join(g[g['市場'] == 'US']['名稱'].head(6))
                     + " ↔ 🇹🇼 " + "、".join(g[g['市場'] == 'TW']['名稱'].head(6)),
                     expanded=bool(len(g[g['燈號'].astype(str).str.contains('🔥', na=False)]))):
        if note:
            st.caption(f"📌 {note}")
        st.dataframe(g[["市場", "代碼", "名稱", "20日%", "距高%", "燈號"]].fillna(""),
                     hide_index=True, width="stretch")

st.caption(f"<span style='color:{MUTED}'>美股資料:yfinance(每日快取);距高%=距近半年高。"
           "美元計價只比相對強弱。run_daily 每日自動更新。</span>", unsafe_allow_html=True)

"""
頁面13：每日強弱日報（自動成文）
================================================
把「大盤 → 族群今日強弱 → RRG 資金輪動 → 新聞熱度」寫成一篇
有感覺的短文。規則式成文離線可跑；設 ANTHROPIC_API_KEY 會再由
Claude 潤成更口語的盤後短評。
"""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import page_header, inject_css, MUTED

st.set_page_config(page_title="每日強弱日報", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("每日強弱日報", "DAILY STRENGTH BRIEF", "📋")

import daily_report


@st.cache_data(ttl=1800, show_spinner="彙整今日強弱並撰寫日報中（約 10-30 秒）…")
def _article(polish: bool):
    return daily_report.generate(polish=polish)


c = st.columns([1.6, 1.4, 4])
polish = c[0].toggle("🤖 Claude 潤稿", value=True,
                     help="需 ANTHROPIC_API_KEY；沒設也能出規則式版本")
if c[1].button("🔄 重新生成"):
    _article.clear()

art = _article(polish)

st.markdown("---")
st.markdown(art)
st.markdown("---")

st.download_button("⬇️ 下載 Markdown", art.encode("utf-8"),
                   file_name=f"daily_brief_{art[4:14].replace('-', '') if len(art) > 14 else 'report'}.md",
                   mime="text/markdown")
st.caption(f"<span style='color:{MUTED}'>每 30 分鐘自動更新一次；按「重新生成」立即重算。"
           f"強弱=族群成分等權漲跌，輪動=JdK RRG 近似，消息=產業新聞熱度。</span>",
           unsafe_allow_html=True)

"""
app.py — 入口路由(st.navigation 分組導航)
================================================
側邊欄分支:今日總覽 → 選股與持倉 / 市場與資金流 / 個股研究 / 系統
頁面本體都在 pages/(檔名不動,URL 不變);首頁本體在 views/home.py。
執行:streamlit run app.py
"""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(page_title="台股決策系統", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")


def _p(fname: str, title: str, icon: str) -> st.Page:
    """pages/ 檔案 → st.Page;URL 沿用「去掉數字前綴的檔名」,舊書籤不失效。"""
    stem = Path(fname).stem
    url = stem.split("_", 1)[1] if "_" in stem and stem.split("_", 1)[0].isdigit() else stem
    return st.Page(f"pages/{fname}", title=title, icon=icon, url_path=url)


nav = st.navigation({
    "": [
        st.Page("views/home.py", title="今日總覽", icon="📈", default=True),
        _p("0_總經.py", "總經(大盤溫度計)", "🌡️"),
    ],
    "選股與持倉": [
        _p("1_今日選股.py", "今日選股(策略掃描)", "🎯"),
        _p("11_翻多選股.py", "翻多選股(底部轉強)", "🔄"),
        _p("14_訊號回查.py", "訊號回查(個股歷史)", "🔍"),
        _p("6_績效追蹤.py", "績效追蹤(持倉管理)", "💼"),
    ],
    "市場與資金流": [
        _p("4_市場資金流向.py", "全球資金流向(RRG+亞洲)", "🌏"),
        _p("2_產業輪動.py", "產業輪動(官方分類RRG)", "🏭"),
        _p("3_族群輪動.py", "主題族群(被動·矽晶圓等)", "🧩"),
        _p("5_新聞分析.py", "新聞與情緒", "📰"),
    ],
    "個股研究": [
        _p("13_個股法人報告.py", "個股研究中心", "🔬"),
        _p("8_籌碼分析儀表板.py", "籌碼分析", "🧮"),
        _p("10_集團股K線.py", "集團股K線", "📊"),
        _p("12_研究文章.py", "研究文章(自產報告)", "📄"),
        _p("9_研究報告瀏覽器.py", "券商報告庫(PDF)", "🗂️"),
    ],
    "系統": [
        _p("7_更新進度.py", "更新進度", "⏱️"),
        _p("15_使用說明.py", "使用說明", "❓"),
    ],
}, expanded=True)
nav.run()

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
                   layout="wide", initial_sidebar_state="collapsed")


def _p(fname: str, title: str, icon: str) -> st.Page:
    """pages/ 檔案 → st.Page;URL 沿用「去掉數字前綴的檔名」,舊書籤不失效。"""
    stem = Path(fname).stem
    url = stem.split("_", 1)[1] if "_" in stem and stem.split("_", 1)[0].isdigit() else stem
    return st.Page(f"pages/{fname}", title=title, icon=icon, url_path=url)


nav = st.navigation({
    "": [
        st.Page("views/home.py", title="今日總覽", icon="📈", default=True),
        _p("26_晨報.py", "每日晨報", "🌅"),
        _p("0_總經.py", "總經(大盤溫度計)", "🌡️"),
    ],
    "選股與持倉": [
        _p("1_今日選股.py", "今日選股(策略掃描)", "🎯"),
        _p("25_籌碼地圖.py", "籌碼選股地圖(五關漏斗)", "🗺️"),
        _p("11_翻多選股.py", "翻多選股(底部轉強)", "🔄"),
        _p("19_月營收預測.py", "月營收預測(開獎前瞻)", "🔮"),
        _p("14_訊號回查.py", "訊號回查(個股歷史)", "🔍"),
        _p("6_績效追蹤.py", "績效追蹤(持倉管理)", "💼"),
        _p("21_權證專區.py", "權證專區(槓桿工具)", "🎫"),
        _p("24_我的ETF.py", "我的ETF(自組模擬)", "🧺"),
    ],
    "市場與資金流": [
        _p("30_中國連動.py", "中國連動雷達(A股對照)", "🐉"),
        _p("16_資金流向日誌.py", "資金流向日誌(當日+解讀)", "💸"),
        _p("22_權證大戶.py", "權證大戶進出(每日)", "🐳"),
        _p("23_法說行事曆.py", "法說行事曆(照時間排)", "🎤"),
        _p("4_市場資金流向.py", "全球資金流向(RRG+亞洲)", "🌏"),
        _p("2_產業輪動.py", "產業輪動(官方分類RRG)", "🏭"),
        _p("3_族群輪動.py", "主題族群(被動·矽晶圓等)", "🧩"),
        _p("5_新聞分析.py", "新聞與情緒", "📰"),
    ],
    "個股研究": [
        _p("28_公司快照.py", "公司快照(研究第一頁)", "🏢"),
        _p("29_財務九宮格.py", "財務九宮格(體質總覽)", "🔲"),
        _p("27_個股戰情室.py", "個股戰情室(一屏儀表牆)", "🎯"),
        _p("13_個股法人報告.py", "個股研究中心", "🔬"),
        _p("20_深度潛力股.py", "深度潛力股(風格長文)", "💎"),
        _p("17_族群儀表板.py", "族群儀表板(一頁總覽)", "🗂️"),
        _p("8_籌碼分析儀表板.py", "籌碼分析", "🧮"),
        _p("18_大戶籌碼週報.py", "大戶籌碼週報(集保)", "🐘"),
        _p("10_集團股K線.py", "集團股K線", "📊"),
        _p("12_研究文章.py", "研究文章(自產報告)", "📄"),
        _p("9_研究報告瀏覽器.py", "券商報告庫(PDF)", "🗂️"),
    ],
    "系統": [
        _p("7_更新進度.py", "更新進度", "⏱️"),
        _p("15_使用說明.py", "使用說明", "❓"),
    ],
}, position="hidden")   # 2026-09-19 介面改造:側欄導航整個拿掉,改首頁駕駛艙區塊卡+全域頂列

# 全域頂列(每一頁都有,回得了家)
_top = st.columns(7)
for _i, (_pg, _lb) in enumerate([
        ("views/home.py", "📈 駕駛艙"),
        ("pages/25_籌碼地圖.py", "🗺️ 地圖"),
        ("pages/6_績效追蹤.py", "🩺 體檢·日誌"),
        ("pages/22_權證大戶.py", "🐳 權證大戶"),
        ("pages/27_個股戰情室.py", "🎯 戰情室"),
        ("pages/19_月營收預測.py", "🔮 月營收"),
        ("pages/7_更新進度.py", "⏱️ 系統")]):
    with _top[_i]:
        st.page_link(_pg, label=_lb)
nav.run()

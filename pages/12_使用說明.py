"""
頁面0：使用說明 / 操作手冊（App 內建，登入後直接看）
排在選單最前面，給朋友快速上手。管理者維護區只有管理者看得到。
"""
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import (CYAN, GREEN, RED, GOLD, PURPLE, TEXT, MUTED, CARD, BORDER,
                      inject_css, page_header)

st.set_page_config(page_title="使用說明", layout="wide")
inject_css()
from gate import require_login, logout_button, is_admin
require_login(); logout_button()
page_header("使用說明", "USER GUIDE", "📖")

st.markdown(
    f"<p style='font-size:1.05rem;color:#c7d3e4;max-width:60ch'>"
    f"系統每天幫你<b style='color:{CYAN}'>選股、看籌碼、追產業輪動、記錄績效</b>。"
    f"左側選單切換頁面。以下是每一頁在幹嘛、怎麼用。</p>",
    unsafe_allow_html=True)

# ── 功能導覽 ──────────────────────────────
st.markdown("### 📂 功能導覽")

FEATURES = [
    ("📡", "今日選股", "Signals", CYAN,
     "系統每天用策略選出的股，<b style='color:%s'>BUY</b> 就是進場訊號。看「掃描日期」確認是哪天的。" % GREEN,
     "展開「🎯 產業輪動篩選」→ 只留領先/改善象限的產業，專挑<b>有資金流入</b>的戰場。"),
    ("🎯", "產業輪動 RRG", "Rotation", CYAN,
     "34 個產業畫成四象限，看資金往哪走。右上<b>領先</b>=最強、左上<b>改善</b>=正在翻上來。",
     "落在<b>領先</b>象限的產業最強；「改善」是潛力產業。看尾巴方向比看點更準。"),
    ("🚀", "翻多選股", "Bull Flip", CYAN,
     "全市場掃出<b>剛由空翻多</b>（SuperTrend 反轉向上）的股，附支撐位與歷史延續機率。",
     "「已延續」小=剛翻多不追高；「距支撐%」小=離停損近、風險小。"),
    ("🏢", "集團股 K 線", "Groups", CYAN,
     "把同集團（台塑/鴻海/國巨…）成員合成一條指數，看整個集團是否<b>一起動</b>。",
     "成員線擠成一束=齊漲齊跌；散開=各走各的。看『平均相關』數字。"),
    ("📊", "籌碼分析", "Chips", CYAN,
     "個股外資/投信/法人、大戶散戶、融資餘額五軌圖，右邊有 <b>SuperTrend</b> 趨勢與風險表。",
     "上方「顯示軌道」可只勾一軌，例如<b>單獨看法人</b>。"),
    ("🌐", "總經", "Macro", CYAN,
     "大盤<b>融資維持率</b>（槓桿風險溫度計，越低越危險）＋七/八月<b>季節性窗口</b>燈號。",
     "維持率跌破警戒且走低=賣壓大；季節性綠燈=順風期。"),
]

cols = st.columns(2)
for i, (ico, name, en, ac, desc, how) in enumerate(FEATURES):
    with cols[i % 2]:
        st.markdown(
            f"""<div style="background:linear-gradient(180deg,{CARD},#0b1220);
            border:1px solid {BORDER};border-radius:14px;padding:16px 18px;margin-bottom:14px">
            <div style="display:flex;align-items:baseline;gap:9px;margin-bottom:6px">
              <span style="font-size:18px">{ico}</span>
              <b style="font-size:16px">{name}</b>
              <span style="margin-left:auto;font-family:monospace;font-size:10px;
                    letter-spacing:.14em;color:{MUTED}">{en.upper()}</span></div>
            <div style="color:#b9c6d8;font-size:14px;margin-bottom:9px">{desc}</div>
            <div style="border-top:1px dashed {BORDER};padding-top:8px;font-size:13px;color:{MUTED}">
              <b style="color:{CYAN}">怎麼用</b>　{how}</div></div>""",
            unsafe_allow_html=True)

st.markdown(
    f"""<div style="background:#0b1220;border:1px solid {CYAN}44;border-radius:14px;
    padding:16px 18px;margin-bottom:14px">
    <div style="display:flex;align-items:baseline;gap:9px;margin-bottom:6px">
      <span style="font-size:18px">📈</span><b style="font-size:16px">績效追蹤（你的持倉）</b>
      <span style="margin-left:auto;font-family:monospace;font-size:10px;letter-spacing:.14em;color:{MUTED}">PORTFOLIO</span></div>
    <div style="color:#b9c6d8;font-size:14px;margin-bottom:9px">
      記錄自己買的股。系統自動算 <b style="color:{GOLD}">移動停利</b>：獲利後停損線一路往上抬，
      打到就賣、<b>鎖住基本獲利</b>。可加碼（第2次進場各自一列）。</div>
    <div style="border-top:1px dashed {BORDER};padding-top:8px;font-size:13px;color:{MUTED}">
      <b style="color:{CYAN}">放心</b>　你的持倉存在雲端，App 重開也不會不見。跌破移動停損收盤會自動出場。</div></div>""",
    unsafe_allow_html=True)

# ── 核心觀念 ──────────────────────────────
st.markdown("### 🧭 三個核心觀念")
st.markdown("<div style='color:%s;margin-bottom:8px'>把這三點記住，比會按每個按鈕重要。</div>" % MUTED,
            unsafe_allow_html=True)

CONCEPTS = [
    ("移動停利", "TRAILING STOP", GOLD,
     "進場後停損線<b>先抬到成本（保本）、再一路往上鎖利</b>，只升不降。打到那條金線就賣——"
     "不猜頭部，讓賺的抱著、虧的快砍。"),
    ("先選戰場", "SECTOR FIRST", CYAN,
     "用<b>產業輪動</b>找出有資金的產業（領先/改善），再在裡面用<b>今日選股/翻多</b>挑個股。"
     "產業對＋訊號對，比單看一檔穩。"),
    ("單一指標不準", "NO SILVER BULLET", GREEN,
     "任何指標（RS、VIX、季節性…）都只是<b>機率的順風</b>，不是保證。進出場要<b>兩個以上確認</b>，"
     "並永遠靠移動停利控風險。"),
]
for lab, en, ac, txt in CONCEPTS:
    st.markdown(
        f"""<div style="display:grid;grid-template-columns:150px 1fr;gap:16px;
        padding:14px 0;border-top:1px solid {BORDER}">
        <div><b style="font-size:15px;color:{ac}">{lab}</b>
          <div style="font-family:monospace;font-size:10px;letter-spacing:.14em;color:{MUTED};margin-top:3px">{en}</div></div>
        <div style="color:#bcc8da;font-size:14px">{txt}</div></div>""",
        unsafe_allow_html=True)

# ── FAQ ──────────────────────────────────
st.markdown("### ❓ 常見問題")
with st.expander("第一次開很慢、轉圈圈？"):
    st.write("正常。系統在下載當天資料（1–3 分鐘），之後就快了。休眠一陣子後第一次開也會再等一下。")
with st.expander("資料是哪一天的？"):
    st.write("以今日選股上的「掃描日期」為準。若和今天差幾天，代表還沒更新（跟管理者說一聲）。")
with st.expander("我加的持倉會不會不見？"):
    st.write("不會。持倉存在雲端，App 重開、換裝置都留著。記得選對自己的名字。")
with st.expander("這些選股可以照著買嗎？"):
    st.write("僅供參考、**不是投資建議**。所有訊號都是統計傾向，盈虧自負，務必自己判斷＋控好停損。")

# ── 管理者維護（只有管理者看得到）──────────────
if is_admin():
    st.markdown("---")
    st.markdown(
        f"""<div style="background:linear-gradient(180deg,#12101f,#0c0a16);
        border:1px solid {PURPLE}55;border-radius:14px;padding:18px 20px">
        <div style="font-family:monospace;font-size:11px;letter-spacing:.2em;color:{PURPLE}">FOR ADMIN · 給管理者</div>
        <b style="font-size:16px">維護備忘</b>
        <ul style="margin:.6em 0 0;color:#c3c9de;font-size:14px;line-height:1.9">
          <li><b>資料更新</b>：已設 GitHub Action，每天台灣 17:00 自動更新股價+掃描、重壓資料包、雲端隔天自動抓新。你零維護。</li>
          <li><b>看大家持倉</b>：打開 Google 試算表，<code>portfolio</code> 分頁裡每個人的持倉都在（user 欄分）。</li>
          <li><b>手動更新</b>：GitHub → Actions → 「每日更新資料包」→ Run workflow。</li>
          <li><b>給朋友</b>：只給網址 + 共用密碼；管理者密碼自己保管。</li>
        </ul></div>""",
        unsafe_allow_html=True)

st.markdown(
    f"<div style='margin-top:34px;padding-top:14px;border-top:1px solid {BORDER};"
    f"color:{MUTED};font-size:12px;font-family:monospace'>"
    f"台股策略系統 · 自己人測試版　|　僅供研究參考 · 非投資建議 · 盈虧自負</div>",
    unsafe_allow_html=True)

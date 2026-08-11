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
    ("🌐", "總經（頁0）", "Macro", CYAN,
     "大盤<b>融資維持率</b>（槓桿風險溫度計，130 追繳線）＋季節性窗口燈號。每日排程自動重算，秒開。",
     "維持率跌破警戒且走低=賣壓大；顯示「快取落後」時按重新彙整。"),
    ("📡", "今日選股（頁1）", "Signals", CYAN,
     "策略每日掃全市場，<b style='color:%s'>BUY</b>=進場訊號，含<b>檢核欄</b>（❌=資料/條件對不上，別碰）。"
     "跌停股自動剔除。" % GREEN,
     "先用<b>⚡風險上限開關</b>（1~10%%逐1、10以上逐5）縮小清單 → 點個股按鈕彈出 K 線："
     "<b>🎯為什麼選它</b>＋入場點▲標記 → 勾選<b>批次加入</b>績效追蹤。"),
    ("🎯", "產業輪動 RRG（頁2）", "Sector RRG", CYAN,
     "官方 33 產業四象限（週線）。點由小到大=行進方向，尾巴只畫近5週。",
     "領先且尾巴續往右上=最強；一週看一次就夠（週線節奏）。"),
    ("🧬", "族群輪動（頁3）", "Themes", CYAN,
     "20 個<b>概念族群</b>（被動元件/功率/矽晶圓/CPO/散熱…）RRG＋"
     "<b style='color:%s'>💰法人資金潮汐</b>：X=近5日法人買超<b>億元</b>、四狀態（漲潮/輪動/觀望/退潮）。" % GOLD,
     "RRG 看價格、潮汐看真金白銀——<b>兩張同向可信度加倍，背離=價籌打架要小心</b>。"),
    ("🌍", "市場資金流向（頁4）", "Global Flow", CYAN,
     "全球 16 市場 RRG（可播動畫）＋<b>亞洲對照</b>：台/韓/日/港/陸 20日報酬與韓-台價差極端監測（30年百分位）。",
     "RS視窗 20=短線、60=波段、120=大層級；價差進 2 百分位會標🚨（僅記錄，不預測方向）。"),
    ("📰", "新聞分析（頁5）＝市場消息面", "News Intel", CYAN,
     "四個分頁：信心分數、新聞情緒（免API也能跑）、法人報告PDF、"
     "<b>產業趨勢雷達</b>（新聞熱度×RRG，🔥=轉熱+資金改善）。",
     "看「哪個產業的消息在轉熱」；個股研究一律去頁13。"),
    ("📈", "績效追蹤（頁6）", "Portfolio", CYAN,
     "持倉自動算<b>移動停利</b>（賺1R保本→鎖利只升不降），跌破自動出場記錄。",
     "狀態欄「持有中(初始停損)」=還沒觸發；可同股加碼各自一列。"),
    ("📊", "籌碼分析（頁8）", "Chips", CYAN,
     "個股法人/大戶散戶/融資五軌圖＋SuperTrend 趨勢。",
     "「顯示軌道」可只勾一軌單獨看法人。"),
    ("🏢", "集團股 K 線（頁10）", "Groups", CYAN,
     "同集團成員合成指數，看是否齊漲齊跌。",
     "成員線擠成一束=一起動；看『平均相關』。"),
    ("🚀", "翻多選股（頁11）", "Bull Flip", CYAN,
     "全市場掃<b>剛由空翻多</b>（SuperTrend 反轉），附支撐與歷史延續機率。",
     "「已延續」小=剛翻多；「距支撐%」小=風險小。"),
    ("📰", "研究文章（頁12）", "Library", GOLD,
     "頁13 產生的報告自動發佈到這裡，<b>網站式閱讀版面</b>，且已 commit 進 git 永久保存。",
     "左側清單選文章、右側閱讀；可下載/刪除。"),
    ("🧾", "個股研究中心（頁13）＝單一入口", "Research Hub", GOLD,
     "<b>Key 股號全自動</b>：月營收明細/三情境推估、模型回測+誤差歸因、"
     "<b>融資融券每日結論（含台指期結算對應）</b>、重大訊息🔴、"
     "<b>全年估值（H1實績+H2推估，財報>自結>推估三層）</b>、預實追蹤自動對答案、"
     "同業比較圖、報告兩模式（產業比較型/法人六層型）。",
     "研究一檔股票從這頁開始；法說紀要貼補充欄；產生的報告自動進頁12。"),
    ("🔎", "訊號回查（頁14）", "Lookback", GOLD,
     "Key 股號查<b>策略以前找到過它嗎</b>：哪幾天、什麼等級、加入過持倉沒、"
     "<b>為什麼當初沒選到</b>（自動診斷），K 線疊策略歷史訊號看錯過成本。",
     "看到別人推的飆股，先來這裡查系統當初有沒有抓到、卡在哪。"),
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

# ── 主頁功能 ──────────────────────────────
st.markdown(
    f"""<div style="background:#0b1220;border:1px solid {GOLD}44;border-radius:14px;
    padding:16px 18px;margin-bottom:14px">
    <b style="font-size:16px">📝 主頁「今日族群趨勢」三分頁</b>
    <div style="color:#b9c6d8;font-size:14px;margin-top:6px">
    <b>強弱日報</b>（第一分頁）：大盤→最強/最弱族群→資金輪動觀察→明日觀察，
    一篇看完今天；資料舊了會跳⚠️警告標明落後幾天。<b>熱力地圖/族群明細</b>：當日各產業漲跌與下鑽。</div></div>""",
    unsafe_allow_html=True)

# ── FAQ ──────────────────────────────────
st.markdown("### ❓ 常見問題")
with st.expander("資料幾點更新？（重要）"):
    st.write(
        "- **股價**：官方源（證交所/櫃買）盤後約 14:00 公布，系統 **15:10** 起自動更新——下午三點多看就是今天的\n"
        "- **三大法人**：約 16:00 公布，17:10 槍補上\n"
        "- **融資融券**：約 21:00 公布，21:10/23:10 槍補上（白天看到前一日屬正常）\n"
        "- **月營收**：每月 10 日前；**季報**：5/15、8/14、11/14、3/31 前\n"
        "- 雲端資料包每天 15:10/17:00/22:30 三班更新；日報資料舊了會自動跳⚠️警告")
with st.expander("第一次開很慢、轉圈圈？"):
    st.write("正常。雲端在下載資料包（約 1–3 分鐘），之後就快了。資料日期落後時到「更新進度」頁按「📦 立即重抓最新資料包」。")
with st.expander("訊號旁的「檢核」欄是什麼？"):
    st.write("每筆訊號都用原始資料重新驗證過：✅=通過；❌會寫原因（如融資資料過期、條件對不上）——❌的別當真訊號。")
with st.expander("我加的持倉會不會不見？"):
    st.write("不會。持倉存在雲端（Google Sheets），App 重開、換裝置都留著。多檔勾選是批次一次寫入，不會漏。")
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
          <li><b>資料更新</b>：GitHub Action 每天台灣 15:10/17:00/22:30 三班（官方源當日K→籌碼→新聞→掃描→資料包）；
              本機 Windows 排程 15:10 起每 2 小時，傍晚每槍補法人/融資融券。零維護。</li>
          <li><b>資料異常自癒</b>：大盤檔自動清異常列；資料包下載失敗會在「更新進度」頁紅字顯示＋一鍵重抓。</li>
          <li><b>登入</b>：目前關閉（免密碼直接進，自動為管理者）；要重新上鎖在 secrets [auth] 加 enabled=true。</li>
          <li><b>看大家持倉</b>：Google 試算表 <code>portfolio</code> 分頁（user 欄分）。</li>
          <li><b>手動更新</b>：GitHub → Actions → 「每日更新資料包」→ Run workflow。</li>
        </ul></div>""",
        unsafe_allow_html=True)

st.markdown(
    f"<div style='margin-top:34px;padding-top:14px;border-top:1px solid {BORDER};"
    f"color:{MUTED};font-size:12px;font-family:monospace'>"
    f"台股策略系統 · 自己人測試版　|　僅供研究參考 · 非投資建議 · 盈虧自負</div>",
    unsafe_allow_html=True)

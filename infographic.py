# -*- coding: utf-8 -*-
"""
infographic.py — 懶人包級資訊圖產生器(HTML/CSS 排版 → Playwright 渲染 PNG)
=================================================================
matplotlib 畫統計圖,這裡畫「懶人包」:多欄卡片+流程箭頭+圖標+中文大字。
用法: render_html(html, out_png, width=1660)  或  python infographic.py 跑示範。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent
IMG = ROOT / "data" / "research_articles" / "img"

BASE_CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Microsoft JhengHei','Noto Sans TC',sans-serif}
body{background:linear-gradient(135deg,#1b3a5c 0%,#20486e 55%,#173352 100%);padding:34px 30px;width:1660px}
.title{color:#fff;font-size:46px;font-weight:900;text-align:center;letter-spacing:2px;
  text-shadow:0 2px 8px rgba(0,0,0,.4);margin-bottom:26px}
.row{display:flex;gap:24px;align-items:stretch}
.panel{flex:1;background:#f4f7fb;border-radius:22px;padding:20px 18px 18px;
  box-shadow:0 10px 26px rgba(0,0,0,.35)}
.phead{position:relative;z-index:3;color:#fff;font-size:26px;font-weight:800;text-align:center;border-radius:999px;
  padding:10px 6px;margin:-34px auto 16px;width:88%;box-shadow:0 4px 10px rgba(0,0,0,.25)}
.blue{background:#1f6fb2}.purple{background:#7b3fa0}.orange{background:#e07b1f}
.card{background:#fff;border-radius:14px;padding:12px 14px;margin:10px 0;
  box-shadow:0 2px 6px rgba(0,0,0,.10);font-size:21px;color:#233}
.card b{color:#0f2c4c}
.flow{display:flex;align-items:center;gap:8px;margin:10px 0}
.fbox{background:#dbe8f5;border:2px solid #9db9d8;border-radius:12px;padding:10px 12px;
  font-size:20px;font-weight:700;color:#173a5e;text-align:center;flex:1}
.fbox.hot{background:#fde3e0;border-color:#e08e86;color:#8c2f28}
.fbox.ok{background:#e2f2e4;border-color:#8fc79a;color:#20603a}
.arrow{font-size:26px;color:#4a6a8f;font-weight:900}
.bars{display:flex;justify-content:space-around;align-items:flex-end;height:215px;margin:34px 0 4px}
.bar{width:26%;text-align:center;color:#123}
.stick{width:64px;margin:0 auto;border-radius:10px 10px 4px 4px;position:relative}
.stick .pct{position:absolute;top:8px;width:100%;font-size:22px;font-weight:900;color:#fff !important;text-shadow:0 1px 3px rgba(0,0,0,.35)}
.bname{font-size:22px;font-weight:800;margin-top:8px}
.bsub{font-size:16.5px;color:#456;line-height:1.4;margin-top:4px;white-space:nowrap}
.note{font-size:16px;color:#9db4cc;text-align:center;margin-top:18px}
.badge{display:inline-block;background:#eef4fa;border:1.5px solid #b9cfe4;border-radius:8px;
  padding:2px 8px;font-size:17px;margin:2px 2px;color:#1f4e7d;font-weight:700}
.big{font-size:40px}
</style>"""


def render_html(html: str, out: Path, width: int = 1660, scale: int = 2) -> Path:
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")   # 用系統內建 Edge,免下載
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": 240},
                        device_scale_factor=scale)
        pg.set_content(html, wait_until="networkidle")
        pg.screenshot(path=str(out), full_page=True)
        b.close()
    return out


# ── 示範:不鏽鋼管件鏈懶人包(對齊使用者提供的範例版型) ──
DEMO = BASE_CSS + """
<div class="title">不鏽鋼管件鏈懶人包:大甲、彰源與「下一棒」解析</div>
<div class="row">

<div class="panel"><div class="phead blue">一、鏈上股價漲幅差異原因</div>
  <div class="bars">
    <div class="bar"><div class="stick" style="height:170px;background:linear-gradient(#c62828,#e57368)"><div class="pct" style="color:#c62828">+126%</div></div>
      <div class="bname">大甲(2221)</div><div class="bsub">EP/BA超潔淨管件<br><b>純度題材本尊</b></div></div>
    <div class="bar"><div class="stick" style="height:96px;background:linear-gradient(#d84315,#ef8a65)"><div class="pct" style="color:#d84315">+46%</div></div>
      <div class="bname">彰源(2030)</div><div class="bsub">上游鋼管·產能極大<br>吃純水/廢水外圍單</div></div>
    <div class="bar"><div class="stick" style="height:46px;background:linear-gradient(#f9a825,#fbd06a)"><div class="pct" style="color:#b07800">+14%</div></div>
      <div class="bname">允強(2034)</div><div class="bsub">同為鋼管<br>題材疊度較低·落後</div></div>
  </div>
  <div class="card">📌 <b>差異=疊度</b>:業務與題材的重疊度越純,市場給的漲幅越大——「獲利純度」是排序鍵。</div>
</div>

<div class="panel"><div class="phead purple">二、EP/BA 潔淨管技術階層</div>
  <div class="flow"><div class="fbox">半導體廠<br>特殊氣體管路</div><div class="arrow">➜</div>
    <div class="fbox hot">EP/BA 超潔淨<br>無縫鋼管</div><div class="arrow">➜</div>
    <div class="fbox">無塵室<br>微塵=0 容忍</div></div>
  <div class="card">🔬 <b>需求分級</b>(市場觀點,待查證):</div>
  <div class="flow"><div class="fbox hot">半導體級<br>純度最高</div><div class="arrow">→</div><div class="fbox">強新?<br><span style="font-size:17px">疊度最高·待查證</span></div></div>
  <div class="flow"><div class="fbox">大宗管材<br>+外圍純水廢水</div><div class="arrow">→</div><div class="fbox ok">彰源<br><span style="font-size:17px">產能極大·已驗證</span></div></div>
  <div class="flow"><div class="fbox">廠房水電<br>消防配管</div><div class="arrow">→</div><div class="fbox">美亞?<br><span style="font-size:17px">外圍基建·待查證</span></div></div>
</div>

<div class="panel"><div class="phead orange">三、下一棒的檢核三問</div>
  <div class="card"><span class="big">🧪</span> <b>①純度</b>——該業務占營收/獲利多少?<br>
    <span class="badge">九宮格查毛利結構</span><span class="badge">快照查業務占比</span></div>
  <div class="card"><span class="big">🏭</span> <b>②產能</b>——吃得下這波量嗎?滿載了沒?<br>
    <span class="badge">月營收動能</span><span class="badge">資本支出表態</span></div>
  <div class="card"><span class="big">⏳</span> <b>③時程</b>——受惠是現在,還是兩年後?<br>
    <span class="badge">法說時間表</span><span class="badge">在手訂單</span></div>
  <div class="card" style="background:#fff7e8">⚠️ 三問全過→再過<b>體檢卡</b>;帶「?」的公司=假設,查證後才進鏈譜。</div>
</div>
</div>
<div class="note">資料:系統鏈譜+市場貼文觀點(標?者未驗證)·本圖為研究筆記非投資建議 · TW-BACKTEST 供應鏈雷達</div>
"""

if __name__ == "__main__":
    out = render_html(DEMO, IMG / "chain_steel_infographic.png")
    print("saved:", out)


# ── 晶技 3042:AI 重評懶人包 ──
INFO_3042 = BASE_CSS + """
<div class="title">晶技(3042)AI 重評懶人包:石英「心跳稅」的單價革命</div>
<div class="row">

<div class="panel"><div class="phead blue">一、重評本質:ASP 階梯</div>
  <div class="bars">
    <div class="bar"><div class="stick" style="height:40px;background:linear-gradient(#f9a825,#fbd06a)"><div class="pct">1.5</div></div>
      <div class="bname">800G</div><div class="bsub">現役主力</div></div>
    <div class="bar"><div class="stick" style="height:64px;background:linear-gradient(#d84315,#ef8a65)"><div class="pct">2~2.5</div></div>
      <div class="bname">1.6T</div><div class="bsub"><b>放量中</b></div></div>
    <div class="bar"><div class="stick" style="height:148px;background:linear-gradient(#b3261e,#e57368)"><div class="pct">~7 美元</div></div>
      <div class="bname">3.2T</div><div class="bsub">2027量產<br><b>單價 4 倍以上</b></div></div>
  </div>
  <div class="card">🏭 法說原文:「相同應用位置、更高規格——<b>每機櫃時脈價值 ASP +50%</b>」+IEEE 1588 新增用量</div>
  <div class="card">📌 同樣的產線、同樣的壁壘,<b>單價表第一次陡峭向上</b>=從被動元件評價走向 AI 零組件評價</div>
</div>

<div class="panel"><div class="phead purple">二、為什麼是它:規格門檻墊高</div>
  <div class="flow"><div class="fbox">光通訊往<br>1.6T/3.2T</div><div class="arrow">➜</div>
    <div class="fbox hot">sub-30fs 抖動<br><b>變成入場門檻</b></div><div class="arrow">➜</div>
    <div class="fbox">能玩的只剩<br>4~5 家(市占20%+)</div></div>
  <div class="flow"><div class="fbox" style="min-width:190px">NVLink/CXL/PCIe 6-7<br>多協定並存</div><div class="arrow">➜</div>
    <div class="fbox hot">時脈域倍增<br>GPU/DPU/NIC/光模組</div><div class="arrow">➜</div>
    <div class="fbox ok" style="min-width:150px">差分XO<br>顆數+單價齊升</div></div>
  <div class="card">🚗 <b>第二引擎·車用</b>:L2→L3 每車 <b>+45 顆</b>(滲透率20-25%),Grade1 車規全系列</div>
  <div class="card">📡 <b>第三引擎·6G</b>:參考頻率上移至 491.52MHz、sub-5ppb → <b>OCXO 等級升級</b>(2027起)</div>
</div>

<div class="panel"><div class="phead orange">三、鐵證與對答案點</div>
  <div class="card" style="background:#fde9e7"><span class="big">🚨</span> <b>Lytica 2026/07</b>:頻率控制=<b>全市場最緊缺類別</b><br>
    <span class="badge">可得率 82.4% 最低</span><span class="badge">價格 +2.5%</span><span class="badge">交期 +13.5%</span></div>
  <div class="card">✅ 已兌現:7月毛利率 <b>36%</b>(Q2 33.1%)·8月營收+23.5% 連創同期新高·同業NDK上修EPS+30%</div>
  <div class="card">💰 下檔地板:<b>連續十年配息率 80%+</b>(中性 EPS 6.45→股利約5.2元)</div>
  <div class="card" style="background:#fff7e8">⚠️ <b>裂縫=行情本體</b>:FactSet 共識停在 <b>90 元</b>(2025/12)vs 市價 203——外資補報告之日=下段引信</div>
  <div class="card">📅 對答案:<span class="badge">每月10日營收</span><span class="badge">11/14 Q3(毛利35%+?)</span><span class="badge">外資報告</span></div>
</div>
</div>
<div class="note">資料:公司9/1法說簡報·優分析·Lytica元件市場報告·系統模型|研究筆記非投資建議 · TW-BACKTEST</div>
"""


def make_3042():
    return render_html(INFO_3042, IMG / "3042_infographic.png")

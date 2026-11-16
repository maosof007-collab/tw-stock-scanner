# -*- coding: utf-8 -*-
"""族群海報:資訊安全 — 誰是真的做資安、占多少、今天誰在漲。(2026-11-16)
占比與題材是查證資料(寫死在下面,●=開過原文、?=只看到摘要);漲跌/營收/籌碼讀數每次重產時即時算。"""
import glob

import pandas as pd

import industry_tree as it
from poster import card, checks, save_poster, shell, ud
from twtime import now_tw

DATE = now_tw().strftime("%Y%m%d")

# (代號, 名稱, 做什麼, 資安占營收, 查證)
PURE = [
    ("7765", "中華資安", "資安檢測、監控、顧問;中華電信子公司", "約 100%;毛利率 43%", "●"),
    ("6690", "安碁資訊", "資安監控中心、檢測;宏碁集團", "未揭露,本業即資安;毛利率 42%", "●"),
    ("8272", "全景軟體", "身分認證、加密的自有軟體", "約八成;毛利率 68%", "?"),
    ("7823", "奧義賽博-KY", "AI 資安軟體,九成訂閱", "約 100%;毛利率 79%,本業虧損", "●"),
]
HW = [
    ("3564", "其陽", "防火牆等網路安全設備的硬體代工", "86%;毛利率 31%", "●"),
    ("6416", "瑞祺電通", "網路安全硬體平台", "74%(期間不明);毛利率 24%", "?"),
    ("6245", "立端", "網路安全硬體平台", "約 74%(舊資料);毛利率 28%", "?"),
]
AGENT = [
    ("3029", "零壹", "資安與網路設備代理", "48%(含網路設備);毛利率 11%", "●"),
    ("6112", "邁達特", "資訊產品代理、雲端服務", "5.4%", "●"),
    ("6163", "華電網", "系統整合", "6.5%", "●"),
    ("6214", "精誠", "資訊服務龍頭", "未揭露", "?"),
    ("2480", "敦陽科", "系統整合", "未揭露", "?"),
]
# 11/16 媒體列為「資安/資服」漲停的,我沒查過資安占比
FOLLOW = [("6697", "東捷資訊"), ("7767", "仁大資訊"), ("6865", "偉康科技"), ("6752", "叡揚"),
          ("6148", "驊宏資"), ("2468", "華經"), ("2471", "資通"), ("6751", "智聯服務")]
CHIP = [("5274", "信驊"), ("4919", "新唐"), ("3529", "力旺")]

sl = pd.read_csv("data/stock_list.csv", dtype=str)
known = set(sl.code)
allc = [c for grp in (PURE, HW, AGENT) for c, *_ in grp] + [c for c, _ in FOLLOW + CHIP]
R = it.readings(tuple(c for c in allc if c in known), with_health=True)


def px(code):
    """(今日%, 5日%, 20日%, 今日量/20日均量, 最後日期);沒有價量檔回 None"""
    f = glob.glob(f"data/{code}.TW*.csv")
    if not f:
        return None
    d = pd.read_csv(f[0]).dropna(subset=["Close"])
    if len(d) < 25:
        return None
    c, v = d.Close, d.Volume
    r = lambda n: (c.iloc[-1] / c.iloc[-1 - n] - 1) * 100
    return r(1), r(5), r(20), v.iloc[-1] / v.iloc[-21:-1].mean(), d.Date.iloc[-1]


P = {c: px(c) for c in allc}
LAST = max(p[4] for p in P.values() if p)
bm = pd.read_csv("data/benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
BM1 = (bm.iloc[-1] / bm.iloc[-2] - 1) * 100
BMPT = bm.iloc[-1] - bm.iloc[-2]


def mv(code) -> str:
    p = P.get(code)
    if not p:
        return "<small>系統無價量</small>"
    return (f'{ud(round(p[0], 1), f"{p[0]:+.1f}%")}<br><small>5 日 {p[1]:+.0f}%、20 日 {p[2]:+.0f}%<br>量 {p[3]:.1f} 倍</small>')


def table(rows) -> str:
    out = '<table><tr><th>公司</th><th>資安占營收</th><th>近3月營收</th><th>今日</th></tr>'
    for code, name, role, share, flag in rows:
        if code in R.index and pd.notna(R.loc[code, "yoy3"]):
            x = R.loc[code]
            rev = (f'{ud(round(float(x.yoy3)), f"{float(x.yoy3):+.0f}%")}'
                   f'<br><small>前3月 {float(x.yoy3_prev):+.0f}% {x.health}</small>')
        else:
            rev = "<small>系統無資料</small>"
        out += (f'<tr><td><b>{name}</b> {code}<br><small>{role}</small></td>'
                f'<td>{flag} {share}</td><td class="n">{rev}</td><td class="n">{mv(code)}</td></tr>')
    return out + "</table>"


def mini(rows) -> str:
    out = '<table><tr><th>公司</th><th>今日</th><th>5 日</th><th>20 日</th><th>量(倍)</th></tr>'
    for code, name in rows:
        p = P.get(code)
        if not p:
            out += f'<tr><td><b>{name}</b> {code}</td><td colspan="4"><small>系統無價量</small></td></tr>'
            continue
        out += (f'<tr><td><b>{name}</b> {code}</td><td class="n">{ud(round(p[0], 1), f"{p[0]:+.1f}%")}</td>'
                f'<td class="n">{p[1]:+.0f}%</td><td class="n">{p[2]:+.0f}%</td><td class="n">{p[3]:.1f}</td></tr>')
    return out + "</table>"


def rng(rows, i=0) -> str:
    v = [P[c][i] for c, *_ in rows if P.get(c)]
    return f"{min(v):+.0f}%~{max(v):+.0f}%"


pure3 = [r for r in PURE if P.get(r[0])]
d1 = "、".join(f"{n} {P[c][0]:+.1f}%" for c, n, *_ in pure3)
volx = [P[c][3] for c, *_ in pure3]
MD = f"{int(LAST[5:7])}/{int(LAST[8:10])}"

c_concl = card("結論(重點先看)", checks([
    ("ok", f"{MD} 大盤 {ud(round(BM1, 1), f'{BM1:+.2f}%')}({BMPT:+,.0f} 點),<b>純資安逆勢</b>:{d1};"
           f"三檔近 5 日 {rng(pure3, 1)}"),
    ("ok", "不是今天才開始:安碁 11 月中已在一年新高,全景軟體 20 日漲幅最大——"
           f"純資安近 20 日 {rng(pure3, 2)}"),
    ("xx", f"<b>同一個「資安概念」兩種走勢</b>:漲的是服務與軟體;硬體平台今天 {rng(HW)}、"
           f"安全晶片 {rng(CHIP)}"),
    ("wn", "?題材(媒體說法,我只看到摘要):銀行遭駭與帳戶盜用事件、微軟當機;"
           "政府研議擴大資安法納管範圍;AI 伺服器出貨延後,資金轉到軟體與資服"),
    ("wn", "營收沒有跟著跳:中華資安近 3 月年增 23%、安碁 8%、全景 9%——一週漲兩三成是評價在動"),
    ("xx", f"今天三檔的量是 20 日均量的 <b>{min(volx):.1f}~{max(volx):.1f} 倍</b>且漲停:"
           "系統家規這是「爆量後禁入」的窗;大盤燈號 🔴(禁開新倉、只出不進)"),
]), src="●=開過原文 ?=只看到摘要", extra_cls="grow")

c_pure = card("純資安:服務商與自有產品", table(PURE)
              + '<div class="note">真正做資安的掛牌公司很少:數聯、TeamT5、池安、熵碼等 14 家沒掛牌,只能透過母公司碰到。'
                '奧義在台灣創新板(7823),系統還沒有它的價量。</div>')
c_hw = card("硬體平台:替國際資安大廠做設備", table(HW)
            + '<div class="note">毛利率 24~31%,跟的是防火牆設備的換機週期,不是台灣的資安事件。</div>')
c_agent = card("代理與整合:資安只是一部分", table(AGENT))
c_follow = card(f"{MD} 被媒體列為資安、資服的漲停股", mini(FOLLOW)
                + '<div class="note"><b>這幾家我沒查過資安占營收多少</b>,多數是資訊服務公司。'
                  '媒體另外點名藍新資訊(6938),系統沒有這一檔。</div>')
c_chip = card("安全晶片:安全功能是產品特性,拆不出營收", mini(CHIP))

c_drive = card("需求誰在推", """<table><tr><th>推力</th><th>內容</th></tr>
<tr><td><b>法規</b></td><td>●資安法修正 2025/12/1 施行:通報時限 1 小時、罰鍰上限加倍</td></tr>
<tr><td><b>事件</b></td><td>●2024 年上市櫃資安重訊 69 件,年增 176%</td></tr>
<tr><td><b>後量子加密</b></td><td>●美國 6 月下令聯邦系統 2030 年底前換完;Gartner 把 2027 年防火牆設備成長預測從 7.8% 上修到 13.4%——對應的是硬體平台</td></tr>
<tr><td><b>利潤在哪</b></td><td>國際原廠毛利 75~82% > 台灣服務商 42~46% > 硬體代工 24~31% > 代理約 11%</td></tr></table>""")

c_risk = card("限制與反面意見", checks([
    ("xx", "服務商靠加人成長:中華資安上半年營收增 21%、獲利只增 13%"),
    ("xx", "內需小:安碁一年營收約 24 億元,Fortinet 一季就 20.8 億美元"),
    ("wn", "專案集中下半年認列,政府預算延遲會直接拖訂單"),
    ("wn", "今年 AI 找漏洞工具推出後,國際資安股曾單日跌一成;Fortinet 第三季優於財測,盤後仍跌 25%"),
    ("wn", "資金往平台大廠集中,人力型服務商不導入 AI 會被擠壓(查證時的推論)"),
]), extra_cls="risk")

c_note = card("讀這張表要注意", checks([
    ("wn", "占比多半來自法說摘要和媒體;立端、瑞祺電的 74% 不要當成 2026 年數字"),
    ("wn", f"漲跌與量是系統 {MD} 收盤;營收體檢燈號的籌碼部分還是前一個交易日(法人資料盤後才公布)"),
    ("wn", "容易搞錯:7892 是元鈦科不是池安;中菲行是物流,做金融系統的是中菲電腦(5403);來毅數位 8 月已下興櫃"),
    ("ok", "被掛概念但占比很低:邁達特、華電網、大綜、伊雲谷、是方"),
]), extra_cls="risk grow")

html = shell(
    title_html="資訊安全<b>族群</b>總整理",
    subtitle=f"純資安掛牌只有四家——{MD} 大盤重挫那天,系統有價量的三家都漲停;硬體和晶片那一段跟著大盤跌",
    brand="資安鏈",
    cols=[c_concl + c_pure, c_follow + c_hw + c_agent + c_chip, c_drive + c_risk + c_note],
    footer=f"素材:逐家上網查證(2026/11/16)+系統 {DATE[:4]}/{DATE[4:6]}/{DATE[6:]} 價量與營收讀數 · 本海報為研究筆記非投資建議")
print("saved:", save_poster("資安", DATE, html))

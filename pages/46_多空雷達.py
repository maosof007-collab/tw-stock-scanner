"""
頁面46:多空雷達 — 照族群的卡片式雷達(一族群一張卡、一檔一列、三燈+標籤)
================================
版型依使用者 2026-11-12 提供的參考畫面:族群頭(排名升降/上漲家數/徽章)+
個股列(外資・投信・大戶 三燈:圓點=中期立場、箭頭=短期方向;大戶跑/避開×N)。
數據全來自 dual_radar.compute()(每日排程重掃):
  三燈=法人日檔近20/5日累計、集保400張以上大戶近4週/最新週變化
  大戶跑=最新週 ≤ -1pp(大戶週報既有門檻);避開×N=破季線/融資套牢>3倍/爆量收黑/法人雙賣
  🌱候補=7/30 復盤營收因子;🐻反彈空=S1(回測 EV10 +3.1%/勝率75%)
"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="多空雷達", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("多空雷達", "LONG / SHORT RADAR", "⚖️")

import dual_radar as _dr
_dr = importlib.reload(_dr)          # 每次重載:長駐不重啟的 app 也吃得到模組更新
D = Path(__file__).parent.parent / "data"

if not (D / "_dual_radar_stocks.csv").exists():
    st.info("尚無雷達資料——按下方「重新掃描」產生第一份(或等每日排程)。")
    if st.button("🔄 重新掃描"):
        with st.spinner("全市場掃描中(約 1-2 分鐘)…"):
            _dr.compute()
        st.rerun()
    st.stop()


@st.cache_data(ttl=600)
def _load(mtime: float):             # mtime 進快取鍵:檔案一更新就重讀(參數不可加底線前綴)
    s = pd.read_csv(D / "_dual_radar_stocks.csv", dtype={"code": str})
    g = pd.read_csv(D / "_dual_radar_groups.csv")
    return s, g


sdf, gdf = _load((D / "_dual_radar_stocks.csv").stat().st_mtime)
if "排名20" not in gdf.columns or "bull_ok" not in sdf.columns:
    st.warning("雷達資料是舊格式——請按「重新掃描」更新一次。")
    if st.button("🔄 重新掃描"):
        with st.spinner("全市場掃描中(約 1-2 分鐘)…"):
            _dr.compute()
        st.rerun()
    st.stop()

asof = str(sdf["date"].max())
members = sdf[sdf["group"] != "(未分組)"].copy()
members["group"] = members["group"].str.split("|")
members = members.explode("group")

# ── 控制列 ──
c1, c2, c3, c4 = st.columns([2.2, 1.6, 1, 1])
q = c1.text_input("🔎 搜尋個股(全市場;代號或名稱)", placeholder="例:2408、南亞科、正達").strip()
order = c2.selectbox("族群排序", ["20日排名(強→弱)", "偏空在前(淨傾向低→高)", "今日上漲家數比"])
with c3:
    st.write("")
    open_all = st.toggle("全部展開", value=False)
with c4:
    st.write("")
    if st.button("🔄 重新掃描", help="全市場逐檔掃約 1-2 分鐘;每日排程會自動掃"):
        with st.spinner("全市場掃描中(約 1-2 分鐘)…"):
            _dr.compute()
        st.cache_data.clear()
        st.rerun()

n_run = int(members.drop_duplicates("code")["big_run"].sum())
n_s1 = int((sdf["s1_today"] == True).sum())  # noqa: E712
n_bull = int((sdf["bull_ok"] == True).sum())  # noqa: E712
st.caption(f"資料 **{asof[5:].replace('-', '/')}**|{gdf.shape[0]} 族群 {members['code'].nunique()} 檔|"
           f"大戶跑 {n_run} 檔|🐻 反彈空命中 {n_s1}|🌱 多方候補 {n_bull}(全市場)|"
           "燈號=外資・投信・大戶:圓點=中期(法人20日/大戶4週)、箭頭=短期(法人5日/大戶最新週);紅買綠賣")

CSS = ("<style>"
       ".gc{background:#0f1b2d;border:1px solid #1f3350;border-radius:14px;margin:0 auto 10px;max-width:880px;color:#e8eef7;overflow:hidden}"
       ".gc summary{list-style:none;cursor:pointer;padding:14px 18px}.gc summary::-webkit-details-marker{display:none}"
       ".gh{display:flex;justify-content:space-between;align-items:center;gap:12px}"
       ".gn{font-size:1.25rem;font-weight:700;margin-right:8px}"
       ".bd{font-size:.85rem;font-weight:700;padding:2px 8px;border-radius:7px;border:1.5px solid #f5c542;color:#f5c542}"
       ".bd.acc{border-color:#ff5a5f;color:#ff5a5f}"
       ".gs{color:#8a9bb3;font-size:.92rem;margin-top:4px}"
       ".bar{height:5px;background:#1c2c44;border-radius:3px;margin-top:8px;width:min(46vw,400px)}.bar i{display:block;height:5px;border-radius:3px;background:#ff5a5f}"
       ".gr{display:flex;align-items:center;gap:22px;text-align:right;white-space:nowrap}"
       ".pct{font-size:1.05rem;line-height:1.15;font-variant-numeric:tabular-nums}.pct small{display:block;color:#8a9bb3;font-size:.85rem}"
       ".sc{font-size:1.2rem;font-weight:700;font-variant-numeric:tabular-nums}"
       ".r{color:#ff5a5f}.g{color:#2ecc8f}.m{color:#5b6b82}"
       ".th,.row{display:grid;grid-template-columns:minmax(0,1.5fr) 110px 110px;align-items:center;padding:0 18px}"
       ".th{color:#8a9bb3;font-size:.85rem;padding-top:6px;padding-bottom:6px;border-top:1px solid #1f3350}"
       ".th span:nth-child(2){text-align:center}.th span:nth-child(3){text-align:right}"
       ".row{border-top:1px solid #1a2a42;padding-top:10px;padding-bottom:10px}"
       ".n1{font-size:1.12rem;font-weight:700}.n2{color:#8a9bb3;font-size:.9rem;margin-top:3px;display:flex;flex-wrap:wrap;gap:5px;align-items:center}"
       ".tg{font-size:.8rem;padding:1px 7px;border-radius:6px;border:1.5px solid;white-space:nowrap}"
       ".tg.y{border-color:#f5c542;color:#f5c542}.tg.a{border:1.5px dashed #ff7b80;color:#ff9a9e}"
       ".tg.b{border-color:#ff5a5f;color:#ff5a5f}.tg.s{border-color:#b08cff;color:#c9b0ff}"
       ".tg.q{border-color:#33445c;color:#7f8ea3;border-width:1px}"
       ".gc.hit{border-color:#f5c542}.gp{color:#8a9bb3;font-size:.8rem}"
       ".lts{display:flex;justify-content:center;gap:9px}.lt{display:flex;flex-direction:column;align-items:center;line-height:1}"
       ".d{width:13px;height:13px;border-radius:50%;display:block;margin-bottom:3px}.d.r{background:#ff5a5f}.d.g{background:#2ecc8f}.d.m{background:#3a4a62}"
       ".lt b{font-size:.95rem;font-weight:700}"
       ".px{text-align:right;font-variant-numeric:tabular-nums}.p1{font-size:1.1rem}.p2{font-size:.92rem}"
       "</style>")
st.markdown(CSS, unsafe_allow_html=True)


def _cls(v) -> str:
    if v is None or pd.isna(v) or v == 0:
        return "m"
    return "r" if v > 0 else "g"


def _light(mid, short, tip: str) -> str:
    cm, cs = _cls(mid), _cls(short)
    arrow = "–" if cs == "m" else ("↗" if cs == "r" else "↘")
    return f'<span class="lt" title="{tip}"><i class="d {cm}"></i><b class="{cs}">{arrow}</b></span>'


def _delta(v: int) -> str:
    if v > 0:
        return f'<b class="r">▲{v}</b>'
    if v < 0:
        return f'<b class="g">▼{-v}</b>'
    return '<b class="m">–</b>'


def _row(r, show_groups: bool = False) -> str:
    """標籤互斥:有硬傷(避開/大戶跑)就不給候補;破季線只是灰色狀態標,不算避開。"""
    tags = ""
    if r["big_run"] == True:  # noqa: E712
        tags += f'<span class="tg y" title="400張以上大戶持股最新週 {r["bh1"]:+.2f}pp">大戶跑</span>'
    n = int(r["avoid_n"]) if pd.notna(r["avoid_n"]) else 0
    if n:
        why = [t for flag, t in [(r["trap"], "融資套牢>3倍日均量"), (r["vol_black"], "今日爆量收黑"),
                                 (r["inst_dual_sell"], "外資投信近5日雙賣")] if flag == True]  # noqa: E712
        tags += f'<span class="tg a" title="{"、".join(why)}">避開×{n}</span>'
    if r["s1_today"] == True:  # noqa: E712
        tags += '<span class="tg s" title="套牢池反彈空 S1 命中(回測 EV10 +3.1%)">🐻反彈空</span>'
    if r["bull_ok"] == True:  # noqa: E712
        tags += f'<span class="tg b" title="營收YoY {r["rev_yoy"]:+.0f}%+殺深+未收復,且無避開理由、大戶未跑">🌱候補</span>'
    if r["below_ma60"] == True:  # noqa: E712
        tags += '<span class="tg q" title="收盤在 60 日均線下(狀態,不算避開理由)">季線下</span>'
    if show_groups:
        gtxt = str(r["group"]).replace("|", "、")
        tags += f'<span class="gp">{gtxt}</span>'
    lights = (_light(r["fi20"], r["fi5"], f'外資 20日 {r["fi20"]:+,.0f}張/5日 {r["fi5"]:+,.0f}張' if pd.notna(r["fi20"]) else "外資:無資料")
              + _light(r["it20"], r["it5"], f'投信 20日 {r["it20"]:+,.0f}張/5日 {r["it5"]:+,.0f}張' if pd.notna(r["it20"]) else "投信:無資料")
              + _light(r["bh4"], r["bh1"], f'大戶 4週 {r["bh4"]:+.2f}pp/最新週 {r["bh1"]:+.2f}pp' if pd.notna(r["bh4"]) else "大戶:無資料"))
    c = _cls(r["chg1"])
    return (f'<div class="row"><div><div class="n1">{r["name"]}</div><div class="n2">{r["code"]}・{tags}</div></div>'
            f'<div class="lts">{lights}</div>'
            f'<div class="px"><div class="p1">{r["close"]:,.2f}</div><div class="p2 {c}">{r["chg1"]:+.2f}%</div></div></div>')


def _card(g, rows: pd.DataFrame, opened: bool) -> str:
    n, up = int(g["檔數"]), int(g["上漲檔"])
    pct = up / n * 100 if n else 0
    badge = ""
    if isinstance(g["徽章"], str) and g["徽章"]:
        badge = f'<span class="bd{" acc" if g["徽章"] == "吸籌中" else ""}">{g["徽章"]}</span>'
    net = float(g["淨傾向"])
    head = (f'<summary><div class="gh"><div><span class="gn">{g["group"]}</span>{badge}'
            f'<div class="gs">20日排名 {int(g["排名20"])}・昨 {_delta(int(g["昨升降"]))}・5天 {_delta(int(g["五日升降"]))}'
            f'・20日中位 {g["r20中位"]:+.1f}%</div>'
            f'<div class="bar"><i style="width:{pct:.0f}%"></i></div></div>'
            f'<div class="gr"><div class="pct">{pct:.0f}%<small>{up}/{n}</small></div>'
            f'<div class="sc {_cls(net)}" title="淨傾向=多方分-空方分">{net:+.1f}</div></div></div></summary>')
    body = ('<div class="th"><span>股票</span><span>外資・投信・大戶</span><span>收盤／今日</span></div>'
            + "".join(_row(r) for _, r in rows.iterrows()))
    return f'<details class="gc"{" open" if opened else ""}>{head}{body}</details>'


g_sorted = {"20日排名(強→弱)": gdf.sort_values("排名20"),
            "偏空在前(淨傾向低→高)": gdf.sort_values("淨傾向"),
            "今日上漲家數比": gdf.assign(_p=gdf["上漲檔"] / gdf["檔數"]).sort_values("_p", ascending=False)}[order]

hit_groups = None
if q:
    # 個股搜尋:全市場(雷達掃描範圍)直接出一張結果卡,再列出它所屬的整個族群當對照
    hits = sdf[sdf["code"].str.contains(q, case=False, regex=False)
               | sdf["name"].astype(str).str.contains(q, case=False, regex=False)].head(30)
    if hits.empty:
        st.info(f"雷達範圍內找不到「{q}」——日均成交額不到 0.5 億、又不在 30 個主題族群裡的股票不在掃描範圍。")
    else:
        body = ('<div class="th"><span>股票</span><span>外資・投信・大戶</span><span>收盤／今日</span></div>'
                + "".join(_row(r, show_groups=True) for _, r in hits.iterrows()))
        st.markdown(f'<details class="gc hit" open><summary><div class="gh"><div><span class="gn">🔎 搜尋結果</span>'
                    f'<div class="gs">「{q}」共 {len(hits)} 檔;灰字=所屬族群(未分組=不在主題族群內)</div></div></div></summary>'
                    f'{body}</details>', unsafe_allow_html=True)
    hit_groups = {g for gs in hits["group"] for g in str(gs).split("|")}

for _, g in g_sorted.iterrows():
    if hit_groups is not None and g["group"] not in hit_groups:
        continue                     # 搜尋時只留命中個股所屬的族群(整族列出,方便跟同族比)
    rows = members[members["group"] == g["group"]].sort_values("chg1", ascending=False)
    st.markdown(_card(g, rows, opened=bool(q) or open_all), unsafe_allow_html=True)

# ── 已驗證的兩張行動清單(全市場,不限族群) ──
with st.expander(f"📋 全市場行動清單:🌱 多方候補 {n_bull} 檔/🐻 反彈空近5日命中"):
    cl, cr = st.columns(2)
    with cl:
        st.markdown("**🌱 多方候補**(營收YoY>30%+殺深>10%+未收復,**且無避開理由、大戶未跑**;7/30 復盤快彈率 57%)")
        b = sdf[sdf["bull_ok"] == True].sort_values("turn", ascending=False).head(30)  # noqa: E712
        st.dataframe(b[["code", "name", "close", "off_hi", "flush", "retrace", "rev_yoy", "turn"]]
                     .rename(columns={"code": "代碼", "name": "名稱", "close": "收盤", "off_hi": "距250高%",
                                      "flush": "殺幅%", "retrace": "回升幅度", "rev_yoy": "營收YoY%", "turn": "日均額(億)"})
                     .style.format({"回升幅度": "{:.0%}", "距250高%": "{:+.1f}", "殺幅%": "{:+.1f}",
                                    "營收YoY%": "{:+.1f}"}, na_rep="—"),
                     hide_index=True, width="stretch", height=380)
    with cr:
        st.markdown("**🐻 套牢池反彈空 S1**(回測 EV10 +3.1%/勝率 75%/n76;次日開盤進、10日出)")
        h = sdf[sdf["s1_hits"].fillna("") != ""].sort_values("chg5", ascending=False)
        if h.empty:
            st.info("近 5 日無命中(月均 2-3 筆)。")
        else:
            st.dataframe(h[["code", "name", "close", "chg5", "off_hi", "margin_mult", "vol_mult", "s1_hits"]]
                         .rename(columns={"code": "代碼", "name": "名稱", "close": "收盤", "chg5": "5日漲%",
                                          "off_hi": "距250高%", "margin_mult": "套牢倍數", "vol_mult": "量倍",
                                          "s1_hits": "命中日"})
                         .style.format({"5日漲%": "{:+.1f}", "距250高%": "{:+.1f}"}, na_rep="—"),
                         hide_index=True, width="stretch", height=380)
    st.caption("不接刀:多方等站回 MA20/突破確認;空方只空瘋狂反彈、不追殺(反彈失敗空與爆量長黑追空回測皆負 EV)。處置股不可空。")

with st.expander("📖 怎麼讀這頁"):
    st.markdown(
        "- **三顆燈**由左至右=外資・投信・大戶(集保 400 張以上)。**圓點**是中期立場(法人近 20 日累計買賣超、大戶近 4 週持股變化),"
        "**箭頭**是短期方向(法人近 5 日、大戶最新一週)。紅=買/增、綠=賣/減、灰=無資料。滑鼠停在燈上看實際張數。\n"
        "- **大戶跑**=最新一週大戶持股比例減少 ≥1pp(與大戶週報同門檻;集保每週更新一次)。\n"
        "- **避開×N**=籌碼行為面的硬傷:融資套牢>3 倍日均量、今日爆量收黑、外資投信近 5 日雙賣——中幾條算幾,滑鼠停上去看是哪幾條。"
        "「季線下」只是灰色狀態標,不算避開理由。\n"
        "- **🌱候補**與避開**互斥**:營收YoY>30%+殺深+未收復,而且沒有任何避開理由、大戶沒在跑,才給候補。\n"
        "- **族群頭**:20 日排名=30 族群按「成分股 20 日報酬中位」排序;▲▼=跟昨天/5 天前比的名次升降;"
        "右側百分比=今日上漲家數;最右數字=淨傾向(多方分-空方分)。\n"
        "- **徽章**:疑似出貨=過半成分大戶跑,且法人沒有明顯在接(20 日買超檔數不到六成);吸籌中=六成以上法人買超+過半大戶增持。\n"
        "- 分數與標籤是體檢,不是買賣單。")

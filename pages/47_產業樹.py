"""
頁面47:產業樹 — 先垂直(樹幹:上游→下游)再水平(枝葉),再問慣性/痛點/限制
=================================================================
一棵樹一個檔:data/industry_trees/<slug>.json(查證後人工入檔;✓=有來源,?=假設)。
每個節點接系統既有讀數(industry_tree.readings):營收轉折、20日/距高/季線、
外資・投信・大戶、買前體檢燈;「限制」用現金流量表的資本支出查核(industry_tree.capex_*)。
擴產查核表 data/_tree_capex.csv 由 run_daily 每週重建;本頁只讀檔(按鈕可手動重算)。
"""
import html
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
import ui_theme as T
from ui_theme import inject_css, page_header

st.set_page_config(page_title="產業樹", page_icon="🌳", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("產業樹", "INDUSTRY TREE · TRUNK / BRANCH / LIMIT", "🌳")

import industry_tree as _it
_it = importlib.reload(_it)          # 迭代中的模組:長駐不重啟的 app 也吃得到更新
D = Path(__file__).parent.parent / "data"

trees = _it.load_all()
if not trees:
    st.info("還沒有任何一棵樹——把查證過的鏈寫成 data/industry_trees/<名稱>.json 就會出現在這裡。")
    st.stop()

titles = {t.get("title", k): k for k, t in trees.items()}
sel = st.selectbox("選一棵樹(一個產業一棵,越種越多)", list(titles), key="tree_sel")
tree = trees[titles[sel]]
slug = tree["_slug"]

bad = _it.validate(tree)
if bad:
    st.error("代號查核沒過(先修樹檔再看讀數):" + ";".join(bad))

E = html.escape
mem = _it.members(tree)
codes = tuple(dict.fromkeys(mem["code"].tolist()))


def _stamp() -> float:
    ms = [p.stat().st_mtime for p in (D / "_rev_history.csv", D / "_bigholder_panel.csv",
                                      D / "benchmark_TWII.csv") if p.exists()]
    return max(ms) if ms else 0.0


@st.cache_data(ttl=900, show_spinner="讀取每個節點的營收/籌碼/體檢…")
def _readings(cs: tuple, stamp: float) -> pd.DataFrame:      # stamp 進快取鍵:資料一更新就重算
    return _it.readings(cs)


R = _readings(codes, _stamp())
CX = _it.load_capex()
asof = str(R["date"].dropna().max()) if "date" in R.columns and R["date"].notna().any() else "—"
rev_ym = str(R["rev_ym"].dropna().max()) if R["rev_ym"].notna().any() else "—"
cx_q = str(CX["q"].dropna().max()) if len(CX) and CX["q"].notna().any() else "—"


def _cx(code: str) -> tuple[str, str, dict]:
    row = CX.loc[code].to_dict() if len(CX) and code in CX.index else {"q": None}
    y3 = R.loc[code, "yoy3"] if code in R.index else None
    lamp, txt = _it.capex_verdict(row, y3)
    return lamp, txt, row


# ── 一句話 + 資料日期 ─────────────────────────────────────────
st.markdown(
    f"<div style='border:1px solid {T.BORDER};border-radius:12px;background:{T.CARD};padding:12px 16px;margin:6px 0 10px'>"
    f"<div style='font-size:12px;color:{T.MUTED}'>這棵樹要回答的問題</div>"
    f"<div style='font-size:17px;font-weight:700;color:{T.TEXT};margin:2px 0 6px'>{E(tree.get('question', ''))}</div>"
    f"<div style='font-size:13.5px;color:{T.TEXT};line-height:1.6'>{E(tree.get('thesis', ''))}</div>"
    f"<div style='font-size:12px;color:{T.MUTED};margin-top:8px'>樹檔更新 {E(tree.get('updated', '—'))}|股價・法人 {asof}|"
    f"大戶 {E(R.attrs.get('bh_week', '') or '—')} 週|營收 {rev_ym}|財報 {cx_q}|"
    f"<span style='color:{T.GREEN}'>✓</span> 有來源查證 <span style='color:{T.GOLD}'>?</span> 假設待查</div></div>",
    unsafe_allow_html=True)

# ── 哪一段在動(各段中位數) ────────────────────────────────────
rows = []
for part, key in (("樹幹", "trunk"), ("枝葉", "branches")):
    for seg in tree.get(key, []):
        cs = [str(m[0]) for m in seg.get("members", []) if str(m[0]) in R.index]
        if not cs:
            continue
        x = R.loc[cs]
        lamps = [_cx(c)[0] for c in cs]

        def _med(col: str):
            return round(float(x[col].median()), 1) if col in x.columns and x[col].notna().any() else None

        rows.append({"位置": part, "段": seg.get("stage", ""), "檔數": len(cs),
                     "營收近3月年增%(中位)": _med("yoy3"), "前3月%": _med("yoy3_prev"),
                     "20日%(中位)": _med("r20"), "距高%(中位)": _med("off_hi"),
                     "季線下": f"{int(x['below_ma60'].fillna(False).astype(bool).sum())}/{len(cs)}" if "below_ma60" in x.columns else "—",
                     "大戶4週(中位)": _med("bh4"),
                     "外資20日買超": f"{int((x['fi20'] > 0).sum())}/{len(cs)}",
                     "🟢在蓋產能": lamps.count("🟢"), "🔴沒在蓋(查稼動率)": lamps.count("🔴")})
st.markdown("#### 哪一段在動")
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption("讀法:營收看「近3月年增」有沒有比「前3月」高(需求在加速);大戶4週是 400 張以上持股比例的變化(百分點);"
           "🟢/🔴 是下方「限制」的擴產查核結果。中位數只在同一段檔數夠多時才有代表性。")


# ── 成員表(樹幹/枝葉共用) ──────────────────────────────────────
def _num(v, fmt="{:+.1f}", suf="", color=True) -> str:
    if v is None or v != v:
        return f"<span style='color:{T.MUTED}'>—</span>"
    col = T.TEXT if not color or abs(v) < 1e-9 else (T.RED if v > 0 else T.GREEN)
    return f"<span style='color:{col}'>{fmt.format(v)}{suf}</span>"


_KIND_COL = {"由負轉正": "RED", "加速": "RED", "維持高成長": "GOLD", "持平成長": "MUTED", "跌幅收斂": "MUTED", "衰退": "GREEN", "資料不足": "MUTED"}


def _member_table(members: list) -> str:
    th = f"padding:5px 8px;text-align:right;font-weight:500;color:{T.MUTED};font-size:12px;border-bottom:1px solid {T.BORDER};white-space:nowrap"
    td = f"padding:6px 8px;text-align:right;border-bottom:1px solid {T.GRID};white-space:nowrap"
    heads = ["公司", "在這一段做什麼", "營收近3月年增", "(前3月)", "20日", "距高", "季線", "外資20日", "投信20日", "大戶4週", "體檢", "擴產"]
    h = "".join(f"<th style='{th}{';text-align:left' if i < 2 else ''}'>{x}</th>" for i, x in enumerate(heads))
    body = ""
    for m in members:
        code, name, role = str(m[0]), m[1], m[2]
        flag = m[3] if len(m) > 3 else "?"
        r = R.loc[code] if code in R.index else pd.Series(dtype=object)
        fl = f"<span style='color:{T.GREEN if flag == '✓' else T.GOLD};font-weight:700'>{E(flag)}</span>"
        kind = r.get("rev_kind", "資料不足")
        kcol = getattr(T, _KIND_COL.get(kind, "MUTED"))
        hi = " 🏔️" if bool(r.get("rev_hi", False)) else ""
        ma = r.get("below_ma60")
        ma_s = f"<span style='color:{T.MUTED}'>—</span>" if ma is None or ma != ma else (f"<span style='color:{T.GREEN}'>下</span>" if bool(ma) else f"<span style='color:{T.RED}'>上</span>")
        lamp, txt, _row = _cx(code)
        body += ("<tr>"
                 f"<td style='{td};text-align:left'><b style='color:{T.TEXT}'>{E(name)}</b> <span style='color:{T.MUTED};font-size:12px'>{code}</span> {fl}</td>"
                 f"<td style='{td};text-align:left;white-space:normal;color:{T.TEXT};min-width:200px'>{E(role)}</td>"
                 f"<td style='{td}'>{_num(r.get('yoy3'), '{:+.0f}', '%')} <span style='color:{kcol};font-size:11.5px'>{E(kind)}{hi}</span></td>"
                 f"<td style='{td}'>{_num(r.get('yoy3_prev'), '{:+.0f}', '%', color=False)}</td>"
                 f"<td style='{td}'>{_num(r.get('r20'), '{:+.1f}', '%')}</td>"
                 f"<td style='{td}'>{_num(r.get('off_hi'), '{:+.0f}', '%')}</td>"
                 f"<td style='{td}'>{ma_s}</td>"
                 f"<td style='{td}'>{_num(r.get('fi20'), '{:+,.0f}')}</td>"
                 f"<td style='{td}'>{_num(r.get('it20'), '{:+,.0f}')}</td>"
                 f"<td style='{td}'>{_num(r.get('bh4'), '{:+.2f}')}</td>"
                 f"<td style='{td}' title='{E(str(r.get('health_txt', '')))}'>{E(str(r.get('health', '') or '—'))}</td>"
                 f"<td style='{td}' title='{E(txt)}'>{lamp}</td>"
                 "</tr>")
    return (f"<div style='overflow-x:auto;margin:0 0 4px'><table style='width:100%;border-collapse:collapse;font-size:13px'>"
            f"<tr>{h}</tr>{body}</table></div>")


def _seg_card(i: int, seg: dict, accent: str, sub_key: str, sub_label: str) -> str:
    extra = ""
    if seg.get("global"):
        extra += f"<div style='font-size:12.5px;color:{T.MUTED};margin-top:4px'>全球主要供應商:{E(seg['global'])}</div>"
    if seg.get("note"):
        extra += f"<div style='font-size:13px;color:{T.TEXT};margin-top:4px;line-height:1.55'>{E(seg['note'])}</div>"
    if seg.get("capex_note"):
        extra += f"<div style='font-size:12px;color:{T.GOLD};margin-top:4px'>看擴產時注意:{E(seg['capex_note'])}</div>"
    return (f"<div style='border:1px solid {T.BORDER};border-left:4px solid {accent};border-radius:10px;background:{T.CARD};padding:10px 14px;margin:8px 0 6px'>"
            f"<div style='font-size:16px;font-weight:700;color:{T.TEXT}'>{i}. {E(seg.get('stage', ''))}</div>"
            f"<div style='font-size:13px;color:{T.MUTED};margin-top:2px'>{sub_label}{E(seg.get(sub_key, ''))}</div>{extra}</div>")


st.markdown("---")
st.markdown("### 🌲 樹幹|垂直:從上游到下游,這個東西經歷了什麼")
trunk = tree.get("trunk", [])
for i, seg in enumerate(trunk, 1):
    st.markdown(_seg_card(i, seg, T.CYAN, "what", ""), unsafe_allow_html=True)
    if seg.get("members"):
        st.markdown(_member_table(seg["members"]), unsafe_allow_html=True)
    else:
        st.caption("這一段沒有台灣上市櫃公司(或還沒查證到)。")
    if i < len(trunk):
        st.markdown(f"<div style='text-align:center;color:{T.MUTED};font-size:15px;line-height:1'>▼</div>", unsafe_allow_html=True)
st.caption("欄位:營收=近3個月合計跟去年同期比(括號是再往前3個月);🏔️=最新月營收創歷史新高;距高=離250日高點;"
           "外資/投信=近20日累計買賣超(張);大戶4週=400張以上持股比例變化(百分點);體檢=買前體檢卡結論;擴產=下方「限制」查核。"
           "體檢與擴產欄把滑鼠移上去看原因。紅=正、綠=負。")

if tree.get("branches"):
    st.markdown("---")
    st.markdown("### 🌿 枝葉|水平:它旁邊還有什麼,誰在推它升級(或搶它的位置)")
    for i, seg in enumerate(tree["branches"], 1):
        st.markdown(_seg_card(i, seg, T.PURPLE, "push", "推動力:"), unsafe_allow_html=True)
        if seg.get("members"):
            st.markdown(_member_table(seg["members"]), unsafe_allow_html=True)

# ── 慣性 / 痛點 / 限制 ─────────────────────────────────────────
st.markdown("---")
st.markdown("### 🧭 思辯|慣性 → 痛點 → 限制")


def _src(s) -> str:
    if not s:
        return ""
    return f" <a href='{E(s)}' target='_blank' style='color:{T.BLUE};font-size:12px'>來源</a>"


if tree.get("inertia"):
    st.markdown("**慣性**(這個產業一再重複的走法,換一個產業也適用)")
    items = "".join(f"<li style='margin:3px 0;color:{T.TEXT}'>{E(x['text'] if isinstance(x, dict) else x)}{_src(x.get('src') if isinstance(x, dict) else '')}</li>"
                    for x in tree["inertia"])
    st.markdown(f"<ul style='font-size:13.5px;line-height:1.6;margin:0 0 8px 0'>{items}</ul>", unsafe_allow_html=True)

if tree.get("pains"):
    st.markdown("**痛點**(順著慣性問下去,卡在哪裡;誰在解)")
    out = ""
    for p in tree["pains"]:
        fl = p.get("flag", "?")
        out += (f"<div style='border:1px solid {T.BORDER};border-radius:10px;background:{T.CARD};padding:9px 13px;margin:6px 0'>"
                f"<div style='font-size:14px;font-weight:700;color:{T.TEXT}'>{E(p.get('pain', ''))} "
                f"<span style='color:{T.GREEN if fl == '✓' else T.GOLD}'>{E(fl)}</span>{_src(p.get('src'))}</div>"
                f"<div style='font-size:13px;color:{T.TEXT};margin-top:3px;line-height:1.55'><span style='color:{T.MUTED}'>解法:</span>{E(p.get('fix', ''))}</div>"
                f"<div style='font-size:13px;color:{T.TEXT};margin-top:2px;line-height:1.55'><span style='color:{T.MUTED}'>誰在解:</span>{E(p.get('who', ''))}</div></div>")
    st.markdown(out, unsafe_allow_html=True)

if tree.get("limits"):
    st.markdown("**限制**(打不破的東西——公司說「明年就解決」時,拿這些來對)")
    out = ""
    for p in tree["limits"]:
        out += (f"<div style='border:1px solid {T.BORDER};border-left:4px solid {T.GOLD};border-radius:10px;background:{T.CARD};padding:9px 13px;margin:6px 0'>"
                f"<div style='font-size:14px;font-weight:700;color:{T.TEXT}'>{E(p.get('limit', ''))}{_src(p.get('src'))}</div>"
                f"<div style='font-size:13px;color:{T.TEXT};margin-top:3px;line-height:1.55'>{E(p.get('why', ''))}</div>"
                f"<div style='font-size:12.5px;color:{T.MUTED};margin-top:3px'>系統怎麼查:{E(p.get('check', ''))}</div></div>")
    st.markdown(out, unsafe_allow_html=True)

# ── 擴產查核表 ─────────────────────────────────────────────────
st.markdown("#### 🏗️ 擴產查核|公司說要擴產,錢有沒有真的花下去")
if not len(CX):
    st.info("還沒有擴產查核表(每日排程每週重建一次)。可以先按下方按鈕算第一份。")
else:
    CLAIMS = tree.get("claims", {})
    crow = []
    seen = set()
    for _, m in mem.iterrows():
        if m.code in seen:
            continue
        seen.add(m.code)
        lamp, txt, row = _cx(m.code)
        crow.append({"判定": lamp, "公司": f"{m['name']} {m.code}", "段": m.stage,
                     "營收近3月年增%": R.loc[m.code, "yoy3"] if m.code in R.index else None,
                     "資本支出近4季(億)": row.get("capex_ttm"), "前4季(億)": row.get("capex_prev"),
                     "變化%": row.get("capex_chg"), "最新一季(億)": row.get("capex_q"),
                     "資本支出/折舊": row.get("capex_dep"), "佔營收%": row.get("capex_rev"),
                     "固定資產年增%": row.get("ppe_yoy"), "存貨天數": row.get("inv_days"),
                     "去年同期": row.get("inv_days_ly"), "財報怎麼說": txt,
                     "公司怎麼說": (lambda c: (f"{c.get('flag', '?')} {c.get('say', '')}" + (f"({c['date']})" if c.get("date") else "")) if c else "—")(CLAIMS.get(m.code)),
                     "財報季": row.get("q")})
    cdf = pd.DataFrame(crow)
    cdf["_o"] = cdf["判定"].map({"🔴": 0, "🟢": 1, "🟡": 2, "⚪": 3})
    cdf = cdf.sort_values(["_o", "變化%"], ascending=[True, False]).drop(columns="_o")
    st.dataframe(cdf, hide_index=True, width="stretch",
                 column_config={"財報怎麼說": st.column_config.TextColumn(width="large"),
                                "公司怎麼說": st.column_config.TextColumn(width="large")})
st.caption("規則(寫死、可檢查):🟢 資本支出是折舊的 1.5 倍以上、且近4季比前4季多三成以上=真的在蓋產能;"
           "🔴 營收近3月年增三成以上,但資本支出還不到折舊、或近4季沒有增加=需求強卻沒在蓋(有閒置產能的公司本來就不用蓋,所以要去查稼動率);🟡 其餘。"
           "「公司怎麼說」是法說或新聞的口徑(✓ 開過原文、? 只看到摘要),跟左邊的財報數字並排,對不上的就是要追問的地方。"
           "資本支出=現金流量表「取得不動產、廠房及設備」。**查不到的東西**:稼動率和交期不在財報裡,只能看法說,樹檔裡會標來源。"
           "資本支出花下去到產能開出還有時間差,這張表回答的是「有沒有在蓋」,不是「何時開出」。")
if st.button("🔄 重新計算擴產查核(連線抓財報,約 1 分鐘)", key=f"cx_rebuild_{slug}"):
    with st.spinner("抓現金流量表/資產負債表…"):
        _it.build_capex(force=True)
    st.rerun()

# ── 別掛錯題材 ─────────────────────────────────────────────────
if tree.get("excluded"):
    st.markdown("#### 🚫 別掛錯|名字像、其實不在這條鏈上(或只沾到邊)")
    out = "".join(f"<li style='margin:3px 0;color:{T.TEXT}'><b>{E(x[1])}</b> <span style='color:{T.MUTED};font-size:12px'>{E(str(x[0]))}</span>:{E(x[2])}</li>"
                  for x in tree["excluded"])
    st.markdown(f"<ul style='font-size:13.5px;line-height:1.6;margin:0 0 8px 0'>{out}</ul>", unsafe_allow_html=True)

# ── 來源 / 怎麼種下一棵 ────────────────────────────────────────
if tree.get("sources"):
    with st.expander(f"📚 這棵樹的來源({len(tree['sources'])} 筆)"):
        for s in tree["sources"]:
            if isinstance(s, dict) and s.get("url"):
                st.markdown(f"- [{s.get('title', s['url'])}]({s['url']})" + (f"({s['date']})" if s.get("date") else ""))
            else:
                st.markdown(f"- {s}")
c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("pages/32_產業鏈.py", label="⛓️ 產業鏈魚骨圖(接力警示)")
with c2:
    st.page_link("pages/29_財務九宮格.py", label="🔲 財務九宮格(單檔看資本支出/存貨)")
with c3:
    st.page_link("pages/46_多空雷達.py", label="⚖️ 多空雷達(照族群)")
st.caption("種下一棵:照同樣格式寫 data/industry_trees/<名稱>.json(樹幹 trunk/枝葉 branches/慣性 inertia/痛點 pains/限制 limits),"
           "成員一律 [代號, 名稱, 角色, ✓或?]。先排樹幹的前後因果,再掛枝葉;沒查到來源的一律標 ?。")

"""
pages/32_產業鏈.py — 產業鏈魚骨圖(一條鏈一張圖,每日發想的家)
=================================================================
資料:data/supply_chain.json(查證過的鏈譜)+ 每日供應鏈發想(草稿題目)。
畫法:graphviz 魚骨(上游→中游→下游,外圍掛側邊),節點=股票卡(20日動能上色)。
鏈很大就一條一頁——用上方選單切換,不塞在同一屏。
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import MUTED, inject_css, page_header

st.set_page_config(page_title="產業鏈", page_icon="⛓️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("產業鏈魚骨圖", "SUPPLY CHAIN MAP", "⛓️")

import supply_chain as _sc

_SEG_ORDER = {"上游": 0, "原料": 0, "製程": 1, "中游": 1, "設備": 1,
              "檢測": 2, "下游": 3, "終端": 3, "外圍": 4, "平行": 4}


def _seg(role: str) -> str:
    return str(role).split("|")[0].strip()


def _mom_color(m):
    if m is None:
        return "#3a4556", "#c9d4e3"
    if m >= 20:
        return "#B3261E", "#ffffff"
    if m >= 5:
        return "#E5484D", "#ffffff"
    if m >= -5:
        return "#4a5568", "#e6edf3"
    return "#1F7A44", "#ffffff"


chains = _sc.load()
names = [c["chain"] for c in chains]
sel = st.selectbox("選一條鏈(一條鏈一頁,不互相干擾)", names, key="chain_sel")
ch = next(c for c in chains if c["chain"] == sel)
st.caption(f"📌 {ch.get('note', '')}|鏈譜檔:data/supply_chain.json(查證後手動增修;"
           f"每日發想只出題,不自動入譜)")

# ── 魚骨圖(HTML/CSS 卡片流,懶人包同款視覺) ──
moms = {m[0]: _sc._mom(m[0]) for m in ch["members"]}
segs: dict[str, list] = {}
for m, nm, role in ch["members"]:
    segs.setdefault(_seg(role), []).append((m, nm, role))
seg_sorted = sorted(segs.keys(), key=lambda s: _SEG_ORDER.get(s, 9))

_SEG_ICON = {"上游": "⛏️", "原料": "⛏️", "製程": "🏭", "中游": "🏭", "設備": "🏭",
             "檢測": "🔬", "下游": "📦", "終端": "📦", "外圍": "🧱", "平行": "🧱"}


def _grad(mm):
    if mm is None:
        return "linear-gradient(145deg,#39455a,#2b3648)", "#c9d4e3"
    if mm >= 20:
        return "linear-gradient(145deg,#c62828,#8e1f1a)", "#fff"
    if mm >= 5:
        return "linear-gradient(145deg,#e5544a,#b93a31)", "#fff"
    if mm >= -5:
        return "linear-gradient(145deg,#4a5568,#39455a)", "#e6edf3"
    return "linear-gradient(145deg,#2e8b57,#1f6a41)", "#fff"


_html = ["""<style>
.cwrap{display:flex;align-items:stretch;gap:0;overflow-x:auto;padding:10px 2px 16px}
.cseg{background:rgba(255,255,255,.03);border:1px solid #26303f;border-radius:18px;
  padding:14px 12px 12px;min-width:190px;flex:1}
.cseglab{color:#8b98a8;font-size:.82rem;letter-spacing:3px;text-align:center;
  margin-bottom:10px;font-weight:700}
.cnode{border-radius:14px;padding:12px 10px;margin:10px 0;text-align:center;
  box-shadow:0 6px 16px rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.10)}
.cname{font-size:1.02rem;font-weight:800;letter-spacing:.5px}
.crole{font-size:.74rem;opacity:.85;margin-top:3px}
.cmom{display:inline-block;margin-top:7px;background:rgba(0,0,0,.28);
  border-radius:999px;padding:2px 12px;font-size:.82rem;font-weight:800;
  font-family:'Share Tech Mono',monospace}
.carrow{display:flex;align-items:center;color:#5a7a9f;font-size:1.7rem;
  font-weight:900;padding:0 6px}
</style><div class="cwrap">"""]
for i, s in enumerate(seg_sorted):
    if i:
        _html.append('<div class="carrow">➜</div>')
    _html.append(f'<div class="cseg"><div class="cseglab">{_SEG_ICON.get(s, "🔹")} {s}</div>')
    for m, nm, role in segs[s]:
        mm = moms.get(m)
        bg, fg = _grad(mm)
        mtxt = f"20日 {mm:+.0f}%" if mm is not None else "20日 —"
        _html.append(
            f'<div class="cnode" style="background:{bg};color:{fg}">'
            f'<div class="cname">{nm} <span style="opacity:.8">{m}</span></div>'
            f'<div class="crole">{role.split("|")[-1]}</div>'
            f'<div class="cmom">{mtxt}</div></div>')
    _html.append("</div>")
_html.append("</div>")
st.markdown("".join(_html), unsafe_allow_html=True)
st.caption("節點色=20日動能:深紅≥20%/紅≥5%/灰盤整/綠下跌。**紅的已在跑,灰綠的就是「還沒動的下一棒」候選**——先過九宮格看獲利純度,再過體檢卡。")

# ── 鏈上明細表 ──
rv = _sc.relay_view(ch["members"][0][0])
rv = rv[rv["鏈"] == sel].drop(columns=["鏈", "本檔"])
st.dataframe(rv, hide_index=True, width="stretch")
c1, c2 = st.columns(2)
with c1:
    st.page_link("pages/29_財務九宮格.py", label="🔲 比獲利純度(九宮格)")
with c2:
    st.page_link("pages/27_個股戰情室.py", label="🎯 個股戰情室")

# ── ⛓️ 每日供應鏈發想(思考題的家) ──
st.markdown("---")
st.markdown("### 💡 每日供應鏈發想(系統出題,你來想「第二個大甲」)")
_dp = ROOT / "data" / "supply_chain_drafts.json"
if _dp.exists():
    try:
        drafts = json.loads(_dp.read_text(encoding="utf-8"))
    except Exception:
        drafts = []
    if drafts:
        import analyst_report as _ar
        for d in reversed(drafts[-7:]):          # 近7題
            with st.expander(f"{d['date']}|主角:{d['subject']}",
                             expanded=(d is drafts[-1])):
                try:
                    st.markdown(_ar.read_article(d["article"]))
                except Exception:
                    st.info("文章檔不存在(可能被清理)。")
        st.caption("發想=假設。查證成立→把鏈寫進 data/supply_chain.json,魚骨圖與地圖接力警示就會開始盯它。")
    else:
        st.info("尚無發想紀錄——run_daily 每天自動出一題(需引擎)。")
else:
    st.info("尚無發想紀錄——run_daily 每天自動出一題(需引擎)。")

st.caption(f"<span style='color:{MUTED}'>魚骨圖只畫「查證過」的鏈;產業很大,一條一條建,"
           f"每深挖一檔就把它的上下游寫進鏈譜——這頁會越用越厚。</span>", unsafe_allow_html=True)

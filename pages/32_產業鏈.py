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

# ── 魚骨圖(懶人包引擎渲染 PNG;動能變了才重畫) ──
import json as _json_cm


@st.cache_data(show_spinner="渲染鏈圖(懶人包引擎)…")
def _chain_png(chain_name: str, mom_key: str) -> str:
    import importlib
    import infographic
    infographic = importlib.reload(infographic)
    ch2 = next(c for c in _sc.load() if c["chain"] == chain_name)
    moms2 = {m[0]: _sc._mom(m[0]) for m in ch2["members"]}
    out = ROOT / "data" / "research_articles" / "img" /         f"_chain_{abs(hash(chain_name)) % 99999}.png"
    infographic.make_chain_png(ch2, moms2, out)
    return str(out)


moms = {m[0]: _sc._mom(m[0]) for m in ch["members"]}
_mkey = _json_cm.dumps({k: round(v, 1) if v is not None else None
                        for k, v in sorted(moms.items())})
try:
    st.image(_chain_png(sel, _mkey), width="stretch")
except Exception as _e:
    st.warning(f"鏈圖渲染失敗(雲端無瀏覽器屬正常,退回表格):{_e}")
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

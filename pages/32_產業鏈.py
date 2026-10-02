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

# ── 🧬 技術拆解圖:問題→解法→產品→公司(2026-10-02)──────────────
# 資料:data/tech_maps/*.json(nodes 三欄+edges+公司對應;✓查證/?假設,直接改檔即可)
st.markdown("---")
st.markdown("### 🧬 技術拆解圖|問題 → 解法 → 產品 → 公司")
_TM_DIR = ROOT / "data" / "tech_maps"
_tms = sorted(_TM_DIR.glob("*.json")) if _TM_DIR.exists() else []
if not _tms:
    st.info("尚無拆解圖——把產業技術文丟給系統即可建圖(data/tech_maps/*.json)。")
else:
    import json as _tmj
    import streamlit.components.v1 as _tmc
    _opts = {}
    for _p in _tms:
        try:
            _opts[_tmj.loads(_p.read_text(encoding="utf-8")).get("title", _p.stem)] = _p
        except Exception:
            continue
    _sel = st.selectbox("選一張拆解圖", list(_opts), key="tm_sel")
    _d = _tmj.loads(_opts[_sel].read_text(encoding="utf-8"))
    if _d.get("note"):
        st.caption(_d["note"])
    _payload = _tmj.dumps(_d, ensure_ascii=False)
    _html = """
<style>
 body{margin:0;background:#0e1117;font-family:'Microsoft JhengHei',sans-serif}
 .wrap3{display:grid;grid-template-columns:1fr 1fr 1.35fr;gap:26px;padding:10px 6px}
 .colh{color:#8b94a7;font-size:12px;margin-bottom:2px}
 .colh b{display:block;color:#e6e9f0;font-size:15px;margin-top:2px}
 .nd{border:1.5px solid #2a3040;border-radius:10px;padding:7px 11px;margin:7px 0;
     color:#55607a;font-size:13.5px;cursor:pointer;background:#141926;transition:.15s}
 .nd .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#394052;
     margin-right:7px;vertical-align:1px}
 .nd.on{color:#eef1f8;border-color:#5b8def;background:#182036;box-shadow:0 0 10px #5b8def33}
 .nd.on .dot{background:#5b8def}
 .nd.src{border-color:#e06c5a;box-shadow:0 0 12px #e06c5a44}
 .nd.src .dot{background:#e06c5a}
 .chips{margin-top:5px}
 .chip{display:inline-block;font-size:11px;border-radius:6px;padding:1px 7px;margin:2px 3px 0 0;
     border:1px solid #2a3040;color:#4a5468;background:#10141f}
 .nd.on .chip{color:#cdd6e6}
 .nd.on .chip.v{border-color:#3f8f5f;color:#7fd3a0}
 .nd.on .chip.q{border-color:#8f7a3f;color:#e0c070}
 .hint{color:#59627a;font-size:12px;padding:4px 6px}
</style>
<div class="hint">點任一節點 → 亮出它的上游問題與下游產品/公司;✓綠=查證過,?黃=假設待查</div>
<div class="wrap3" id="map"></div>
<script>
const D = __DATA__;
const IN = {}, OUT = {};
D.edges.forEach(([a,b]) => {(OUT[a]=OUT[a]||[]).push(b);(IN[b]=IN[b]||[]).push(a);});
function reach(id, adj){const s=new Set(), q=[id];while(q.length){const x=q.pop();
  (adj[x]||[]).forEach(y=>{if(!s.has(y)){s.add(y);q.push(y);}});}return s;}
const map=document.getElementById('map');
const colDivs=D.cols.map((c,i)=>{const d=document.createElement('div');
  const [a,b]=c.split('|');d.innerHTML=`<div class="colh">${a}<b>${b||''}</b></div>`;
  map.appendChild(d);return d;});
const els={};
Object.entries(D.nodes).forEach(([id,n])=>{
  const e=document.createElement('div');e.className='nd';e.id=id;
  let chips='';
  (n.companies||[]).forEach(([c,nm,role,fl])=>{
    chips+=`<span class="chip ${fl==='✓'?'v':'q'}">${nm} ${c}·${role}${fl==='?'?' ?':''}</span>`;});
  e.innerHTML=`<span class="dot"></span>${n.label}`+(chips?`<div class="chips">${chips}</div>`:'');
  e.onclick=()=>{
    document.querySelectorAll('.nd').forEach(x=>x.classList.remove('on','src'));
    const up=reach(id,IN), dn=reach(id,OUT);
    e.classList.add('on','src');
    up.forEach(x=>els[x]&&els[x].classList.add('on'));
    dn.forEach(x=>els[x]&&els[x].classList.add('on'));
  };
  els[id]=e;colDivs[n.col].appendChild(e);
});
</script>"""
    _tmc.html(_html.replace("__DATA__", _payload), height=780, scrolling=True)
    st.caption("建新圖:把技術文/報告丟給系統 → 引擎拆「問題/解法/產品」草稿 → 公司對應逐一查證後入檔。")

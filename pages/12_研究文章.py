"""
頁面12:研究文章(自產報告的網站式閱讀頁)
================================================
頁13產生的報告會自動發佈到這裡——像逛研究網站一樣:
左側文章清單(標題/個股/日期),右側閱讀版面。
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_theme import page_header, inject_css, MUTED, CYAN

st.set_page_config(page_title="研究文章", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("研究文章", "RESEARCH LIBRARY", "📰")

import importlib
import analyst_report as _ar
if not hasattr(_ar, "list_articles"):
    _ar = importlib.reload(_ar)

arts = _ar.list_articles()
if not arts:
    st.info("還沒有文章——到「🧾 個股法人報告」頁產生報告,會自動發佈到這裡。")
    st.stop()

# ── 分類瀏覽:晨報 / 各族群(批次報告) / 個股報告 ──
try:
    from theme_groups import THEME_GROUPS
    _tg = set(THEME_GROUPS)
except Exception:
    _tg = set()


def _cat(a: dict) -> str:
    if a.get("mode") == "晨報":
        return "🌅 晨報"
    if a.get("name") in _tg:
        return f"🧩 {a['name']}"
    return "🔬 個股"


_cats = ["全部"]
for a in arts:                                  # 依出現順序去重
    c = _cat(a)
    if c not in _cats:
        _cats.append(c)
_sel = st.segmented_control("分類", _cats, default="全部", key="lib_cat")
if _sel and _sel != "全部":
    arts = [a for a in arts if _cat(a) == _sel]
    if not arts:
        st.info("此分類目前沒有文章")
        st.stop()

# 閱讀版面 CSS(文章寬度/字距,像網站)
st.markdown("""<style>
.article-body {max-width: 860px; margin: 0 auto; line-height: 1.9; font-size: 16px;}
.article-body h1 {font-size: 26px; line-height: 1.4; margin-bottom: 4px;}
.article-body h2 {font-size: 20px; margin-top: 28px; border-left: 4px solid #00E5FF;
                  padding-left: 10px;}
.article-body table {font-size: 14px;}
.article-meta {max-width: 860px; margin: 0 auto; color: #8b949e; font-size: 13px;}
</style>""", unsafe_allow_html=True)

left, right = st.columns([1.1, 3])

with left:
    st.markdown("**文章列表**")
    # 三層樹:族群 → 成分股 → 文章(晨報/非族群個股各自成節點)
    code2grp = {}
    try:
        from theme_groups import THEME_GROUPS as _TGM
        for g, cs in _TGM.items():
            for c in cs:
                code2grp.setdefault(c, g)     # 一檔多族群時取第一個
    except Exception:
        pass

    tree: dict[str, dict[str, list[dict]]] = {}
    for a in arts:
        if a.get("mode") == "晨報":
            node, sub = "🌅 晨報", ""
        elif a.get("name") in _tg:
            node, sub = f"🧩 {a['name']}", "📊 族群總覽"
        elif a.get("code") in code2grp:
            node, sub = f"🧩 {code2grp[a['code']]}", f"{a['code']} {a['name']}"
        else:
            node, sub = "🔬 其他個股", f"{a['code']} {a['name']}"
        tree.setdefault(node, {}).setdefault(sub, []).append(a)

    valid_files = {a["file"] for a in arts}
    if st.session_state.get("lib_file") not in valid_files:
        st.session_state["lib_file"] = arts[0]["file"]

    for node, subs in tree.items():
        n_arts = sum(len(v) for v in subs.values())
        cur_in = any(a["file"] == st.session_state["lib_file"]
                     for v in subs.values() for a in v)
        with st.expander(f"{node}（{n_arts}）", expanded=cur_in or len(tree) <= 2):
            for sub, items in subs.items():
                if sub:
                    st.markdown(f"<div style='color:#8b949e;font-size:12px;"
                                f"margin:6px 0 2px 2px'>▾ {sub}</div>",
                                unsafe_allow_html=True)
                for a in items:
                    cur = a["file"] == st.session_state["lib_file"]
                    lbl = f"{'▸ ' if cur else ''}{a['date'][:10]}｜{a['mode']}"
                    if st.button(lbl, key=f"lib_{a['file']}",
                                 type="primary" if cur else "secondary",
                                 width="stretch"):
                        st.session_state["lib_file"] = a["file"]
                        st.rerun()
    meta = next(a for a in arts if a["file"] == st.session_state["lib_file"])
    st.caption(f"共 {len(arts)} 篇")
    if st.button("🗑 刪除這篇", key="lib_del"):
        try:
            (_ar.ART_DIR / meta["file"]).unlink()
            st.session_state.pop("lib_file", None)
            st.rerun()
        except Exception:
            st.error("刪除失敗")

with right:
    body = _ar.read_article(meta["file"])
    st.markdown(f"<div class='article-meta'>📅 {meta['date']}　·　{meta['code']} "
                f"{meta['name']}　·　{meta['mode']}模式</div>", unsafe_allow_html=True)
    st.markdown("<div class='article-body'>", unsafe_allow_html=True)
    st.markdown(body)
    st.markdown("</div>", unsafe_allow_html=True)
    st.download_button("⬇️ 下載 Markdown", body.encode("utf-8"),
                       file_name=meta["file"], mime="text/markdown", key="lib_dl")

"""
pages/33_財經報.py — 財經報專刊閱讀頁(一期一檔 HTML,報紙級排版)
=================================================================
期刊在 data/papers/*.html(newspaper.py 產出);此頁選期→內嵌渲染。
"""
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from ui_theme import inject_css, page_header

st.set_page_config(page_title="財經報", page_icon="🗞️", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("財經報專刊", "THE PAPER", "🗞️")

# ── 🏆 研究名單總排名(2026-10-23「我們找那麼多,應該也要有排名」)──
with st.expander("🏆 研究名單總排名(覆蓋標的·每日重算)", expanded=False):
    try:
        import pandas as _rpd
        from pathlib import Path as _RP
        _rk = _rpd.read_csv(_RP(__file__).parent.parent / "data" / "_research_rank.csv",
                            dtype={"代碼": str})
        _cols = ["排名", "代碼", "名稱", "總分", "營收分", "獲利分", "籌碼分", "位置分",
                 "扣分", "營收YoY3", "毛利率", "外資天", "大戶4週Δ", "距年高%", "融資%"]
        st.dataframe(_rk[[c for c in _cols if c in _rk.columns]],
                     hide_index=True, use_container_width=True, height=560)
        st.caption("總分=營收30%+獲利30%+籌碼25%+位置15%-家規扣分(處置10/爆量8/融資≥30% 8/迴轉警5);"
                   "業外佔比重的獲利分腰斬。排名是體檢不是買單——高分看續航,低分看原因。")
        st.markdown("##### 🤫 還沒發動版(低檔+整理+吃貨;位置是資格不是分數)")
        try:
            _qk = _rpd.read_csv(_RP(__file__).parent.parent / "data" / "_research_rank_quiet.csv",
                                dtype={"代碼": str})
            _qc = ["潛伏排名", "代碼", "名稱", "潛伏分", "籌碼分", "營收分", "獲利分",
                   "距年高%", "60日%", "外資天", "大戶4週Δ", "融資%"]
            st.dataframe(_qk[[c for c in _qc if c in _qk.columns]],
                         hide_index=True, use_container_width=True)
            st.caption("資格:距年高≤-15%+站60MA+60日<25%+無爆量/處置;排序=籌碼40%+營收30%+獲利30%。"
                       "家規:觀察名單零部位,進場等它自己出第一根後回測不破;融資%高的列大跌日禁接。")
        except Exception:
            st.caption("潛伏榜尚未生成。")
        if st.button("🔄 立即重算(約2分鐘)"):
            import research_rank
            with st.spinner("全名單重算中…"):
                research_rank.build()
            st.rerun()
    except Exception as _e:
        st.info(f"排名表尚未生成——run_daily 會自動產生({_e})")

import newspaper as _np
from symbols import resolve as _rs

issues = _np.list_issues()
if not issues:
    st.info("尚無期刊——素材(法人報告/法說/筆記)交給系統即可組版。")
    st.stop()

# 海報歸海報、報紙歸報紙(2026-11-16):檔名帶「海報」的是一屏總覽,其餘是長文期刊;「總覽」是海報目錄
_is_poster = lambda i: "海報" in i["code"] or i["code"] == "總覽"
_posters = [i for i in issues if _is_poster(i)]
_papers = [i for i in issues if not _is_poster(i)]
_posters.sort(key=lambda i: (i["code"] != "總覽", -int(i["date"]) if str(i["date"]).isdigit() else 0, i["code"]))   # 目錄置頂,其餘新到舊
_kind = st.radio("類別", [f"🖼 海報({len(_posters)})", f"📰 報紙期刊({len(_papers)})"],
                 horizontal=True, key="paper_kind")
issues = _posters if _kind.startswith("🖼") else _papers
if not issues:
    st.info("這一類目前沒有內容。")
    st.stop()

labels = []
for i in issues:
    _c = i["code"].replace("海報", "")
    _d = f"{i['date'][:4]}/{i['date'][4:6]}/{i['date'][6:]}"
    if i["code"] == "總覽":
        labels.append(f"📋 海報總覽(全部海報目錄)|{_d}")
    else:
        nm = (_rs(_c)[1] or _c) if _c[:4].isdigit() else _c   # 族群名(如「資安」)不查股名,否則會被模糊比對成個股
        if nm != _c:
            labels.append(f"{nm} {_c}|{_d}")
        elif "海報" in i["code"] and not _c[:4].isdigit():
            labels.append(f"🗂 {_c}(族群)|{_d}")                      # 族群海報沒有代號
        else:
            labels.append(f"{_c}|{_d}")                               # 專題報紙(CPO、ASIC…)或查不到股名的代號
idx = st.selectbox("選期", range(len(issues)), format_func=lambda k: labels[k], key=f"paper_idx_{_kind[:1]}")
p = Path(issues[idx]["path"])
html = p.read_text(encoding="utf-8")


def _with_links(doc: str) -> str:
    """讓刊物裡的相對連結(./xxx.html)在 app 裡點得開。
    components.html 是 srcdoc iframe,相對連結會被瀏覽器當成 app 自己的網址 → 「Page not found」(2026-11-16 使用者截圖)。
    做法:把 data/papers 每一份的內容一起塞進去,點連結時在同一格裡換成那一份,上方給「回總覽」。"""
    import json as _json
    docs = {f.name: f.read_text(encoding="utf-8", errors="ignore")
            for f in p.parent.glob("*.html") if f.name != p.name}
    blob = _json.dumps(docs, ensure_ascii=False).replace("</", "<\\/")
    return ('<div id="_pv_bar" style="display:none;position:sticky;top:0;z-index:9;background:#0d2b52;color:#fff;'
            'padding:9px 14px;font:15px sans-serif"><a href="#" id="_pv_back" style="color:#ffd35c;font-weight:700;'
            'text-decoration:none">← 回海報總覽</a><span id="_pv_ttl" style="margin-left:14px;opacity:.85"></span></div>'
            '<iframe id="_pv_view" style="display:none;width:100%;height:1330px;border:0"></iframe>'
            f'<div id="_pv_home">{doc}</div>'
            f'<script>const DOCS={blob};const $=i=>document.getElementById(i);'
            'function pvShow(n){$("_pv_view").srcdoc=DOCS[n];$("_pv_ttl").textContent=n.replace(".html","");'
            '$("_pv_home").style.display="none";$("_pv_view").style.display="block";$("_pv_bar").style.display="block";window.scrollTo(0,0);}'
            '$("_pv_back").addEventListener("click",e=>{e.preventDefault();$("_pv_view").style.display="none";'
            '$("_pv_bar").style.display="none";$("_pv_home").style.display="block";});'
            'document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("a");'
            'if(!a||a.id==="_pv_back")return;const h=a.getAttribute("href")||"";if(!h.startsWith("./"))return;'
            'e.preventDefault();const n=decodeURIComponent(h.slice(2));'
            'if(DOCS[n])pvShow(n);else alert("找不到 "+n);});</script>')


components.html(_with_links(html) if 'href="./' in html else html, height=1400, scrolling=True)
st.download_button("⬇️ 下載本期 HTML(可傳 LINE/開瀏覽器)", html.encode("utf-8"),
                   file_name=p.name, mime="text/html")
st.caption("素材=法人報告/法說/使用者筆記;本刊為研究筆記非投資建議。")

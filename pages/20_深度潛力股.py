"""頁20 — 深度潛力股(「發掘潛力股」風格長文)。"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="深度潛力股", page_icon="💎", layout="wide")

import deep_report as _dr
_dr = importlib.reload(_dr)          # 迭代中模組:無條件重載

st.title("💎 深度潛力股")
st.caption("「邏輯投資·發掘潛力股」風格的個股長文:風口切入 → 財務矛盾統一 → 籌碼 → 情境與兌現訊號。"
           "所有數字出自系統管線;非投資建議。")

arts = _dr.list_deep()
if not arts:
    st.info("尚無報告。用下方「產生新報告」開第一篇。")
else:
    labels = [f"{a['name'] or a['code']} | {a['title'][:60]}({a['date'][:10]})" for a in arts]
    idx = st.selectbox("選擇報告", range(len(arts)), format_func=lambda i: labels[i])
    a = arts[idx]

    # 即時數據卡(讀報告當下的最新座標,和文章成文時點對照)
    ps = _dr._price_stats(a["code"]) if a["code"] else {}
    bh = _dr._bigholder_series(a["code"], weeks=2) if a["code"] else pd.DataFrame()
    if ps:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("現價", f"{ps['close']:.1f}", f"{ps['date']}", delta_color="off")
        c2.metric("距一年高", f"{ps['off_high']:+.1f}%")
        c3.metric("一年區間", f"{ps['lo252']:.0f}~{ps['hi252']:.0f}")
        if not bh.empty:
            last = bh.iloc[-1]
            delta = (f"{last['大戶%'] - bh.iloc[0]['大戶%']:+.2f}pp" if len(bh) > 1 else None)
            c4.metric("大戶>400張", f"{last['大戶%']:.1f}%", delta)
        st.caption("↑ 即時座標(每日更新);內文數字為成文時點。")

    st.markdown("---")
    st.markdown(_dr.read_deep(a["fname"]))

st.markdown("---")
with st.expander("✍️ 產生新報告(引擎)"):
    st.caption("素材=系統月營收/季報/EPS情境/籌碼/法說筆記/產品組合;素材沒有的內容寧留白不編造。")
    code = st.text_input("股票代號", key="deep_code")
    extra = st.text_area("補充素材(法說重點/產能/產品佔比等,選填)", key="deep_extra", height=80)
    if st.button("產生", type="primary") and code.strip():
        import llm
        from apikey import get_key
        if not (llm._cli_path() or get_key()):
            st.error(f"引擎不可用:{llm.fail_reason()}")
        else:
            with st.spinner("寫作中(約1-2分鐘)…"):
                txt = _dr.generate_deep(code.strip(), extra.strip())
            if txt.startswith("⚠️"):
                st.error(txt)
            else:
                import analyst_report as ar
                dig_name = ""
                try:
                    sl = pd.read_csv(Path(__file__).parent.parent / "data" / "stock_list.csv",
                                     encoding="utf-8-sig", dtype=str)
                    hit = sl[sl["code"] == code.strip()]
                    dig_name = hit["name"].iloc[0] if not hit.empty else ""
                except Exception:
                    pass
                fn = _dr.save_deep(code.strip(), dig_name, txt)
                msg = _dr.git_publish_deep(fn)
                st.success(f"已存檔 {fn}({msg})。重新整理頁面即可看到。")

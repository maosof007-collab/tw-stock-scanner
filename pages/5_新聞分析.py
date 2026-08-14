"""
pages/5_新聞分析.py — 新聞情緒 + 法人報告 + 信心分數
"""
import sys, json, os
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── 統一設計系統（科幻 HUD）───────────────
from ui_theme import (DARK, CARD, BORDER, TEXT, MUTED, GREEN, RED, GOLD,
                      BLUE, PURPLE, CYAN, inject_css, page_header)

NEWS_DIR    = ROOT / "data" / "news"
REPORTS_DIR = ROOT / "data" / "reports"
SCAN_DIR    = ROOT / "scan_results"

st.set_page_config(page_title="新聞分析", page_icon="📰", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()


# ─────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────
@st.cache_data(ttl=60)
def load_sentiment():
    csvs = sorted(NEWS_DIR.glob("sentiment_*.csv"), reverse=True)
    if not csvs:
        return pd.DataFrame(), ""
    df = pd.read_csv(csvs[0], encoding="utf-8-sig")
    date_str = csvs[0].stem.replace("sentiment_", "")
    return df, date_str

@st.cache_data(ttl=60)
def load_confidence():
    csvs = sorted(SCAN_DIR.glob("confidence_*.csv"), reverse=True)
    if not csvs:
        return pd.DataFrame(), ""
    df = pd.read_csv(csvs[0], encoding="utf-8-sig")
    date_str = csvs[0].stem.replace("confidence_", "")
    return df, date_str

@st.cache_data(ttl=300)
def load_reports():
    jsons = sorted(REPORTS_DIR.glob("parsed_*.json"), reverse=True)
    if not jsons:
        return []
    with open(jsons[0], encoding="utf-8") as f:
        return json.load(f)

def check_api_key() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        cfg = ROOT / "config.json"
        if cfg.exists():
            try:
                key = json.loads(cfg.read_text("utf-8")).get("anthropic_api_key","")
            except: pass
    return bool(key)


# ─────────────────────────────────────────
# 主畫面
# ─────────────────────────────────────────
page_header("新聞情緒 × 法人報告 × 信心分數", "NEWS INTEL · CONFIDENCE", "📰")

# API Key 狀態（統一經 apikey：env → config.json → Streamlit secrets）
from apikey import key_status, test_key
_ks = key_status()
has_key = _ks["found"]
if has_key:
    kc1, kc2 = st.columns([4, 1.2])
    kc1.caption(f"🔑 API Key：**已設定**（{_ks['source']}，{_ks['masked']}）— "
                f"新聞情緒 / 日報潤稿 / 文章解讀 / 法人報告 已升級 Claude 解析")
    if kc2.button("🧪 測試連線", key="key_test"):
        ok, msg = test_key()
        (st.success if ok else st.error)(msg)
else:
    from llm import engine_status

    @st.cache_data(ttl=600, show_spinner="檢查可用的 Claude 引擎…")
    def _engine():
        return engine_status()

    es = _engine()
    if es["engine"] == "cli":
        st.caption(f"🔑 無 API 金鑰，但偵測到 **{es['detail']}** ✅ — "
                   f"日報潤稿 / 文章解讀 / 個股筆記 已可用（走本機 Claude 訂閱，免 API 付款）")
        has_key = True    # 讓下游功能視同可用
    else:
        def _is_cloud():
            try:
                from auto_refresh import _pack_mode
                return _pack_mode()
            except Exception:
                return False
        if _is_cloud():
            st.info(
                "☁️ **雲端顯示模式**：情緒與信心分數由**本機每天自動產生並同步**到這裡"
                "（看下方各分頁的「最後計算」日期）——瀏覽不需要任何金鑰。\n\n"
                "想在雲端「即時重算」才需要在 App Secrets 設 `ANTHROPIC_API_KEY`。"
            )
        else:
            st.warning(
                f"⚠️ 目前無可用 Claude 引擎（{es['detail']}）——相關功能為離線退化模式。\n\n"
                "兩條升級路線擇一：\n"
                "1. **本機免付款**：終端機執行 `claude` → 輸入 `/login` 登入你的 Claude 訂閱即可\n"
                "2. **API 金鑰**：`config.json` 加 `\"anthropic_api_key\": \"sk-ant-...\"`"
            )
            if st.button("🔁 重新檢查引擎", key="engine_recheck"):
                _engine.clear()
                st.rerun()

# 分頁
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 信心分數排行", "📰 新聞情緒", "📄 法人報告", "🏭 產業趨勢雷達"])
st.caption("💡 個股相關研究(文章解讀/筆記/報告)已整併到「🧾 個股法人報告」頁——這頁專注市場與產業消息面。")


# ══════════════════════════════════════════
# Tab 1：信心分數排行
# ══════════════════════════════════════════
with tab1:
    conf_df, conf_date = load_confidence()
    sent_df, sent_date = load_sentiment()

    col_info, col_run = st.columns([4, 2])
    with col_info:
        if conf_date:
            fmt = f"{conf_date[:4]}-{conf_date[4:6]}-{conf_date[6:]}"
            st.markdown(f"**最後計算：** `{fmt}`")
        else:
            st.info("尚未計算信心分數，請點擊右側按鈕")

    with col_run:
        if st.button("🧮 重新計算信心分數", type="primary",
                     width="stretch", disabled=not has_key):
            with st.spinner("計算中..."):
                import subprocess
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "confidence_score.py")],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
            load_confidence.clear()
            st.rerun()

    if not conf_df.empty:
        # 補中文股名 + 同股去重(同檔可被多個策略選中,排行/散佈只留最高分那筆;明細表仍列全部)
        try:
            _sl = pd.read_csv(ROOT / "data" / "stock_list.csv",
                              encoding="utf-8-sig", dtype=str)
            _nm = dict(zip(_sl["ticker"], _sl["name"]))
        except Exception:
            _nm = {}
        if "代碼" in conf_df.columns:
            conf_df["名稱"] = conf_df["代碼"].map(_nm).fillna("")
            conf_uni = (conf_df.sort_values("confidence", ascending=False)
                        .drop_duplicates(subset=["代碼"]).copy())
            # 一檔一列:同股被多策略選中 → 合併成「入選策略」欄,分數取最高
            if "策略" in conf_df.columns:
                _ag = (conf_df.groupby("代碼")["策略"].agg(
                    lambda s: "、".join(dict.fromkeys(s.astype(str)))))
                _cnt = conf_df.groupby("代碼")["策略"].nunique()
                conf_uni["入選策略"] = conf_uni["代碼"].map(_ag)
                conf_uni["策略數"] = conf_uni["代碼"].map(_cnt)
        else:
            conf_uni = conf_df

        st.caption("📌 **這份名單怎麼來的**:母體=昨日全部策略掃描出的訊號股(非新聞挑的),"
                   "每檔評分=技術面40%(訊號等級/RS/風險)+新聞情緒30%+法人報告30%;"
                   "沒有相關新聞或報告時該層以中性50計。同股被多策略選中只列一次"
                   "(分數取最高,「入選策略」欄看全部);策略數≥2=多策略共振,可信度加分。")
        # KPI(檔數口徑,不重複計)
        st.markdown("---")
        strong = (conf_uni["confidence"] >= 80).sum() if "confidence" in conf_uni else 0
        bullish = (conf_uni["confidence"] >= 65).sum() if "confidence" in conf_uni else 0
        watch = (conf_uni["confidence"].between(50, 65)).sum() if "confidence" in conf_uni else 0
        avg_conf = conf_uni["confidence"].mean() if "confidence" in conf_uni else 0

        k1, k2, k3, k4 = st.columns(4)
        for col, label, val, cls in [
            (k1, "強力做多 ⭐⭐⭐", f"{strong}", "green"),
            (k2, "做多 ⭐⭐",      f"{bullish}", "blue"),
            (k3, "觀察 ⭐",       f"{watch}",  "gold"),
            (k4, "平均信心分",    f"{avg_conf:.1f}", ""),
        ]:
            with col:
                st.markdown(
                    f"""<div class="score-card">
                    <div class="score-label">{label}</div>
                    <div class="score-value {cls}">{val}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

        # 信心分數分布圖
        if "confidence" in conf_df.columns:
            col_chart, col_table = st.columns([1, 1])

            with col_chart:
                # 橫條圖：前15名(高分在上)
                top = conf_uni.head(15).copy().iloc[::-1]
                top["label"] = top.apply(
                    lambda r: f"{str(r.get('代碼','')).split('.')[0]} "
                              f"{str(r.get('名稱',''))[:6]}",
                    axis=1,
                )
                bar_colors = [
                    GREEN if v >= 80 else (BLUE if v >= 65 else (GOLD if v >= 50 else RED))
                    for v in top["confidence"]
                ]
                fig = go.Figure(go.Bar(
                    x=top["confidence"],
                    y=top["label"],
                    orientation="h",
                    marker=dict(color=bar_colors, opacity=0.9),
                    text=[f" {v:.0f}" for v in top["confidence"]],
                    textposition="outside",
                    textfont=dict(size=12, color=TEXT),
                    hovertemplate="<b>%{y}</b><br>信心分：%{x:.1f}<extra></extra>",
                ))
                fig.add_vline(x=65, line_dash="dash", line_color=GREEN,
                              line_width=1.5, opacity=0.6)
                fig.update_layout(
                    paper_bgcolor=DARK, plot_bgcolor=CARD,
                    font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
                    xaxis=dict(gridcolor=BORDER, range=[0, 105], title="信心分數"),
                    yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
                    height=max(380, len(top)*30+60),
                    margin=dict(l=10, r=60, t=20, b=30),
                    showlegend=False,
                    title=dict(text="信心分數 Top 15", font=dict(size=14, color=TEXT)),
                )
                st.plotly_chart(fig, width="stretch")

            with col_table:
                # 三維分數散佈
                plot_df = conf_uni[conf_uni["confidence"] >= 50].head(30)
                if not plot_df.empty and all(
                    c in plot_df for c in ["tech_score","news_score","report_score"]
                ):
                    _sc_txt = (plot_df.get("代碼", plot_df.index).astype(str)
                               .str.split(".").str[0]
                               + " " + plot_df.get("名稱", "").astype(str).str[:4])
                    fig2 = go.Figure(go.Scatter(
                        x=plot_df["tech_score"],
                        y=plot_df["news_score"],
                        mode="markers+text",
                        text=_sc_txt,
                        textposition="top center",
                        textfont=dict(size=10, color=TEXT),
                        marker=dict(
                            size=plot_df["confidence"] / 5,
                            color=plot_df["confidence"],
                            colorscale=[[0, RED], [0.5, GOLD], [1, GREEN]],
                            cmin=40, cmax=100,
                            opacity=0.85,
                            showscale=True,
                            colorbar=dict(title="信心分", tickfont=dict(color=TEXT, size=11)),
                        ),
                        hovertemplate=(
                            "<b>%{text}</b><br>"
                            "技術:%{x:.0f}  新聞:%{y:.0f}<br>"
                            "信心分:%{marker.color:.0f}<extra></extra>"
                        ),
                    ))
                    fig2.update_layout(
                        paper_bgcolor=DARK, plot_bgcolor=CARD,
                        font=dict(family="Microsoft JhengHei, Arial", size=12, color=TEXT),
                        xaxis=dict(gridcolor=BORDER, title="技術面分數", range=[30,105]),
                        yaxis=dict(gridcolor=BORDER, title="新聞情緒分數", range=[20,90]),
                        height=420,
                        title=dict(text="三維信心散佈圖", font=dict(size=14, color=TEXT)),
                        margin=dict(l=60, r=20, t=50, b=50),
                    )
                    st.plotly_chart(fig2, width="stretch")

        # 明細表(一檔一列;要看每個策略的個別紀錄到「訊號回查」頁)
        st.markdown("---")
        st.markdown("### 📋 信心分數明細(一檔一列)")
        show_cols = [c for c in [
            "代碼","名稱","入選策略","策略數","訊號等級","進場時機","收盤","停損",
            "confidence","signal_type","tech_score","news_score","report_score"
        ] if c in conf_uni.columns]

        def color_conf(val):
            if isinstance(val, float):
                if val >= 80: return f"color:{GREEN};font-weight:700"
                if val >= 65: return f"color:{GREEN}"
                if val >= 50: return f"color:{GOLD}"
                return f"color:{MUTED}"
            return ""

        st.dataframe(
            conf_uni[show_cols].style
                .map(color_conf, subset=["confidence"] if "confidence" in show_cols else [])
                .format({
                    "收盤":"{:.1f}","停損":"{:.1f}",
                    "confidence":"{:.1f}","tech_score":"{:.1f}",
                    "news_score":"{:.1f}","report_score":"{:.1f}",
                }),
            width="stretch", height=500,
        )

        csv = conf_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ 下載信心分數 CSV", csv,
                           file_name=f"confidence_{conf_date}.csv", mime="text/csv")


# ══════════════════════════════════════════
# Tab 2：新聞情緒
# ══════════════════════════════════════════
with tab2:
    sent_df, sent_date = load_sentiment()

    col_a, col_b = st.columns([4, 2])
    with col_a:
        if sent_date:
            fmt = f"{sent_date[:4]}-{sent_date[4:6]}-{sent_date[6:]}"
            st.markdown(f"**分析日期：** `{fmt}`　共 {len(sent_df)} 則")
    with col_b:
        if st.button("🔄 抓取並分析今日新聞", type="primary",
                     width="stretch", disabled=not has_key):
            with st.spinner("抓取中（約1-2分鐘）..."):
                import subprocess
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "analyze_news.py")],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
            load_sentiment.clear()
            st.rerun()

    if not sent_df.empty:
        # 情緒概覽
        pos = (sent_df["score"] > 0.2).sum()
        neg = (sent_df["score"] < -0.2).sum()
        neu = len(sent_df) - pos - neg
        avg = float(sent_df["score"].mean())

        m1, m2, m3, m4 = st.columns(4)
        for col, label, val, cls in [
            (m1, "正面新聞", str(pos), "green"),
            (m2, "負面新聞", str(neg), "red"),
            (m3, "中性新聞", str(neu), ""),
            (m4, "市場情緒均分", f"{avg:+.3f}", "green" if avg > 0 else "red"),
        ]:
            with col:
                st.markdown(
                    f"""<div class="score-card">
                    <div class="score-label">{label}</div>
                    <div class="score-value {cls}">{val}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # 情緒分布圖
        c1, c2 = st.columns(2)
        with c1:
            fig_hist = go.Figure()
            pos_data = sent_df[sent_df["score"] > 0]["score"]
            neg_data = sent_df[sent_df["score"] < 0]["score"]
            fig_hist.add_trace(go.Histogram(x=pos_data, nbinsx=20, name="正面",
                                            marker_color=GREEN, opacity=0.75))
            fig_hist.add_trace(go.Histogram(x=neg_data, nbinsx=20, name="負面",
                                            marker_color=RED, opacity=0.75))
            fig_hist.add_vline(x=avg, line_dash="dash", line_color=GOLD,
                               annotation_text=f"均值{avg:+.2f}",
                               annotation_font=dict(color=GOLD))
            fig_hist.update_layout(
                paper_bgcolor=DARK, plot_bgcolor=CARD,
                font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
                xaxis=dict(gridcolor=BORDER, title="情緒分數"),
                yaxis=dict(gridcolor=BORDER, title="則數"),
                title=dict(text="情緒分數分布", font=dict(size=14, color=TEXT)),
                legend=dict(font=dict(color=TEXT), bgcolor=CARD),
                height=320, margin=dict(t=50, b=40, l=50, r=20),
            )
            st.plotly_chart(fig_hist, width="stretch")

        with c2:
            # 來源分布
            src_cnt = sent_df["source"].value_counts().head(8).reset_index()
            src_cnt.columns = ["source","count"]
            fig_src = px.bar(src_cnt, x="count", y="source", orientation="h",
                             color_discrete_sequence=[BLUE])
            fig_src.update_layout(
                paper_bgcolor=DARK, plot_bgcolor=CARD,
                font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
                xaxis=dict(gridcolor=BORDER),
                yaxis=dict(gridcolor=BORDER),
                title=dict(text="新聞來源分布", font=dict(size=14, color=TEXT)),
                showlegend=False,
                height=320, margin=dict(t=50, b=40, l=10, r=20),
            )
            st.plotly_chart(fig_src, width="stretch")

        # 新聞明細
        st.markdown("---")
        st.markdown("### 📋 新聞明細")

        # 過濾器
        fc1, fc2 = st.columns([2, 2])
        with fc1:
            sent_filter = st.multiselect("情緒篩選",
                ["positive","neutral","negative"], default=["positive","negative"])
        with fc2:
            impact_filter = st.multiselect("影響程度",
                ["high","medium","low"], default=["high","medium"])

        filtered = sent_df[
            sent_df["sentiment"].isin(sent_filter if sent_filter else ["positive","neutral","negative"]) &
            sent_df["impact"].isin(impact_filter if impact_filter else ["high","medium","low"])
        ].sort_values("score", ascending=False)

        def color_sentiment(val):
            if val == "positive": return f"color:{GREEN};font-weight:600"
            if val == "negative": return f"color:{RED};font-weight:600"
            return f"color:{MUTED}"

        show = [c for c in ["source","title","sentiment","score","impact","tickers","reason","published"]
                if c in filtered.columns]
        st.dataframe(
            filtered[show].style
                .map(color_sentiment, subset=["sentiment"])
                .format({"score":"{:+.3f}"}),
            width="stretch", height=500,
        )

    else:
        st.info("尚無新聞情緒資料。點擊「抓取並分析今日新聞」開始。")
        if not has_key:
            st.warning("需要設定 ANTHROPIC_API_KEY 才能使用情緒分析功能。")


# ══════════════════════════════════════════
# Tab 3：法人報告
# ══════════════════════════════════════════
with tab3:
    reports = load_reports()

    st.markdown("### 📄 上傳法人研究報告（PDF）")

    if not has_key:
        st.warning("需要設定 ANTHROPIC_API_KEY 才能解析法人報告。")
    else:
        uploaded = st.file_uploader(
            "將 PDF 拖曳至此（支援多檔）",
            type=["pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded and st.button("🔍 解析法人報告", type="primary"):
            # 儲存上傳的 PDF
            REPORTS_DIR.mkdir(exist_ok=True)
            pdf_paths = []
            for uf in uploaded:
                p = REPORTS_DIR / uf.name
                p.write_bytes(uf.read())
                pdf_paths.append(p)

            with st.spinner(f"解析 {len(pdf_paths)} 份報告中（使用 Claude + Files API）..."):
                try:
                    from parse_report import parse_reports
                    results = parse_reports(pdf_paths, cleanup=True)
                    load_reports.clear()
                    st.success(f"成功解析 {len(results)} 份報告！")
                    st.rerun()
                except Exception as e:
                    st.error(f"解析失敗：{e}")

    # 顯示已解析的報告
    if reports:
        st.markdown("---")
        st.markdown(f"### 已解析報告（{len(reports)} 份）")

        for r in reports:
            tickers = r.get("tickers") or []
            company = r.get("company_name") or ",".join(tickers)
            rating  = r.get("rating", "NR")
            upside  = r.get("upside_pct")
            tp      = r.get("target_price")

            rating_color = {
                "Buy": GREEN, "Outperform": GREEN,
                "Hold": GOLD,
                "Sell": RED,  "Underperform": RED,
            }.get(rating, MUTED)

            with st.expander(
                f"**{company}** [{','.join(tickers)}]  "
                f"評等：{rating}  {'目標價：' + str(tp) if tp else ''}  "
                f"{'上漲空間：' + str(upside) + '%' if upside else ''}",
                expanded=False,
            ):
                r1, r2 = st.columns(2)
                with r1:
                    st.markdown(f"**機構：** {r.get('institution','—')}")
                    st.markdown(f"**日期：** {r.get('report_date','—')}")
                    st.markdown(f"**摘要：** {r.get('summary','—')}")

                with r2:
                    eps = r.get("eps_estimates") or {}
                    if eps:
                        st.markdown("**EPS 預估：**")
                        for yr, val in eps.items():
                            st.markdown(f"  - {yr}：{val}")

                # 核心論點
                thesis = r.get("key_thesis") or []
                if thesis:
                    st.markdown("**核心論點：**")
                    for t in thesis:
                        st.markdown(f"  ✅ {t}")

                # 風險
                risks = r.get("risks") or []
                if risks:
                    st.markdown("**主要風險：**")
                    for risk in risks:
                        st.markdown(f"  ⚠️ {risk}")

                # 催化劑
                cats = r.get("catalysts") or []
                if cats:
                    st.markdown("**近期催化劑：**")
                    for c in cats:
                        st.markdown(f"  🎯 {c}")
    else:
        st.info("尚無解析的法人報告。上傳 PDF 即可開始。")


# ══════════════════════════════════════════
# Tab 4：產業趨勢雷達（消息面 × 資金面）
# ══════════════════════════════════════════
with tab4:
    from news_trend import build_sector_trend

    @st.cache_data(ttl=900, show_spinner="彙整產業新聞趨勢…")
    def _trend(win):
        return build_sector_trend(win=win)

    @st.cache_data(ttl=1800, show_spinner="計算 RRG 象限（首次約 15-25 秒）…")
    def _rrg_quadrant():
        from sector_rrg import build_rrg
        pts, _, _ = build_rrg()
        return dict(zip(pts["產業"], pts["象限"])) if not pts.empty else {}

    tc = st.columns([1, 1.4, 3])
    win = tc[0].selectbox("統計窗(日)", [7, 3, 14], index=0,
                          help="近N日新聞則數 vs 前N日 → 熱度動能")
    with tc[1]:
        if st.button("📡 立即掃產業新聞", help="逐產業抓 Google News（約 20-30 秒）"):
            with st.spinner("掃描 33 產業新聞中…"):
                from fetch_news import fetch_sector_news
                fetch_sector_news(days=max(win, 2))
            _trend.clear()
            st.rerun()

    trend, headlines, asof = _trend(win)
    if trend.empty:
        st.info("還沒有產業新聞資料——按上方「📡 立即掃產業新聞」抓一批，之後每日更新會自動累積。")
    else:
        quad = _rrg_quadrant()
        trend = trend.copy()
        trend["RRG象限"] = trend["產業"].map(quad).fillna("—")
        Q_ICON = {"領先": "🔴 領先", "改善": "🔵 改善", "弱化": "🟡 弱化", "落後": "🟣 落後", "—": "—"}
        trend["RRG象限"] = trend["RRG象限"].map(lambda q: Q_ICON.get(q, q))
        # 🔥 = 消息轉熱(熱度Δ>0 且情緒≥0) 且 資金面在改善/領先
        trend["🔥"] = [
            "🔥" if (r["熱度Δ%"] > 0 and r["情緒"] >= 0 and ("改善" in r["RRG象限"] or "領先" in r["RRG象限"]))
            else ""
            for _, r in trend.iterrows()
        ]
        st.caption(f"**消息面熱度 × 資金面位置**——🔥 = 新聞轉熱且 RRG 在改善/領先（趨勢起點候選）。"
                   f"情緒為標題詞典計分(-1~+1)。資料截至 **{str(asof)[:10]}**。")

        def _c_senti(v):
            return f"color:{GREEN}" if v > 0.1 else (f"color:{RED}" if v < -0.1 else f"color:{MUTED}")
        def _c_mom(v):
            return f"color:{GREEN}" if v > 0 else (f"color:{RED}" if v < 0 else "")
        st.dataframe(
            trend.style.map(_c_senti, subset=["情緒"]).map(_c_mom, subset=["熱度Δ%"])
                 .format({"熱度Δ%": "{:+.0f}%", "情緒": "{:+.2f}", "趨勢分": "{:+.2f}"}),
            width="stretch", height=420, hide_index=True)

        # 產業標題細看
        pick = st.selectbox("🔍 看某產業的新聞標題", trend["產業"].tolist())
        hs = headlines.get(pick)
        if hs is not None and not hs.empty:
            for _, h in hs.iterrows():
                icon = "🟢" if h["score"] > 0 else ("🔴" if h["score"] < 0 else "⚪")
                d = str(h["pub_date"])[:10]
                st.markdown(f"{icon} `{d}` [{h['title']}]({h['url']})　"
                            f"<span style='color:{MUTED};font-size:11px'>{h['source']}</span>",
                            unsafe_allow_html=True)

st.markdown(
    f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
    f"資料：{NEWS_DIR} | {REPORTS_DIR}</p>",
    unsafe_allow_html=True,
)

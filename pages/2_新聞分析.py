"""
pages/2_新聞分析.py — 新聞情緒 + 法人報告 + 信心分數
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

# ── 顏色 ─────────────────────────────
DARK   = "#0d1117"; CARD = "#161b22"; BORDER = "#30363d"
TEXT   = "#e6edf3"; MUTED = "#8b949e"
GREEN  = "#1D9E75"; RED = "#F85149"; GOLD = "#D29922"
BLUE   = "#58A6FF"; PURPLE = "#BC8CFF"

NEWS_DIR    = ROOT / "data" / "news"
REPORTS_DIR = ROOT / "data" / "reports"
SCAN_DIR    = ROOT / "scan_results"

st.set_page_config(page_title="新聞分析", page_icon="📰", layout="wide")

st.markdown(f"""
<style>
  body, .stApp {{ background-color:{DARK}; color:{TEXT}; }}
  .score-card {{
    background:{CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:14px 18px; text-align:center;
  }}
  .score-label {{ color:{MUTED}; font-size:12px; margin-bottom:4px; }}
  .score-value {{ font-size:26px; font-weight:700; }}
  .green {{ color:{GREEN}; }} .red {{ color:{RED}; }}
  .gold  {{ color:{GOLD};  }} .blue {{ color:{BLUE}; }}

  /* 上傳按鈕 */
  div[data-testid="stFileUploader"] {{
    background:{CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:12px;
  }}
</style>
""", unsafe_allow_html=True)


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
st.title("📰 新聞情緒 × 法人報告 × 信心分數")

# API Key 狀態
has_key = check_api_key()
if not has_key:
    st.warning(
        "⚠️ 未設定 ANTHROPIC_API_KEY。\n\n"
        "請在終端機設定：`set ANTHROPIC_API_KEY=sk-ant-...`\n"
        "或在 `config.json` 加入 `'anthropic_api_key'` 欄位後重啟 APP。\n\n"
        "設定後即可使用新聞情緒分析和法人報告解析功能。"
    )

# 分頁
tab1, tab2, tab3 = st.tabs(["📊 信心分數排行", "📰 新聞情緒", "📄 法人報告"])


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
                     use_container_width=True, disabled=not has_key):
            with st.spinner("計算中..."):
                import subprocess
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "confidence_score.py")],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
            load_confidence.clear()
            st.rerun()

    if not conf_df.empty:
        # KPI
        st.markdown("---")
        strong = (conf_df["confidence"] >= 80).sum() if "confidence" in conf_df else 0
        bullish = (conf_df["confidence"] >= 65).sum() if "confidence" in conf_df else 0
        watch = (conf_df["confidence"].between(50, 65)).sum() if "confidence" in conf_df else 0
        avg_conf = conf_df["confidence"].mean() if "confidence" in conf_df else 0

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
                # 橫條圖：前15名
                top = conf_df.head(15).copy()
                top["label"] = top.apply(
                    lambda r: f"{r.get('代碼','')}\n{str(r.get('名稱',''))[:6]}",
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
                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                # 三維分數散佈
                plot_df = conf_df[conf_df["confidence"] >= 50].head(30)
                if not plot_df.empty and all(
                    c in plot_df for c in ["tech_score","news_score","report_score"]
                ):
                    fig2 = go.Figure(go.Scatter(
                        x=plot_df["tech_score"],
                        y=plot_df["news_score"],
                        mode="markers+text",
                        text=plot_df.get("代碼", plot_df.index).astype(str),
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
                    st.plotly_chart(fig2, use_container_width=True)

        # 明細表
        st.markdown("---")
        st.markdown("### 📋 信心分數明細")
        show_cols = [c for c in [
            "代碼","名稱","產業","訊號等級","進場時機","收盤","停損",
            "confidence","signal_type","tech_score","news_score","report_score"
        ] if c in conf_df.columns]

        def color_conf(val):
            if isinstance(val, float):
                if val >= 80: return f"color:{GREEN};font-weight:700"
                if val >= 65: return f"color:{GREEN}"
                if val >= 50: return f"color:{GOLD}"
                return f"color:{MUTED}"
            return ""

        st.dataframe(
            conf_df[show_cols].style
                .applymap(color_conf, subset=["confidence"] if "confidence" in show_cols else [])
                .format({
                    "收盤":"{:.1f}","停損":"{:.1f}",
                    "confidence":"{:.1f}","tech_score":"{:.1f}",
                    "news_score":"{:.1f}","report_score":"{:.1f}",
                }),
            use_container_width=True, height=500,
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
                     use_container_width=True, disabled=not has_key):
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
            st.plotly_chart(fig_hist, use_container_width=True)

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
            st.plotly_chart(fig_src, use_container_width=True)

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
                .applymap(color_sentiment, subset=["sentiment"])
                .format({"score":"{:+.3f}"}),
            use_container_width=True, height=500,
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

st.markdown(
    f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
    f"資料：{NEWS_DIR} | {REPORTS_DIR}</p>",
    unsafe_allow_html=True,
)

"""
pages/3_績效追蹤.py — 選股紀錄 & 績效追蹤

功能：
  - 新增持倉（股號、進場日、進場價、股數、停損價）
  - 即時損益（讀最新 CSV）
  - 績效圖表（持倉曲線、個別損益）
  - 已出場紀錄 & 統計
"""
import sys, json
from pathlib import Path
from datetime import datetime, date

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

ROOT     = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data"
TRACK_FILE = ROOT / "data" / "portfolio_track.csv"

from ui_theme import (DARK, CARD, BORDER, TEXT, MUTED, GREEN, RED, GOLD,
                      BLUE, PURPLE, CYAN, inject_css, page_header)

st.set_page_config(page_title="績效追蹤", page_icon="📈", layout="wide")
inject_css()


# ─────────────────────────────────────────
# 工具
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def load_name_map():
    p = DATA_DIR / "stock_list.csv"
    if not p.exists(): return {}
    df = pd.read_csv(p, encoding="utf-8-sig")
    return dict(zip(df["ticker"].str.strip(), df["name"].str.strip()))

# 持倉存取改用多使用者模組（每人各自 portfolio_{user}.csv）
from portfolio import load_portfolio, save_portfolio
import trailing   # 移動停利（保本→鎖利，與策略引擎同規則）

def get_current_price(ticker: str) -> float | None:
    """從本地 CSV 取最新收盤價"""
    # 注意：必須先去掉 .TWO 再去掉 .TW（".TWO" 含 ".TW"，順序錯會變成 "6217O"）
    code = ticker.replace(".TWO", "").replace(".TW", "")
    for suffix in [".TW", ".TWO"]:
        p = DATA_DIR / f"{code}{suffix}.csv"
        if p.exists():
            try:
                df = pd.read_csv(p, index_col=0, parse_dates=True, usecols=[0,4])
                df.columns = ["Close"]
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                return float(df["Close"].dropna().iloc[-1])
            except: pass
    return None

def get_price_date(ticker: str) -> str:
    """取得本地價格 CSV 的最後日期（判斷資料是否過期）"""
    code = ticker.replace(".TWO", "").replace(".TW", "")
    for suffix in [".TW", ".TWO"]:
        p = DATA_DIR / f"{code}{suffix}.csv"
        if p.exists():
            try:
                df = pd.read_csv(p, index_col=0, parse_dates=True, usecols=[0, 4])
                return str(pd.to_datetime(df.index).max().date())
            except: pass
    return ""

def enrich_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """加入即時損益"""
    if df.empty: return df
    rows = []
    for _, r in df.iterrows():
        r = r.copy()
        if r.get("status") == "已出場":
            ep = float(r.get("exit_price") or 0)
            ent= float(r.get("entry_price") or 0)
            shares = float(r.get("shares") or 0)
            r["current_price"] = ep
            r["pnl_pct"]  = round((ep - ent) / ent * 100, 2) if ent else 0.0
            r["pnl_amt"]  = round((ep - ent) * shares * 1000, 0)
        else:
            cp = get_current_price(str(r.get("ticker","")))
            ent = float(r.get("entry_price") or 0)
            shares = float(r.get("shares") or 0)
            r["current_price"] = round(cp, 2) if cp else ent
            # 四捨五入：消除 float32 價格精度雜訊（同日進場 現價≈進場價 應為 0%）
            r["pnl_pct"] = round((cp - ent) / ent * 100, 2) if cp and ent else 0.0
            r["pnl_amt"] = round((cp - ent) * shares * 1000, 0) if cp and ent else 0.0
            # 移動停利：以進場價/自設初始停損為基準，回放到最新一根K，得到動態停損（保本→鎖利）
            sl_init = float(r.get("stop_loss") or 0)
            tr = trailing.trailing_stop(str(r.get("ticker","")),
                                        ent, r.get("entry_date",""), sl_init)
            r["trail_stop"]  = float(tr["stop"])
            r["stop_state"]  = tr["state"]
            r["lock_pct"]    = float(tr["lock_pct"])
            # 停損觸發判斷改用動態停損（現價 <= 移動停損）→ 打到就出場，鎖住基本獲利
            r["hit_stop"]   = bool(cp and r["trail_stop"] > 0 and cp <= r["trail_stop"])
            r["price_date"] = get_price_date(str(r.get("ticker","")))
        rows.append(r)
    out = pd.DataFrame(rows)
    if "hit_stop" not in out.columns:
        out["hit_stop"] = False
    return out


# ─────────────────────────────────────────
# 主畫面
# ─────────────────────────────────────────
page_header("選股績效追蹤", "PORTFOLIO TRACKER", "📈")
from gate import require_login, logout_button
_USER = require_login(); logout_button()
st.caption(f"目前使用者：**{_USER}**（持倉與通知各自獨立）")
# 每 5 分鐘自動刷新（背景 auto_refresh 盤中會更新持倉股價，這裡重讀顯示）
st_autorefresh(interval=5 * 60 * 1000, key="pf_autorefresh")
name_map = load_name_map()

portfolio = load_portfolio(_USER)

# 自動清除無效持倉（無代碼或進場價<=0，多半是表單沒填就送出的壞資料）
if not portfolio.empty:
    ep_num = pd.to_numeric(portfolio.get("entry_price"), errors="coerce").fillna(0)
    tk_ok  = portfolio.get("ticker", "").astype(str).str.strip() != ""
    valid  = portfolio[(ep_num > 0) & tk_ok]
    if len(valid) != len(portfolio):
        dropped = portfolio[~((ep_num > 0) & tk_ok)]["ticker"].astype(str).tolist()
        save_portfolio(valid, _USER)          # 直接從 CSV 移除
        portfolio = valid
        st.toast(f"已自動移除 {len(dropped)} 筆無效持倉（無代碼/進場價0）：{'、'.join(dropped)}")

# 自動停損出場（開啟時，開頁就檢查一次；背景守護盤中/收盤也會跑）
from auto_refresh import auto_stop_enabled, set_auto_stop
if auto_stop_enabled() and not portfolio.empty:
    from portfolio import auto_stop_exit
    _auto_exited = auto_stop_exit(_USER)
    if _auto_exited:
        _tks = "、".join(r["ticker"] for r in _auto_exited)
        st.toast(f"🛑 自動停損出場：{_tks}（已記錄+LINE通知）")
        portfolio = load_portfolio(_USER)

active_df  = portfolio[portfolio["status"] != "已出場"] if not portfolio.empty else pd.DataFrame()
closed_df  = portfolio[portfolio["status"] == "已出場"] if not portfolio.empty else pd.DataFrame()
active_rich = enrich_portfolio(active_df)
closed_rich = enrich_portfolio(closed_df)

# ── 新增持倉 sidebar ───────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 設定")
    _as = st.toggle("自動停損出場（收盤跌破停損自動記錄並移除）",
                    value=auto_stop_enabled())
    if _as != auto_stop_enabled():
        set_auto_stop(_as)
        st.rerun()
    st.caption("以收盤價判斷，非盤中跳動；App 開著時背景每 5 分鐘也會檢查")

    with st.expander(f"📧 Email 停損通知（{_USER} 專屬）"):
        from portfolio import load_notify, save_notify
        from notifier import notify_stop_exit
        _cfg = load_notify(_USER)
        _em = _cfg.get("email", {"enabled": False, "smtp": "smtp.gmail.com",
                                 "port": 587, "user": "", "password": "", "to": ""})
        st.caption("Gmail 需用「應用程式密碼」（非登入密碼）")
        st.markdown("[① 取得 Gmail 應用程式密碼](https://myaccount.google.com/apppasswords)")
        en  = st.checkbox("啟用 Email 停損通知", value=_em.get("enabled", False))
        usr = st.text_input("Gmail 帳號", value=_em.get("user", ""))
        pwd = st.text_input("應用程式密碼（16碼）", value=_em.get("password", ""), type="password")
        to  = st.text_input("收件人 Email", value=_em.get("to", "") or _em.get("user", ""))
        c1, c2 = st.columns(2)

        def _save_email(enable):
            _cfg["email"] = {"enabled": enable, "smtp": "smtp.gmail.com", "port": 587,
                             "user": usr.strip(), "password": pwd.strip(),
                             "to": (to.strip() or usr.strip())}
            save_notify(_USER, _cfg)

        if c1.button("💾 儲存", use_container_width=True):
            _save_email(en); st.success("已儲存")
        if c2.button("🔔 測試寄信", use_container_width=True):
            _save_email(True)
            ok = notify_stop_exit([{"ticker": "TEST", "name": "測試", "exit_price": 100.0,
                                    "stop_loss": 100.0, "pnl_pct": -5.0}], load_notify(_USER))
            st.success("已寄出，請看信箱") if ok else st.error("寄信失敗，檢查帳號/應用程式密碼")

    st.markdown("---")
    st.markdown("## ➕ 新增持倉")

    # 從今日掃描結果快速匯入
    scan_csvs = sorted((ROOT / "scan_results").glob("signals_*.csv"), reverse=True)
    if scan_csvs:
        scan_df = pd.read_csv(scan_csvs[0], encoding="utf-8-sig")
        buy_df  = scan_df[scan_df["訊號等級"].str.contains("BUY", na=False)]
        if not buy_df.empty:
            st.markdown("**從今日訊號快速選入：**")
            selected = st.selectbox(
                "選擇股票",
                ["（手動輸入）"] + buy_df["代碼"].tolist(),
                label_visibility="collapsed",
            )
        else:
            selected = "（手動輸入）"
    else:
        selected = "（手動輸入）"
        buy_df   = pd.DataFrame()

    if selected != "（手動輸入）" and not buy_df.empty:
        row = buy_df[buy_df["代碼"] == selected].iloc[0]
        default_ticker = selected
        default_price  = float(row.get("收盤", 0))
        default_stop   = float(row.get("停損", 0))
        default_strat  = str(row.get("策略", ""))
    else:
        default_ticker = ""
        default_price  = 0.0
        default_stop   = 0.0
        default_strat  = ""

    with st.form("add_position", clear_on_submit=True):
        ticker_in = st.text_input("股票代碼（如 2330.TW）", value=default_ticker)
        c1, c2 = st.columns(2)
        entry_price = c1.number_input("進場價", value=default_price, min_value=0.0, step=0.1)
        shares_in   = c2.number_input("股數（張）", value=1, min_value=1, step=1)
        entry_date  = st.date_input("進場日", value=date.today())
        stop_loss   = st.number_input("停損價（留 0 = 自動用 進場−1.5ATR）",
                                      value=default_stop, min_value=0.0, step=0.1)
        strategy_in = st.text_input("策略", value=default_strat)
        note_in     = st.text_input("備註")
        add_more    = st.checkbox("第2次進場（加碼）— 同股再記一筆，各自算移動停損",
                                  value=False,
                                  help="勾選後即使已持有同一檔也會另計一列（第2次/第3次進場）。")

        if st.form_submit_button("✅ 加入追蹤", type="primary", use_container_width=True):
            if not ticker_in:
                st.error("請輸入股票代碼")
            elif entry_price <= 0:
                st.error("請輸入進場價（不可為 0）")
            else:
                tk = ticker_in.strip().upper()
                # 補 suffix
                if not tk.endswith(".TW") and not tk.endswith(".TWO"):
                    tk += ".TW"
                name = name_map.get(tk, "")
                _held = portfolio[(portfolio["ticker"].astype(str).str.upper() == tk) &
                                  (portfolio["status"] == "持倉中")] if not portfolio.empty \
                        else pd.DataFrame()
                _lot = len(_held) + 1
                if not _held.empty and not add_more:
                    st.warning(f"⚠️ {tk} 已在持倉中。若要**第2次進場（加碼）**，"
                               f"請勾選上方核取方塊再送出；否則勿重複加入。")
                else:
                    _note = note_in
                    if _lot >= 2:
                        _note = (f"第{_lot}次進場" + (f"｜{note_in}" if note_in else "")).strip("｜")
                    new_id = int(datetime.now().timestamp() * 1000)
                    new_row = pd.DataFrame([{
                        "id":          new_id,
                        "ticker":      tk,
                        "name":        name,
                        "entry_date":  str(entry_date),
                        "entry_price": entry_price,
                        "shares":      shares_in,
                        "stop_loss":   stop_loss,
                        "strategy":    strategy_in,
                        "note":        _note,
                        "exit_date":   "",
                        "exit_price":  "",
                        "status":      "持倉中",
                    }])
                    portfolio = pd.concat([portfolio, new_row], ignore_index=True)
                    save_portfolio(portfolio, _USER)
                    st.success(f"已加入 {tk} {name}" + (f"（第{_lot}次進場）" if _lot >= 2 else ""))
                    st.rerun()

    st.markdown("---")
    st.markdown("**出場紀錄**")
    if not active_df.empty:
        exit_sel = st.selectbox(
            "選擇出場股票",
            active_df["ticker"].tolist(),
            label_visibility="collapsed",
        )
        exit_price_in = st.number_input("出場價", min_value=0.0, step=0.1, key="exit_price")
        exit_date_in  = st.date_input("出場日", value=date.today(), key="exit_date")
        if st.button("✅ 確認出場", use_container_width=True):
            idx = portfolio[
                (portfolio["ticker"] == exit_sel) & (portfolio["status"] == "持倉中")
            ].index
            if len(idx) > 0:
                portfolio.loc[idx[0], "exit_date"]  = str(exit_date_in)
                portfolio.loc[idx[0], "exit_price"] = exit_price_in
                portfolio.loc[idx[0], "status"]     = "已出場"
                save_portfolio(portfolio, _USER)
                st.success(f"{exit_sel} 已出場")
                st.rerun()


# ── KPI ────────────────────────────────────
st.markdown("---")
total_pnl   = float(active_rich["pnl_amt"].sum()) if not active_rich.empty else 0
total_cost  = float((active_rich["entry_price"] * active_rich["shares"] * 1000).sum()) if not active_rich.empty else 0
total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0
win_closed  = (closed_rich["pnl_pct"] > 0).sum() if not closed_rich.empty else 0
win_rate    = win_closed / len(closed_rich) * 100 if not closed_rich.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
for col, label, val, cls in [
    (k1, "持倉中",   f"{len(active_df)} 檔",     "blue"),
    (k2, "未實現損益", f"{total_pnl:+,.0f} 元",   "green" if total_pnl >= 0 else "red"),
    (k3, "未實現損益%", f"{total_pnl_pct:+.2f}%", "green" if total_pnl_pct >= 0 else "red"),
    (k4, "已出場",   f"{len(closed_df)} 筆",      ""),
    (k5, "出場勝率", f"{win_rate:.1f}%",           "green" if win_rate >= 50 else "gold"),
]:
    with col:
        st.markdown(
            f"""<div class="pnl-card">
            <div class="pnl-label">{label}</div>
            <div class="pnl-value {cls}">{val}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── 停損觸發警示 + 一鍵記錄出場並移除 ──────────
if not active_rich.empty and "hit_stop" in active_rich.columns:
    hit = active_rich[active_rich["hit_stop"]]
    if not hit.empty:
        lines = "　".join(
            f"**{r['ticker']} {r.get('name','')}**（現價 {r['current_price']:.1f} ≤ 移動停損 "
            f"{float(r.get('trail_stop', r.get('stop_loss', 0))):.1f}，鎖利 {float(r.get('lock_pct',0)):+.1f}%）"
            for _, r in hit.iterrows()
        )
        wc, bc = st.columns([4.2, 1.4])
        with wc:
            st.error(f"🛑 **{len(hit)} 檔已觸發停損：**　{lines}")
        with bc:
            if st.button("🛑 停損出場（記錄並移除）", type="primary",
                         use_container_width=True):
                today = str(date.today())
                done = []
                for _, r in hit.iterrows():
                    # 以 id 精準比對「該筆」持倉（同股多筆加碼時各自獨立出場）
                    idx = portfolio[(portfolio["id"] == r["id"]) &
                                    (portfolio["status"] == "持倉中")].index
                    if not len(idx):  # 後備：舊資料無 id 時退回用代碼
                        idx = portfolio[(portfolio["ticker"] == r["ticker"]) &
                                        (portfolio["status"] == "持倉中")].index
                    if len(idx):
                        # 以現價（已跌破停損）作為出場價 → 移到出場紀錄
                        portfolio.loc[idx[0], "exit_date"]  = today
                        portfolio.loc[idx[0], "exit_price"] = round(float(r["current_price"]), 2)
                        portfolio.loc[idx[0], "status"]     = "已出場"
                        note = str(portfolio.loc[idx[0], "note"] or "")
                        portfolio.loc[idx[0], "note"] = (note + " ｜停損出場").strip("｜ ")
                        done.append(str(r["ticker"]))
                save_portfolio(portfolio, _USER)
                st.success(f"已停損出場並移到出場紀錄：{'、'.join(done)}")
                st.rerun()

# ── 資料過期提醒 + 一鍵更新 ──────────────────
if not active_rich.empty and "price_date" in active_rich.columns:
    today_str = date.today().strftime("%Y-%m-%d")
    stale = active_rich[active_rich["price_date"].astype(str) < today_str]
    if not stale.empty:
        oldest = stale["price_date"].min()
        wc, bc = st.columns([4.2, 1.3])
        with wc:
            st.warning(
                f"⚠️ 部分持倉的價格資料非今日（最舊：{oldest}），"
                f"現價/停損判斷可能失準。"
            )
        with bc:
            if st.button("🔄 立即更新持倉股價", type="primary",
                         use_container_width=True):
                from auto_refresh import update_held_now
                bar = st.progress(0.0, text="準備更新...")
                def _cb(i, total, tk):
                    bar.progress((i - 1) / max(total, 1),
                                 text=f"[{i}/{total}] 更新 {tk} ...")
                fails = update_held_now(_cb)
                bar.progress(1.0, text="✅ 更新完成")
                if fails:
                    st.error("更新失敗：" + ", ".join(fails))
                else:
                    st.rerun()
            st.caption("全市場更新請到「⏱️ 更新進度」頁")

# ── 分頁 ────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 持倉損益圖", "📋 持倉明細", "🏁 出場紀錄"])

# ══ Tab1：損益圖 ════════════════════════════
with tab1:
    if active_rich.empty:
        st.info("尚無持倉，請從左側新增")
    else:
        # 個別損益橫條圖
        ar = active_rich.copy()
        ar["label"] = ar["ticker"] + "  " + ar["name"].fillna("")
        bar_c = [GREEN if v >= 0 else RED for v in ar["pnl_pct"]]

        fig_pnl = go.Figure(go.Bar(
            x=ar["pnl_pct"],
            y=ar["label"],
            orientation="h",
            marker=dict(color=bar_c, opacity=0.88),
            text=[f"  {v:+.2f}%  ({int(a/1000):+,}K)" for v, a in
                  zip(ar["pnl_pct"], ar["pnl_amt"])],
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "損益率：%{x:+.2f}%<br>"
                "損益額：%{customdata[0]:+,.0f} 元<br>"
                "進場：%{customdata[1]} @ %{customdata[2]:.1f}<extra></extra>"
            ),
            customdata=ar[["pnl_amt","entry_date","entry_price"]].values,
        ))
        fig_pnl.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
        # 損益率軸給最小範圍 ±3%，避免全部≈0%（同日進場）時軸自動縮到 μ 刻度撐爆
        _pmax = max(3.0, float(ar["pnl_pct"].abs().max()) * 1.15)
        fig_pnl.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            title=dict(text="持倉未實現損益",
                       font=dict(size=15, color=TEXT), x=0.01),
            xaxis=dict(gridcolor=BORDER, title="損益率 (%)", range=[-_pmax, _pmax]),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
            height=max(350, len(ar)*40+80),
            margin=dict(l=10, r=120, t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

        # 距停損空間（用移動停損）
        _stopcol = "trail_stop" if "trail_stop" in ar.columns else "stop_loss"
        if _stopcol in ar.columns:
            ar2 = ar[ar[_stopcol] > 0].copy()
            if not ar2.empty:
                ar2["to_stop"] = (ar2["current_price"] - ar2[_stopcol]) / ar2["current_price"] * 100
                ar2 = ar2.sort_values("to_stop")
                stop_c = [RED if v < 3 else (GOLD if v < 8 else BLUE) for v in ar2["to_stop"]]
                fig_stop = go.Figure(go.Bar(
                    x=ar2["to_stop"],
                    y=ar2["ticker"] + "  " + ar2["name"].fillna(""),
                    orientation="h",
                    marker=dict(color=stop_c, opacity=0.85),
                    text=[f"  {v:.1f}%" for v in ar2["to_stop"]],
                    textposition="outside",
                    textfont=dict(size=12, color=TEXT),
                    hovertemplate="<b>%{y}</b><br>距停損：%{x:.1f}%<extra></extra>",
                ))
                fig_stop.update_layout(
                    paper_bgcolor=DARK, plot_bgcolor=CARD,
                    font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
                    title=dict(text="距停損空間（紅<3%警示）",
                               font=dict(size=15, color=TEXT), x=0.01),
                    xaxis=dict(gridcolor=BORDER, title="距停損 (%)"),
                    yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
                    height=max(300, len(ar2)*40+80),
                    margin=dict(l=10, r=80, t=50, b=30),
                    showlegend=False,
                )
                st.plotly_chart(fig_stop, use_container_width=True)


# ══ Tab2：持倉明細 ══════════════════════════
with tab2:
    if active_rich.empty:
        st.info("尚無持倉")
    else:
        active_rich = active_rich.copy()
        active_rich["停損狀態"] = active_rich.apply(
            lambda x: "🛑 已觸發" if x.get("hit_stop")
            else x.get("stop_state", "✅ 持有中"), axis=1)

        show = [c for c in [
            "ticker","name","entry_date","entry_price","current_price",
            "pnl_pct","pnl_amt","trail_stop","停損狀態","shares","strategy","note"
        ] if c in active_rich.columns]

        rename = {
            "ticker":"代碼","name":"名稱","entry_date":"進場日",
            "entry_price":"進場價","current_price":"現價",
            "pnl_pct":"損益%","pnl_amt":"損益額",
            "trail_stop":"移動停損","shares":"張數",
            "strategy":"策略","note":"備註",
        }

        def color_pnl(val):
            if isinstance(val, float):
                if val > 5:   return f"color:{GREEN};font-weight:700"
                if val > 0:   return f"color:{GREEN}"
                if val < -5:  return f"color:{RED};font-weight:700"
                if val < 0:   return f"color:{RED}"
            return ""

        disp = active_rich[show].rename(columns=rename)
        st.dataframe(
            disp.style
                .map(color_pnl, subset=["損益%"] if "損益%" in disp.columns else [])
                .format({
                    "進場價":"{:.1f}","現價":"{:.1f}","移動停損":"{:.1f}",
                    "損益%":"{:+.2f}%","損益額":"{:+,.0f}",
                }),
            use_container_width=True,
            height=min(600, len(disp)*38+60),
        )

        # ── 同股多筆（第2次進場/加碼）→ 合計加權平均 ──
        dups = active_rich["ticker"].value_counts()
        multi = dups[dups >= 2].index.tolist()
        if multi:
            st.markdown("**加碼合計（同股多筆 → 加權平均成本）**")
            sm = []
            for tk in multi:
                g = active_rich[active_rich["ticker"] == tk]
                sh = g["shares"].astype(float)
                tot_sh = float(sh.sum())
                avg_cost = float((g["entry_price"].astype(float) * sh).sum() / tot_sh) if tot_sh else 0.0
                cur = float(g["current_price"].astype(float).iloc[0])
                pnl_amt = float(g["pnl_amt"].astype(float).sum())
                sm.append({
                    "代碼": tk, "名稱": g["name"].iloc[0], "筆數": len(g),
                    "加權平均成本": round(avg_cost, 2), "現價": round(cur, 2),
                    "總張數": int(tot_sh),
                    "整體損益%": round((cur - avg_cost) / avg_cost * 100, 2) if avg_cost else 0.0,
                    "整體損益額": round(pnl_amt, 0),
                })
            st.dataframe(pd.DataFrame(sm), use_container_width=True, hide_index=True,
                         column_config={
                             "整體損益%": st.column_config.NumberColumn(format="%+.2f%%"),
                             "整體損益額": st.column_config.NumberColumn(format="%+,.0f"),
                         })

        # ── 持倉 K 線圖（標買進箭頭 + 策略買賣訊）+ 籌碼 5 軌 ──
        st.markdown("#### 📈 持倉圖表")
        from kline_chart import render_kline
        opts = active_rich["ticker"].tolist()
        sel_k = st.selectbox("選擇持倉看圖", opts, key="kline_sel")
        krow = active_rich[active_rich["ticker"] == sel_k].iloc[0]

        tab_k, tab_chip = st.tabs(["📈 K 線（買進箭頭+策略訊號）", "📊 籌碼 5 軌"])
        with tab_k:
            render_kline(
                ticker       = str(krow["ticker"]),
                name         = str(krow.get("name", "") or ""),
                entry_date   = str(krow.get("entry_date", "") or ""),
                entry_price  = float(krow.get("entry_price", 0) or 0),
                stop         = float(krow.get("stop_loss", 0) or 0),
                trail_stop   = float(krow.get("trail_stop", 0) or 0),
                lock_pct     = float(krow.get("lock_pct", 0) or 0),
                strategy_name= str(krow.get("strategy", "") or ""),
            )
            # ── 下方：SUPER TREND 圖 + 風險（趨勢/支撐/延續機率）──
            st.markdown("##### ⚡ SUPER TREND 趨勢與風險")
            from chip_chart import build_supertrend_figure, render_supertrend_table
            stc1, stc2 = st.columns([2.6, 1])
            with stc1:
                stfig = build_supertrend_figure(str(krow["ticker"]), height=340)
                if stfig is not None:
                    st.plotly_chart(stfig, use_container_width=True)
                else:
                    st.caption("SUPER TREND：資料不足")
            with stc2:
                render_supertrend_table(str(krow["ticker"]))
        with tab_chip:
            try:
                from chip_chart import build_chip_figure
                cfig = build_chip_figure(str(krow["ticker"]), height=720)
                if cfig is not None:
                    st.plotly_chart(cfig, use_container_width=True)
                else:
                    st.caption("無籌碼資料")
            except Exception as e:
                st.caption(f"籌碼圖載入失敗：{e}")

        # 刪除持倉
        with st.expander("🗑️ 刪除持倉"):
            del_sel = st.selectbox("選擇刪除", active_df["ticker"].tolist(), key="del_sel")
            if st.button("確認刪除", key="del_btn"):
                idx = portfolio[
                    (portfolio["ticker"] == del_sel) & (portfolio["status"] == "持倉中")
                ].index
                if len(idx):
                    portfolio = portfolio.drop(idx[0])
                    save_portfolio(portfolio, _USER)
                    st.rerun()


# ══ Tab3：出場紀錄 ══════════════════════════
with tab3:
    if closed_rich.empty:
        st.info("尚無出場紀錄")
    else:
        # 統計
        avg_win  = closed_rich[closed_rich["pnl_pct"]>0]["pnl_pct"].mean() if win_closed else 0
        avg_loss = closed_rich[closed_rich["pnl_pct"]<=0]["pnl_pct"].mean() if (len(closed_rich)-win_closed) else 0
        total_closed_pnl = closed_rich["pnl_amt"].sum()

        m1, m2, m3, m4 = st.columns(4)
        for col, label, val, cls in [
            (m1, "出場勝率",   f"{win_rate:.1f}%",        "green" if win_rate>=50 else "red"),
            (m2, "平均獲利",   f"+{avg_win:.2f}%",         "green"),
            (m3, "平均虧損",   f"{avg_loss:.2f}%",         "red"),
            (m4, "總實現損益", f"{total_closed_pnl:+,.0f}", "green" if total_closed_pnl>=0 else "red"),
        ]:
            with col:
                st.markdown(
                    f"""<div class="pnl-card">
                    <div class="pnl-label">{label}</div>
                    <div class="pnl-value {cls}">{val}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

        # 出場損益圖
        cr = closed_rich.copy()
        cr["label"] = cr["ticker"] + "  " + cr["name"].fillna("")
        cr = cr.sort_values("pnl_pct", ascending=False)
        bar_c2 = [GREEN if v > 0 else RED for v in cr["pnl_pct"]]
        fig_cl = go.Figure(go.Bar(
            x=cr["pnl_pct"],
            y=cr["label"],
            orientation="h",
            marker=dict(color=bar_c2, opacity=0.88),
            text=[f"  {v:+.2f}%" for v in cr["pnl_pct"]],
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            hovertemplate=(
                "<b>%{y}</b><br>損益率：%{x:+.2f}%<br>"
                "損益額：%{customdata[0]:+,.0f}<br>"
                "進場：%{customdata[1]}  出場：%{customdata[2]}<extra></extra>"
            ),
            customdata=cr[["pnl_amt","entry_date","exit_date"]].values,
        ))
        fig_cl.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
        fig_cl.update_layout(
            paper_bgcolor=DARK, plot_bgcolor=CARD,
            font=dict(family="Microsoft JhengHei, Arial", size=13, color=TEXT),
            title=dict(text="已出場損益", font=dict(size=15, color=TEXT), x=0.01),
            xaxis=dict(gridcolor=BORDER, title="損益率 (%)"),
            yaxis=dict(gridcolor=BORDER, tickfont=dict(size=12)),
            height=max(300, len(cr)*40+80),
            margin=dict(l=10, r=100, t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_cl, use_container_width=True)

        # 明細表
        show2 = [c for c in [
            "ticker","name","entry_date","entry_price",
            "exit_date","exit_price","pnl_pct","pnl_amt","strategy"
        ] if c in closed_rich.columns]
        rename2 = {
            "ticker":"代碼","name":"名稱","entry_date":"進場日",
            "entry_price":"進場價","exit_date":"出場日",
            "exit_price":"出場價","pnl_pct":"損益%","pnl_amt":"損益額","strategy":"策略"
        }
        disp2 = closed_rich[show2].rename(columns=rename2)
        st.dataframe(
            disp2.style
                .map(color_pnl, subset=["損益%"] if "損益%" in disp2.columns else [])
                .format({"進場價":"{:.1f}","出場價":"{:.1f}","損益%":"{:+.2f}%","損益額":"{:+,.0f}"}),
            use_container_width=True,
        )

        csv = disp2.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ 下載出場紀錄", csv,
                           file_name="trade_record.csv", mime="text/csv")

st.markdown(
    f"<p style='color:{MUTED};font-size:12px;text-align:right'>"
    f"持倉資料：{TRACK_FILE}</p>",
    unsafe_allow_html=True,
)

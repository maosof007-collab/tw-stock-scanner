"""
pages/48_個股.py — 個股整合頁(一檔股票一頁)
=================================================================
2026-11-24 使用者:「我大部分其實都有,我少的是整合、美觀性」「介面可以好好的大改,修正得更容易讀」。
做法:上面一條固定的報價列,下面分頁;「總覽」是一格一格的卡片——每張卡=一張小圖+幾個關鍵數字+一句白話+「更多」連到原本的細節頁。
這一頁只讀本機檔案(日線、bulk 季報/月營收、三大法人、融資券、集保、內部人設質、海報),不發任何請求;資料由每日排程更新。
「估值」分頁也一樣:三情境、本益比帶、明年情境用本機 bulk 季報算(forecast_card.anchor(q=…));河流圖只讀「估值前瞻」抓過的快取檔。
網址可以帶代號:/個股?code=6425。
沒有的資料(個股殖利率、淨值比、內部人買賣事後申報)不顯示,不用別的數字頂替。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import ui_theme as th
from twtime import now_tw
from ui_theme import inject_css, page_header

st.set_page_config(page_title="個股", page_icon="🔎", layout="wide")
inject_css()
from gate import require_login, logout_button
require_login(); logout_button()
page_header("個股", "ONE STOCK · ONE PAGE", "🔎")

D = ROOT / "data"
UP, DN = th.RED, th.GREEN            # 台股:紅漲綠跌


# ── 讀檔(只讀本機;10 分鐘快取)──
@st.cache_data(ttl=600, show_spinner=False)
def load_px(code: str) -> pd.DataFrame:
    fs = sorted(D.glob(f"{code}.TW*.csv"))
    if not fs:
        return pd.DataFrame()
    d = pd.read_csv(fs[0], parse_dates=["Date"]).dropna(subset=["Close"])
    return d[d.Close > 0].reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_fin(code: str) -> pd.DataFrame:
    q = pd.read_csv(D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    q = q[q.code == code].sort_values("季度").reset_index(drop=True)
    q.columns = ["code", "q", "rev", "gm", "om", "nm", "eps"]
    return q


@st.cache_data(ttl=600, show_spinner=False)
def load_rev(code: str) -> pd.DataFrame:
    r = pd.read_csv(D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    r = r[r.code == code].sort_values("ym").reset_index(drop=True)
    r["rev"] = r["revenue"] / 100          # 百萬 → 億
    return r.rename(columns={"yoy%": "yoy"})[["ym", "rev", "yoy"]]


@st.cache_data(ttl=600, show_spinner=False)
def load_inst(code: str) -> pd.DataFrame:
    p = D / "institutional" / f"{code}_inst.csv"
    if not p.exists():
        return pd.DataFrame()
    i = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
    out = pd.DataFrame({"date": i["date"], "外資": i["外陸資買賣超股數(不含外資自營商)"] / 1000, "投信": i["it_net"] / 1000,
                        "自營商": (i.get("dealer_self_net", 0) + i.get("dealer_hedge_net", 0)) / 1000})
    return out.fillna(0).reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_margin(code: str) -> pd.DataFrame:
    p = D / "margin" / f"{code}_margin.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["date"]).sort_values("date")[["date", "margin_balance", "short_balance"]].reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_big(code: str) -> pd.DataFrame:
    p = D / "tdcc" / f"{code}_tdcc.csv"
    if not p.exists():
        return pd.DataFrame()
    t = pd.read_csv(p, parse_dates=["date"])
    b = t[t.level.between(12, 15)].groupby("date").pct.sum()          # 400 張以上
    h = t[t.level.between(1, 15)].groupby("date").holders.sum()
    return pd.DataFrame({"big": b, "holders": h}).reset_index()


@st.cache_data(ttl=600, show_spinner=False)
def load_pledge(code: str) -> pd.DataFrame:
    p = D / "insider_pledge.csv.gz"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_csv(p, dtype=str)
    d = d[d.code == code].copy()
    if d.empty:
        return d
    def roc(x):
        try:
            y, m, dd = str(x).split("/")
            return pd.Timestamp(int(y) + 1911, int(m), int(dd))
        except Exception:
            return pd.NaT
    d["dt"] = d["date"].map(roc)
    for c in ("pledge", "release", "cum"):
        d[c] = pd.to_numeric(d[c].str.replace(",", ""), errors="coerce").fillna(0) / 1000
    d["role"] = d["role"].str.replace(r"^[A-Z0-9]+\s*", "", regex=True)
    return d.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_insider(code: str) -> pd.DataFrame:
    import insider_trades as it
    return it.series(code)


@st.cache_data(ttl=600, show_spinner=False)
def load_mprice(code: str) -> pd.DataFrame:
    import insider_trades as it
    return it.monthly_price(code)


def insider_fig(ins: pd.DataFrame, mp: pd.DataFrame) -> go.Figure:
    """上:月底收盤線+內部人淨增(紅)/淨減(綠)的點——圓=董監合計、菱形=經理人持股變動,點越大估計金額越大,最大的幾個月拉框標示;
    下:每月增加(往上)/減少(往下)的估計金額,深色=董監、淺色=經理人。"""
    from plotly.subplots import make_subplots
    d = ins.tail(36).reset_index(drop=True)
    months = [str(x) for x in pd.period_range(d.ym.iloc[0], f"{now_tw():%Y-%m}", freq="M")]
    pos = {m: i for i, m in enumerate(months)}
    close = mp.set_index("ym").close.reindex(months)
    lo, hi = float(close.min()), float(close.max())
    span = max(hi - lo, hi * 0.05)
    f = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24], vertical_spacing=0.03)
    f.add_scatter(x=months, y=close, mode="lines", line=dict(color=th.TEXT, width=2), fill="tozeroy", fillcolor=f"rgba({th.ACC_RGB},0.10)",
                  hovertemplate="月底收盤 %{y:g}<extra></extra>", row=1, col=1)
    a = d[d.net_k != 0].assign(who="董監", k=lambda z: z.net_k, amt=lambda z: z.net_amt)
    m = d[d.mgr_chg_k.fillna(0) != 0].assign(who="經理人", k=lambda z: z.mgr_chg_k, amt=lambda z: z.mgr_chg_k * z["avg"] / 10)
    ev = pd.concat([a, m], ignore_index=True)
    ev["y"] = ev.ym.map(close)
    ev = ev.dropna(subset=["y", "amt"])
    if len(ev):
        mx = ev.amt.abs().max() or 1
        for who, sym in (("董監", "circle"), ("經理人", "diamond")):
            e = ev[ev.who == who]
            if e.empty:
                continue
            f.add_scatter(x=e.ym, y=e.y, mode="markers", row=1, col=1,
                          marker=dict(symbol=sym, size=9 + 15 * np.sqrt(e.amt.abs() / mx), color=[UP if v > 0 else DN for v in e.k], line=dict(color=th.DARK, width=1.5)),
                          customdata=np.stack([e.k, e.amt, e["avg"]], axis=1),
                          hovertemplate=who + " %{customdata[0]:+,.0f} 張|約 %{customdata[1]:+,.0f} 萬|月均價 %{customdata[2]:.1f}<extra></extra>")
        for sign, ay, colr in ((1, hi + span * 0.42, UP), (-1, lo - span * 0.42, DN)):
            top = ev[np.sign(ev.k) == sign].assign(a=lambda z: z.amt.abs()).nlargest(4, "a").sort_values("ym")
            for j, r in enumerate(top.itertuples()):
                ax = (0.10 + 0.80 * (j + 0.5) / max(len(top), 1)) * (len(months) - 1)
                f.add_annotation(x=pos[r.ym], y=r.y, ax=ax, ay=ay, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=0, arrowwidth=1.2, arrowcolor=colr,
                                 text=f"{r.ym[2:].replace('-', '/')} {r.who}{'增' if sign > 0 else '減'} {abs(r.k):,.0f} 張<br>均 {r.avg:.1f}・約 {abs(r.amt):,.0f} 萬",
                                 font=dict(size=11, color=colr), bordercolor=colr, borderwidth=1.2, borderpad=4, bgcolor=th.CARD, align="center")
    ma = d.mgr_chg_k.fillna(0) * d["avg"] / 10
    f.add_bar(x=d.ym, y=d.buy_amt, marker_color=UP, hovertemplate="董監增加 約 %{y:,.0f} 萬<extra></extra>", row=2, col=1)
    f.add_bar(x=d.ym, y=-d.sell_amt, marker_color=DN, hovertemplate="董監減少 約 %{y:,.0f} 萬<extra></extra>", row=2, col=1)
    f.add_bar(x=d.ym, y=ma.clip(lower=0), marker_color=UP, opacity=0.45, hovertemplate="經理人增加 約 %{y:,.0f} 萬<extra></extra>", row=2, col=1)
    f.add_bar(x=d.ym, y=ma.clip(upper=0), marker_color=DN, opacity=0.45, hovertemplate="經理人減少 約 %{y:,.0f} 萬<extra></extra>", row=2, col=1)
    last_i = pos[d.ym.iloc[-1]]
    if last_i < len(months) - 1:
        f.add_vrect(x0=last_i + 0.5, x1=len(months) - 0.5, fillcolor=th.MUTED, opacity=0.12, line_width=0, annotation_text="尚未申報", annotation_position="bottom left",
                    annotation_font=dict(size=10, color=th.MUTED))
    f.update_layout(height=440, margin=dict(l=4, r=8, t=6, b=4), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=th.MUTED, size=11),
                    showlegend=False, barmode="relative", bargap=0.3, hovermode="x unified")
    f.update_xaxes(showgrid=False, tickfont=dict(size=10), type="category", categoryorder="array", categoryarray=months, nticks=14)
    f.update_yaxes(gridcolor=th.GRID, zerolinecolor=th.BORDER, tickfont=dict(size=10))
    f.update_yaxes(range=[lo - span * 0.62, hi + span * 0.62], row=1, col=1)
    f.update_yaxes(title_text="萬元", title_font=dict(size=10), row=2, col=1)
    return f


@st.cache_data(ttl=600, show_spinner=False)
def load_val(code: str) -> dict:
    """估值:三情境、歷史本益比帶、明年情境都只用本機 bulk 季報+日線算;河流圖只讀已經抓過的快取檔。這一頁不發請求。"""
    import importlib

    import forecast_card as FC
    import fundamentals as FU
    import pe_river as PR
    FC, PR = importlib.reload(FC), importlib.reload(PR)      # 迭代中模組:無條件重載(只在快取過期時跑一次)
    A = FC.anchor(code, q=FU._bulk_quarterly(code, 4))
    if not A.get("ok"):
        return {"ok": False}
    band = FC.pe_band(code, A["q"])
    NY = FC.next_year(code, A)
    px = load_px(code)
    rows = FC.next_year_rows(NY, float(px.Close.iloc[-1]) if len(px) else None) if NY.get("ok") else []
    try:
        RV = PR.series(code, 10, fetch=False)
    except Exception:
        RV = None
    return dict(ok=True, A=A, band=band, NY=NY, rows=rows, RV=RV)


@st.cache_data(ttl=600, show_spinner=False)
def load_meta(code: str) -> dict:
    sl = pd.read_csv(D / "stock_list.csv", dtype=str, encoding="utf-8-sig").drop_duplicates("code").set_index("code")
    m = dict(name=code, sector="", market="")
    if code in sl.index:
        m.update(name=sl.name[code], sector=sl.sector[code] if pd.notna(sl.sector[code]) else "", market=sl.market[code])
    tags = []
    try:
        dis = pd.read_csv(D / "_disposal_now.csv", dtype=str)
        if ((dis.code == code) & (dis.end >= f"{now_tw():%Y-%m-%d}")).any():
            tags.append(("處置中", DN))
    except Exception:
        pass
    try:
        t = pd.read_csv(D / "_turnaround_scan.csv", dtype=str)
        r = t[t[t.columns[0]] == code]
        if len(r):
            r = r.iloc[0]
            g = {"A": "剛轉盈", "B": "轉盈第二季", "C": "準備轉盈"}.get(str(r.get("grp")), "")
            if g:
                tags.append((g, th.GOLD))
            if str(r.get("S2")) == "True":
                tags.append(("連兩季三率三升", UP))
            elif str(r.get("S")) == "True":
                tags.append(("三率三升", UP))
    except Exception:
        pass
    m["tags"] = tags
    return m


# ── 小工具 ──
def col(x) -> str:
    return th.TEXT if x is None or pd.isna(x) or x == 0 else (UP if x > 0 else DN)


def sp(txt: str, x) -> str:
    return f'<span style="color:{col(x)};font-weight:700">{txt}</span>'


def kv(rows: list) -> str:
    """rows: [(標籤, 值的 HTML)] → 一張兩欄小表(單行 HTML)。"""
    body = "".join(f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>' for k, v in rows)
    return f'<table class="kv">{body}</table>'


def grid(head: list, rows: list) -> str:
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="kv gr"><tr>{h}</tr>{b}</table>'


def plain(txt: str) -> None:
    st.markdown(f'<div class="plain"><b>白話</b>{txt}</div>', unsafe_allow_html=True)


def head(title: str, sub: str, more: str = "", href: str = "") -> None:
    link = f'<a href="{href}" target="_self">{more} →</a>' if more else ""
    st.markdown(f'<div class="ch"><span><b>{title}</b><small>{sub}</small></span>{link}</div>', unsafe_allow_html=True)


def fig_base(h: int = 170) -> go.Figure:
    f = go.Figure()
    f.update_layout(height=h, margin=dict(l=4, r=4, t=6, b=4), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=th.MUTED, size=11), showlegend=False, bargap=0.25, hovermode="x unified")
    f.update_xaxes(showgrid=False, tickfont=dict(size=10))
    f.update_yaxes(gridcolor=th.GRID, zerolinecolor=th.BORDER, tickfont=dict(size=10))
    return f


def show(f: go.Figure, key: str) -> None:
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False}, key=key)


CSS = (f"<style>.qb{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:6px 26px;padding:10px 16px;border:1px solid {th.BORDER};border-radius:10px;background:{th.CARD};margin-bottom:8px}}"
       f".qb .nm{{font-size:1.5rem;font-weight:900;color:{th.TEXT}}}.qb .nm small{{font-size:.85rem;color:{th.MUTED};font-weight:600;margin-left:8px}}"
       f".qb .px{{font-size:2.1rem;font-weight:900;line-height:1}}.qb .it{{line-height:1.2}}.qb .it b{{display:block;font-size:1.05rem;color:{th.TEXT}}}.qb .it span{{font-size:.75rem;color:{th.MUTED}}}"
       f".qb .tg{{font-size:.75rem;font-weight:800;border:1.5px solid;border-radius:10px;padding:1px 8px;margin-left:6px;vertical-align:middle}}"
       f".ch{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid {th.BORDER};padding-bottom:3px;margin-bottom:2px}}"
       f".ch b{{font-size:1rem;color:{th.TEXT}}}.ch small{{color:{th.MUTED};margin-left:8px;font-size:.78rem}}.ch a{{font-size:.78rem;color:{th.BLUE};text-decoration:none;white-space:nowrap}}"
       f"table.kv{{width:100%;border-collapse:collapse;font-size:.86rem}}table.kv td,table.kv th{{padding:4px 6px;border-bottom:1px solid {th.GRID}}}"
       f"table.kv td.k{{color:{th.MUTED}}}table.kv td.v{{text-align:right;font-weight:700;color:{th.TEXT};font-variant-numeric:tabular-nums}}"
       f"table.gr th{{color:{th.MUTED};font-weight:600;text-align:right;font-size:.78rem}}table.gr th:first-child,table.gr td:first-child{{text-align:left}}"
       f"table.gr td{{text-align:right;font-variant-numeric:tabular-nums;color:{th.TEXT}}}"
       f".plain{{font-size:.8rem;color:{th.MUTED};margin-top:6px;line-height:1.5}}.plain b{{color:{th.BLUE};border:1px solid {th.BLUE};border-radius:4px;padding:0 5px;margin-right:6px;font-size:.72rem}}"
       "</style>")
st.markdown(CSS, unsafe_allow_html=True)

# ── 選股 ──
import stock_nav as _sn
from symbols import resolve as _resolve
raw = st.text_input("代號或名稱", value=_sn.cur_code("2330"), max_chars=12, label_visibility="collapsed",
                    placeholder="輸入代號或名稱,例如 2330、台積電").strip()
code, _nm = _resolve(raw)
if not code:
    st.warning(f"找不到「{raw}」。請輸入上市櫃的代號或名稱。")
    st.stop()
st.query_params["code"] = code
_sn.set_cur_code(code)
_sn.bar("總覽")
meta, px, fin, rev = load_meta(code), load_px(code), load_fin(code), load_rev(code)
inst, mg, big, plg = load_inst(code), load_margin(code), load_big(code), load_pledge(code)
try:
    ins = load_insider(code)
except Exception:
    ins = pd.DataFrame()
if px.empty:
    st.warning(f"{code} {meta['name']}:本機沒有這檔的日線檔,無法顯示。")
    st.stop()

# ── 報價列 ──
last, prev = px.iloc[-1], px.iloc[-2] if len(px) > 1 else px.iloc[-1]
chg = last.Close - prev.Close
pct = chg / prev.Close * 100 if prev.Close else 0
ttm = fin.eps.tail(4).sum() if len(fin) >= 4 else np.nan
pe = last.Close / ttm if pd.notna(ttm) and ttm > 0 else np.nan
y1 = px.tail(252)
amt20 = (px.Close * px.Volume).tail(20).mean() / 1e8
tags = "".join(f'<span class="tg" style="color:{c};border-color:{c}">{t}</span>' for t, c in meta["tags"])
items = [("成交張數", f"{last.Volume / 1000:,.0f}"), ("本益比(近四季)", "—" if pd.isna(pe) else f"{pe:.1f}"),
         ("近四季 EPS", "—" if pd.isna(ttm) else f"{ttm:.2f}"), ("20 日均成交值", f"{amt20:.2f} 億"),
         ("一年高/低(盤中)", f"{y1.High.max():g} / {y1.Low.min():g}")]
if len(ins) and pd.notna(ins.shares.iloc[-1]):
    items += [("市值", f"{ins.shares.iloc[-1] * last.Close / 1e8:,.0f} 億"), (f"董監持股 {ins.ym.iloc[-1][5:]} 月", f"{ins.pct_dir.iloc[-1]:.1f}%")]
items.append(("資料日期", f"{last.Date:%Y-%m-%d}"))
st.markdown(f'<div class="qb"><div><div class="nm">{code} {meta["name"]}<small>{meta["market"]} · {meta["sector"]}</small>{tags}</div>'
            f'<span class="px" style="color:{col(chg)}">{last.Close:g}</span> <span style="color:{col(chg)};font-weight:800">{chg:+.2f}({pct:+.2f}%)</span></div>'
            + "".join(f'<div class="it"><b>{v}</b><span>{k}</span></div>' for k, v in items) + "</div>", unsafe_allow_html=True)

t_ov, t_rev, t_fin, t_val, t_chip, t_res = st.tabs(["總覽", "月營收", "財務", "估值", "籌碼", "研究與海報"])


def qlab(q: str) -> str:
    return f"{q[2:4]}Q{int(q[5:7]) // 3}"


# ══════════ 總覽 ══════════
with t_ov:
    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        if fin.empty:
            head("財務摘要", "沒有季報資料")
        else:
            f8, r0 = fin.tail(8), fin.iloc[-1]
            ly = fin.iloc[-5] if len(fin) >= 5 else None
            head("財務摘要", qlab(r0.q), "財務九宮格", f"財務九宮格?code={code}")
            g = fig_base()
            g.add_bar(x=[qlab(x) for x in f8.q], y=f8.eps, marker_color=[UP if v >= 0 else DN for v in f8.eps], hovertemplate="EPS %{y:.2f}<extra></extra>")
            show(g, "ov_fin")
            dd = lambda k: "" if ly is None or pd.isna(ly[k]) else " " + sp(f"({r0[k] - ly[k]:+.1f} 點)", r0[k] - ly[k])
            st.markdown(kv([("單季 EPS(元)", sp(f"{r0.eps:.2f}", r0.eps)), ("近四季 EPS(元)", "—" if pd.isna(ttm) else f"{ttm:.2f}"),
                            ("毛利率", f"{r0.gm:.1f}%{dd('gm')}"), ("營業利益率", f"{r0.om:.1f}%{dd('om')}"), ("淨利率", f"{r0.nm:.1f}%{dd('nm')}")]), unsafe_allow_html=True)
            n_pos = int((fin.om.iloc[::-1] > 0).cumprod().sum())
            msg = f"圖是近 8 季的單季 EPS。本業(營業利益率)" + (f"已經連 {n_pos} 季為正" if n_pos else "這一季是虧的")
            if ly is not None:
                msg += f";毛利率比去年同季{'高' if r0.gm >= ly.gm else '低'} {abs(r0.gm - ly.gm):.1f} 個百分點"
            if r0.nm - r0.om > 5:
                msg += f"。淨利率比營業利益率高 {r0.nm - r0.om:.1f} 點,獲利有一部分不是本業賺的"
            plain(msg + "。括號是和去年同季比。")
    with c2, st.container(border=True):
        if rev.empty:
            head("營收", "沒有月營收資料")
        else:
            r24, m0 = rev.tail(24), rev.iloc[-1]
            hi12 = rev.rev.rolling(12, min_periods=12).max()
            head("營收", m0.ym, "月營收預測", "月營收預測")
            g = fig_base()
            g.add_bar(x=r24.ym, y=r24.rev, marker_color=[UP if (pd.notna(hi12[i]) and rev.rev[i] >= hi12[i]) else th.BLUE for i in r24.index],
                      hovertemplate="%{y:.2f} 億<extra></extra>")
            g.update_xaxes(nticks=6)
            show(g, "ov_rev")
            ytd = rev[rev.ym.str[:4] == m0.ym[:4]]
            lyr = rev[rev.ym.isin([f"{int(x[:4]) - 1}{x[4:]}" for x in ytd.ym])]
            cum = (ytd.rev.sum() / lyr.rev.sum() - 1) * 100 if len(lyr) == len(ytd) and lyr.rev.sum() else np.nan
            st.markdown(kv([("單月營收(億)", f"{m0.rev:.2f}"), ("單月年增率", sp(f"{m0.yoy:+.1f}%", m0.yoy)),
                            ("今年累計年增率", "—" if pd.isna(cum) else sp(f"{cum:+.1f}%", cum))]), unsafe_allow_html=True)
            r6 = rev.tail(7).copy()
            r6["mom"] = r6.rev.pct_change() * 100
            st.markdown(grid(["月份", "營收(億)", "月增", "年增"], [[r.ym, f"{r.rev:.2f}", sp(f"{r.mom:+.1f}%", r.mom), sp(f"{r.yoy:+.1f}%", r.yoy)]
                                                           for r in r6.tail(6).iloc[::-1].itertuples()]), unsafe_allow_html=True)
            n_hi = int((rev.rev.tail(12).values >= hi12.tail(12).values).sum())
            plain(f"藍柱是月營收,紅柱是創近 12 個月新高的月份(近一年有 {n_hi} 個月)。公司每月 10 日前公布上個月營收。")
    with c3, st.container(border=True):
        if inst.empty:
            head("三大法人", "沒有法人資料")
        else:
            i20, i0 = inst.tail(20), inst.iloc[-1]
            head("三大法人", f"{i0.date:%Y-%m-%d}", "籌碼分析", "籌碼分析儀表板")
            g = fig_base()
            for nm_, c_ in (("外資", th.BLUE), ("投信", th.GOLD), ("自營商", th.PURPLE)):
                g.add_bar(x=i20.date, y=i20[nm_], name=nm_, marker_color=c_, hovertemplate=nm_ + " %{y:,.0f} 張<extra></extra>")
            g.update_layout(barmode="relative", showlegend=True, legend=dict(orientation="h", y=1.18, x=0, font=dict(size=10)))
            show(g, "ov_inst")
            s5, s20 = inst.tail(5).sum(numeric_only=True), i20.sum(numeric_only=True)
            st.markdown(grid(["(張)", "外資", "投信", "自營商"],
                             [[lab] + [sp(f"{v[k]:+,.0f}", v[k]) for k in ("外資", "投信", "自營商")] for lab, v in (("最新一天", i0), ("5 日累計", s5), ("20 日累計", s20))]),
                        unsafe_allow_html=True)
            pm = px.set_index("Date").Close
            st.markdown(grid(["日期", "收盤", "外資", "投信", "自營商"],
                             [[f"{r.date:%m-%d}", f"{pm.get(r.date, np.nan):g}", sp(f"{r.外資:+,.0f}", r.外資), sp(f"{r.投信:+,.0f}", r.投信), sp(f"{r.自營商:+,.0f}", r.自營商)]
                              for r in inst.tail(5).iloc[::-1].itertuples()]), unsafe_allow_html=True)
            plain("柱子是近 20 日每天的買賣超(張),往上是買超。外資=外國機構、投信=國內基金、自營商=券商自己的部位(含避險)。")
    with st.container(border=True):
        if ins.empty:
            head("內部人持股增減", "還沒有這檔的資料")
            plain("資料來自公開資訊觀測站每月的股權異動彙總表,由排程抓進本機;這一檔目前不在快取裡。")
        else:
            i36, il = ins.tail(36), ins.iloc[-1]
            s6, s12 = ins.tail(6), ins.tail(12)
            head("內部人持股增減", f"董事、監察人每月增加/減少的股數,加上經理人月底持股的變動 · 申報至 {il.ym}", "", "")
            st.markdown('<div style="font-size:.86rem;margin:2px 0 0">'
                        + f'董監近 6 個月淨增減 {sp(f"{s6.net_amt.sum():+,.0f} 萬", s6.net_amt.sum())}({s6.net_k.sum():+,.0f} 張)　'
                        + f'近 12 個月 {sp(f"{s12.net_amt.sum():+,.0f} 萬", s12.net_amt.sum())}({s12.net_k.sum():+,.0f} 張)　'
                        + f'董監持股 {il.pct_dir:.1f}%' + (f'(一年前 {ins.pct_dir.iloc[-13]:.1f}%)' if len(ins) >= 13 else "")
                        + (f'　經理人持股近 12 個月 {sp(f"{s12.mgr_chg_k.sum():+,.0f} 張", s12.mgr_chg_k.sum())}' if s12.mgr_chg_k.notna().any() else "")
                        + (f'　10% 大股東 {sp(f"{s12.big_chg_k.sum():+,.0f} 張", s12.big_chg_k.sum())}' if s12.big_chg_k.notna().any() and s12.big_chg_k.abs().sum() > 0 else "")
                        + "</div>", unsafe_allow_html=True)
            show(insider_fig(ins, load_mprice(code)), "ov_ins")
            plain("白線是月底收盤;紅色是那個月淨增加、綠色是淨減少,圓點=董監合計、菱形=經理人,點越大估計金額越大,最大的幾個月拉框標示。下面的柱子是每月增加(往上)和減少(往下)的估計金額,深色董監、淺色經理人。"
                  "官方彙總表只有合計,沒有逐人和職稱,也分不出是市場買賣、贈與還是信託;經理人是用月底持股前後相減算的,人員異動也會造成變動,兼任董事的人可能和董監重複。"
                  "金額是股數乘當月平均收盤價估的。公司每月 15 日前申報上個月,灰色區塊是還沒申報的月份。")
    c4, c5, c6 = st.columns(3)
    with c4, st.container(border=True):
        head("籌碼", f"{mg.date.iloc[-1]:%Y-%m-%d}" if len(mg) else "", "大戶籌碼週報", "大戶籌碼週報")
        rows = []
        if len(mg):
            mb, m20 = mg.margin_balance.iloc[-1], mg.margin_balance.iloc[-1] - mg.margin_balance.iloc[-21] if len(mg) > 21 else np.nan
            g = fig_base()
            g.add_scatter(x=mg.date.tail(120), y=mg.margin_balance.tail(120), mode="lines", line=dict(color=th.GOLD, width=2), hovertemplate="融資 %{y:,.0f} 張<extra></extra>")
            show(g, "ov_mg")
            rows += [("融資餘額(張)", f"{mb:,.0f}"), ("融資 20 日增減(張)", sp(f"{m20:+,.0f}", m20)), ("融券餘額(張)", f"{mg.short_balance.iloc[-1]:,.0f}")]
        if len(big):
            b0 = big.iloc[-1]
            b4 = big.iloc[-5] if len(big) >= 5 else None
            rows.append((f"大戶持股(400 張以上){b0.date:%m/%d}", f"{b0.big:.2f}%"))
            if b4 is not None:
                rows += [("大戶 4 週變化", sp(f"{b0.big - b4.big:+.2f} 個百分點", b0.big - b4.big)),
                         ("股東人數 4 週", sp(f"{(b0.holders / b4.holders - 1) * 100:+.1f}%", -(b0.holders / b4.holders - 1)))]
        st.markdown(kv(rows) if rows else "沒有融資與集保資料", unsafe_allow_html=True)
        plain("線是近 120 日的融資餘額。融資=散戶借錢買股,餘額增加代表借錢買的人變多;大戶持股增加、股東人數減少,代表股票往少數人手上集中。")
    with c5, st.container(border=True):
        head("內部人設質", "董監、經理人、大股東把股票拿去質押", "", "")
        if plg.empty:
            st.markdown(kv([("2014 年以來的設質公告", "0 筆")]), unsafe_allow_html=True)
        else:
            y = plg[plg.dt >= plg.dt.max() - pd.Timedelta(days=365)]
            cum = plg.groupby("who").cum.last()
            st.markdown(kv([("近一年設質(張)", f"{y.pledge.sum():,.0f}"), ("近一年解質(張)", f"{y.release.sum():,.0f}"),
                            ("目前還在質押的人數", f"{int((cum > 0).sum())}"), ("目前累積設質(張)", f"{cum.sum():,.0f}")]), unsafe_allow_html=True)
            st.markdown(grid(["異動日", "身份", "姓名", "設質", "解質"],
                             [[f"{r.dt:%Y-%m-%d}", r.role[:8], str(r.who)[:8], f"{r.pledge:,.0f}", f"{r.release:,.0f}"] for r in plg.tail(6).iloc[::-1].itertuples()]),
                        unsafe_allow_html=True)
        plain("設質=把股票押給銀行借錢,逐筆公告。董監每月增減在上面那張圖。")
    with c6, st.container(border=True):
        head("研究與海報", "這檔已經做過的", "財經報", "財經報")
        ps = sorted(D.glob(f"papers/{code}*.html"), reverse=True)
        if ps:
            st.markdown(grid(["類型", "日期"], [["海報" if "海報" in p.stem else "報紙期刊", p.stem.split("_")[-1]] for p in ps[:6]]), unsafe_allow_html=True)
        else:
            st.markdown(kv([("海報/報紙期刊", "還沒有")]), unsafe_allow_html=True)
        links = [("公司快照", f"公司快照?code={code}"), ("估值前瞻(本益比河流)", "估值前瞻"), ("個股戰情室(技術線+五軌)", "個股戰情室"),
                 ("券商觀點", "券商觀點"), ("法說行事曆", "法說行事曆"), ("新聞與情緒", "新聞分析")]
        st.markdown(kv([(k, f'<a href="{h}" target="_self" style="color:{th.BLUE};text-decoration:none">打開 →</a>') for k, h in links]), unsafe_allow_html=True)
        plain("最新一張海報在上面的「研究與海報」分頁可以直接看。最上面那一排是這檔股票的其他細節頁,切過去會帶著代號。")

# ══════════ 月營收 ══════════
with t_rev:
    if rev.empty:
        st.info("沒有月營收資料。")
    else:
        g = fig_base(260)
        g.add_bar(x=rev.ym, y=rev.rev, marker_color=th.BLUE, hovertemplate="%{y:.2f} 億<extra></extra>")
        st.caption(f"月營收(億),{rev.ym.iloc[0]}~{rev.ym.iloc[-1]}")
        show(g, "rev_all")
        g = fig_base(200)
        g.add_bar(x=rev.ym, y=rev.yoy, marker_color=[UP if v >= 0 else DN for v in rev.yoy.fillna(0)], hovertemplate="年增 %{y:+.1f}%<extra></extra>")
        st.caption("單月年增率(%)")
        show(g, "rev_yoy")
        t = rev.iloc[::-1].copy()
        t["mom"] = rev.rev.pct_change().iloc[::-1] * 100
        st.dataframe(t.rename(columns={"ym": "月份", "rev": "營收(億)", "yoy": "年增%", "mom": "月增%"}).round(2), hide_index=True, width="stretch")

# ══════════ 財務 ══════════
with t_fin:
    if fin.empty:
        st.info("沒有季報資料。")
    else:
        a, b = st.columns(2)
        with a:
            g = fig_base(260)
            for k, nm_, c_ in (("gm", "毛利率", th.BLUE), ("om", "營業利益率", th.GOLD), ("nm", "淨利率", th.PURPLE)):
                g.add_scatter(x=[qlab(x) for x in fin.q], y=fin[k], name=nm_, mode="lines+markers", line=dict(color=c_, width=2), marker=dict(size=5),
                              hovertemplate=nm_ + " %{y:.1f}%<extra></extra>")
            g.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)))
            st.caption("三率(%)")
            show(g, "fin_m")
        with b:
            g = fig_base(260)
            g.add_bar(x=[qlab(x) for x in fin.q], y=fin.eps, marker_color=[UP if v >= 0 else DN for v in fin.eps], hovertemplate="EPS %{y:.2f}<extra></extra>")
            st.caption("單季 EPS(元)")
            show(g, "fin_e")
        st.dataframe(fin.iloc[::-1][["q", "rev", "gm", "om", "nm", "eps"]].rename(
            columns={"q": "季度", "rev": "營收(億)", "gm": "毛利率%", "om": "營益率%", "nm": "淨利率%", "eps": "EPS"}), hide_index=True, width="stretch")

# ══════════ 估值 ══════════
with t_val:
    V = load_val(code)
    if not V.get("ok"):
        st.info("沒有季報 EPS,估值算不出來。")
    else:
        VA, band, NY, RV = V["A"], V["band"], V["NY"], V["RV"]
        core_dead = VA["nonop_pct"] >= 40 and VA["ttm_core"] <= 0
        scale = VA["ttm_core"] / VA["ttm"] if (VA["nonop_pct"] >= 40 and not core_dead and VA["ttm"]) else 1.0
        trough = bool(VA.get("yr_avg_eps") and VA["yr_avg_eps"] > 0 and VA["ttm"] < 0.4 * VA["yr_avg_eps"])
        pe_now = last.Close / VA["ttm"] if VA["ttm"] > 0 else None
        va, vb, vc = st.columns(3)
        with va, st.container(border=True):
            head("本益比位置", "對比自己近 3 年", "估值前瞻", f"估值前瞻?code={code}")
            if band and pe_now:
                lo_, hi_ = min(band["P25"], pe_now) * 0.8, max(band["P75"], pe_now) * 1.15
                g = fig_base(110)
                g.add_bar(y=[""], x=[band["P75"] - band["P25"]], base=[band["P25"]], orientation="h", marker_color=f"rgba({th.ACC_RGB},0.35)",
                          hovertemplate=f"近 3 年中間一半的月份:{band['P25']}~{band['P75']} 倍<extra></extra>")
                g.add_scatter(x=[band["P50"]], y=[""], mode="markers", marker=dict(symbol="line-ns", size=30, line=dict(width=2, color=th.MUTED)),
                              hovertemplate=f"中位數 {band['P50']} 倍<extra></extra>")
                g.add_scatter(x=[pe_now], y=[""], mode="markers+text", marker=dict(size=15, color=th.TEXT, line=dict(width=2, color=th.CARD)),
                              text=[f"現在 {pe_now:.1f} 倍"], textposition="top right" if pe_now < band["P25"] else "top left" if pe_now > band["P75"] else "top center", textfont=dict(size=12, color=th.TEXT),
                              hovertemplate=f"現在 {pe_now:.1f} 倍<extra></extra>")
                g.update_layout(hovermode="closest", bargap=0.55)
                g.update_xaxes(range=[lo_, hi_], ticksuffix=" 倍")
                show(g, "val_pos")
            st.markdown(kv([("現在本益比", "—" if not pe_now else f"{pe_now:.1f} 倍"), ("近四季 EPS(元)", sp(f"{VA['ttm']:.2f}", VA["ttm"])),
                            ("其中本業(估)", f"{VA['ttm_core']:.2f}(業外約占 {VA['nonop_pct']}%)"),
                            ("近 3 年 25 / 50 / 75 分位", "樣本不足" if not band else f"{band['P25']} / {band['P50']} / {band['P75']} 倍")]), unsafe_allow_html=True)
            if not pe_now:
                msg = "近四季 EPS 是負的,沒有本益比"
            elif not band:
                msg = "歷史本益比的樣本不夠(虧損期太長或上市不久),只能看現在這個數字"
            else:
                where = ("低於 25 分位,在自己近 3 年偏低的那四分之一" if pe_now < band["P25"] else "在 25 分位到中位數之間" if pe_now < band["P50"]
                         else "在中位數到 75 分位之間" if pe_now <= band["P75"] else "高於 75 分位,在自己近 3 年偏高的那四分之一")
                msg = f"色塊是近 3 年中間一半月份的本益比範圍,直線是中位數,圓點是現在:{pe_now:.1f} 倍,{where}"
            if VA["nonop_pct"] >= 40:
                msg += f"。近四季獲利約 {VA['nonop_pct']}% 不是本業賺的,帳面本益比會顯得比實際便宜"
            if trough:
                msg += f"。近四季 EPS 不到歷史年均 {VA['yr_avg_eps']} 元的四成,獲利在谷底時本益比會虛高"
            if NY.get("ok") and NY["peak"]:
                msg += "。獲利在高峰(見右邊),景氣循環股這時本益比最低,偏低不代表便宜"
            plain(msg + "。")
        with vb, st.container(border=True):
            head(f"{VA['year']} 年三情境", f"已實現 {VA['n_done']} 季 {VA['realized']} 元+外推 {VA['n_left']} 季", "", "")
            if core_dead:
                st.markdown(kv([(k, f"{VA['scen'][k]:.2f} 元") for k in ("保守", "基準", "樂觀")]), unsafe_allow_html=True)
                plain(f"本業近四季是虧的(估 {VA['ttm_core']:.2f} 元),帳面 EPS 靠業外撐著,拿 EPS 乘本益比這個算法不適用,所以不列價位。")
            elif band:
                st.markdown(grid(["情境", "全年 EPS", "×25 分位", "×中位數", "×75 分位"],
                                 [[k, f"{VA['scen'][k]:.2f}"] + [f"{VA['scen'][k] * scale * band[p]:,.1f}" for p in ("P25", "P50", "P75")]
                                  for k in ("保守", "基準", "樂觀")]), unsafe_allow_html=True)
                plain("三個情境只差在今年剩下幾季怎麼推:基準=最近兩季平均;保守=近四季平均和「近兩季打 85 折」取低的;樂觀=近兩季加 15%。"
                      f"右邊三欄是 EPS 乘上自己近 3 年本益比的分位,意思是「市場過去給過的價位範圍」,不是目標價。現價 {last.Close:g}。"
                      + (f"業外占比高,價位已經改用本業比例({scale:.2f})折算。" if scale < 1 else ""))
            else:
                st.markdown(kv([(k, f"{VA['scen'][k]:.2f} 元") for k in ("保守", "基準", "樂觀")]), unsafe_allow_html=True)
                plain("歷史本益比樣本不足,只列情境 EPS,不換算價位。")
        with vc, st.container(border=True):
            if NY.get("ok"):
                head(f"{NY['year']} 年情境(下修思考)", f"算到 {NY['last_q'][:7]} 這一季", "", "")
                st.markdown(grid(["情境", "EPS", "現價隱含本益比"],
                                 [[r["情境"], f"{r['EPS']:.2f}", "—" if r["本益比"] is None else f"{r['本益比']:.1f} 倍"] for r in V["rows"]]), unsafe_allow_html=True)
                msg = ";".join(f"{r['情境']}={r['怎麼算']}" for r in V["rows"]) + "。由好到壞,每一列只改一個假設;這是壓力測試,不是預測"
                if NY["peak"]:
                    msg += (f"。🏔 獲利高峰:最近兩季營益率 {NY['opm_now']}%,比近 12 季中位數 {NY['opm_med']}% 高 {NY['gap']} 點,"
                            + ("前年是虧損" if (NY["eps_y2"] or 0) <= 0 else f"近四季 EPS 是前年全年 {NY['eps_y2']} 元的 {NY['ttm'] / NY['eps_y2']:.1f} 倍"))
                plain(msg + "。")
            else:
                head("明年情境(下修思考)", "這一檔不列", "", "")
                plain((NY.get("why") or "季報不到 6 季,或缺毛利率、營益率,算不出來") + "。")
        with st.container(border=True):
            if RV:
                import pe_river as PR
                head("本益比河流圖", f"近 {RV['years']:.0f} 年 · 未還原股價 · 資料到 {RV['last']:%Y-%m-%d}", "估值前瞻(可改年數)", f"估值前瞻?code={code}")
                show(PR.figure(RV, meta["name"], title=" "), "val_river")
                plain((f"{RV['last']:%m/%d} 收盤 {RV['close']:,.1f}、近四季 EPS {RV['ttm']:.2f},本益比 {RV['pe']:.1f} 倍,在自己近 {RV['years']:.0f} 年排第 {RV['rank']:.0f} 百分位"
                       if RV["pe"] else "近四季 EPS 是負的,沒有本益比")
                      + f";歷史最低 {RV['pe_min']:.1f} 倍({RV['pe_min_d']:%Y/%m})、最高 {RV['pe_max']:.1f} 倍({RV['pe_max_d']:%Y/%m})。"
                      "河道=每天的近四季 EPS × 這檔自己歷史本益比的第 5/25/50/75/95 百分位,顏色越深本益比越高,粗線是股價。EPS 往下修,整條河會一起往下移。"
                      + (f"這段期間有 {RV['loss_days']} 個交易日近四季 EPS 是負的,那幾段沒有河道。" if RV["loss_days"] else "")
                      + "這張圖讀的是上次在「估值前瞻」抓下來的檔,這一頁不發請求,日期比報價列舊是正常的。")
            else:
                head("本益比河流圖", "這一檔還沒有資料", "到估值前瞻抓", f"估值前瞻?code={code}")
                plain("河流圖要 20 年的未還原股價和單季 EPS,只有在「估值前瞻」開過這一檔才會抓下來存著;這一頁只讀本機、不發請求。上市不到兩年或長期虧損的也畫不出來。")

# ══════════ 籌碼 ══════════
with t_chip:
    a, b = st.columns(2)
    with a:
        if len(inst):
            i60 = inst.tail(60)
            g = fig_base(260)
            for nm_, c_ in (("外資", th.BLUE), ("投信", th.GOLD), ("自營商", th.PURPLE)):
                g.add_bar(x=i60.date, y=i60[nm_], name=nm_, marker_color=c_, hovertemplate=nm_ + " %{y:,.0f} 張<extra></extra>")
            g.update_layout(barmode="relative", showlegend=True, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)))
            st.caption("三大法人買賣超(張),近 60 日")
            show(g, "chip_i")
        if len(big):
            g = fig_base(220)
            g.add_scatter(x=big.date, y=big.big, mode="lines+markers", line=dict(color=th.BLUE, width=2), marker=dict(size=4), hovertemplate="大戶 %{y:.2f}%<extra></extra>")
            st.caption("大戶(400 張以上)持股比例(%),每週")
            show(g, "chip_b")
    with b:
        if len(mg):
            g = fig_base(260)
            g.add_scatter(x=mg.date.tail(250), y=mg.margin_balance.tail(250), mode="lines", line=dict(color=th.GOLD, width=2), hovertemplate="融資 %{y:,.0f} 張<extra></extra>")
            st.caption("融資餘額(張),近 250 日")
            show(g, "chip_m")
            g = fig_base(220)
            g.add_scatter(x=mg.date.tail(250), y=mg.short_balance.tail(250), mode="lines", line=dict(color=th.PURPLE, width=2), hovertemplate="融券 %{y:,.0f} 張<extra></extra>")
            st.caption("融券餘額(張),近 250 日")
            show(g, "chip_s")
    if len(inst):
        st.dataframe(inst.tail(20).iloc[::-1].assign(date=lambda z: z.date.dt.strftime("%Y-%m-%d")).rename(columns={"date": "日期"}).round(0), hide_index=True, width="stretch")

# ══════════ 研究與海報 ══════════
with t_res:
    ps = sorted(D.glob(f"papers/{code}海報_*.html"), reverse=True)
    if not ps:
        st.info(f"{code} {meta['name']} 還沒有做過海報。")
    else:
        st.caption(f"最新一張海報:{ps[0].name}(共 {len(ps)} 張;其餘在「財經報」頁)")
        import streamlit.components.v1 as components
        components.html(ps[0].read_text(encoding="utf-8"), height=1400, scrolling=True)

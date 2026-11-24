# -*- coding: utf-8 -*-
"""
pe_river.py — 本益比河流圖(個股)
================================================================
畫法:每一天的「近四季 EPS 合計」× 這檔股票自己歷史本益比的幾個分位 = 幾條河道,再把股價疊上去。
      股價在河的哪一層,就是市場現在給它的本益比在自己歷史上的位置。

資料(FinMind 免費端點,一檔兩個請求,快取 20 小時放 data/fundamentals,不進 git):
  TaiwanStockFinancialStatements 的單季 EPS(2005 年起)、TaiwanStockPrice 的未還原收盤價。
  一定要用未還原價:系統日線是還息還原價,拿它除以當年的 EPS,越早的本益比會被壓得越低。

口徑:
  近四季 EPS 用「當天已經公布」的財報——第 1~3 季加 45 天、年報加 90 天才算公布(法定期限)。
  近四季 EPS ≤ 0 的日子沒有本益比,河道在那一段斷掉。
  減資、分割、面額變更會讓股價跳空而 EPS 還混著新舊股數,前後一年的河道會失真;flags 列出股價單日跳動超過 15% 的日子
  (大額除權息也會被列進來,那種不影響河道)。
用法:
  res = pe_river.series("2330", years=10);  fig = pe_river.figure(res, "台積電")
  python -X utf8 pe_river.py 2330        # 印出關鍵數字對帳
"""
from __future__ import annotations

import json
import sys
import time

import pandas as pd
import requests

from pathlib import Path

from fundamentals import FM_URL, FUND_DIR

ROOT = Path(__file__).parent

CACHE_HOURS = 20
QS = (0.05, 0.25, 0.50, 0.75, 0.95)          # 河道分位
PE_CAP = 200                                 # 本益比超過這個當成沒有意義(EPS 接近 0)
JUMP = 0.15                                  # 單日漲跌超過這個=減資、分割、面額變更或大額除權息(漲跌幅限制是 10%)


def _get(dataset: str, code: str, start: str, tag: str, fetch: bool = True) -> list[dict]:
    """自己的快取檔(和 fundamentals._fm 分開:它的快取不分起始日,混用會讓別頁拿到不同長度)。"""
    p = FUND_DIR / f"{code}_river_{tag}.json"

    def stale() -> list[dict]:
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        except Exception:
            return []

    if not fetch:                              # 只讀已經抓過的檔(/個股 用:那一頁不發請求)
        return stale()
    if p.exists() and time.time() - p.stat().st_mtime < CACHE_HOURS * 3600:
        got = stale()
        if got:
            return got
    try:
        import ssl_trust
        ssl_trust.ensure()
        j = requests.get(FM_URL, params={"dataset": dataset, "data_id": code, "start_date": start}, timeout=30).json()
        data = j.get("data", []) if j.get("status") == 200 else []
        if data:
            FUND_DIR.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
    except Exception:
        pass
    return stale()                             # 限流或斷線:用舊的


def series(code: str, years: int = 10, fetch: bool = True) -> dict | None:
    """回傳畫圖和列表要的全部東西;資料不夠回 None。fetch=False 只讀快取檔,沒抓過就回 None。"""
    eps = pd.DataFrame(_get("TaiwanStockFinancialStatements", code, "2005-01-01", "eps", fetch))
    px = pd.DataFrame(_get("TaiwanStockPrice", code, "2005-01-01", "px", fetch))
    if eps.empty or px.empty or "type" not in eps:
        return None
    e = eps[eps["type"] == "EPS"][["date", "value"]].copy()
    e["date"] = pd.to_datetime(e["date"])
    e = e.sort_values("date").drop_duplicates("date").set_index("date")["value"].astype(float)
    ttm = e.rolling(4).sum().dropna()
    if len(ttm) < 8:
        return None
    # 公布日:年報(12 月底)加 90 天,其餘加 45 天
    ok = [d + pd.Timedelta(days=90 if d.month == 12 else 45) for d in ttm.index]
    known = pd.Series(ttm.values, index=pd.DatetimeIndex(ok)).sort_index()

    px["date"] = pd.to_datetime(px["date"])
    c = px.sort_values("date").set_index("date")["close"].astype(float)
    c = c[c > 0]
    df = pd.DataFrame({"close": c})
    df["ttm"] = known.reindex(df.index, method="ffill")
    df = df.dropna(subset=["ttm"])
    start = df.index[-1] - pd.DateOffset(years=years)
    df = df[df.index >= start]
    if len(df) < 250:
        return None
    df["pe"] = (df.close / df.ttm).where((df.ttm > 0) & (df.close / df.ttm < PE_CAP))
    pe = df.pe.dropna()
    if len(pe) < 250:
        return None
    levels = {q: float(pe.quantile(q)) for q in QS}
    for q, lv in levels.items():
        df[f"b{int(q * 100)}"] = (df.ttm * lv).where(df.ttm > 0)
    r = c.pct_change()
    flags = [d.strftime("%Y/%m/%d") for d in r[(r.abs() > JUMP) & (r.index >= start)].index]
    now_pe = float(df.pe.iloc[-1]) if pd.notna(df.pe.iloc[-1]) else None
    return dict(code=code, df=df, levels=levels, flags=flags, years=round((df.index[-1] - df.index[0]).days / 365.25, 1),
                close=float(df.close.iloc[-1]), ttm=float(df.ttm.iloc[-1]), pe=now_pe, last=df.index[-1],
                rank=(float((pe < now_pe).mean() * 100) if now_pe else None),
                pe_min=float(pe.min()), pe_min_d=pe.idxmin(), pe_max=float(pe.max()), pe_max_d=pe.idxmax(),
                eps_q=e.index[-1], loss_days=int((df.ttm <= 0).sum()))


def table(res: dict) -> pd.DataFrame:
    """河道對照表:用「現在的近四季 EPS」換算每一層的股價。"""
    rows = [{"位置": f"歷史最低({res['pe_min_d']:%Y/%m})", "本益比": res["pe_min"]}]
    rows += [{"位置": f"第 {int(q * 100)} 百分位" + ("(中位數)" if q == 0.5 else ""), "本益比": lv}
             for q, lv in res["levels"].items()]
    rows.append({"位置": f"歷史最高({res['pe_max_d']:%Y/%m})", "本益比": res["pe_max"]})
    t = pd.DataFrame(rows)
    t["對應股價"] = t["本益比"] * res["ttm"]
    t["離現價%"] = (t["對應股價"] / res["close"] - 1) * 100
    return t.round({"本益比": 1, "對應股價": 1, "離現價%": 1})


def figure(res: dict, name: str = "", title: str | None = None, price_name: str = "股價(未還原)",
           unit: str = "元", eps_name: str = "近四季 EPS", now_name: str = "現價"):
    import plotly.graph_objects as go

    import ui_theme as T

    df = res["df"]
    keys = [f"b{int(q * 100)}" for q in QS]
    # 河道=同一個藍色由淺到深(本益比由低到高);股價用墨色粗線壓在最上面
    fills = ["rgba(37,99,235,0.16)", "rgba(37,99,235,0.30)", "rgba(37,99,235,0.46)", "rgba(37,99,235,0.64)"]   # 最淺那層也要看得到
    names = [f"{int(QS[i] * 100)}~{int(QS[i + 1] * 100)} 百分位" for i in range(4)]
    fig = go.Figure()
    has = df[keys[0]].notna()
    run = (has != has.shift()).cumsum()[has]                       # 連續有河道的每一段各畫一次(中間缺的留空)
    for n, (_, seg_idx) in enumerate(run.groupby(run).groups.items()):
        seg = df.loc[seg_idx]
        fig.add_trace(go.Scatter(x=seg.index, y=seg[keys[0]], mode="lines", line=dict(width=0, shape="hv"),
                                 hoverinfo="skip", showlegend=False))
        for i in range(4):
            fig.add_trace(go.Scatter(
                x=seg.index, y=seg[keys[i + 1]], mode="lines",
                line=dict(width=0.6, color="rgba(37,99,235,0.55)", shape="hv"),
                fill="tonexty", fillcolor=fills[i], name=names[i], legendgroup=names[i], showlegend=(n == 0),
                customdata=seg[keys[i]], hovertemplate="%{customdata:,.0f} ~ %{y:,.0f}<extra>" + names[i] + "</extra>"))
    fig.add_trace(go.Scatter(
        x=df.index, y=df.close, mode="lines", line=dict(width=2, color=T.TEXT), name=price_name,
        customdata=df[["pe", "ttm"]].values,
        hovertemplate=price_name + " %{y:,.1f}|本益比 %{customdata[0]:.1f} 倍|" + eps_name + " %{customdata[1]:,.2f}<extra></extra>"))
    last = df.index[-1]
    for q, k in zip(QS, keys):                                     # 右邊直接標每條河道的本益比與價位
        y = df[k].iloc[-1]
        if pd.notna(y):
            fig.add_annotation(x=last, y=y, xanchor="left", xshift=6, showarrow=False, align="left",
                               text=f"{res['levels'][q]:.1f} 倍|{y:,.0f}", font=dict(size=11, color=T.MUTED))
    down = res["close"] < float(df.close.tail(60).mean())          # 最近在跌=線在左上方,標籤放左下;反之放左上
    fig.add_annotation(x=last, y=res["close"], ax=-70, ay=45 if down else -45, showarrow=True, arrowhead=0, arrowwidth=1,
                       arrowcolor=T.MUTED, bgcolor="rgba(255,255,255,0.85)" if T.TEXT.upper() == "#1A1D24" else "rgba(4,7,13,0.85)",
                       text=f"<b>{now_name} {res['close']:,.1f}</b>" + (f"({res['pe']:.1f} 倍)" if res["pe"] else ""),
                       font=dict(size=12, color=T.TEXT))
    # 循環股獲利谷底時最上層河道會衝到天上,把股價壓成一條線;縱軸最多看到股價最高點的 1.6 倍
    hi = float(min(max(df.close.max(), df[keys[-1]].max()), df.close.max() * 1.6))
    fig.update_layout(
        title=title or f"{name} {res['code']} 本益比河流圖(近 {res['years']:.0f} 年)——河道=近四季 EPS × 自己歷史本益比的分位",
        height=520, hovermode="x unified", margin=dict(l=10, r=110, t=60, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        yaxis=dict(title=unit, range=[0, hi * 1.05], gridcolor=T.GRID, zeroline=False),
        xaxis=dict(gridcolor=T.GRID))
    return fig


# ══════════════════════════════════════════════════════════════ 大盤(加權指數)
MKT_CSV = ROOT / "data" / "twse_market_pe.csv"          # fetch_twse_pe.py 產的官方月資料
GAP_DAYS = 45                                            # 月底獲利最多往後沿用幾個交易日(超過=那個月的官方資料缺了)
MKT_PE_CAP = 40                                          # 大盤本益比超過這個=獲利崩掉(2009~2010 年衝到 100 倍以上),不列入分位
BWIBBU = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"


def _index() -> pd.Series:
    """加權指數日收盤:長歷史(data/_twii_long.csv,1997 年起)接每天更新的 benchmark_TWII.csv。"""
    parts = []
    for f in ("_twii_long.csv", "benchmark_TWII.csv"):
        p = ROOT / "data" / f
        if p.exists():
            parts.append(pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0].dropna())
    s = pd.concat(parts)
    return s[~s.index.duplicated(keep="last")].sort_index()


def _bwibbu(day: pd.Timestamp) -> pd.DataFrame:
    """證交所某一天全部上市個股的收盤價與本益比(官方查詢介面,一天一個請求)。"""
    import ssl_trust
    ssl_trust.ensure()
    j = requests.get(BWIBBU, params={"date": day.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30).json()
    if j.get("stat") != "OK" or not j.get("data"):
        return pd.DataFrame()
    d = pd.DataFrame(j["data"], columns=j["fields"])
    out = pd.DataFrame({"code": d["證券代號"].astype(str).str.strip(),
                        "close": pd.to_numeric(d["收盤價"].astype(str).str.replace(",", ""), errors="coerce"),
                        "pe": pd.to_numeric(d["本益比"].astype(str).str.replace(",", ""), errors="coerce")})
    return out.dropna(subset=["close"])


def nowcast(base: pd.Timestamp, last: pd.Timestamp, fetch: bool = True) -> dict | None:
    """官方月資料之後才公布的財報,估它讓大盤獲利變了多少。
    做法:base(上次官方月底)和 last(最新交易日)各抓一次全部個股的本益比,每檔獲利=收盤÷本益比×股數,
    只算兩天都有本益比的個股,回傳獲利總額的比值。股數用現在的(shares_map),兩天相隔不到一個月,影響很小。
    快取在 data/fundamentals;抓不到回 None(頁面就只用官方月底的獲利)。
    fetch=False 只讀快取——頁面用這個,請求由每日排程的 fetch_twse_pe.py 發(家規:更新不靠開頁面觸發)。"""
    p = FUND_DIR / "market_nowcast.json"
    key = f"{base:%Y%m%d}_{last:%Y%m%d}"
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("key") == key:
            return c
    except Exception:
        pass
    if not fetch:
        return None
    try:
        from fundamentals import shares_map
        sh = pd.Series(shares_map(), dtype=float)
        a, b = _bwibbu(base), _bwibbu(last)
        if a.empty or b.empty or sh.empty:
            return None
        m = a.merge(b, on="code", suffixes=("0", "1"))
        m["sh"] = m.code.map(sh)
        m = m.dropna(subset=["sh"])
        cap0 = float((m.close0 * m.sh).sum())
        both = m[(m.pe0 > 0) & (m.pe1 > 0)]
        e0, e1 = float((both.close0 / both.pe0 * both.sh).sum()), float((both.close1 / both.pe1 * both.sh).sum())
        pos0 = m[m.pe0 > 0]
        out = dict(key=key, ratio=e1 / e0, n=int(len(both)), n_all=int(len(m)),
                   pe_bottom_up=cap0 / float((pos0.close0 / pos0.pe0 * pos0.sh).sum()))
        FUND_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out), encoding="utf-8")
        return out
    except Exception:
        return None


def market_series(years: int = 20, fetch: bool = False) -> dict | None:
    """大盤版:官方月底本益比 → 每點獲利(指數÷本益比) → 河道。回傳格式和 series() 一樣,多了 pb/yield 的月資料。"""
    if not MKT_CSV.exists():
        return None
    m = pd.read_csv(MKT_CSV, dtype={"ym": str})
    idx = _index()
    if m.empty or idx.empty:
        return None
    per = idx.index.to_period("M")
    mend = pd.Series(idx.index, index=per).groupby(level=0).last()        # 每個月最後一個交易日
    m["date"] = pd.PeriodIndex(m.ym, freq="M").map(mend)
    m = m.dropna(subset=["date", "pe"]).set_index("date").sort_index()
    m["eps"] = idx.reindex(m.index) / m.pe                                 # 指數每一點對應的獲利
    df = pd.DataFrame({"close": idx})
    df["ttm"] = m.eps.reindex(df.index, method="ffill", limit=GAP_DAYS)      # 缺月份的那一段留空
    df = df[df.index >= m.index[0]]
    base, last = m.index[-1], df.index[-1]
    nc = nowcast(base, last, fetch) if last > base else None
    if nc and pd.notna(df.ttm.iloc[-1]):                                    # 最新一天改用估過新財報的獲利
        df.loc[last, "ttm"] = df.ttm.iloc[-1] * nc["ratio"]
    else:
        nc = None
    start = last - pd.DateOffset(years=years)
    df = df[df.index >= start].copy()
    if len(df) < 250:
        return None
    df["pe"] = df.close / df.ttm
    hist = (df.pe.iloc[:-1] if nc else df.pe).dropna()                     # 分位只用官方口徑的日子
    if len(hist) < 250 or pd.isna(df.pe.iloc[-1]):
        return None
    odd = hist[hist >= MKT_PE_CAP]
    hist = hist[hist < MKT_PE_CAP]
    want = pd.period_range(max(start, m.index[0]), base, freq="M")
    gaps = [str(p) for p in want if p not in set(m.index.to_period("M"))]
    levels = {q: float(hist.quantile(q)) for q in QS}
    for q, lv in levels.items():
        df[f"b{int(q * 100)}"] = df.ttm * lv
    now_pe = float(df.pe.iloc[-1])
    mm = m[m.index >= start]
    return dict(code="", df=df, levels=levels, flags=[], years=round((df.index[-1] - df.index[0]).days / 365.25, 1),
                close=float(df.close.iloc[-1]), ttm=float(df.ttm.iloc[-1]), pe=now_pe, last=last,
                rank=float((hist < now_pe).mean() * 100), pe_min=float(hist.min()), pe_min_d=hist.idxmin(),
                pe_max=float(hist.max()), pe_max_d=hist.idxmax(), eps_q=base, loss_days=0,
                base=base, base_pe=float(m.pe.iloc[-1]), pe_plain=float(df.close.iloc[-1] / m.eps.iloc[-1]),
                nowcast=nc, monthly=mm, gaps=gaps,
                odd=(f"{odd.index[0]:%Y/%m}~{odd.index[-1]:%Y/%m}" if len(odd) else ""), odd_days=int(len(odd)))


def market_trio(res: dict) -> pd.DataFrame:
    """三個官方估值指標(月底值)在這段期間的位置。殖利率越低越貴,讀百分位時要反過來。"""
    mm, rows = res["monthly"], []
    for col, nm in (("pe", "本益比(倍)"), ("pb", "股價淨值比(倍)"), ("yield", "殖利率(%)")):
        s = mm[col].dropna()
        if col == "pe":
            s = s[(s < MKT_PE_CAP) | (s.index == s.index[-1])]      # 和河道同口徑:獲利崩掉的月份不算
        rows.append({"指標": nm, f"{res['base']:%Y/%m} 月底": s.iloc[-1], "百分位": round(float((s < s.iloc[-1]).mean() * 100)),
                     "中位數": s.median(), "最低": f"{s.min():.2f}({s.idxmin():%Y/%m})", "最高": f"{s.max():.2f}({s.idxmax():%Y/%m})"})
    return pd.DataFrame(rows).round(2)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "market":
        r = market_series(int(sys.argv[2]) if len(sys.argv) > 2 else 20, fetch=True)
        if not r:
            sys.exit("沒有 data/twse_market_pe.csv,先跑 fetch_twse_pe.py")
        nc = r["nowcast"]
        print(f"大盤 到 {r['last']:%Y-%m-%d}|收盤 {r['close']:,.0f}|官方月底({r['base']:%Y-%m-%d})本益比 {r['base_pe']}"
              f"|用月底獲利算現在 {r['pe_plain']:.1f} 倍|"
              + (f"估過新財報(獲利 ×{nc['ratio']:.3f},{nc['n']} 檔)後 {r['pe']:.1f} 倍"
                 f"|自己加總的月底本益比 {nc['pe_bottom_up']:.1f}(對官方 {r['base_pe']})" if nc else "沒有新財報估計"))
        print(f"在近 {r['years']:.0f} 年排第 {r['rank']:.0f} 百分位")
        print(table(r).to_string(index=False))
        print(market_trio(r).to_string(index=False))
        sys.exit(0)
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    r = series(code)
    if not r:
        sys.exit(f"{code}: 資料不夠(上市太短、長期虧損,或 FinMind 抓不到)")
    print(f"{code} 到 {r['last']:%Y-%m-%d}|收盤 {r['close']}|近四季 EPS {r['ttm']:.2f}(最新一季 {r['eps_q']:%Y-%m})|"
          f"本益比 {r['pe']:.1f} 倍,在近 {r['years']:.0f} 年排第 {r['rank']:.0f} 百分位")
    print(table(r).to_string(index=False))
    print("虧損天數:", r["loss_days"], "|股價單日跳動超過 15%(減資、分割或大額除權息):", r["flags"] or "無")

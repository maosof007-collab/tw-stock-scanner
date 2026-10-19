# -*- coding: utf-8 -*-
"""
attention_scan.py — 今日強勢資金(EOD 成交注意力版)
=================================================================
起因(2026-10-19):用戶看到「台股成交注意力」盤中掃描器,要求做類似的:
今天強勢資金+隔日沖警戒,白底介面,LINE 好讀版。
我們沒有盤中 5 分K,做 EOD 誠實版——核心同一套:**錢的占比不會騙人**:
  占比倍數 = 今日成交額佔全市場比 ÷ 自己 20 日平均佔比(資金湧入倍率)
  RS = 個股漲幅 − 大盤漲幅(相對強弱)
  收盤位置 = (收−低)/(高−低)(尾盤誰在守)
隔日沖警戒:迴轉率雷達 🔪(漲≥8%+量比≥2.5)或 高迴轉率 — 明天的賣壓名單。
產出:data/_attention.csv + data/attention/att_{date}.html(白底)+ LINE 摘要文字。
"""
from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
OUT_DIR = D / "attention"
OUT_DIR.mkdir(exist_ok=True)


def scan(min_amount: float = 1e8, top: int = 20) -> dict:
    bm = pd.read_csv(D / "benchmark_TWII.csv", usecols=["Date", "Close"]).dropna()
    mkt_r = (bm["Close"].iloc[-1] / bm["Close"].iloc[-2] - 1) * 100
    rows, total_amt = [], 0.0
    for f in glob.glob(str(D / "[0-9]*.csv")):
        name = Path(f).stem
        code = name.split(".")[0]
        if not (code.isdigit() and len(code) == 4):
            continue
        try:
            px = pd.read_csv(f, usecols=["Date", "Open", "High", "Low", "Close", "Volume"]).dropna()
        except Exception:
            continue
        if len(px) < 25:
            continue
        c, v = px["Close"].astype(float), px["Volume"].astype(float)
        amt = c * v
        a0 = float(amt.iloc[-1])
        total_amt += a0
        if a0 < min_amount:
            continue
        chg = (c.iloc[-1] / c.iloc[-2] - 1) * 100
        volr = float(v.iloc[-1] / max(v.shift(1).tail(21).head(20).mean(), 1))
        hi, lo = float(px["High"].iloc[-1]), float(px["Low"].iloc[-1])
        pos = (c.iloc[-1] - lo) / (hi - lo) * 100 if hi > lo else 50.0
        hi20 = bool(c.iloc[-1] >= c.tail(20).max())
        rows.append({"代碼": code, "日期": px["Date"].iloc[-1], "收盤": round(c.iloc[-1], 2),
                     "漲跌%": round(chg, 2), "RS": round(chg - mkt_r, 2),
                     "額(億)": round(a0 / 1e8, 2), "_amt": a0,
                     "_amt20": float(amt.tail(21).head(20).mean()),
                     "量比": round(volr, 2), "收位%": round(pos, 0),
                     "創20日高": "✓" if hi20 else ""})
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    # 占比與占比倍數(資金湧入倍率)
    df["占比%"] = df["_amt"] / total_amt * 100
    df["占比倍數"] = (df["_amt"] / total_amt) / (df["_amt20"] / total_amt).clip(lower=1e-9)
    df["占比倍數"] = df["占比倍數"].clip(upper=15).round(2)
    df["占比%"] = df["占比%"].round(2)
    # 名稱
    try:
        import symbols
        df["名稱"] = [symbols.resolve(c)[1] or "" for c in df["代碼"]]
    except Exception:
        df["名稱"] = ""
    # 迴轉率雷達合併(隔日沖維度)
    df["迴轉率%"], df["隔日沖"] = None, ""
    try:
        t = pd.read_csv(D / "_turnover.csv", dtype=str)
        tv = {r["代碼"]: r for _, r in t.iterrows()}
        for i, r in df.iterrows():
            h = tv.get(r["代碼"])
            if h is not None:
                df.at[i, "迴轉率%"] = h.get("迴轉率%")
                if "🔪" in str(h.get("標記", "")):
                    df.at[i, "隔日沖"] = "🔪"
    except Exception:
        pass
    # 規則版隔日沖:大漲+爆量(即使不在雷達前40)
    df.loc[(df["漲跌%"] >= 8) & (df["量比"] >= 2.5) & (df["隔日沖"] == ""), "隔日沖"] = "⚠"
    # 綜合分(百分位均值:RS/占比倍數/量比/收位)
    for col, w in (("RS", 1), ("占比倍數", 1), ("量比", 1), ("收位%", 1)):
        df[f"_p{col}"] = df[col].rank(pct=True) * 100
    df["分數"] = (df[[c for c in df.columns if c.startswith("_p")]].mean(axis=1)).round(1)
    df = df.sort_values("分數", ascending=False).reset_index(drop=True)
    keep = ["代碼", "名稱", "分數", "漲跌%", "RS", "額(億)", "占比%", "占比倍數",
            "量比", "收位%", "創20日高", "隔日沖", "迴轉率%", "收盤", "日期"]
    df = df[keep]
    df.to_csv(D / "_attention.csv", index=False, encoding="utf-8-sig")
    date = str(df["日期"].iloc[0])[:10]
    meta = {"date": date, "total_amt": total_amt, "mkt_r": mkt_r, "n": len(df)}
    return {"df": df, "meta": meta, "top": df.head(top),
            "surge": df.sort_values("占比倍數", ascending=False).head(10),
            "dt": df[df["隔日沖"] != ""].sort_values("漲跌%", ascending=False).head(15)}


# ---------------------------------------------------------------- 白底 HTML
_CSS = """body{font-family:'Microsoft JhengHei',sans-serif;background:#fff;color:#1a1a1a;
margin:0;padding:24px;max-width:1080px;margin:auto}
h1{font-size:22px;border-bottom:2px solid #1a1a1a;padding-bottom:8px}
h2{font-size:16px;margin:26px 0 8px;color:#333}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}
.card{border:1px solid #e3e3e3;border-radius:8px;padding:10px 16px;background:#fafafa}
.card .k{font-size:12px;color:#888}.card .v{font-size:19px;font-weight:700}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th{background:#f4f4f4;text-align:right;padding:6px 8px;border-bottom:2px solid #ddd;
font-weight:600;color:#555}th:nth-child(-n+2){text-align:left}
td{padding:5px 8px;border-bottom:1px solid #eee;text-align:right;font-variant-numeric:tabular-nums}
td:nth-child(-n+2){text-align:left}
.up{color:#d0342c;font-weight:600}.dn{color:#1a8a4d;font-weight:600}
.hl{background:#fff6e5}.warn{color:#c47f00;font-weight:700}
.note{font-size:12px;color:#999;margin-top:18px;line-height:1.7}"""


def _cell(v, col):
    s = "" if v is None or (isinstance(v, float) and pd.isna(v)) else v
    cls = ""
    if col in ("漲跌%", "RS") and isinstance(v, (int, float)):
        cls = "up" if v > 0 else ("dn" if v < 0 else "")
        s = f"{v:+.2f}"
    return f'<td class="{cls}">{s}</td>'


def _table(df: pd.DataFrame, cols: list[str]) -> str:
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for _, r in df.iterrows():
        tr_cls = ' class="hl"' if r.get("隔日沖") else ""
        body += f"<tr{tr_cls}>" + "".join(_cell(r.get(c), c) for c in cols) + "</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


def save_html(res: dict) -> Path:
    m, top, surge, dt = res["meta"], res["top"], res["surge"], res["dt"]
    cols = ["代碼", "名稱", "分數", "漲跌%", "RS", "額(億)", "占比%", "占比倍數",
            "量比", "收位%", "創20日高", "隔日沖"]
    up_n = int((res["df"]["漲跌%"] > 0).sum())
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>強勢資金 {m['date']}</title><style>{_CSS}</style></head><body>
<h1>📊 今日強勢資金|{m['date']}</h1>
<div class="cards">
<div class="card"><div class="k">大盤</div><div class="v {'up' if m['mkt_r']>0 else 'dn'}">{m['mkt_r']:+.2f}%</div></div>
<div class="card"><div class="k">合格檔數(額≥1億)</div><div class="v">{m['n']}</div></div>
<div class="card"><div class="k">上漲比例</div><div class="v">{up_n}/{m['n']}</div></div>
<div class="card"><div class="k">全市場成交額</div><div class="v">{m['total_amt']/1e8:,.0f} 億</div></div></div>
<h2>💪 強勢資金 Top 20(分數=RS×占比倍數×量比×收位 百分位)</h2>{_table(top, cols)}
<h2>🚀 占比竄升榜(資金湧入倍率 Top 10)</h2>{_table(surge, cols)}
<h2>🔪 隔日沖警戒(明天的賣壓名單——家規:爆量+2~3天禁入)</h2>
{_table(dt, cols) if len(dt) else '<p>今日無警戒檔。</p>'}
<p class="note">EOD 版成交注意力:占比倍數=今日佔全市場成交比 ÷ 自身20日均佔比(錢湧進來幾倍);
收位=收盤在當日高低區間的位置(尾盤誰在守)。黃底列=隔日沖警戒。
🔪=迴轉率雷達警戒 ⚠=漲≥8%+量比≥2.5。資料=收盤日K,非盤中;研究用非投資建議。
TW-BACKTEST attention v1</p></body></html>"""
    p = OUT_DIR / f"att_{m['date'].replace('-', '')}.html"
    p.write_text(html, encoding="utf-8")
    return p


# ---------------------------------------------------------------- LINE 摘要
def line_text(res: dict, n: int = 5) -> str:
    m, top, dt = res["meta"], res["top"], res["dt"]
    L = [f"💪 強勢資金 {m['date'][5:]}(大盤{m['mkt_r']:+.1f}%)"]
    for _, r in top.head(n).iterrows():
        L.append(f"{r['代碼']}{r['名稱']} {r['漲跌%']:+.1f}% 占比x{r['占比倍數']}"
                 f" 量{r['量比']}x{' ' + r['隔日沖'] if r['隔日沖'] else ''}")
    if len(dt):
        L.append("🔪 隔日沖警戒(明日賣壓,禁入):")
        L.append("、".join((dt["代碼"] + dt["名稱"]).head(8).tolist()))
    L.append("白底完整版:App → 強勢資金頁")
    return "\n".join(L)


def run_daily_step() -> str:
    res = scan()
    if not res:
        return "attention: 無資料"
    p = save_html(res)
    return f"attention: {len(res['df'])}檔 → {p.name}"


if __name__ == "__main__":
    r = scan()
    if r:
        print(save_html(r))
        print(line_text(r))

"""
weekly_review.py — 每週操作檢視 SOP(仿使用者的 BEST MATCH 節點流)
=================================================================
決策日誌:data/decision_journal.csv(date,code,name,ref_close,thesis,status)
每週(排程週六 09:00)自動跑四關:
  ① 組合風險全檢:各持股報酬/煞車距離(收盤-2ATR)/族群集中度
  ② 產業輪動:本週族群強弱 + 營收雷達方向
  ③ 決策回顧:本週買進的檔,系統當時有無背書(訊號/判讀)
  ④ 論點盤點:THESIS 還成不成立(營收/法人/RS 對照)
→ 週檢視報告存文章庫(mode=週檢視)+ git 上雲。
用法:
  python weekly_review.py --buy 2618 --thesis "航空Q3旺季+油價回落"
  python weekly_review.py --close 2618 --note "停利出場"
  python weekly_review.py            # 產生本週檢視報告
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd
from twtime import now_tw

ROOT = Path(__file__).parent
JOURNAL = ROOT / "data" / "decision_journal.csv"


def _load() -> pd.DataFrame:
    if JOURNAL.exists():
        return pd.read_csv(JOURNAL, encoding="utf-8-sig", dtype={"code": str})
    return pd.DataFrame(columns=["date", "code", "name", "ref_close", "thesis",
                                 "status", "close_date", "close_note"])


def _save(df: pd.DataFrame) -> None:
    df.to_csv(JOURNAL, index=False, encoding="utf-8-sig")


def _px(code: str) -> pd.DataFrame | None:
    for suf in (".TW.csv", ".TWO.csv"):
        p = ROOT / "data" / f"{code}{suf}"
        if p.exists():
            d = pd.read_csv(p, index_col=0, parse_dates=True)
            d = d[[c for c in ("High", "Low", "Close") if c in d.columns]]
            return d.apply(pd.to_numeric, errors="coerce").dropna()
    return None


def add_trade(code: str, thesis: str, buy_price: float | None = None) -> None:
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"])).get(code, "")
    px = _px(code)
    ref = round(float(px["Close"].iloc[-1]), 2) if px is not None else None
    df = _load()
    if "buy_price" not in df.columns:
        df["buy_price"] = None
    df.loc[len(df)] = {"date": f"{now_tw():%Y-%m-%d}", "code": code, "name": nm,
                       "ref_close": ref, "buy_price": buy_price, "thesis": thesis,
                       "status": "open", "close_date": "", "close_note": ""}
    _save(df)
    print(f"[journal] 記錄買進 {code} {nm} 買入價 {buy_price or f'(未填,參考{ref})'}|論點:{thesis}")


def stop_suggestion(code: str, buy_price: float | None = None) -> dict:
    """停損建議(家規):未賺1R=初始停損(買價-1.5ATR);賺≥1R=保本+移動(收盤-2ATR取高)。
    回傳 {初始, 移動, 20日低, 建議, 說明}。"""
    px = _px(code)
    if px is None or len(px) < 30:
        return {}
    c = px["Close"]
    close = float(c.iloc[-1])
    tr = pd.concat([(px["High"] - px["Low"]),
                    (px["High"] - c.shift(1)).abs(),
                    (px["Low"] - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    trail = round(close - 2 * atr, 1)
    low20 = round(float(c.rolling(20).min().iloc[-1]), 1)
    out = {"移動(收盤-2ATR)": trail, "20日低": low20, "現價": close}
    if buy_price:
        init = round(buy_price - 1.5 * atr, 1)
        out["初始(買價-1.5ATR)"] = init
        if close >= buy_price + 1.5 * atr:          # 已賺 ≥1R
            out["建議"] = round(max(buy_price, trail), 1)
            out["說明"] = "已賺1R→保本+移動停利(只升不降)"
        else:
            out["建議"] = init
            out["說明"] = f"未賺1R→守初始停損(風險{(init/buy_price-1)*100:.1f}%)"
    else:
        out["建議"] = trail
        out["說明"] = "未填買入價→暫用移動煞車;填入買入價可算精確停損"
    return out


def close_trade(code: str, note: str, buy_price: float | None = None) -> None:
    """平倉。buy_price 給定時只平該筆(分批持倉各自進出);未給則平該代號全部 open。"""
    df = _load()
    m = (df["code"] == code) & (df["status"] == "open")
    if buy_price is not None:
        bp = pd.to_numeric(df["buy_price"], errors="coerce")
        m = m & (bp.sub(float(buy_price)).abs() < 0.01)
        if not m.any():
            print(f"[journal] 找不到 {code} 買價 {buy_price} 的 open 筆,未動作")
            return
    df.loc[m, ["status", "close_date", "close_note"]] = ["closed", f"{now_tw():%Y-%m-%d}", note]
    _save(df)
    print(f"[journal] 平倉 {code}({int(m.sum())}筆):{note}")


# ────────────────────────────────────────
def _stock_context(code: str) -> dict:
    """判讀所需數據:報酬/煞車/營收/法人/RS(全 best-effort)。"""
    out = {}
    px = _px(code)
    if px is None or len(px) < 61:
        return out
    c = px["Close"]
    out["close"] = float(c.iloc[-1])
    out["wk_ret"] = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) > 6 else None
    tr = pd.concat([(px["High"] - px["Low"]),
                    (px["High"] - c.shift(1)).abs(),
                    (px["Low"] - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    out["brake"] = round(out["close"] - 2 * atr, 1)          # 煞車=收盤-2ATR
    out["brake_pct"] = round((out["brake"] / out["close"] - 1) * 100, 1)
    try:
        bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0,
                         parse_dates=True).iloc[:, 0]
        b = bm.reindex(c.index).ffill()
        out["rs60"] = round(float((c.iloc[-1] / c.iloc[-61]) / (b.iloc[-1] / b.iloc[-61])), 2)
        out["bm_wk"] = (bm.iloc[-1] / bm.iloc[-6] - 1) * 100
    except Exception:
        pass
    try:
        bulk = pd.read_csv(ROOT / "data" / "fundamentals" / "bulk_rev_2026_all.csv",
                           dtype={"code": str})
        t = bulk[bulk["code"] == code].sort_values("month")
        if len(t):
            out["yoy_last"] = float(t["yoy"].iloc[-1])
    except Exception:
        pass
    try:
        m = pd.read_csv(ROOT / "data" / "institutional" / f"{code}_inst.csv",
                        usecols=lambda x: x in ("date", "外陸資買賣超股數(不含外資自營商)",
                                                "外資買賣超股數", "it_net"))
        a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
        b2 = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
        it = pd.to_numeric(m.get("it_net"), errors="coerce").fillna(0)
        out["fi5_lots"] = round(float((a.fillna(b2).fillna(0) + it).tail(5).sum()) / 1000)
    except Exception:
        pass
    return out


def _week_rotation() -> str:
    from theme_groups import THEME_GROUPS
    rows = []
    for g, codes in THEME_GROUPS.items():
        rets = []
        for c in codes:
            px = _px(c)
            if px is not None and len(px) > 6:
                rets.append((px["Close"].iloc[-1] / px["Close"].iloc[-6] - 1) * 100)
        if len(rets) >= 3:
            rows.append((g, sum(rets) / len(rets)))
    rows.sort(key=lambda x: -x[1])
    top = "、".join(f"{g}({v:+.1f}%)" for g, v in rows[:5])
    bot = "、".join(f"{g}({v:+.1f}%)" for g, v in rows[-5:])
    return f"本週最強:{top}\n本週最弱:{bot}"


def _signal_backing(code: str) -> str:
    """近10個掃描日,系統策略有無選過這檔(BUY級)。"""
    import glob, os
    hits = []
    for f in sorted(glob.glob(str(ROOT / "scan_results" / "signals_*.csv")))[-10:]:
        try:
            s = pd.read_csv(f, encoding="utf-8-sig", usecols=["代碼", "訊號等級", "策略"])
        except Exception:
            continue
        s = s[(s["代碼"].astype(str).str.startswith(code)) &
              (s["訊號等級"].astype(str).str.startswith("BUY"))]
        for _, r in s.iterrows():
            hits.append(f"{os.path.basename(f)[8:16]}{r['策略']}")
    return f"近10日系統背書 {len(hits)} 次({hits[-1]})" if hits else "近10日無系統訊號背書(獨立判斷單)"


def run_review() -> str:
    df = _load()
    opens = df[df["status"] == "open"]
    date_s = f"{now_tw():%Y-%m-%d}"
    L = [f"# 週檢視 {date_s}", ""]

    L.append("## ① 組合風險全檢")
    if opens.empty:
        L.append("(無持倉記錄)")
    secs = {}
    for _, r in opens.iterrows():
        ctx = _stock_context(r["code"])
        if not ctx:
            L.append(f"- {r['code']} {r['name']}:無價格資料")
            continue
        bp = r.get("buy_price")
        bp = float(bp) if pd.notna(bp) and bp else None
        base = bp or r["ref_close"]
        ret = (ctx["close"] / base - 1) * 100 if base else None
        sug = stop_suggestion(r["code"], bp)
        from theme_groups import THEME_GROUPS
        grp = next((g for g, cs in THEME_GROUPS.items() if r["code"] in cs), "其他")
        secs[grp] = secs.get(grp, 0) + 1
        L.append(f"- **{r['code']} {r['name']}**({'買入' if bp else '參考'} @{base}):"
                 f"現價 {ctx['close']:.1f}({f'{ret:+.1f}%' if ret is not None else '?'}),"
                 f"本週 {ctx.get('wk_ret', 0):+.1f}%;"
                 f"**停損建議 {sug.get('建議', ctx['brake'])}**({sug.get('說明', '')})"
                 f"——跌破=紀律出場,不討論")
    if len(opens) > 1:
        conc = "、".join(f"{g}×{n}" for g, n in secs.items())
        L.append(f"- 集中度:{conc}" + ("(⚠️ 同族群疊加,系統性風險共振)" if max(secs.values()) > 1 else ""))

    L.append("\n## ② 產業輪動(本週)")
    L.append(_week_rotation())

    L.append("\n## ③ 決策回顧(本週新單的系統背書)")
    wk_ago = f"{now_tw() - pd.Timedelta(days=7):%Y-%m-%d}"
    for _, r in df[df["date"] >= wk_ago].iterrows():
        L.append(f"- {r['code']} {r['name']}:{_signal_backing(r['code'])}")

    L.append("\n## ④ 論點盤點(THESIS 還成立嗎)")
    for _, r in opens.iterrows():
        ctx = _stock_context(r["code"])
        facts = []
        if ctx.get("yoy_last") is not None:
            facts.append(f"最新月YoY {ctx['yoy_last']:+.0f}%")
        if ctx.get("fi5_lots") is not None:
            facts.append(f"法人5日 {ctx['fi5_lots']:+,} 張")
        if ctx.get("rs60") is not None:
            facts.append(f"RS60 {ctx['rs60']}")
        L.append(f"- **{r['code']} {r['name']}** 論點:「{r['thesis']}」")
        L.append(f"  當前事實:{';'.join(facts) if facts else '無資料'}")
    L.append("\n*煞車=收盤-2×ATR(每週上移不下移);週檢視是紀律儀式,不是重新說服自己的機會。非投資建議。*")

    content = "\n".join(L)
    # LLM 總評(有引擎才附)
    try:
        import llm
        from apikey import get_key
        if llm._cli_path() or get_key():
            out = llm.generate(
                "你是嚴格的操作教練。針對這份週檢視,寫 3-5 條【教練總評】:哪個決策有系統背書、"
                "哪個是獨立判斷單需要加倍警覺、論點與事實矛盾處直說。輸出即本文,條列,150-250字。",
                content, max_tokens=800)
            if out:
                content += "\n\n## 🏋️ 教練總評\n" + out
    except Exception:
        pass

    from analyst_report import save_article, git_publish
    fn = save_article("WKLY", "週檢視", "週檢視", content)
    print(f"[weekly] {fn}|{git_publish(fn)}")
    return fn


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--buy" in args:
        code = args[args.index("--buy") + 1]
        thesis = args[args.index("--thesis") + 1] if "--thesis" in args else "(論點待補)"
        price = float(args[args.index("--price") + 1]) if "--price" in args else None
        add_trade(code, thesis, price)
    elif "--close" in args:
        code = args[args.index("--close") + 1]
        note = args[args.index("--note") + 1] if "--note" in args else ""
        close_trade(code, note)
    else:
        run_review()

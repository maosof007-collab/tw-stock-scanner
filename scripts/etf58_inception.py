# -*- coding: utf-8 -*-
"""ETF58 高股息/收益型 ETF「上市以來」B、C、D、E 四榜(2026-11-23,使用者給了 2025/10~2026/09 的 ETF58 兩組檔案,
要求照同樣格式做「上市以來」版,因為每檔上市時間不同)。

口徑照原檔(ETF58_BCDE_*_20261101.xlsx):
  月初價 = 上個月底收盤(第一個月 = 上市首日收盤);當月除息權利按除息日、當月付款按付款日;
  已付款 = 付款日 ≤ 截止日;期末應收 = 已除息、截止日還沒付款;美元計價(IQQQ、QQA、00687C)用當日台銀美元即期中價換成台幣。
和原檔不同的只有期間:從每檔上市首日到截止日(預設 2026-09-30)。因為上市長短差很多:
  有成本組(B1/C1/D1/E1)另外算「年化/年均」並用它排名;未滿 12 個月的不年化、另列在後。
  無投入成本組(B2/C2/D2/E2)本來就是逐月平均,直接把月份拉長到上市以來。

資料:FinMind(TaiwanStockPrice 未還原收盤、TaiwanStockDividend 除息日/發放日/金額、TaiwanExchangeRate)、yfinance(IQQQ、QQA)。
快取 data/etf58/raw/。  用法:
  python -X utf8 scripts/etf58_inception.py fetch            # 抓資料(約 3 分鐘)
  python -X utf8 scripts/etf58_inception.py update           # 增量補到最新(每日流程 Step 4.5851 會自動跑;etf58_exam.py 的考卷靠它)
  python -X utf8 scripts/etf58_inception.py check <原檔.xlsx>  # 用同一條管線重算 2025/10~2026/09,和原檔逐檔核對
  python -X utf8 scripts/etf58_inception.py build [截止日]     # 產生 xlsx + PDF"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RAW = ROOT / "data" / "etf58" / "raw"
END = "2026-09-30"
FM = "https://api.finmindtrade.com/api/v4/data"
USD = {"IQQQ", "QQA", "00687C"}          # 美元計價,要換台幣
US = {"IQQQ", "QQA"}                     # 美國掛牌(yfinance)
NAMES = {
    "00400A": "主動國泰動能高息", "00401A": "主動摩根台灣鑫收", "00404A": "主動聯博動能50", "00406A": "主動中信台灣收益", "00408A": "主動第一金優股息",
    "0056": "元大高股息", "00679B": "元大美債20年", "00687B": "國泰20年美債", "00687C": "國泰20年美債+櫃U", "00697B": "元大美債7-10",
    "00701": "國泰股利精選30", "00702": "國泰標普低波高息", "00713": "元大台灣高息低波", "00719B": "元大美債1-3", "00730": "富邦臺灣優質高息",
    "00731": "復華富時高息低波", "00771": "元大US高息特別股", "00859B": "群益0-1年美債", "00864B": "中信美國公債0-1", "00878": "國泰永續高股息",
    "00882": "中信中國高股息", "00900": "富邦特選高股息30", "00907": "永豐優息存股", "00915": "凱基優選高股息30", "00918": "大華優利高填息30",
    "00919": "群益台灣精選高息", "00929": "復華台灣科技優息", "00930": "永豐ESG低碳高息", "00931B": "統一美債20年", "00932": "兆豐永續高息等權",
    "00934": "中信成長高股息", "00936": "台新永續高息中小", "00939": "統一台灣高息動能", "00940": "元大台灣價值高息", "00943": "兆豐電子高息等權",
    "00944": "野村趨勢動能高息", "00946": "群益科技高息成長", "00956": "中信日經高股息", "00960": "野村全球航運龍頭", "00961": "FT臺灣永續高息",
    "00962": "台新AI優息動能", "00963": "中信全球高股息", "00964": "中信亞太高股息", "00967B": "元大優息美債", "00972": "野村日本動能高息",
    "00980D": "主動聯博投等入息", "00981D": "主動中信非投等債", "00982D": "主動富邦動態入息", "00983D": "主動富邦複合收益", "00984A": "主動安聯台灣高息",
    "00984D": "主動聯博全球非投", "00985D": "主動貝萊德優投等", "00986D": "主動復華金融債息", "00987D": "主動統一美債量化", "00998A": "主動復華金融股息",
    "00999A": "主動野村臺灣高息", "IQQQ": "ProShares納斯達克100高收入ETF", "QQA": "景順QQQ入息優勢ETF"}
CODES = list(NAMES)


# ───────────────────────── 抓資料(只給手動/排程) ─────────────────────────
def _fm(ds: str, code: str, start: str = "1994-01-01") -> list:
    import requests
    for k in range(4):
        try:
            j = requests.get(FM, params={"dataset": ds, "data_id": code, "start_date": start}, timeout=60).json()
            if j.get("status") == 200:
                return j["data"]
            print("  FinMind", ds, code, j.get("status"), str(j.get("msg"))[:80], flush=True)
            if j.get("status") == 402:                     # 超過免費額度:停,不硬抓
                raise SystemExit("FinMind 額度用完,晚點再跑 fetch(已抓的有快取)")
        except SystemExit:
            raise
        except Exception as e:
            print("  retry", ds, code, type(e).__name__, flush=True)
        time.sleep(8)
    return []


def fetch(force: bool = False) -> None:
    import ssl_trust
    ssl_trust.ensure()
    RAW.mkdir(parents=True, exist_ok=True)

    def save(name, data):
        (RAW / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    for c in CODES:
        if c in US:
            continue
        for tag, ds in (("px", "TaiwanStockPrice"), ("div", "TaiwanStockDividend")):
            p = RAW / f"{c}_{tag}.json"
            if p.exists() and not force:
                continue
            d = _fm(ds, c)
            keep = ("date", "close") if tag == "px" else ("date", "CashEarningsDistribution", "CashStatutorySurplus",
                                                          "CashExDividendTradingDate", "CashDividendPaymentDate")
            save(p.name, [{k: r.get(k) for k in keep} for r in d])
            print(c, tag, len(d), flush=True)
            time.sleep(0.5)
    p = RAW / "USD_fx.json"
    if not p.exists() or force:
        d = _fm("TaiwanExchangeRate", "USD", "2017-01-01")
        save(p.name, [{k: r.get(k) for k in ("date", "spot_buy", "spot_sell")} for r in d])
        print("USD fx", len(d), flush=True)
    import yfinance as yf
    for c in US:
        p = RAW / f"{c}_px.json"
        if p.exists() and not force:
            continue
        h = yf.Ticker(c).history(start="2020-01-01", auto_adjust=False)
        save(p.name, [{"date": str(k)[:10], "close": float(v)} for k, v in h.Close.dropna().items()])
        dv = h.Dividends[h.Dividends > 0]
        save(f"{c}_div.json", [{"ex": str(k)[:10], "amt": float(v)} for k, v in dv.items()])
        print(c, "px", len(h), "div", len(dv), flush=True)


def update(div_every: int = 3) -> str:
    """每日流程用的增量更新:股價、匯率只補「快取最後一天」之後的;配息表每 div_every 天整份重抓一次(上次日期記在 raw/_meta.json,不看檔案時間)。
    FinMind 額度用完就停、不丟例外(已補的留著,下次接著補)。回傳一句話摘要。"""
    import ssl_trust
    ssl_trust.ensure()
    from twtime import now_tw
    today = f"{now_tw():%Y-%m-%d}"
    mp = RAW / "_meta.json"
    meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    do_div = (pd.Timestamp(today) - pd.Timestamp(meta.get("div", "2000-01-01"))).days >= div_every
    n_px = n_div = 0
    if meta.get("px") == today and not do_div:
        return "今天已經補過"

    def merge(p: Path, new: list, key: str) -> int:
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        m = {r[key]: r for r in old}
        k0 = len(m)
        m.update({r[key]: r for r in new if r.get(key)})
        p.write_text(json.dumps([m[k] for k in sorted(m)], ensure_ascii=False), encoding="utf-8")
        return len(m) - k0

    def last(p: Path, default: str) -> str:
        if not p.exists():
            return default
        d = json.loads(p.read_text(encoding="utf-8"))
        return max(r["date"] for r in d) if d else default

    try:
        for c in CODES:
            if c in US:
                continue
            p = RAW / f"{c}_px.json"
            a = last(p, "1994-01-01")
            if a < today:
                d = _fm("TaiwanStockPrice", c, a)
                n_px += merge(p, [{"date": r.get("date"), "close": r.get("close")} for r in d], "date")
                time.sleep(0.3)
            if do_div:
                d = _fm("TaiwanStockDividend", c)
                if d:                                                    # 空的不覆蓋(請求失敗 ≠ 沒配息)
                    keep = ("date", "CashEarningsDistribution", "CashStatutorySurplus", "CashExDividendTradingDate", "CashDividendPaymentDate")
                    (RAW / f"{c}_div.json").write_text(json.dumps([{k: r.get(k) for k in keep} for r in d], ensure_ascii=False), encoding="utf-8")
                    n_div += 1
                time.sleep(0.3)
        p = RAW / "USD_fx.json"
        d = _fm("TaiwanExchangeRate", "USD", last(p, "2017-01-01"))
        merge(p, [{k: r.get(k) for k in ("date", "spot_buy", "spot_sell")} for r in d], "date")
        if do_div:
            meta["div"] = today
    except SystemExit as e:                                              # FinMind 402
        mp.write_text(json.dumps(meta), encoding="utf-8")
        return f"額度用完,先停:股價補 {n_px} 筆、配息重抓 {n_div} 檔({e})"
    try:
        import yfinance as yf
        for c in US:
            p = RAW / f"{c}_px.json"
            a = pd.Timestamp(last(p, "2020-01-01")) - pd.Timedelta(days=10)
            h = yf.Ticker(c).history(start=f"{a:%Y-%m-%d}", auto_adjust=False)
            n_px += merge(p, [{"date": str(k)[:10], "close": float(v)} for k, v in h.Close.dropna().items()], "date")
            dv = h.Dividends[h.Dividends > 0]
            merge(RAW / f"{c}_div.json", [{"ex": str(k)[:10], "amt": float(v)} for k, v in dv.items()], "ex")
    except Exception as e:
        mp.write_text(json.dumps(meta), encoding="utf-8")
        return f"股價補 {n_px} 筆、配息重抓 {n_div} 檔;美國兩檔沒補到({type(e).__name__})"
    meta["px"] = today
    mp.write_text(json.dumps(meta), encoding="utf-8")
    return f"股價補 {n_px} 筆、配息重抓 {n_div} 檔"


# ───────────────────────── 讀快取 ─────────────────────────
def fx() -> pd.Series:
    d = pd.DataFrame(json.loads((RAW / "USD_fx.json").read_text(encoding="utf-8")))
    d = d[(d.spot_buy > 0) & (d.spot_sell > 0)]
    s = ((d.spot_buy + d.spot_sell) / 2)
    s.index = pd.to_datetime(d.date)
    return s.sort_index()


def us_paydates() -> dict:
    """美國兩檔的付款日:原檔「配息來源」裡官方的日期(data/etf58/us_paydates.json);沒有的用 除息日+4 個營業日 推估。"""
    p = ROOT / "data" / "etf58" / "us_paydates.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load(code: str, FX: pd.Series | None = None) -> tuple[pd.Series, pd.DataFrame]:
    """→ (每日收盤 TWD, 配息表[ex, pay, amt(原幣), ccy, twd, est_pay])"""
    px = pd.DataFrame(json.loads((RAW / f"{code}_px.json").read_text(encoding="utf-8")))
    s = pd.Series(px.close.astype(float).values, index=pd.to_datetime(px.date)).sort_index()
    s = s[s > 0]
    raw = json.loads((RAW / f"{code}_div.json").read_text(encoding="utf-8"))
    if code in US:
        pay = us_paydates().get(code, {})
        dv = pd.DataFrame([{"ex": pd.Timestamp(r["ex"]), "amt": r["amt"],
                            "pay": pd.Timestamp(pay[r["ex"]]) if r["ex"] in pay else pd.Timestamp(r["ex"]) + pd.offsets.BDay(4),
                            "est_pay": r["ex"] not in pay} for r in raw])
    else:
        rows = []
        for r in raw:
            amt = float(r.get("CashEarningsDistribution") or 0) + float(r.get("CashStatutorySurplus") or 0)
            ex = r.get("CashExDividendTradingDate") or ""
            if amt <= 0 or not ex:
                continue
            pay = r.get("CashDividendPaymentDate") or ""
            rows.append({"ex": pd.Timestamp(ex), "amt": amt, "pay": pd.Timestamp(pay) if pay else pd.Timestamp(ex) + pd.offsets.BDay(18),
                         "est_pay": not pay})
        dv = pd.DataFrame(rows)
    if len(dv):
        dv = dv.drop_duplicates(["ex", "amt"]).sort_values("ex").reset_index(drop=True)
    else:
        dv = pd.DataFrame(columns=["ex", "amt", "pay", "est_pay"])
    dv["ex"], dv["pay"], dv["est_pay"] = pd.to_datetime(dv.ex), pd.to_datetime(dv.pay), dv.est_pay.astype(bool)
    dv["amt"] = dv.amt.astype(float)
    dv["ccy"] = "USD" if code in USD else "TWD"
    if code in USD:
        FX = fx() if FX is None else FX
        s = s * FX.reindex(s.index, method="ffill")
        dv["twd"] = [a * float(FX.asof(e)) for a, e in zip(dv.amt, dv.ex)] if len(dv) else []
    else:
        dv["twd"] = dv.amt
    return s.dropna(), dv


# ───────────────────────── 計算 ─────────────────────────
def twii() -> pd.Series:
    """加權指數每日收盤(不含息):拿來對照「同一段期間大盤漲多少」。"""
    a = pd.read_csv(ROOT / "data" / "_twii_long.csv", index_col=0, parse_dates=True).Close
    b = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0]
    return pd.concat([a, b[b.index > a.index[-1]]]).sort_index()


def compute(code: str, end: str = END, start: str | None = None, FX: pd.Series | None = None, IDX: pd.Series | None = None) -> dict | None:
    """start=None → 從上市首日;給 start(例 2025-10-01)→ 原檔的固定期間口徑(核對用)。"""
    s, dv = load(code, FX)
    endT = pd.Timestamp(end)
    listed = s.index[0]
    s = s[s.index <= endT]
    if start:
        s = s[s.index >= pd.Timestamp(start)]
    if s.empty:
        return None
    d0, p0, p1 = s.index[0], float(s.iloc[0]), float(s.iloc[-1])
    dv = dv[(dv.ex > d0) & (dv.ex <= endT)].copy()               # 首日買進,之後除息的才有權利
    dv["paid"] = dv.pay <= endT
    paid, recv = float(dv.twd[dv.paid].sum()), float(dv.twd[~dv.paid].sum())
    # 逐月
    g = s.groupby(s.index.to_period("M"))
    rows, prev_d, prev_p = [], d0, p0
    for m, x in g:
        ex_m = float(dv.twd[dv.ex.dt.to_period("M") == m].sum())
        pay_m = float(dv.twd[dv.paid & (dv.pay.dt.to_period("M") == m)].sum())
        rows.append({"月份": str(m), "基準日": f"{prev_d:%Y-%m-%d}", "末日": f"{x.index[-1]:%Y-%m-%d}", "月初價": prev_p, "月末價": float(x.iloc[-1]),
                     "當月除息權利": ex_m, "當月付款": pay_m, "有效日價數": len(x), "本月平均價": float(x.mean())})
        prev_d, prev_p = x.index[-1], float(x.iloc[-1])
    M = pd.DataFrame(rows)
    M["價差"] = M.月末價 - M.月初價
    M["含息損益"] = M.價差 + M.當月除息權利
    M["B2當月報酬"] = M.含息損益 / M.月初價
    M["C2當月現金率"] = M.當月付款 / M.月初價
    n = len(M)
    days = (s.index[-1] - d0).days
    yrs = days / 365.25
    cost = float(M.本月平均價.mean())
    b1 = (p1 - p0 + paid + recv) / p0
    c1 = paid / p0
    full = n >= 12
    e1_net = p1 - cost + paid + recv
    e2_px, e2_dv = float(M.價差.mean()), float(M.當月除息權利.mean())
    mkt = float(IDX.asof(s.index[-1]) / IDX.asof(d0) - 1) if IDX is not None else np.nan      # 同期間加權指數(不含息)
    return dict(code=code, name=NAMES[code], listed=listed, d0=d0, d1=s.index[-1], months=n, days=days, years=yrs, full=full,
                p0=p0, p1=p1, paid=paid, recv=recv, cost=cost, n_div=len(dv), est_pay=int(dv.est_pay.sum()) if len(dv) else 0,
                MKT=mkt, MKTy=(1 + mkt) ** (1 / yrs) - 1 if full and pd.notna(mkt) else np.nan,
                B1=b1, B1y=(1 + b1) ** (1 / yrs) - 1 if full and b1 > -1 else np.nan,
                C1=c1, C1y=c1 / yrs if full else np.nan, D1=c1 / yrs / 12 if full else np.nan,
                E1_px=p1 - cost, E1_dv=paid + recv, E1_net=e1_net, E1_net_y=e1_net / yrs if full else np.nan,
                B2=float(M.B2當月報酬.mean()), C2=float(M.C2當月現金率.mean()), D2=float(M.C2當月現金率.mean()),
                E2_px=e2_px, E2_dv=e2_dv, E2_net=e2_px + e2_dv, monthly=M, divs=dv)


def compute_all(end: str = END, start: str | None = None) -> list[dict]:
    FX, IDX = fx(), twii()
    out = []
    for c in CODES:
        r = compute(c, end, start, FX, IDX)
        if r is not None:
            out.append(r)
    return out


def splits_check() -> list:
    """單日漲跌超過 25% 的日子(可能是分割/反分割,要人工看)。"""
    FX, out = fx(), []
    for c in CODES:
        s, _ = load(c, FX)
        r = s.pct_change()
        for d, v in r[r.abs() > 0.25].items():
            out.append((c, f"{d:%Y-%m-%d}", round(float(v) * 100, 1), float(s.shift(1)[d]), float(s[d])))
    return out


def check(src: str) -> pd.DataFrame:
    """用同一條管線重算原檔的期間(2025/10/01~2026/09/30),和原檔「基礎_58」逐檔比。"""
    import openpyxl
    ws = openpyxl.load_workbook(src, data_only=True)["基礎_58"]
    rows = []
    mine = {r["code"]: r for r in compute_all("2026-09-30", "2025-10-01")}
    for r in ws.iter_rows(min_row=6, values_only=True):
        if not r[0] or r[0] not in mine:
            continue
        m = mine[r[0]]
        rows.append({"代碼": r[0], "月數 原/我": f"{r[2]}/{m['months']}", "期初價 原": r[3], "我": round(m["p0"], 4), "9/30 原": r[4], "我 ": round(m["p1"], 4),
                     "已付 原": r[5], "我  ": round(m["paid"], 4), "應收 原": r[6], "我   ": round(m["recv"], 4),
                     "均價成本 原": round(r[7], 3), "我    ": round(m["cost"], 3),
                     "B1 差(點)": round((m["B1"] - r[8]) * 100, 2), "B2 差(點)": round((m["B2"] - r[9]) * 100, 3)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_columns", 40)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        fetch("--force" in sys.argv)
    elif cmd == "update":
        print(update())
    elif cmd == "check":
        t = check(sys.argv[2])
        print(t.to_string(index=False))
        print("\n單日漲跌 >25%:", splits_check())
    elif cmd == "build":
        import etf58_build
        etf58_build.main(sys.argv[2] if len(sys.argv) > 2 else END)
    else:
        R = compute_all()
        t = pd.DataFrame([{k: v for k, v in r.items() if k not in ("monthly", "divs", "name")} for r in R])
        print(t.round(4).to_string(index=False))

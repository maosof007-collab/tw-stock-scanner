# -*- coding: utf-8 -*-
"""
margin_alert.py — 斷頭投降日掃描(全市場融資維持率)
=================================================================
「需要做這個 還有掃描進line」「每一檔都要」(2026-11-01)。
全市場 data/margin/*.csv 逐檔掃(~1,900 檔),分層:
  ・日誌全收 → data/_margin_alert_log.csv(警戒池+投降日,回溯驗證用)
  ・LINE 推「投降日」全部列出(每一檔都要;訊號天生稀少,爆量日自動分段)
    + 警戒池只報檔數(火藥庫統計,名單看網頁排行榜)

定義(與融資維持率反彈策略同源):
  維持率   = 收盤 ÷ 融資加權平均成本 ÷ 0.6 × 100%(推估——TWSE 只給張數)
  警戒池   = 維持率 < WARN_RATIO(135%),餘額 ≥ MIN_BAL 張(濾雜訊)
  投降日   = 警戒池 且 當日融資減幅 ≥ CAPIT_PCT(5%)——斷頭/停損大出,
             賣壓出清訊號;搏反彈還要看「量增+價穩」,家規照舊。
維持率是推估值,絕對數字只做相對比較;融資成數統一用 0.6。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
MARGIN_DIR = ROOT / "data" / "margin"
LOG = ROOT / "data" / "_margin_alert_log.csv"
SENT = ROOT / "data" / "_margin_alert_sent.json"

WARN_RATIO = 135.0   # 警戒線(%):追繳 130% 之前一步
CAPIT_PCT = 5.0      # 投降日:當日融資減幅門檻(%)
MIN_BAL = 500        # 前日融資餘額至少(張)——太小的減幅都是雜訊
MIN_PRICE = 10.0     # 雞蛋水餃股不看
LOOKBACK = 120       # 成本推估滾動窗(交易日)——融資限期半年,陳年成本早換手;
                     # 全史推估會出現 40% 這種現實不存在的維持率(早斷頭了)


def _close_series(code: str) -> pd.Series | None:
    for suf in (".TW.csv", ".TWO.csv"):
        p = ROOT / "data" / f"{code}{suf}"
        if p.exists():
            try:
                px = pd.read_csv(p, usecols=["Date", "Close"], parse_dates=["Date"])
                s = px.dropna().set_index("Date")["Close"]
                return s[~s.index.duplicated(keep="last")].sort_index()
            except Exception:
                return None
    return None


def _weighted_cost_arr(balance: np.ndarray, close: np.ndarray) -> np.ndarray:
    """融資加權平均成本逐日序列(同 strategies/margin_maintenance._weighted_cost,
    為了讓通知跑者不 import strategies 包——那個 __init__ 會載入全部策略)。
    餘額增加=以當日收盤建倉更新均價;減少=只減量成本不變。"""
    n = len(balance)
    out = np.full(n, np.nan)
    hold_qty = hold_cost = 0.0
    for i in range(n):
        b = balance[i] if not np.isnan(balance[i]) else 0.0
        px = close[i]
        if i == 0:
            hold_qty, hold_cost = max(b, 0.0), px
        else:
            delta = b - max(balance[i - 1], 0.0)
            if delta > 0 and px > 0:
                new_qty = hold_qty + delta
                hold_cost = ((hold_cost * hold_qty + px * delta) / new_qty
                             if new_qty > 0 else px)
                hold_qty = new_qty
            elif delta < 0:
                hold_qty = max(hold_qty + delta, 0.0)
            if hold_qty <= 0:
                hold_cost, hold_qty = px, max(b, 0.0)
        out[i] = hold_cost
    return out


def _weighted_cost(balance: np.ndarray, close: np.ndarray) -> float:
    arr = _weighted_cost_arr(balance, close)
    return float(arr[-1]) if len(arr) else 0.0


def scan(date: str | None = None) -> pd.DataFrame:
    """全市場掃一輪。回傳警戒池(含投降日標記),date=None 用各檔最新共同日。
    欄位:代號/名稱/日期/收盤/漲跌%/維持率%/融資餘額/日增減/日增減%/5日增減%/類型"""
    try:
        from symbols import resolve
    except Exception:
        resolve = None
    rows = []
    for f in sorted(MARGIN_DIR.glob("*_margin.csv")):
        code = f.name.split("_")[0]
        if not (code.isdigit() and len(code) == 4):
            continue
        try:
            m = pd.read_csv(f, usecols=["date", "name", "margin_balance"],
                            parse_dates=["date"])
        except Exception:
            continue
        m = (m.dropna(subset=["date"]).drop_duplicates("date", keep="last")
              .sort_values("date").set_index("date"))
        if date is not None:
            m = m[m.index <= pd.Timestamp(date)]
        if len(m) < 10:
            continue
        bal = m["margin_balance"].astype(float)
        if bal.iloc[-2] < MIN_BAL:
            continue
        px = _close_series(code)
        if px is None:
            continue
        if date is not None:
            px = px[px.index <= pd.Timestamp(date)]
        # 新鮮度:融資與股價的最新日期需一致(融資晚上才公布,沒到就跳過)
        if len(px) < 2 or px.index[-1] != m.index[-1]:
            continue
        close = float(px.iloc[-1])
        if close < MIN_PRICE:
            continue
        aligned = px.reindex(m.index).ffill()
        cost = _weighted_cost(bal.tail(LOOKBACK).values,
                              aligned.tail(LOOKBACK).values)
        if not cost or cost <= 0:
            continue
        ratio = close / cost / 0.6 * 100.0
        if ratio >= WARN_RATIO:
            continue
        d1 = bal.iloc[-1] - bal.iloc[-2]
        d1p = d1 / bal.iloc[-2] * 100.0
        d5p = ((bal.iloc[-1] / bal.iloc[-6] - 1) * 100.0) if len(bal) >= 6 else np.nan
        chg = (close / float(px.iloc[-2]) - 1) * 100.0
        name = str(m["name"].iloc[-1]).strip()
        if (not name or name == "nan") and resolve:
            try:
                name = resolve(code)[1] or code
            except Exception:
                name = code
        rows.append({
            "日期": f"{m.index[-1]:%Y-%m-%d}", "代號": code, "名稱": name,
            "收盤": round(close, 2), "漲跌%": round(chg, 2),
            "維持率%": round(ratio, 1), "融資餘額": int(bal.iloc[-1]),
            "日增減": int(d1), "日增減%": round(d1p, 2),
            "5日增減%": round(d5p, 2) if d5p == d5p else None,
            "類型": "投降日" if d1p <= -CAPIT_PCT else "警戒",
        })
    df = pd.DataFrame(rows)
    return (df.sort_values(["類型", "維持率%"], ascending=[False, True])
              .reset_index(drop=True) if len(df) else df)


def _load_margin(code: str) -> pd.DataFrame | None:
    f = MARGIN_DIR / f"{code}_margin.csv"
    if not f.exists():
        return None
    try:
        m = pd.read_csv(f, usecols=["date", "margin_balance", "margin_quota"],
                        parse_dates=["date"])
    except Exception:
        return None
    return (m.dropna(subset=["date"]).drop_duplicates("date", keep="last")
             .sort_values("date").set_index("date"))


def maint_series(code: str, days: int = 240) -> pd.DataFrame | None:
    """個股維持率曲線(頁44「選號碼就看得到」用)。
    回傳近 days 日:收盤/估算成本/維持率%/融資餘額/日增減/使用率%。
    成本推估前面多墊 LOOKBACK 日暖身,與 scan() 口徑一致。"""
    m = _load_margin(code)
    px = _close_series(code)
    if m is None or px is None or len(m) < 10:
        return None
    m = m.tail(days + LOOKBACK)
    aligned = px.reindex(m.index).ffill()
    bal = m["margin_balance"].astype(float)
    cost = _weighted_cost_arr(bal.values, aligned.values)
    out = pd.DataFrame({
        "收盤": aligned.values, "估算成本": np.round(cost, 2),
        "維持率%": np.round(aligned.values / np.where(cost > 0, cost, np.nan)
                          / 0.6 * 100.0, 1),
        "融資餘額": bal.values,
        "日增減": bal.diff().values,
        "使用率%": np.round(bal.values / m["margin_quota"].replace(0, np.nan)
                          .astype(float).values * 100.0, 1),
    }, index=m.index).tail(days)
    return out.dropna(subset=["收盤"])


HIST = ROOT / "data" / "_margin_capit_hist.csv"


def backfill(start: str = "2025-01-01") -> pd.DataFrame:
    """投降日全程回放:逐檔找出歷史上所有「維持率<135% 且 融資單日減≥5%」的日子,
    記錄其後 5/20 日報酬與 20 日內最高漲幅 → data/_margin_capit_hist.csv。
    成本推估用分段滾動(每段 LOOKBACK 日、前面墊 LOOKBACK 日暖身),
    避免全史累積的陳年成本漂移(會算出 40% 這種現實不存在的維持率)。"""
    rows = []
    t0 = pd.Timestamp(start)
    for f in sorted(MARGIN_DIR.glob("*_margin.csv")):
        code = f.name.split("_")[0]
        if not (code.isdigit() and len(code) == 4):
            continue
        m = _load_margin(code)
        px = _close_series(code)
        if m is None or px is None or len(m) < LOOKBACK:
            continue
        aligned = px.reindex(m.index).ffill()
        bal = m["margin_balance"].astype(float)
        n = len(m)
        ratio = np.full(n, np.nan)
        for s in range(0, n, LOOKBACK):          # 分段:暖身 LOOKBACK + 有效 LOOKBACK
            lo = max(0, s - LOOKBACK)
            arr = _weighted_cost_arr(bal.values[lo:s + LOOKBACK],
                                     aligned.values[lo:s + LOOKBACK])
            seg = arr[s - lo:]
            ratio[s:s + len(seg)] = (aligned.values[s:s + len(seg)]
                                     / np.where(seg > 0, seg, np.nan) / 0.6 * 100)
        d1p = bal.pct_change().values * 100.0
        prev = bal.shift(1).values
        hit = ((ratio < WARN_RATIO) & (d1p <= -CAPIT_PCT) & (prev >= MIN_BAL)
               & (aligned.values >= MIN_PRICE) & (m.index >= t0))
        closes = px.values
        pidx = {d: i for i, d in enumerate(px.index)}
        for i in np.where(hit)[0]:
            d = m.index[i]
            j = pidx.get(d)
            if j is None:
                continue
            c0 = closes[j]
            fw = closes[j + 1:j + 21]
            rows.append({
                "日期": f"{d:%Y-%m-%d}", "代號": code,
                "收盤": round(float(c0), 2),
                "維持率%": round(float(ratio[i]), 1),
                "融資減%": round(float(d1p[i]), 2),
                "5日%": round((float(fw[4]) / c0 - 1) * 100, 2) if len(fw) >= 5 else None,
                "20日%": round((float(fw[-1]) / c0 - 1) * 100, 2) if len(fw) >= 20 else None,
                "20日內最高%": round((float(fw.max()) / c0 - 1) * 100, 2) if len(fw) else None,
            })
    df = pd.DataFrame(rows)
    if len(df):
        try:
            from symbols import resolve
            names = {c: (resolve(c)[1] or c) for c in df["代號"].unique()}
            df.insert(2, "名稱", df["代號"].map(names))
        except Exception:
            df.insert(2, "名稱", df["代號"])
        df = df.sort_values("日期")
        df.to_csv(HIST, index=False, encoding="utf-8-sig")
    return df


def _log_append(df: pd.DataFrame) -> None:
    if df.empty:
        return
    old = (pd.read_csv(LOG, dtype={"代號": str}) if LOG.exists()
           else pd.DataFrame())
    pd.concat([old, df]).drop_duplicates(["日期", "代號"], keep="last") \
      .to_csv(LOG, index=False, encoding="utf-8-sig")


def _fmt(r: pd.Series) -> str:
    return (f"・{r['名稱']} {r['代號']}|維持率 {r['維持率%']:.0f}%|"
            f"融資 {r['日增減%']:+.1f}%({r['日增減']:+,}張)|"
            f"收 {r['收盤']}({r['漲跌%']:+.1f}%)")


def push() -> str:
    """晚間 LINE:投降日每一檔都列;警戒池只報數。一天(每個資料日)只推一次。"""
    df = scan()
    if df.empty:
        return "全市場無警戒(維持率<135%)標的"
    d = df["日期"].iloc[0]
    try:
        sent = json.loads(SENT.read_text(encoding="utf-8")) if SENT.exists() else {}
    except Exception:
        sent = {}
    if sent.get("date") == d:
        return f"{d} 已推過,跳過"
    _log_append(df)
    cap = df[df["類型"] == "投降日"]
    warn_n = int((df["類型"] == "警戒").sum())
    head = f"💥 斷頭投降日掃描 {d[5:]}\n維持率<{WARN_RATIO:.0f}% 共 {len(df)} 檔"
    if cap.empty:
        msg = (head + f"\n今日無投降日(融資單日大減≥{CAPIT_PCT:.0f}%)——"
               f"火藥庫 {warn_n} 檔還在凹單,賣壓未出清,不是接的時候")
        msgs = [msg]
    else:
        lines = [_fmt(r) for _, r in cap.iterrows()]   # 每一檔都要
        body = (head + f"\n其中投降日 {len(cap)} 檔(單日融資大減≥{CAPIT_PCT:.0f}%"
                ",斷頭/停損出籠):\n" + "\n".join(lines)
                + "\n⚠ 搏反彈家規:還要量增+價穩才接;大盤破季線禁接刀;"
                  "融資使用率>30%大跌日禁接")
        # LINE 單則上限,超長自動分段(每段 ~25 行)
        msgs, chunk = [], []
        for ln in body.split("\n"):
            chunk.append(ln)
            if len(chunk) >= 28:
                msgs.append("\n".join(chunk)); chunk = []
        if chunk:
            msgs.append("\n".join(chunk))
    try:
        import line_push
        if line_push.enabled():
            for m in msgs:
                line_push.push_text(m)
    except Exception:
        pass
    try:
        SENT.write_text(json.dumps({"date": d}), encoding="utf-8")
    except Exception:
        pass
    return f"{d}:警戒 {warn_n}+投降 {len(cap)} 檔,LINE {len(msgs)} 則"


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "backfill":
        h = backfill()
        v = h.dropna(subset=["20日%"])
        print(f"投降日回放 {len(h)} 筆(2025-01 起);20日可驗 {len(v)} 筆")
        if len(v):
            print(f"  5日 平均 {v['5日%'].mean():+.2f}% | 20日 平均 {v['20日%'].mean():+.2f}%"
                  f" 中位 {v['20日%'].median():+.2f}% 勝率 {(v['20日%'] > 0).mean()*100:.0f}%"
                  f" | 20日內曾漲>10% {(v['20日內最高%'] >= 10).mean()*100:.0f}%")
    else:
        out = scan()
        print(f"警戒池 {len(out)} 檔(投降日 {(out['類型'] == '投降日').sum() if len(out) else 0})")
        if len(out):
            print(out.head(30).to_string(index=False))

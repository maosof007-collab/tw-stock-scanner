"""
model_track.py — 模型預實追蹤(預測 vs 實際,自動對答案)
=================================================================
把估值模型的預測值存檔;月營收(每月10日前公布)與季報(FinMind)
系統自動抓,新資料一到就比對:
  誤差 ±5% 🟢 | ±10% 🟡 | 更大 🔴 | 未公布 ⏳
學對方模型的紀律:「26Q2 預測951.6 vs 實際933 誤差-2.0% 綠燈」。
預測存 data/fundamentals/model_track.json,頁13顯示與新增。
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

from fundamentals import monthly_revenue, quarterly_fin

TRACK = Path(__file__).parent / "data" / "fundamentals" / "model_track.json"

# metric: monthly_rev(百萬) / quarterly_rev(百萬) / quarterly_gm(%)
_METRIC_NAME = {"monthly_rev": "月營收(百萬)", "quarterly_rev": "季營收(百萬)",
                "quarterly_gm": "季毛利率(%)"}


def _load() -> list[dict]:
    if TRACK.exists():
        try:
            return json.loads(TRACK.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(rows: list[dict]):
    TRACK.parent.mkdir(parents=True, exist_ok=True)
    TRACK.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def add_prediction(code: str, metric: str, period: str, predicted: float,
                   note: str = "") -> bool:
    """period: 月營收用 '2026-07';季用 '2026-Q3'。同key覆蓋。"""
    rows = _load()
    rows = [r for r in rows if not (r["code"] == code and r["metric"] == metric
                                    and r["period"] == period)]
    rows.append({"code": code, "metric": metric, "period": period,
                 "predicted": float(predicted), "note": note})
    _save(rows)
    return True


def remove_prediction(code: str, metric: str, period: str):
    rows = [r for r in _load() if not (r["code"] == code and r["metric"] == metric
                                       and r["period"] == period)]
    _save(rows)


def _actual(code: str, metric: str, period: str):
    """抓實際值;未公布回 None。"""
    try:
        if metric == "monthly_rev":
            mon = monthly_revenue(code, years=2)
            hit = mon[mon["ym"] == period]
            return float(hit["revenue"].iloc[0]) if not hit.empty else None
        q = quarterly_fin(code, years=3)
        if q.empty:
            return None
        y, qq = period.split("-Q")
        qmap = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
        key = f"{y}-{qmap.get(qq, '')}"
        hit = q[q["季度"].astype(str).str.startswith(key)]
        if hit.empty:
            return None
        if metric == "quarterly_rev":
            return float(hit["營收(億)"].iloc[0]) * 100      # 億→百萬
        if metric == "quarterly_gm":
            return float(hit["毛利率%"].iloc[0])
    except Exception:
        return None
    return None


def check_all(code: str | None = None) -> pd.DataFrame:
    """回傳追蹤表:預測/實際/誤差%/燈號。"""
    rows = _load()
    if code:
        rows = [r for r in rows if r["code"] == code]
    out = []
    for r in sorted(rows, key=lambda x: (x["code"], x["period"])):
        act = _actual(r["code"], r["metric"], r["period"])
        if act is None:
            lamp, err = "⏳ 未公布", None
        else:
            if r["metric"] == "quarterly_gm":                 # 毛利率用絕對差(pp)
                err = act - r["predicted"]
                lamp = "🟢" if abs(err) <= 2 else ("🟡" if abs(err) <= 4 else "🔴")
                err = round(err, 1)
            else:
                err = (act / r["predicted"] - 1) * 100
                lamp = "🟢" if abs(err) <= 5 else ("🟡" if abs(err) <= 10 else "🔴")
                err = round(err, 1)
        out.append({"代碼": r["code"], "指標": _METRIC_NAME.get(r["metric"], r["metric"]),
                    "期間": r["period"], "預測": r["predicted"],
                    "實際": round(act, 1) if act is not None else "—",
                    "誤差": (f"{err:+.1f}{'pp' if r['metric']=='quarterly_gm' else '%'}"
                             if err is not None else "—"),
                    "燈號": lamp, "備註": r.get("note", "")})
    return pd.DataFrame(out)


# ════════════════════════════════════════
# 損益表級 預測 vs 實際(整張 P&L 對照,仿投顧預實表)
# ════════════════════════════════════════
PL_PATH = Path("data/pl_forecast.json")


def set_pl_forecast(code: str, period: str, rev: float, gm_pct: float, opex: float,
                    nonop: float = 0.0, tax_pct: float = 20.0, note: str = "") -> None:
    """存一份季度損益預測(營收百萬/毛利率%/營業費用百萬/業外/稅率),其餘科目自動推導。"""
    import json
    d = {}
    try:
        d = json.loads(PL_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    d.setdefault(code, {})[period] = {"rev": rev, "gm_pct": gm_pct, "opex": opex,
                                      "nonop": nonop, "tax_pct": tax_pct, "note": note}
    PL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PL_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def get_pl_forecasts(code: str) -> dict:
    import json
    try:
        return json.loads(PL_PATH.read_text(encoding="utf-8")).get(code, {})
    except Exception:
        return {}


def _pl_actual(code: str, period: str) -> dict:
    """從 FinMind 財報原始檔取單季實際損益(百萬)。period: 2026-Q2。"""
    import json as _json
    y, q = period.split("-Q")
    date = {"1": f"{y}-03-31", "2": f"{y}-06-30",
            "3": f"{y}-09-30", "4": f"{y}-12-31"}[q]
    p = Path(f"data/fundamentals/{code}_TaiwanStockFinancialStatements.json")
    if not p.exists():
        from fundamentals import _fm
        _fm("TaiwanStockFinancialStatements", code, f"{int(y)-1}-01-01")
    try:
        rows = _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for r in rows:
        if r.get("date") == date:
            out[r["type"]] = float(r["value"]) / 1e6
    return out


def pl_compare(code: str, period: str):
    """整張損益表 預測vs實際 對照(DataFrame);實際未公布回 None。"""
    f = get_pl_forecasts(code).get(period)
    if not f:
        return None
    a = _pl_actual(code, period)
    if not a.get("Revenue"):
        return None
    # 預測推導
    p_rev = f["rev"]; p_gp = p_rev * f["gm_pct"] / 100
    p_cost = p_rev - p_gp; p_op = p_gp - f["opex"]
    p_pre = p_op + f.get("nonop", 0.0)
    p_net = p_pre * (1 - f.get("tax_pct", 20.0) / 100)
    a_gm = a["GrossProfit"] / a["Revenue"] * 100 if a.get("GrossProfit") else None
    rows = [
        ("營業收入", p_rev, a.get("Revenue")),
        ("毛利率%", f["gm_pct"], a_gm),
        ("營業成本合計", p_cost, a.get("CostOfGoodsSold")),
        ("營業費用合計", f["opex"], a.get("OperatingExpenses")),
        ("營業利益", p_op, a.get("OperatingIncome")),
        ("業外損益", f.get("nonop", 0.0), a.get("TotalNonoperatingIncomeAndExpense")),
        ("稅前淨利", p_pre, a.get("PreTaxIncome")),
        ("本期淨利", p_net, a.get("IncomeAfterTaxes")),
    ]
    import pandas as _pd
    out = []
    for name, pv, av in rows:
        err = (av - pv) if (av is not None and pv is not None) else None
        pct = (err / abs(pv) * 100) if (err is not None and pv) else None
        unit = "pp" if name == "毛利率%" else ""
        out.append({"損益項目": name,
                    "預測": round(pv, 1) if pv is not None else None,
                    "實際": round(av, 1) if av is not None else None,
                    "誤差": (f"{err:+.1f}{unit}" if err is not None else "—"),
                    "誤差%": (f"{pct:+.1f}%" if pct is not None else "—")})
    return _pd.DataFrame(out)

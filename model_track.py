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
    """period: 月營收用 '2026-07';季用 '2026-Q3'。
    去重鍵含「來源」(note 第一段)——同一期間可存多來源(本模型/富邦/群益)同場對答案;
    同來源重存才覆蓋。曾因鍵不含來源,富邦預測被群益蓋掉、原版被修正版蓋掉(2026-09-01修)。"""
    src = (note or "").split(";")[0].split("(")[0][:12]
    rows = _load()
    rows = [r for r in rows if not (r["code"] == code and r["metric"] == metric
                                    and r["period"] == period
                                    and (r.get("note") or "").split(";")[0].split("(")[0][:12] == src)]
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
        _src = (r.get("note") or "").split(";")[0].split("(")[0][:12] or "—"
        out.append({"代碼": r["code"], "指標": _METRIC_NAME.get(r["metric"], r["metric"]),
                    "期間": r["period"], "來源": _src, "預測": r["predicted"],
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


SECTOR_FIT = {
    # 模型=月營收YoY連續外推;lumpy/非月營收驅動的產業要標警語
    "建材營造業": "⚠️低適用:交屋認列跳動,YoY模型結構性失準(群益對照已驗證)",
    "金融保險業": "⚠️不適用:無毛利率概念,勿用本模型",
    "航運業": "⚠️慎用:運價驅動,YoY中位落後轉折,配BDRY/SCFI判讀",
    "通信網路業": "⚠️慎用:記憶體漲價轉嫁虛胖(中磊法說),配毛利率驗證",
    "生技醫療業": "⚠️慎用:授權金/里程碑收入跳動",
}


def auto_pl_forecast(code: str, period: str) -> dict | None:
    """系統自動產生季度損益預測(免手填),並內建自我修正:
      營收   = 已公布月份用實際 + 未公布月份用「去年同月×(1+近3月YoY中位)」
      毛利率 = 最新實際季 + 近兩季QoQ趨勢(截幅±2pp)←每次財報對答案後自動重新錨定
      費用率/稅率 = 近4季滾動;業外 = 近4季中位
    財報已公布的期間 → 凍結不覆寫(對答案的考卷不能改)。"""
    if _pl_actual(code, period).get("Revenue"):
        return get_pl_forecasts(code).get(period)          # 已開獎:凍結

    from fundamentals import monthly_revenue, quarterly_fin
    import pandas as _pd
    y, q = int(period.split("-Q")[0]), int(period.split("-Q")[1])
    months = [(y, (q - 1) * 3 + i) for i in (1, 2, 3)]

    mon = monthly_revenue(code, years=3)
    if mon.empty:
        return None
    mon = mon.set_index("ym")
    yoy_med = float(_pd.to_numeric(mon["yoy%"], errors="coerce").tail(3).median()) / 100
    rev = 0.0
    used_actual = 0
    for yy, mm in months:
        ym = f"{yy}-{mm:02d}"
        if ym in mon.index:                                # 已公布月份用實際(混合=修正機制①)
            rev += float(mon.loc[ym, "revenue"]); used_actual += 1
        else:
            base_ym = f"{yy-1}-{mm:02d}"
            if base_ym in mon.index:
                rev += float(mon.loc[base_ym, "revenue"]) * (1 + yoy_med)

    qf = quarterly_fin(code, years=2)
    if qf.empty or len(qf) < 3:
        return None
    gms = _pd.to_numeric(qf["毛利率%"], errors="coerce").dropna()
    trend = float((gms.diff().tail(2)).mean())
    gm = float(gms.iloc[-1]) + max(-2.0, min(2.0, trend))  # 修正機制②:錨定最新+趨勢截幅
    rev_hist = _pd.to_numeric(qf["營收(億)"], errors="coerce") * 100
    op_hist = _pd.to_numeric(qf["營益率%"], errors="coerce")
    opex_rate = float((gms.tail(4) - op_hist.tail(4)).mean())      # 費用率=毛利率-營益率
    opex = rev * opex_rate / 100
    net_hist = _pd.to_numeric(qf["淨利率%"], errors="coerce")
    # 業外(匯損益等):近4季中位——出口商(如3042)單季匯損益可達營益±25%,不可設0
    nonop_med = 0.0
    try:
        import json as _json
        from pathlib import Path as _P
        _raw = _json.loads(_P(f"data/fundamentals/{code}_TaiwanStockFinancialStatements.json")
                           .read_text(encoding="utf-8"))
        _no = [r["value"] / 1e6 for r in _raw
               if r["type"] == "TotalNonoperatingIncomeAndExpense"]
        if len(_no) >= 4:
            nonop_med = float(_pd.Series(_no[-4:]).median())
    except Exception:
        pass
    # 稅率+業外合併效果:近4季 (營益率-淨利率) 均值當摩擦成本
    friction = float((op_hist.tail(4) - net_hist.tail(4)).mean())
    tax_pct = max(10.0, min(30.0, friction / max(op_hist.tail(4).mean(), 1e-6) * 100))
    _fit = ""
    try:
        _sl = _pd.read_csv("data/stock_list.csv", encoding="utf-8-sig", dtype=str)
        _sec = dict(zip(_sl["code"], _sl["sector"])).get(code, "")
        _fit = SECTOR_FIT.get(_sec, "")
    except Exception:
        pass
    note = ((_fit + ";" if _fit else "") + f"系統模型(自動@{__import__('twtime').now_tw():%m/%d};"
            f"營收含{used_actual}個實際月+YoY中位{yoy_med*100:+.0f}%;"
            f"GM錨定{gms.iloc[-1]:.1f}+趨勢{trend:+.1f}截幅)")
    set_pl_forecast(code, period, round(rev, 1), round(gm, 1), round(opex, 1),
                    round(nonop_med, 1), round(tax_pct, 1), note)
    return get_pl_forecasts(code).get(period)

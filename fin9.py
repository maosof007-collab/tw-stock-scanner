"""
fin9.py — 財務九宮格資料組裝(一屏九圖的體質總覽)
=================================================================
資料:FinMind 三大報表(損益/資產負債/現金流量,經 fundamentals._fm 快取20h)。
重點換算:
  存貨天數 = 存貨/營業成本×91.25;收現天數 = 應收/營收×91.25
  本業EPS = EPS×(營業利益/稅前淨利);業外 = 其餘
  現金流量表為年內累計 → 按年差分還原單季
  自由現金流 = 營業現金流 - 資本支出
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fundamentals import _fm, quarterly_fin, monthly_revenue, shares_map

ROOT = Path(__file__).parent
Q_DAYS = 91.25


def _pivot(dataset: str, code: str, start: str = "2021-01-01") -> pd.DataFrame:
    data = _fm(dataset, code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    return df.pivot_table(index="date", columns="type", values="value", aggfunc="first")


def _decum(s: pd.Series) -> pd.Series:
    """年內累計 → 單季(現金流量表用)。index 為日期字串。"""
    d = s.copy().astype(float)
    yr = pd.to_datetime(pd.Series(d.index)).dt.year.values
    out = d.values.copy()
    for i in range(1, len(out)):
        if yr[i] == yr[i - 1] and pd.notna(d.values[i]) and pd.notna(d.values[i - 1]):
            out[i] = d.values[i] - d.values[i - 1]
    return pd.Series(out, index=d.index)


def assemble(code: str) -> dict:
    inc = _pivot("TaiwanStockFinancialStatements", code)
    bal = _pivot("TaiwanStockBalanceSheet", code)
    cf = _pivot("TaiwanStockCashFlowsStatement", code)
    A: dict = {"q": quarterly_fin(code, years=6), "mon": monthly_revenue(code, 3)}
    if inc.empty:
        return A

    idx = inc.index
    lab = pd.to_datetime(pd.Series(idx))
    A["季別"] = (lab.dt.year.astype(str).str[2:] + "Q" + lab.dt.quarter.astype(str)).values

    rev = inc.get("Revenue")
    gp = inc.get("GrossProfit")
    op = inc.get("OperatingIncome")
    pre = inc.get("PreTaxIncome", inc.get("IncomeBeforeIncomeTax"))
    eps = inc.get("EPS")

    # 本業/業外 EPS 分解
    if eps is not None and op is not None and pre is not None:
        ratio = (op / pre).clip(-0.5, 1.5)
        A["eps_core"] = (eps * ratio).round(2)
        A["eps_other"] = (eps - A["eps_core"]).round(2)
        A["eps"] = eps
        A["core_ratio%"] = (ratio * 100).round(0)

    # 存貨/收現天數
    if bal is not None and not bal.empty:
        b = bal.reindex(idx)
        inv, ar = b.get("Inventories"), b.get("AccountsReceivableNet")
        cost = rev - gp if (rev is not None and gp is not None) else None
        if inv is not None and cost is not None:
            A["存貨天數"] = (inv / cost * Q_DAYS).round(1)
        if ar is not None and rev is not None:
            A["收現天數"] = (ar / rev * Q_DAYS).round(1)
        liab, ta = b.get("Liabilities"), b.get("TotalAssets")
        if liab is not None and ta is not None:
            A["負債比%"] = (liab / ta * 100).round(1)
            A["淨值"] = ta - liab

    # 現金流(單季,億)
    if cf is not None and not cf.empty:
        c = cf.reindex(idx)
        ocf = c.get("CashFlowsFromOperatingActivities")
        capex = c.get("PropertyAndPlantAndEquipment")
        if ocf is not None:
            A["營業現金流"] = (_decum(ocf) / 1e8).round(2)
        if capex is not None:
            A["資本支出"] = (_decum(capex).abs() / 1e8).round(2)
        if ocf is not None and capex is not None:
            A["自由現金流"] = (A["營業現金流"] - A["資本支出"]).round(2)

    # 頭欄:股價/股本/每股淨值/本業PE
    close = None
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            close = float(pd.read_csv(p, usecols=["Close"]).dropna()["Close"].iloc[-1])
            break
    A["close"] = close
    sh = shares_map().get(code)
    if sh:
        A["股本(億)"] = round(sh * 10 / 1e8, 1)
        if "淨值" in A and pd.notna(A["淨值"].iloc[-1]):
            A["每股淨值"] = round(float(A["淨值"].iloc[-1]) / sh, 1)
    if close is not None and "eps_core" in A:
        core_ttm = float(A["eps_core"].tail(4).sum())
        if core_ttm > 0:
            A["本業PE"] = round(close / core_ttm, 1)

    # 月營收 今年vs去年(含累計)
    mon = A["mon"]
    if not mon.empty:
        m = mon.copy()
        m["yr"] = m["ym"].str[:4].astype(int)
        m["mo"] = m["ym"].str[5:].astype(int)
        this_y = m["yr"].max()
        A["mon_cmp"] = {
            "月": list(range(1, 13)),
            "今年": [float(m[(m.yr == this_y) & (m.mo == i)]["revenue"].sum()) or None
                    for i in range(1, 13)],
            "去年": [float(m[(m.yr == this_y - 1) & (m.mo == i)]["revenue"].sum()) or None
                    for i in range(1, 13)],
            "this_y": this_y,
        }
    return A

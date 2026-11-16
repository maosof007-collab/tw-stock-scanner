"""
industry_tree.py — 產業樹:先垂直(樹幹)再水平(枝葉),再問慣性/痛點/限制
=================================================================
一棵樹 = data/industry_trees/<slug>.json(人工查證後入檔;✓=有來源,?=假設待查):
  trunk    樹幹:上游→下游,每一段 {stage, what, global, note, capex_note, members}
  branches 枝葉:板子上/模組裡還放什麼、誰在推它升級 {stage, push, members}
  inertia  慣性:這個產業一再重複的走法
  pains    痛點:{pain, fix, who, flag, src}
  limits   限制:打不破的東西 {limit, why, check}(check=系統拿哪個數字來查)
  claims   公司說法:{代號: {say, date, src, flag}}——法說/新聞講的產能與擴產,跟財報數字並排對
  excluded 別掛錯:[代號, 名稱, 為什麼不算這條鏈](名字像、其實不在鏈上的)
  members  一律 [代號, 名稱, 角色, ✓/?]

系統替每個節點接上的讀數(全部沿用既有模組,不另立口徑):
  營收  data/_rev_history.csv:近3月合計年增 vs 前3月 → 轉正/加速/高成長/衰退
  價格  dual_radar._scan_one:20日%、距250日高、是否在季線下
  籌碼  dual_radar._inst_lights(外資/投信20日)、_bigholder_delta(大戶4週)
  限制  capex_one():現金流量表「取得不動產、廠房及設備」近4季 vs 前4季、
        資本支出/折舊(>1.5 才算真的在蓋產能)、固定資產年增、存貨天數
擴產查核表存 data/_tree_capex.csv(run_daily 每週重建;頁面只讀檔,不靠開頁觸發)。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"
TREE_DIR = D / "industry_trees"
CAPEX_CSV = D / "_tree_capex.csv"
REBUILD_DAYS = 7            # 季報資料:一週重算一次就夠


# ── 樹 ─────────────────────────────────────────────────────────
def load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not TREE_DIR.exists():
        return out
    for p in sorted(TREE_DIR.glob("*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        t["_slug"] = p.stem
        out[p.stem] = t
    return out


def members(tree: dict) -> pd.DataFrame:
    """樹幹+枝葉的全部成員(一檔可掛多段)。"""
    rows = []
    for part, key in (("樹幹", "trunk"), ("枝葉", "branches")):
        for i, seg in enumerate(tree.get(key, [])):
            for m in seg.get("members", []):
                rows.append(dict(part=part, order=i, stage=seg.get("stage", ""),
                                 code=str(m[0]), name=m[1], role=m[2],
                                 flag=m[3] if len(m) > 3 else "?"))
    return pd.DataFrame(rows, columns=["part", "order", "stage", "code", "name", "role", "flag"])


def validate(tree: dict) -> list[str]:
    """家規:代號必先查證。回傳問題清單(空=全過)。"""
    sl = pd.read_csv(D / "stock_list.csv", dtype=str).set_index("code")["name"]
    bad = []
    for _, r in members(tree).iterrows():
        if r.code not in sl.index:
            bad.append(f"{r.code} {r['name']}:股票清單沒有這個代號")
        elif sl[r.code] != r["name"]:
            bad.append(f"{r.code}:樹上寫「{r['name']}」,股票清單是「{sl[r.code]}」")
    return bad


def all_codes() -> list[str]:
    cs: list[str] = []
    for t in load_all().values():
        cs += members(t)["code"].tolist()
    return sorted(set(cs))


# ── 節點讀數 ───────────────────────────────────────────────────
def _rev_stats(x: pd.DataFrame) -> dict:
    """近3月合計年增 vs 前3月合計年增(都跟去年同期比)。x=單檔、依 ym 排序。"""
    out = dict(rev_ym=None, yoy1=np.nan, yoy3=np.nan, yoy3_prev=np.nan, rev_kind="資料不足", rev_hi=False)
    r = pd.to_numeric(x["rev"], errors="coerce").to_numpy(float)
    if len(r) < 18:
        return out
    out["rev_ym"] = str(x["ym"].iloc[-1])
    out["yoy1"] = round(float(x["yoy"].iloc[-1]), 1) if pd.notna(x["yoy"].iloc[-1]) else np.nan

    def y3(end: int) -> float:               # end=結尾位置(不含)
        a, b = r[end - 3:end].sum(), r[end - 15:end - 12].sum()
        return (a / b - 1) * 100 if b and b > 0 else np.nan

    now, prev = y3(len(r)), y3(len(r) - 3)
    out["yoy3"], out["yoy3_prev"] = round(now, 1), round(prev, 1)
    out["rev_hi"] = bool(r[-1] >= np.nanmax(r) - 1e-9)
    if now != now or prev != prev:
        return out
    if prev <= 0 < now:
        k = "由負轉正"
    elif now > 0 and prev > 0 and now - prev >= 10:
        k = "加速"
    elif now > 20:
        k = "維持高成長"
    elif now > 0:
        k = "持平成長"
    elif now - prev >= 10:
        k = "跌幅收斂"
    else:
        k = "衰退"
    out["rev_kind"] = k
    return out


def readings(codes: tuple[str, ...], with_health: bool = True) -> pd.DataFrame:
    """每個節點的系統讀數(index=code)。沿用 dual_radar / pretrade 的既有口徑。"""
    import dual_radar as dr

    keep = frozenset(codes)
    try:
        rev = pd.read_csv(D / "_rev_history.csv", dtype={"code": str})
        rev = rev[rev["code"].isin(keep)].sort_values("ym")
    except Exception:                              # 缺檔(雲端資料包未到)→ 營收欄留白,頁面不倒
        rev = pd.DataFrame(columns=["code", "ym", "rev", "yoy"])
    bh = dr._bigholder_delta()
    rows = []
    for c in codes:
        r: dict = {"code": c}
        f = next((D / f"{c}{s}.csv" for s in (".TW", ".TWO") if (D / f"{c}{s}.csv").exists()), None)
        if f is not None:
            s = dr._scan_one(str(f), keep=keep)
            if s:
                r.update({k: s[k] for k in ("date", "close", "r20", "chg5", "off_hi", "below_ma60")})
        r.update(dr._inst_lights(c))
        if len(bh) and c in bh.index:
            r["bh1"], r["bh4"] = bh.loc[c, "bh1"], bh.loc[c, "bh4"]
        r.update(_rev_stats(rev[rev["code"] == c]))
        if with_health:
            try:
                import pretrade
                h = pretrade.health_check(c)
                r["health"] = str(h.get("verdict", ""))[:1]
                r["health_txt"] = str(h.get("verdict", ""))
            except Exception:
                r["health"], r["health_txt"] = "", ""
        rows.append(r)
    out = pd.DataFrame(rows).set_index("code")
    out.attrs["bh_week"] = bh.attrs.get("week", "") if len(bh) else ""
    return out


# ── 限制:擴產查核 ───────────────────────────────────────────────
def capex_one(code: str) -> dict:
    """單檔擴產查核(億元)。資料不足回 {'code','q':None}。"""
    from fin9 import _decum, _pivot

    out: dict = {"code": code, "q": None}
    cf = _pivot("TaiwanStockCashFlowsStatement", code)
    if cf is None or cf.empty or "PropertyAndPlantAndEquipment" not in cf.columns:
        return out
    cf = cf.sort_index()
    cap = (_decum(cf["PropertyAndPlantAndEquipment"]).abs() / 1e8).dropna()
    if len(cap) < 8:
        return out
    out["q"] = str(cap.index[-1])
    ttm, prev = float(cap.iloc[-4:].sum()), float(cap.iloc[-8:-4].sum())
    out["capex_ttm"], out["capex_prev"] = round(ttm, 2), round(prev, 2)
    out["capex_chg"] = round((ttm / prev - 1) * 100, 0) if prev > 0.005 else np.nan
    out["capex_q"] = round(float(cap.iloc[-1]), 2)
    if "Depreciation" in cf.columns:
        dep = (_decum(cf["Depreciation"]).abs() / 1e8).reindex(cap.index)
        d4 = float(dep.iloc[-4:].sum())
        out["dep_ttm"] = round(d4, 2)
        out["capex_dep"] = round(ttm / d4, 2) if d4 > 0.005 else np.nan
    inc = _pivot("TaiwanStockFinancialStatements", code)
    if inc is not None and not inc.empty and "Revenue" in inc.columns:
        inc = inc.sort_index()
        rv = (inc["Revenue"] / 1e8).reindex(cap.index)
        r4 = float(rv.iloc[-4:].sum())
        out["capex_rev"] = round(ttm / r4 * 100, 1) if r4 > 0 else np.nan
    bal = _pivot("TaiwanStockBalanceSheet", code)
    if bal is not None and not bal.empty:
        bal = bal.sort_index()
        if "PropertyPlantAndEquipment" in bal.columns:
            ppe = (bal["PropertyPlantAndEquipment"] / 1e8).dropna()
            if len(ppe) >= 5:
                out["ppe"] = round(float(ppe.iloc[-1]), 2)
                out["ppe_yoy"] = round((ppe.iloc[-1] / ppe.iloc[-5] - 1) * 100, 0) if ppe.iloc[-5] > 0 else np.nan
        if "Inventories" in bal.columns and inc is not None and {"Revenue", "GrossProfit"} <= set(inc.columns):
            cost = (inc["Revenue"] - inc["GrossProfit"]).reindex(bal.index)
            days = (bal["Inventories"] / cost * 91.25).replace([np.inf, -np.inf], np.nan).dropna()
            if len(days) >= 5:
                out["inv_days"], out["inv_days_ly"] = round(float(days.iloc[-1]), 0), round(float(days.iloc[-5]), 0)
    return out


def capex_verdict(c: dict | pd.Series, yoy3: float | None) -> tuple[str, str]:
    """(燈, 一句話)。規則寫死、可檢查:
    🟢 真的在蓋:資本支出/折舊 ≥1.5 且 近4季比前4季 +30% 以上
    🔴 需求強卻沒蓋:營收近3月年增 ≥30%,但 資本支出/折舊 <1 或 近4季資本支出沒增加
       (不等於壞事:有閒置產能的公司本來就不用蓋,所以這盞燈的意思是「去查稼動率」)
    🟡 其餘(維持性支出、或擴產幅度不大)
    """
    q = c.get("q")
    if q is None or q != q:
        return "⚪", "沒有現金流量表資料"
    cd, chg = c.get("capex_dep"), c.get("capex_chg")
    cd = cd if cd == cd else None
    chg = chg if chg == chg else None
    hot = yoy3 is not None and yoy3 == yoy3 and yoy3 >= 30
    if cd is not None and chg is not None and cd >= 1.5 and chg >= 30:
        return "🟢", f"在蓋產能:資本支出是折舊的 {cd:.1f} 倍,比前四季 {chg:+.0f}%"
    if hot and ((cd is not None and cd < 1) or (chg is not None and chg <= 0)):
        why = f"資本支出只有折舊的 {cd:.1f} 倍" if cd is not None and cd < 1 else f"資本支出比前四季 {chg:+.0f}%"
        return "🔴", f"營收年增 {yoy3:.0f}% 但{why}——靠既有產能在撐,要查稼動率還剩多少"
    if cd is not None and cd >= 1.5:
        return "🟡", f"資本支出是折舊的 {cd:.1f} 倍,但沒有比前四季明顯增加"
    if chg is not None and chg >= 30:
        return "🟡", f"資本支出 {chg:+.0f}%,但金額還不到折舊的 1.5 倍"
    if cd is not None and chg is not None:
        return "🟡", f"資本支出是折舊的 {cd:.1f} 倍、比前四季 {chg:+.0f}%,沒有明顯放大"
    return "🟡", "維持性支出,看不出擴產"


def load_capex() -> pd.DataFrame:
    try:
        return pd.read_csv(CAPEX_CSV, dtype={"code": str}).set_index("code")
    except Exception:
        return pd.DataFrame()


def build_capex(force: bool = False) -> pd.DataFrame:
    """重建全部樹的擴產查核表。7 天內建過、且涵蓋所有代號就跳過(force=True 強制)。"""
    codes = all_codes()
    old = load_capex()
    today = now_tw().date()
    if not force and len(old) and set(codes) <= set(old.index) and "built" in old.columns:
        try:
            last = pd.to_datetime(old["built"]).max().date()
            if (today - last).days < REBUILD_DAYS:
                return old
        except Exception:
            pass
    rows = []
    for c in codes:
        try:
            r = capex_one(c)
        except Exception:
            r = {"code": c, "q": None}
        r["built"] = f"{today:%Y-%m-%d}"
        rows.append(r)
    df = pd.DataFrame(rows)
    if df["q"].notna().sum() == 0 and len(old):      # 全部抓不到(斷網/限流)→ 保留舊檔
        return old
    if len(old):                                     # 只有部分抓不到 → 那幾檔沿用舊列(含舊的 built,7 天閘門到期會再試)
        keep = old.reset_index()
        keep = keep[keep["code"].astype(str).isin(df.loc[df["q"].isna(), "code"].astype(str)) & keep["q"].notna()]
        if len(keep):
            df = pd.concat([df[~df["code"].astype(str).isin(keep["code"].astype(str))], keep], ignore_index=True)
    df.to_csv(CAPEX_CSV, index=False, encoding="utf-8-sig")
    return df.set_index("code")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for slug, t in load_all().items():
        bad = validate(t)
        print(slug, t.get("title"), "| 成員", len(members(t)), "| 代號查核:", "全過" if not bad else bad)
    d = build_capex(force="--force" in sys.argv)
    print(d.to_string())

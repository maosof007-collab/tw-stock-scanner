# -*- coding: utf-8 -*-
"""
bulk_fin.py — 全市場財報/月營收 bulk 快取(MOPS 彙總表 → 壓縮檔進 git)
=================================================================
為什麼:FinMind 一檔一檔抓會限流+雲端被擋;MOPS 彙總表「一季一請求/一月一請求」
       就能拿全市場 → 壓成 data/bulk_fin/*.csv.gz(幾MB)進 git,雲端任何代碼直接用。
產出:fin_q_all.csv.gz  (code,季度,營收(億),毛利率%,營益率%,淨利率%,EPS — 單季值)
     rev_all.csv.gz    (code,ym,revenue(百萬),yoy%)
fundamentals.quarterly_fin / monthly_revenue 在 FinMind 失敗時自動 fallback 到這裡。
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "bulk_fin"
OUT.mkdir(parents=True, exist_ok=True)
_HDR = {"User-Agent": "Mozilla/5.0"}


# ── 季報:ajax_t163sb04 綜合損益彙總(累計制 → 年內差分成單季) ──
def _fetch_quarter(roc_year: int, season: int, typek: str) -> pd.DataFrame:
    r = requests.post("https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",
                      data={"encodeURIComponent": "1", "step": "1", "firstin": "1",
                            "off": "1", "isQuery": "Y", "TYPEK": typek,
                            "year": str(roc_year), "season": f"{season:02d}"},
                      headers=_HDR, timeout=40)
    r.encoding = "utf-8"
    try:
        tables = pd.read_html(io.StringIO(r.text))
    except ValueError:
        return pd.DataFrame()
    rows = []
    for t in tables:
        cols = [str(c).replace(" ", "").replace("　", "") for c in t.columns]
        if not any("公司代號" in c for c in cols):
            continue
        t.columns = cols
        cmap, used = {}, set()

        def _put(c, k):
            if k not in used:
                cmap[c] = k
                used.add(k)
        for c in cols:
            if "公司代號" in c:
                _put(c, "code")
            elif "營業收入" in c and "營業外" not in c:
                _put(c, "rev")
            elif "營業毛利" in c:
                _put(c, "gp")
            elif "營業利益" in c and "營業外" not in c:
                _put(c, "op")
            elif "基本每股盈餘" in c:
                _put(c, "eps")
            elif "本期淨利" in c and "母公司" not in c and "非控制" not in c:
                _put(c, "ni")
        t = t.rename(columns=cmap)
        if "ni" not in t.columns:                     # 金融業表頭不同,取含「淨利」欄
            for c in cols:
                if "淨利" in c and c not in cmap:
                    t = t.rename(columns={c: "ni"}); break
        keep = [c for c in ("code", "rev", "gp", "op", "ni", "eps") if c in t.columns]
        if "code" not in keep or "rev" not in keep:
            continue
        sub = t[keep].copy()
        sub = sub[sub["code"].astype(str).str.fullmatch(r"\d{4,6}")]
        rows.append(sub)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True)
    df = df.loc[:, ~df.columns.duplicated()]
    for c in df.columns:
        if c != "code":
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
    df["code"] = df["code"].astype(str)
    y = roc_year + 1911
    m = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[season]
    df["季度"] = f"{y}-{m}"
    return df


def build_quarters(start_roc: int = 112, end_roc: int = 115, end_season: int = 2,
                   sleep: float = 2.0) -> pd.DataFrame:
    """抓累計制原始 → 差分單季 → 比率化,存 fin_q_all.csv.gz。"""
    frames = []
    for yr in range(start_roc, end_roc + 1):
        for se in (1, 2, 3, 4):
            if yr == end_roc and se > end_season:
                break
            for tk in ("sii", "otc"):
                d = _fetch_quarter(yr, se, tk)
                print(f"  {yr}Q{se} {tk}: {len(d)}")
                if len(d):
                    frames.append(d)
                time.sleep(sleep)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.drop_duplicates(subset=["code", "季度"], keep="first").sort_values(["code", "季度"])
    # 年內差分(累計 → 單季)
    raw["yr"] = raw["季度"].str[:4]
    for c in ("rev", "gp", "op", "ni", "eps"):
        if c in raw.columns:
            prev = raw.groupby(["code", "yr"])[c].shift(1)
            raw[c + "_q"] = raw[c] - prev.fillna(0)
    out = pd.DataFrame({
        "code": raw["code"], "季度": raw["季度"],
        "營收(億)": (raw["rev_q"] / 1e5).round(2),          # 千元 → 億
        "毛利率%": (raw.get("gp_q") / raw["rev_q"] * 100).round(2),
        "營益率%": (raw.get("op_q") / raw["rev_q"] * 100).round(2),
        "淨利率%": (raw.get("ni_q") / raw["rev_q"] * 100).round(2),
        "EPS": raw.get("eps_q").round(2),
    })
    out = out[out["營收(億)"].notna() & (out["營收(億)"] > 0)]
    out.to_csv(OUT / "fin_q_all.csv.gz", index=False, encoding="utf-8-sig",
               compression="gzip")
    return out


# ── 月營收:t21sc03 全市場月表(當月+去年當月 → YoY 直接有) ──
def _fetch_month(roc_year: int, month: int, market: str) -> pd.DataFrame:
    url = (f"https://mopsov.twse.com.tw/nas/t21/{market}/"
           f"t21sc03_{roc_year}_{month}_0.html")
    r = requests.get(url, headers=_HDR, timeout=40)
    if r.status_code != 200 or len(r.content) < 5000:
        return pd.DataFrame()
    try:                                   # MOPS 月表是 big5:先解碼再解析,否則掉列
        tables = pd.read_html(io.StringIO(r.content.decode("big5", errors="replace")))
    except ValueError:
        return pd.DataFrame()
    rows = []
    for t in tables:
        cols = [("".join(map(str, c)) if isinstance(c, tuple) else str(c))
                .replace(" ", "").replace("　", "") for c in t.columns]
        t.columns = cols
        cc = next((c for c in cols if "公司代號" in c), None)
        mc = next((c for c in cols if "當月營收" in c and "去年" not in c), None)
        lc = next((c for c in cols if "去年當月營收" in c), None)
        if not (cc and mc):
            continue
        sub = t[[cc, mc] + ([lc] if lc else [])].copy()
        sub.columns = ["code", "rev"] + (["rev_ly"] if lc else [])
        sub = sub[sub["code"].astype(str).str.fullmatch(r"\d{4,6}")]
        rows.append(sub)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True)
    for c in df.columns:
        if c != "code":
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
    df["code"] = df["code"].astype(str)
    df["ym"] = f"{roc_year + 1911}-{month:02d}"
    return df


def build_months(months_back: int = 40, sleep: float = 1.2) -> pd.DataFrame:
    from twtime import now_tw
    t = now_tw()
    frames = []
    y, m = t.year, t.month - 1          # 上個月起往回
    for _ in range(months_back):
        if m < 1:
            m += 12; y -= 1
        for mk in ("sii", "otc"):
            d = _fetch_month(y - 1911, m, mk)
            if len(d):
                frames.append(d)
            time.sleep(sleep)
        print(f"  {y}-{m:02d}: ok")
        m -= 1
    raw = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["code", "ym"])
    out = pd.DataFrame({
        "code": raw["code"], "ym": raw["ym"],
        "revenue": (raw["rev"] / 1e3).round(1),            # 千元 → 百萬
        "yoy%": ((raw["rev"] / raw["rev_ly"] - 1) * 100).round(2)
                 if "rev_ly" in raw.columns else None,
    })
    out = out.sort_values(["code", "ym"])
    out.to_csv(OUT / "rev_all.csv.gz", index=False, encoding="utf-8-sig",
               compression="gzip")
    return out


def refresh_latest():
    """run_daily 用:補最新一月營收+最新一季財報(各2請求),併入既有檔。"""
    from twtime import now_tw
    t = now_tw()
    # 月營收
    p = OUT / "rev_all.csv.gz"
    if p.exists():
        old = pd.read_csv(p, dtype={"code": str})
        y, m = t.year, t.month - 1
        if m < 1:
            m += 12; y -= 1
        frames = [old]
        for mk in ("sii", "otc"):
            d = _fetch_month(y - 1911, m, mk)
            if len(d):
                frames.append(pd.DataFrame({
                    "code": d["code"], "ym": d["ym"],
                    "revenue": (d["rev"] / 1e3).round(1),
                    "yoy%": ((d["rev"] / d["rev_ly"] - 1) * 100).round(2)
                            if "rev_ly" in d.columns else None}))
            time.sleep(1)
        new = (pd.concat(frames, ignore_index=True)
               .drop_duplicates(subset=["code", "ym"], keep="last")
               .sort_values(["code", "ym"]))
        new.to_csv(p, index=False, encoding="utf-8-sig", compression="gzip")
    # 季報:重抓「當前年度」各已公布季 → 差分 → 併回其他年度舊資料(不整檔覆寫)
    roc = t.year - 1911
    se = {1: 4, 2: 4, 3: 4, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 2,
          10: 3, 11: 3, 12: 3}[t.month]
    yr = roc - 1 if t.month <= 3 else roc
    qp = OUT / "fin_q_all.csv.gz"
    if qp.exists():
        frames = []
        for s in range(1, se + 1):
            for tk in ("sii", "otc"):
                d = _fetch_quarter(yr, s, tk)
                if len(d):
                    frames.append(d)
                time.sleep(1.5)
        if frames:
            raw = (pd.concat(frames, ignore_index=True)
                   .drop_duplicates(subset=["code", "季度"]).sort_values(["code", "季度"]))
            raw["yr"] = raw["季度"].str[:4]
            for c in ("rev", "gp", "op", "ni", "eps"):
                if c in raw.columns:
                    raw[c + "_q"] = raw[c] - raw.groupby(["code", "yr"])[c].shift(1).fillna(0)
            new = pd.DataFrame({
                "code": raw["code"], "季度": raw["季度"],
                "營收(億)": (raw["rev_q"] / 1e5).round(2),
                "毛利率%": (raw.get("gp_q") / raw["rev_q"] * 100).round(2),
                "營益率%": (raw.get("op_q") / raw["rev_q"] * 100).round(2),
                "淨利率%": (raw.get("ni_q") / raw["rev_q"] * 100).round(2),
                "EPS": raw.get("eps_q").round(2)})
            new = new[new["營收(億)"].notna() & (new["營收(億)"] > 0)]
            old = pd.read_csv(qp, dtype={"code": str})
            year_tag = str(yr + 1911)
            old = old[~old["季度"].astype(str).str.startswith(year_tag)]
            merged = (pd.concat([old, new], ignore_index=True)
                      .sort_values(["code", "季度"]))
            merged.to_csv(qp, index=False, encoding="utf-8-sig", compression="gzip")


if __name__ == "__main__":
    import sys
    if "--quarters" in sys.argv:
        q = build_quarters()
        print("quarters:", len(q), "rows")
    if "--months" in sys.argv:
        m = build_months()
        print("months:", len(m), "rows")

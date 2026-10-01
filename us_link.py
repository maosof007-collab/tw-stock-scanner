# -*- coding: utf-8 -*-
"""
us_link.py — 美股連動雷達(美股族群領先 ↔ 台股受惠/供應對照)
=================================================================
命題:美股族群「整族轉強」是台股對應鏈的領先訊號(教案:2026/09/30 夜資安全族創高
PANW/CRWD/OKTA/S/FTNT/ZS → 台股資安服務鏈隔日對照)。配對同時標「客戶關係」——
美股巨頭常是台廠的終端客戶(NVDA→台積/廣達;Starlink→萬泰科)。
資料:yfinance 美股日K(data/us/ 快取);對照表 data/us_pairs.json 可增修。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
US_DIR = ROOT / "data" / "us"
US_DIR.mkdir(parents=True, exist_ok=True)
PAIRS = ROOT / "data" / "us_pairs.json"

_SEED = [
    {"theme": "資安 Cybersecurity",
     "note": "AI普及→攻擊面擴大→資安=基礎建設重定價;台股端=服務/維運/整合(純度低於美股原廠,吃預算擴張)",
     "us": [["PANW", "Palo Alto"], ["CRWD", "CrowdStrike"], ["FTNT", "Fortinet"],
            ["ZS", "Zscaler"], ["OKTA", "Okta"], ["S", "SentinelOne"]],
     "tw": [["7765", "中華資安"], ["6690", "安碁資訊"], ["2480", "敦陽科"],
            ["3029", "零壹"], ["6214", "精誠"], ["6218", "豪勉(維運邊)"]]},
    {"theme": "AI算力/伺服器",
     "note": "客戶關係:NVDA/雲端四巨頭=台鏈終端客戶",
     "us": [["NVDA", "NVIDIA"], ["SMCI", "Supermicro"], ["VRT", "Vertiv(液冷)"], ["DELL", "Dell"]],
     "tw": [["2330", "台積電"], ["2382", "廣達"], ["6669", "緯穎"],
            ["6933", "AMAX-KY"], ["3017", "奇鋐"], ["3324", "雙鴻"]]},
    {"theme": "光通訊/CPO",
     "us": [["AVGO", "Broadcom"], ["COHR", "Coherent"], ["LITE", "Lumentum"], ["CRDO", "Credo"]],
     "tw": [["4979", "華星光"], ["3363", "上詮"], ["6426", "統新"], ["3450", "聯鈞"]]},
    {"theme": "客製ASIC",
     "note": "AVGO/MRVL 的台鏈對手與協作:設計服務+IP",
     "us": [["AVGO", "Broadcom"], ["MRVL", "Marvell"]],
     "tw": [["3443", "創意"], ["3661", "世芯"], ["6643", "M31"], ["3035", "智原"]]},
    {"theme": "低軌衛星",
     "note": "客戶關係:Starlink/AST=台廠出貨對象",
     "us": [["ASTS", "AST SpaceMobile"], ["RKLB", "Rocket Lab"]],
     "tw": [["6190", "萬泰科(套組)"], ["3491", "昇達科"], ["6672", "騰輝(火箭主板)"]]},
    {"theme": "記憶體",
     "us": [["MU", "Micron"], ["WDC", "WD"], ["SNDK", "SanDisk"]],
     "tw": [["2408", "南亞科"], ["8299", "群聯"], ["2344", "華邦電"]]},
]


def pairs() -> list[dict]:
    if PAIRS.exists():
        try:
            return json.loads(PAIRS.read_text(encoding="utf-8"))
        except Exception:
            pass
    PAIRS.write_text(json.dumps(_SEED, ensure_ascii=False, indent=1), encoding="utf-8")
    return _SEED


def fetch_us(period: str = "6mo") -> int:
    import yfinance as yf
    ok = 0
    for p in pairs():
        for tk, _ in p["us"]:
            try:
                d = yf.Ticker(tk).history(period=period)
                if len(d) > 20:
                    d = d.reset_index()[["Date", "Close", "Volume"]]
                    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
                    d.to_csv(US_DIR / f"{tk}.csv", index=False)
                    ok += 1
            except Exception:
                continue
    return ok


def _mom_us(tk: str):
    p = US_DIR / f"{tk}.csv"
    if not p.exists():
        return None, None
    c = pd.read_csv(p)["Close"].dropna()
    if len(c) < 61:
        return None, None
    m20 = round(float(c.iloc[-1] / c.iloc[-21] - 1) * 100, 1)
    hi = round(float(c.iloc[-1] / c.tail(120).max() - 1) * 100, 1)   # 距半年高
    return m20, hi


def scan() -> pd.DataFrame:
    import supply_chain as sc
    rows = []
    for p in pairs():
        us_lead, near_high = -999, False
        for tk, nm in p["us"]:
            m20, hi = _mom_us(tk)
            if m20 is not None:
                us_lead = max(us_lead, m20)
                if hi is not None and hi >= -2:
                    near_high = True
                rows.append({"主題": p["theme"], "市場": "US", "代碼": tk, "名稱": nm,
                             "20日%": m20, "距高%": hi, "燈號": ""})
        for c, nm in p["tw"]:
            m = sc._mom(c.split("(")[0] if "(" in c else c)
            lamp = ""
            if us_lead > -999 and us_lead >= 10 and near_high and (m or 0) < us_lead - 8:
                lamp = "🔥 美股領先·台股待跟"
            rows.append({"主題": p["theme"], "市場": "TW", "代碼": c, "名稱": nm,
                         "20日%": m, "距高%": None, "燈號": lamp})
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(US_DIR / "_us_scan.csv", index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    print("fetched:", fetch_us())
    print(scan().to_string(index=False))

# -*- coding: utf-8 -*-
"""
quiet_accum.py — 還沒發動掃描(低檔整理 + 外資連續吃貨 + 未出量第一根)
=================================================================
起因(2026-10-01):「每天選很多檔,整理出 5 檔還沒發動的——相對低檔、整理區間、
外資一直吃貨、還沒出量的第一根。」和選股頁相反:選股抓「已發動」,這裡抓「發動前」。
條件(全部要過):
  ① 低檔未發動:收盤距 250 日高 ≤ -10%(還沒創高=行情還沒走)
  ② 整理區間:近 40 日箱體幅 ≤ 25% 且近 20 日 ≤ 15%,收盤 ≥ 60日均(整理偏強不破底)
  ③ 外資吃貨:近 20 交易日買超天數 ≥ 12,且累計買超 > 0
  ④ 未出量:近 15 日沒有任何一天量 > 前20日均量×2.3(爆量第一根還沒出現)
  ⑤ 可交易:20 日均成交金額 ≥ 3000 萬
排序:外資吸籌比(20日累計買超股數 ÷ 20日總成交股數)——吃貨越兇越前面。
加欄「AI/轉型」:選出來還要看故事——有 AI 關聯或轉型題材的才有資金再進的理由
(族群表自動對 + 個案轉型手標;標(假設)的=供應關係待查證)。
家規對接:這是「觀察名單」不是買點——家規禁追,進場仍等它自己出第一根後回測不破。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
D = ROOT / "data"
INST = D / "institutional"
OUT = D / "_quiet_accum.csv"

# 外陸資買賣超股數(不含外資自營商)= 第5欄(位置取,欄名是中文)
_FI_COL = 4

# 族群 → AI 故事(theme_groups 成分自動對)
_AI_THEME = {
    "AI伺服器": "AI|伺服器", "散熱": "AI|散熱", "重電": "AI|資料中心電力",
    "電源": "AI|電源", "半導體設備": "AI|半導體設備", "ABF載板": "AI|載板",
    "記憶體": "AI|記憶體", "石英元件": "AI|時脈元件", "光通訊CPO": "AI|光通訊",
    "IC設計": "AI|IC設計", "晶圓代工": "AI|晶圓代工", "封測": "AI|封測",
    "矽晶圓": "AI|矽晶圓", "玻璃基板TGV": "AI|玻璃基板",
    "機器人自動化": "AI|機器人", "PCB": "AI|板材(查產品線)", "網通": "AI|網通(查)",
    "被動元件": "AI|伺服器被動件",
}
# 個案轉型故事(不在族群表、但有 AI/轉型敘事;(假設)=待查證)
_AI_EXTRA = {
    "2354": "轉型|鴻海系AI伺服器散熱/機殼(假設)",
    "1609": "轉型|電網電纜→AI電力間接(假設)",
    "2451": "記憶體模組|AI邊緣/工控(假設)",
    "2367": "轉型|低軌衛星板(假設)",
    "4766": "轉型|製鞋膠→電子膠/封裝材料(假設)",
    "2328": "鴻海系|連接器/板(AI關聯低)",
}


def _ai_tag(code: str) -> str:
    try:
        from theme_groups import THEME_GROUPS
        for t, codes in THEME_GROUPS.items():
            if code in codes and t in _AI_THEME:
                return _AI_THEME[t]
    except Exception:
        pass
    return _AI_EXTRA.get(code, "")


def _price(code: str) -> pd.DataFrame | None:
    for suf in (".TW.csv", ".TWO.csv"):
        p = D / f"{code}{suf}"
        if p.exists():
            try:
                df = pd.read_csv(p).dropna(subset=["Close"])
                if len(df) >= 260:
                    return df
            except Exception:
                return None
    return None


def _fi_recent(code: str, n: int = 20) -> pd.DataFrame | None:
    p = INST / f"{code}_inst.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        fi = pd.to_numeric(df.iloc[:, _FI_COL], errors="coerce")
        out = pd.DataFrame({"date": df["date"], "fi_net": fi}).dropna()
        return out.tail(n) if len(out) >= n else None
    except Exception:
        return None


def _check(code: str) -> dict | None:
    px = _price(code)
    if px is None:
        return None
    c, h, l, v = (px["Close"].astype(float), px["High"].astype(float),
                  px["Low"].astype(float), px["Volume"].astype(float))
    close = c.iloc[-1]
    if close <= 0 or v.tail(20).mean() * close < 30_000_000:          # ⑤ 流動性
        return None
    hi250 = c.tail(250).max()
    pos = (close / hi250 - 1) * 100
    if pos > -10:                                                     # ① 還沒發動
        return None
    box40 = (h.tail(40).max() / l.tail(40).min() - 1) * 100
    box20 = (h.tail(20).max() / l.tail(20).min() - 1) * 100
    ma60 = c.tail(60).mean()
    if box40 > 25 or box20 > 15 or close < ma60:                      # ② 整理偏強
        return None
    vol20 = v.shift(1).rolling(20).mean()
    burst = (v.tail(15) > vol20.tail(15) * 2.3).any()
    if burst:                                                         # ④ 已出過量→出局
        return None
    fi = _fi_recent(code)
    if fi is None:
        return None
    buy_days = int((fi["fi_net"] > 0).sum())
    net = float(fi["fi_net"].sum())
    if buy_days < 12 or net <= 0:                                     # ③ 連續吃貨
        return None
    absorb = net / max(float(v.tail(20).sum()), 1) * 100              # 吸籌比%
    return {"代碼": code, "AI/轉型": _ai_tag(code),
            "收盤": round(close, 2), "距年高%": round(pos, 1),
            "箱體40日%": round(box40, 1), "箱體20日%": round(box20, 1),
            "外資買超天(20日)": buy_days, "外資累計買超(張)": round(net / 1000),
            "吸籌比%": round(absorb, 1), "20日均額(億)": round(v.tail(20).mean() * close / 1e8, 2)}


def scan(top: int = 5) -> pd.DataFrame:
    import symbols
    codes = sorted(p.name.split("_")[0] for p in INST.glob("*_inst.csv")
                   if p.name.split("_")[0].isdigit() and len(p.name.split("_")[0]) == 4)
    rows = []
    for code in codes:
        r = _check(code)
        if r:
            try:
                r["名稱"] = symbols.resolve(code)[1] or ""
            except Exception:
                r["名稱"] = ""
            rows.append(r)
    df = pd.DataFrame(rows)
    if not df.empty:
        # AI/轉型有故事的優先,同組內按吸籌比
        df["_ai"] = (df["AI/轉型"] != "").astype(int)
        df = (df.sort_values(["_ai", "吸籌比%"], ascending=False)
                .drop(columns="_ai").head(top))
        cols = ["代碼", "名稱", "AI/轉型"] + [c for c in df.columns
                                              if c not in ("代碼", "名稱", "AI/轉型")]
        df = df[cols]
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    print(scan(10).to_string(index=False))

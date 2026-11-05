# -*- coding: utf-8 -*-
"""
short_watch.py — 明日空方觀察名單(強勢榜鏡像)
=================================================================
「幫忙想另外一個方向 放空」(2026-11-05)。
回放依據(data/_attention_hist.csv,2023 起 18,463 筆,隔日開盤空→當日收盤回補):
  全榜 +0.48%/筆;「跳空≥3% 才進場」 +1.21%;再排除連榜≥2 後 +1.13%,
  2023/2024/2025/2026 逐年皆正(1.29/1.13/0.87/1.22)。賺的是隔日沖倒貨
  +追價套牢的結構財,不是方向財。
規則(全部寫死在這裡,頁 39 只負責呈現):
  1. 候選=最新榜 Top20,排除處置股(分盤撮合、不能券賣/當沖)與連榜≥2(妖股右尾)
  2. 觸發:隔日開盤 ≥ 觸發價(收盤×1.03)才空;沒跳空=整天不動,名單只是候選
  3. 只做現股當沖「先賣後買」(下單前確認標的在可先賣後買名單),收盤前必回補、不留倉
     ——同批股票抱空 5 天期望值歸零甚至翻負,這條邊只存在於 D+1 當沖口徑
  4. 停損:進場後逆漲 3.5% 無條件回補(回放右尾單筆最慘 -28%,勝率僅 52%,
     期望值全靠砍掉右尾才拿得到)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

D = Path(__file__).parent / "data"
GAP_TRIG = 1.03      # 開盤 ≥ 收盤×1.03 才觸發
STOP_PCT = 3.5       # 進場後逆漲 % 無條件回補
TOP = 20


def _streaks(codes: list[str], board_date: str) -> dict[str, int]:
    """每檔連榜數(含榜單當天):用回放檔的 Top20 歷史往回數連續在榜天數。"""
    out = {c: 1 for c in codes}
    try:
        h = pd.read_csv(D / "_attention_hist.csv", usecols=["日期", "代號"],
                        dtype={"代號": str})
    except Exception:
        return out
    prior = sorted({d for d in h["日期"].unique() if d < board_date})[::-1][:10]
    sets = [set(h.loc[h["日期"] == d, "代號"]) for d in prior]
    for c in codes:
        for s in sets:
            if c in s:
                out[c] += 1
            else:
                break
    return out


def _disposal(board_date: str) -> dict[str, str]:
    """處置中個股 {code: 說明}(處置迄日 >= 榜單日才算仍在處置)。"""
    try:
        d = pd.read_csv(D / "_disposal_now.csv", dtype=str)
        d = d[d["end"] >= board_date]
        return {r["code"]: f"{r['name']}({r['nth']}至{r['end']})" for _, r in d.iterrows()}
    except Exception:
        return {}


def build_short_watch() -> dict:
    """回傳 {date, df, excluded}。df 為空=今天沒有合格候選。"""
    a = pd.read_csv(D / "_attention.csv", dtype={"代碼": str})
    board_date = str(a["日期"].iloc[0])[:10]
    top = a.head(TOP).copy()
    codes = top["代碼"].tolist()
    streak = _streaks(codes, board_date)
    disp = _disposal(board_date)

    excluded: list[str] = []
    rows = []
    for _, r in top.iterrows():
        c = r["代碼"]
        if c in disp:
            excluded.append(f"🚫處置 {c} {disp[c]}")
            continue
        if streak.get(c, 1) >= 2:
            excluded.append(f"🔥連榜{streak[c]} {c} {r['名稱']}(妖股右尾不空)")
            continue
        close = float(r["收盤"])
        trig = close * GAP_TRIG
        rows.append({
            "代號": c, "名稱": r["名稱"], "收盤": close,
            "觸發價(開盤≥)": round(trig, 2),
            "停損(逆漲3.5%)": round(trig * (1 + STOP_PCT / 100), 2),
            "漲跌%": r["漲跌%"], "量比": r["量比"], "收位%": r["收位%"],
            "隔日沖": r.get("隔日沖", ""),
            "警示": "🔒昨近漲停,防再鎖板" if float(r["漲跌%"]) >= 9.8 else "",
        })
    return {"date": board_date, "df": pd.DataFrame(rows), "excluded": excluded}


if __name__ == "__main__":
    sw = build_short_watch()
    print(f"榜單日 {sw['date']},合格候選 {len(sw['df'])} 檔")
    if not sw["df"].empty:
        print(sw["df"].to_string(index=False))
    for x in sw["excluded"]:
        print("剔除:", x)

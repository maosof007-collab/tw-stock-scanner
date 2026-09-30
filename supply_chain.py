"""
supply_chain.py — 供應鏈接力雷達(贏家的上下游,下一棒在哪)
=================================================================
教案:大甲(管件)噴出 → 往上游找供應商 → 彰源 vs 允強比「獲利純度」→ 彰源 +92%。
資料:data/supply_chain.json 人工+引擎累積的鏈譜(可自行增修)。
用法:relay_alerts(突破名單) → 鏈上同伴點名;chain_of(code) → 戰情室顯示。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
FILE = ROOT / "data" / "supply_chain.json"

# 種子鏈譜(寫入 json 後以 json 為準)
_SEED = [
    {"chain": "不鏽鋼管件鏈", "note": "大甲教案:管件旺→上游鋼管吃量;彰源以鋼管獲利純度勝允強",
     "members": [["2221", "大甲", "下游|白鐵管件"],
                 ["2030", "彰源", "上游|不鏽鋼管(獲利純度高)"],
                 ["2034", "允強", "上游|不鏽鋼管(對照組)"]]},
    {"chain": "玻璃基板TGV鏈", "note": "製程做孔 vs 檢測驗孔",
     "members": [["6207", "雷科", "製程|雷射鑽切"], ["8027", "鈦昇", "製程|雷射加工"],
                 ["8064", "東捷", "製程|玻璃改質"], ["6664", "群翊", "製程|塗佈壓合"],
                 ["3055", "蔚華科", "檢測|三站品管"]]},
    {"chain": "CCL樹脂鏈", "note": "上游樹脂自主化",
     "members": [["4764", "雙鍵", "上游|MPPO/HC樹脂"], ["1815", "富喬", "上游|玻纖布"],
                 ["2383", "台光電", "中游|CCL"], ["6274", "台燿", "中游|CCL"],
                 ["2368", "金像電", "下游|PCB"]]},
]


def load() -> list[dict]:
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    FILE.write_text(json.dumps(_SEED, ensure_ascii=False, indent=1), encoding="utf-8")
    return _SEED


def chain_of(code: str) -> list[dict]:
    """個股所屬的鏈(可能多條)。"""
    return [c for c in load() if any(m[0] == str(code) for m in c["members"])]


def _mom(code: str):
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            c = pd.read_csv(p, usecols=["Close"])["Close"].dropna()
            if len(c) > 21:
                return round(float(c.iloc[-1] / c.iloc[-21] - 1) * 100, 1)
    return None


def relay_view(code: str) -> pd.DataFrame:
    """鏈上全體成員+20日動能(誰先動了、誰還沒動)。"""
    rows = []
    for ch in chain_of(code):
        for m, nm, role in ch["members"]:
            rows.append({"鏈": ch["chain"], "代碼": m, "名稱": nm, "角色": role,
                         "20日%": _mom(m), "本檔": "←" if m == str(code) else ""})
    return pd.DataFrame(rows)


def relay_alerts(breakout_codes: list[str]) -> list[str]:
    """突破名單中若有人在鏈上 → 點名同鏈「還沒動」的夥伴(20日<+10%)。"""
    out = []
    for bc in breakout_codes:
        for ch in chain_of(bc):
            me = next((m for m in ch["members"] if m[0] == str(bc)), None)
            laggards = [f"{nm}{m}({role.split('|')[-1]},20日{_mom(m) or 0:+.0f}%)"
                        for m, nm, role in ch["members"]
                        if m != str(bc) and (_mom(m) or 0) < 10]
            if laggards and me:
                out.append(f"⛓️ {me[1]}{bc} 突破|同鏈「{ch['chain']}」待接力:"
                           + "、".join(laggards))
    return out

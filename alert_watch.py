# -*- coding: utf-8 -*-
"""
alert_watch.py — 警報哨兵:風險燈/前哨/持倉停損「狀態變化」才推 LINE
=================================================================
起因(2026-10-17):「我很怕我沒看到」——系統再準,訊號躺在 App 裡沒人看就是零。
原則:推「變化」不推「狀態」(燈一直紅不會每天吵你;變色、跳分、新前哨、新🛑才推)。
配額:LINE 免費 200 則/月——變化驅動天生省額度。
接線:run_daily 在 market_risk.assess() 之後呼叫 check_and_push();
     sentinel_morning.py 早上抓隔夜數據後也呼叫(同一套去重,不會重複推)。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
D = ROOT / "data"
STATE = D / "_alert_state.json"


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _etf_stops() -> list[str]:
    try:
        import my_etf
        pt = my_etf.positions_table()
        if len(pt):
            return sorted(f"{r['名稱']}{r['代碼']}" for _, r in pt[pt["⚠"] == "🛑"].iterrows())
    except Exception:
        pass
    return []


def check_and_push() -> str:
    cur = _load(D / "_market_risk.json")
    if not cur:
        return "無風險燈資料,略過"
    prev = _load(STATE)
    msgs = []
    # ① 燈變色(含轉好——轉好也要知道,那是劇本 Step 5 的鑰匙)
    if cur.get("lamp") != prev.get("lamp") and prev.get("lamp"):
        msgs.append(f"🚦 風險燈變色:{prev['lamp']} → {cur['lamp']}({cur.get('score')}分)")
    # ② 分數跳升 ≥3(同色內惡化也要知道)
    try:
        if cur["score"] - prev.get("score", cur["score"]) >= 3:
            msgs.append(f"⚠️ 風險分數跳升:{prev.get('score')} → {cur['score']}")
    except Exception:
        pass
    # ③ 新出現的理由(前哨/期貨/事件——只推新增的,已知的不重複吵)
    new_r = [r for r in cur.get("reasons", []) if r not in set(prev.get("reasons", []))]
    for r in new_r:
        if any(k in r for k in ("資金前哨", "外資期貨", "事件日", "亞鄰", "韓-台")):
            msgs.append(f"🔔 {r}")
    # ④ ETF 持倉新觸停損
    stops = _etf_stops()
    new_s = [s for s in stops if s not in set(prev.get("stops", []))]
    if new_s:
        msgs.append("🛑 持倉觸停損:" + "、".join(new_s) + "——家規:跌破就走,不攤平")
    # 存狀態(無論推不推,狀態都要前進,避免重複)
    STATE.write_text(json.dumps({"lamp": cur.get("lamp"), "score": cur.get("score"),
                                 "reasons": cur.get("reasons", []), "stops": stops},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    if not msgs:
        return "無狀態變化,不推"
    text = "📡 tw_backtest 哨兵\n" + "\n".join(msgs[:8])
    try:
        import line_push
        if line_push.enabled():
            return line_push.push_text(text)
        return "LINE 未設定——訊息:" + text[:120]
    except Exception as e:
        return f"推播例外:{type(e).__name__}"


if __name__ == "__main__":
    print(check_and_push())

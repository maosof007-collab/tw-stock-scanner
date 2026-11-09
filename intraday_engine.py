# -*- coding: utf-8 -*-
"""
intraday_engine.py — 盤中引擎(當沖自動化 第①②步,2026-11-09)
=================================================================
「當沖自動化 還需要甚麼?」→ 缺的第一樣:訊號不能跟著網頁活。
這支獨立跑,不開 app 也會:
  1. 每分鐘錄 rt_flow 快照(與頁 42 共用檔,同分鐘去重,不衝突)
  2. 推強勢池駐留提醒(與頁 42 共用 sent 狀態,不重複推)
  3. 盯 short_watch 空方觸發:開盤 ≥ 觸發價(收盤×1.03)→ 記模擬空單 + LINE
  4. 盯停損(逆漲 3.5%)與 13:25 尾盤回補,全部記進模擬倉
模擬倉:data/_paper_short.csv(日期,代號,進場,停損,出場,原因,報酬%)。
跑 2~4 週對帳回放統計(毛利 +1.21%/筆)後,才談券商 API 真單。
下單永遠是人:引擎只推 LINE,不碰任何下單 API。
排程:intraday_task.bat → 工作排程器 tw_intraday_engine(平日 08:58)。
手動測試:python intraday_engine.py --once(跑一輪就退出)
"""
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from twtime import now_tw          # noqa: E402
import rt_flow                     # noqa: E402

LEDGER = ROOT / "data" / "_paper_short.csv"
COLS = ["日期", "代號", "名稱", "觸發價", "進場", "停損", "出場", "出場時間", "原因", "報酬%"]
ENTRY_CUTOFF = (9, 30)    # 09:30 後不再進新單(策略是開盤跳空衰竭)
EOD = (13, 25)            # 尾盤回補
HALT = (13, 33)           # 引擎收工


def _log(msg: str) -> None:
    print(f"[{now_tw():%H:%M:%S}] {msg}", flush=True)


def _push(text: str) -> None:
    try:
        import line_push
        line_push.push_text(text)
    except Exception as e:
        _log(f"LINE 推播失敗:{e}")


def _quotes(codes: list[str]) -> dict:
    """MIS 即時:{code: (開盤, 最新, 昨收)}。0/None 一律當沒價。"""
    uni = rt_flow.universe().drop_duplicates("code").set_index("code")
    items = [f"{uni.loc[c, 'ex']}_{c}.tw" for c in codes if c in uni.index]
    out = {}
    for i in range(0, len(items), rt_flow._BATCH):
        try:
            for r in rt_flow._mis("|".join(items[i:i + rt_flow._BATCH])):
                o, z, y = (rt_flow._num(r.get(k)) for k in ("o", "z", "y"))
                if not z or z <= 0:
                    a0 = rt_flow._num(str(r.get("a", "")).split("_")[0])
                    b0 = rt_flow._num(str(r.get("b", "")).split("_")[0])
                    z = (a0 + b0) / 2 if (a0 and b0) else (a0 or b0)
                out[r["c"]] = (o if (o and o > 0) else None,
                               z if (z and z > 0) else None, y)
        except Exception:
            continue
    return out


def _load() -> pd.DataFrame:
    if LEDGER.exists():
        return pd.read_csv(LEDGER, dtype={"代號": str}, encoding="utf-8-sig")
    return pd.DataFrame(columns=COLS)


def _save(df: pd.DataFrame) -> None:
    df.to_csv(LEDGER, index=False, encoding="utf-8-sig")


def run(once: bool = False) -> None:
    t0 = now_tw()
    if t0.weekday() >= 5:
        _log("週末,收工。")
        return
    today = f"{t0:%Y-%m-%d}"
    while now_tw().hour < 9 and not once:
        time.sleep(20)

    try:
        import short_watch
        wl = short_watch.build_short_watch()
        cand = {str(r["代號"]): r for _, r in wl["df"].iterrows()} if len(wl["df"]) else {}
        _log(f"空方候選 {len(cand)} 檔(榜日 {wl['date']})")
    except Exception:
        cand = {}
        _log("short_watch 載入失敗:\n" + traceback.format_exc())

    led = _load()
    entered = set(led.loc[led["日期"] == today, "代號"].astype(str))

    while True:
        t = now_tw()
        if (t.hour, t.minute) >= HALT:
            break
        try:
            rt_flow.record()
        except Exception:
            _log("快照失敗(略過此輪)")
        try:  # 強勢池駐留提醒(sent 狀態與頁 42 共用,不會重複)
            ss = rt_flow.strong_stocks(rt_flow.load_day())
            for m in rt_flow.strong_alert(ss):
                _push(m)
                _log("推播:" + m.splitlines()[0])
        except Exception:
            pass

        # ── 空方觸發(09:30 前;開盤價一出現就判,只判開盤價)──
        todo = [c for c in cand if c not in entered]
        if todo and (t.hour, t.minute) <= ENTRY_CUTOFF:
            q = _quotes(todo)
            hits = []
            for c in todo:
                o = q.get(c, (None, None, None))[0]
                if o is None:
                    continue
                r = cand[c]
                trig = float(r["觸發價(開盤≥)"])
                entered.add(c)                      # 有開盤價就算判過
                if o >= trig:
                    stop = round(o * (1 + short_watch.STOP_PCT / 100), 2)
                    led = pd.concat([led, pd.DataFrame([{
                        "日期": today, "代號": c, "名稱": r["名稱"], "觸發價": trig,
                        "進場": o, "停損": stop}])], ignore_index=True)
                    hits.append(f"{r['名稱']} {c} 開 {o:g}(≥{trig:g})停損 {stop:g}")
            if hits:
                _save(led)
                _push("🩸 空方觸發(模擬倉已記,現股當沖先賣後買)\n" + "\n".join(hits)
                      + "\n逆漲3.5%回補、13:25 無條件回補;限空令/券源自查")
                _log(f"觸發 {len(hits)} 檔")

        # ── 停損 / 尾盤回補 ──
        pos = led[(led["日期"] == today) & (led["出場"].isna())]
        if len(pos):
            q = _quotes(list(pos["代號"].astype(str)))
            eod = (t.hour, t.minute) >= EOD
            for i, r in pos.iterrows():
                z = q.get(str(r["代號"]), (None, None, None))[1]
                if z is None:
                    continue
                why = "停損" if z >= float(r["停損"]) else ("尾盤回補" if eod else None)
                if why:
                    ret = round((float(r["進場"]) / z - 1) * 100, 2)
                    led.loc[i, ["出場", "出場時間", "原因", "報酬%"]] = [z, f"{t:%H:%M}", why, ret]
                    _push(f"{'🛑' if why == '停損' else '🏁'} {r['名稱']} {r['代號']} {why}"
                          f" {z:g}(空單 {ret:+.2f}%)")
            _save(led)
            if eod:
                done = led[(led["日期"] == today) & led["報酬%"].notna()]
                if len(done):
                    _push("📒 今日模擬空單結算:{} 筆,合計 {:+.2f}%".format(
                        len(done), done["報酬%"].sum()))
                break
        if once:
            break
        time.sleep(max(5, 60 - now_tw().second))
    _log("收工。")


if __name__ == "__main__":
    run(once="--once" in sys.argv)

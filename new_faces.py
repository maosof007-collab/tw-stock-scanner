# -*- coding: utf-8 -*-
"""
new_faces.py — 新面孔雷達(訊號榜的「連續上榜且沒研究過」濃縮器)
=================================================================
起因(2026-10-29):大世科 10/13 起連續兩週在 signals 榜上,但榜單每天 500+ 檔
沒人讀得完,LINE 只推 attention Top20 又沒收它——漏斗斷在中間。
兩條規則(都要「不在研究名單」,每檔一輪只提醒一次):
  ①新面孔:近 5 個掃描日上榜 ≥3 天,且之前 30 個掃描日從未出現(真·初登場)
  ②釘子戶:最近 5 個掃描日「全」上榜(回鍋後賴著不走——大世科 9 月上過榜、
    消失三週、10 月回鍋連續兩週,純「首見」規則抓不到,這條才抓得到)
附一行體檢(research_rank._one),每日 LINE ≤5 檔;同檔 14 日內不重複提醒。
設計原則:同「強勢池駐留提醒」——瞬間上榜是雜訊,賴著不走才值得抬頭。
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
SR = ROOT / "scan_results"
MARK = ROOT / "data" / "_new_faces_sent.txt"
STATE = ROOT / "data" / "_new_faces_state.json"   # code -> 上次提醒日(集數去重)

WINDOW = 5      # 近 N 個掃描日
NEED = 3        # 新面孔:上榜 ≥N 天
LOOKBACK = 30   # 之前 N 個掃描日內出現過 → 不是新面孔
STICKY = 5      # 釘子戶:最近 N 個掃描日全上榜
COOLDOWN = 14   # 同檔兩次提醒最少間隔(日)
TOP = 5


def _codes(f: str) -> set[str]:
    try:
        df = pd.read_csv(f, dtype=str)
        col = "代碼" if "代碼" in df.columns else df.columns[2]
        return {str(c).split(".")[0] for c in df[col].dropna()}
    except Exception:
        return set()


def _known() -> set[str]:
    """已研究名單:出過報的 + 快析過的(research_rank 宇宙)。"""
    try:
        import research_rank as RR
        return set(RR.universe())
    except Exception:
        return set()


def scan(files: list[str] | None = None) -> pd.DataFrame:
    files = files or sorted(glob.glob(str(SR / "signals_2*.csv")))
    if len(files) < WINDOW + 1:
        return pd.DataFrame()
    recent, prior = files[-WINDOW:], files[-(WINDOW + LOOKBACK):-WINDOW]
    seen_prior = set().union(*[_codes(f) for f in prior]) if prior else set()
    sets = [_codes(f) for f in recent]
    cnt: dict[str, int] = {}
    for s in sets:
        for c in s:
            cnt[c] = cnt.get(c, 0) + 1
    known = _known()
    sticky_all = set.intersection(*sets[-STICKY:]) if len(sets) >= STICKY else set()
    kinds: dict[str, str] = {}
    for c, n in cnt.items():
        if not (c.isdigit() and len(c) == 4) or c in known:
            continue
        if n >= NEED and c not in seen_prior:
            kinds[c] = "新面孔"
        elif c in sticky_all:
            kinds[c] = "釘子戶"
    cands = list(kinds)
    if not cands:
        return pd.DataFrame()
    # 一行體檢
    import research_rank as RR
    rev = pd.read_csv(RR.D / "bulk_fin" / "rev_all.csv.gz", dtype={"code": str})
    q = pd.read_csv(RR.D / "bulk_fin" / "fin_q_all.csv.gz", dtype={"code": str})
    # 集數去重:14 日內提醒過的不再出現
    try:
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    except Exception:
        state = {}
    from twtime import now_tw
    today = pd.Timestamp(f"{now_tw():%Y-%m-%d}")
    cands = [c for c in cands
             if c not in state or (today - pd.Timestamp(state[c])).days >= COOLDOWN]
    if not cands:
        return pd.DataFrame()
    rows = []
    for c in cands:
        r = RR._one(c, rev, q) or {"代碼": c, "名稱": ""}
        r["上榜天"] = cnt[c]
        r["類型"] = kinds[c]
        rows.append(r)
    df = pd.DataFrame(rows)
    # 排序:新面孔優先 → 上榜天 → 60日動能
    df["_k"] = (df["類型"] == "新面孔").astype(int)
    df = df.sort_values(["_k", "上榜天", "60日%"], ascending=False).drop(columns="_k")
    return df.head(TOP)


def _mark_sent(df: pd.DataFrame) -> None:
    from twtime import now_tw
    try:
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    except Exception:
        state = {}
    for c in df["代碼"]:
        state[str(c)] = f"{now_tw():%Y-%m-%d}"
    STATE.write_text(json.dumps(state), encoding="utf-8")


def _fmt(df: pd.DataFrame) -> str:
    lines = ["👀 新面孔雷達|連續上榜但你還沒研究過"]
    for _, r in df.iterrows():
        flags = []
        m = r.get("融資%")
        if pd.notna(m) and m is not None and float(m) >= 30:
            flags.append(f"融資{float(m):.0f}%⚠")
        if r.get("爆量窗"):
            flags.append("爆量窗")
        if r.get("處置"):
            flags.append("處置⚠")
        lines.append(
            f"・{r.get('類型','')} {r.get('名稱','')} {r['代碼']}|近{WINDOW}掃描日上榜{r['上榜天']}天|"
            f"收{r.get('收盤','-')} 距年高{r.get('距年高%','-')}% 60日{r.get('60日%','-')}%|"
            f"營收YoY3 {r.get('營收YoY3','-')}% 外資天{r.get('外資天','-')}"
            + (f"|{'/'.join(flags)}" if flags else ""))
    lines.append("—觀察非買單;想深挖哪檔再開報告")
    return "\n".join(lines)


def push() -> str:
    """每日一次;無新面孔就安靜(不推空訊息)。給 notify_push 掛。"""
    from twtime import now_tw
    today = f"{now_tw():%Y-%m-%d}"
    if MARK.exists() and MARK.read_text().strip() == today:
        return "今日已推過"
    df = scan()
    if df.empty:
        MARK.write_text(today)
        return "無新面孔(安靜)"
    msg = _fmt(df)
    try:
        import line_push
        if line_push.enabled():
            line_push.push_text(msg)
            MARK.write_text(today)
            _mark_sent(df)
            return f"推播 {len(df)} 檔 ✅"
    except Exception as e:
        return f"LINE 失敗:{e}"
    MARK.write_text(today)
    _mark_sent(df)
    return f"找到 {len(df)} 檔(LINE 未啟用)\n{msg}"


if __name__ == "__main__":
    d = scan()
    print(d.to_string(index=False) if len(d) else "無新面孔")
    if len(d):
        print("\n" + _fmt(d))

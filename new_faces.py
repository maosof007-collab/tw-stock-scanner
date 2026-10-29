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
LOG = ROOT / "data" / "_new_faces_log.csv"        # 提醒日誌(回溯+實盤累積,頁面驗證用)

WINDOW = 5      # 近 N 個掃描日
NEED = 3        # 新面孔:上榜 ≥N 天
LOOKBACK = 30   # 之前 N 個掃描日內出現過 → 不是新面孔
STICKY = 5      # 釘子戶:最近 N 個掃描日全上榜
RETURN_MAX = .4  # 釘子戶的「回鍋」條件:前30掃描日出現率≤40%(常年掛榜的不算,
#                  消失過再回來賴著才是訊號——大世科 9月上榜→消失3週→10月回鍋)
COOLDOWN = 14   # 同檔兩次提醒最少間隔(日)
# 分層(2026-10-29 全程回放的教訓:任何「每日N檔」硬上限都會漏魚——大世科就被
# 「新面孔優先」擠掉過):日誌全收、全回測;LINE 只推 5 檔摘要,漏的去頁面看
PUSH_STICKY = 3   # LINE:釘子戶名額(按60日動能)
PUSH_FRESH = 2    # LINE:新面孔名額(按上榜天→動能)


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


def _candidates(files: list[str]) -> dict[str, tuple[str, int]]:
    """核心偵測:files 的最後 WINDOW 天為「近期」→ code -> (類型, 上榜天)。"""
    if len(files) < WINDOW + 1:
        return {}
    recent, prior = files[-WINDOW:], files[-(WINDOW + LOOKBACK):-WINDOW]
    prior_sets = [_codes(f) for f in prior]
    seen_prior = set().union(*prior_sets) if prior_sets else set()
    prior_cnt: dict[str, int] = {}
    for s in prior_sets:
        for c in s:
            prior_cnt[c] = prior_cnt.get(c, 0) + 1
    sets = [_codes(f) for f in recent]
    cnt: dict[str, int] = {}
    for s in sets:
        for c in s:
            cnt[c] = cnt.get(c, 0) + 1
    known = _known()
    sticky_all = set.intersection(*sets[-STICKY:]) if len(sets) >= STICKY else set()
    kinds: dict[str, tuple[str, int]] = {}
    for c, n in cnt.items():
        if not (c.isdigit() and len(c) == 4) or c in known:
            continue
        if n >= NEED and c not in seen_prior:
            kinds[c] = ("新面孔", n)
        elif c in sticky_all and prior_cnt.get(c, 0) <= RETURN_MAX * max(len(prior_sets), 1):
            kinds[c] = ("釘子戶", n)   # 回鍋型:消失過又回來賴著,常年掛榜的不算
    return kinds


def scan(files: list[str] | None = None) -> pd.DataFrame:
    files = files or sorted(glob.glob(str(SR / "signals_2*.csv")))
    kinds = _candidates(files)
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
        r["上榜天"] = kinds[c][1]
        r["類型"] = kinds[c][0]
        r["性質"], r["證據"] = diagnose(c, q, r)
        rows.append(r)
    df = pd.DataFrame(rows)
    # 全收不設上限(頁面看全池);LINE 摘要由 pick_push 另挑
    return df.sort_values(["類型", "60日%"], ascending=[False, False])


def pick_push(df: pd.DataFrame) -> pd.DataFrame:
    """LINE 摘要:釘子戶3(60日動能)+新面孔2(上榜天→動能)。漏網的在頁面全池。"""
    if df.empty:
        return df
    st_ = df[df["類型"] == "釘子戶"].sort_values("60日%", ascending=False)
    fr_ = df[df["類型"] == "新面孔"].sort_values(["上榜天", "60日%"], ascending=False)
    return pd.concat([st_.head(PUSH_STICKY), fr_.head(PUSH_FRESH)])


# ───────────────── 性質診斷:炒作?題材?還是還他公道? ─────────────────
def _pe_ttm(code: str, q: pd.DataFrame, price: float | None) -> float | None:
    """近四季 EPS 合計 → PE(TTM);虧損或缺資料回 None。"""
    try:
        eps = (q[q.code == code].sort_values("季度").EPS.astype(float).tail(4))
        t = float(eps.sum())
        return round(float(price) / t, 1) if len(eps) == 4 and t > 0 and price else None
    except Exception:
        return None


def _theme_of(code: str) -> str | None:
    try:
        from theme_groups import THEME_GROUPS
        for g, codes in THEME_GROUPS.items():
            if code in codes:
                return g
    except Exception:
        pass
    return None


def diagnose(code: str, q: pd.DataFrame, r: dict) -> tuple[str, str]:
    """「最後找原因:單純炒作?有題材?還是 PE 太低還他公道?」(2026-10-29)
    規則式三分法,證據全印出來——這是初判,不是結論,深挖還是開報告。"""
    pe = _pe_ttm(code, q, r.get("收盤"))
    yoy = r.get("營收YoY3")
    yoy = float(yoy) if pd.notna(yoy) and yoy is not None else None
    theme = _theme_of(code)
    # 炒作跡象計數:籌碼面全是散戶的腳印
    hype = []
    m = r.get("融資%")
    if pd.notna(m) and m is not None and float(m) >= 30:
        hype.append(f"融資{float(m):.0f}%")
    if r.get("爆量窗"):
        hype.append("爆量窗")
    if r.get("外資天") == 0:
        hype.append("外資0天")
    if r.get("處置"):
        hype.append("處置")
    fund = yoy is not None and yoy >= 20          # 基本面:營收三月YoY≥20%
    if pe is None and not fund:
        hype.append("無獲利")                      # 近四季虧損又沒營收故事 → 炒作跡象
    value = pe is not None and pe <= 12 and (yoy is None or yoy > -5)   # 低PE且沒在爛
    ev = []
    if pe is not None:
        ev.append(f"PE {pe}")
    elif pe is None and r.get("收盤"):
        ev.append("近四季虧損/無EPS")
    if yoy is not None:
        ev.append(f"YoY3 {yoy:+.0f}%")
    if theme:
        ev.append(f"題材:{theme}")
    ev += hype
    if value and len(hype) < 2:
        tag = "還他公道"                           # 低估值補漲,籌碼乾淨
    elif fund and len(hype) >= 2:
        tag = "題材+過熱⚠"                        # 故事是真的,但散戶擠滿車
    elif fund or (theme and yoy is not None and yoy > 0):
        tag = "題材"
    elif len(hype) >= 2:
        tag = "炒作⚠"                             # 沒基本面、全靠籌碼
    else:
        tag = "不明"
    return tag, "|".join(ev) if ev else "資料不足"


# ───────────────── 回溯與績效(雷達準不準,用歷史驗) ─────────────────
_PX: dict[str, pd.Series | None] = {}   # 日線快取(回溯/績效要掃上千檔)


def _px(code: str) -> pd.Series | None:
    if code in _PX:
        return _PX[code]
    s = None
    for suf in (".TW.csv", ".TWO.csv"):
        p = ROOT / "data" / f"{code}{suf}"
        if p.exists():
            try:
                ser = pd.read_csv(p, parse_dates=["Date"]).set_index("Date")["Close"]
                s = ser[ser > 0]
            except Exception:
                s = None
            break
    _PX[code] = s
    return s


def backfill() -> pd.DataFrame:
    """用歷史 signals 檔逐日重放雷達(含冷卻+每日≤TOP),寫 data/_new_faces_log.csv。
    注意:排除名單用「今天的」研究宇宙(歷史當下更少),所以回溯偏嚴、實盤只會更早叫。"""
    files = sorted(glob.glob(str(SR / "signals_2*.csv")))
    state: dict[str, pd.Timestamp] = {}
    rows = []
    for i in range(WINDOW + 1, len(files) + 1):
        sub = files[:i]
        d = pd.Timestamp(Path(sub[-1]).stem.split("_")[1])
        kinds = _candidates(sub)
        cands = [(c, k, n) for c, (k, n) in kinds.items()
                 if c not in state or (d - state[c]).days >= COOLDOWN]
        for c, k, n in cands:          # 日誌全收(LINE 另挑摘要,頁面看全池)
            state[c] = d
            s = _px(c)
            px = float(s[s.index <= d].iloc[-1]) if s is not None and len(s[s.index <= d]) else None
            rows.append({"提醒日": f"{d:%Y-%m-%d}", "代號": c, "類型": k,
                         "上榜天": n, "當日收盤": px})
    log = pd.DataFrame(rows)
    if len(log):
        try:
            from symbols import resolve
            log["名稱"] = [resolve(c)[1] or c for c in log["代號"]]
        except Exception:
            log["名稱"] = log["代號"]
        log = log[["提醒日", "代號", "名稱", "類型", "上榜天", "當日收盤"]]
        log.to_csv(LOG, index=False, encoding="utf-8-sig")
        # 冷卻狀態也交接給實盤(不然 scan() 不知道回溯提醒過誰,隔天整池重炸)
        STATE.write_text(json.dumps({c: f"{d:%Y-%m-%d}" for c, d in state.items()}),
                         encoding="utf-8")
    return log


def _log_append(df: pd.DataFrame) -> None:
    """實盤提醒也進日誌(與回溯同一張表,頁面才能持續驗證)。(提醒日,代號) 去重。"""
    from twtime import now_tw
    today = f"{now_tw():%Y-%m-%d}"
    rows = [{"提醒日": today, "代號": str(r["代碼"]), "名稱": r.get("名稱", ""),
             "類型": r.get("類型", ""), "上榜天": r.get("上榜天", ""),
             "當日收盤": r.get("收盤")} for _, r in df.iterrows()]
    new = pd.DataFrame(rows)
    try:
        old = pd.read_csv(LOG, dtype={"代號": str}) if LOG.exists() else pd.DataFrame()
        out = pd.concat([old, new]).drop_duplicates(["提醒日", "代號"], keep="first")
        out.to_csv(LOG, index=False, encoding="utf-8-sig")
    except Exception:
        pass


def performance() -> pd.DataFrame:
    """日誌 + 日線 → 每筆提醒的現價/報酬%/提醒後最高漲幅%/天數。"""
    if not LOG.exists():
        return pd.DataFrame()
    log = pd.read_csv(LOG, dtype={"代號": str})
    out = []
    for _, r in log.iterrows():
        s = _px(r["代號"])
        d0, p0 = pd.Timestamp(r["提醒日"]), r["當日收盤"]
        row = dict(r)
        if s is not None and pd.notna(p0) and p0:
            after = s[s.index >= d0]
            if len(after):
                row["現價"] = round(float(s.iloc[-1]), 1)
                row["報酬%"] = round((float(s.iloc[-1]) / p0 - 1) * 100, 1)
                row["最高漲幅%"] = round((float(after.max()) / p0 - 1) * 100, 1)
                row["天數"] = int((s.index[-1] - d0).days)
        out.append(row)
    return pd.DataFrame(out)


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
            f"・{r.get('類型','')} {r.get('名稱','')} {r['代碼']}"
            f"【{r.get('性質','')}】|近{WINDOW}掃描日上榜{r['上榜天']}天|"
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
    _log_append(df)                       # 全池進日誌(頁面回測用)
    pick = pick_push(df)                  # LINE 只推摘要
    msg = _fmt(pick) + f"\n(全池 {len(df)} 檔 → 網頁「新面孔雷達」看)"
    try:
        import line_push
        if line_push.enabled():
            line_push.push_text(msg)
            MARK.write_text(today)
            _mark_sent(df)
            return f"推播 {len(pick)}/{len(df)} 檔 ✅"
    except Exception as e:
        return f"LINE 失敗:{e}"
    MARK.write_text(today)
    _mark_sent(df)
    return f"找到 {len(df)} 檔(LINE 未啟用)\n{msg}"


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "backfill":
        log = backfill()
        print(f"回溯完成:{len(log)} 筆提醒 → {LOG}")
        perf = performance()
        if len(perf):
            print(perf.to_string(index=False))
    else:
        d = scan()
        print(d.to_string(index=False) if len(d) else "無新面孔")
        if len(d):
            print("\n" + _fmt(d))

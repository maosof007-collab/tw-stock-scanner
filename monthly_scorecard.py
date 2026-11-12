# -*- coding: utf-8 -*-
"""
monthly_scorecard.py — 系統月度記分卡:哪些符合預期、哪些沒用,每月對一次總帳
=================================================================
起因(2026-11-12 使用者):「每個月更新一下吧,那些符合預期那些沒用,要出個總結。」
素材全是現成的,只做彙整:
  A 預實追蹤 model_track.check_all()(🟢🟡🔴 對答案)
  B 策略衰減 strategy_decay.compute()——現場重算!
    (CSV 設計「run_daily 週六重算」,但排程只跑平日 → 永遠停在舊日期的教案)
  C 強勢榜戰績 attention_replay.review_line()
  D 失土收復率月變化(有進行中週期才有)
分層鐵律:全文存進研究文章庫(mode=記分卡,頁「研究文章庫」可讀),
推播一則濃縮。每月 11 日後第一個排程時段產出(marker 防重)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"
MARK = D / "_scorecard_sent.txt"


def _sec_track() -> tuple[list[str], list[str]]:
    """A 預實追蹤 → (md_lines, push_lines)。"""
    from model_track import check_all
    df = check_all()
    if df.empty:
        return (["(無預測記錄)"], [])
    opened = df[~df["燈號"].str.startswith("⏳")]
    cnt = opened["燈號"].value_counts()
    g, y, r = int(cnt.get("🟢", 0)), int(cnt.get("🟡", 0)), int(cnt.get("🔴", 0))
    md = [f"累計已開獎 **{len(opened)}** 筆:🟢{g} 🟡{y} 🔴{r}(⏳未開獎 {len(df) - len(opened)})", ""]
    # 按來源算命中率:誰的預測能用、誰的沒用
    md.append("| 來源 | 筆數 | 🟢 | 🔴 | 判定 |")
    md.append("|---|---|---|---|---|")
    push = []
    for src, gdf in opened.groupby("來源"):
        n = len(gdf)
        if n < 3:
            continue
        gr = (gdf["燈號"] == "🟢").mean()
        rr = (gdf["燈號"] == "🔴").mean()
        verdict = "✅ 可用" if gr >= 0.5 else ("⚠️ 參考用" if rr < 0.5 else "❌ 沒用,別再信")
        md.append(f"| {src} | {n} | {gr * 100:.0f}% | {rr * 100:.0f}% | {verdict} |")
        push.append(f"{src}:🟢{gr * 100:.0f}%/🔴{rr * 100:.0f}% {verdict.split()[0]}")
    # 本期開獎(上個月的月營收+最近開的季報)
    t = now_tw()
    pm = f"{t.year}-{t.month - 1:02d}" if t.month > 1 else f"{t.year - 1}-12"
    cur = opened[opened["期間"] == pm]
    if len(cur):
        md += ["", f"**本期開獎({pm} 月營收)**:"]
        for _, row in cur.iterrows():
            md.append(f"- {row['燈號']} {row['代碼']} {row['來源']}:預測 {row['預測']:,.0f} → "
                      f"實際 {row['實際']} (誤差 {row['誤差']})")
    return md, push


def _sec_decay() -> tuple[list[str], list[str]]:
    """B 策略衰減(現場重算,不吃停在 9/20 的舊 CSV)。"""
    from strategy_decay import compute
    df = compute()
    if df.empty:
        return (["(無資料)"], [])
    md = ["| 策略 | 近期EV% | 歷史EV% | 狀態 | 勝率% |", "|---|---|---|---|---|"]
    push = []
    for _, r in df.iterrows():
        md.append(f"| {r['策略']} | {r['近期EV(fwd20)%']} | {r['歷史EV%']} | {r['狀態']} | {r['勝率%']} |")
    dead = df[df["狀態"].astype(str).str.contains("🔴")]
    ok = df[df["狀態"].astype(str).str.contains("🟢")]
    if len(dead):
        push.append("🔴失效策略:" + "、".join(dead["策略"].astype(str).str[:10]))
    if len(ok):
        push.append("🟢仍有效:" + "、".join(ok["策略"].astype(str).str[:10]))
    md += ["", "⚠️ 判讀警語:近 60 日視窗落在大跌段時,多頭策略 EV 被壓爛屬**天氣問題**,"
           "不等於體質失效——連兩個月(跨到回升段)還 🔴 才停用;空頭段反而該看哪些策略逆勢 🟢(那才是真信號)。"]
    return md, push


def _sec_attention() -> tuple[list[str], list[str]]:
    from attention_replay import review_line
    ln = review_line()
    return ([ln], [ln.split("|")[0].strip()])


def _sec_recovery() -> tuple[list[str], list[str]]:
    p = D / "recovery_rate.csv"
    if not p.exists():
        return (["(本月無進行中大跌週期)"], [])
    h = pd.read_csv(p)
    t = now_tw()
    cur = h[h["asof"].astype(str).str.startswith(f"{t:%Y-%m}")]
    if cur.empty:
        return (["(本月無觀測)"], [])
    a, b = cur.iloc[0], cur.iloc[-1]
    ln = (f"失土收復率 {a['asof'][5:]} {a['full_pct']}% → {b['asof'][5:]} {b['full_pct']}%"
          f"(大盤回升 {b['twii_pos']}%)")
    return ([ln], [ln])


def build_report() -> tuple[str, str]:
    """回傳 (全文md, 推播濃縮)。各節獨立 try——一節壞了不拖全卡。"""
    t = now_tw()
    md = [f"# 系統記分卡 {t.year}/{t.month:02d} — 哪些符合預期、哪些沒用", ""]
    push = [f"📇 系統記分卡 {t.year}/{t.month:02d}"]
    for title, fn in [("一、預實追蹤(預測 vs 實際)", _sec_track),
                      ("二、策略衰減(近60日 vs 歷史回測EV)", _sec_decay),
                      ("三、強勢榜戰績", _sec_attention),
                      ("四、失土收復率(本月)", _sec_recovery)]:
        md += [f"## {title}", ""]
        try:
            m, p = fn()
            md += m + [""]
            push += p[:3]
        except Exception as e:
            md += [f"(本節產出失敗:{type(e).__name__}: {e})", ""]
    md += ["---", "規則:🔴 的來源/策略下月**降權或停用**;🟢 的保留;新預測一律先進 model_track 再談。",
           "全文存研究文章庫(mode=記分卡);本卡每月 11 日後自動產出。"]
    return "\n".join(md), "\n".join(push[:10])[:1500]


def push() -> str:
    """每月一次:11 日後(月營收 10 日公布完)第一個排程時段。"""
    t = now_tw()
    ym = f"{t:%Y-%m}"
    if t.day < 11:
        return "未到 11 日(等月營收公布完),跳過"
    if MARK.exists() and MARK.read_text() == ym:
        return "本月記分卡已出過,跳過"
    md, condensed = build_report()
    from analyst_report import save_article
    fname = save_article("SYS", "系統記分卡", "記分卡", md)
    import line_push
    r = line_push.push_text(condensed) if line_push.enabled() else "推播未設定(文章已存)"
    MARK.write_text(ym)
    return f"已存 {fname};推播:{r}"


if __name__ == "__main__":
    import sys
    md, condensed = build_report()
    print(md)
    print("\n===== 推播濃縮 =====\n" + condensed)
    if "--push" in sys.argv:
        print(push())

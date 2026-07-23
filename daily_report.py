"""
daily_report.py — 每日強弱日報（自動成文）
=================================================================
把「大盤 → 族群今日強弱 → RRG 資金輪動 → 新聞熱度」縫成一篇
人看得有感覺的短文，而不是一堆表格。

兩段式：
  1. build_digest()   蒐集當日數據（純 pandas，離線可跑）
  2. write_article()  規則式成文；若有 ANTHROPIC_API_KEY 再用 Claude 潤稿
"""
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd

from twtime import now_tw
from theme_groups import THEME_GROUPS

ROOT = Path(__file__).parent
DATA = ROOT / "data"


# ────────────────────────────────────────
# 數據蒐集
# ────────────────────────────────────────
def _last2_close(code: str):
    """個股最近兩日收盤（回 None 表示無資料）"""
    for suf in (".TW", ".TWO"):
        p = DATA / f"{code}{suf}.csv"
        if p.exists():
            try:
                df = pd.read_csv(p, usecols=[0, 4])
                df.columns = ["date", "close"]
                s = pd.to_numeric(df["close"], errors="coerce").dropna()
                if len(s) >= 2:
                    return float(s.iloc[-2]), float(s.iloc[-1]), str(df["date"].iloc[-1])[:10]
            except Exception:
                pass
    return None


def _bench_today():
    p = DATA / "benchmark_TWII.csv"
    if not p.exists():
        return None
    b = pd.read_csv(p)
    c = pd.to_numeric(b["Close"], errors="coerce").dropna()
    if len(c) < 65:
        return None
    chg = (c.iloc[-1] / c.iloc[-2] - 1) * 100
    ma60 = c.tail(60).mean()
    return {
        "close": round(float(c.iloc[-1])),
        "chg": round(float(chg), 2),
        "above_ma60": bool(c.iloc[-1] > ma60),
        "date": str(b["Date"].iloc[-1])[:10],
    }


def _theme_daily():
    """各族群今日平均漲跌 + 領軍個股"""
    name_map = {}
    try:
        sl = pd.read_csv(DATA / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        name_map = dict(zip(sl["code"], sl["name"]))
    except Exception:
        pass
    rows = []
    for theme, codes in THEME_GROUPS.items():
        chgs = []
        for c in codes:
            r = _last2_close(c)
            if r:
                chgs.append((name_map.get(c, c), (r[1] / r[0] - 1) * 100))
        if len(chgs) < 2:
            continue
        avg = sum(v for _, v in chgs) / len(chgs)
        lead = max(chgs, key=lambda x: x[1]) if avg >= 0 else min(chgs, key=lambda x: x[1])
        rows.append({"族群": theme, "chg": round(avg, 2),
                     "lead_name": lead[0], "lead_chg": round(lead[1], 2)})
    df = pd.DataFrame(rows)
    return df.sort_values("chg", ascending=False).reset_index(drop=True) if not df.empty else df


def _tail_dir(tail: pd.DataFrame) -> str:
    """尾巴方向：比較最新點與 2~3 週前"""
    if tail is None or len(tail) < 3:
        return ""
    dx = tail["ratio"].iloc[-1] - tail["ratio"].iloc[-3]
    dy = tail["mom"].iloc[-1] - tail["mom"].iloc[-3]
    if dx > 0.1 and dy > 0.1:
        return "往右上（資金流入）"
    if dx < -0.1 and dy < -0.1:
        return "往左下（資金流出）"
    if dy > 0.1:
        return "動能回升"
    if dy < -0.1:
        return "動能轉弱"
    return "橫向整理"


def _rrg_view():
    """族群 RRG：象限 + 尾巴方向"""
    try:
        from sector_rrg import build_rrg
        pts, tails, _ = build_rrg(min_members=2, max_members=10, groups=THEME_GROUPS)
        if pts.empty:
            return {}
        return {r["產業"]: {"quad": r["象限"], "dir": _tail_dir(tails.get(r["產業"]))}
                for _, r in pts.iterrows()}
    except Exception:
        return {}


def _news_view(win: int = 7):
    """新聞熱度：{產業: (熱度Δ%, 情緒)}"""
    try:
        from news_trend import build_sector_trend
        trend, _, _ = build_sector_trend(win=win)
        if trend.empty:
            return {}
        return {r["產業"]: (r["熱度Δ%"], r["情緒"]) for _, r in trend.iterrows()}
    except Exception:
        return {}


def build_digest() -> dict:
    return {
        "bench": _bench_today(),
        "themes": _theme_daily(),
        "rrg": _rrg_view(),
        "news": _news_view(),
        "generated": now_tw().strftime("%Y-%m-%d %H:%M"),
    }


# ────────────────────────────────────────
# 規則式成文
# ────────────────────────────────────────
def _fmt_theme_line(r, rrg) -> str:
    info = rrg.get(r["族群"], {})
    quad = info.get("quad", "")
    dirn = info.get("dir", "")
    extra = []
    if quad:
        extra.append(f"RRG {quad}象限")
    if dirn and dirn != "橫向整理":
        extra.append(dirn)
    tail = f"（{'、'.join(extra)}）" if extra else ""
    verb = "領軍" if r["chg"] >= 0 else "最重"
    return (f"**{r['族群']} {r['chg']:+.2f}%**，{r['lead_name']} {r['lead_chg']:+.2f}% {verb}{tail}")


def write_article(d: dict) -> str:
    bench, themes, rrg, news = d["bench"], d["themes"], d["rrg"], d["news"]
    if themes is None or themes.empty:
        return "（資料不足，還無法產生日報）"

    strong = themes.head(3)
    weak = themes.tail(3).iloc[::-1]
    date_str = bench["date"] if bench else now_tw().strftime("%Y-%m-%d")

    # 資料過期偵測：資料日落後「上一個應收盤交易日」就大聲警告，別讓人以為時間錯了
    stale_note = ""
    if bench:
        today = now_tw()
        expect = today.date()
        # 今天還沒收盤(<14:00)或假日 → 往前找最近一個工作日
        if today.weekday() >= 5 or today.hour < 14:
            d = pd.Timestamp(expect) - pd.Timedelta(days=1)
            while d.weekday() >= 5:
                d -= pd.Timedelta(days=1)
            expect = d.date()
        behind = len(pd.bdate_range(bench["date"], expect)) - 1
        if behind >= 1:
            stale_note = (f"\n> ⚠️ **注意：資料只到 {date_str}，已落後約 {behind} 個交易日。**"
                          f"標題日期＝資料日（不是今天）。請等背景更新完成，"
                          f"或到「更新進度」頁按立即更新後重新生成。\n")

    # 一句話總結
    s_names = "、".join(strong["族群"])
    w_names = "、".join(weak["族群"])
    if bench:
        updn = "漲" if bench["chg"] >= 0 else "跌"
        tone = ("多方續攻" if bench["chg"] > 0.8 else "偏多整理" if bench["chg"] > 0
                else "偏空整理" if bench["chg"] > -0.8 else "空方壓境")
        summary = (f"大盤{updn} {abs(bench['chg']):.2f}%（{tone}），"
                   f"資金往 {s_names} 靠攏，{w_names} 相對承壓。")
    else:
        summary = f"資金往 {s_names} 靠攏，{w_names} 相對承壓。"

    L = [f"# 📋 {date_str} 台股強弱日報", stale_note, f"> {summary}", ""]

    # 大盤
    if bench:
        ma = "季線之上，中期多頭架構未壞" if bench["above_ma60"] else "季線之下，中期趨勢偏空、操作宜保守"
        L += ["## 大盤",
              f"加權指數收 **{bench['close']:,}**（{bench['chg']:+.2f}%），位於{ma}。", ""]

    # 強勢
    L += ["## 🔴 今日最強"]
    for _, r in strong.iterrows():
        L.append(f"- {_fmt_theme_line(r, rrg)}")
    L.append("")

    # 弱勢
    L += ["## 🟣 今日相對弱"]
    for _, r in weak.iterrows():
        L.append(f"- {_fmt_theme_line(r, rrg)}")
    L.append("")

    # 資金輪動觀察：改善且往右上 = 接近轉領先；領先但動能轉弱 = 注意
    rising = [t for t, v in rrg.items()
              if v["quad"] == "改善" and "右上" in (v["dir"] or "")]
    tiring = [t for t, v in rrg.items()
              if v["quad"] in ("領先", "弱化") and ("左下" in (v["dir"] or "") or "轉弱" in (v["dir"] or ""))]
    if rising or tiring:
        L += ["## 🔄 資金輪動觀察"]
        if rising:
            L.append(f"- **接近轉入領先**：{'、'.join(rising)}——改善象限且軌跡持續往右上，"
                     f"是輪動打法最想等的位置。")
        if tiring:
            L.append(f"- **動能退潮**：{'、'.join(tiring)}——位階仍高但動能走弱，"
                     f"持有者留意移動停利，別追高。")
        L.append("")

    # 明日觀察：新聞轉熱 + 情緒偏多
    hot = [(s, mom, sen) for s, (mom, sen) in news.items() if mom > 50 and sen >= 0]
    hot.sort(key=lambda x: -x[1])
    if hot:
        L += ["## 👀 明日觀察（消息面轉熱）"]
        for s, mom, sen in hot[:5]:
            mood = "偏多" if sen > 0.1 else "中性"
            L.append(f"- **{s}**：新聞熱度 {mom:+.0f}%、風向{mood}")
        L.append("")

    L += ["---",
          f"*本文由系統於 {d['generated']}（台灣時間）自動生成，數據源：族群等權漲跌、"
          f"JdK RRG 近似輪動、產業新聞熱度。僅供參考，非投資建議。*"]
    return "\n".join(L)


# ────────────────────────────────────────
# Claude 潤稿（選配）
# ────────────────────────────────────────
def polish_with_claude(article: str) -> str | None:
    """把規則式文章交給 Claude 重寫得更口語（API 或本機 Claude CLI）；不可用回 None。"""
    from llm import generate
    return generate(
        ("你是台股資深盤後主筆。若原文含「⚠️」開頭的警告行，必須原封不動保留在標題下方。"
         "把使用者給的數據型日報改寫成 400-600 字、"
         "口語有畫面感的盤後短評：保留所有數字與族群名，用「資金像水」的敘事"
         "串起強弱與輪動，分 3-4 段，開頭一句抓住今天的主軸，結尾給一句"
         "明日觀察。輸出 markdown，標題沿用原標題。不加免責聲明（原文已有）。"),
        article, max_tokens=1500)


def generate(polish: bool = True) -> str:
    d = build_digest()
    art = write_article(d)
    if polish:
        p = polish_with_claude(art)
        if p:
            art = p + "\n\n---\n*本文由 Claude 依系統數據撰寫，僅供參考，非投資建議。*"
    return art

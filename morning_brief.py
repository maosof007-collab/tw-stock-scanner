"""
morning_brief.py — 台股盤前晨報(每日 07:15 排程,08:00 前上雲)
=================================================================
① 隔夜國際盤面(美股四大+費半+台積電ADR+油價/美元)— yfinance
② 隔夜國內外新聞(Google News/鉅亨/Yahoo RSS)→ Claude 逐則評論
③ 今日主流族群預判(隔夜盤面 × 昨日族群動能 × 新聞催化)
④ 行事曆(期貨結算日/月營收公布旬)
產出 → data/research_articles/(mode=晨報)→ git push → 雲端「研究文章」可讀
無 Claude 引擎時退化為純數據版(表格+標題,無評論)。

執行:python morning_brief.py [--force]
      (同日已產生過會跳過,--force 強制重寫)
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from twtime import now_tw

try:                                    # Windows 主控台/排程 log 是 cp950,印 emoji 會炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ────────────────────────────────────────
# ① 隔夜國際盤面
# ────────────────────────────────────────
_TICKERS = [
    ("^DJI",    "道瓊工業"),
    ("^GSPC",   "S&P 500"),
    ("^IXIC",   "那斯達克"),
    ("^SOX",    "費城半導體"),
    ("TSM",     "台積電 ADR"),
    ("NVDA",    "輝達"),
    ("CL=F",    "WTI 原油"),
    ("TWD=X",   "美元兌台幣"),
]


def overnight_markets() -> pd.DataFrame:
    """美股收盤與關鍵商品:最後兩個交易日收盤 → 漲跌%。抓不到的略過。"""
    import yfinance as yf
    rows = []
    for sym, label in _TICKERS:
        try:
            h = yf.Ticker(sym).history(period="7d")["Close"].dropna()
            if len(h) < 2:
                continue
            last, prev = float(h.iloc[-1]), float(h.iloc[-2])
            rows.append({"項目": label,
                         "收盤": round(last, 2),
                         "漲跌%": round((last / prev - 1) * 100, 2),
                         "日期": h.index[-1].strftime("%m/%d")})
        except Exception:
            continue
    return pd.DataFrame(rows)


# ────────────────────────────────────────
# ② 隔夜新聞(近 20 小時)
# ────────────────────────────────────────
_QUERIES = ["台股 盤前", "美股 收盤", "聯準會 利率", "半導體 台積電",
            "AI 伺服器", "中國 經濟", "地緣政治 關稅",
            "運價 航運"]     # 航運領先事件:搶運/塞港/紅海/罷工/SCFI——新聞是這些訊號的最快載體


def overnight_news(max_items: int = 45) -> list[dict]:
    """近20小時新聞:[{stamp, source, title, url}](新到舊,去重)。"""
    import fetch_news as fn
    items = []
    for q in _QUERIES:
        try:
            items += fn.fetch_google_news_rss(q)
        except Exception:
            continue
    for f in (lambda: fn.fetch_cnyes_rss(), lambda: fn.fetch_yahoo_finance_rss("台股")):
        try:
            items += f()
        except Exception:
            continue
    seen, out = set(), []
    now = now_tw().replace(tzinfo=None)
    # 盤前資訊集鐵律:新聞窗上緣最多到當天 08:30(開盤前)。
    # 07:15 正常跑不受影響;下午補跑時擋掉盤中/盤後新聞,預判才不會有事後之明。
    end = min(now, now.replace(hour=8, minute=30, second=0, microsecond=0))
    start = end - pd.Timedelta(hours=20)
    for it in items:
        t = (it.get("title") or "").strip()
        key = t[:24]
        if not t or key in seen:
            continue
        pub = pd.to_datetime(it.get("published"), errors="coerce")
        if pd.notna(pub) and not (start <= pub <= end):
            continue
        if pd.isna(pub):
            continue          # 無時間戳的新聞無法證明是盤前發布,一律不用
        seen.add(key)
        out.append({"stamp": pub.strftime("%m/%d %H:%M") if pd.notna(pub) else "--",
                    "source": it.get("source", ""),
                    "title": t,
                    "url": (it.get("url") or "").strip()})
        if len(out) >= max_items:
            break
    return out


def news_links_section(news: list[dict], limit: int = 30) -> str:
    """連結清單由程式直出(轉址網址太長,交給模型抄寫容易斷鏈)。"""
    if not news:
        return ""
    lines = [f"- {n['stamp']}｜{n['source']}｜" +
             (f"[{n['title']}]({n['url']})" if n["url"] else n["title"])
             for n in news[:limit]]
    return "\n\n## 📎 新聞原文連結\n" + "\n".join(lines)


# ────────────────────────────────────────
# ③ 昨日族群/產業動能
# ────────────────────────────────────────
def yesterday_sectors() -> str:
    try:
        from sector_view import load_stock_info, compute_sector_heatmap
        hm = compute_sector_heatmap(load_stock_info())
        if hm.empty:
            return "（無產業資料）"
        top = hm.head(5)
        bot = hm.tail(5)
        fmt = lambda df: "\n".join(
            f"  {r['sector']}: {r['avg_chg']:+.2f}%（上漲{r['up']}/共{r['total']}檔;強勢股 {r['top_gainers']}）"
            for _, r in df.iterrows())
        return f"最強5產業:\n{fmt(top)}\n最弱5產業:\n{fmt(bot)}"
    except Exception as e:
        return f"（產業動能計算失敗:{type(e).__name__}）"


def data_asof() -> str:
    """個股資料最後日期(誠實標註「昨日動能」是哪一天)。"""
    try:
        p = Path(__file__).parent / "data" / "2330.TW.csv"
        d = pd.read_csv(p, index_col=0, usecols=[0, 4]).index[-1]
        return str(d)[:10]
    except Exception:
        return "未知"


# ────────────────────────────────────────
# ④ 行事曆
# ────────────────────────────────────────
def calendar_notes() -> list[str]:
    notes = []
    today = now_tw().date()
    try:
        from analyst_report import next_futures_settlement
        s, dd = next_futures_settlement()
        if dd == 0:
            notes.append(f"⚠️ 今天是台指期結算日({s:%m/%d})——尾盤波動放大,慎防結算行情")
        elif dd <= 3:
            notes.append(f"台指期結算日倒數 {dd} 天({s:%m/%d})——結算週留意多空拉鋸")
        else:
            notes.append(f"下次台指期結算:{s:%m/%d}(還有 {dd} 天)")
    except Exception:
        pass
    if today.day <= 10:
        notes.append(f"月營收公布旬(每月10日前)——{today.month}月上旬陸續公布上月營收,留意優於預期個股")
    try:
        from us_events import upcoming_macro, upcoming_earnings, expo_events
        notes += upcoming_macro(today, days=8)
        notes += upcoming_earnings(today, days=10)
        notes += expo_events(today, days=14)
    except Exception:
        pass
    return notes


# ────────────────────────────────────────
# 晨報生成
# ────────────────────────────────────────
_SYS_MORNING = """你是台股盤前晨報主筆,讀者是早上開盤前 10 分鐘看報的投資人。
【輸出鐵律】回覆「就是」晨報本文,從標題第一個字開始,無前言無總結無「已完成」。
【誠實鐵律】數字只能照抄數據包,嚴禁捏造;新聞只能引用給你的標題,不可腦補內文細節;
沒有的資料寫「無資料」。
格式(markdown,標題固定):
# 台股晨報 {date}
## ① 隔夜國際盤面
盤面表格照抄,後接 2-3 句解讀:費半/那指表現對台股電子與半導體的傳導、
台積電 ADR 對現貨開盤的暗示、油價匯率要點。
## ② 今晨大事評論
從新聞標題挑 6-10 則最重要的,分【國際】【國內】兩組;每則一行:
「**標題重點** — 一句評論(影響哪個族群/個股,偏多或偏空)」。
大盤行情類標題(台股漲X點)不要挑,挑有資訊量的事件。
## ③ 今日主流預判
2-4 個族群,每個:族群名+理由(隔夜盤面/昨日動能/新聞催化,至少引用其一)+
觀察點(開盤看哪些指標股確認)。開頭必須明寫:「以下為盤前假設,開盤後需驗證」。
## ④ 今日行事曆
行事曆條列照抄。
結尾一句:「本晨報由系統自動彙整,非投資建議。」
全文 700-1100 字。"""


def build_brief() -> str:
    now = now_tw()
    date_s = f"{now:%Y-%m-%d}"
    late_run = (now.hour, now.minute) >= (8, 45)      # 開盤後才補跑
    asof = data_asof()
    mkt = overnight_markets()
    news = overnight_news()
    sect = yesterday_sectors()
    cal = calendar_notes()
    if late_run and asof == date_s:
        # 當天收盤價已入庫——「前一交易日動能」會變成今日收盤,直接洩漏答案,不給模型
        sect = "（盤後補跑且當日資料已入庫,為避免事後之明,本段不提供）"
    digest = "\n".join([
        f"日期:{date_s}(台灣時間早晨)",
        "【隔夜國際盤面】",
        mkt.to_string(index=False) if not mkt.empty else "（yfinance 全數抓取失敗——盤面段寫「無資料」）",
        f"【前一交易日({asof})台股產業動能】",
        sect,
        "【隔夜新聞標題(近20小時)】",
        "\n".join(f"[{n['stamp']}|{n['source']}] {n['title']}" for n in news)
        if news else "（新聞抓取失敗）",
        "【行事曆】",
        "\n".join(f"- {n}" for n in cal) if cal else "- 無特別事項",
    ])
    import llm
    banner = ""
    if late_run:
        banner = (f"> ⚠️ **本篇為盤後補產生（{now:%H:%M}）**——新聞窗已截至當日 08:30 模擬盤前資訊,"
                  f"但仍非正式盤前產出;「今日主流預判」僅供格式參考,不具盤前效力。\n\n")
    out = llm.generate(_SYS_MORNING.replace("{date}", date_s), digest, max_tokens=2200)
    if out:
        return banner + out + news_links_section(news)
    # 離線退化:純數據版
    body = [f"# 台股晨報 {date_s}（數據版,無 Claude 引擎:{llm.fail_reason()}）",
            "## ① 隔夜國際盤面",
            "```", mkt.to_string(index=False) if not mkt.empty else "無資料", "```",
            f"## ② 昨日({data_asof()})產業動能", "```", sect, "```",
            "## ③ 隔夜新聞標題"] + [f"- {n['title']}" for n in news[:20]] + \
           ["## ④ 行事曆"] + [f"- {n}" for n in cal] + \
           ["", "本晨報由系統自動彙整,非投資建議。"]
    return banner + "\n".join(body) + news_links_section(news)


def already_done_today() -> bool:
    """數據版(引擎故障退化件)不佔當日名額——之後的重試槍要能換成正式版。"""
    from analyst_report import ART_DIR
    tag = now_tw().strftime("%Y%m%d")
    for p in ART_DIR.glob(f"art_{tag}_*_MKT.md"):
        try:
            if "數據版" not in p.read_text(encoding="utf-8")[:300]:
                return True
        except Exception:
            return True
    return False


def run(force: bool = False) -> str:
    if not force and already_done_today():
        print(f"[morning_brief] 今日晨報已存在,跳過({now_tw():%H:%M})")
        return ""
    print(f"[morning_brief] 開始產生 {now_tw():%Y-%m-%d %H:%M}")
    content = build_brief()
    from analyst_report import save_article, git_publish
    fname = save_article("MKT", "台股", "晨報", content)
    msg = git_publish(fname)
    if "數據版" not in content[:120]:
        _log_mentions(content)      # 退化件=生新聞標題堆,會把33檔雜訊灌進前瞻追蹤,不記
        try:                        # LINE 群組推播(best-effort;config.json 有金鑰才會動)
            import line_push
            if line_push.enabled():
                print(f"[morning_brief] {line_push.push_markdown(content)}")
        except Exception:
            pass
    else:
        print("[morning_brief] 數據版不記提及(避免污染前瞻追蹤)")
    print(f"[morning_brief] 完成:{fname}|{msg}")
    return fname


def _log_mentions(content: str) -> None:
    """記錄晨報點名的個股 → data/brief_mentions.csv(前瞻追蹤當沖/隔日表現用)。"""
    try:
        import re
        sl = pd.read_csv(Path(__file__).parent / "data" / "stock_list.csv",
                         encoding="utf-8-sig", dtype=str)
        # 媒體品牌與同名股票撞名(東森新聞≠東森國際、工商時報≠時報文化)→ 這些股名不匹配
        _MEDIA = {"東森", "時報", "中視", "三立", "聯合", "中央", "自由", "風傳媒", "力士"}
        names = {str(r["name"]).strip(): str(r["code"]).strip()
                 for _, r in sl.iterrows()
                 if len(str(r["name"]).strip()) >= 2
                 and str(r["name"]).strip() not in _MEDIA}
        pat = re.compile("|".join(re.escape(n) for n in
                                  sorted(names, key=len, reverse=True)))
        hits = sorted({names[n] + "|" + n for n in set(pat.findall(content))})
        if not hits:
            return
        p = Path(__file__).parent / "data" / "brief_mentions.csv"
        rows = [f"{now_tw():%Y-%m-%d},{h.split('|')[0]},{h.split('|')[1]}" for h in hits]
        header = "" if p.exists() else "date,code,name\n"
        with open(p, "a", encoding="utf-8-sig") as f:
            f.write(header + "\n".join(rows) + "\n")
        print(f"[morning_brief] 記錄提及個股 {len(rows)} 檔 → brief_mentions.csv")
    except Exception as e:
        print(f"[morning_brief] 提及記錄失敗(不影響晨報):{type(e).__name__}")


if __name__ == "__main__":
    run(force="--force" in sys.argv)

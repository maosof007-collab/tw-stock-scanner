"""
money_flow_daily.py — 當日族群資金流向日誌(盤後自動文章)
=================================================================
每日盤後(法人資料 ~16:00 公布後):
① 彙整各族群「當日」外資+投信買賣超金額、漲跌、5日累計
② 搭配當日新聞標題 → Claude 寫一篇 CMoney 筆記風格的盤後資金流向文章
   (吸睛標題/每節小標=一句話結論/數字照抄/新聞歸因/結尾兩個驗證訊號)
③ 存文章庫(mode=資金流向)+ git push 上雲 → 「資金流向日誌」頁顯示
執行:python money_flow_daily.py [--force]
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd
from twtime import now_tw

ROOT = Path(__file__).parent
D = ROOT / "data"


def build_daily_flow() -> tuple[pd.DataFrame, str]:
    """各族群當日資金流向表 + 資料日。欄:族群/當日買超(億)/當日均漲%/5日累計(億)/強勢股"""
    from theme_groups import THEME_GROUPS
    sl = pd.read_csv(D / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))
    rows, asof = [], ""
    for theme, codes in THEME_GROUPS.items():
        day_val = 0.0
        five_val = 0.0
        chgs, movers = [], []
        for c in codes:
            p = D / "institutional" / f"{c}_inst.csv"
            if not p.exists():
                continue
            try:
                m = pd.read_csv(p, usecols=lambda x: x in
                                ("date", "外陸資買賣超股數(不含外資自營商)",
                                 "外資買賣超股數", "it_net"))
                m["date"] = pd.to_datetime(m["date"], errors="coerce")
                a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
                b = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
                it = pd.to_numeric(m.get("it_net"), errors="coerce").fillna(0)
                m["net"] = a.fillna(b).fillna(0) + it
                m = m.dropna(subset=["date"]).sort_values("date")
                px = None
                for suf in (".TW.csv", ".TWO.csv"):
                    q = D / f"{c}{suf}"
                    if q.exists():
                        px = pd.read_csv(q, index_col=0, parse_dates=True,
                                         usecols=[0, 4]).iloc[:, 0].dropna()
                        break
                if px is None or m.empty:
                    continue
                last = m.iloc[-1]
                d0 = last["date"]
                asof = max(asof, f"{d0:%Y-%m-%d}")
                close = float(px.asof(d0))
                v = float(last["net"]) * close / 1e8
                day_val += v
                for _, r5 in m.tail(5).iterrows():
                    five_val += float(r5["net"]) * close / 1e8
                if len(px) >= 2 and px.index[-1] == d0:
                    chg = (px.iloc[-1] / px.iloc[-2] - 1) * 100
                    chgs.append(chg)
                    movers.append((abs(v), f"{nm.get(c, c)}({chg:+.1f}%,法人{v:+.1f}億)"))
            except Exception:
                continue
        if not chgs:
            continue
        movers.sort(reverse=True)
        rows.append({"族群": theme, "當日買超(億)": round(day_val, 1),
                     "當日均漲%": round(sum(chgs) / len(chgs), 2),
                     "5日累計(億)": round(five_val, 1),
                     "焦點股": "、".join(x[1] for x in movers[:2])})
    df = pd.DataFrame(rows).sort_values("當日買超(億)", ascending=False)
    return df, asof


def _today_news(max_items: int = 30) -> list[str]:
    import glob
    out, seen = [], set()
    today = f"{now_tw():%Y-%m-%d}"
    for f in sorted(glob.glob(str(D / "news" / "news_*.csv")), reverse=True)[:2]:
        try:
            n = pd.read_csv(f, encoding="utf-8-sig", usecols=["title", "published"])
        except Exception:
            continue
        n["published"] = pd.to_datetime(n["published"], errors="coerce")
        n = n[n["published"] >= today]
        for _, r in n.sort_values("published", ascending=False).iterrows():
            t = str(r["title"]).strip()
            if t[:24] in seen:
                continue
            seen.add(t[:24])
            out.append(t)
            if len(out) >= max_items:
                return out
    return out


_SYS_FLOW = """你是台股盤後籌碼專欄作者,文風仿 CMoney 筆記(範本特徵你必須遵守):
【輸出鐵律】回覆「就是」文章本文,從標題開始,無前言無總結。
【文風鐵律】
1. 標題:帶具體數字+懸念問句(例:「外資單日砸XX億搬進YY,是換防還是逃命?」)
2. 每節小標=一句話結論(粗體),不是分類名——讀者只看小標就能知道你的判斷
3. 每節 2-4 句,數字內嵌在敘事裡,因果推演;嚴禁條列堆數字
4. 新聞歸因:資金流向要對照給你的新聞標題找「為什麼」;新聞沒講的就寫「缺乏明確催化,
   留意是否為隔日沖熱錢」——不可腦補原因
5. 倒數第二節:「兩個訊號,決定XX是真輪動還是一日行情」——給兩個可驗證的觀察點(含門檻)
6. 最後一段:一句話並列「現在進場的人在賭什麼 vs 等待的人在等什麼」
【誠實鐵律】數字只能照抄數據包;口徑=外資+投信(不含自營商);金額為估算(股數×收盤)。
全文 500-800 字,結尾一句免責。"""


def generate_article() -> str:
    flow, asof = build_daily_flow()
    if flow.empty:
        return "（無法人資料）"
    news = _today_news()
    bm_txt = ""
    try:
        bm = pd.read_csv(D / "benchmark_TWII.csv", index_col=0, parse_dates=True).iloc[:, 0]
        bm_txt = f"大盤 {bm.iloc[-1]:,.0f}({(bm.iloc[-1]/bm.iloc[-2]-1)*100:+.2f}%)"
    except Exception:
        pass
    digest = "\n".join([
        f"資料日:{asof} {bm_txt}",
        "【族群資金流向(外資+投信,金額=股數×收盤估算)】",
        flow.to_string(index=False),
        "【今日新聞標題】",
        "\n".join(f"- {t}" for t in news) if news else "（今日無新聞檔）",
    ])
    import llm
    out = llm.generate(_SYS_FLOW, digest, max_tokens=1800)
    if out:
        return out + f"\n\n---\n*口徑:外資+投信買賣超(不含自營商),金額為估算;產生於 {now_tw():%Y-%m-%d %H:%M}。非投資建議。*"
    return f"（文章生成失敗:{llm.fail_reason()}）"


def already_done_today() -> bool:
    from analyst_report import ART_DIR
    tag = now_tw().strftime("%Y%m%d")
    return any(ART_DIR.glob(f"art_{tag}_*_FLOW.md"))


def data_is_today() -> bool:
    """今日法人資料到位才寫(16:00 後);否則寫的是昨天的流向。"""
    p = D / "institutional" / "2330_inst.csv"
    try:
        m = pd.read_csv(p, usecols=["date"])
        return str(m["date"].iloc[-1])[:10] == f"{now_tw():%Y-%m-%d}"
    except Exception:
        return False


def run(force: bool = False) -> str:
    if not force and already_done_today():
        print("[money_flow] 今日已產生,跳過")
        return ""
    if not force and not data_is_today():
        print("[money_flow] 今日法人資料未到(約16:00後),跳過")
        return ""
    import llm
    if llm.engine_status()["engine"] == "none":
        print("[money_flow] 無 Claude 引擎,跳過")
        return ""
    print(f"[money_flow] 產生資金流向日誌 {now_tw():%H:%M}")
    content = generate_article()
    if content.startswith("（"):
        print(content)
        return ""
    from analyst_report import save_article, git_publish
    fn = save_article("FLOW", "資金流向", "資金流向", content)
    print(f"[money_flow] {fn}|{git_publish(fn)}")
    return fn


if __name__ == "__main__":
    run(force="--force" in sys.argv)

"""
index_map.py — 每日大盤結構解析(仿 T3 母樹圖方法論的可自動化骨架)
=================================================================
方法論(取自使用者分享的 T3 60M MOTHER MAP,可程式化的部分):
  ① 擺動點偵測(zigzag)→ 大盤波段地圖(起點/外1~外5 式的高低點序列)
  ② 兩把 Fib 尺:「最近一把推升」(局部尺)與「往前重抓的大段」(母級尺)
     ——先用局部尺測承接,停不住才換大尺(不是替回調找更深目標)
  ③ 裁決條件樹:站上/跌破哪些位階 → 目前劇本與失效線(只給條件,不做預測)
  ④ Claude 寫敘事,數字照抄;無引擎時輸出純數據版
產出 → 文章庫(mode=大盤解析)→ 總經頁顯示;每日 15:10 後排程自動產。
執行:python index_map.py [--force]
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


def load_index() -> pd.Series:
    bm = pd.read_csv(ROOT / "data" / "benchmark_TWII.csv", index_col=0, parse_dates=True)
    idx = pd.to_datetime(bm.index)
    bm.index = idx.tz_convert(None) if idx.tz is not None else idx
    return pd.to_numeric(bm.iloc[:, 0], errors="coerce").dropna()


def zigzag(s: pd.Series, pct: float = 0.03) -> list[tuple]:
    """擺動點:反向波動 ≥ pct 才確認轉折。回傳 [(date, price, 'H'/'L')]。"""
    piv = []
    direction = 0                      # 1=尋高 -1=尋低
    ext_i = s.index[0]
    ext_v = float(s.iloc[0])
    for d, v in s.items():
        v = float(v)
        if direction >= 0:
            if v > ext_v:
                ext_v, ext_i = v, d
            elif v <= ext_v * (1 - pct):
                piv.append((ext_i, ext_v, "H"))
                direction, ext_v, ext_i = -1, v, d
        if direction <= 0:
            if v < ext_v:
                ext_v, ext_i = v, d
            elif v >= ext_v * (1 + pct) and direction == -1:
                piv.append((ext_i, ext_v, "L"))
                direction, ext_v, ext_i = 1, v, d
        if direction == 0:
            direction = 1
    piv.append((ext_i, ext_v, "H" if direction == 1 else "L"))   # 進行中的極值
    return piv


def fib_levels(lo: float, hi: float) -> dict:
    rng = hi - lo
    return {"23.6%": round(hi - rng * 0.236), "38.2%": round(hi - rng * 0.382),
            "50%": round(hi - rng * 0.5), "61.8%": round(hi - rng * 0.618),
            "76.4%": round(hi - rng * 0.764), "100%": round(lo)}


def build_map() -> dict:
    s = load_index()
    close = float(s.iloc[-1])
    chg = (close / float(s.iloc[-2]) - 1) * 100
    piv = zigzag(s.tail(500), 0.03)

    # 最近一把推升:最後一組 L→H(H 在 L 之後)
    highs = [p for p in piv if p[2] == "H"]
    lows = [p for p in piv if p[2] == "L"]
    last_h = highs[-1]
    lows_before = [p for p in lows if p[0] < last_h[0]]
    local_l = lows_before[-1] if lows_before else lows[0] if lows else piv[0]
    # 母級尺:更早的重要低點(近500日最低)
    grand_lo_v = float(s.tail(500).min())
    grand_lo_d = s.tail(500).idxmin()

    fib_local = fib_levels(local_l[1], last_h[1])
    fib_grand = fib_levels(grand_lo_v, last_h[1])
    ma5 = float(s.rolling(5).mean().iloc[-1])
    ma20 = float(s.rolling(20).mean().iloc[-1])
    ma60 = float(s.rolling(60).mean().iloc[-1])

    swing_txt = " → ".join(f"{p[1]:,.0f}({p[0]:%m/%d}{'高' if p[2]=='H' else '低'})"
                           for p in piv[-7:])
    return {"date": f"{s.index[-1]:%Y-%m-%d}", "close": close, "chg": chg,
            "swing": swing_txt,
            "local": {"lo": round(local_l[1]), "lo_d": f"{local_l[0]:%m/%d}",
                      "hi": round(last_h[1]), "hi_d": f"{last_h[0]:%m/%d}",
                      "fib": fib_local},
            "grand": {"lo": round(grand_lo_v), "lo_d": f"{grand_lo_d:%m/%d}",
                      "hi": round(last_h[1]), "fib": fib_grand},
            "ma": {"5MA": round(ma5), "20MA": round(ma20), "60MA": round(ma60)}}


_SYS_MAP = """你是大盤結構分析師,方法論=「兩把尺+裁決樹」(T3 母樹圖式):
【輸出鐵律】回覆即解析本文,從標題開始;數字只能照抄數據包,嚴禁自創價位。
【方法鐵律】
1. 不做預測,只給「條件樹」:站上X=劇本A升權/跌破Y=劇本B升權,每個劇本都要有失效線
2. 先用「最近一把推升」的 Fib 測承接;明寫「若50%附近停不住+下壓斜率擴張,
   才往前換大尺」——換尺是重新判斷市場在修正哪一段漲幅,不是找更深目標
3. 分清事實與候選:已發生的價位=事實;浪型身分=候選,要寫「候選」不可寫死
格式(markdown):
# 大盤解析 {date}|收盤與定位一句話
## ① 價格事實
收盤/漲跌/波段地圖(照抄)/均線位置,3-4句。
## ② 第一把尺:最近推升的承接測試
局部 Fib 表照抄;現價落在哪兩檔之間;50%與61.8%的裁決意義。
## ③ 第二把尺:母級空間地圖(備而不用)
大段 Fib 表照抄;明寫啟用條件(局部尺停不住才換);強調這是地圖不是目標順序。
## ④ 裁決樹
「反彈/多方劇本」:站上哪些價位依序升權(用5MA/20MA/前高)。
「回調/空方劇本」:跌破哪些價位依序升權(用Fib檔位/60MA)。
各給失效線。
結尾:「本解析為結構條件樹,非預測;非投資建議。」全文500-800字。"""


def generate() -> str:
    m = build_map()
    digest = "\n".join([
        f"日期:{m['date']} 收盤 {m['close']:,.0f}({m['chg']:+.2f}%)",
        f"波段地圖(3%擺動):{m['swing']}",
        f"均線:5MA {m['ma']['5MA']:,} / 20MA {m['ma']['20MA']:,} / 60MA {m['ma']['60MA']:,}",
        f"【第一把尺】最近推升 {m['local']['lo']:,}({m['local']['lo_d']})→{m['local']['hi']:,}({m['local']['hi_d']})",
        "  " + "  ".join(f"{k}={v:,}" for k, v in m["local"]["fib"].items()),
        f"【第二把尺】母級 {m['grand']['lo']:,}({m['grand']['lo_d']})→{m['grand']['hi']:,}",
        "  " + "  ".join(f"{k}={v:,}" for k, v in m["grand"]["fib"].items()),
    ])
    import llm
    out = llm.generate(_SYS_MAP.replace("{date}", m["date"]), digest, max_tokens=1800)
    if out:
        return out + f"\n\n---\n*擺動點=3%zigzag自動偵測;產生於 {now_tw():%Y-%m-%d %H:%M}。結構條件樹非預測,非投資建議。*"
    # 離線數據版
    return ("# 大盤解析 " + m["date"] + "(數據版)\n```\n" + digest +
            "\n```\n本解析為結構條件樹,非預測;非投資建議。")


def already_done_today() -> bool:
    from analyst_report import ART_DIR
    tag = now_tw().strftime("%Y%m%d")
    return any(ART_DIR.glob(f"art_{tag}_*_IDX.md"))


def run(force: bool = False) -> str:
    if not force and already_done_today():
        print("[index_map] 今日已產生,跳過")
        return ""
    m_date = build_map()["date"]
    if not force and m_date != f"{now_tw():%Y-%m-%d}":
        print(f"[index_map] 大盤資料還停在 {m_date},今日未更新,跳過")
        return ""
    print(f"[index_map] 產生大盤解析 {now_tw():%H:%M}")
    content = generate()
    from analyst_report import save_article, git_publish
    fn = save_article("IDX", "大盤", "大盤解析", content)
    print(f"[index_map] {fn}|{git_publish(fn)}")
    return fn


if __name__ == "__main__":
    run(force="--force" in sys.argv)

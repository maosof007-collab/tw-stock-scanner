"""
analyst_report.py — 個股法人報告產生器(六層框架+正反方對照+月營收推估)
=================================================================
方法論來自金居/晶技/環宇-KY 的分析實戰:
  ①驅動力(量價齊揚) ②供需量化 ③營收模型 ④毛利分層
  ⑤EPS→本益比→目標價(三情境) ⑥反方風險必列 + 正反方對照表

系統負責「可驗證的數學」:
  · 出貨/營收動能:月營收 YoY/MoM、季度毛利/營益/EPS 趨勢、籌碼
  · 月營收推估:去年同月 ×(1+情境YoY),YoY 由近月動能自動導出
    (保守=近6月最低、中性=近3月中位、樂觀=近3月最高),使用者可改
  · EPS 情境:推估季營收 × 情境淨利率(近2季均值±調整)÷ 股數
Claude 負責「敘事與判斷」:把數據包+使用者補充資料(法說/產能/佔比)
寫成法人報告;數字嚴禁改動,推測必須標明。
"""
from __future__ import annotations

import pandas as pd

from twtime import now_tw
from fundamentals import (monthly_revenue, quarterly_fin, shares_map,
                          _chip_context)


# ────────────────────────────────────────
# 月營收推估(三情境,純數學)
# ────────────────────────────────────────
def forecast_monthly(code: str, months: int = 6,
                     override: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """回傳 (預估表, 假設dict)。預估月營收 = 去年同月 × (1 + 情境YoY)。
    override: {'保守YoY%':x,'中性YoY%':y,'樂觀YoY%':z} 使用者自訂假設。"""
    mon = monthly_revenue(code, years=4)
    if mon.empty or len(mon) < 15:
        return pd.DataFrame(), {}
    yoy3 = mon["yoy%"].tail(3)
    yoy6 = mon["yoy%"].tail(6)
    assume = override or {
        "保守YoY%": round(float(yoy6.min()), 1),
        "中性YoY%": round(float(yoy3.median()), 1),
        "樂觀YoY%": round(float(yoy3.max()), 1),
    }
    rev_map = dict(zip(mon["ym"], mon["revenue"]))
    last_ym = mon["ym"].iloc[-1]
    y, m = int(last_ym[:4]), int(last_ym[5:7])
    rows = []
    for _ in range(months):
        m += 1
        if m > 12:
            m = 1; y += 1
        ym = f"{y}-{m:02d}"
        base = rev_map.get(f"{y-1}-{m:02d}")
        if base is None:
            continue
        rows.append({
            "月份": ym, "去年同月": round(base, 1),
            "保守": round(base * (1 + assume["保守YoY%"] / 100), 1),
            "中性": round(base * (1 + assume["中性YoY%"] / 100), 1),
            "樂觀": round(base * (1 + assume["樂觀YoY%"] / 100), 1),
        })
    return pd.DataFrame(rows), assume


def eps_scenarios(code: str, fc: pd.DataFrame) -> pd.DataFrame:
    """用推估營收×情境淨利率÷股數 → 未來兩季 EPS 概估(附年化)。"""
    q = quarterly_fin(code, years=2)
    sh = shares_map().get(code, 0)
    if fc.empty or q.empty or sh <= 0 or "淨利率%" not in q.columns:
        return pd.DataFrame()
    nm = float(q["淨利率%"].tail(2).mean())
    rows = []
    for label, adj in [("保守", -3.0), ("中性", 0.0), ("樂觀", +3.0)]:
        rev_m = fc[label].mean()                       # 平均月營收(百萬)
        q_rev = rev_m * 3                              # 概估季營收
        eps_q = q_rev * 1e6 * max(nm + adj, 0) / 100 / sh
        rows.append({"情境": label, "假設淨利率%": round(nm + adj, 1),
                     "季EPS概估": round(eps_q, 2), "年化EPS": round(eps_q * 4, 2)})
    return pd.DataFrame(rows)


# ────────────────────────────────────────
# 模型回測(backcast):用「當時可得資訊」回推歷史預測,對照實際
# ────────────────────────────────────────
def backcast_monthly(code: str, lookback: int = 12) -> pd.DataFrame:
    """walk-forward:第 m 月的預測 = 去年同月 × (1 + 前3個月YoY中位數)。
    不偷看未來——完全用 m 月之前已公布的資料。回傳 月份/實際/模型/誤差%。"""
    mon = monthly_revenue(code, years=4).reset_index(drop=True)
    if len(mon) < 18:
        return pd.DataFrame()
    rows = []
    for i in range(max(15, len(mon) - lookback), len(mon)):
        base_idx = i - 12
        if base_idx < 0:
            continue
        yoy_hist = mon["yoy%"].iloc[max(0, i - 3):i].dropna()
        if len(yoy_hist) < 3 or pd.isna(mon["revenue"].iloc[base_idx]):
            continue
        pred = mon["revenue"].iloc[base_idx] * (1 + float(yoy_hist.median()) / 100)
        act = mon["revenue"].iloc[i]
        rows.append({"月份": mon["ym"].iloc[i], "實際": round(act, 1),
                     "模型": round(pred, 1), "誤差%": round((act / pred - 1) * 100, 1)})
    return pd.DataFrame(rows)


_SYS_ATTR = """你是研究員,任務是「模型誤差歸因」。給你:某股的模型回測誤差表
(walk-forward:預測=去年同月×前3月YoY中位)、季度財務、近月新聞標題、使用者補充。
輸出 markdown:
1. 整體評估:模型偏差是「結構性」(持續同向=動能模型抓不到轉折)還是「單月事件」
2. 挑出 |誤差|最大的 2-3 個月,各給:可能原因假說(依據數據,不可瞎編)+
   **驗證路徑**——具體到看哪裡:財報哪個科目(毛利率→產品組合/公開說明書產品別;
   存貨→備貨或遞延出貨;業外→一次性;月營收公告備註欄=公司自己解釋)、
   法說該問什麼、可查什麼新聞關鍵字
3. 模型改進建議一條(如:該股 YoY 動能窗口太短/該用季節性)
事實與推測分開;沒有新聞資料的月份就明說。300-500字,直接輸出本文。"""


def attribute_errors(code: str, bc: pd.DataFrame, extra: str = "") -> str:
    """Claude 誤差歸因:大誤差月份 × 季度財務 × 新聞標題。"""
    if bc.empty:
        return "（無回測資料）"
    q = quarterly_fin(code, years=2)
    # 撈系統新聞庫中提及該股的標題(2026-06 起才有累積,誠實標註)
    news_txt = ""
    try:
        from pathlib import Path
        name = ""
        sl = pd.read_csv(Path(__file__).parent / "data" / "stock_list.csv",
                         encoding="utf-8-sig", dtype=str)
        hit = sl[sl["code"] == code]
        name = hit["name"].iloc[0] if not hit.empty else ""
        hits = []
        for p in sorted((Path(__file__).parent / "data" / "news").glob("news_*.csv")):
            try:
                nd = pd.read_csv(p, encoding="utf-8-sig", usecols=["title", "published"])
                m = nd[nd["title"].astype(str).str.contains(name, na=False)] if name else nd.iloc[0:0]
                hits += [f"{str(r['published'])[:10]} {r['title'][:60]}" for _, r in m.iterrows()]
            except Exception:
                continue
        news_txt = "\n".join(hits[-15:]) if hits else "（系統新聞庫 2026-06 起累積,無此股標題）"
    except Exception:
        news_txt = "（新聞庫讀取失敗）"
    digest = (f"個股:{code} {name}\n【模型回測誤差表】\n{bc.to_string(index=False)}\n\n"
              f"【季度財務】\n{q.to_string(index=False)}\n\n【新聞標題】\n{news_txt}\n")
    if extra.strip():
        digest += f"\n【使用者補充(法說等)】\n{extra.strip()[:3000]}\n"
    from llm import generate
    out = generate(_SYS_ATTR, digest, max_tokens=1500)
    return out or "（無可用 Claude 引擎,僅顯示誤差表）"


# ────────────────────────────────────────
# 數據包
# ────────────────────────────────────────
def build_digest(code: str, extra: str = "") -> dict:
    name = ""
    try:
        sl = pd.read_csv(__import__("pathlib").Path(__file__).parent / "data" / "stock_list.csv",
                         encoding="utf-8-sig", dtype=str)
        hit = sl[sl["code"] == code]
        name = hit["name"].iloc[0] if not hit.empty else ""
    except Exception:
        pass
    mon = monthly_revenue(code, years=3)
    q = quarterly_fin(code, years=4)
    fc, assume = forecast_monthly(code)
    eps_sc = eps_scenarios(code, fc)
    price_txt = ""
    try:
        from pathlib import Path
        for suf in (".TW", ".TWO"):
            p = Path(__file__).parent / "data" / f"{code}{suf}.csv"
            if p.exists():
                d = pd.read_csv(p, usecols=[0, 4]); d.columns = ["date", "close"]
                cl = pd.to_numeric(d["close"], errors="coerce").dropna()
                hi = cl.tail(120).max()
                sh = shares_map().get(code, 0)
                price_txt = (f"現價 {cl.iloc[-1]:.1f}({d['date'].iloc[-1]}），"
                             f"距120日高 {(cl.iloc[-1]/hi-1)*100:+.1f}%")
                if sh > 0:
                    price_txt += f"，市值約 {cl.iloc[-1]*sh/1e8:,.0f} 億"
                break
    except Exception:
        pass
    return {"code": code, "name": name, "monthly": mon, "quarterly": q,
            "forecast": fc, "assume": assume, "eps_sc": eps_sc,
            "chips": _chip_context(code), "price": price_txt, "extra": extra}


# ────────────────────────────────────────
# 法人報告生成(Claude)
# ────────────────────────────────────────
_SYS = """你是一位嚴謹的台股賣方分析師。
【輸出格式鐵律】你的回覆「就是」報告檔案本文——從報告標題第一個字開始輸出,
到免責聲明結束;嚴禁任何前言、說明、完成總結、「報告已生成」之類的話。
輸出一份 markdown 法人報告。骨架固定六層:
一、驅動力(核心題材)——判定量價齊揚成立與否
二、供需量化與市佔——能 bottom-up 就推,不能就誠實改用代理變數,假設全標明
三、營收模型與出貨動能——引用月營收數據與系統推估表(表格數字嚴禁改動,原樣引用)
四、毛利率分層——用季度毛利/營益趨勢講產品組合變化
五、EPS→本益比→目標價——用系統EPS情境表,本益比自訂並說明理由(保守/中性/樂觀)
六、反方風險(必列)
另外兩個硬性要求:
· 報告開頭放「投資摘要」+一張**正反方對照表**(|多方論點|空方論點|,各至少4條,
  每條要有數據或事實支撐,不可空話)
· 誠實紀律:股價已反映多少要講;數據矛盾要點名;推測與事實分開;
  使用者補充資料引用時註明「使用者提供」;單位照數據包原樣,嚴禁移動小數點
結尾:3-4個「後續追蹤點」+免責聲明(個人研究非投資建議)。長度800-1200字。"""


def generate_report(code: str, extra: str = "") -> str:
    d = build_digest(code, extra)
    if d["monthly"].empty:
        return f"（抓不到 {code} 的財務資料）"
    parts = [f"個股：{d['code']} {d['name']}　{d['price']}",
             f"籌碼：{d['chips'] or '無'}",
             "【月營收(百萬) 近18月】", d["monthly"].tail(18).to_string(index=False),
             "【季度財務 近4年】", d["quarterly"].to_string(index=False)]
    if not d["forecast"].empty:
        parts += [f"【系統月營收推估(百萬) 假設:{d['assume']}】",
                  d["forecast"].to_string(index=False)]
    if not d["eps_sc"].empty:
        parts += ["【系統EPS情境】", d["eps_sc"].to_string(index=False)]
    if extra.strip():
        parts += ["【使用者補充資料(法說/產能/產品佔比等)】", extra.strip()[:5000]]
    from llm import generate
    out = generate(_SYS, "\n".join(parts), max_tokens=3000)
    if out:
        return out + f"\n\n---\n*系統數據:FinMind/TWSE;產生於 {now_tw():%Y-%m-%d %H:%M}。情境試算非投資建議。*"
    return "（無可用 Claude 引擎——請確認 API key 或本機 claude 登入後重試;下方數據表仍可用）"

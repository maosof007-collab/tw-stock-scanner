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
# H1 實績 + H2 推估 → 全年估值(半年報視角)
# ────────────────────────────────────────
# ────────────────────────────────────────
# 重大訊息(MOPS)與融資融券日表
# ────────────────────────────────────────
_IMPORTANT_KW = ["轉換公司債", "現金增資", "減資", "私募", "合併", "收購", "處分",
                 "財務報告", "財測", "股利", "注意交易", "處置", "違約", "裁罰",
                 "更正", "暫停", "解除", "質押", "備案"]


def fetch_announcements(code: str) -> pd.DataFrame:
    """MOPS 重大訊息(今年+去年)。欄:日期/時間/主旨/重要。快取20h。"""
    import json, time, requests
    from pathlib import Path
    cache = Path(__file__).parent / "data" / "fundamentals" / f"{code}_ann.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 20 * 3600:
        try:
            return pd.DataFrame(json.loads(cache.read_text(encoding="utf-8")))
        except Exception:
            pass
    from twtime import now_tw
    roc = now_tw().year - 1911
    rows = []
    for y in (roc, roc - 1):
        try:
            r = requests.post("https://mops.twse.com.tw/mops/api/t05st01",
                              json={"companyId": code, "year": str(y), "month": "all",
                                    "firstDay": "", "lastDay": ""},
                              headers={"User-Agent": "Mozilla/5.0",
                                       "Content-Type": "application/json",
                                       "Referer": "https://mops.twse.com.tw/mops/#/web/t05st01"},
                              timeout=20)
            j = r.json()
            for row in ((j.get("result") or {}).get("data") or []):
                subj = str(row[4]).replace("\r\n", "").replace("\n", "")
                rows.append({"日期": row[2], "時間": row[3], "主旨": subj,
                             "重要": "🔴" if any(k in subj for k in _IMPORTANT_KW) else ""})
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["日期", "時間"], ascending=False).reset_index(drop=True)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(df.to_dict("records"), ensure_ascii=False),
                             encoding="utf-8")
        except Exception:
            pass
    return df


def margin_short_table(code: str, days: int = 20) -> pd.DataFrame:
    """每日融資融券表:融資餘額/增減/維持率(推估)/融券餘額/增減/券資比。"""
    from pathlib import Path
    D = Path(__file__).parent / "data"
    p = D / "margin" / f"{code}_margin.csv"
    if not p.exists():
        return pd.DataFrame()
    m = pd.read_csv(p, usecols=["date", "margin_balance", "short_balance"])
    m["date"] = pd.to_datetime(m["date"], errors="coerce")
    m = m.dropna(subset=["date"]).tail(days + 1)
    px = None
    for suf in (".TW", ".TWO"):
        pp = D / f"{code}{suf}.csv"
        if pp.exists():
            px = pd.read_csv(pp, usecols=[0, 4]); px.columns = ["date", "close"]
            px["date"] = pd.to_datetime(px["date"], errors="coerce")
            px["close"] = pd.to_numeric(px["close"], errors="coerce")
            px["ma60"] = px["close"].rolling(60).mean()
            break
    if px is not None:
        m = m.merge(px[["date", "close", "ma60"]], on="date", how="left")
        # 維持率推估:收盤/(融資成數0.6×成本MA60)×100(與總經頁同款推估口徑)
        m["維持率(推估)%"] = (m["close"] / (0.6 * m["ma60"]) * 100).round(1)
    m["融資增減"] = m["margin_balance"].diff()
    m["融券增減"] = m["short_balance"].diff()
    m["券資比%"] = (m["short_balance"] / m["margin_balance"].replace(0, pd.NA) * 100).round(1)
    out = m.tail(days).copy()
    out["日期"] = out["date"].dt.strftime("%Y-%m-%d")
    if "close" in out.columns:
        out["收盤"] = out["close"].round(1)
    cols = ["日期", "收盤", "margin_balance", "融資增減", "維持率(推估)%",
            "short_balance", "融券增減", "券資比%"]
    out = out[[c for c in cols if c in out.columns]].rename(
        columns={"margin_balance": "融資餘額(張)", "short_balance": "融券餘額(張)"})
    return out.iloc[::-1].reset_index(drop=True)     # 最新在上


def next_futures_settlement():
    """下一個台指期結算日(每月第三個週三)。回傳 (date, 距今日曆天)。"""
    from twtime import now_tw
    import datetime as _dt
    t = now_tw().date()

    def third_wed(y, m):
        d = _dt.date(y, m, 1)
        wed = 2 - d.weekday()
        if wed < 0:
            wed += 7
        return d + _dt.timedelta(days=wed + 14)
    s = third_wed(t.year, t.month)
    if s < t:
        ny, nm = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
        s = third_wed(ny, nm)
    return s, (s - t).days


def margin_conclusion(tbl: pd.DataFrame) -> list[str]:
    """每日融資融券白話結論(規則式),含台指期結算日對應。tbl=margin_short_table輸出(最新在上)。"""
    if tbl.empty or len(tbl) < 6:
        return ["融資融券資料不足,無法下結論。"]
    t = tbl.iloc[::-1].reset_index(drop=True)          # 轉回舊→新
    out = []
    mb = t["融資餘額(張)"].astype(float)
    sb = t["融券餘額(張)"].astype(float)
    d5m = mb.iloc[-1] - mb.iloc[-6]
    d5s = sb.iloc[-1] - sb.iloc[-6]
    pct5m = d5m / max(mb.iloc[-6], 1) * 100
    # ① 融資
    if pct5m > 5:
        out.append(f"🔺 **融資近5日大增 {d5m:+,.0f} 張({pct5m:+.1f}%)**——散戶槓桿追價升溫,"
                   "短線籌碼轉浮動(反指標警戒),漲勢中助漲、回檔時殺融資會放大跌幅。")
    elif pct5m < -5:
        out.append(f"🔻 **融資近5日大減 {d5m:+,.0f} 張({pct5m:+.1f}%)**——槓桿退場/清洗,"
                   "若價格同步止穩=籌碼沉澱偏正面;若價跌融資減=多殺多退潮。")
    else:
        out.append(f"➖ 融資近5日 {d5m:+,.0f} 張,槓桿變化平穩。")
    # ② 維持率
    if "維持率(推估)%" in t.columns and pd.notna(t["維持率(推估)%"].iloc[-1]):
        mr = float(t["維持率(推估)%"].iloc[-1])
        if mr < 130:
            out.append(f"⚠️ **維持率推估 {mr:.0f}%,逼近追繳線(130)**——融資戶瀕臨斷頭,"
                       "既是殺盤引信也是跌深反彈的彈簧,嚴設停損。")
        elif mr < 150:
            out.append(f"🟡 維持率推估 {mr:.0f}%(150 以下偏低)——融資戶普遍套牢,上方解套賣壓重。")
        else:
            out.append(f"🟢 維持率推估 {mr:.0f}%,融資結構健康。")
    # ③ 融券 + 券資比
    ratio = float(t["券資比%"].iloc[-1]) if "券資比%" in t.columns and pd.notna(t["券資比%"].iloc[-1]) else None
    if d5s > 0 and (ratio or 0) > 20:
        out.append(f"🩳 **融券近5日 +{d5s:,.0f} 張、券資比 {ratio:.0f}%(偏高)**——"
                   "空單大量堆積:股價若續強,軋空燃料充足;若轉弱,空方判斷正確。")
    elif d5s > 0:
        out.append(f"🩳 融券近5日 +{d5s:,.0f} 張(券資比 {ratio if ratio is not None else 0:.0f}%),空方試單/避險增加。")
    elif d5s < 0:
        px_up = ("收盤" in t.columns and pd.notna(t["收盤"].iloc[-1])
                 and float(t["收盤"].iloc[-1]) > float(t["收盤"].iloc[-6]))
        out.append(f"🧯 融券近5日回補 {d5s:,.0f} 張——"
                   + ("**且股價同步上漲=軋空進行中**,動能未竭前勿逆勢放空。" if px_up
                      else "空方退場,上方壓力減輕。"))
    # ④ 期貨結算對應
    sdate, dleft = next_futures_settlement()
    if dleft <= 2:
        out.append(f"⏰ **台指期結算日就在 {sdate:%m/%d}(剩 {dleft} 天)**——結算前融券強制回補與"
                   "期現套利平倉會放大波動;此時的融券增減參考性低(避險盤進出),隔天再看趨勢較準。")
    elif dleft <= 7:
        out.append(f"📅 本月台指期結算日 {sdate:%m/%d}(約 {dleft} 天後)——進入結算週,"
                   "若融券偏高且股價撐在高檔,結算前軋空機率上升;反之高融資+價弱易被壓低結算。")
    else:
        out.append(f"📅 下次台指期結算日 {sdate:%m/%d}(約 {dleft} 天後),目前非結算干擾期,籌碼變化可照常解讀。")
    return out


_SELF_RPT = __import__("pathlib").Path(__file__).parent / "data" / "fundamentals" / "self_report.json"


def get_self_h1(code: str, year: int) -> float | None:
    """公司自結 H1 EPS(使用者輸入過就記住)"""
    import json
    try:
        d = json.loads(_SELF_RPT.read_text(encoding="utf-8"))
        v = d.get(f"{code}_{year}H1")
        return float(v) if v is not None else None
    except Exception:
        return None


def set_self_h1(code: str, year: int, eps: float):
    import json
    d = {}
    try:
        d = json.loads(_SELF_RPT.read_text(encoding="utf-8"))
    except Exception:
        pass
    d[f"{code}_{year}H1"] = float(eps)
    _SELF_RPT.parent.mkdir(parents=True, exist_ok=True)
    _SELF_RPT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def h1_valuation(code: str) -> dict:
    """半年報估值:今年 H1 用實績(Q1/Q2 EPS;Q2未公布則用月營收×淨利率推估並標註),
    H2 用月營收推估×淨利率情境 → FY EPS 三情境 × 本益比階梯 → 目標價。"""
    from twtime import now_tw
    year = now_tw().year
    q = quarterly_fin(code, years=2)
    mon = monthly_revenue(code, years=3)
    fc, assume = forecast_monthly(code, months=8)
    sh = shares_map().get(code, 0)
    if q.empty or mon.empty or sh <= 0:
        return {}
    nm2 = float(q["淨利率%"].tail(2).mean()) if "淨利率%" in q.columns else 0.0

    def _q_eps(qdate):
        hit = q[q["季度"].astype(str).str.startswith(qdate)]
        return float(hit["EPS"].iloc[0]) if not hit.empty and pd.notna(hit["EPS"].iloc[0]) else None

    q1 = _q_eps(f"{year}-03-31")
    q2 = _q_eps(f"{year}-06-30")
    if q1 is None:
        return {}
    notes = []
    # 事前推估的 Q2(月營收×淨利率)——不論最後用哪個來源,都拿它「對答案」
    q2_rev = mon[mon["ym"].isin([f"{year}-04", f"{year}-05", f"{year}-06"])]["revenue"].sum()
    q2_est = (q2_rev * 1e6 * nm2 / 100 / sh) if (q2_rev > 0 and nm2) else None
    q2_src = ""
    if q2 is not None:                       # ① 財報實績
        q2_src = "財報實績"
    else:
        self_h1 = get_self_h1(code, year)    # ② 公司自結(輸入過會記住)
        if self_h1 is not None:
            q2 = self_h1 - q1
            q2_src = "公司自結(H1−Q1)"
            notes.append(f"Q2 取自公司自結 H1 {self_h1:.2f} − Q1 {q1:.2f} = {q2:.2f};8/14 財報公布後自動改用實績")
        elif q2_est is not None:             # ③ 推估
            q2 = q2_est
            q2_src = "推估"
            notes.append(f"Q2 財報未公布,以月營收加總 {q2_rev:,.0f}百萬 × 近2季淨利率 {nm2:.1f}% 推估 EPS {q2:.2f}")
    # 對答案:實際(財報/自結) vs 事前推估
    if q2 is not None and q2_est is not None and q2_src != "推估":
        gap = (q2 - q2_est)
        notes.append(f"📏 對答案:Q2 {q2_src} {q2:.2f} vs 事前推估 {q2_est:.2f}(差 {gap:+.2f}"
                     f",{'實際優於推估=獲利結構比近2季更好' if gap > 0 else '實際低於推估'})")
    h1 = q1 + (q2 or 0)

    # H2 = 已公布的 7-12 月實際 + 其餘月份推估
    h2_months = [f"{year}-{m:02d}" for m in range(7, 13)]
    act = mon[mon["ym"].isin(h2_months)]
    act_sum = float(act["revenue"].sum())
    act_n = len(act)
    fc_rest = fc[fc["月份"].isin(h2_months)] if not fc.empty else pd.DataFrame()
    rows = []
    for label, adj in [("保守", -3.0), ("中性", 0.0), ("樂觀", +3.0)]:
        fc_sum = float(fc_rest[label].sum()) if not fc_rest.empty else 0.0
        h2_rev = act_sum + fc_sum
        h2_eps = h2_rev * 1e6 * max(nm2 + adj, 0) / 100 / sh
        fy = h1 + h2_eps
        rows.append({"情境": label, "H2營收推估(百萬)": round(h2_rev, 0),
                     "假設淨利率%": round(nm2 + adj, 1),
                     "H2 EPS": round(h2_eps, 2), "FY EPS": round(fy, 2),
                     "×15": round(fy * 15, 0), "×20": round(fy * 20, 0),
                     "×25": round(fy * 25, 0), "×30": round(fy * 30, 0)})
    if act_n:
        notes.append(f"H2 已含 {act_n} 個月實際營收({act_sum:,.0f}百萬),其餘為推估")
    price = None
    try:
        for suf in (".TW", ".TWO"):
            p = (ROOT if False else __import__("pathlib").Path(__file__).parent) / "data" / f"{code}{suf}.csv"
            if p.exists():
                d = pd.read_csv(p, usecols=[0, 4]); d.columns = ["date", "close"]
                price = float(pd.to_numeric(d["close"], errors="coerce").dropna().iloc[-1])
                break
    except Exception:
        pass
    return {"year": year, "q1": round(q1, 2), "q2": (round(q2, 2) if q2 is not None else None),
            "q2_src": q2_src,
            "h1": round(h1, 2), "table": pd.DataFrame(rows), "notes": notes,
            "price": price,
            "implied_pe": (round(price / rows[1]["FY EPS"], 1)
                           if price and rows[1]["FY EPS"] > 0 else None)}


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
    if out:
        return out
    from llm import fail_reason
    return f"（歸因生成失敗：{fail_reason()}——僅顯示誤差表）"


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
# 研究文章庫(生成的報告存檔,像網站一樣瀏覽)
# ────────────────────────────────────────
ART_DIR = __import__("pathlib").Path(__file__).parent / "data" / "research_articles"
CONF_PATH = __import__("pathlib").Path(__file__).parent / "data" / "conf_notes.json"


def get_conf_notes(code: str) -> list[dict]:
    """該股的法說/重要質性筆記 [{date, note}](新到舊)。"""
    import json
    try:
        d = json.loads(CONF_PATH.read_text(encoding="utf-8"))
        return sorted(d.get(code, []), key=lambda x: x.get("date", ""), reverse=True)
    except Exception:
        return []


def add_conf_note(code: str, note: str) -> None:
    """存法說筆記(進 git → 雲端同步;之後該股與其族群的報告自動引用)。"""
    import json
    d = {}
    try:
        d = json.loads(CONF_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    d.setdefault(code, []).append({"date": f"{now_tw():%Y-%m-%d}", "note": note.strip()})
    CONF_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _conf_extra(codes) -> str:
    """一組股票的法說筆記文字包(縫進報告 digest;質性資訊修正量化誤讀,如營收虛胖)。"""
    if isinstance(codes, str):
        codes = [codes]
    lines = []
    for c in codes:
        for n in get_conf_notes(c)[:3]:
            lines.append(f"- {c}({n['date']}):{n['note']}")
    out = ""
    if lines:
        out = ("\n【法說/質性筆記(使用者記錄——量化數據要用這些修正,"
               "例如營收成長若為漲價轉嫁則屬虛胖,需以毛利率驗證)】\n" + "\n".join(lines))
    # 產品組合(法說結構化層):報告推論必須基於實際產品結構
    try:
        from product_mix import mix_digest
        for c in codes:
            out += mix_digest(c)
    except Exception:
        pass
    return out


def save_article(code: str, name: str, mode: str, content: str) -> str:
    """存成文章;回傳檔名。標題取內文第一行。"""
    ART_DIR.mkdir(parents=True, exist_ok=True)
    ts = now_tw().strftime("%Y%m%d_%H%M")
    first = next((ln.strip().lstrip("#* ").rstrip("*")
                  for ln in content.splitlines() if ln.strip()), f"{code} 研究")
    header = (f"<!--meta\ntitle: {first[:80]}\ncode: {code}\nname: {name}\n"
              f"mode: {mode}\ndate: {now_tw():%Y-%m-%d %H:%M}\n-->\n\n")
    p = ART_DIR / f"art_{ts}_{code}.md"
    p.write_text(header + content, encoding="utf-8")
    return p.name


def git_publish(fname: str) -> str:
    """把文章 commit 進 git(+嘗試 push)。雲端無權限時自動略過,不影響存檔。"""
    import subprocess
    root = ART_DIR.parent.parent          # repo 根目錄

    def run(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, timeout=90, encoding="utf-8", errors="replace")
    try:
        rel = f"data/research_articles/{fname}"
        if run("add", rel).returncode != 0:
            return "git add 失敗(略過)"
        r = run("commit", "-m", f"docs: 研究文章 {fname}")
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "nothing to commit" not in out:
            return "git commit 失敗(略過)"
        run("pull", "--rebase", "origin", "main")
        p = run("push", "origin", "main")
        return ("已 commit 並推上 GitHub ✅(雲端重部署也不會消失)"
                if p.returncode == 0 else
                "已本機 commit ✅(push 失敗——雲端環境無權限屬正常,本機下次推送會帶上)")
    except Exception as e:
        return f"git 發佈略過({type(e).__name__})"


def list_articles() -> list[dict]:
    """文章清單(新到舊):{file,title,code,name,mode,date}"""
    out = []
    if not ART_DIR.exists():
        return out
    for p in sorted(ART_DIR.glob("art_*.md"), reverse=True):
        meta = {"file": p.name, "title": p.stem, "code": "", "name": "",
                "mode": "", "date": ""}
        try:
            txt = p.read_text(encoding="utf-8")
            if txt.startswith("<!--meta"):
                for ln in txt.split("-->")[0].splitlines()[1:]:
                    if ":" in ln:
                        k, v = ln.split(":", 1)
                        if k.strip() in meta:
                            meta[k.strip()] = v.strip()
        except Exception:
            continue
        out.append(meta)
    return out


def read_article(fname: str) -> str:
    p = ART_DIR / fname
    txt = p.read_text(encoding="utf-8")
    return txt.split("-->", 1)[1].strip() if txt.startswith("<!--meta") else txt


# ────────────────────────────────────────
# 同業比較(產業寫作模式用)
# ────────────────────────────────────────
def peer_compare(codes: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """回傳 (月營收指數化表, 季度毛利率對比表)。指數化=各自24月前=100。"""
    from pathlib import Path
    sl = pd.read_csv(Path(__file__).parent / "data" / "stock_list.csv",
                     encoding="utf-8-sig", dtype=str)
    nm = dict(zip(sl["code"], sl["name"]))
    rev_cols, gm_cols = {}, {}
    for c in codes:
        label = f"{c} {nm.get(c, '')}"
        mon = monthly_revenue(c, years=2)
        if not mon.empty:
            s = mon.set_index("ym")["revenue"]
            rev_cols[label] = (s / s.iloc[0] * 100).round(1)
        q = quarterly_fin(c, years=3)
        if not q.empty and "毛利率%" in q.columns:
            gm_cols[label] = q.set_index("季度")["毛利率%"]
    rev = pd.DataFrame(rev_cols).rename_axis("ym").reset_index() if rev_cols else pd.DataFrame()
    gm = pd.DataFrame(gm_cols).rename_axis("季度").reset_index() if gm_cols else pd.DataFrame()
    return rev, gm


_SYS_INDUSTRY = """你是產業分析寫作者(優分析風格),寫一篇「同業比較型」產業文章。
【輸出格式鐵律】回覆就是文章本文,從標題開始,嚴禁前言或完成總結。
風格規範(嚴格遵守):
· 標題用**問句式**:點出現象+懸念(例:「XX三雄當中,為什麼A的營收最先創高?」)
· 開場:現象→成因預告,兩三句直接切入,不寒暄
· 論述遞進鏈:**產品結構→客群→產業週期位置→營運表現**——解釋「同族群為何表現分化」
· 數據呈現:講**趨勢與占比**,避免數字堆砌;引用給你的營收指數化/毛利率對比,數字照抄
· 語氣:條件式語言(「通常會較快反映」「若景氣成長來源改變」),不喊買賣、不給目標價
· 每家公司一段:它的產品結構(有補充資料就用,沒有就誠實說「公開產品佔比待查」並列出該查什麼)
  →對應客群→在本輪週期的位置
· 結論:**教方法論**——「下次比較同族群時,先從景氣成長來源找受惠順序」這類可遷移的框架
· 結尾列「觀察清單」:接下來每家該盯的一個數字
600-1000字,markdown。免責一句話帶過。"""


def generate_industry_report(code: str, peers: list[str], extra: str = "") -> str:
    """產業比較型報告(優分析風):主角+同業的營收/毛利對比,產品結構靠補充資料。"""
    all_codes = [code] + [p for p in peers if p and p != code]
    extra = (extra or "") + _conf_extra(all_codes)
    rev, gm = peer_compare(all_codes)
    if rev.empty:
        return "（抓不到比較資料）"
    d = build_digest(code, extra)
    parts = [f"主角:{code} {d['name']}　{d['price']}",
             f"比較對象:{', '.join(all_codes)}",
             "【月營收指數化(各自24月前=100)】", rev.tail(15).to_string(index=False),
             "【季度毛利率%對比】", gm.tail(8).to_string(index=False),
             f"【主角月營收YoY 近6月】{[round(v,1) for v in d['monthly']['yoy%'].tail(6)]}"]
    if extra.strip():
        parts += ["【補充資料(產品結構/法說等,使用者提供)】", extra.strip()[:5000]]
    else:
        parts += ["【注意】未提供產品結構資料——文章需誠實標明,並列出該查的產品別問題"]
    from llm import generate
    out = generate(_SYS_INDUSTRY, "\n".join(parts), max_tokens=2500)
    if out:
        return out + f"\n\n---\n*數據:FinMind/TWSE;產生於 {now_tw():%Y-%m-%d %H:%M}。產業觀察非投資建議。*"
    from llm import fail_reason
    return f"（報告生成失敗：{fail_reason()}）"


_SYS_FLASH = """你是券商晨報研究員,寫一則「月營收快評」(仿投顧晨報格式,但不喊買賣)。
【輸出鐵律】回覆即快評本文,從粗體導言開始,無前言無總結。格式:
1. **導言一段**(粗體):「XX(代碼) MM/YYYY 營收 A 百萬,MoM±x%、YoY±y%,優於/低於模型預期
   (與模型預期值 B 差異約 ±z%),主因……」——主因只能寫數據可支持或補充資料提供的;
   都沒有就寫「主因待查(建議看月營收公告備註/法說)」
2. 「## 數據明細」:當月/累計營收與YoY、近3月走勢
3. 「## 模型 vs 實際」:模型預期值怎麼來(去年同月×前3月YoY中位)、誤差、
   這個誤差是雜訊還是趨勢轉變(對照歷史回測誤差)
4. 「## 展望與情境」:引用給你的 H1 估值/推估表數字(照抄勿改)
5. 「## 追蹤點」2-3條
數字精確、單位照抄;推測與事實分開。350-600字。結尾一句免責。"""


def generate_flash_note(code: str, extra: str = "") -> str:
    """月營收快評(晨報式):最新月營收 vs 模型預期值+誤差+展望。"""
    extra = (extra or "") + _conf_extra(code)
    d = build_digest(code, extra)
    mon = d["monthly"]
    if mon.empty:
        return f"（抓不到 {code} 月營收）"
    bc = backcast_monthly(code, lookback=6)
    hv = h1_valuation(code)
    last = mon.iloc[-1]
    mom = (mon["revenue"].iloc[-1] / mon["revenue"].iloc[-2] - 1) * 100 if len(mon) > 1 else 0
    ytd = mon[mon["ym"].str.startswith(last["ym"][:4])]["revenue"].sum()
    parts = [f"個股:{d['code']} {d['name']}　{d['price']}",
             f"最新月營收:{last['ym']} = {last['revenue']:,.1f} 百萬,MoM {mom:+.1f}%,YoY {last['yoy%']:+.1f}%",
             f"今年累計:{ytd:,.0f} 百萬",
             "【近6月營收】", mon.tail(6).to_string(index=False)]
    if not bc.empty:
        parts += ["【模型 vs 實際(walk-forward 回測)】", bc.to_string(index=False)]
    if hv:
        parts += [f"【H1估值】Q1 {hv['q1']} / Q2 {hv['q2']}({hv.get('q2_src','')}) / H1 {hv['h1']};現價隱含PE {hv.get('implied_pe')}x",
                  hv["table"].to_string(index=False)]
    if extra.strip():
        parts += ["【補充資料(使用者提供:法說/公告歸因等)】", extra.strip()[:3000]]
    from llm import generate
    out = generate(_SYS_FLASH, "\n".join(parts), max_tokens=1800)
    if out:
        return out + f"\n\n---\n*模型預期值=去年同月×前3月YoY中位;產生於 {now_tw():%Y-%m-%d %H:%M}。非投資建議。*"
    from llm import fail_reason
    return f"（快評生成失敗：{fail_reason()}）"


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
    extra = (extra or "") + _conf_extra(code)
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
    from llm import fail_reason
    return f"（報告生成失敗：{fail_reason()}——下方數據表仍可用）"

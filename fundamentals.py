"""
fundamentals.py — 個股基本面資料 + 財報筆記產生器
=================================================================
學「產品轉型觀察筆記」的寫法（觀察 → 數字推論 → 主觀結論 + 免責）：
  資料：FinMind 免費 API（月營收、季度綜合損益）＋ 系統內籌碼/股價
  產生：有 ANTHROPIC_API_KEY → Claude 仿該風格寫筆記；
        使用者可貼「補充資料」（法說 QA、公開說明書產品佔比、ASP 等），
        Claude 會把它跟財報數字縫在一起推論——這正是範文最有價值的部分。
  快取：data/fundamentals/{code}_*.json，20 小時。
"""
from __future__ import annotations
import json
import time
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
DATA = ROOT / "data"
FUND_DIR = DATA / "fundamentals"
FUND_DIR.mkdir(parents=True, exist_ok=True)

FM_URL = "https://api.finmindtrade.com/api/v4/data"
CACHE_HOURS = 20


def _fm(dataset: str, code: str, start: str) -> list[dict]:
    """FinMind 免費端點（無 token，量少夠用）；20 小時快取。
    限流(402)或任何失敗 → 退回舊快取(不論多舊)——基本面資料月更,舊快取遠勝空手。"""
    p = FUND_DIR / f"{code}_{dataset}.json"
    if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_HOURS * 3600:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _stale() -> list[dict]:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    try:
        r = requests.get(FM_URL, params={"dataset": dataset, "data_id": code,
                                         "start_date": start}, timeout=25)
        j = r.json()
        data = j.get("data", []) if j.get("status") == 200 else []
        if data:
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        return _stale()          # 限流/空回應:用舊快取,並保留舊 mtime 讓下次仍會嘗試更新
    except Exception:
        return _stale()


def monthly_revenue(code: str, years: int = 3) -> pd.DataFrame:
    """月營收 + YoY%。欄位: ym, revenue(百萬), yoy%"""
    start = f"{now_tw().year - years - 1}-01-01"
    data = _fm("TaiwanStockMonthRevenue", code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["ym"] = df["revenue_year"].astype(str) + "-" + df["revenue_month"].astype(str).str.zfill(2)
    df["revenue"] = df["revenue"] / 1e6
    df = df.sort_values("ym").reset_index(drop=True)
    df["yoy%"] = (df["revenue"] / df["revenue"].shift(12) - 1) * 100
    return df[["ym", "revenue", "yoy%"]].tail(years * 12)


def quarterly_fin(code: str, years: int = 3) -> pd.DataFrame:
    """季度損益：營收/毛利率/營益率/淨利率/EPS"""
    start = f"{now_tw().year - years - 1}-01-01"
    data = _fm("TaiwanStockFinancialStatements", code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    piv = df.pivot_table(index="date", columns="type", values="value", aggfunc="first")
    out = pd.DataFrame(index=piv.index)
    rev = piv.get("Revenue")
    if rev is None:
        return pd.DataFrame()
    out["營收(億)"] = rev / 1e8
    if "GrossProfit" in piv:
        out["毛利率%"] = piv["GrossProfit"] / rev * 100
    if "OperatingIncome" in piv:
        out["營益率%"] = piv["OperatingIncome"] / rev * 100
    if "IncomeAfterTaxes" in piv:
        out["淨利率%"] = piv["IncomeAfterTaxes"] / rev * 100
    if "EPS" in piv:
        out["EPS"] = piv["EPS"]
    out = out.reset_index().rename(columns={"date": "季度"})
    return out.round(2).tail(years * 4)


def _chip_context(code: str) -> str:
    """外資近20日累計買賣超 + 融資近20日增減（有資料才寫）"""
    bits = []
    p = DATA / "institutional" / f"{code}_inst.csv"
    if p.exists():
        try:
            m = pd.read_csv(p)
            a = pd.to_numeric(m.get("外陸資買賣超股數(不含外資自營商)"), errors="coerce")
            b = pd.to_numeric(m.get("外資買賣超股數"), errors="coerce")
            fi = a.fillna(b).dropna().tail(20).sum() / 1000
            bits.append(f"外資近20日累計{'買超' if fi >= 0 else '賣超'} {abs(fi):,.0f} 張")
        except Exception:
            pass
    p2 = DATA / "margin" / f"{code}_margin.csv"
    if p2.exists():
        try:
            mg = pd.read_csv(p2)["margin_balance"].dropna()
            d = mg.iloc[-1] - mg.iloc[-min(20, len(mg))]
            bits.append(f"融資近20日{'增' if d >= 0 else '減'} {abs(d):,.0f} 張")
        except Exception:
            pass
    return "；".join(bits)


def build_note_digest(code: str) -> dict:
    """組筆記所需的數據包"""
    name = ""
    try:
        sl = pd.read_csv(DATA / "stock_list.csv", encoding="utf-8-sig", dtype=str)
        hit = sl[sl["code"] == code]
        name = hit["name"].iloc[0] if not hit.empty else ""
    except Exception:
        pass
    return {
        "code": code, "name": name,
        "monthly": monthly_revenue(code),
        "quarterly": quarterly_fin(code),
        "chips": _chip_context(code),
    }


# ────────────────────────────────────────
# 選股/回測用：時點對齊的基本面序列（含公布時滯，避免未來函數）
# ────────────────────────────────────────
def revenue_yoy_series(code: str) -> pd.Series:
    """月營收 YoY%，index=「可得日」（次月10日才公布）。回測按日 ffill 使用。"""
    data = _fm("TaiwanStockMonthRevenue", code, "2014-01-01")
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data).sort_values(["revenue_year", "revenue_month"])
    rev = df["revenue"].astype(float)
    yoy = (rev / rev.shift(12) - 1) * 100
    avail = pd.to_datetime(dict(year=df["revenue_year"], month=df["revenue_month"], day=1)) \
        + pd.offsets.MonthBegin(1) + pd.Timedelta(days=9)      # 次月10日
    s = pd.Series(yoy.values, index=avail)
    return s.dropna()


def eps5_series(code: str) -> pd.Series:
    """近5年平均EPS，index=可得日（年報隔年4/1）。"""
    data = _fm("TaiwanStockFinancialStatements", code, "2014-01-01")
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data)
    eps = df[df["type"] == "EPS"].copy()
    if eps.empty:
        return pd.Series(dtype=float)
    eps["year"] = pd.to_datetime(eps["date"]).dt.year
    annual = eps.groupby("year")["value"].sum()
    annual = annual[annual.index < now_tw().year]      # 今年未完不算年度EPS
    avg5 = annual.rolling(5, min_periods=3).mean()      # 資料不足5年放寬到3年
    avail = pd.to_datetime([f"{y + 1}-04-01" for y in avg5.index])
    return pd.Series(avg5.values, index=avail).dropna()


def shares_map() -> dict:
    """{code: 流通股數}（實收資本額/10；上市+上櫃 bulk，快取20h）"""
    p = FUND_DIR / "shares_map.json"
    if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_HOURS * 3600:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    out = {}
    for url in ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
                "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            for row in r.json():
                code = str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or "").strip()
                cap = str(row.get("實收資本額") or row.get("實收資本額(元)")
                          or row.get("Paidin.Capital.NTDollars") or "0")
                cap = float(cap.replace(",", "") or 0)
                if code and cap > 0:
                    out[code] = cap / 10.0          # 面額10元 → 股數
        except Exception:
            continue
    if out:
        p.write_text(json.dumps(out), encoding="utf-8")
        return out
    if p.exists():                        # 兩源都失敗 → 舊快取(股數變動極慢)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return out


_STYLE = """你是寫「個股觀察筆記」的個人投資人，文風範例（要學的骨架）：
- 開頭一律附免責：**「以下屬個人基於公開資訊的主觀推論及投資筆記，不構成任何投資建議，歡迎指正。」**
- 觀察 → 數字推論 → 主觀結論的節奏：先陳述財報可見的「變化」（如毛利率逐季改善、
  某產品佔比上升），再用數字做簡單回推（如 ASP=金額/出貨量），最後才給主觀判斷，
  並明說哪些是推測。
- 語氣坦白謙虛（「就我個人理解」「粗估」「簡單線性回推」），數字精確引用。
- 用 markdown；小標題分段：营收動能／獲利結構變化／籌碼面／（若有補充資料）法說與產品線推論／主觀結論與追蹤點。
- 別編造：數據包沒有的事實不要寫；補充資料裡的數字可引用並註明來源是使用者提供。
- 數字單位照數據包原樣照抄（表頭寫「營收(億)」值為 8.23 就寫 8.23 億），
  嚴禁自行換算或移動小數點；沒把握的數字寧可不寫。
- 結尾列 2-3 個「後續追蹤點」（下一季該驗證什麼）。長度 500-800 字。"""


def write_note(code: str, extra: str = "") -> str:
    """產生財報筆記。有 key 用 Claude 仿風格；沒 key 回數據摘要版。"""
    d = build_note_digest(code)
    mon: pd.DataFrame = d["monthly"]
    q: pd.DataFrame = d["quarterly"]
    if mon.empty and q.empty:
        return f"（抓不到 {code} 的財務資料——FinMind 免費額度或代碼問題）"

    mon_txt = mon.tail(13).to_string(index=False) if not mon.empty else "無"
    q_txt = q.to_string(index=False) if not q.empty else "無"
    digest = (f"個股：{d['code']} {d['name']}\n"
              f"【月營收(百萬) 近13月】\n{mon_txt}\n\n"
              f"【季度損益 近3年】\n{q_txt}\n\n"
              f"【籌碼】{d['chips'] or '無資料'}\n")
    if extra.strip():
        digest += f"\n【使用者提供的補充資料（法說/公開說明書等）】\n{extra.strip()[:4000]}\n"

    from llm import generate
    out = generate(_STYLE, digest, max_tokens=2000)
    if out:
        return out + f"\n\n---\n*數據：FinMind/系統籌碼庫，產生於 {now_tw():%Y-%m-%d %H:%M}*"

    # 離線版：純數據摘要
    L = [f"# 📝 {d['code']} {d['name']} 財報數據摘要（離線模式）",
         "> 以下屬公開資訊整理，不構成投資建議。設定 ANTHROPIC_API_KEY 可升級為完整觀察筆記。",
         "", "## 月營收（近13月，百萬）", "```", mon_txt, "```",
         "", "## 季度損益（近3年）", "```", q_txt, "```",
         "", f"## 籌碼\n{d['chips'] or '無資料'}"]
    if extra.strip():
        L += ["", "## 你的補充資料（原文保留）", extra.strip()]
    return "\n".join(L)

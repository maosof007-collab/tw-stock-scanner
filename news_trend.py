"""
news_trend.py — 產業趨勢雷達（消息面）
=================================================================
從 data/news/news_*.csv 聚合出「哪個產業的新聞正在變熱、風向偏多還偏空」：
  · 熱度動能 = 近 N 日提及則數 vs 前 N 日（倍數變化）
  · 情緒     = 標題詞典計分（正/負面詞，免 API、可離線跑）
  · 產業歸屬 = 抓取時的 sector 標籤 + 標題關鍵字/成分股股名比對補標
搭配 RRG（資金面）交叉看：新聞轉熱 + RRG 改善/領先 = 趨勢起點候選。
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"
NEWS_DIR = DATA / "news"

# ── 標題情緒詞典（台股財經新聞常用詞）──
POS_WORDS = [
    "漲停", "大漲", "飆", "急漲", "創新高", "新高", "看好", "看多", "利多", "報喜",
    "優於預期", "超預期", "上修", "調升", "擴產", "急單", "滿載", "搶單", "大單",
    "回溫", "復甦", "轉盈", "成長", "創高", "目標價上看", "買進評等", "加碼",
    "受惠", "突破", "強勢", "熱銷", "供不應求", "漲價", "旺季",
]
NEG_WORDS = [
    "跌停", "大跌", "重挫", "崩", "急殺", "創新低", "新低", "看壞", "看空", "利空",
    "低於預期", "不如預期", "下修", "調降", "砍單", "抽單", "殺價", "庫存調整",
    "疲弱", "衰退", "轉虧", "虧損", "裁員", "停工", "訴訟", "違約", "示警",
    "失守", "弱勢", "賣壓", "降評", "跌價", "淡季", "觀望",
]


def _title_score(title: str) -> float:
    """詞典計分：每命中一詞 ±1，夾在 [-1, 1]。"""
    s = sum(1 for w in POS_WORDS if w in title) - sum(1 for w in NEG_WORDS if w in title)
    return max(-1.0, min(1.0, float(s)))


def _load_news(days: int) -> pd.DataFrame:
    files = sorted(NEWS_DIR.glob("news_*.csv"))
    if not files:
        return pd.DataFrame()
    frames = []
    for p in files[-(days + 3):]:            # 檔名按日期排，少讀舊檔
        try:
            frames.append(pd.read_csv(p, encoding="utf-8-sig"))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["title"] = df["title"].astype(str)
    df = df.drop_duplicates(subset="title")
    # 濾掉大盤行情類雜訊（「台股漲25.91點」這種會被每個產業查詢撈到，灌水熱度）
    noise = re.compile(r"^台股[漲跌]|大盤|加權指數|收盤|開盤|盤中速報|盤後解析|台股(?:開高|開低|收紅|收黑|收漲|收跌)")
    df = df[~df["title"].str.contains(noise)]
    df["pub_date"] = pd.to_datetime(df["published"].astype(str).str[:10], errors="coerce")
    df = df.dropna(subset=["pub_date"])
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
    return df[df["pub_date"] >= cutoff].reset_index(drop=True)


def _sector_maps():
    """(股名→產業, 產業關鍵字→產業)。股名取 ≥2 字避免誤撞。"""
    sl = pd.read_csv(DATA / "stock_list.csv", encoding="utf-8-sig", dtype=str).dropna(subset=["sector"])
    name2sec = {str(n).strip(): s for n, s in zip(sl["name"], sl["sector"])
                if isinstance(n, str) and len(str(n).strip()) >= 2}
    kw2sec = {}
    for sec in sl["sector"].unique():
        base = re.sub(r"(工業|產業|事業)$", "", str(sec))
        base = base.replace("業", "") if base.endswith("業") else base
        if len(base) >= 2 and "其他" not in base:
            kw2sec[base] = sec
    return name2sec, kw2sec


def _tag_sector(df: pd.DataFrame) -> pd.DataFrame:
    """補標產業：已有 sector 標籤者沿用；否則用產業關鍵字→成分股股名比對標題。"""
    name2sec, kw2sec = _sector_maps()
    if "sector" not in df.columns:
        df["sector"] = ""
    df["sector"] = df["sector"].fillna("").astype(str)

    def tag(row):
        if row["sector"] and row["sector"] != "nan":
            return row["sector"]
        t = row["title"]
        for kw, sec in kw2sec.items():
            if kw in t:
                return sec
        for nm, sec in name2sec.items():
            if nm in t:
                return sec
        return ""

    df["sector"] = df.apply(tag, axis=1)
    return df


def build_sector_trend(win: int = 7):
    """回傳 (trend_df, headlines_dict, asof)。
    trend_df: 產業/近N日/前N日/熱度Δ/情緒/代表標題數；headlines: {產業: DataFrame}。"""
    df = _load_news(days=win * 2)
    if df.empty:
        return pd.DataFrame(), {}, None
    df = _tag_sector(df)
    df = df[df["sector"] != ""].copy()
    if df.empty:
        return pd.DataFrame(), {}, None
    df["score"] = df["title"].map(_title_score)

    asof = df["pub_date"].max()
    recent_cut = asof - pd.Timedelta(days=win - 1)
    rec = df[df["pub_date"] >= recent_cut]
    prev = df[df["pub_date"] < recent_cut]

    rows, headlines = [], {}
    for sec, g in df.groupby("sector"):
        r = rec[rec["sector"] == sec]
        p = prev[prev["sector"] == sec]
        n_r, n_p = len(r), len(p)
        momentum = (n_r - n_p) / max(n_p, 1)
        senti = r["score"].mean() if n_r else 0.0
        rows.append({
            "產業": sec,
            f"近{win}日": n_r, f"前{win}日": n_p,
            "熱度Δ%": round(momentum * 100, 0),
            "情緒": round(float(senti), 2),
            "趨勢分": round(momentum + float(senti), 2),
        })
        hs = g.sort_values("pub_date", ascending=False)
        headlines[sec] = hs[["pub_date", "title", "score", "source", "url"]].head(30)

    trend = pd.DataFrame(rows).sort_values("趨勢分", ascending=False).reset_index(drop=True)
    return trend, headlines, asof

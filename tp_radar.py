"""
tp_radar.py — 目標價雷達(分析師共識追蹤)
=================================================================
資料源:鉅亨網 tw_forecast 分類 = Factset 共識速報自動流。
標題即資料:「Factset 最新調查:XX(1234-TW)目標價調升至X元,幅度約Y%」
           「Factset 最新調查:XX(1234-TW)EPS預估上修至X元,預估目標價為Y元」
限制:feed 只留最近 ~40 篇 → 必須每天抓才能累積歷史(data/tp_radar.csv)。
用途:持股/ETF/觀察名單的目標價異動警示;戰情室顯示最新共識。
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "tp_radar.csv"

_HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://news.cnyes.com/"}

# 目標價調升/調降
_RE_TP = re.compile(
    r"Factset\s*最新調查[:：]\s*(?P<name>[^(（]+)[（(](?P<code>\d{4,6})-TW[)）]"
    r"目標價調(?P<dir>升|降)至\s*(?P<tp>[\d,.]+)\s*元(?:[,，]幅度約\s*(?P<pct>[\d.]+)%)?")
# EPS 上修/下修(附帶目標價)
_RE_EPS = re.compile(
    r"Factset\s*最新調查[:：]\s*(?P<name>[^(（]+)[（(](?P<code>\d{4,6})-TW[)）]"
    r"EPS預估(?P<dir>上修|下修)至\s*(?P<eps>[\d,.]+)\s*元(?:[,，]預估目標價為\s*(?P<tp>[\d,.]+)\s*元)?")


def _get(url: str):
    req = urllib.request.Request(url, headers=_HDRS)
    return json.load(urllib.request.urlopen(req, timeout=20))


def _parse_title(title: str) -> dict | None:
    m = _RE_TP.search(title)
    if m:
        return {"code": m["code"], "名稱": m["name"].strip(),
                "類型": "目標價", "方向": "↑" if m["dir"] == "升" else "↓",
                "目標價": float(m["tp"].replace(",", "")),
                "EPS預估": None,
                "幅度%": float(m["pct"]) if m["pct"] else None}
    m = _RE_EPS.search(title)
    if m:
        return {"code": m["code"], "名稱": m["name"].strip(),
                "類型": "EPS", "方向": "↑" if m["dir"] == "上修" else "↓",
                "目標價": float(m["tp"].replace(",", "")) if m["tp"] else None,
                "EPS預估": float(m["eps"].replace(",", "")),
                "幅度%": None}
    return None


def fetch() -> pd.DataFrame:
    """抓 tw_forecast feed(近~40篇),parse 後併入 data/tp_radar.csv(newsId 去重)。"""
    rows = []
    for page in (1, 2):
        try:
            d = _get(f"https://api.cnyes.com/media/api/v1/newslist/category/tw_forecast?limit=30&page={page}")
        except Exception:
            break
        items = (d.get("items") or {}).get("data") or []
        if not items:
            break
        for it in items:
            r = _parse_title(it.get("title", ""))
            if r is None:
                continue
            ts = it.get("publishAt")
            r["日期"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
            r["newsId"] = it.get("newsId")
            rows.append(r)
    new = pd.DataFrame(rows)
    if OUT.exists():
        old = pd.read_csv(OUT, dtype={"code": str})
        merged = pd.concat([old, new], ignore_index=True)
    else:
        merged = new
    if not merged.empty:
        merged["newsId"] = merged["newsId"].astype("Int64")
        merged = (merged.drop_duplicates(subset=["newsId"])
                        .sort_values("日期", ascending=False))
        cols = ["日期", "code", "名稱", "類型", "方向", "目標價", "EPS預估", "幅度%", "newsId"]
        merged = merged[[c for c in cols if c in merged.columns]]
        merged.to_csv(OUT, index=False, encoding="utf-8-sig")
    return new


def load() -> pd.DataFrame:
    if OUT.exists():
        return pd.read_csv(OUT, dtype={"code": str})
    return pd.DataFrame()


def latest_for(code: str) -> dict | None:
    """個股最新一筆共識(戰情室用):{日期, 目標價, EPS預估, 方向, 類型}。"""
    df = load()
    if df.empty:
        return None
    g = df[df["code"].astype(str) == str(code)]
    if g.empty:
        return None
    return g.sort_values("日期", ascending=False).iloc[0].to_dict()


def alerts(codes: list[str], days: int = 3) -> pd.DataFrame:
    """近 days 天內,名單中個股的目標價/EPS 異動(晨報/駕駛艙用)。"""
    df = load()
    if df.empty:
        return df
    cutoff = f"{now_tw() - pd.Timedelta(days=days):%Y-%m-%d}"
    codes = {str(c) for c in codes}
    return df[(df["日期"] >= cutoff) & (df["code"].astype(str).isin(codes))]


if __name__ == "__main__":
    got = fetch()
    print(f"本次抓到 {len(got)} 筆;累積 {len(load())} 筆")
    if not got.empty:
        print(got.to_string(index=False))

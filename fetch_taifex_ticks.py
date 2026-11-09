# -*- coding: utf-8 -*-
"""
fetch_taifex_ticks.py — 期交所逐筆成交 → 台指 1 分 K 累積庫(微台機器人前置)
=================================================================
教案(2026-11-09「看看期貨吧 微台機器人」):期交所免費逐筆只保留近 30 個
交易日,每天流失一天;要回測微台當沖,今天就得開始囤。
來源:https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_YYYY_MM_DD.zip
     (Big5、逐筆:成交日期,商品代號,到期月份,成交時間,成交價格,成交數量(B+S),…)
產出:data/taifex_1min.csv.gz — date,time,prod,contract,session,open,high,low,close,vol
  - prod ∈ {TX,MTX,TMF};contract=近月(當日量最大之純月份,排除價差單)
  - session: day(08:45–13:45)/ night(其餘);vol 為 B+S 口數(真實量除以 2)
  - 檔名日=交易日;夜盤(成交日期=前一日 15:00 起)歸同一交易日
雷點:G 碟大量寫入會 I/O 錯誤 → zip/解壓全在 C:(tempfile);
     requests 會被 AVG TLS 攔截 → 一律 subprocess curl。
排程:daily_task.bat 每晚跑(增量,已有的交易日直接跳過)。
"""
import gzip
import io
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "taifex_1min.csv.gz"
URL = "https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{:%Y_%m_%d}.zip"
PRODS = {"TX", "MTX", "TMF"}
COLS = ["date", "time", "prod", "contract", "session", "open", "high", "low", "close", "vol"]


def _have() -> set:
    """已完成的交易日。今天永遠重抓:盤中跑到的是不完整檔,晚上要讓完整檔蓋掉。"""
    if OUT.exists():
        ds = pd.read_csv(OUT, usecols=["date"])["date"].astype(str).unique()
        return {x for x in ds if x < f"{date.today():%Y-%m-%d}"}
    return set()


def _fetch(d: date, tmp: Path) -> Path | None:
    z = tmp / f"{d:%Y%m%d}.zip"
    r = subprocess.run(["curl", "-sS", "-f", "-o", str(z), URL.format(d)],
                       capture_output=True, text=True)
    return z if r.returncode == 0 and z.stat().st_size > 1000 else None


def _day(d: date, zpath: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as zf:
        raw = zf.read(zf.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), encoding="cp950", skiprows=1, header=None,
                     usecols=[0, 1, 2, 3, 4, 5], dtype=str,
                     names=["d0", "prod", "contract", "t", "px", "qty"])
    for c in ("prod", "contract"):
        df[c] = df[c].str.strip()
    df = df[df["prod"].isin(PRODS) & df["contract"].str.fullmatch(r"\d{6}")]
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df["px"] = pd.to_numeric(df["px"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    df = df.dropna(subset=["px", "qty"])
    t = df["t"].str.zfill(6)
    df["hhmm"] = t.str[:2] + ":" + t.str[2:4]
    df["session"] = "night"
    df.loc[(df["d0"] == f"{d:%Y%m%d}") & (df["hhmm"] >= "08:45") & (df["hhmm"] <= "13:45"),
           "session"] = "day"
    out = []
    for p, g in df.groupby("prod"):
        near = g.groupby("contract")["qty"].sum().idxmax()  # 近月=量最大純月份
        g = g[g["contract"] == near].sort_values(["d0", "t"])
        k = g.groupby(["session", "hhmm"]).agg(
            open=("px", "first"), high=("px", "max"), low=("px", "min"),
            close=("px", "last"), vol=("qty", "sum")).reset_index()
        k.insert(0, "contract", near)
        k.insert(0, "prod", p)
        out.append(k)
    k = pd.concat(out, ignore_index=True)
    k.insert(0, "date", f"{d:%Y-%m-%d}")
    return k.rename(columns={"hhmm": "time"})[COLS]


def main() -> int:
    have = _have()
    news = []
    with tempfile.TemporaryDirectory() as td:  # C: 碟,避開 G: I/O 雷
        tmp = Path(td)
        for i in range(45, -1, -1):
            d = date.today() - timedelta(days=i)
            if d.weekday() >= 5 or f"{d:%Y-%m-%d}" in have:
                continue
            z = _fetch(d, tmp)
            if z is None:
                continue
            try:
                k = _day(d, z)
            except Exception as e:
                print(f"{d} 解析失敗:{e}")
                continue
            finally:
                z.unlink(missing_ok=True)
            if len(k):
                news.append(k)
                print(f"{d} OK:{len(k)} 根 1 分 K")
    if not news:
        print(f"無新資料(庫存 {len(have)} 個交易日)")
        return 0
    allk = pd.concat(([pd.read_csv(OUT, dtype={"time": str})] if OUT.exists() else []) + news,
                     ignore_index=True)
    allk = allk.drop_duplicates(["date", "time", "prod", "session"], keep="last").sort_values(
        ["date", "prod", "session", "time"])
    with gzip.open(OUT, "wt", encoding="utf-8", newline="") as f:
        allk.to_csv(f, index=False)
    print(f"累積 {allk['date'].nunique()} 個交易日、{len(allk)} 根(新增 {len(news)} 日)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

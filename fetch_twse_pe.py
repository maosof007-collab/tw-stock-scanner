# -*- coding: utf-8 -*-
"""
fetch_twse_pe.py — 證交所官方「大盤本益比、殖利率、股價淨值比」月資料
================================================================
來源:證交所 統計報表 > 上市公司月報 >「大盤、各產業類股及上市股票本益比、殖利率及股價淨值比」
      https://www.twse.com.tw/staticFiles/inspection/inspection/04/001/YYYYMM_C04001.zip (每月一個 ZIP,內含 .xls)
      官方定義:大盤本益比 = 月底大盤總市值 ÷ 大盤所有上市公司近四季稅後純益總額。每月第 7 個營業日更新上個月。
做法:只抓 data/twse_market_pe.csv 裡還沒有的月份;ZIP 在記憶體裡解開、只讀「大盤」那一列,原始檔不落地。
      1999/03~2002/11 的舊版面沒有「大盤」列,所以從 2002/12 開始。當月的檔案 9 號以後才會去問。
輸出:data/twse_market_pe.csv  欄位 ym(YYYY-MM), pe, yield, pb
用法:python -X utf8 fetch_twse_pe.py            # 補缺的月份(每天跑也只會多打一次請求)
      python -X utf8 fetch_twse_pe.py --since 2015-01   # 只補某個月份之後缺的
需要 xlrd(讀舊版 .xls):pip install xlrd
"""
from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from twtime import now_tw

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "twse_market_pe.csv"
URL = "https://www.twse.com.tw/staticFiles/inspection/inspection/04/001/{ym}_C04001.zip"
UA = {"User-Agent": "Mozilla/5.0"}
FIRST = "2002-12"          # 報表從 1999/03 起就有,但 2002/11 以前的版面沒有「大盤」那一列
PAUSE = 6.0                # 每個請求之間停幾秒。0.4 秒抓一百多個就被證交所 CDN 的流量保護擋(回 428),之後十幾分鐘全擋


def _num(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group(0)) if m else None


def parse(content: bytes) -> dict | None:
    """ZIP 位元組 → {'pe','yield','pb'};找不到「大盤」列回 None。"""
    import xlrd
    z = zipfile.ZipFile(io.BytesIO(content))
    wb = xlrd.open_workbook(file_contents=z.read(z.infolist()[0]))
    for sh in wb.sheets():
        for r in range(sh.nrows):
            vals = sh.row_values(r)
            for i, v in enumerate(vals):
                if isinstance(v, str) and re.sub(r"[\s　]", "", v) == "大盤":
                    nums = [x for x in (_num(c) for c in vals[i + 1:] if str(c).strip() != "") if x is not None]
                    if len(nums) >= 3:
                        return {"pe": nums[0], "yield": nums[1], "pb": nums[2]}
    return None


def months(since: str) -> list[str]:
    end = pd.Timestamp(now_tw().date()).to_period("M") - 1          # 最新只會有上個月
    return [str(p) for p in pd.period_range(since, end, freq="M")]


def main(since: str = FIRST) -> pd.DataFrame:
    import ssl_trust
    ssl_trust.ensure()
    old = pd.read_csv(OUT, dtype={"ym": str}) if OUT.exists() else pd.DataFrame(columns=["ym", "pe", "yield", "pb"])
    have = set(old.ym)
    todo = [m for m in months(since) if m not in have]
    last_m = str(pd.Timestamp(now_tw().date()).to_period("M") - 1)
    if now_tw().day < 9:                                            # 上個月的檔案第 7 個營業日才發布,太早問只是白打
        todo = [m for m in todo if m != last_m]
    rows, skipped, missing, blocked = [], [], [], False
    for k, ym in enumerate(todo):
        try:
            r = requests.get(URL.format(ym=ym.replace("-", "")), headers=UA, timeout=60)
        except Exception as e:
            missing.append(f"{ym}({type(e).__name__})")
            time.sleep(PAUSE)
            continue
        if r.status_code == 200 and r.content[:2] == b"PK":
            got = parse(r.content)
            (rows.append({"ym": ym, **got}) if got else skipped.append(ym))
        elif r.status_code == 428 or b"Anti-DDoS" in r.content[:4000]:
            blocked = True                                          # 證交所 CDN 的流量保護(要過瀏覽器檢查):不繞、不重打,下次排程再補
            missing += todo[k:]
            break
        else:
            missing.append(ym)                                      # 還沒發布
        if k % 25 == 24:
            print(f"  ...{k + 1}/{len(todo)} 最新 {rows[-1] if rows else None}", flush=True)
        time.sleep(PAUSE)
    df = pd.concat([old, pd.DataFrame(rows)], ignore_index=True) if rows else old
    df = df.drop_duplicates("ym", keep="last").sort_values("ym")
    if rows:
        df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"新增 {len(rows)} 個月|共 {len(df)} 個月 {df.ym.min() if len(df) else '-'} ~ {df.ym.max() if len(df) else '-'}"
          f"|沒有大盤列 {len(skipped)} 個月{(':' + skipped[0] + '~' + skipped[-1]) if skipped else ''}"
          f"|抓不到 {len(missing)} 個月{(':' + ','.join(missing[:6])) if missing else ''}"
          + ("|被證交所的流量保護擋住,這次先停,下次排程再補" if blocked else ""))
    return df


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[a.index("--since") + 1] if "--since" in a else FIRST)
    try:                                   # 官方月底之後公布的財報:估一次放快取,頁面只讀不抓
        import pe_river
        r = pe_river.market_series(20, fetch=True)
        if r:
            print(f"大盤 {r['last']:%m/%d} 本益比約 {r['pe']:.1f} 倍(官方 {r['base']:%Y/%m} 月底 {r['base_pe']} 倍)"
                  + (f",新財報估計:獲利 ×{r['nowcast']['ratio']:.3f}" if r["nowcast"] else ",沒有新財報估計"))
    except Exception as e:
        print(f"[warn] 新財報估計失敗: {e!r}")

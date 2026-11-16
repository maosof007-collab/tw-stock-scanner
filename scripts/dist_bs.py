# -*- coding: utf-8 -*-
"""電子通路業的資產負債表/現金流(公開資訊觀測站 t164sb03/t164sb05,單位換成億)→ data/_dist_bs.csv。
給 make_poster_dist.py 用;每季財報出齊後重跑:python -X utf8 scripts/dist_bs.py [民國年 季]
(FinMind 免費端點常被限流,這裡直接讀觀測站。)"""
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "_dist_bs.csv"
Y, S = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (115, 3)
H = {"User-Agent": "Mozilla/5.0"}
CODES = {"3702":"大聯大","3036":"文曄","2347":"聯強","8112":"至上","3048":"益登","6227":"茂綸","3312":"弘憶股","8096":"擎亞",
         "3028":"增你強","3033":"威健","6265":"方土昶","3209":"全科","3010":"華立","5434":"崇越","3055":"蔚華科","3444":"利機","8070":"長華*"}
ITEMS = {"存貨":"inv","應收帳款淨額":"ar","預付款項":"prepay","合約負債－流動":"cl","短期借款":"stdebt","現金及約當現金":"cash","應付帳款":"ap"}
def fetch(kind, code, y, s):
    for k in range(3):
        try:
            r = requests.post(f"https://mopsov.twse.com.tw/mops/web/ajax_{kind}", data={"encodeURIComponent":"1","step":"1","firstin":"1","off":"1",
                "queryName":"co_id","inpuType":"co_id","TYPEK":"all","isnew":"false","co_id":code,"year":str(y),"season":f"{s:02d}"}, headers=H, timeout=40)
            r.encoding = "utf-8"
            ts = [t for t in pd.read_html(io.StringIO(r.text)) if t.shape[0] > 10]
            if ts: return ts[0]
        except Exception as e:
            err = e
        time.sleep(4)
    return None
rows = []
for code, nm in CODES.items():
    rec = {"code": code, "名": nm}
    for (y, s) in ((Y, S), (Y, S - 1) if S > 1 else (Y - 1, 4)):
        t = fetch("t164sb03", code, y, s); time.sleep(2.2)
        if t is None: continue
        t.columns = [" ".join(str(x) for x in c) for c in t.columns]
        lab = t.iloc[:, 0].astype(str).str.replace(" ", "").str.replace("　", "")
        dcols = [c for c in t.columns if "月" in c and "金額" in c]
        for c in dcols:
            m = re.search(r"(\d+)年(\d+)月", c); d = f"{int(m.group(1))+1911}-{m.group(2)}"
            for zh, en in ITEMS.items():
                v = t.loc[lab == zh, c]
                if len(v): rec[f"{en}_{d}"] = float(v.iloc[0]) / 1e5   # 仟元→億
    t = fetch("t164sb05", code, Y, S); time.sleep(2.2)
    if t is not None:
        t.columns = [" ".join(str(x) for x in c) for c in t.columns]
        lab = t.iloc[:, 0].astype(str).str.replace(" ", "").str.replace("　", "")
        v = t.loc[lab.str.contains("營業活動之淨現金流入（流出）")]
        if len(v):
            nums = pd.to_numeric(v.iloc[0, 1:], errors="coerce").dropna()
            rec["ocf_9m"], rec["ocf_9m_ly"] = nums.iloc[0] / 1e5, nums.iloc[1] / 1e5
    rows.append(rec); print(nm, len(rec), file=sys.stderr)
pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
print("saved:", OUT)

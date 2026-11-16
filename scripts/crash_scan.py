# 依 strategies/crash_recovery.py 的定義,列出最近事件的錯殺候選與收復狀態(只讀)
import glob, sys, numpy as np, pandas as pd
bm = pd.read_csv('data/benchmark_TWII.csv', index_col=0, parse_dates=True).iloc[:, 0].dropna()
bm2 = bm.pct_change(2)
ev = bm2[bm2 <= -0.05]
print('近 60 日事件:'); print((ev.tail(8) * 100).round(1).to_string())
sl = pd.read_csv('data/stock_list.csv', dtype=str); nm = dict(zip(sl.code, sl.name)); sec = dict(zip(sl.code, sl.sector))
E_list = [d for d in ev.index if d >= pd.Timestamp('2026-10-01')]
rows = []
for f in glob.glob('data/[0-9][0-9][0-9][0-9].TW*.csv'):
    import os; code = os.path.basename(f)[:4]
    if code not in nm: continue
    try:
        d = pd.read_csv(f, index_col=0, parse_dates=True)
    except Exception: continue
    d = d[d.Volume > 0]
    if len(d) < 80: continue
    c, v = d.Close, d.Volume
    vol20 = v.rolling(20).mean()
    for E in E_list:
        loc = d.index.searchsorted(E)
        if loc >= len(d) or d.index[loc] != E or loc < 3: continue
        ref = float(c.iloc[loc - 2]); drop = c.iloc[loc] / ref - 1
        if drop > -0.10: continue
        seg = c.iloc[loc + 1: loc + 11]
        hit = seg[seg > ref]
        left = 10 - len(seg)
        rows.append(dict(code=code, name=nm[code], sec=sec[code], E=E.strftime('%m/%d'), ref=round(ref, 2), drop=round(drop * 100, 1),
                         last=round(float(c.iloc[-1]), 2), last_date=d.index[-1].strftime('%m/%d'),
                         gap=round((c.iloc[-1] / ref - 1) * 100, 1), hit=(hit.index[0].strftime('%m/%d') if len(hit) else ''),
                         left=left, vol20=int(vol20.iloc[-1] / 1000), amt20=round(float((c * v).tail(20).mean() / 1e8), 2),
                         off_hi=round((c.iloc[-1] / c.tail(250).max() - 1) * 100, 1)))
x = pd.DataFrame(rows)
print('事件×個股 筆數', len(x), '| 各事件:', x.groupby('E').size().to_dict())
x.to_csv(sys.argv[1], index=False, encoding='utf-8-sig')
last = x[x.E == x.E.max()] if len(x) else x
liq = last[last.vol20 >= 500]
print('最新事件', last.E.iloc[0], '候選', len(last), '| 均量≥500張', len(liq), '| 已收復', (liq.hit != '').sum(), '| 未收復', (liq.hit == '').sum())

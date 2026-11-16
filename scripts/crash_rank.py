# 對「11/6 事件、已收復、流動性夠」的錯殺候選,用 research_rank 的同一套算分排序(只讀)
import sys, time, pandas as pd, numpy as np
sys.path.insert(0, '.')
import research_rank as rr
x = pd.read_csv(sys.argv[1], dtype={'code': str})
x = x[(x.vol20 >= 500)]
print('候選(均量≥500張):', len(x), '已收復:', (x.hit.notna() & (x.hit != '')).sum())
rev = pd.read_csv(rr.D / 'bulk_fin' / 'rev_all.csv.gz', dtype={'code': str})
q = pd.read_csv(rr.D / 'bulk_fin' / 'fin_q_all.csv.gz', dtype={'code': str})
t0 = time.time(); rows = []
for c in x.code:
    try:
        r = rr._one(c, rev, q)
    except Exception as e:
        r = None
    if r: rows.append(r)
print('scored', len(rows), round(time.time() - t0), 's')
df = pd.DataFrame(rows)
def pct(col, asc=True):
    s = df[col].astype(float); return (s.rank(pct=True, ascending=asc) * 100).fillna(50)
s_rev = (pct('營收YoY3') + pct('加速度')) / 2
s_prof = (pct('毛利率Δ') + pct('營益率')) / 2
s_prof = s_prof.where(~df.get('業外重', False).fillna(False).astype(bool), s_prof * 0.5)
s_chip = (pct('外資天') + pct('大戶4週Δ')) / 2
s_pos = (pct('距年高%') + df['站60MA'].astype(int) * 100) / 2
df['營收分'], df['獲利分'], df['籌碼分'], df['位置分'] = s_rev.round(0), s_prof.round(0), s_chip.round(0), s_pos.round(0)
pen = (df.get('處置', False).fillna(False).astype(bool) * 10 + df.get('爆量窗', False).fillna(False).astype(bool) * 8
       + (pd.to_numeric(df.get('融資%'), errors='coerce').fillna(0) >= 30) * 8 + df.get('迴轉警', False).fillna(False).astype(bool) * 5)
df['扣分'] = pen
df['總分'] = (s_rev * .30 + s_prof * .30 + s_chip * .25 + s_pos * .15 - pen).round(1)
m = df.merge(x[['code', 'sec', 'drop', 'ref', 'gap', 'hit', 'left', 'amt20']], left_on='代碼', right_on='code')
m = m.sort_values('總分', ascending=False)
m.to_csv(sys.argv[2], index=False, encoding='utf-8-sig')
pd.set_option('display.width', 280); pd.set_option('display.max_rows', 200)
cols = ['代碼', '名稱', 'sec', '總分', '營收分', '獲利分', '籌碼分', '位置分', '扣分', 'drop', 'gap', 'hit', '收盤', '距年高%', '營收YoY3', '加速度', '毛利率', '毛利率Δ', '營益率', '業外重', '外資天', '大戶4週Δ', '融資%', 'amt20']
rec = m[m.hit.notna() & (m.hit != '')]
print('=== 已收復 前 40 ==='); print(rec[cols].head(40).to_string(index=False))
nr = m[~(m.hit.notna() & (m.hit != ''))]
print('=== 未收復 前 15 ==='); print(nr[cols].head(15).to_string(index=False))

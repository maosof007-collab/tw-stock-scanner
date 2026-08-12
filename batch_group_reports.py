"""
batch_group_reports.py — 族群批次產業報告(免逐檔 key 代碼)
=================================================================
每個族群:市值最大者當主角、其餘當同業 → 產業比較型報告
→ 存研究文章庫 → git push 上雲(雲端「研究文章」頁可讀)。

執行:
  python batch_group_reports.py                       # 預設 光通訊CPO 封測 晶圓代工(族群比較報告)
  python batch_group_reports.py 散熱 PCB 重電          # 任何 theme_groups.py 定義的族群
  python batch_group_reports.py 光通訊CPO --per-stock  # 族群內每檔:月營收快評+法人六層
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

DEFAULT_GROUPS = ["光通訊CPO", "封測", "晶圓代工"]


def _last_close(code: str) -> float:
    d = Path(__file__).parent / "data"
    for suf in (".TW.csv", ".TWO.csv"):
        p = d / f"{code}{suf}"
        if p.exists():
            try:
                s = pd.read_csv(p, index_col=0, usecols=[0, 4]).iloc[:, 0].dropna()
                return float(s.iloc[-1])
            except Exception:
                pass
    return 0.0


def pick_leader(codes: list[str]) -> str:
    """市值最大者當報告主角(股數×收盤);抓不到就用第一檔。"""
    from fundamentals import shares_map
    sh = shares_map()
    best, best_cap = codes[0], -1.0
    for c in codes:
        cap = sh.get(c, 0) * _last_close(c)
        if cap > best_cap:
            best, best_cap = c, cap
    return best


def run_group(gname: str) -> str:
    from theme_groups import THEME_GROUPS
    from analyst_report import generate_industry_report, save_article, git_publish
    codes = THEME_GROUPS.get(gname)
    if not codes:
        return f"❌ {gname}:theme_groups.py 沒有這個族群(可用:{'/'.join(THEME_GROUPS)})"
    leader = pick_leader(codes)
    peers = [c for c in codes if c != leader]
    print(f"[{gname}] 主角 {leader}(市值最大),同業 {','.join(peers)} — 撰寫中…")
    extra = (f"本篇為『{gname}』族群批次掃描報告(主角=族群內市值最大者,同業=其餘成分股)。"
             f"請以族群視角寫:比較成分股的營收動能與毛利結構差異,點出族群內最強/最弱者及原因。")
    rpt = generate_industry_report(leader, peers, extra=extra)
    if rpt.startswith("（"):
        return f"❌ {gname}:{rpt}"
    fn = save_article(leader, gname, "產業比較", rpt)
    msg = git_publish(fn)
    return f"✅ {gname}:{fn}|{msg}"


def _stock_names() -> dict:
    try:
        sl = pd.read_csv(Path(__file__).parent / "data" / "stock_list.csv",
                         encoding="utf-8-sig", dtype=str)
        return dict(zip(sl["code"], sl["name"]))
    except Exception:
        return {}


def run_per_stock(gname: str) -> list[str]:
    """族群內每檔成分股:月營收快評 + 法人六層,各自發佈。"""
    from theme_groups import THEME_GROUPS
    import analyst_report as ar
    codes = THEME_GROUPS.get(gname)
    if not codes:
        return [f"❌ {gname}:theme_groups.py 沒有這個族群"]
    names = _stock_names()
    out = []
    for i, c in enumerate(codes):
        if i:
            time.sleep(3)
        nm = names.get(c, "")
        for label, gen, mode in (("快評", ar.generate_flash_note, "月營收快評"),
                                 ("六層", ar.generate_report, "法人六層")):
            print(f"[{gname}] {c} {nm} {label} 撰寫中…")
            try:
                rpt = gen(c, extra=f"本篇為『{gname}』族群批次掃描的成分股報告。")
            except Exception as e:
                out.append(f"❌ {c} {nm} {label}:{type(e).__name__} {e}")
                continue
            if rpt.startswith("（"):
                out.append(f"❌ {c} {nm} {label}:{rpt}")
                continue
            fn = ar.save_article(c, nm, mode, rpt)
            msg = ar.git_publish(fn)
            out.append(f"✅ {c} {nm} {label}:{fn}|{msg}")
            print(out[-1])
    return out


if __name__ == "__main__":
    per_stock = "--per-stock" in sys.argv
    groups = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_GROUPS
    for i, g in enumerate(groups):
        if i:
            time.sleep(3)                    # FinMind 限流禮貌間隔
        if per_stock:
            print("\n".join(run_per_stock(g)))
        else:
            print(run_group(g))

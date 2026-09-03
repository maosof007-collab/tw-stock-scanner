"""
deep_report.py — 深度潛力股報告(「邏輯投資·發掘潛力股」風格)
================================================================
風格要素(取自 vocus 邏輯投資專欄的寫法):
  風口式標題(題材×公司) → 開場聲明不推介 → 公司是誰 → 成長引擎(產品線)
  → 財務解剖(矛盾統一:營收 vs 毛利的辯證) → 籌碼結構 → 投資邏輯(情境+兌現訊號)
  → 風險提示。全程數字佐證、由淺入深、不喊買賣。
存檔:data/deep_reports/deep_{code}_{ts}.md(獨立於研究文章庫,自成一頁)。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DEEP_DIR = ROOT / "data" / "deep_reports"


# ────────────────────────────────────────
# 素材組裝(全部來自系統既有管線,不新抓)
# ────────────────────────────────────────
def _bigholder_series(code: str, weeks: int = 8) -> pd.DataFrame:
    """>400張大戶持股比例近 N 週(來自週報 panel 快取)。"""
    try:
        p = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv")
        if code not in p.columns:
            return pd.DataFrame()
        return p[["date", code]].dropna().tail(weeks).rename(columns={code: "大戶%"})
    except Exception:
        return pd.DataFrame()


def _inst_sum(code: str, since: str) -> dict:
    """自 since 日起外資/投信買賣超(張)。"""
    try:
        i = pd.read_csv(ROOT / "data" / "institutional" / f"{code}_inst.csv")
        i = i.sort_values("date")
        i = i[i["date"] >= since]
        return {
            "外資張": round(i["外陸資買賣超股數(不含外資自營商)"].fillna(0).sum() / 1000),
            "投信張": round(i["it_net"].fillna(0).sum() / 1000),
        }
    except Exception:
        return {}


def _price_stats(code: str) -> dict:
    """現價/一年高低/距高(%)。"""
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if not p.exists():
            continue
        try:
            d = pd.read_csv(p, usecols=[0, 4])
            d.columns = ["date", "close"]
            cl = pd.to_numeric(d["close"], errors="coerce")
            d = d.assign(close=cl).dropna().sort_values("date")
            last = d.iloc[-1]
            hi = float(d["close"].tail(252).max())
            lo = float(d["close"].tail(252).min())
            return {"date": str(last["date"]), "close": float(last["close"]),
                    "hi252": hi, "lo252": lo,
                    "off_high": (float(last["close"]) / hi - 1) * 100 if hi else 0.0}
        except Exception:
            return {}
    return {}


def build_deep_context(code: str, extra: str = "") -> dict:
    """報告素材包:月營收/季報/EPS情境/籌碼/法說筆記/產品組合/大戶趨勢。"""
    import analyst_report as ar
    dig = ar.build_digest(code, extra=extra)
    dig["conf"] = ar._conf_extra(code)
    dig["bigholder"] = _bigholder_series(code)
    since = (now_tw() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    dig["inst30"] = _inst_sum(code, since)
    dig["pstats"] = _price_stats(code)
    return dig


# ────────────────────────────────────────
# 生成(Claude 引擎;素材不足處寧留白不編造)
# ────────────────────────────────────────
_SYS_DEEP = """你是台股專欄作家,寫作風格對標 vocus「邏輯投資|發掘潛力股」系列。
輸出即文章本文(markdown),不要 meta 說明、不要「以下是文章」開場白。

【風格鐵律】
1. 標題:發掘潛力股|站在<題材1>、<題材2>…的風口上|<公司名>(<代號>)——題材取自實際產品線。
2. 開場先聲明「本文無推介股票之意圖,僅為個人研究記錄」,再用產業趨勢鉤子切入(由大到小)。
3. 章節:公司是誰 → 成長引擎(產品線逐一講) → 財務解剖 → 籌碼結構 → 投資邏輯 → 風險提示。
4. 財務解剖必用「矛盾統一」辯證:找出看似矛盾的兩個數字(例:營收放緩 vs 毛利率創高),
   用產品組合遷移解釋,這是本風格的靈魂。**矛盾必須真實存在於素材數字中——
   嚴禁為了戲劇性發明矛盾(如素材顯示毛利率上升卻寫成下滑=嚴重錯誤,直接作廢)。**
5. 每個論點配具體數字(百分比/金額/張數/pp),數字全部取自提供素材,嚴禁自創。
6. 投資邏輯給情境(保守/中性/樂觀)與「兌現訊號」(哪個日期看哪個數字),不做預測不喊買賣。
7. 風險提示至少三條,每條要有近例或量化依據。
8. 【誠實鐵律】素材沒有的公司沿革/客戶名/產品細節一律不寫;寧可寫「法說未揭露、待補」。
9. 結尾加一行:*本文由系統資料管線產出,非投資建議。*"""


def generate_deep(code: str, extra: str = "") -> str:
    """產出一篇深度潛力股文章(引擎不可用時回錯誤訊息字串)。"""
    import llm
    ctx = build_deep_context(code, extra)
    parts = [f"公司:{ctx['name']}({code}) {ctx.get('price', '')}"]
    if ctx.get("pstats"):
        s = ctx["pstats"]
        parts.append(f"股價:{s['close']:.1f}({s['date']}),一年區間 {s['lo252']:.1f}~{s['hi252']:.1f},"
                     f"距一年高 {s['off_high']:+.1f}%")
    for key, label in [("monthly", "月營收(近3年)"), ("quarterly", "季報(近4年)"),
                       ("forecast", "系統月營收推估"), ("eps_sc", "EPS情境")]:
        df = ctx.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            parts.append(f"【{label}】\n{df.to_string(index=False)}")
    if isinstance(ctx.get("bigholder"), pd.DataFrame) and not ctx["bigholder"].empty:
        parts.append(f"【大戶>400張持股%(週)】\n{ctx['bigholder'].to_string(index=False)}")
    if ctx.get("inst30"):
        parts.append(f"【近30日法人】{ctx['inst30']}")
    if ctx.get("chips"):
        parts.append(f"【籌碼摘要】{ctx['chips']}")
    if ctx.get("conf"):
        parts.append(ctx["conf"])
    if extra:
        parts.append(f"【使用者補充】{extra}")
    out = llm.generate(_SYS_DEEP, "\n\n".join(parts), max_tokens=4000)
    if not out:
        import llm as _l
        return f"⚠️ 引擎不可用:{_l.fail_reason()}"
    return out


# ────────────────────────────────────────
# 存檔 / 列表 / 讀取 / 上雲
# ────────────────────────────────────────
def save_deep(code: str, name: str, content: str) -> str:
    DEEP_DIR.mkdir(parents=True, exist_ok=True)
    ts = now_tw().strftime("%Y%m%d_%H%M")
    first = next((ln.strip().lstrip("#* ").rstrip("*")
                  for ln in content.splitlines() if ln.strip()), f"{code} 深度報告")
    header = (f"<!--meta\ntitle: {first[:100]}\ncode: {code}\nname: {name}\n"
              f"date: {now_tw():%Y-%m-%d %H:%M}\n-->\n\n")
    p = DEEP_DIR / f"deep_{ts}_{code}.md"
    p.write_text(header + content, encoding="utf-8")
    return p.name


def list_deep() -> list[dict]:
    """[{fname, title, code, name, date}] 新到舊。"""
    out = []
    if not DEEP_DIR.exists():
        return out
    for p in sorted(DEEP_DIR.glob("deep_*.md"), reverse=True):
        meta = {"fname": p.name, "title": p.stem, "code": "", "name": "", "date": ""}
        try:
            head = p.read_text(encoding="utf-8")[:600]
            for k in ("title", "code", "name", "date"):
                m = re.search(rf"^{k}:\s*(.+)$", head, re.M)
                if m:
                    meta[k] = m.group(1).strip()
        except Exception:
            pass
        out.append(meta)
    return out


def read_deep(fname: str) -> str:
    p = DEEP_DIR / fname
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8")
    return re.sub(r"<!--meta.*?-->\s*", "", txt, count=1, flags=re.S)


def git_publish_deep(fname: str) -> str:
    """commit + push(雲端無權限自動略過)。"""
    def run(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=90, encoding="utf-8", errors="replace")
    try:
        rel = f"data/deep_reports/{fname}"
        if run("add", rel).returncode != 0:
            return "git add 失敗(略過)"
        r = run("commit", "-m", f"docs: 深度潛力股 {fname}")
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "nothing to commit" not in out:
            return "git commit 失敗(略過)"
        run("pull", "--rebase")
        pr = run("push")
        return "已上雲" if pr.returncode == 0 else "已 commit(push 待網路)"
    except Exception as e:
        return f"git 略過({e})"

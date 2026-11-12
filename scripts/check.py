"""tw_backtest 守則檢查 — 把 CLAUDE.md 的鐵律變成會失敗的檢查。

用法:python scripts\\check.py
回傳碼 0 = 全過;1 = 有違規。

datetime.now() 這條採「棘輪」:既有的舊用法記在 NOW_BASELINE,只擋新增的;
修掉舊的之後把數字調低(檢查會提示),只能往下不能往上。
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_DIRS = [ROOT, ROOT / "pages", ROOT / "views", ROOT / "strategies", ROOT / "scripts"]

# 雲端(Streamlit Cloud / GitHub Action)跑在 UTC,這些呼叫會差 8 小時 → 用 twtime.now_tw()
_NOW_OWNERS = {"datetime", "date", "dt.datetime", "dt.date",
               "datetime.datetime", "datetime.date", "pd.Timestamp"}
# 2026-11-03 盤點時就存在的舊用法(檔名 → 處數)。只准減少,不准增加
NOW_BASELINE = {
    "analyze_news.py": 2, "auto_refresh.py": 2, "auto_update.py": 3,
    "backtest_news_daytrade_930.py": 1, "confidence_score.py": 1, "data_provider.py": 2,
    "disposal.py": 1, "download_all_tw_stocks.py": 1, "download_tw_stocks.py": 1,
    "news_trend.py": 1, "nova_trade.py": 1, "1_今日選股.py": 1, "6_績效追蹤.py": 5,
    "9_研究報告瀏覽器.py": 1, "portfolio.py": 5, "report_db.py": 1, "scan_signals.py": 4,
}
# public repo:這些檔案絕不能被 git 追蹤
SECRET_PATTERNS = [r"(^|/)config\.json$", r"(^|/)secrets\.toml$", r"credentials", r"\.env$"]

errors: list[str] = []
notes: list[str] = []


def _py_files():
    for d in PY_DIRS:
        if d.exists():
            yield from sorted(d.glob("*.py"))


def _parse(p: Path):
    src = p.read_text(encoding="utf-8-sig")
    try:
        return src, ast.parse(src)
    except SyntaxError as e:
        errors.append(f"[語法] {p.relative_to(ROOT)}:{e.lineno} {e.msg}")
        return src, None


def check_python():
    """語法、datetime.now() 棘輪、Styler.applymap(雲端新版 pandas 已移除)。"""
    for p in _py_files():
        src, tree = _parse(p)
        if tree is None:
            continue
        name = p.name
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "applymap":
                errors.append(f"[pandas] {p.relative_to(ROOT)}:{node.lineno} .applymap 雲端已移除 — 改用 .map")
        if name == "twtime.py":
            continue
        # 帶參數的 datetime.now(TW_TZ) 是對的,只算無參數呼叫
        calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call) and not n.args and not n.keywords}
        now_hits = [n.lineno for n in ast.walk(tree)
                    if isinstance(n, ast.Attribute) and id(n) in calls
                    and n.attr in ("now", "today") and ast.unparse(n.value) in _NOW_OWNERS]
        allowed = NOW_BASELINE.get(name, 0)
        if len(now_hits) > allowed:
            lines = ",".join(map(str, sorted(now_hits)))
            errors.append(f"[時區] {p.relative_to(ROOT)} 第 {lines} 行用了 datetime.now()/date.today()"
                          f"(基準 {allowed} 處)— 改用 twtime.now_tw(),雲端是 UTC 會差 8 小時")
        elif len(now_hits) < allowed:
            notes.append(f"[時區] {name} 已降到 {len(now_hits)} 處,把 NOW_BASELINE 改小鎖住進度")


_KEYISH = re.compile(r"^_(mtime|mt|ver|version|stamp|key|ts|tick|sig)$")


def check_cache_key_underscore():
    """st.cache_data 的參數若以底線開頭,Streamlit 會把它排除在快取鍵外。
    拿 `_mtime` 當「檔案更新就重讀」的鍵=完全無效,快取鎖死到 ttl 到期
    (2026-11-12:斷頭雷達/強勢資金/新面孔雷達 三頁四處,資料更新了畫面還是舊的)。"""
    for p in _py_files():
        _, tree = _parse(p)
        if tree is None:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not any("cache_data" in ast.unparse(d) or "cache_resource" in ast.unparse(d)
                       for d in fn.decorator_list):
                continue
            for a in fn.args.args + fn.args.kwonlyargs:
                ann = ast.unparse(a.annotation) if a.annotation else ""
                if a.arg.startswith("_") and (_KEYISH.match(a.arg) or ann in ("float", "int", "str")):
                    errors.append(f"[快取鍵] {p.relative_to(ROOT)}:{fn.lineno} {fn.name}({a.arg}) "
                                  f"— 底線開頭的參數不會進快取鍵,檔案更新也不會重讀;把底線拿掉")


def check_bat_git_add():
    """bat 的 git add 不可用 glob pathspec:檔案沒產生時整行 fatal,其他 pattern 一起失效。"""
    for p in sorted(ROOT.glob("*.bat")):
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="ignore") if raw.startswith(b"\xef\xbb\xbf") else raw.decode("cp950", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            m = re.search(r"\bgit\s+add\b(.*)", line, re.I)
            if m and re.search(r"[*?]", m.group(1).split(">")[0]):
                errors.append(f"[bat] {p.name}:{i} git add 用了萬用字元 — 改用目錄層級 git add -A <dir>")


def check_gate_order():
    """登入門必須在 st.navigation 之後、nav.run() 之前;放前面會退回 pages/ 舊路由繞過登入。"""
    src = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    line = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = ast.unparse(n.func)
            if f in ("st.navigation", "require_login", "nav.run") and f not in line:
                line[f] = n.lineno
    if "require_login" not in line:
        errors.append("[登入門] app.py 沒有呼叫 require_login()")
    elif not (line.get("st.navigation", 0) < line["require_login"] < line.get("nav.run", 10**9)):
        errors.append(f"[登入門] app.py 的 require_login() 在第 {line['require_login']} 行,"
                      f"必須介於 st.navigation(第 {line.get('st.navigation')} 行)與 nav.run() 之間")


def check_pages_registered():
    """pages/ 每個檔案都要掛進 app.py 的 st.navigation,也要寫進 docs/FEATURE_MAP.md。"""
    app = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    fmap_path = ROOT / "docs" / "FEATURE_MAP.md"
    fmap = fmap_path.read_text(encoding="utf-8-sig") if fmap_path.exists() else ""
    for p in sorted((ROOT / "pages").glob("*.py")):
        stem = p.stem
        url = stem.split("_", 1)[1] if "_" in stem and stem.split("_", 1)[0].isdigit() else stem
        if f'"{p.name}"' not in app:
            errors.append(f"[路由] pages/{p.name} 沒掛進 app.py 的 st.navigation(會變成孤兒頁)")
        if f"`/{url}`" not in fmap:
            errors.append(f"[Feature Map] /{url} 沒寫進 docs/FEATURE_MAP.md")


def check_no_secrets_tracked():
    """public repo:金鑰檔不可被 git 追蹤。"""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        notes.append("[金鑰] 無法執行 git ls-files,略過")
        return
    for f in out.splitlines():
        if f.endswith(".example.json"):
            continue
        if any(re.search(pat, f, re.I) for pat in SECRET_PATTERNS):
            errors.append(f"[金鑰] {f} 被 git 追蹤了 — public repo,立刻 git rm --cached 並換金鑰")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    check_python()
    check_cache_key_underscore()
    check_bat_git_add()
    check_gate_order()
    check_pages_registered()
    check_no_secrets_tracked()
    for n in notes:
        print("  · " + n)
    if errors:
        print("✗ 守則檢查失敗:")
        for e in dict.fromkeys(errors):
            print("  " + e)
        return 1
    print("✓ 守則檢查通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())

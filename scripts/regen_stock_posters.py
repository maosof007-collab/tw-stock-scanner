"""整批重產個股海報(每季財報或每月營收公布後跑一次)。
python -X utf8 scripts/regen_stock_posters.py
會跑下面每一支腳本(共 32 檔個股海報),全部成功後把同代號、日期較舊、而且已經進 git 的舊版刪掉(沒進 git 的不刪),最後重產總覽。
"""
from __future__ import annotations

import collections
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["make_poster_1568.py", "make_poster_2338.py", "make_poster_2436.py", "make_poster_3008.py", "make_poster_3178.py",
           "make_poster_3312.py", "make_poster_4566.py", "make_poster_4906.py", "make_poster_4916.py", "make_poster_6279.py",
           "make_poster_8176.py", "make_posters_cpo1111.py", "make_posters_haven.py", "make_posters_wave1111.py",
           "make_posters_warn1111.py", "make_poster_6271.py"]


def main() -> int:
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8="1")
    ca = ROOT / "_ca_bundle.pem"
    if ca.exists():
        env.update(SSL_CERT_FILE=str(ca), REQUESTS_CA_BUNDLE=str(ca), CURL_CA_BUNDLE=str(ca))
    saved, failed = 0, []
    for f in SCRIPTS:
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", f], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        n = sum(1 for ln in r.stdout.splitlines() if ln.startswith("saved"))
        saved += n
        print(f"{f}: {n} 張" + ("" if r.returncode == 0 else f"  ← 失敗 exit={r.returncode}"))
        if r.returncode:
            failed.append(f)
            print(r.stderr[-600:])
    print(f"共 {saved} 張;失敗 {failed or '無'}")
    if failed:
        print("有腳本失敗,舊版不刪。")
        return 1
    by = collections.defaultdict(list)
    for p in (ROOT / "data" / "papers").glob("*海報_*.html"):
        m = re.match(r"(\d{4})海報_(\d{8})\.html", p.name)
        if m:
            by[m.group(1)].append((m.group(2), p))
    tracked = set(subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "data/papers"], cwd=ROOT, capture_output=True,
                                 text=True, encoding="utf-8").stdout.splitlines())
    removed = 0
    for code, v in by.items():
        v.sort()
        for _, p in v[:-1]:
            if f"data/papers/{p.name}" in tracked:
                p.unlink()
                removed += 1
    sys.path.insert(0, str(ROOT))
    import make_poster_index
    print("刪掉舊版", removed, "張;總覽:", make_poster_index.build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

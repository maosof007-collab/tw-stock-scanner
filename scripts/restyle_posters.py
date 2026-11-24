# -*- coding: utf-8 -*-
"""把 data/papers 裡每一張海報內嵌的 <style>(與排版小程式)換成目前 poster.CSS(只換樣式,內容一個字都不動)。
起因(2026-11-19):海報固定 1180px 切三欄,表格被擠爛——CSS 是產生當下寫死在檔案裡的,改引擎救不到舊檔。
用法:python -X utf8 scripts/restyle_posters.py          (加 --dry 只列出會改哪些)
安全檢查:換完後把標籤拿掉比對文字,和原檔不同就不寫回。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import poster  # noqa: E402

STYLE = re.compile(r"<style>.*?</style>(\s*<script id=\"pk\">.*?</script>)?", re.S)   # 樣式+排版小程式一起換
NEW = STYLE.search(poster.CSS).group(0)
WRAP = re.compile(r'<div class="wrap[^"]*"(?: data-kind="[^"]*")?>')


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", STYLE.sub("", html))).strip()


def main(dry: bool = False) -> None:
    done = skip = same = 0
    for f in sorted((ROOT / "data" / "papers").glob("*海報_*.html")):
        old = f.read_text(encoding="utf-8")
        m = STYLE.search(old)
        if not m or ".bignums" not in m.group(0) or ".card .ct" not in m.group(0):
            skip += 1                      # 不是海報引擎產的(例如報紙版),不碰
            continue
        if m.group(0) == NEW and poster.wrap_open(poster.kind_of(f.name)) in old:
            same += 1
            continue
        new = old[:m.start()] + NEW + old[m.end():]
        new = WRAP.sub(lambda _: poster.wrap_open(poster.kind_of(f.name)), new, count=1)      # 類型=顏色+主角規則
        if text_of(new) != text_of(old):
            print("內容比對不一致,跳過:", f.name)
            skip += 1
            continue
        if not dry:
            f.write_text(new, encoding="utf-8")
        done += 1
    print(f"換樣式 {done} 張|本來就是新版 {same} 張|跳過 {skip} 張" + ("(dry run,沒有寫檔)" if dry else ""))


if __name__ == "__main__":
    main("--dry" in sys.argv)

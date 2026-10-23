# -*- coding: utf-8 -*-
"""
yt_notes.py — YT 影片轉文字檔(含會員影片;供財經報/研究筆記取材)
=================================================================
起因(2026-10-23):「網頁貼 YT 網址→生出文字檔→寫報告;影片要會員,我有會員」。
原理:yt-dlp 讀你本機瀏覽器的登入 cookies(你有會員=它看得到),
     優先抓字幕(免轉錄、秒級);無字幕才需要另接 Whisper(未接)。
cookies 來源優先序:
  1) data/_yt_cookies.txt(瀏覽器擴充「Get cookies.txt LOCALLY」匯出;最穩)
  2) Chrome 登入態 → 3) Edge 登入態(新版瀏覽器加密可能擋,失敗就用 1)
安全鐵律:cookies 檔與轉錄文字都含個人授權內容——data/yt_notes/ 與
  data/_yt_cookies.txt 必須 gitignore,絕不進雲端(朋友共用+版權)。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "yt_notes"
OUT.mkdir(exist_ok=True)
COOKIES = ROOT / "data" / "_yt_cookies.txt"


def _vtt_to_text(vtt: str) -> str:
    """WEBVTT → 純文字:去時間軸/標籤/重複行(自動字幕逐字重疊很多)。"""
    lines, seen = [], None
    for ln in vtt.splitlines():
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if (not ln or "-->" in ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))
                or ln.isdigit()):
            continue
        if ln != seen:
            lines.append(ln)
            seen = ln
    return "\n".join(lines)


def fetch(url: str) -> dict:
    """抓標題+字幕 → data/yt_notes/{id}_{title}.txt。回傳 {ok, path|err, title, source}。"""
    import yt_dlp
    base = {"skip_download": True, "quiet": True, "no_warnings": True,
            "writesubtitles": True, "writeautomaticsub": True,
            "subtitleslangs": ["zh-TW", "zh-Hant", "zh", "zh-CN", "en"],
            "subtitlesformat": "vtt"}
    trials = []
    if COOKIES.exists():
        trials.append({**base, "cookiefile": str(COOKIES)})
    trials.append({**base, "cookiesfrombrowser": ("chrome",)})
    trials.append({**base, "cookiesfrombrowser": ("edge",)})
    trials.append(dict(base))                       # 無 cookies(公開影片)
    last_err = ""
    for opts in trials:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            vid = info.get("id", "video")
            title = re.sub(r'[\\/:*?"<>|]', "_", info.get("title", vid))[:60]
            subs = info.get("subtitles") or {}
            autos = info.get("automatic_captions") or {}
            pick, src = None, ""
            for lang in ("zh-TW", "zh-Hant", "zh", "zh-CN", "en"):
                if lang in subs:
                    pick, src = subs[lang], f"手動字幕({lang})"
                    break
            if pick is None:
                for lang in ("zh-TW", "zh-Hant", "zh", "zh-CN", "en"):
                    if lang in autos:
                        pick, src = autos[lang], f"自動字幕({lang})"
                        break
            if pick is None:
                last_err = "無任何字幕——需要 Whisper 轉錄(未接),或等頻道上字幕"
                continue
            fmt = next((f for f in pick if f.get("ext") == "vtt"), pick[0])
            import urllib.request
            req = urllib.request.Request(fmt["url"], headers={"User-Agent": "Mozilla/5.0"})
            vtt = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
            text = _vtt_to_text(vtt)
            if len(text) < 50:
                last_err = "字幕內容過短"
                continue
            p = OUT / f"{vid}_{title}.txt"
            p.write_text(f"# {info.get('title','')}\n# 頻道:{info.get('uploader','')}"
                         f"|時長:{info.get('duration_string','')}|來源:{src}\n"
                         f"# {url}\n\n{text}", encoding="utf-8")
            return {"ok": True, "path": p, "title": info.get("title", ""),
                    "source": src, "chars": len(text)}
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:150]}"
            continue
    return {"ok": False, "err": last_err}


def list_notes() -> list[Path]:
    return sorted(OUT.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)


if __name__ == "__main__":
    import sys
    r = fetch(sys.argv[1] if len(sys.argv) > 1 else input("URL: "))
    print(r)

"""產生 /verify 用的全站巡檢 JavaScript(網址清單直接從 app.py 的 st.navigation 讀)。

用法:python scripts\\sweep_js.py [頁名 ...] > 輸出貼進 javascript_tool
  不給頁名 = 首頁 + 全部頁;給頁名(例如 斷頭雷達 今日選股)= 只巡這幾頁。
巡檢在同源 iframe 裡依序載入每個網址,背景執行,結果存在 window.__res;
再用 POLL 那行查進度(javascript_tool 單次呼叫約 45 秒就會逾時,不能同步等)。
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def page_urls() -> list[str]:
    """首頁 '' + app.py 裡每個 _p("檔名") 的網址(去掉數字前綴)。"""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8-sig"))
    urls = [""]
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_p" and n.args:
            stem = Path(n.args[0].value).stem
            urls.append(stem.split("_", 1)[1] if stem.split("_", 1)[0].isdigit() else stem)
    return urls


SWEEP = r"""
window.__res = []; window.__done = false;
(async () => {
  for (const u of %s) {
    const f = document.createElement('iframe');
    f.style.cssText = 'width:1400px;height:900px;position:fixed;left:-3000px;top:0';
    document.body.appendChild(f);
    const t0 = Date.now();
    f.src = location.origin + '/' + encodeURI(u);
    let last = -1, stable = 0, txt = '', gated = false;
    while (Date.now() - t0 < 90000) {
      await new Promise(r => setTimeout(r, 1500));
      try {
        const d = f.contentDocument;
        const m = d && d.querySelector('[data-testid="stMain"]');
        txt = m ? m.innerText : '';
        gated = !!(d && d.querySelector('input[type="password"][aria-label="密碼"]'));  // gate.py 的欄位;績效追蹤另有郵件密碼欄
        const busy = d && d.querySelector('[data-testid="stSpinner"], [data-testid="stStatusWidget"] svg');
        if (txt.length > 0 && txt.length === last && !busy) { if (++stable >= 2) break; } else stable = 0;
        last = txt.length;
      } catch (e) {}
    }
    const d = f.contentDocument;
    window.__res.push({
      url: '/' + u, s: Math.round((Date.now() - t0) / 1000), len: txt.length, gated,
      exc: d ? d.querySelectorAll('[data-testid="stException"]').length : -1,
      tb: /Traceback/.test(txt),
    });
    f.remove();
  }
  window.__done = true;
})();
'started ' + %d + ' pages';
"""

POLL = ("JSON.stringify({done: window.__done, n: window.__res.length, "
        "bad: window.__res.filter(r => r.exc || r.tb || r.len < 50 || r.gated), "
        "slow: window.__res.filter(r => r.s >= 30).map(r => r.url + ' ' + r.s + 's')})")


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    urls = page_urls()
    if sys.argv[1:]:
        want = [a.strip("/") for a in sys.argv[1:]]
        missing = [w for w in want if w not in urls]
        if missing:
            sys.exit(f"app.py 裡找不到這些頁:{missing}")
        urls = want
    print("// ① 啟動巡檢(貼進 javascript_tool)")
    print(SWEEP % (json.dumps(urls, ensure_ascii=False), len(urls)))
    print("// ② 每隔一陣子查進度,done=true 才算跑完")
    print(POLL)


if __name__ == "__main__":
    main()

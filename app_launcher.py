"""
app_launcher.py — 桌面視窗 App 啟動器
用內嵌 Python 起 Streamlit（隱藏黑窗），開在原生視窗（pywebview）。
關閉視窗 = 自動關閉 Streamlit。無 WebView 時退回瀏覽器。
啟動：pythonw.exe app_launcher.py
"""
import os
import sys
import time
import socket
import subprocess
import urllib.request
from pathlib import Path

HERE  = Path(__file__).resolve().parent           # app/
PYDIR = HERE.parent / "python"                    # ../python
PYEXE = PYDIR / "python.exe"
APPPY = HERE / "app.py"
TITLE = "台股策略系統"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_health(port: int, timeout: int = 90) -> bool:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


PORT_FILE = HERE / "data" / "_app_port.txt"


def _alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    # 防重複啟動:已有一份在跑 → 直接開視窗/瀏覽器連過去,不再起第二個伺服器搶資料庫
    if PORT_FILE.exists():
        try:
            old = int(PORT_FILE.read_text().strip())
            if _alive(old):
                url = f"http://127.0.0.1:{old}"
                try:
                    import webview
                    webview.create_window(TITLE, url, width=1440, height=900)
                    webview.start()
                except Exception:
                    import webbrowser
                    webbrowser.open(url)
                return
        except Exception:
            pass

    port = _free_port()
    try:
        PORT_FILE.write_text(str(port))
    except Exception:
        pass
    if PYEXE.exists():
        py = str(PYEXE)
    else:                              # pythonw 啟動時,子行程改用同目錄 python.exe
        cand = Path(sys.executable).with_name("python.exe")
        py = str(cand if cand.exists() else sys.executable)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [py, "-m", "streamlit", "run", str(APPPY),
         "--server.port", str(port), "--server.address", "127.0.0.1",
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=str(HERE), creationflags=flags,
    )
    url = f"http://127.0.0.1:{port}"
    _wait_health(port, 90)
    try:
        import webview
        webview.create_window(TITLE, url, width=1440, height=900)
        webview.start()                       # 阻塞直到視窗關閉
    except Exception:
        import webbrowser
        webbrowser.open(url)
        try:
            proc.wait()                       # 無視窗 → 等 streamlit 結束
        except KeyboardInterrupt:
            pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            PORT_FILE.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()

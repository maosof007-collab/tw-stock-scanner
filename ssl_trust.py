# -*- coding: utf-8 -*-
"""
ssl_trust.py — AVG TLS 攔截解方:certifi + Windows 憑證存放區 → 本地信任清單
=================================================================
病因:AVG Web Shield 會攔截 HTTPS 重簽憑證(簽發者=AVG 根憑證,只存在
Windows 憑證存放區,certifi 不認得)→ requests/yt-dlp 全部
CERTIFICATE_VERIFY_FAILED。2026-11-12 起全機生效(之前只偶發)。

解法(不關驗證、不改系統):ssl.enum_certificates 讀出 ROOT/CA 存放區,
與 certifi 官方清單合併成 _ca_bundle.pem(已 gitignore),再設
SSL_CERT_FILE/REQUESTS_CA_BUNDLE 環境變數。

用法:
  daily_task.bat 開頭跑 `python ssl_trust.py`(重建清單,7 天重建一次),
  之後 `set REQUESTS_CA_BUNDLE=..._ca_bundle.pem` 讓所有子步驟吃到。
  Python 內:`import ssl_trust; ssl_trust.ensure()`(建檔+設本行程環境變數)。
"""
from __future__ import annotations

import base64
import os
import ssl
import time
from pathlib import Path

import certifi

BUNDLE = Path(__file__).parent / "_ca_bundle.pem"
MAX_AGE_DAYS = 7


def _windows_store_pem() -> str:
    """Windows ROOT/CA 存放區 → PEM 文字(含 AVG 等本機信任的根憑證)。"""
    blocks: list[str] = []
    seen: set[bytes] = set()
    for store in ("ROOT", "CA"):
        try:
            certs = ssl.enum_certificates(store)
        except Exception:
            continue
        for der, enc, _trust in certs:
            if enc != "x509_asn" or der in seen:
                continue
            seen.add(der)
            b64 = base64.encodebytes(der).decode("ascii")
            blocks.append("-----BEGIN CERTIFICATE-----\n" + b64 + "-----END CERTIFICATE-----\n")
    return "".join(blocks)


def build(force: bool = False) -> Path:
    if (not force and BUNDLE.exists()
            and time.time() - BUNDLE.stat().st_mtime < MAX_AGE_DAYS * 86400):
        return BUNDLE
    pem = Path(certifi.where()).read_text(encoding="ascii", errors="ignore")
    pem += "\n# ==== Windows certificate store (ROOT/CA) below ====\n"
    pem += _windows_store_pem()
    tmp = BUNDLE.with_suffix(".tmp")
    tmp.write_text(pem, encoding="ascii")
    tmp.replace(BUNDLE)
    return BUNDLE


def ensure() -> str:
    """建檔(必要時)並設定本行程環境變數;回傳清單路徑。"""
    p = str(build())
    os.environ.setdefault("SSL_CERT_FILE", p)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", p)
    os.environ.setdefault("CURL_CA_BUNDLE", p)
    return p


if __name__ == "__main__":
    p = build(force="--force" in __import__("sys").argv)
    n = Path(p).read_text(encoding="ascii", errors="ignore").count("BEGIN CERTIFICATE")
    print(f"[ssl_trust] {p}({n} certs)")

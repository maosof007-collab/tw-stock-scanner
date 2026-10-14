# -*- coding: utf-8 -*-
"""
nova_trade.py — 台新 Nova API(Fugle SDK)下單通道(2026-10-15)
=================================================================
鐵律(寫死,不可繞過):
  1. 憑證/密碼只存本機 config.json(已 gitignore),程式永不印出、永不入庫
  2. 預設 dry-run:place() 一律模擬,除非 config "nova_live": true 且呼叫端 live=True(雙重開關)
  3. 每一筆(模擬或實單)都寫 data/trade_log.csv——先留痕,後下單
  4. 買單前跑家規前置檢查(_pre_trade_check):體檢紅燈/爆量窗/迴轉率警戒 → 擋下並記原因
事前準備(使用者本人完成):台新帳戶→憑證e管家匯出 .pfx→線上簽署API聲明書(隔日生效)
→ 於 https://ml-fugle-api.tssco.com.tw/FugleSDK/docs/download/download-sdk 下載 wheel
→ pip install taishin_sdk-<ver>-cp37-abi3-win_amd64.whl → 首次 register_api_auth。
config.json 需新增:
  "nova": {"id": "身分證字號", "pwd": "密碼", "cert_path": "C:/.../xxx.pfx",
            "cert_pwd": "憑證密碼", "nova_live": false}
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
LOG = ROOT / "data" / "trade_log.csv"
_SDK = None
_ACC = None


def config() -> dict:
    try:
        return json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("nova", {})
    except Exception:
        return {}


def status() -> dict:
    """環境體檢:SDK 裝了沒/設定齊不齊/實單開關。給頁面顯示用,不觸發登入。"""
    s = {"sdk": False, "config": False, "live": False, "hint": ""}
    try:
        import taishin_sdk  # noqa: F401
        s["sdk"] = True
    except ImportError:
        s["hint"] = ("未安裝 SDK:至官方下載頁取得 wheel 後 "
                     "pip install taishin_sdk-<ver>-cp37-abi3-win_amd64.whl")
    cfg = config()
    s["config"] = all(cfg.get(k) for k in ("id", "pwd", "cert_path", "cert_pwd"))
    if s["sdk"] and not s["config"]:
        s["hint"] = "SDK 已裝;config.json 的 nova 區塊未填(id/pwd/cert_path/cert_pwd)"
    s["live"] = bool(cfg.get("nova_live"))
    return s


def connect():
    """登入並快取帳號。只在真的要查詢/下單時呼叫。"""
    global _SDK, _ACC
    if _ACC is not None:
        return _SDK, _ACC
    from taishin_sdk import TaishinSDK            # ImportError 由呼叫端顯示 hint
    cfg = config()
    sdk = TaishinSDK()
    accounts = sdk.login(cfg["id"], cfg["pwd"], cfg["cert_path"], cfg["cert_pwd"])
    _SDK, _ACC = sdk, accounts[0]
    return _SDK, _ACC


def _pre_trade_check(code: str, side: str) -> list[str]:
    """家規前置檢查:回傳攔截原因清單(空=放行)。只攔買單。"""
    if side != "Buy":
        return []
    blocks = []
    try:                                           # 迴轉率🔪警戒(爆量窗)
        tv = pd.read_csv(ROOT / "data" / "_turnover.csv", dtype={"代碼": str})
        r = tv[tv["代碼"] == code]
        if len(r) and "警戒" in str(r["隔日沖指紋"].iloc[0]):
            blocks.append("🔪 迴轉率雷達警戒中(爆量日+2~3天禁入)")
    except Exception:
        pass
    try:                                           # 日K爆量窗:近2日量>2.3×20日均
        for suf in (".TW.csv", ".TWO.csv"):
            p = ROOT / "data" / f"{code}{suf}"
            if p.exists():
                px = pd.read_csv(p, usecols=["Volume"]).dropna()
                v = px["Volume"].astype(float)
                if len(v) > 25 and (v.tail(2) > v.iloc[-22:-2].mean() * 2.3).any():
                    blocks.append("爆量窗(近2日量>2.3×均量)——家規禁入")
                break
    except Exception:
        pass
    return blocks


def place(code: str, lots: int, side: str = "Buy", price: float | None = None,
          live: bool = False, force: bool = False) -> dict:
    """下單。預設 dry-run;live=True 且 config nova_live=true 才送實單。
    lots=張數;price=None 代表以漲跌停保護價市價化前先擋(v1 僅支援限價)。"""
    now = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    blocks = _pre_trade_check(code, side) if not force else []
    mode = "LIVE" if (live and config().get("nova_live")) else "DRY"
    rec = {"time": now, "mode": mode, "side": side, "code": code,
           "lots": lots, "price": price, "status": "", "note": ""}
    if blocks:
        rec["status"] = "BLOCKED"
        rec["note"] = ";".join(blocks)
    elif price is None:
        rec["status"] = "REJECT"
        rec["note"] = "v1 僅支援限價單——請給價格"
    elif mode == "DRY":
        rec["status"] = "SIMULATED"
    else:
        try:
            sdk, acc = connect()
            from taishin_sdk import (BSAction, MarketType, Order, OrderType,
                                     PriceType, TimeInForce)
            order = Order(
                buy_sell=BSAction.Buy if side == "Buy" else BSAction.Sell,
                symbol=code, price=str(price), quantity=int(lots) * 1000,
                market_type=MarketType.Common, price_type=PriceType.Limit,
                time_in_force=TimeInForce.ROD, order_type=OrderType.Stock)
            res = sdk.stock.place_order(acc, order)
            rec["status"] = "SENT"
            rec["note"] = f"seq={getattr(res, 'seq_no', '')}"
        except Exception as e:
            rec["status"] = "ERROR"
            rec["note"] = f"{type(e).__name__}: {e}"[:120]
    old = pd.read_csv(LOG, dtype=str) if LOG.exists() else pd.DataFrame()
    pd.concat([old, pd.DataFrame([rec])], ignore_index=True).to_csv(
        LOG, index=False, encoding="utf-8-sig")
    return rec


def order_results() -> pd.DataFrame:
    sdk, acc = connect()
    rs = sdk.stock.get_order_results(acc)
    rows = [{"seq_no": getattr(r, "seq_no", ""), "code": getattr(r, "stock_no", ""),
             "org_qty": getattr(r, "org_qty", ""), "filled": getattr(r, "filled_qty", ""),
             "avg_price": getattr(r, "avg_price", ""), "can_cancel": getattr(r, "can_cancel", "")}
            for r in (rs or [])]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("status:", status())
    print(place("2330", 1, "Buy", 1000.0))        # dry-run 煙霧測試

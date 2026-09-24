"""
cn_link.py — 中國連動雷達(A股龍頭 ↔ 台股受惠對照)
=================================================================
命題:中國同題材龍頭常先行(光通訊=中際旭創先噴、電子布=宏和科技、
矽晶圓=滬硅/中環 ↔ 台勝科)。追蹤 A 股龍頭動能,對照台股是否落後=補漲觀察。
資料:yfinance(A股 .SS/.SZ),快取 data/cn/;對照表 data/cn_pairs.json 可自行增修。
誠實標註:對照是題材映射不是因果;先行≠必然跟漲,只是把「該去查」的名單排出來。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
CN_DIR = ROOT / "data" / "cn"
CN_DIR.mkdir(parents=True, exist_ok=True)
PAIRS_FILE = ROOT / "data" / "cn_pairs.json"

# 種子對照表(寫入 json 後以 json 為準,可自行編修)
_SEED = [
    {"theme": "光通訊/CPO", "cn": [["300308.SZ", "中際旭創"], ["300502.SZ", "新易盛"]],
     "tw": [["3363", "上詮"], ["3163", "波若威"], ["4979", "華星光"], ["4977", "眾達-KY"],
            ["3450", "聯鈞"], ["6442", "光聖"]]},
    {"theme": "電子布/CCL", "cn": [["603256.SS", "宏和科技"], ["600183.SS", "生益科技"],
                                  ["600176.SS", "中國巨石"]],
     "tw": [["1815", "富喬"], ["1802", "台玻"], ["6274", "台燿"], ["6213", "聯茂"],
            ["2383", "台光電"]]},
    {"theme": "矽晶圓", "cn": [["688126.SS", "滬硅產業"], ["002129.SZ", "TCL中環"]],
     "tw": [["3532", "台勝科"], ["6488", "環球晶"], ["6182", "合晶"]]},
    {"theme": "記憶體", "cn": [["603986.SS", "兆易創新"], ["688008.SS", "瀾起科技"]],
     "tw": [["2408", "南亞科"], ["2344", "華邦電"], ["8299", "群聯"]]},
    {"theme": "PCB", "cn": [["002463.SZ", "滬電股份"]],
     "tw": [["2368", "金像電"], ["2316", "楠梓電"], ["3044", "健鼎"]]},
    {"theme": "被動元件", "cn": [["300408.SZ", "三環集團"], ["000636.SZ", "風華高科"]],
     "tw": [["2327", "國巨"], ["2492", "華新科"]]},
    {"theme": "面板", "cn": [["000725.SZ", "京東方"]],
     "tw": [["2409", "友達"], ["3481", "群創"]]},
]


def pairs() -> list[dict]:
    if PAIRS_FILE.exists():
        try:
            return json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    PAIRS_FILE.write_text(json.dumps(_SEED, ensure_ascii=False, indent=1), encoding="utf-8")
    return _SEED


def fetch_cn(period: str = "1y") -> int:
    """更新所有 A 股日K到 data/cn/{ticker}.csv。回傳成功檔數。"""
    import yfinance as yf
    ok = 0
    for p in pairs():
        for tk, _ in p["cn"]:
            try:
                d = yf.Ticker(tk).history(period=period)
                if len(d) > 20:
                    d = d.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
                    d["Date"] = pd.to_datetime(d["Date"]).dt.strftime("%Y-%m-%d")
                    d.to_csv(CN_DIR / f"{tk}.csv", index=False)
                    ok += 1
            except Exception:
                continue
    return ok


def _mom(closes: pd.Series) -> dict:
    c = pd.to_numeric(closes, errors="coerce").dropna()
    if len(c) < 61:
        return {}
    last = float(c.iloc[-1])
    return {"20日%": round((last / float(c.iloc[-21]) - 1) * 100, 1),
            "60日%": round((last / float(c.iloc[-61]) - 1) * 100, 1),
            "距60日高%": round((last / float(c.tail(60).max()) - 1) * 100, 1)}


def _tw_close(code: str) -> pd.Series | None:
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            return pd.read_csv(p, usecols=["Close"])["Close"]
    return None


def cn_series(tk: str) -> pd.DataFrame | None:
    p = CN_DIR / f"{tk}.csv"
    if p.exists():
        return pd.read_csv(p)
    return None


def scan() -> pd.DataFrame:
    """每主題:中國龍頭動能 vs 台股對照動能;判定燈號。存 data/cn/_cn_scan.csv。"""
    rows = []
    for p in pairs():
        cn_moms = []
        for tk, nm in p["cn"]:
            d = cn_series(tk)
            m = _mom(d["Close"]) if d is not None else {}
            if m:
                cn_moms.append(m)
                rows.append({"主題": p["theme"], "市場": "🇨🇳", "代碼": tk, "名稱": nm, **m})
        cn_lead = max((m["20日%"] for m in cn_moms), default=None)
        cn_high = min((abs(m["距60日高%"]) for m in cn_moms), default=None)
        for code, nm in p["tw"]:
            s = _tw_close(code)
            m = _mom(s) if s is not None else {}
            if not m:
                continue
            lamp = ""
            if cn_lead is not None:
                if cn_lead >= 15 and cn_high is not None and cn_high <= 3 \
                        and m["20日%"] <= cn_lead - 10:
                    lamp = "🔥 補漲觀察"
                elif cn_lead <= -10:
                    lamp = "⚠️ 中國退潮"
            rows.append({"主題": p["theme"], "市場": "🇹🇼", "代碼": code, "名稱": nm,
                         **m, "燈號": lamp})
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(CN_DIR / "_cn_scan.csv", index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    print("fetched:", fetch_cn())
    df = scan()
    print(df.to_string(index=False))

# -*- coding: utf-8 -*-
"""
rt_flow.py — 盤中族群資金流(證交所 MIS 即時快照 → 流入/流出推估)
=================================================================
起因(2026-10-28):「我想做一個跟台新即時的平台,即時看族群資金流進流出」。
原理:MIS API 每分鐘快照 → 累積成交量增量 × 成交價 × 1000 = 該分鐘成交金額;
     方向用價格變化判定(漲=流入、跌=流出、平=與昨收比)。
     這是推估,不是逐筆內外盤——但族群層級聚合後排序高度一致(台新同款邏輯)。
資料:免費、上市(tse_)+上櫃(otc_)都走 mis.twse.com.tw;指數 t00/o00。
快照存 data/_rt_flow/YYYYMMDD.csv(gitignore——盤中暫態資料,不進雲端)。
族群對照:theme_groups.THEME_GROUPS(改表即生效)。
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from theme_groups import THEME_GROUPS
from twtime import now_tw

ROOT = Path(__file__).parent
RT_DIR = ROOT / "data" / "_rt_flow"
RT_DIR.mkdir(exist_ok=True)

_HDR = {"User-Agent": "Mozilla/5.0"}
_BATCH = 50          # MIS 單次查詢上限內的安全批量
_NAMES: dict[str, str] = {}   # code -> 名稱(抓一次就記住)
# 跌停鎖死陷阱(2026-10-30 台燿教案):無成交+五檔被清空 → 舊 fallback 退到「昨收」,
# 跌停股顯示 0%、方向判定也被污染 → 記住每檔最後一個真實價,快照斷線時頂上
_LAST_PX: dict[str, float] = {}
_LAST_PX_DATE = ""


# ─────────────────────────── 宇宙與市場別 ───────────────────────────
def _market_map() -> dict[str, str]:
    """code -> tse/otc;來源 stock_list.csv,查不到預設 tse。"""
    try:
        sl = pd.read_csv(ROOT / "data" / "stock_list.csv", dtype={"code": str})
        return {r.code: ("otc" if r.market == "上櫃" else "tse") for r in sl.itertuples()}
    except Exception:
        return {}


def universe() -> pd.DataFrame:
    """族群成分股攤平:code / group / ex。一檔多族群會重複列(聚合時各算各的)。"""
    mk = _market_map()
    rows = [{"code": c, "group": g, "ex": mk.get(c, "tse")}
            for g, codes in THEME_GROUPS.items() for c in codes]
    return pd.DataFrame(rows)


# ─────────────────────────── MIS 快照 ───────────────────────────
def _mis(ex_ch: str) -> list[dict]:
    url = (f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?"
           f"ex_ch={ex_ch}&json=1&delay=0&_={int(time.time()*1000)}")
    req = urllib.request.Request(url, headers=_HDR)
    return json.loads(urllib.request.urlopen(req, timeout=15).read()).get("msgArray", [])


def _num(x) -> float | None:
    try:
        v = float(str(x).replace(",", ""))
        return v if v == v else None   # NaN guard
    except (TypeError, ValueError):
        return None


def indices() -> dict:
    """加權(t00)+櫃買(o00)即時:{名: (最新, 漲跌%)}。"""
    out = {}
    try:
        for r in _mis("tse_t00.tw|otc_o00.tw"):
            z, y = _num(r.get("z")), _num(r.get("y"))
            name = "加權指數" if r.get("c") == "t00" else "櫃買指數"
            if z and y:
                out[name] = (z, (z / y - 1) * 100)
            elif y:
                out[name] = (y, 0.0)
    except Exception:
        pass
    return out


def usdtwd() -> tuple[float, float] | None:
    """USD/TWD 即時(Yahoo):(最新, 對昨收%)。貶=+、升=-。止跌訊號#1 盯這個。"""
    try:
        req = urllib.request.Request(
            "https://query1.finance.yahoo.com/v8/finance/chart/TWD=X?range=1d&interval=5m",
            headers=_HDR)
        m = json.loads(urllib.request.urlopen(req, timeout=10).read())["chart"]["result"][0]["meta"]
        px, y = m["regularMarketPrice"], m.get("chartPreviousClose") or m.get("previousClose")
        return (px, (px / y - 1) * 100) if px and y else None
    except Exception:
        return None


def _seed_last_px() -> None:
    """重啟後從今日既有快照回填 _LAST_PX(排除 price==y 的昨收fallback列)。"""
    f = RT_DIR / f"{now_tw():%Y%m%d}.csv"
    if not f.exists():
        return
    try:
        prev = pd.read_csv(f, dtype={"code": str})
        g = prev[prev["price"] != prev["y"]].groupby("code").tail(1)
        _LAST_PX.update(dict(zip(g["code"], g["price"])))
    except Exception:
        pass


def snap() -> pd.DataFrame:
    """抓整個宇宙一輪快照:ts/code/price/vol(張)/y。無成交價(盤前)的列略過。"""
    global _LAST_PX_DATE
    today = f"{now_tw():%Y%m%d}"
    if _LAST_PX_DATE != today:
        _LAST_PX.clear()
        _LAST_PX_DATE = today
        _seed_last_px()
    uni = universe().drop_duplicates("code")
    rows = []
    ts = f"{now_tw():%H:%M:%S}"
    items = [f"{r.ex}_{r.code}.tw" for r in uni.itertuples()]
    for i in range(0, len(items), _BATCH):
        try:
            for r in _mis("|".join(items[i:i + _BATCH])):
                if r.get("n"):
                    _NAMES[r.get("c", "")] = r["n"]
                v, y = _num(r.get("v")), _num(r.get("y"))
                if v is None:          # 還沒有任何成交 → 無量可算
                    continue
                # MIS 陷阱:z 只在「最近5秒剛好有成交」才有值,其餘回 "-"
                # fallback:最新成交 → 買賣最佳報價中點 → 單邊報價 → 最後真實價 → 昨收
                # (跌停/漲停鎖死時五檔會被清空,退到昨收會把跌停股畫成 0%)
                z = _num(r.get("z"))
                if z is None:
                    a0 = _num(str(r.get("a", "")).split("_")[0])
                    b0 = _num(str(r.get("b", "")).split("_")[0])
                    z = (a0 + b0) / 2 if (a0 and b0) else (a0 or b0)
                if z is not None:
                    _LAST_PX[r["c"]] = z
                else:
                    z = _LAST_PX.get(r["c"]) or y
                if z is None:
                    continue
                rows.append({"ts": ts, "code": r["c"], "price": z, "vol": v, "y": y})
        except Exception:
            continue
        time.sleep(0.25)
    return pd.DataFrame(rows)


def record() -> int:
    """抓一輪並追加到當日檔;回傳寫入筆數。同一分鐘重複呼叫不重寫。"""
    f = RT_DIR / f"{now_tw():%Y%m%d}.csv"
    df = snap()
    if df.empty:
        return 0
    if f.exists():
        try:
            last = pd.read_csv(f, usecols=["ts"]).ts.iloc[-1]
            if str(last)[:5] == df.ts.iloc[0][:5]:   # 同一分鐘 → 跳過
                return 0
        except Exception:
            pass
    df.to_csv(f, mode="a", header=not f.exists(), index=False, encoding="utf-8-sig")
    return len(df)


# ─────────────────────────── 流向計算 ───────────────────────────
def load_day(date: str | None = None) -> pd.DataFrame:
    """讀當日(或指定 YYYYMMDD)快照;沒有就找最近一天。"""
    f = RT_DIR / f"{date or f'{now_tw():%Y%m%d}'}.csv"
    if not f.exists():
        files = sorted(RT_DIR.glob("2*.csv"))
        if not files:
            return pd.DataFrame()
        f = files[-1]
    df = pd.read_csv(f, dtype={"code": str})
    df.attrs["date"] = f.stem
    return df


def stock_flows(day: pd.DataFrame) -> pd.DataFrame:
    """快照 → 每檔每分鐘資金流(萬元):漲=+、跌=-、平=與昨收比。"""
    if day.empty:
        return pd.DataFrame()
    day = day.sort_values(["code", "ts"]).copy()
    day["sec"] = pd.to_timedelta(day["ts"]).dt.total_seconds()
    g = day.groupby("code")
    day["dv"] = g["vol"].diff().fillna(day["vol"]).clip(lower=0)      # 首筆=開盤以來累積
    day["dp"] = g["price"].diff()
    # 方向:正常一分鐘增量看 tick;首筆或補抓(間隔>90秒,增量橫跨多分鐘)看對昨收
    # ——否則漏抓後追回的大增量會被單一 tick 整包誤判(2026-10-28 南亞科教案)
    catchup = g["sec"].diff().isna() | (g["sec"].diff() > 90)
    sgn = np.sign(day["dp"].fillna(0))
    tie = np.sign((day["price"] - day["y"]).fillna(0))
    day["dir"] = np.where(catchup, tie, np.where(sgn != 0, sgn, tie))
    day["amt"] = day["dv"] * day["price"] * 1000 / 1e4                # 萬元
    day["flow"] = day["amt"] * day["dir"]
    return day


def group_flows(day: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """回傳 (族群總表, 族群分時累積)。金額單位:億元。"""
    sf = stock_flows(day)
    if sf.empty:
        return pd.DataFrame(), pd.DataFrame()
    m = sf.merge(universe(), on="code")                    # 一檔多族群 → 各族群都計
    per_ts = (m.groupby(["group", "ts"])
               .agg(flow=("flow", "sum"), amt=("amt", "sum")).reset_index())
    per_ts["累積淨流"] = per_ts.groupby("group")["flow"].cumsum() / 1e4   # 億
    last = sf.sort_values("ts").groupby("code").tail(1).copy()
    last["pct"] = (last["price"] / last["y"] - 1) * 100
    pm = last.merge(universe(), on="code")
    tot = (m.groupby("group").agg(淨流入=("flow", "sum"), 總成交=("amt", "sum"))
            .div(1e4).join(pm.groupby("group")["pct"].median().rename("漲跌%"))
            .sort_values("淨流入", ascending=False).reset_index())
    # Δ1分:最後一輪快照的淨流(億)——「跟前一分鐘比」的方向箭頭用
    last_ts = per_ts["ts"].max()
    d1 = per_ts[per_ts["ts"] == last_ts].set_index("group")["flow"] / 1e4
    tot["Δ1分"] = d1.reindex(tot["group"]).fillna(0).values
    return tot, per_ts


def all_stocks(day: pd.DataFrame) -> pd.DataFrame:
    """全宇宙個股聚合(產業全景 treemap / 個股貢獻排行用)。
    一檔多族群時取第一個族群(treemap 不能重複計面積)。金額單位:萬元。"""
    sf = stock_flows(day)
    if sf.empty:
        return pd.DataFrame()
    agg = sf.groupby("code").agg(淨流入=("flow", "sum"), 成交額=("amt", "sum"))
    last = sf.sort_values("ts").groupby("code").tail(1).set_index("code")
    out = agg.join(last[["price", "y"]])
    out["漲跌%"] = (out["price"] / out["y"] - 1) * 100
    # Δ1分:最後一輪快照這一分鐘的淨流(萬元)——頁面畫「比前一分鐘」箭頭
    last_ts = sf["ts"].max()
    d1 = sf[sf["ts"] == last_ts].groupby("code")["flow"].sum()
    out["Δ1分"] = d1.reindex(out.index).fillna(0)
    grp = universe().drop_duplicates("code").set_index("code")["group"]
    out["族群"] = grp.reindex(out.index)
    try:
        from symbols import resolve
        out["名稱"] = [_NAMES.get(c) or (resolve(c)[1] or c) for c in out.index]
    except Exception:
        out["名稱"] = [_NAMES.get(c, c) for c in out.index]
    return (out.reset_index()[["code", "名稱", "族群", "price", "漲跌%", "成交額", "淨流入",
                               "Δ1分"]]
              .rename(columns={"code": "代號", "price": "最新"}))


def stock_table(day: pd.DataFrame, group: str) -> pd.DataFrame:
    """單一族群的個股明細(最新價/漲跌%/成交額/淨流入,萬→億顯示在頁面處理)。"""
    sf = stock_flows(day)
    if sf.empty:
        return pd.DataFrame()
    codes = THEME_GROUPS.get(group, [])
    sub = sf[sf["code"].isin(codes)]
    agg = sub.groupby("code").agg(淨流入=("flow", "sum"), 成交額=("amt", "sum"))
    last = sub.sort_values("ts").groupby("code").tail(1).set_index("code")
    out = agg.join(last[["price", "y", "vol"]])
    out["漲跌%"] = (out["price"] / out["y"] - 1) * 100
    try:
        from symbols import resolve
        out["名稱"] = [_NAMES.get(c) or (resolve(c)[1] or c) for c in out.index]
    except Exception:
        out["名稱"] = [_NAMES.get(c, c) for c in out.index]
    return (out.reset_index()[["code", "名稱", "price", "漲跌%", "成交額", "淨流入", "vol"]]
              .rename(columns={"code": "代號", "price": "最新", "vol": "張數"})
              .sort_values("淨流入", ascending=False))


# ─────────────────────────── 盤中強勢股(當沖觀察池) ───────────────────────────
# 量能時段曲線:台股 U 型(開盤重、午間輕、尾盤重)的粗估累積比例——量比用,推估值
_VC_MIN = [0, 15, 30, 60, 120, 180, 240, 270]
_VC_CUM = [.02, .14, .20, .30, .45, .60, .80, 1.0]

_AVG5: dict[str, float | None] = {}   # code -> 近5日均量(張);當日不變,抓一次


def _avg5_vol(code: str) -> float | None:
    if code in _AVG5:
        return _AVG5[code]
    v = None
    for suf in (".TW.csv", ".TWO.csv"):
        p = ROOT / "data" / f"{code}{suf}"
        if p.exists():
            try:
                s = pd.read_csv(p, usecols=["Volume"]).Volume.astype(float)
                s = s[s > 0].tail(5)
                v = float(s.mean()) / 1000 if len(s) else None   # 股 → 張
            except Exception:
                v = None
            break
    _AVG5[code] = v
    return v


def strong_stocks(day: pd.DataFrame, min_amt: float = 3000) -> pd.DataFrame:
    """盤中強勢股體檢:漲幅/量比/買氣/位置 四維合成分(0~100)。
    量比=今日累積張 ÷(5日均量×時段曲線);買氣=淨流入/成交額(-1~1)。
    min_amt:今日累積成交額門檻(萬元)——流動性不足不進池(當沖滑價殺人)。
    僅供觀察:家內回測(news_daytrade)唯一正期望組是「跳空1~3%」,>3% 追高無肉。"""
    sf = stock_flows(day)
    if sf.empty:
        return pd.DataFrame()
    sf = sf.copy()
    sf["pv"] = sf["dv"] * sf["price"]
    agg = sf.groupby("code").agg(淨流=("flow", "sum"), 額=("amt", "sum"),
                                 日高=("price", "max"), Σdv=("dv", "sum"), Σpv=("pv", "sum"))
    last = sf.sort_values("ts").groupby("code").tail(1).set_index("code")
    t = agg.join(last[["price", "y", "vol", "ts"]])
    t["漲%"] = (t["price"] / t["y"] - 1) * 100
    t["均價"] = np.where(t["Σdv"] > 0, t["Σpv"] / t["Σdv"], t["price"])
    t["站均價"] = t["price"] >= t["均價"]
    t["距日高%"] = (t["price"] / t["日高"] - 1) * 100
    # 量比:經過時間用最後快照的時刻
    mins = (pd.to_timedelta(t["ts"]).dt.total_seconds() - 9 * 3600) / 60
    frac = np.interp(mins.clip(1, 270), _VC_MIN, _VC_CUM)
    av5 = pd.Series({c: _avg5_vol(c) for c in t.index}, dtype=float)
    t["量比"] = t["vol"] / (av5 * frac)
    t["買氣"] = np.where(t["額"] > 0, t["淨流"] / t["額"], 0)
    # 池門檻:上漲 + 流動性
    t = t[(t["漲%"] > 0) & (t["額"] >= min_amt)]
    if t.empty:
        return pd.DataFrame()

    def r(col):
        return (t[col].rank(pct=True) * 100).fillna(50)
    t["強勢分"] = (r("漲%") * .35 + r("量比") * .25 + r("買氣") * .20
                 + t["站均價"].astype(int) * 10
                 + (t["距日高%"] >= -1.0).astype(int) * 10).round(1)
    grp = universe().drop_duplicates("code").set_index("code")["group"]
    t["族群"] = grp.reindex(t.index)
    try:
        from symbols import resolve
        t["名稱"] = [_NAMES.get(c) or (resolve(c)[1] or c) for c in t.index]
    except Exception:
        t["名稱"] = [_NAMES.get(c, c) for c in t.index]
    out = (t.reset_index()[["code", "名稱", "族群", "price", "漲%", "量比", "買氣",
                            "站均價", "距日高%", "淨流", "額", "強勢分"]]
             .rename(columns={"code": "代號", "price": "最新"})
             .sort_values("強勢分", ascending=False))
    return out


def strong_alert(ss: pd.DataFrame, topn: int = 12, need: int = 10) -> list[str]:
    """強勢池「駐留提醒」:同一檔在 Top{topn} 累積出現 ≥need 次(≈分鐘)→ LINE 一次/日。
    起因(2026-10-29):「我沒選到的股,如果一直選到,是否能提醒」——瞬間上榜可能是雜訊,
    賴著不走才值得抬頭看。狀態存 _rt_flow/_strong_hits_YYYYMMDD.json(與快照同生命週期)。"""
    if ss is None or len(ss) == 0:
        return []
    f = RT_DIR / f"_strong_hits_{now_tw():%Y%m%d}.json"
    try:
        state = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        state = {}
    hits: dict = state.get("hits", {})
    sent: list = state.get("sent", [])
    top = ss.head(topn)
    for c in top["代號"]:
        hits[str(c)] = hits.get(str(c), 0) + 1
    out = []
    for _, r in top.iterrows():
        c = str(r["代號"])
        if hits[c] >= need and c not in sent:
            out.append(
                f"🎯 強勢池駐留|{r['名稱']} {c}({r['族群']})\n"
                f"在 Top{topn} 已待 {hits[c]} 分鐘\n"
                f"現價 {r['最新']:.1f}({r['漲%']:+.1f}%)量比 {r['量比']:.1f}、買氣 {r['買氣']:+.2f}\n"
                f"{'站均價上' if r['站均價'] else '均價線下'}、距日高 {r['距日高%']:+.1f}%\n"
                f"⚠ 觀察非買單;開盤跳空>3%追高無肉(家內回測)")
            sent.append(c)
    try:
        f.write_text(json.dumps({"hits": hits, "sent": sent}), encoding="utf-8")
    except Exception:
        pass
    if out:
        try:
            import line_push
            if line_push.enabled():
                for m in out:
                    line_push.push_text(m)
        except Exception:
            pass
    return out


if __name__ == "__main__":
    print("指數:", indices())
    n = record()
    print(f"快照寫入 {n} 檔")
    tot, _ = group_flows(load_day())
    print(tot.head(10).to_string(index=False) if len(tot) else "尚無盤中資料")
    ss = strong_stocks(load_day())
    if len(ss):
        print("\n=== 盤中強勢股 Top10 ===")
        print(ss.head(10).to_string(index=False))

"""國家政策重點產業:族群名單與三個檢定(海報 make_poster_policy.py 用)。

  event_table()  過去的政策宣布後 6/12/24 個月,對應族群中位數報酬 vs 大盤、營收有沒有跟上
  now_table()    現在各政策族群:近三個月營收年增、10 月營收是否創 12 個月新高、10/6 以來 vs 大盤、站上年線比例
  king_table()   各族群營收最大的那一家(龍頭)是誰、占多少、營收與股價
族群名單三種來源:系統 theme_groups、官方產業別(data/stock_list.csv 的 sector)、手挑。
手挑與抄自其他海報的代號全部寫在 EXPECT,名稱和 stock_list 對不上就報錯(代號必先查證)。
CLI:python -X utf8 policy_groups.py
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

import bear_sector as B
from theme_groups import THEME_GROUPS

PEAK = "2026-10-06"          # 加權指數這一波高點
PREV_LOW = "2025-04-09"      # 上一次落底日

# 手挑/抄來的代號 → 預期名稱
EXPECT = {
    # 國防軍工(系統軍工組 4 檔+台船、全訊;同 bear_sector.DEFENSE)
    "2634": "漢翔", "8033": "雷虎", "2630": "亞航", "6753": "龍德造船", "2208": "台船", "5222": "全訊",
    # 無人機(手挑)
    "5371": "中光電", "7402": "邑錡",
    # 重電(系統重電組 4 檔+亞力、大同)
    "1503": "士電", "1504": "東元", "1513": "中興電", "1519": "華城", "1514": "亞力", "2371": "大同",
    # 離岸風電(手挑)
    "9958": "世紀鋼", "3708": "上緯投控", "1589": "永冠-KY", "6806": "森崴能源",
    # 機器人(系統機器人組 4 檔+達明、盟立)
    "2049": "上銀", "1590": "亞德客-KY", "2359": "所羅門", "1597": "直得", "4585": "達明", "2464": "盟立",
    # 公共工程營造(手挑)
    "9933": "中鼎", "2535": "達欣工", "5521": "工信", "2546": "根基", "2543": "皇昌", "5511": "德昌",
    # 資安(抄自 make_poster_sec.py 的核心名單)
    "7765": "中華資安", "6690": "安碁資訊", "8272": "全景軟體", "3564": "其陽", "6416": "瑞祺電通", "6245": "立端",
    "3029": "零壹", "6112": "邁達特", "6163": "華電網", "6214": "精誠", "2480": "敦陽科",
    # 低軌衛星(抄自 make_poster_leo.py)
    "3491": "昇達科", "7717": "萊德光電-KY", "3105": "穩懋", "4916": "事欣科", "6134": "萬旭", "6271": "同欣電", "3178": "公準",
    "6426": "統新", "8086": "宏捷科", "2313": "華通", "2367": "燿華", "2383": "台光電", "2355": "敬鵬", "6285": "啟碁",
    "5243": "乙盛-KY", "6928": "攸泰科技", "1582": "信錦", "3138": "耀登", "6190": "萬泰科", "5457": "宣德", "2332": "友訊",
    "2312": "金寶", "2314": "台揚",
}

DEFENSE = ["2634", "8033", "2630", "6753", "2208", "5222"]
DRONE = ["8033", "5371", "7402"]
POWER = ["1503", "1504", "1513", "1519", "1514", "2371"]
WIND = ["9958", "3708", "1589", "6806"]
ROBOT = ["2049", "1590", "2359", "1597", "4585", "2464"]
BUILD = ["9933", "2535", "5521", "2546", "2543", "5511"]
SEC = ["7765", "6690", "8272", "3564", "6416", "6245", "3029", "6112", "6163", "6214", "2480"]
LEO = ["3491", "7717", "3105", "4916", "6134", "6271", "3178", "6426", "5222", "8086", "2313", "2367", "2383", "2355", "6285",
       "5243", "6928", "1582", "3138", "6190", "5457", "2332", "2312", "2314"]

# 族群 → (來源說明, 代號清單或官方產業別, 對應的政策)
SPEC = {
    "國防軍工": ("手挑 6 檔", DEFENSE, "國防預算、國機國造、國艦國造"),
    "無人機": ("手挑 3 檔", DRONE, "無人機條例 6 年 2,400 億"),
    "重電": ("系統重電組+亞力、大同", POWER, "強韌電網 10 年 5,645 億"),
    "電線電纜": ("官方產業別", "電器電纜", "強韌電網"),
    "離岸風電": ("手挑 4 檔", WIND, "離岸風電區塊開發"),
    "綠能環保": ("官方產業別", "綠能環保", "再生能源、淨零"),
    "機器人": ("系統機器人組+達明、盟立", ROBOT, "智慧機器人 4 年 200 億"),
    "AI算力資服": ("系統 AIDC 基建資服組", [str(c) for c in THEME_GROUPS["AIDC基建資服"]], "主權 AI 及算力、AI 新十大建設"),
    "矽光子光通訊": ("系統光通訊 CPO 組", [str(c) for c in THEME_GROUPS["光通訊CPO"]], "AI 新十大建設關鍵技術"),
    "資安": ("資安海報核心名單", SEC, "五大信賴產業(安控)"),
    "低軌衛星": ("低軌衛星海報名單", LEO, "低軌通訊衛星計畫、次世代通訊"),
    "公共工程營造": ("手挑 6 檔", BUILD, "公共建設 7,288 億、治水 591 億"),
    "建材營造": ("官方產業別", "建材營造業", "公共建設(多數是建商,不是承攬工程的)"),
    "水泥": ("官方產業別", "水泥工業", "公共建設"),
    "食品": ("官方產業別", "食品工業", "普發現金、兒少津貼(錢進民眾口袋)"),
    "貿易百貨": ("官方產業別", "貿易百貨業", "普發現金、兒少津貼"),
    "觀光餐旅": ("官方產業別", "觀光餐旅", "普發現金、兒少津貼"),
    "生技醫療": ("官方產業別", "生技醫療業", "健康台灣深耕計畫"),
}
ORDER = list(SPEC)

# 過去的政策宣布:(名稱, 宣布日, 族群, 說明)
EVENTS = [
    ("國機國造+國艦國造", "2017-02-07", "國防軍工", "2017/2/7 高教機簽約啟動;3/21 潛艦國造簽署"),
    ("離岸風電遴選", "2018-04-30", "離岸風電", "2018/4/30 經濟部公布遴選結果(日期未經本次查證)"),
    ("無人機國家隊", "2022-08-13", "無人機", "2022/8/13 嘉義亞創中心揭牌,宣告成立"),
    ("強韌電網", "2022-08-19", "重電", "2022/8/19 行政院核定,10 年 5,645 億"),
    ("強韌電網(電線電纜)", "2022-08-19", "電線電纜", "同上"),
]
HORIZONS = (6, 12, 24)


@lru_cache(maxsize=1)
def groups() -> dict:
    sl = B.stock_list()
    nm = dict(zip(sl["code"], sl["name"]))
    bad = [f"{c} 應為 {n},名單上是 {nm.get(c)}" for c, n in EXPECT.items() if nm.get(c) != n]
    if bad:
        raise ValueError("手挑名單代號與 stock_list 名稱不符:" + ";".join(bad))
    out = {}
    for g, (_, src, _) in SPEC.items():
        codes = sorted(sl[sl["sector"] == src]["code"]) if isinstance(src, str) else list(src)
        miss = [c for c in codes if c not in nm]
        if miss:
            raise ValueError(f"{g} 名單裡有 stock_list 沒有的代號:{miss}")
        out[g] = codes
    return out


def _r3() -> pd.DataFrame:
    """每檔近 3 個月營收合計(月 × 代號)。"""
    return B._rev().rolling(3).sum()


def _yoy3() -> pd.DataFrame:
    r3 = _r3()
    return r3 / r3.shift(12) - 1


# ------------------------------------------------------------------ 3. 現在
def member_now() -> pd.DataFrame:
    tw = B.twii()
    last = tw.index[-1]
    r3, y3 = _r3(), _yoy3()
    rows = []
    for g, codes in groups().items():
        for c in codes:
            p = B.px(c)
            has = len(p) > 0 and p.index[-1] >= last - pd.Timedelta(days=10)
            ma = p.rolling(240).mean()
            col = r3[c] if c in r3.columns else pd.Series(dtype=float)
            rows.append(dict(族群=g, 代號=c, 名稱=B.name(c), 有股價=bool(has),
                             這次=B._ret(p, PEAK, last) if has else np.nan,
                             上一波=B._ret(p, PREV_LOW, PEAK) if has else np.nan,
                             站上年線=(bool(p.iloc[-1] > ma.iloc[-1]) if has and len(p) > 240 else np.nan),
                             營收年增=float(y3[c].iloc[-1]) if c in y3.columns else np.nan,
                             營收創高=(bool(col.iloc[-1] >= col.iloc[-12:].max()) if len(col.dropna()) >= 12 and col.iloc[-1] == col.iloc[-1] else np.nan),
                             近12月營收=float(B._rev()[c].iloc[-12:].sum(min_count=12)) if c in y3.columns else np.nan))
    return pd.DataFrame(rows)


def index_now() -> dict:
    tw = B.twii()
    return dict(這次=B._ret(tw, PEAK, tw.index[-1]), 上一波=B._ret(tw, PREV_LOW, PEAK), 日期=tw.index[-1].date(),
                營收月=str(B._rev().index[-1]))


def now_table(m: pd.DataFrame | None = None) -> pd.DataFrame:
    m = member_now() if m is None else m
    ix = index_now()
    rows = []
    for g in ORDER:
        d = m[m["族群"] == g]
        dp = d[d["有股價"]]
        rows.append(dict(族群=g, 名單檔數=len(d), 有股價=len(dp), 營收年增=d["營收年增"].median(),
                         營收正成長=float((d["營收年增"].dropna() > 0).mean()) if d["營收年增"].notna().any() else np.nan,
                         營收創高=float(d["營收創高"].dropna().astype(float).mean()) if d["營收創高"].notna().any() else np.nan,
                         這次=dp["這次"].median(), 差大盤=dp["這次"].median() - ix["這次"], 上一波=dp["上一波"].median(),
                         站上年線=float(dp["站上年線"].dropna().astype(float).mean()) if dp["站上年線"].notna().any() else np.nan))
    return pd.DataFrame(rows).set_index("族群")


# ------------------------------------------------------------------ 4. 龍頭
def king_table(m: pd.DataFrame | None = None) -> pd.DataFrame:
    m = member_now() if m is None else m
    rows = []
    for g in ORDER:
        d = m[(m["族群"] == g) & m["近12月營收"].notna()].sort_values("近12月營收", ascending=False)
        if d.empty:
            continue
        k = d.iloc[0]
        tot = d["近12月營收"].sum()
        second = d.iloc[1] if len(d) > 1 else None
        rows.append(dict(族群=g, 龍頭=f"{k['名稱']} {k['代號']}", 占比=k["近12月營收"] / tot, 近12月營收億=k["近12月營收"] / 1e5,
                         龍頭營收年增=k["營收年增"], 同業營收年增=d["營收年增"].iloc[1:].median() if len(d) > 1 else np.nan,
                         龍頭這次=k["這次"], 同業這次=d["這次"].iloc[1:].median() if len(d) > 1 else np.nan,
                         龍頭站上年線=k["站上年線"], 第二大=(f"{second['名稱']} {second['代號']}" if second is not None else "—"),
                         第二大占比=(second["近12月營收"] / tot if second is not None else np.nan), 檔數=len(d)))
    return pd.DataFrame(rows).set_index("族群")


# ------------------------------------------------------------------ 2. 過去的政策宣布
def event_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    """回傳 (族群彙總, 個股明細)。報酬=宣布日前最後一筆收盤 → N 個月後;營收年增=近 3 個月合計對去年同期。"""
    tw = B.twii()
    y3 = _yoy3()
    g = groups()
    rows, det = [], []
    for name, d0, grp, why in EVENTS:
        d0 = pd.Timestamp(d0)
        pre = d0 - pd.DateOffset(months=6)
        rec = {}
        for c in g[grp]:
            p = B.px(c)
            r = dict(事件=name, 代號=c, 名稱=B.name(c), 前6月=B._ret(p, pre, d0))
            for h in HORIZONS:
                r[f"後{h}月"] = B._ret(p, d0, d0 + pd.DateOffset(months=h))
            for h in (0, 12, 24):
                ym = f"{(d0 + pd.DateOffset(months=h)):%Y-%m}"
                r[f"營收年增{h}"] = float(y3.loc[ym, c]) if (ym in y3.index and c in y3.columns) else np.nan
            if r["後6月"] == r["後6月"]:
                det.append(r)
        dd = pd.DataFrame([x for x in det if x["事件"] == name])
        rec.update(事件=name, 宣布日=d0.date(), 族群=grp, 說明=why, 檔數=len(dd), 前6月=dd["前6月"].median() if len(dd) else np.nan,
                   大盤前6月=B._ret(tw, pre, d0))
        for h in HORIZONS:
            end = d0 + pd.DateOffset(months=h)
            rec[f"後{h}月"] = dd[f"後{h}月"].median() if len(dd) else np.nan
            rec[f"大盤後{h}月"] = B._ret(tw, d0, end)
            rec[f"差{h}"] = rec[f"後{h}月"] - rec[f"大盤後{h}月"]
            rec[f"贏大盤{h}"] = float((dd[f"後{h}月"].dropna() > rec[f"大盤後{h}月"]).mean()) if len(dd) else np.nan
        if len(dd):
            # 分段:0–6、6–12、12–24 個月各自漲多少(每檔自己算再取中位數)
            rec["段0_6"] = dd["後6月"].median()
            rec["段6_12"] = ((1 + dd["後12月"]) / (1 + dd["後6月"]) - 1).median()
            rec["段12_24"] = ((1 + dd["後24月"]) / (1 + dd["後12月"]) - 1).median()
        for h in (0, 12, 24):
            rec[f"營收年增{h}"] = dd[f"營收年增{h}"].median() if len(dd) and dd[f"營收年增{h}"].notna().any() else np.nan
        rows.append(rec)
    return pd.DataFrame(rows).set_index("事件"), pd.DataFrame(det)


if __name__ == "__main__":
    pd.set_option("display.width", 280)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.max_rows", 400)
    print({k: len(v) for k, v in groups().items()})
    print(index_now())
    m = member_now()
    print(now_table(m).round(3).to_string())
    print(king_table(m).round(3).to_string())
    e, d = event_table()
    print(e.drop(columns=["說明"]).round(3).T.to_string())
    print(d.round(3).to_string())

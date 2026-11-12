"""
corp_actions.py — 公司行為雷達(股票分割/面額變更/減資 公告掃描)
=================================================================
「提前布局」的合法時點=MOPS 公告日。每日全市場重大訊息掃關鍵字,
記錄到 data/corp_actions_log.csv(公告日→之後自己排最後交易日/恢復買賣日曆)。
案例統計(2025-2026 分割恢復買賣,系統價格資料實測):
  預跑低+比例大(≥1拆4)=恢復後大漲;預跑>100%=利多出盡風險。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent
LOG = ROOT / "data" / "corp_actions_log.csv"
_HDR = {"User-Agent": "Mozilla/5.0"}
KEYWORDS = ["股票分割", "面額", "減資", "股份分割"]


def fetch_market_announcements() -> pd.DataFrame:
    """今日全市場重大訊息(上市必有;上櫃端點不穩,失敗容忍)。"""
    frames = []
    try:
        r = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap04_L",
                         timeout=30, headers=_HDR)
        df = pd.DataFrame(r.json())
        df.columns = [c.strip() for c in df.columns]        # 各表先各自 strip 再併,防撞名
        df["market"] = "上市"
        frames.append(df)
    except Exception:
        pass
    for url in ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O",
                "https://www.tpex.org.tw/openapi/v1/t187ap04_O"):
        try:
            r = requests.get(url, timeout=30, headers=_HDR)
            j = r.json()
            if isinstance(j, list) and j:
                df = pd.DataFrame(j)
                df.columns = [c.strip() for c in df.columns]
                # TPEX 用英文欄名 → 統一成上市欄名
                df = df.rename(columns={"SecuritiesCompanyCode": "公司代號",
                                        "CompanyName": "公司名稱"})
                df["market"] = "上櫃"
                frames.append(df)
                break
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.loc[:, ~out.columns.duplicated()]
    return out


def scan_and_log() -> pd.DataFrame:
    """掃關鍵字 → 去重寫入 log。回傳今日新命中。"""
    df = fetch_market_announcements()
    if df.empty:
        return df
    subj_col = next((c for c in df.columns if "主旨" in c), None)
    if subj_col is None:
        return pd.DataFrame()
    hit = df[df[subj_col].astype(str).str.contains("|".join(KEYWORDS), na=False)].copy()
    if hit.empty:
        return hit
    keep = {}
    for c in ("發言日期", "公司代號", "公司名稱", subj_col, "market"):
        if c in hit.columns:
            keep[c] = c
    hit = hit[list(keep)].rename(columns={subj_col: "主旨"})
    hit["主旨"] = hit["主旨"].astype(str).str.replace("\r", "").str.replace("\n", " ").str[:120]
    old = pd.DataFrame()
    if LOG.exists():
        old = pd.read_csv(LOG, dtype=str)
    merged = pd.concat([old, hit.astype(str)], ignore_index=True)
    merged = merged.drop_duplicates(subset=[c for c in ("發言日期", "公司代號", "主旨")
                                            if c in merged.columns])
    merged.to_csv(LOG, index=False, encoding="utf-8-sig")
    new_n = len(merged) - len(old)
    if new_n:
        print(f"[corp_actions] 新命中 {new_n} 筆")
    return hit


def recent(days: int = 60) -> pd.DataFrame:
    if not LOG.exists():
        return pd.DataFrame()
    df = pd.read_csv(LOG, dtype=str)
    return df.tail(200)


# 2025-2026 分割恢復買賣案例實測(系統價格資料,恢復日進場)
SPLIT_CASES = pd.DataFrame([
    {"代號": "7780", "名稱": "大研生醫*", "恢復日": "2026-01-08", "比例": "1拆10",
     "預跑60日%": 870.0, "恢復後10日%": 45.9, "恢復後20日%": 47.6},
    {"代號": "5904", "名稱": "寶雅*", "恢復日": "2026-07-22", "比例": "1拆10",
     "預跑60日%": 17.2, "恢復後10日%": 14.1, "恢復後20日%": 23.6},
    {"代號": "5314", "名稱": "世紀*", "恢復日": "2026-08-06", "比例": "1拆4",
     "預跑60日%": -20.6, "恢復後10日%": 65.2, "恢復後20日%": 116.6},
    {"代號": "4747", "名稱": "強生", "恢復日": "2026-08-12", "比例": "1拆2",
     "預跑60日%": -3.4, "恢復後10日%": 1.3, "恢復後20日%": None},
    {"代號": "6949", "名稱": "沛爾生醫-創", "恢復日": "2026-09-07", "比例": "1拆20",
     "預跑60日%": 105.5, "恢復後10日%": None, "恢復後20日%": None},
])


def render_radar() -> None:
    """雷達畫面(pages/45 專頁與 pages/22 tab 共用,文案只維護這一份)。"""
    import streamlit as st
    st.markdown("#### 公告雷達(每日掃全市場重大訊息:股票分割/面額變更/減資)")
    st.caption("「提前布局」的合法時點=**公告日**。公告→股東會→停止買賣→恢復買賣,"
               "中間通常有數週到數月——雷達命中後把恢復買賣日記進行事曆。")
    rec = recent()
    if rec.empty:
        st.info("尚無記錄(run_daily 每日自動掃;可先手動執行 python corp_actions.py)。")
    else:
        st.dataframe(rec.iloc[::-1], hide_index=True, width="stretch")
    st.markdown("#### 2025-2026 分割恢復買賣案例實測(恢復日進場)")
    st.dataframe(SPLIT_CASES, hide_index=True, width="stretch")
    st.markdown("""
**規則(從案例歸納,樣本仍小,持續累積)**:
1. **恢復買賣日才是主戰場**——不必真的搶「提前」:世紀* 分割前 60 日還跌 20%,錢全在恢復後(+116.6%);
2. **比例要大**(≥1拆4):1拆2 的強生只有 +1.3%,「變便宜」的錯覺不夠強;
3. **預跑是反指標**:分割前已暴漲(沛爾 +105%)=利多出盡,恢復日 -10% 教訓;預跑低或負的才有行情;
4. **首日量價定調**:恢復日漲停鎖死=跟(照天量統計掛 -15% 統計停損);開高走低=沛爾型,跳過;
5. 疊加題材(世紀*=AI 無人機)才有連續漲停的燃料——分割只是火柴,題材才是柴堆。
""")


if __name__ == "__main__":
    h = scan_and_log()
    print(h.to_string(index=False) if not h.empty else "今日無命中")

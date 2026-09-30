"""
chain_ideas.py — 每日供應鏈發想(找「第二個大甲」的思考日課)
=================================================================
教案:大甲狂飆→市場翻供應鏈找彰源(產能/外圍)、強新(純度/疊度)、美亞(廠房配管)。
每天:挑一個「今天最有戲的主角」(地圖突破>鯨魚>量價異動)→ 引擎發想上下游候選
     +每檔的「檢核三問」(純度/產能/外圍) → 存文章庫(mode=供應鏈發想)+草稿鏈譜。
鐵律:引擎產出全部標註「假設待查證」;查證後才准手動寫進 data/supply_chain.json。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from twtime import now_tw

ROOT = Path(__file__).parent
DRAFTS = ROOT / "data" / "supply_chain_drafts.json"


def _name_map():
    sl = pd.read_csv(ROOT / "data" / "stock_list.csv", encoding="utf-8-sig", dtype=str)
    return dict(zip(sl["code"], sl["name"]))


def pick_subject() -> tuple[str, str, str] | None:
    """(code, name, 為什麼是它)。優先序:地圖剛突破 > 今日鯨魚 > 放棄。"""
    nm = _name_map()
    try:
        pool = pd.read_csv(ROOT / "data" / "_mmap_pool.csv", dtype=str)
        cc = next((c for c in pool.columns if c in ("代號", "代碼", "code")), None)
        br = pool[pool["狀態"].astype(str).str.contains("突破", na=False)]
        if len(br):
            c0 = str(br[cc].iloc[0])
            return c0, nm.get(c0, c0), "籌碼地圖今日剛突破"
    except Exception:
        pass
    try:
        w = pd.read_csv(ROOT / "data" / "warrants" / "whale_signals.csv", dtype={"ucode": str})
        today = f"{now_tw():%Y-%m-%d}"
        wt = w[w["date"].astype(str).str[:10] == today]
        if len(wt):
            c0 = str(wt["ucode"].iloc[0])
            return c0, nm.get(c0, c0), "今日權證鯨魚訊號"
    except Exception:
        pass
    return None


_SYS = """你是供應鏈偵探。主角股剛出現強勢訊號,你的任務是「發想它的供應鏈延伸」——
市場翻找『第二個大甲』的那種思考(教案:大甲(EP/BA超潔淨鋼管)飆→強新(純度最高,疊度最高)/
彰源(產能極大,吃純水廢水外圍)/美亞(廠房水電消防配管,外圍基建)分層受惠)。
【鐵律】你寫的每一檔候選都是「假設,待查證」——明確標註;不確定代號就寫公司名+『代號待查』;
寧可少寫不可編造;新聞標題只用來判斷主角為什麼強,不得當已驗證事實。
【輸出格式】直接開始:
# ⛓️ 今日供應鏈發想|{主角} 之後,誰是下一棒?
## 主角為什麼強(2-3句,引用給你的動能與新聞線索)
## 鏈的假設(表格:候選|上游/下游/外圍|它供應/承接什麼|受惠疊度高/中/低|這是假設)
## 檢核三問(每檔候選各一組:①純度—該業務占營收獲利多少?②產能—吃得下這波量嗎?
   ③時程—受惠是現在還是兩年後?)
## 明天你該查的三件事(具體:去哪頁看什麼數字)
400-700字。結尾:「以上全部是假設,查證後才寫進鏈譜。」"""


def generate_daily() -> str | None:
    sub = pick_subject()
    if sub is None:
        return None
    code, name, why = sub
    # 主角動能+新聞
    mom = ""
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            c = pd.read_csv(p, usecols=["Close"])["Close"].dropna()
            if len(c) > 61:
                mom = (f"20日{(c.iloc[-1]/c.iloc[-21]-1)*100:+.1f}% / "
                       f"60日{(c.iloc[-1]/c.iloc[-61]-1)*100:+.1f}%")
            break
    try:
        from analyst_report import _cnyes_headlines
        news = _cnyes_headlines(name or code, 10)
    except Exception:
        news = "(無)"
    try:
        import supply_chain
        known = json.dumps(supply_chain.chain_of(code), ensure_ascii=False)
    except Exception:
        known = "[]"
    digest = (f"主角:{name}({code})|訊號:{why}|動能:{mom}\n"
              f"【近期新聞標題(線索,非事實)】\n{news}\n"
              f"【已知鏈譜(若有)】{known}\n"
              f"【現有鏈譜其他鏈(參考格式)】不鏽鋼管件鏈:大甲/彰源/允強")
    from llm import generate
    out = generate(_SYS, digest, max_tokens=2200)
    if not out:
        return None
    # 存文章 + 草稿
    from analyst_report import save_article
    fn = save_article(code, name, "供應鏈發想", out)
    try:
        drafts = json.loads(DRAFTS.read_text(encoding="utf-8")) if DRAFTS.exists() else []
        drafts.append({"date": f"{now_tw():%Y-%m-%d}", "subject": f"{name}{code}",
                       "article": fn})
        DRAFTS.write_text(json.dumps(drafts[-60:], ensure_ascii=False, indent=1),
                          encoding="utf-8")
    except Exception:
        pass
    return fn


if __name__ == "__main__":
    print(generate_daily() or "今日無主角(無突破/無鯨魚)或引擎不可用")

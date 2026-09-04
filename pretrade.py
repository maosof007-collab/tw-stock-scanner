"""
pretrade.py — 買前體檢卡(四個燈+停損建議)
================================================
把「買前三查」變成一鍵:倒貨率/外資倒貨窗/投信/大戶/融資擁擠/爆量追高/榜單屬性。
教訓來源:2449 追高案(利多爆量日後追進,外資正在倒第二輪)與七月三層評比
(偷跑榜+21.9% vs 看好榜-1.2 超額 → 開獎日進場沒有超額)。
燈號:🔴 別現在買 / 🟡 條件不利 / 🟢 通過 / ⚪ 無資料。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


def _price_df(code: str) -> pd.DataFrame | None:
    for suf in (".TW", ".TWO"):
        p = ROOT / "data" / f"{code}{suf}.csv"
        if p.exists():
            d = pd.read_csv(p).dropna().sort_values("Date")
            for c in ("Open", "High", "Low", "Close", "Volume"):
                d[c] = pd.to_numeric(d[c], errors="coerce")
            return d.dropna()
    return None


def health_check(code: str, buy_price: float | None = None) -> dict:
    """回傳 {rows:[{燈,項目,讀數,說明}], verdict, stops:{...}, price}。"""
    rows: list[dict] = []

    d = _price_df(code)
    if d is None or len(d) < 60:
        return {"rows": [{"燈": "⚪", "項目": "價格資料", "讀數": "缺",
                          "說明": "系統無此檔日K,先跑資料更新"}],
                "verdict": "⚪ 無法體檢", "stops": {}, "price": None}
    close = float(d["Close"].iloc[-1])
    v20 = float(d["Volume"].tail(20).mean())
    ma20 = float(d["Close"].tail(20).mean())
    ma60 = float(d["Close"].tail(60).mean())
    hi252 = float(d["Close"].tail(252).max())
    tr = pd.concat([d["High"] - d["Low"],
                    (d["High"] - d["Close"].shift()).abs(),
                    (d["Low"] - d["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(14).mean())

    # ① 倒貨率(外資大買隔日倒的歷史機率)
    try:
        dr = pd.read_csv(ROOT / "data" / "inst_dump_rate.csv", dtype={"code": str})
        hit = dr[dr["code"] == code]
        if hit.empty:
            rows.append({"燈": "⚪", "項目": "隔日沖倒貨率", "讀數": "無樣本",
                         "說明": "法人參與少,對手盤是散戶彼此"})
        else:
            rate, n = float(hit["dump_rate"].iloc[0]), int(hit["events"].iloc[0])
            lamp = "🔴" if rate >= 40 else ("🟡" if rate >= 30 else "🟢")
            rows.append({"燈": lamp, "項目": "隔日沖倒貨率",
                         "讀數": f"{rate:.0f}%({n}次)",
                         "說明": "外資大買隔日倒≥50%的歷史機率;≥30%利多爆量日別追"})
    except Exception:
        rows.append({"燈": "⚪", "項目": "隔日沖倒貨率", "讀數": "讀取失敗", "說明": ""})

    # ② 外資倒貨窗(近10日大買後的反手賣)
    fi_ok = True
    try:
        i = pd.read_csv(ROOT / "data" / "institutional" / f"{code}_inst.csv").sort_values("date")
        fi = (i["外陸資買賣超股數(不含外資自營商)"].fillna(0) / 1000).tail(10).reset_index(drop=True)
        it = (i["it_net"].fillna(0) / 1000).tail(10).reset_index(drop=True)
        big_buy_idx = fi[fi >= max(500, fi.abs().max() * 0.5)].index
        dumping = False
        for bi in big_buy_idx:
            after = fi.iloc[bi + 1:]
            if len(after) and after.sum() <= -0.5 * fi.iloc[bi]:
                dumping = True
        fi5 = fi.tail(5).sum()
        if dumping:
            rows.append({"燈": "🔴", "項目": "外資倒貨窗",
                         "讀數": f"近5日淨{fi5:+,.0f}張",
                         "說明": "近10日出現大買→反手倒≥5成,倒貨進行中,等它倒完(通常2-3天)"})
            fi_ok = False
        elif fi5 < 0:
            rows.append({"燈": "🟡", "項目": "外資動向", "讀數": f"近5日淨{fi5:+,.0f}張",
                         "說明": "外資站賣方"})
            fi_ok = False
        else:
            rows.append({"燈": "🟢", "項目": "外資動向", "讀數": f"近5日淨{fi5:+,.0f}張",
                         "說明": "外資站買方"})
        it10 = it.sum()
        rows.append({"燈": "🟢" if it10 > 0 else ("⚪" if it10 == 0 else "🟡"),
                     "項目": "投信近10日", "讀數": f"{it10:+,.0f}張",
                     "說明": "投信連買=內資法人真金白銀" if it10 > 0 else "投信未參與/站賣方"})
    except Exception:
        rows.append({"燈": "⚪", "項目": "外資/投信", "讀數": "讀取失敗", "說明": ""})

    # ③ 大戶趨勢(集保>400張,近4週)
    try:
        pan = pd.read_csv(ROOT / "data" / "_bigholder_panel.csv")
        if code in pan.columns:
            s = pan[["date", code]].dropna().tail(4)
            delta = float(s[code].iloc[-1] - s[code].iloc[0])
            lamp = "🟢" if delta >= 0.5 else ("🔴" if delta <= -0.5 else "🟡")
            rows.append({"燈": lamp, "項目": "大戶>400張(4週)",
                         "讀數": f"{s[code].iloc[-1]:.1f}%({delta:+.2f}pp)",
                         "說明": "大戶吸籌才做波段;減碼中只做短"})
        else:
            rows.append({"燈": "⚪", "項目": "大戶>400張", "讀數": "無資料", "說明": ""})
    except Exception:
        rows.append({"燈": "⚪", "項目": "大戶>400張", "讀數": "讀取失敗", "說明": ""})

    # ④ 融資擁擠(近5日融資方向 × 價格方向)
    try:
        m = pd.read_csv(ROOT / "data" / "margin" / f"{code}_margin.csv").sort_values("date")
        mb = m["margin_balance"].dropna()
        dm = float(mb.iloc[-1] - mb.iloc[-6]) if len(mb) >= 6 else 0.0
        dp = close / float(d["Close"].iloc[-6]) - 1
        if dm > 0 and dp > 0:
            rows.append({"燈": "🟡", "項目": "融資擁擠", "讀數": f"5日{dm:+,.0f}張",
                         "說明": "融資追價中——你買的位置人很多"})
        elif dm > 0 and dp < 0:
            rows.append({"燈": "🔴", "項目": "融資接刀", "讀數": f"5日{dm:+,.0f}張",
                         "說明": "價跌資增=散戶接刀,柴堆變厚"})
        elif dm < 0 and dp > 0:
            rows.append({"燈": "🟢", "項目": "融資換手", "讀數": f"5日{dm:+,.0f}張",
                         "說明": "價漲資減=現金接走融資貨,健康"})
        else:
            rows.append({"燈": "🟢", "項目": "融資", "讀數": f"5日{dm:+,.0f}張", "說明": "同步降溫"})
    except Exception:
        rows.append({"燈": "⚪", "項目": "融資", "讀數": "讀取失敗", "說明": ""})

    # ⑤ 爆量追高窗(近6日內出現 量≥3×基準量 的利多爆量日;基準量取窗前20日,避免被爆量日自己灌高)
    d = d.reset_index(drop=True)
    v_base = float(d["Volume"].iloc[-26:-6].median()) if len(d) >= 26 else v20
    rb = d.tail(6)[d.tail(6)["Volume"] >= 2.5 * v_base]
    if not rb.empty:
        days_ago = len(d) - 1 - int(rb.index[-1])
        lamp = "🔴" if days_ago <= 3 else "🟡"
        rows.append({"燈": lamp, "項目": "爆量追高窗",
                     "讀數": f"{days_ago}日前爆量(≥3×均量)",
                     "說明": "利多爆量日+2~3天是倒貨窗;開獎日進場沒有超額(七月三層評比)"})
    else:
        rows.append({"燈": "🟢", "項目": "爆量追高窗", "讀數": "近6日無異常爆量",
                     "說明": "非開獎日追價"})

    # ⑥ 位置(均線/距高)
    pos_lamp = "🟢" if close > ma20 > ma60 else ("🟡" if close > ma20 or close > ma60 else "🔴")
    rows.append({"燈": pos_lamp, "項目": "位置",
                 "讀數": f"MA20 {ma20:.1f}/MA60 {ma60:.1f},距年高{(close / hi252 - 1) * 100:+.0f}%",
                 "說明": "多頭排列才有波段順風"})

    # 總評
    n_red = sum(1 for r in rows if r["燈"] == "🔴")
    n_yel = sum(1 for r in rows if r["燈"] == "🟡")
    if n_red >= 2:
        verdict = f"🔴 別現在買({n_red}紅{n_yel}黃)——等倒貨窗過/大戶回頭再看"
    elif n_red == 1:
        verdict = f"🟡 有一個致命傷({n_red}紅{n_yel}黃)——要買就減半倉+緊停損"
    elif n_yel >= 2:
        verdict = f"🟡 條件平庸({n_yel}黃)——不如去偷跑榜找更好的"
    else:
        verdict = "🟢 體檢通過——記得先寫決策日誌再下單"
    # 波動警語
    atr_pct = atr / close * 100
    if atr_pct >= 4:
        verdict += f"|⚠️ 日振幅{atr_pct:.1f}%,倉位打對折"

    bp = buy_price or close
    stops = {"初始停損(買價-1.5ATR)": round(bp - 1.5 * atr, 1),
             "MA20參考": round(ma20, 1), "ATR14": round(atr, 2),
             "現價": close}
    return {"rows": rows, "verdict": verdict, "stops": stops, "price": close}

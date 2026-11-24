"""事件研究海報:內需/車用/單車/國防 在空頭有沒有機會。

使用者 2026-11-20:「內需 知道國內市場內需不夠 看起來只會有一個蠱王撐到最後 內需/車用/單車/國防 族群 有機會嗎」
三個問題都用 bear_sector.py 算:跌的時候(歷次跌幅 vs 大盤)、反彈的時候(落底後 60/120 日)、蠱王檢定(龍頭占比與股價)。
主角=歷次表+兩張左右分開的圖(差距是「比大盤多或少」,不是跌幅,所以用 dbars)。
"""
from __future__ import annotations

import pandas as pd

import bear_sector as B
from poster import bignums, card, checks, dbars, row, save_poster, shell_flow
from twtime import now_tw

EP_LABEL = {"2015": "2015<br>4/27→8/24", "2018": "2018<br>10/1→1/3", "2020": "2020<br>1/14→3/19",
            "2022": "2022<br>1/4→10/25", "2025": "2025<br>2/20→4/9"}


def pc(x, d: int = 0) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:+.{d}f}%"


def pt(x) -> str:
    return "—" if pd.isna(x) else f"{x * 100:+.0f} 點"


def main() -> str:
    m = B.member_table()
    ix = B.index_row()
    F = B.fall_table(m)
    R = B.rebound_table(m)
    K = B.king_table(m)
    RN, rev_ym = B.rev_now(m)
    eps = B.episodes()
    end = eps[-1][2]
    now_lbl = f"這次<br>10/6→{end:%m/%d}"
    inner = [k for k in B.ORDER if B.KIND[k] == "內需"]
    past, now = B.PAST, B.NOW

    # ── 主角一:歷次表 ──
    th = "".join(f"<th>{EP_LABEL[e]}</th>" for e in past)
    tb = (f"<table><tr><th>類別</th><th>族群</th><th>檔數</th>{th}<th>{now_lbl}</th>"
          "<th>前五次<br>比大盤少跌</th><th>現在站上<br>年線的比例</th></tr>")
    tb += ('<tr><td colspan="3"><b>加權指數</b></td>' + "".join(f'<td class="n"><b>{pc(ix[e])}</b></td>' for e in past)
           + f'<td class="n"><b>{pc(ix[now])}</b></td><td>—</td><td>—</td></tr>')
    for k, r in F.iterrows():
        cells = ""
        for e in past + [now]:
            worse = r[e] < ix[e]
            cls = ' class="n yl"' if worse else ' class="n"'
            cells += f"<td{cls}>{pc(r[e])}</td>"
        tb += (f'<tr><td>{r["類別"]}</td><td><b>{k}</b></td><td class="n">{int(r["檔數"])}</td>{cells}'
               f'<td class="n">{int(r["贏大盤次數"])} / 5 次</td><td class="n">{r["站上年線"] * 100:.0f}%</td></tr>')
    tb += "</table>"
    c_hist = card("📉 六次大盤下跌:各族群跌多少(成分股中位數)", tb,
                  src="黃底=跌得比大盤多。期間=加權指數那一波的高點到低點(收盤);「這次」還沒確認落底,算到資料最後一天。"
                      "個股用還原價,加權指數不含息")

    # ── 主角二:兩張左右分開的圖 ──
    rows = []
    for k, r in F.sort_values("過去差距中位", ascending=False).iterrows():
        tip = f"{k}:前五次下跌,和大盤的差距中位數 {pt(r['過去差距中位'])},最差一次 {pt(r['過去最差差距'])},這次 {pt(r['差' + now])}"
        rows.append((k, round(r["過去差距中位"] * 100), [f"{int(r['贏大盤次數'])}/5", pt(r["過去最差差距"]), pt(r["差" + now])], tip))
    eg = F.loc["食品"]
    c_fall = card("① 跌的時候:比大盤多跌還是少跌(前五次的中位數)",
                  checks([("ok", "<b>怎麼看</b>:藍色往右=跌得比大盤少;橘色往左=跌得比大盤多。單位是百分點,<b>不是跌幅</b>"),
                          ("ok", f"例:2020 年大盤 {pc(ix['2020'])}、食品 {pc(eg['2020'])},差距就是 {pt(eg['差2020'])}")])
                  + dbars(rows, "比大盤多跌", "比大盤少跌", ["少跌次數", "最差一次", "這次"], unit=" 點",
                          c_left="#e07b00", c_right="#2f6db5"),
                  src="差距=族群成分股中位數漲跌幅−加權指數漲跌幅")
    rows = []
    for k, r in R.sort_values("差中位60", ascending=False).iterrows():
        tip = (f"{k}:大盤落底後 60 個交易日,族群中位數 {pc(r['中位60'])}、大盤 {pc(r['大盤中位60'])};"
               f"120 個交易日 族群 {pc(r['中位120'])}、大盤 {pc(r['大盤中位120'])}")
        rows.append((k, round(r["差中位60"] * 100), [pc(r["中位60"]), f"{int(r['贏60'])}/5", f"{pt(r['差中位120'])}({int(r['贏120'])}/5)"], tip))
    c_reb = card("② 反彈的時候:大盤落底後 60 個交易日,贏大盤還是落後",
                 checks([("ok", "<b>怎麼看</b>:藍色往右=反彈比大盤多;橘色往左=反彈比大盤少(一樣在漲,只是漲得少)"),
                         ("ok", f"五次落底後 60 個交易日,大盤中位數 {pc(R['大盤中位60'].iloc[0])};120 個交易日 {pc(R['大盤中位120'].iloc[0])}")])
                 + dbars(rows, "反彈落後大盤", "反彈贏大盤", ["族群漲", "贏大盤", "120 日差距(贏)"], unit=" 點",
                         c_left="#e07b00", c_right="#2f6db5"),
                 src="長條=五次(2015、2018、2020、2022、2025)差距的中位數。2026 這一波還沒確認落底,沒有這一段")

    # ── 結論 ──
    win5 = [k for k in inner if F.loc[k, "贏大盤次數"] == 5]
    in_reb = [int(R.loc[k, "贏60"]) for k in inner]
    full = list(K.index[K["中幾項"] == 3])
    none = list(K.index[K["中幾項"] == 0])
    up_share = list(K.index[K["占比上升"]])
    dn_share = list(K.index[~K["占比上升"]])
    car, bike, dfn = F.loc["車用"], F.loc["單車"], F.loc["國防"]
    concl = [
        ("ok", f"<b>內需:跌的時候有用</b>。前五次都比大盤少跌的有 {'、'.join(win5)};其餘 {'、'.join(k for k in inner if k not in win5)} 是 4 次。"
               f"這次大盤 {pc(ix[now])},內需各組 {pc(F.loc[inner, now].min())}~{pc(F.loc[inner, now].max())}"),
        ("wn", f"<b>內需:反彈的時候落後大盤</b>。大盤落底後 60 個交易日,六組內需在五次裡贏大盤的次數是 "
               f"{min(in_reb)}~{max(in_reb)} 次;中位數漲 {pc(R.loc[inner, '中位60'].min())}~{pc(R.loc[inner, '中位60'].max())},"
               f"大盤 {pc(R['大盤中位60'].iloc[0])}。它們是防守,不是進攻"),
        ("wn", f"<b>車用:過去不抗跌</b>。前五次只有 {int(car['贏大盤次數'])} 次跌得比大盤少,最差一次多跌 {abs(car['過去最差差距']) * 100:.0f} 點;"
               f"反彈也只贏 {int(R.loc['車用', '贏60'])} 次。這次 {pc(car[now])},比大盤少跌 {car['差' + now] * 100:.0f} 點"),
        ("wn", f"<b>單車:跌的時候跟大盤差不多,反彈靠一次</b>。前五次差距中位數 {pt(bike['過去差距中位'])};"
               f"反彈 60 日贏大盤的 {int(R.loc['單車', '贏60'])} 次裡有一次是 2020 年疫情({pc(R.loc['單車', '2020+60'])})。"
               f"現在 {int(bike['檔數'])} 檔全部在年線下"),
        ("wn", f"<b>國防:這次比大盤多跌</b>({pc(dfn[now])},大盤 {pc(ix[now])})。過去反彈 120 日贏大盤 {int(R.loc['國防', '贏120'])} 次、"
               f"中位數 {pc(R.loc['國防', '中位120'])}——但名單是現在回頭挑的 {int(dfn['檔數'])} 檔,這個數字偏樂觀"),
        ("wn", f"<b>蠱王只成立一半</b>:龍頭占比上升的有 {'、'.join(up_share)};下降的有 {'、'.join(dn_share)}。"
               f"三項(占比升、下跌時贏同業、長期贏同業)全中的只有 {'、'.join(full) or '沒有'}"
               + (f";三項全不中:{'、'.join(none)}" if none else "")),
        ("wn", f"<b>而且長期都輸大盤</b>:2019 年初至今大盤 {pc(ix['2019至今'])},八個龍頭裡最高的是 "
               f"{K['龍頭2019至今'].idxmax()}的{K.loc[K['龍頭2019至今'].idxmax(), '龍頭名稱']} {pc(K['龍頭2019至今'].max())}"),
    ]
    c_concl = card("📌 結論", checks(concl))
    n_full = len(full)
    c_big4 = card("🔢 四個數字", bignums([
        ("內需反彈贏大盤", f"{min(in_reb)}~{max(in_reb)} 次", "落底後 60 日,五次裡"),
        ("食品 跌的時候", pt(F.loc["食品", "過去差距中位"]).replace(" 點", "點"), f"比大盤少跌,{int(F.loc['食品', '贏大盤次數'])}/5 次"),
        ("車用 少跌次數", f"{int(car['贏大盤次數'])} / 5", "下跌時贏大盤"),
        ("蠱王三項全中", f"{n_full} / {len(K)}", "、".join(K.loc[full, "龍頭名稱"]) or "沒有")]).replace(
        'class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"'))

    # ── 反彈歷次表 ──
    th = "".join(f"<th>{e} 年<br>落底後</th>" for e in past)
    tb = (f"<table><tr><th>族群</th>{th}<th>五次<br>中位數</th><th>60 日<br>贏大盤</th>"
          "<th>120 日<br>中位數</th><th>120 日<br>贏大盤</th></tr>")
    tb += ("<tr><td><b>加權指數</b></td>" + "".join(f'<td class="n"><b>{pc(ix[e + "+60"])}</b></td>' for e in past)
           + f'<td class="n"><b>{pc(R["大盤中位60"].iloc[0])}</b></td><td>—</td><td class="n"><b>{pc(R["大盤中位120"].iloc[0])}</b></td><td>—</td></tr>')
    for k, r in R.iterrows():
        cells = ""
        for e in past:
            col = e + "+60"
            cls = ' class="n yl"' if r[col] < ix[col] else ' class="n"'
            cells += f"<td{cls}>{pc(r[col])}</td>"
        tb += (f'<tr><td><b>{k}</b></td>{cells}<td class="n">{pc(r["中位60"])}</td><td class="n">{int(r["贏60"])} / 5</td>'
               f'<td class="n">{pc(r["中位120"])}</td><td class="n">{int(r["贏120"])} / 5</td></tr>')
    tb += "</table>"
    lows = "、".join(f"{b:%Y/%m/%d}" for _, _, b in eps[:-1])
    c_rebt = card("📈 落底後 60 個交易日:每一次各族群漲多少", tb,
                  src=f"黃底=漲得比大盤少。落底日={lows}(加權指數那一波的收盤最低點)。2026 這一波還沒確認落底,所以沒有這一欄")

    # ── 蠱王 ──
    def yn(b):
        return "✔" if b else "✘"
    tb = ("<table><tr><th>產業</th><th>營收最大的<br>(龍頭)</th><th>可比<br>家數</th><th>龍頭占同業營收<br>2019 → 現在</th><th>前三大合計<br>2019 → 現在</th>"
          "<th>營收成長<br>龍頭 / 同業中位</th><th>成長贏過<br>整體的家數</th><th>六次下跌<br>龍頭贏同業</th><th>2019 年初至今股價<br>龍頭 / 同業中位</th>"
          "<th>占比升·抗跌·長期贏</th></tr>")
    for k, r in K.iterrows():
        tb += (f'<tr><td><b>{k}</b></td><td>{r["龍頭名稱"]} {r["龍頭"]}</td><td class="n">{int(r["可比檔數"])} / {int(r["全部檔數"])}</td>'
               f'<td class="n">{r["市占2019"] * 100:.0f}% → {r["市占現在"] * 100:.0f}%</td>'
               f'<td class="n">{r["前三市占2019"] * 100:.0f}% → {r["前三市占現在"] * 100:.0f}%</td>'
               f'<td class="n">{pc(r["龍頭營收成長"])} / {pc(r["同業營收成長中位"])}</td><td class="n">{r["贏的家數比例"] * 100:.0f}%</td>'
               f'<td class="n">{int(r["下跌時贏同業"])} / {int(r["下跌次數"])}</td>'
               f'<td class="n">{pc(r["龍頭2019至今"])} / {pc(r["同業2019至今"])}</td>'
               f'<td class="n">{yn(r["占比上升"])} {yn(r["下跌抗跌"])} {yn(r["長期贏同業"])}(中 {int(r["中幾項"])} 項)</td></tr>')
    tb += "</table>"
    few = K["贏的家數比例"].drop(index=[k for k in ("電信三雄",) if k in K.index])
    lose = few[few < 0.4]
    bk = K.loc["單車"] if "單車" in K.index else None
    king_notes = [
        ("wn", f"<b>「大者恆大」在營收上看得到</b>:{'、'.join(up_share)} 的龍頭占比上升;"
               f"{'、'.join(lose.index)} 裡成長贏過整個產業的公司只占 {lose.min() * 100:.0f}%~{lose.max() * 100:.0f}%——這幾個產業多數公司在掉占比"),
        ("wn", f"<b>但不是每個產業都只剩一個</b>:{'、'.join(dn_share)} 的龍頭占比是下降的"),
        ("wn", "<b>占比上升不等於股價贏</b>:統一、統一超占比都升、下跌時也比同業抗跌,但 2019 年初至今股價沒有贏同業中位數"),
    ]
    if bk is not None:
        king_notes.append(("wn", f"<b>單車三項全中,但池子在縮</b>:同一批公司的營收比 2019 年 {pc(bk['整體營收成長'])},"
                                 f"巨大 {pc(bk['龍頭營收成長'])}、同業中位 {pc(bk['同業營收成長中位'])};巨大股價 2019 年初至今 {pc(bk['龍頭2019至今'])}"))
    king_notes.append(("wn", f"全部和大盤比都輸:同期加權指數 {pc(ix['2019至今'])}(而且指數還沒算股息)"))
    c_king = card("👑 蠱王檢定:每個產業營收最大的那一家,有沒有越來越大、股價有沒有贏", tb + checks(king_notes),
                  src="營收=2019 全年 vs 最近 12 個月(到 " + rev_ym + ")的合併營收,只算兩段都有完整 12 個月的公司(「可比家數」)。"
                      "這是「占上市櫃同業合併營收的比例」,不是國內市占:合併營收含海外與子公司(例:統一的營收裡包含統一超)。"
                      "三項檢定:占比上升超過 1 個百分點、六次下跌至少 4 次贏同業中位數、2019 年初至今股價贏同業中位數。金融業營收含保費與投資損益,不算")

    # ── 現況 ──
    tb = ("<table><tr><th>族群</th><th>上一波漲幅<br>2025/4/9→10/6</th><th>這次漲跌<br>(中位數)</th><th>收平以上<br>的比例</th><th>站上年線<br>的比例</th>"
          "<th>近三個月營收<br>年增(中位數)</th><th>營收正成長<br>的比例</th></tr>")
    tb += (f'<tr><td><b>加權指數</b></td><td class="n"><b>{pc(ix["前波"])}</b></td><td class="n"><b>{pc(ix[now])}</b></td>'
           "<td>—</td><td>—</td><td>—</td><td>—</td></tr>")
    for k in B.ORDER:
        r, q = F.loc[k], RN.loc[k]
        tb += (f'<tr><td><b>{k}</b></td><td class="n">{pc(r["前波"])}</td><td class="n">{pc(r[now])}</td><td class="n">{r["這次收平以上"] * 100:.0f}%</td>'
               f'<td class="n">{r["站上年線"] * 100:.0f}%</td><td class="n">{pc(q["年增中位"], 1)}</td><td class="n">{q["正成長比例"] * 100:.0f}%</td></tr>')
    tb += "</table>"
    weak = [k for k in B.ORDER if RN.loc[k, "年增中位"] < 0.05]
    above = F["站上年線"].sort_values(ascending=False)
    c_now = card("📍 現在的位置:這次跌得少,但多數已在年線下", tb + checks([
        ("wn", f"<b>「內需不夠」數字上看得到</b>:近三個月營收年增中位數不到 5% 的有 {'、'.join(weak)}"),
        ("wn", f"站上年線比例高的只有 {above.index[0]}({above.iloc[0] * 100:.0f}%)、{above.index[1]}({above.iloc[1] * 100:.0f}%)、"
               f"{above.index[2]}({above.iloc[2] * 100:.0f}%)"),
        ("wn", f"<b>這次跌得少,是因為上一波也沒跟上</b>:2025/4/9 落底到 10/6 高點,大盤 {pc(ix['前波'])},"
               f"這九組的中位數是 {pc(F['前波'].min())}~{pc(F['前波'].max())},沒有一組贏大盤" if (F["前波"] < ix["前波"]).all() else
               f"上一波(2025/4/9→10/6)大盤 {pc(ix['前波'])};贏大盤的族群:{'、'.join(F.index[F['前波'] >= ix['前波']])}")]),
        src=f"這次=10/6 到 {end:%m/%d};年線=240 日均線;營收年增=最近三個月合計 ÷ 去年同期三個月合計(到 {rev_ym})")

    # ── 手選名單:全列 ──
    def mem_table(g):
        d = m[m["族群"] == g]
        t = "<table><tr><th>名稱</th>" + "".join(f"<th>{e}</th>" for e in past) + "<th>這次</th><th>站上年線</th><th>2019 年初至今</th></tr>"
        for _, r in d.iterrows():
            ma = "—" if pd.isna(r["站上年線"]) else ("是" if r["站上年線"] else "否")
            cells = "".join(f'<td class="n">{pc(r[e])}</td>' for e in past + [now])
            t += f'<tr><td><b>{r["名稱"]}</b> {r["代號"]}</td>{cells}<td>{ma}</td><td class="n">{pc(r["2019至今"])}</td></tr>'
        return t + "</table>"
    c_bike = card(f"🚲 單車名單({int(F.loc['單車', '檔數'])} 檔,全列)", mem_table("單車"),
                  src="手選名單,代號已用系統的股票名單核對。官方「運動休閒」類有 27 檔,其餘是健身器材、高爾夫、製鞋等,沒把握是單車的不列")
    c_def = card(f"🛡 國防名單({int(F.loc['國防', '檔數'])} 檔,全列)", mem_table("國防"),
                 src="系統軍工航太組 4 檔(漢翔、雷虎、亞航、龍德造船)加台船、全訊。空白=當時還沒上市或資料不足")
    c_tel = card("📶 電信三雄(3 檔,全列)", mem_table("電信三雄"), src="中華電、台灣大、遠傳")

    # ── 官方產業成分股:全列 ──
    body = ""
    for g in [k for k in B.ORDER if k in B.SECTORS]:
        d = m[m["族群"] == g].sort_values(now, ascending=False)
        chips = "、".join(f"{r['名稱']} {r['代號']}({pc(r[now])})" for _, r in d.iterrows())
        body += (f'<div style="margin:6px 0 2px;font-weight:900;color:#27303b">{g}({len(d)} 檔,官方「{B.SECTORS[g]}」)</div>'
                 f'<div style="font-size:12.5px;line-height:1.7;font-weight:600">{chips}</div>')
    c_mem = card("📋 官方產業成分股全名單(括號=這次 10/6 到現在的漲跌,由高到低)", body,
                 src="成分股照 data/stock_list.csv 的官方產業別,沒有挑過。沒有股價檔的不在內")

    c_lim = card("⚠️ 限制", checks([
        ("wn", "只有五次已經走完的下跌(2015 年起,因為本機股價從 2015 年開始);每次的原因都不同"),
        ("wn", f"單車只有 {int(F.loc['單車', '檔數'])} 檔、國防只有 {int(F.loc['國防', '檔數'])} 檔,而且是現在回頭挑的名單(當年不一定被當成國防股),中位數很容易被一兩檔帶動"),
        ("wn", "個股用還原價(含配息)、加權指數不含息:高配息的內需股和大盤比,會被多算一點;下跌區間短,影響小,2019 年至今那一欄影響大"),
        ("wn", "「占比」是上市櫃同業的合併營收比例,不是國內市場占有率;沒上市的對手、海外營收都會讓它失真。台塑化的營收跟著油價走"),
        ("wn", "電信只有 3 家,2023 年兩樁合併(台灣大併台灣之星、遠傳併亞太)讓另外兩家營收跳升,中華電占比下降有這個原因"),
        ("wn", "日馳 2015 年那一段股價首尾相同,可能是資料問題;早年沒上市的公司那幾次是空白"),
        ("wn", "研究筆記,不是買賣建議;大盤燈號仍是禁開新倉")]), extra_cls="risk")

    blocks = [("wide", c_hist), ("wide", row([c_fall, c_reb], "2")), ("wide", row([c_concl, c_big4], "21")), ("wide", c_now), ("wide", c_rebt), ("wide", c_king),
              c_bike, c_def, c_tel, ("wide", c_mem), c_lim]
    date = f"{now_tw():%Y%m%d}"
    sub = (f"內需六組在五次下跌裡少跌 {int(F.loc[inner, '贏大盤次數'].min())}~5 次,但落底後 60 日贏大盤只有 {min(in_reb)}~{max(in_reb)} 次;"
           f"車用過去只少跌 {int(car['贏大盤次數'])} 次;國防這次 {pc(dfn[now])} 比大盤差;龍頭三項全中的只有 {'、'.join(K.loc[full, '龍頭名稱']) or '沒有'}")
    html = shell_flow(
        title_html="<b>內需、車用、單車、國防</b>:空頭裡有沒有機會?",
        subtitle=sub, brand="內需防禦", blocks=blocks, kind="event",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:本機還原價、月營收、官方產業別(bear_sector.py) · 研究筆記,非投資建議")
    print("副標:", sub)
    return str(save_poster("內需防禦", date, html))


if __name__ == "__main__":
    print(main())

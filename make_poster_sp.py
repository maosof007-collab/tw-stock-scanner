"""選擇權 SP(賣出賣權)防守地圖海報 — 比較/挑選類。
python -X utf8 make_poster_sp.py   → data/papers/選擇權SP防守海報_<日期>.html
數字全部來自 op_defense(期交所每日行情+加權指數歷史);機械式計算,不是下單建議。
"""
from __future__ import annotations

import pandas as pd

import op_defense as D
from poster import bignums, card, checks, hbars, save_poster, shell_flow
from poster import row as prow
from twtime import now_tw


def pct(x, d=1) -> str:
    return "—" if x != x else f"{x * 100:+.{d}f}%"


def p0(x) -> str:
    return "—" if x != x else f"{x * 100:.0f}%"


def n0(x) -> str:
    return "—" if x != x else f"{x:,.0f}"


def strike_table(ch: dict, k: int, lo: int, step: int = 500) -> str:
    """一個到期日的履約價對照表(每 step 點一列)。"""
    xm, xe = D.fwd_min(k), D.fwd_end(k)
    fn = ch["f_now"]
    t = ch["table"]
    t = t[(t["履約價"] % step == 0) & (t["履約價"] >= lo) & (t["履約價"] <= ch["F"] + step)].sort_values("履約價", ascending=False)
    tb = ("<table><tr><th>履約價</th><th>離現在<br>期貨</th><th>權利金(點)<br>現在 / 昨收</th><th>一口收<br>(元)</th><th>損益<br>兩平</th>"
          "<th>未平倉<br>(昨增減)</th><th>波動率</th><th>權利金翻倍<br>期貨約在</th><th>歷史:期間內<br>跌到翻倍點</th>"
          "<th>歷史:到期<br>收在履約價下</th><th>一口保證金<br>現在→翻倍時</th></tr>")
    for r in t.itertuples():
        dbl = getattr(r, "翻倍點", float("nan"))
        p_dbl = float((xm <= dbl / fn - 1).mean()) if dbl == dbl else float("nan")
        p_end = float((xe <= r.履約價 / fn - 1).mean())
        m_now = D.sp_margin(fn, r.履約價, r.權利金)
        m_dbl = D.sp_margin(dbl, r.履約價, r.權利金 * D.STOP_MULT) if dbl == dbl else float("nan")
        chg = "" if r.未平倉增減 != r.未平倉增減 else f" ({int(r.未平倉增減):+d})"
        tb += (f'<tr><td><b>{r.履約價:,}</b></td><td class="n">{pct(r.離現在)}</td><td class="n"><b>{r.權利金:,.0f}</b> / {r.昨結算:,.0f}</td>'
               f'<td class="n">{r.權利金 * D.PT:,.0f}</td><td class="n">{n0(r.損益兩平)}</td><td class="n">{r.未平倉:,}{chg}</td>'
               f'<td class="n">{p0(r.波動率)}</td><td class="n">{n0(dbl)}</td><td class="n">{p0(p_dbl)}</td><td class="n">{p0(p_end)}</td>'
               f'<td class="n">{m_now / 1e4:.1f} → {"—" if m_dbl != m_dbl else f"{m_dbl / 1e4:.1f}"} 萬</td></tr>')
    return tb + "</table>"


def main() -> str:
    days = D.load_days(2)
    asof = pd.Timestamp(days[-1]["Date"].iloc[0])
    L = D.levels()
    lv = D.live_future()
    fn = lv.get("最新") if lv and lv.get("最新") == lv.get("最新") else None
    months = D.months_live(days)
    today = now_tw().date()
    m_today = [m for m in months if D.expiry_of(m) == today]
    m_week = [m for m in months if D.expiry_of(m) > today][0]
    m_mon = [m for m in months if len(m) == 6][0]
    CH = {m: D.chain(m, days, f_now=fn) for m in dict.fromkeys(m_today + [m_week, m_mon])}
    lp = D.live_puts(m_mon) if fn else pd.DataFrame()
    if len(lp) > 20:                       # 月選改用即時權利金重算
        CH[m_mon] = D.chain(m_mon, days, f_now=fn, live=lp, today=today)
    cw, cm = CH[m_week], CH[m_mon]
    px_src = (f"即時買賣價中間({now_tw():%H:%M})" if cm["即時"] else f"期交所 {asof:%m/%d} 結算價")
    fn = fn or cm["F"]
    kw, km = D.trading_days(today, cw["expiry"]), D.trading_days(today, cm["expiry"])
    src_live = f"{lv.get('來源', '')} {lv.get('時間', '')[:2]}:{lv.get('時間', '')[2:4]}" if lv else "抓不到即時價,用昨日結算反推"

    # ── 防守線:賣權未平倉集中在哪 ──
    def wall_rows(ch, label, step):
        b = D.bands(ch, step).sort_values("未平倉", ascending=False).head(4)
        out = ""
        for seg, r in b.iterrows():
            out += (f'<tr><td>{label}</td><td><b>{int(seg):,}~{int(seg) + step - 100:,}</b></td><td class="n">{pct(seg / fn - 1)}</td>'
                    f'<td class="n">{int(r["未平倉"]):,}</td><td class="n">{int(r["增減"]):+,}</td><td class="n">{r["占比"] * 100:.0f}%</td></tr>')
            label = ""
        return out
    tbw = "<table><tr><th>到期日</th><th>賣權集中的區間</th><th>離現在期貨</th><th>未平倉(口)</th><th>昨天增減</th><th>占價外賣權</th></tr>"
    for m in m_today:
        tbw += wall_rows(CH[m], f"今天 {D.expiry_of(m):%m/%d}(週五選)", 500)
    tbw += wall_rows(cw, f"{cw['expiry']:%m/%d}(週選,剩 {kw} 個交易日)", 1000)
    tbw += wall_rows(cm, f"{cm['expiry']:%m/%d}(月選,剩 {km} 個交易日)", 1000)
    tbw += "</table>"
    bm = D.bands(cm, 1000)
    top_m = bm.sort_values("未平倉", ascending=False)
    add_m = bm.sort_values("增減", ascending=False)
    near = bm[bm.index >= fn * 0.9]["未平倉"].sum() / bm["未平倉"].sum()
    c_wall = card("🧱 賣方防守線:賣權未平倉集中在哪", tbw + checks([
        ("wn", f"<b>月選近端沒有像樣的防守線</b>:價外賣權只有 {near * 100:.0f}% 放在離現在一成以內;最大的三段是 "
               + "、".join(f"{int(k):,}({int(v):,} 口)" for k, v in top_m["未平倉"].head(3).items())),
        ("wn", f"<b>昨天新增最多的是 {int(add_m.index[0]):,} 那一段(+{int(add_m['增減'].iloc[0]):,} 口)</b>,離現在 {pct(add_m.index[0] / fn - 1, 0)}"
               "——賣方是把防守往下移,不是在現價附近接")]),
        src=f"資料:期交所 {asof:%m/%d} 一般時段未平倉(op_defense.bands)。區間=每 1,000 點加總(今天到期的每 500 點);只算價外賣權")
    c_bar = card(f"📊 月選({cm['expiry']:%m/%d} 到期)價外賣權未平倉,每 1,000 點一段",
                 hbars([(f"{int(k):,}", int(v), "#0f8a7e") for k, v in bm["未平倉"].items()], unit=" 口").replace("+", ""),
                 src=f"由上往下=離現在越來越遠。現在期貨 {fn:,.0f}")

    # ── 歷史 ──
    H = D.mae_table(horizons=tuple(dict.fromkeys((1, kw, km))))
    th = ("<table><tr><th>之後幾個交易日</th><th>中位數</th><th>最差一成</th><th>最差 5%</th><th>最差 1%</th>"
          "<th>跌超過 5%</th><th>跌超過 8%</th><th>跌超過 10%</th><th>跌超過 15%</th></tr>")
    for k, r in H["rows"].items():
        th += (f'<tr><td><b>{k} 日</b>(對應指數)</td><td class="n">{pct(r["中位"])}<br>{L["收盤"] * (1 + r["中位"]):,.0f}</td>'
               f'<td class="n">{pct(r["最差一成"])}<br>{L["收盤"] * (1 + r["最差一成"]):,.0f}</td>'
               f'<td class="n">{pct(r["最差5趴"])}<br>{L["收盤"] * (1 + r["最差5趴"]):,.0f}</td>'
               f'<td class="n">{pct(r["最差1趴"])}<br>{L["收盤"] * (1 + r["最差1趴"]):,.0f}</td>'
               f'<td class="n">{p0(r["碰到5"])}</td><td class="n">{p0(r["碰到8"])}</td><td class="n">{p0(r["碰到10"])}</td><td class="n">{p0(r["碰到15"])}</td></tr>')
    th += "</table>"
    hm = H["rows"][km]
    c_hist = card("📉 歷史上同樣處境,之後再跌多少", th + checks([
        ("wn", f"「同樣處境」=收盤在季線下、離一年高點至少 15%。1998 年以來共 {H['總天數']:,} 天,現在就在裡面(離高點 {pct(L['離高點'], 0)})"),
        ("wn", "數字是「期間內最低收盤」比當天低多少,不是期末。天數之間高度重疊,實際獨立的空頭只有十來次")]),
        src=f"op_defense.mae_table;指數換算以 {L['日期']:%m/%d} 收盤 {L['收盤']:,.0f} 為準")

    # ── 履約價對照 ──
    note = checks([
        ("wn", f"<b>「權利金翻倍」是家規的賣方停損</b>(op_paper:權利金變兩倍就停損)。表上是「波動率不變、今天就跌到」的算法;"
               "實際上下跌時波動率會升,翻倍會來得更早;越接近到期則越晚"),
        ("wn", "「歷史」兩欄=上面那個處境裡,期間內最低收盤跌到翻倍點的比例、到期日收盤低於履約價的比例"),
        ("wn", f"保證金=權利金市值+MAX(A−價外值, B),A={187000:,}、B={94000:,}(期交所公告的原始保證金,盤中會再調)")])
    lo_m = int(min(30000, (fn * 0.78) // 500 * 500))
    c_mon = card(f"📋 月選 {cm['expiry']:%m/%d} 到期(剩 {km} 個交易日):每個履約價的防守數字",
                 strike_table(cm, km, lo_m) + note,
                 src=f"權利金={px_src};未平倉是 {asof:%m/%d} 收盤;每 500 點列一檔(期交所每 100 點一檔)。現在期貨 {fn:,.0f}({src_live})")
    c_wk = card(f"📋 週選 {cw['expiry']:%m/%d} 到期(剩 {kw} 個交易日)",
                strike_table(cw, kw, int(cw["table"]["履約價"].min())),
                src=f"權利金是 {asof:%m/%d} 結算價(週選沒有接即時報價),今天開盤後已經變貴;這個到期日最低只掛到表上最後一列")

    # ── 今天到期 ──
    c_today = ""
    if m_today:
        ct = CH[m_today[0]]
        bt = D.bands(ct, 500).sort_values("未平倉", ascending=False)
        c_today = card(f"⏰ 今天到期的週五選({ct['expiry']:%m/%d} 13:30 結算)", checks([
            ("wn", f"買權未平倉 {ct['買權未平倉']:,.0f} 口、賣權 {ct['賣權未平倉']:,.0f} 口——<b>賣方主力壓在上面(賣買權),不是在下面接(賣賣權)</b>"),
            ("wn", "賣權集中:" + "、".join(f"{int(k):,}~{int(k) + 400:,}({int(v):,} 口)" for k, v in bt["未平倉"].head(3).items())),
            ("wn", f"昨天結算時價平 {ct['價平']:,.0f}、買賣權合計 {ct['跨式']:,.0f} 點(市場預期今天上下 {ct['跨式'] / ct['F'] * 100:.1f}%);"
                   f"最大痛點 {ct['最大痛點']:,.0f}")]), src="最大痛點=到期落在哪裡,買方合計拿回最少")

    # ── 指數位置 ──
    c_lvl = card("📍 指數現在在哪", checks([
        ("wn", f"{L['日期']:%m/%d} 收 {L['收盤']:,.0f}({pct(L['昨日漲跌'])}),離 {L['高點日']:%m/%d} 高點 {L['高點']:,.0f} {pct(L['離高點'], 0)}"),
        ("wn", f"<b>年線 {L['年線']:,.0f} 已跌破</b>,現在在上方 {pct(L['年線'] / L['收盤'] - 1)},變成壓力;季線 {L['季線']:,.0f}"),
        ("wn", (f"夜盤期貨收 {lv['夜盤收']:,.0f},低點 {lv['夜盤低']:,.0f}、高點 {lv['夜盤高']:,.0f}" if lv else "夜盤期貨抓不到")),
        ("wn", f"單日跌停(−10%)是 {L['收盤'] * 0.9:,.0f};今年最低收盤是 {L['今年低點日']:%m/%d} 的 {L['今年低點']:,.0f}"),
        ("wn", "歷次限空令(見限空令海報):措施後中位數再跌 12%、最差 37%,7 次有 4 次再破底"),
        ("wn", f"近 20 日實際波動(年化){L['近20日實際波動'] * 100:.0f}%;月選價平波動率 {cm['價平波動率'] * 100:.0f}%、週選 {cw['價平波動率'] * 100:.0f}%"
               "——權利金貴,是因為指數真的在大幅震盪")]), src="op_defense.levels")

    d_m = cm["table"]
    d_m = d_m[d_m["翻倍點"].notna() & (d_m["履約價"] <= fn) & (d_m["履約價"] >= lo_m)]
    dbl_lo, dbl_hi = d_m["翻倍點"].min(), d_m["翻倍點"].max()
    xm = D.fwd_min(km)
    p_lo, p_hi = float((xm <= dbl_hi / fn - 1).mean()), float((xm <= dbl_lo / fn - 1).mean())
    ex = cm["table"].iloc[(cm["table"]["履約價"] - fn * 0.94).abs().argmin()]
    ex_k, ex_old, ex_new = int(ex["履約價"]), float(ex["昨結算"]), float(ex["權利金"])
    c_concl = card("📌 結論:防守在哪", checks([
        ("wn", f"<b>現價附近沒有賣方大軍</b>。月選賣權新增最多在 {int(add_m.index[0]):,}(離現在 {pct(add_m.index[0] / fn - 1, 0)}),"
               f"週選集中在 {int(D.bands(cw, 1000)['未平倉'].idxmax()):,} 那一段"),
        ("wn", f"<b>月選不管賣哪一檔,期貨跌到 {dbl_lo:,.0f}~{dbl_hi:,.0f} 權利金就翻倍</b>(家規停損)。"
               f"歷史上同樣處境 {km} 個交易日內跌到那裡的比例是 {p0(min(p_lo, p_hi))}~{p0(max(p_lo, p_hi))}"),
        ("wn", (f"<b>昨天收盤賣的已經在虧</b>:{ex_k:,} 賣權昨收 {ex_old:,.0f} 點、現在 {ex_new:,.0f} 點({pct(ex_new / ex_old - 1, 0)});"
                f"以昨收為成本,翻倍停損是 {ex_old * 2:,.0f} 點") if cm["即時"] else "月選權利金是昨天結算價,今天開盤後已經變貴"),
        ("wn", f"同樣處境 {km} 個交易日內:中位數再跌 {abs(hm['中位']) * 100:.1f}%({L['收盤'] * (1 + hm['中位']):,.0f}),"
               f"最差一成跌 {abs(hm['最差一成']) * 100:.0f}%({L['收盤'] * (1 + hm['最差一成']):,.0f}),最差 5% 跌 {abs(hm['最差5趴']) * 100:.0f}%({L['收盤'] * (1 + hm['最差5趴']):,.0f})"),
        ("wn", f"年線 {L['年線']:,.0f} 已經在頭上;下方有意義的整數關卡只剩賣方自己選的 {int(top_m.index[0]):,}、{int(top_m.index[1]):,}"),
        ("wn", "大盤燈號是「禁開新倉、只出不進」;裸賣賣權是開新倉、而且虧損沒有上限(到指數歸零為止)。價差(同時買更低履約價的賣權)才有上限")]))
    c_big4 = card("🔢 四個數字", bignums([
        ("現在期貨", f"{fn:,.0f}", src_live),
        ("月選價平波動率", f"{cm['價平波動率'] * 100:.0f}%", f"近 20 日實際 {L['近20日實際波動'] * 100:.0f}%"),
        (f"{km} 日內再跌 10%", p0(hm["碰到10"]), f"跌到 {L['收盤'] * 0.9:,.0f}"),
        ("翻倍停損區", f"{dbl_lo / 1000:.1f}~{dbl_hi / 1000:.1f} 千", "月選各履約價")]).replace(
        'class="bignums"', 'class="bignums" style="grid-template-columns:1fr 1fr"'))

    c_lim = card("⚠️ 限制", checks([
        ("wn", f"未平倉和權利金是 {asof:%m/%d} 收盤的,今天盤中會變;期交所不公布誰是賣方,「防守線」只是未平倉集中處,不保證守得住"),
        ("wn", "波動率、翻倍點用 Black-76、利率當 0 算;深價外的報價稀疏,數字較粗"),
        ("wn", "歷史比例混了 1998–2014 年(當時單日漲跌幅上限 7%)和之後(10%);沒有扣國定假日"),
        ("wn", "我不知道你手上的部位。給我履約價、到期日、收的權利金,可以算那一口的翻倍點和保證金"),
        ("wn", "研究筆記,不是下單建議;系統不下單")]), extra_cls="risk")

    blocks = [("wide", prow([c_wall, c_big4 + c_concl], "2")), ("wide", c_mon), ("wide", c_hist), c_bar, c_lvl, ("wide", c_wk)]
    if c_today:
        blocks.append(c_today)
    blocks.append(c_lim)
    date = f"{now_tw():%Y%m%d}"
    html = shell_flow(
        title_html="<b>選擇權 SP 防守地圖</b>:賣權的防守線在哪?",
        subtitle=f"月選賣方把防守往下移到 {int(add_m.index[0]):,}(離現在 {pct(add_m.index[0] / fn - 1, 0)});"
                 f"期貨跌到 {dbl_lo:,.0f}~{dbl_hi:,.0f} 權利金翻倍;歷史上同樣處境 {km} 日內再跌 10% 的比例 {p0(hm['碰到10'])}",
        brand="選擇權 SP", blocks=blocks, kind="compare",
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:期交所每日行情 {asof:%m/%d}、加權指數歷史(op_defense.py) · 機械式計算,非下單建議")
    print("期貨", fn, src_live, "| 月選", m_mon, km, "日 | 週選", m_week, kw, "日 | 翻倍區", round(dbl_lo), round(dbl_hi), "| 機率", round(p_lo, 3), round(p_hi, 3))
    return str(save_poster("選擇權SP防守", date, html))


if __name__ == "__main__":
    print(main())

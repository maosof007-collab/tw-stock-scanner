# -*- coding: utf-8 -*-
"""分點海報:單檔個股「掛牌以來各分點的累計庫存」——誰手上有貨、誰賣的不是自己買的。(2026-11-18)
表格全部由 branch_hist 的快取重算;NOTES 是人工寫的結論與查證(每檔一筆,沒寫的只出表格)。
另外兩張表拿原始申報來對分點:內部人每月持股(bh.insiders)、增資基準日公告+融券現券償還(bh.new_shares/conv_windows)。
手動:python -X utf8 make_poster_branch.py 4566      (加 --refresh 重抓:分點 3~5 分鐘、內部人月報與增資公告只補缺的月份;
      沒抓過的股票第一次三樣全抓,約 15~20 分鐘)"""
import sys

import pandas as pd

import branch_hist as bh
from poster import card, checks, save_poster, shell
from symbols import resolve
from twtime import now_tw

NOTES = {
    "4566": dict(
        sub="永豐金-板新對上了董事兼大股東丁凌全:他每月申報的持股變動,和板新當月淨買賣幾乎一張不差;"
            "他 10 月底持股 13,888 張、全部設質。2024 年那批「來源不明」的賣壓,對得上可轉債轉換",
        concl=[
            ("ok", "●<b>永豐金-板新 = 丁凌全的主要帳戶</b>(數字比對):申報持股 2021/1 增 3,599 張、板新當月淨買 3,593;"
                   "2025/11 增 580、板新 576;2026/3 增 1,223、板新 1,221;2026/6 增 365、板新 367(完整對照見下表)"),
            ("xx", "●丁凌全 2020/12 才第一次出現在申報名單(6,751 張),2026/10 持股 <b>13,888 張、設質 13,888 張(100%)</b>。"
                   "股價三週跌 31%;質押的股票跌價會被要求補擔保品,他的質押價位與成數查不到"),
            ("wn", "●<b>董監質押全部是丁凌全一個人的</b>:董事長劉祖英、董事兼總經理黃亞興質押 0、持股多年沒動。"
                   "丁凌全每次加碼後都把新買的也押進去(未質押 2025/9 有 1,164 張 → 12 月 0 張;2026/6 有 1,165 張 → 7 月 0 張),"
                   "是借錢加碼;現在沒有多餘的股票可以補擔保"),
            ("ok", "<b>「板新轉到嘉義去賣」不成立</b>:丁凌全的申報持股 2021 年以來只有兩個月減少(2022/1 少 73 張、2023/2 少 10 張),"
                   "永豐金-嘉義掛牌以來淨賣的 977 張不可能來自他。板新 10/7 高點 13,712 張後也只淨賣 223 張"),
            ("wn", "<b>永豐金-嘉義比較像融券放空的人</b>:2024/5/31 賣 341 張(當天全市場融券賣出 673 張);"
                   "2026/11/10~11 賣 160 張(融券賣出 259 張),11/16~17 融券「現券償還」243 張,11/6、11/13 兩週集保總股數約多了 420 張(用占比反推)。"
                   "時間對得上「先放空、再拿可轉債換來的股票還」;分點別的融券不公開,無法證實"),
            ("ok", "●<b>2024 年 6~7 月那批來源不明的賣壓,大部分是可轉債</b>:融券餘額從 5/24 的 461 張堆到 6/27 的 13,661 張,"
                   "6/27 股東會開完,6/28 起五個交易日現券償還 11,166 張;8/12 公告第二季可轉債換出 11,191 張新股,兩個數字只差 25 張。"
                   "?股東會前停止過戶期間不能轉換,是一般可轉債的規定,時碩的轉換辦法我沒讀"),
            ("xx", "<b>國票-敦北法人 2024/6/18 淨賣 2,497 張,四樣都對不上</b>:●6 月內部人申報只減 137 張(劉光弘 99、張仰欽 20、詹前偉 18)、"
                   "●當天沒有鉅額交易、●全市場融券賣出只有 595 張、●借券賣出 1 張。賣的是現股,持有人不在申報名單上,是誰查不到"),
            ("ok", "最近三週(10/29 起)賣最多的摩根士丹利、元大-天母、兆豐-台南、野村,賣之前自己的累計都夠——"
                   "是 7/20~10/28 買的貨,用不到匯撥來解釋"),
        ],
        todo=[("國票-敦北法人", "只在 2024 年活躍(買 8,077、賣 11,348 張)。下一步:年報前十大股東 2023 對 2024,看哪個不用申報的法人股東少了"),
              ("永豐金-嘉義", "12 月中看 11 月內部人月報;2027 年 3 月的增資基準日公告會結第四季轉換張數,對 11/10~11 那 160 張"),
              ("凱基-城中", "2024 第二季淨賣最多的第二名,和敦北法人同一段;2024/6/7 賣 1,497 張、6/17 買回 1,429 張"),
              ("永豐金-內湖", "●已對上:法人股東致伸科技 2018/10~2019/4 申報減少的 6 個月裡,4 個月和這個分點的淨賣吻合"),
              ("群益金鼎(總公司)", "2024/6/6 單日買 2,122 張、8/8 賣 1,091 張,累計還有 2,556 張"),
              ("美商高盛", "今年淨買 3,933 張,最近三週還買 1,632 張,是這波下跌最大的買方"),
              ("凱基-汐止", "掛牌以來淨賣約 4,800 張,年年都在賣,像原始股東的出貨點")]),
}


def fmt(x: float) -> str:
    return f"{x:+,.0f}" if x else "0"


def main(code: str, refresh: bool = False) -> str:
    code, name = resolve(code)
    d = bh.fetch(code, refresh=refresh)
    inv = bh.inventory(d)
    cut = inv.attrs["cut"]
    last = d.date.max()
    lots = bh.shares_lots(code)
    note = NOTES.get(code, {})
    date = now_tw().strftime("%Y%m%d")
    ycols = [c for c in inv.columns if c.isdigit()]
    span = f"{d.date.min():%Y/%m} ~ {last.month}/{last.day}"
    rng = f"{cut.month}/{cut.day}~{last.month}/{last.day}"
    pct = (lambda x: f"{x / lots * 100:.1f}%") if lots else (lambda x: "—")

    t1 = f"<table><tr><th>分點</th><th>買</th><th>賣</th><th>累計</th><th>占股本</th><th>{rng}</th></tr>"
    for br, r in inv.head(10).iterrows():
        t1 += (f'<tr><td>{br}</td><td class="n">{r["買"]:,.0f}</td><td class="n">{r["賣"]:,.0f}</td>'
               f'<td class="n rd">{fmt(r["累計"])}</td><td class="n">{pct(r["累計"])}</td><td class="n">{fmt(r["近期"])}</td></tr>')
    t1 += "</table>"
    c_top = card("📦 累計庫存最多的 10 個分點", t1
                 + '<div class="note">累計=掛牌以來買進減賣出(張)。買和賣都很大、累計很小的(外資、總公司)是來回交易;'
                   "買很多、賣很少的才是真的抱著。</div>", span)

    top = inv.index[0]
    b = d[d.br == top].assign(net=lambda x: x.buy - x.sell, y=lambda x: x.date.dt.year)
    yr = b.groupby("y").agg(buy=("buy", "sum"), sell=("sell", "sum"), net=("net", "sum"))
    yr["cum"] = yr.net.cumsum()
    t2 = "<table><tr><th>年</th><th>買</th><th>賣</th><th>淨</th><th>年底累計</th></tr>"
    for y, r in yr.iterrows():
        t2 += (f'<tr{" class=yl" if abs(r.net) >= 1000 else ""}><td class="n">{y}</td><td class="n">{r.buy:,.0f}</td>'
               f'<td class="n">{r.sell:,.0f}</td><td class="n">{fmt(r.net)}</td><td class="n">{r.cum:,.0f}</td></tr>')
    t2 += "</table>"
    big = b.reindex(b.net.abs().sort_values(ascending=False).index[:6]).sort_values("date")
    c_one = card(f"🔍 {top}:逐年", t2 + '<div class="note">單日最大的 6 筆:'
                 + "、".join(f"{r.date:%Y/%m/%d} {fmt(r.net)}" for r in big.itertuples()) + "</div>", "庫存第一名")

    neg = inv[inv["累計"] < 0].sort_values("累計")
    t3 = "<table><tr><th>分點</th><th>買</th><th>賣</th><th>累計</th><th>賣最多的一年</th></tr>"
    for br, r in neg.head(12).iterrows():
        wy = r[ycols].astype(float).idxmin()
        t3 += (f'<tr><td>{br}</td><td class="n">{r["買"]:,.0f}</td><td class="n">{r["賣"]:,.0f}</td>'
               f'<td class="n gn">{fmt(r["累計"])}</td><td class="n">{wy} 年 {fmt(r[wy])}</td></tr>')
    t3 += "</table>"
    big_neg = neg[neg["累計"] <= -400]
    c_neg = card("📤 賣的比買的多:貨不是在這裡買的", t3
                 + f'<div class="note">累計 −400 張以下的分點有 <b>{len(big_neg)}</b> 個,合計 {big_neg["累計"].sum():,.0f} 張'
                   + (f"(約占股本 {-big_neg['累計'].sum() / lots * 100:.0f}%)" if lots else "")
                   + "。這些股票的來源只可能是:掛牌前的原始股、配股、可轉債轉換、從別的帳戶匯撥進來、融券或借券。"
                     "<b>分點資料分不出是哪一種</b>。</div>", span)

    rec = inv[inv["近期"] < 0].sort_values("近期").head(12)
    t4 = f"<table><tr><th>分點</th><th>{rng} 淨賣</th><th>賣之前的累計</th><th>判定</th></tr>"
    n_short = 0
    for br, r in rec.iterrows():
        ok = r["之前累計"] >= -r["近期"]
        n_short += not ok
        t4 += (f'<tr{"" if ok else " class=yl"}><td>{br}</td><td class="n gn">{fmt(r["近期"])}</td><td class="n">{fmt(r["之前累計"])}</td>'
               f'<td>{"自己的庫存" if ok else "庫存不夠"}</td></tr>')
    t4 += "</table>"
    buyers = inv.sort_values("近期", ascending=False).head(4)
    c_rec = card("🧾 最近賣的人,賣的是不是自己買的", t4
                 + f'<div class="note">「庫存不夠」= 賣出的張數超過這個分點掛牌以來的累計。前 12 名賣方裡有 <b>{n_short}</b> 個。'
                   f'同期買最多:{"、".join(f"{br} {fmt(r)}" for br, r in buyers["近期"].items())}。</div>',
                 f"最近 14 個交易日")

    c_how = card("❓ 匯撥看不看得出來", checks([
        ("xx", "<b>匯撥本身看不到</b>。匯撥是把股票從一個帳戶轉到另一個帳戶,不是買賣,分點日報只記買賣"),
        ("ok", "<b>算得出來的是「庫存對不上」</b>:一個分點賣出的張數,超過它掛牌以來在這裡買進的張數,代表貨是從別處來的"),
        ("wn", "但「別處」有五種:掛牌前的原始股、配股、可轉債轉換、匯撥轉入、融券借券。這張表分不出來"),
        ("ok", "要再縮小範圍,就拿原始申報來對:內部人每月申報的持股、增資基準日公告(可轉債轉換)、融券的現券償還——"
               "「內部人申報 × 分點」和「新股從哪來」兩張表就是"),
        ("wn", "反過來也一樣:累計很多的分點,股票可能已經轉走了,從分點資料看不到")]))

    wmap = pd.read_csv(bh.ROOT / "data" / "warrants" / "_warrant_map.csv", dtype=str)
    nw = int((wmap.ucode == code).sum())
    c_w = card("🎟 權證", checks([
        ("wn" if nw == 0 else "ok",
         f"系統權證對照表({len(wmap):,} 筆)裡,以 {name} 為標的的權證有 <b>{nw}</b> 檔"
         + ("——這檔沒有權證可以對照" if nw == 0 else "")),
        ("ok", "有權證的股票做得到:同一個來源也查得到每檔權證的分點買賣,可以把「買股票的分點」和「買權證的分點」放在一起看")]))

    # ── 內部人月報 × 分點:申報的持股變動,對上哪個分點的當月淨買賣 ──
    ins = bh.insiders(code, refresh=refresh)
    c_ins = ""
    if len(ins):
        ly, lm = int(ins.y.iloc[-1]), int(ins.m.iloc[-1])
        mt = bh.insider_match(d, ins)
        mt = mt[(mt.hit >= 3) & (mt.hit * 2 >= mt.months)]
        body = ""
        for r in mt.head(2).itertuples():
            body += (f"<div><b>{r.name}</b> 對 <b>{r.br}</b>:持股變動 ≥50 張的 {r.months} 個月裡,"
                     f"{r.hit} 個月和分點當月淨買賣相差不到 10%</div>"
                     "<table><tr><th>月份</th><th>申報持股變動</th><th>分點當月淨買賣</th></tr>"
                     + "".join(f'<tr><td class="n">{ym // 100}/{ym % 100:02d}</td><td class="n">{fmt(x.chg)}</td>'
                               f'<td class="n">{fmt(x.net)}</td></tr>' for ym, x in r.detail.iterrows()) + "</table>")
        if not body:
            body = "<div>沒有哪一位內部人的持股變動,對得上任何分點的當月淨買賣。</div>"
        now = (ins[(ins.y == ly) & (ins.m == lm)].drop_duplicates("name").sort_values("hold", ascending=False).head(5))
        body += ("<table><tr><th>內部人</th><th>持股</th><th>設質</th><th>設質比</th></tr>"
                 + "".join(f'<tr><td>{r.name}<br><small>{r.title}</small></td><td class="n">{r.hold / 1000:,.0f}</td>'
                           f'<td class="n">{r.pledge / 1000:,.0f}</td>'
                           f'<td class="n{" rd" if r.hold and r.pledge / r.hold >= 0.9 else ""}">'
                           f'{(r.pledge / r.hold * 100 if r.hold else 0):.0f}%</td></tr>' for r in now.itertuples())
                 + "</table>"
                 '<div class="note">●公開資訊觀測站「董監事持股餘額明細」逐月原始申報(張)。分點日報不列客戶姓名,'
                 "這是數字比對;每月 15 日前申報上個月,最近一個月還看不到。</div>")
        c_ins = card("🪪 內部人申報 × 分點", body, f"月報到 {ly}/{lm:02d}")

    # ── 新股從哪來:增資基準日公告 × 融券現券償還 × 同期淨賣最多的分點 ──
    ns = bh.new_shares(code, refresh=refresh)
    c_conv = ""
    if len(ns):
        cw = bh.conv_windows(code, d, ns)
        kind = ns.assign(k=ns.title.map(lambda t: "可轉債轉換" if "轉換公司債" in t else "員工認股" if "員工" in t else "其他"))
        tot = "、".join(f"{k} {v / 1000:,.0f} 張" for k, v in kind.groupby("k").shares.sum().sort_values(ascending=False).items())
        num = lambda v: "—" if v is None or pd.isna(v) else f"{v:,.0f}"
        t5 = "<table><tr><th>轉換的那一季</th><th>新股</th><th>融券賣出</th><th>現券償還</th><th>同期淨賣最多的分點</th></tr>"
        for r in cw.itertuples():
            t5 += (f'<tr><td class="n">{r.q[:4]} {r.q[4:]}<br><small>{r.date:%Y/%m/%d} 公告</small></td><td class="n rd">{r.lots:,.0f}</td>'
                   f'<td class="n">{num(r.short_sell)}</td><td class="n">{num(r.short_redeem)}</td><td>{r.top}</td></tr>')
        t5 += "</table>"
        c_conv = card("🔁 新股從哪來:可轉債轉換 × 融券還券", (t5 if len(cw) else "<div>沒有單次 500 張以上的新股。</div>")
                      + f'<div class="note">●增資基準日公告(公開資訊觀測站),掛牌以來新股合計:{tot}。只列單次 500 張以上的;'
                        "公告結的是前一季申請轉換的股數,融券與分點也取那一季(往後移 7 天,等股票入帳)。"
                        "<b>現券償還</b>=拿手上的股票去還融券,不算買進——先融券放空、再用可轉債換來的股票還,"
                        "分點上就只看得到賣、看不到買回。融券資料從 2023 年起。</div>", "張")

    todo = note.get("todo", [])
    c_todo = card("🗂 接下來可以逐一研究的分點",
                  "<table><tr><th>分點</th><th>看到什麼</th></tr>"
                  + "".join(f"<tr><td><b>{a}</b></td><td>{b_}</td></tr>" for a, b_ in todo) + "</table>") if todo else ""

    c_risk = card("⚠️ 限制", checks([
        ("wn", f"分點名單來自各年與近期的買賣超前 15 名,共 {d.br.nunique()} 個;從沒排進前 15 的小分點沒有算到"),
        ("wn", "同一個分點有很多客戶,累計是全部客戶加總,不等於一個人"),
        ("wn", "總公司與外資分點混有自營、避險、借券,累計為負不代表有人出貨"),
        ("wn", "內部人只申報月底餘額,月中買了又賣看不到;卸任或不到 10% 的大股東不用申報,賣了也查不到"),
        ("wn", "分點別的融券、借券資料不公開;「先放空再用換來的股票還」是用全市場數字對時間,不能指名是哪個分點"),
        ("wn", "來源是富邦 DJ 的公開分點日報;這是研究筆記,不是買賣建議")]), extra_cls="risk")

    c_concl = card("📌 結論", checks(note["concl"])) if note.get("concl") else ""
    html = shell(
        title_html=f"{name}<b>({code})</b>分點庫存",
        subtitle=note.get("sub") or f"{inv.index[0]} 掛牌以來累計 {fmt(inv['累計'].iloc[0])} 張,庫存最多;累計為負的分點 {len(neg)} 個",
        brand=f"{name} 分點",
        cols=[c_concl + c_ins + c_w, c_how + c_top + c_one + c_todo, c_neg + c_conv + c_rec + c_risk],
        footer=f"{date[:4]}/{date[4:6]}/{date[6:]} · 資料:富邦 DJ 公開分點日報({span})、公開資訊觀測站內部人月報與增資公告、"
               "證交所融資融券、集保股權分散表、系統權證對照表 · 研究筆記,非投資建議")
    return str(save_poster(f"{name}分點", date, html))


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "4566", refresh="--refresh" in sys.argv))

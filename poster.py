# -*- coding: utf-8 -*-
"""
poster.py — 深度研究總整理「海報」引擎(2026-11-11 使用者指定版式)
=================================================================
範本:台玻(1802)深度研究總整理海報——亮底、密集卡片網格、紅字大數字、
綠勾結論、藍標題列、情境估值表、粉底風險卡。
與 newspaper.py(暗色報紙)並存:報紙=長文閱讀,海報=一屏總覽。
產出同樣進 data/papers/{code}海報_{date}.html,財經報頁同一選單可選。
"""
from __future__ import annotations

from newspaper import save_issue  # 同一儲存與列表機制

# 海報六類(2026-11-20 使用者核定:「就照這張表做」)。新海報先決定類型,再決定主角和順序——
# 不要每張都用「結論+四個數字」開頭。theme 是顏色;hero 是最上面該放什麼。
KINDS = {
    "stock":   {"name": "個股深度",   "theme": "",        "hero": "投資結論+財報大數字(台玻版式)"},
    "group":   {"name": "族群/產業鏈", "theme": "",        "hero": "成分股總表+鏈上位置"},
    "compare": {"name": "比較/挑選",   "theme": "compare", "hero": "比較表+橫條圖"},
    "event":   {"name": "事件研究",   "theme": "event",   "hero": "歷次走勢圖+歷次表+中位數"},
    "view":    {"name": "觀點查證",   "theme": "event",   "hero": "誰說了什麼(原話或轉述)+影響排名"},
    "scan":    {"name": "每日掃描",   "theme": "scan",    "hero": "排行榜"},
}
# 現有的非個股海報屬於哪一類(檔名「海報_」之前的部分);四位數代號一律個股;沒列到的當族群
NAMED_KIND = {"資安": "group", "國家政策": "group", "低軌衛星": "group", "金融": "group", "電子通路": "group", "統一集團": "group",
              "資安ETF": "compare", "選擇權SP防守": "compare", "內需防禦": "event", "限空令": "event", "流動性凍結": "event", "跳空漲停": "event", "季節與展覽": "event", "銀行停水": "event", "內部人質押": "event", "金融海嘯對照": "event",
              "AI支出下修": "view", "族群強弱": "scan", "避險掃描": "scan", "錯殺": "scan", "轉虧為盈": "scan", "時碩工業分點": "stock"}


def kind_of(filename: str) -> str:
    stem = filename.split("海報_")[0]
    if stem.isdigit() and len(stem) == 4:
        return "stock"
    return NAMED_KIND.get(stem, "group")


def wrap_open(kind: str) -> str:
    th = KINDS.get(kind, {}).get("theme", "")
    cls = "wrap" + (f" t-{th}" if th else "") + (f" k-{kind}" if kind else "")
    return f'<div class="{cls}" data-kind="{kind}">' if kind else '<div class="wrap">'

CSS = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#dfe4ea;font-family:'Microsoft JhengHei','Noto Sans TC',sans-serif;
  color:#1c2733;line-height:1.5;font-size:14px}
.wrap{max-width:1640px;margin:0 auto;padding:10px}
.hd{background:linear-gradient(100deg,#0d2b52 0%,#123c6e 70%,#1b5fa8 100%);color:#fff;
  border-radius:8px;padding:10px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.hd h1{font-size:25px;font-weight:900;letter-spacing:.5px}
.hd h1 b{color:#ffd84d}
.hd .sub{font-size:13px;margin-top:3px;color:#cfe2ff;font-weight:700}
.hd .brand{text-align:right;font-size:11px;color:#9fc3f0;white-space:nowrap}
.hd .brand .bx{border:2px solid #ffd84d;color:#ffd84d;font-weight:900;font-size:13.5px;
  padding:2px 8px;border-radius:6px;display:inline-block;margin-bottom:2px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;align-items:stretch}
.col{display:flex;flex-direction:column;gap:8px;min-width:0}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(13,43,82,.2);overflow:hidden;
  display:flex;flex-direction:column}
.card.grow{flex:1}
.card.grow .cb{flex:1;display:flex;flex-direction:column}
.card.grow .cb .flow{flex:1;justify-content:space-between}
.card.grow .cb ul.ck{flex:1;display:flex;flex-direction:column;justify-content:space-evenly}
.card .ct{background:#0d2b52;color:#fff;font-weight:900;font-size:15.5px;padding:6px 11px;
  display:flex;justify-content:space-between;align-items:baseline}
.card .ct small{color:#9fc3f0;font-weight:400;font-size:11px}
.card .cb{padding:9px 11px}
ul.ck{list-style:none}
ul.ck li{padding:4px 0 4px 26px;position:relative;font-size:13.8px;font-weight:700}
ul.ck li::before{content:"✔";position:absolute;left:2px;color:#15903f;font-weight:900}
ul.ck li.wn::before{content:"⚠";color:#d98400}
ul.ck li.xx::before{content:"✘";color:#c0392b}
ul.ck li b{color:#c0392b}
.bignums{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;text-align:center}
.bn{background:#f2f6fb;border:1px solid #d7e3f2;border-radius:8px;padding:8px 4px}
.bn .k{font-size:12.5px;color:#456;font-weight:800}
.bn .v{font-size:23px;font-weight:900;color:#c0392b;font-family:Arial,sans-serif;letter-spacing:-.5px}
.bn .d{font-size:11.5px;color:#567;font-weight:700}
.up2{color:#c0392b;font-weight:800}.dn2{color:#15903f;font-weight:800}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:2px 0}
th{background:#eaf1f9;color:#0d2b52;font-weight:900;padding:5px 7px;text-align:left;border:1px solid #d7e3f2}
td{padding:5px 7px;border:1px solid #e4ebf4;font-weight:700}
td.n{font-family:Arial;font-weight:800}
.rd{color:#c0392b}.gn{color:#15903f}.yl{background:#fff6d6}
.flow{display:flex;flex-direction:column;gap:5px}
.fbox{background:#eaf3ff;border:1.5px solid #8fb7e8;border-radius:8px;padding:6px 10px;
  font-size:13px;font-weight:700;text-align:center;color:#0d2b52}
.fbox small{display:block;color:#567;font-weight:600;font-size:11.5px}
.fbox.hot{background:#fff3f0;border-color:#e8a194;color:#a03022}
.farr{text-align:center;color:#1b5fa8;font-weight:900;line-height:.9}
.donutrow{display:flex;gap:12px;align-items:center}
.donut{width:128px;height:128px;border-radius:50%;flex:none;position:relative}
.donut::after{content:attr(data-c);position:absolute;inset:32px;background:#fff;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;color:#0d2b52;text-align:center}
.lg{font-size:13px;flex:1}
.lg div{display:flex;align-items:center;gap:6px;padding:2.5px 0;font-weight:700}
.lg i{width:11px;height:11px;border-radius:3px;flex:none}
.lg small{color:#567;font-weight:600;margin-left:auto;text-align:right}
.bars{display:flex;gap:16px;align-items:flex-end;min-height:96px;margin-top:10px;padding:4px 6px 0;justify-content:center}
.bar{width:64px;text-align:center;font-size:11.5px;font-weight:800;color:#345}
.bar i{display:block;border-radius:4px 4px 0 0}
.bar .pv{color:#c0392b;font-size:13px;font-family:Arial}
.risk{background:#fdf0f2}
.risk .ct{background:#8e2437}
.risk ul.ck li::before{content:"⚠";color:#c0392b}
.note{font-size:11.5px;color:#678;margin-top:4px;line-height:1.45}
.ft{text-align:center;font-size:11.5px;color:#56687e;margin-top:10px}
.rows{display:flex;flex-direction:column;gap:8px}
.row{display:grid;gap:8px;align-items:stretch}
.row.r1{grid-template-columns:1fr}.row.r2{grid-template-columns:1fr 1fr}.row.r3{grid-template-columns:repeat(3,1fr)}
.row.r21{grid-template-columns:2fr 1fr}.row.r12{grid-template-columns:1fr 2fr}
.card .src{font-size:11.5px;color:#678;font-weight:600;line-height:1.45;margin-top:6px}
/* 2026-11-19 版面修正(使用者:「字體調整 要不然海報要更大吧?」「有人海報空一堆嗎?」)
   原本固定 1180px 切三欄:每欄 385px,表格被擠爛;後來改一列一列對齊,短卡片旁邊又留一大塊空白。
   現在:卡片照順序由上往下流,瀏覽器自動把各欄排到一樣高(不留洞);七欄以上的表格自動佔滿整列。
   一般寬度兩欄,≥1500px 三欄,手機一欄。舊海報的三個 .col 只是容器,拆掉讓卡片一起流。 */
.card .ct{flex-wrap:wrap;gap:0 10px}
.card .ct small{flex:1 1 170px;text-align:right}
.card .cb{overflow-x:auto}
td.n{white-space:nowrap}
.bn .v{white-space:nowrap}
.bignums{grid-template-columns:repeat(auto-fit,minmax(118px,1fr))}
.bn{padding:8px 2px}
.bn .v{font-size:20px;letter-spacing:-.8px}
.grid,.flowc{display:block;column-count:2;column-gap:8px}
.grid>.col{display:contents}
.grid .card,.flowc>.card{break-inside:avoid;margin-bottom:8px}
.grid .card:has(th:nth-child(7)){column-span:all}
.flowc>.wide{column-span:all;margin-bottom:8px}
.flowc>.wide>.card{margin-bottom:0}
.row>.col>.card:last-child{flex:1}
svg.ch{width:100%;height:auto;display:block}
a.sl{color:inherit;text-decoration:underline dotted #7a8aa0;text-underline-offset:3px;cursor:pointer}
a.sl:hover{color:#1b5fa8;text-decoration:underline}
.hd a.sl{font-size:13px;font-weight:700;margin-left:10px;color:#cfe2ff}
.lgd{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;font-weight:700;color:#345;margin-bottom:4px}
.lgd i{display:inline-block;width:18px;height:4px;border-radius:2px;vertical-align:middle;margin-right:5px}
.hb{display:grid;grid-template-columns:auto 1fr;gap:3px 8px;align-items:center;font-size:12.5px;font-weight:700}
.hb .bar1{height:11px;border-radius:0 4px 4px 0;display:inline-block;vertical-align:middle}
.hb .val{font-family:Arial;font-weight:800;margin-left:5px;font-size:12px}
@media (min-width:1500px){.grid,.flowc{column-count:3}}
@media (max-width:900px){.grid,.flowc{column-count:1}
  .row.r2,.row.r3,.row.r21,.row.r12{grid-template-columns:1fr}}
/* 排版程式跑完後的狀態(.pk):卡片已分進各欄,欄底拉齊 */
.pk{column-count:1 !important;display:flex !important;flex-direction:column;gap:8px}
.pk .card,.pk>.wide{margin-bottom:0 !important}
.pkrow{display:flex;gap:8px;align-items:stretch}
.pkcol{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:8px}
.pkcol>.card{flex:1 1 auto}
.pking .pkrow{align-items:flex-start}
.pking .pkcol>.card{flex:none}
/* 題材風格:個股=深藍(預設)、比較型=青綠、事件研究=深灰琥珀 */
.t-compare .hd{background:linear-gradient(100deg,#0a3338 0%,#0f4c52 70%,#16868c 100%)}
.t-compare .card .ct{background:#0d4046}
.t-compare th{background:#e6f3f3;color:#0d4046}
.t-compare .hd .sub{color:#c9eef0}.t-compare .hd .brand{color:#9fd8dc}
.t-event .hd{background:linear-gradient(100deg,#1c222b 0%,#2f3945 70%,#6b4a12 100%)}
.t-event .hd h1 b{color:#ffb74d}.t-event .hd .brand .bx{border-color:#ffb74d;color:#ffb74d}
.t-event .card .ct{background:#27303b}
.t-event th{background:#eef0f3;color:#27303b}
.t-event .hd .sub{color:#e3e8ee}.t-event .hd .brand{color:#b9c2cd}
.t-scan .hd{background:linear-gradient(100deg,#1d1838 0%,#2e2660 70%,#5a3fa0 100%)}
.t-scan .hd h1 b{color:#ffd84d}.t-scan .card .ct{background:#2a2350}
.t-scan th{background:#eeecf7;color:#2a2350}
.t-scan .hd .sub{color:#e0dcf5}.t-scan .hd .brand{color:#b9b0e0}
.t-event .risk .ct,.t-compare .risk .ct,.t-scan .risk .ct{background:#8e2437}
</style>
<script id="pk">
(function(){
  // 排版:先量每張卡片在一欄寬度下的高度;放不下(表格會被切)的卡片改佔整列;
  // 其餘的在每一段裡「由高到低、放進目前最短的那一欄」,欄內再照原本順序排;最後各欄拉到一樣高。
  function nth(el){var m=0;el.querySelectorAll('tr').forEach(function(r){var k=r.querySelectorAll('th').length;if(k>m)m=k;});return m;}
  function pack(){
    var c=document.querySelector('.grid,.flowc'); if(!c) return;
    if(!c._items){
      var it=[];
      if(c.classList.contains('grid')) c.querySelectorAll('.col > .card').forEach(function(x){it.push(x);});
      else Array.prototype.forEach.call(c.children,function(x){it.push(x);});
      // 每日掃描類:主角是排行榜——沒有指定滿寬區塊時,把最大的那張表移到最前面、佔滿整列
      var w=document.querySelector('.wrap'), kind=w&&w.dataset?w.dataset.kind:'';
      if(kind==='scan'&&!it.some(function(x){return x.classList.contains('wide');})){
        var bi=-1,bs=0; it.forEach(function(x,i){var s=x.querySelectorAll('tr').length*nth(x); if(s>bs){bs=s;bi=i;}});
        if(bi>=0&&bs>=40){var h=it.splice(bi,1)[0]; h.classList.add('wide'); it.unshift(h);}
      }
      c._items=it;
    }
    var W=c.clientWidth, n=W>=1500?3:(W>=900?2:1);
    if(c._n===n) return; c._n=n;
    while(c.firstChild) c.removeChild(c.firstChild);
    c.classList.add('pk');c.classList.add('pking');
    if(n===1){c._items.forEach(function(el){c.appendChild(el);});c.classList.remove('pking');return;}
    var colW=(W-8*(n-1))/n;
    var probe=document.createElement('div');probe.className='pkcol';probe.style.cssText='flex:none;width:'+colW+'px';
    c.appendChild(probe);
    var info=c._items.map(function(el,i){
      if(el.classList.contains('wide')) return {el:el,wide:true,i:i};
      probe.appendChild(el);
      var cb=el.querySelector('.cb'), ov=!!cb&&cb.scrollWidth>cb.clientWidth+2, h=el.offsetHeight;
      probe.removeChild(el);
      return {el:el,wide:ov,h:h,i:i};
    });
    c.removeChild(probe);
    var seg=[];
    function flush(){
      if(!seg.length) return;
      // 欄數:先試最多欄;各欄高度差超過 200px(一張大卡片把某一欄撐高)就少一欄再試,至少兩欄
      function lay(k){var cs=[];for(var j=0;j<k;j++) cs.push({h:0,items:[]});
        seg.slice().sort(function(x,y){return y.h-x.h;}).forEach(function(it){
          var best=cs[0]; cs.forEach(function(d){if(d.h<best.h) best=d;});
          best.items.push(it); best.h+=it.h+8;});
        var hi=0,lo=1e9; cs.forEach(function(d){if(d.h>hi)hi=d.h;if(d.h<lo)lo=d.h;});
        return {cs:cs,imb:hi-lo};}
      var k=Math.min(n,seg.length), pick=lay(k);
      while(k>2&&pick.imb>200){var alt=lay(k-1); if(alt.imb<pick.imb){pick=alt;k--;} else break;}
      var cols=pick.cs, r=document.createElement('div'); r.className='pkrow';
      cols.forEach(function(d){d.items.sort(function(x,y){return x.i-y.i;});});
      cols.sort(function(x,y){return x.items[0].i-y.items[0].i;});
      cols.forEach(function(d){var e=document.createElement('div');e.className='pkcol';
        d.items.forEach(function(it){e.appendChild(it.el);}); r.appendChild(e);});
      c.appendChild(r); seg=[];
    }
    info.forEach(function(it){ if(it.wide){flush();c.appendChild(it.el);} else seg.push(it); });
    flush();
    c.classList.remove('pking');
  }
  var t; function later(){clearTimeout(t);t=setTimeout(pack,120);}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',pack); else pack();
  window.addEventListener('load',function(){var c=document.querySelector('.grid,.flowc');if(c){c._n=0;pack();}});
  window.addEventListener('resize',later);
})();
</script>
"""


def shell(title_html: str, subtitle: str, brand: str, cols: list[str], footer: str) -> str:
    grid = "".join(f'<div class="col">{c}</div>' for c in cols)
    return f"""<title>{subtitle[:20]}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{CSS}
<div class="wrap">
<div class="hd"><div><h1>{title_html}</h1><div class="sub">{subtitle}</div></div>
<div class="brand"><span class="bx">{brand}</span><br>TW·BACKTEST 深度研究</div></div>
<div class="grid">{grid}</div>
<div class="ft">{footer}</div></div>"""


def shell_flow(title_html: str, subtitle: str, brand: str, blocks: list, footer: str, kind: str = "stock") -> str:
    """卡片流版式(2026-11-19):blocks 照閱讀順序給。
    字串=一張(或幾張)卡片,照順序往下流、各欄自動排到一樣高,不留空洞;
    ("wide", html)=佔滿整列——放這個題材的主角(大表、走勢圖),或用 row() 並排兩塊。
    每個題材的主角不一樣:比較型放比較表、事件型放走勢圖、個股型放結論,不要每張都同一個開頭。
    kind:KINDS 的六類之一,決定顏色;主角(hero)由呼叫的人照 KINDS[kind]["hero"] 放在 blocks 最前面。
    卡片分欄由海報裡的小程式做(放進當下最短的那一欄、欄底拉齊),所以不會有空洞。"""
    out = "".join(f'<div class="wide">{b[1]}</div>' if isinstance(b, tuple) else b for b in blocks)
    return f"""<title>{subtitle[:20]}</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{CSS}
{wrap_open(kind)}
<div class="hd"><div><h1>{title_html}</h1><div class="sub">{subtitle}</div></div>
<div class="brand"><span class="bx">{brand}</span><br>TW·BACKTEST 深度研究</div></div>
<div class="flowc">{out}</div>
<div class="ft">{footer}</div></div>"""


def row(cells: list, kind: str = "") -> str:
    """整列裡並排幾塊(放進 ("wide", row([...])));kind="21"/"12" 是 2:1 / 1:2。每一欄最後一張卡片會撐到等高。"""
    cls = f"r{kind}" if kind else f"r{len(cells)}"
    return f'<div class="row {cls}">' + "".join(f'<div class="col">{c}</div>' for c in cells) + "</div>"


def hbars(items: list, unit: str = "%") -> str:
    """橫條圖:items=[(標籤, 數值, 顏色)];負值畫灰色、往右一樣長度(數字照寫)。"""
    mx = max(abs(v) for _, v, _ in items) or 1
    return ('<div class="hb">' + "".join(
        f'<div>{k}</div><div><span class="bar1" style="width:{abs(v) / mx * 78:.1f}%;background:{c if v >= 0 else "#9aa5b1"}"></span>'
        f'<span class="val">{v:+g}{unit}</span></div>' for k, v, c in items) + "</div>")


def dbars(rows: list, left: str, right: str, cols: list, unit: str = "%",
          c_left: str = "#2f6db5", c_right: str = "#e07b00") -> str:
    """左右分開的橫條圖(中間是 0):正值往右、負值往左,一列一項。
    rows=[(標籤, 數值, [右側數字欄...], 滑鼠提示)];cols=右側數字欄的欄名。
    負值不是「下跌」時一定要用這個,不要用 hbars(hbars 把負值也畫成往右,會被看成跌幅)。"""
    lo = min(-10.0, min(v for _, v, _, _ in rows))
    hi = max(10.0, max(v for _, v, _, _ in rows))
    span = hi - lo
    z = -lo / span * 100
    n = len(cols)
    grid = f"display:grid;grid-template-columns:auto minmax(190px,1fr){' auto' * n};gap:4px 8px;align-items:center;font-size:13px"
    head = ('<div></div><div style="display:flex;justify-content:space-between;font-size:11.5px;color:#5b6673">'
            f'<span style="color:{c_left};font-weight:700">◀ {left}</span><span style="color:{c_right};font-weight:700">{right} ▶</span></div>'
            + "".join(f'<div style="font-size:11.5px;color:#5b6673;text-align:right;white-space:nowrap">{c}</div>' for c in cols))
    out = [head]
    for k, v, extra, tip in rows:
        w = abs(v) / span * 100
        if v >= 0:
            bar = (f'<span style="position:absolute;top:2px;bottom:2px;left:{z:.2f}%;width:{w:.2f}%;background:{c_right};border-radius:0 4px 4px 0"></span>'
                   f'<span style="position:absolute;top:0;left:calc({z + w:.2f}% + 5px);font-weight:700;white-space:nowrap">{v:+g}{unit}</span>')
        else:
            bar = (f'<span style="position:absolute;top:2px;bottom:2px;left:{z - w:.2f}%;width:{w:.2f}%;background:{c_left};border-radius:4px 0 0 4px"></span>'
                   f'<span style="position:absolute;top:0;right:calc({100 - z + w:.2f}% + 5px);font-weight:700;white-space:nowrap">{v:+g}{unit}</span>')
        axis = f'<span style="position:absolute;top:-2px;bottom:-2px;left:{z:.2f}%;width:1px;background:#8a94a0"></span>'
        out.append(f'<div style="white-space:nowrap" title="{tip}"><b>{k}</b></div>'
                   f'<div style="padding:0 46px" title="{tip}"><div style="position:relative;height:19px;line-height:19px">{axis}{bar}</div></div>'
                   + "".join(f'<div class="n" style="text-align:right;white-space:nowrap">{e}</div>' for e in extra))
    return f'<div style="{grid}">' + "".join(out) + "</div>"


def slink(code: str, text: str = "") -> str:
    """個股連結(2026-11-24 使用者:「個股有做的都可以連結過去」):點了開 app 的 /個股?code=…。
    海報是嵌在 app 裡的 iframe(Streamlit 的 sandbox 不准換掉整頁),所以用 target=_blank 開新分頁;
    相對網址在 srcdoc iframe 裡會接到 app 自己的位址。直接用瀏覽器開海報檔時這個連結沒有作用。"""
    return f'<a class="sl" href="/個股?code={code}" target="_blank" rel="noopener">{text or code}</a>'


def ud(x: float, txt: str = "") -> str:
    """上升/下降指標:▲紅/▼綠(台股紅漲綠跌);txt 省略時用 x 自己。"""
    t = txt or f"{x:+g}"
    if x > 0:
        return f'<span class="up2">▲{t.lstrip("+")}</span>'
    if x < 0:
        return f'<span class="dn2">▼{t.lstrip("-")}</span>'
    return f"<span>{t}</span>"


def card(title: str, body: str, src: str = "", extra_cls: str = "") -> str:
    # 來源說明短的放標題列右邊;長的放卡片底部——長字串擠在標題列會把標題壓成直排
    if len(src) > 14:
        return (f'<div class="card {extra_cls}"><div class="ct">{title}</div>'
                f'<div class="cb">{body}<div class="src">{src}</div></div></div>')
    s = f"<small>{src}</small>" if src else ""
    return f'<div class="card {extra_cls}"><div class="ct">{title}{s}</div><div class="cb">{body}</div></div>'


def checks(items: list[tuple[str, str]]) -> str:
    """items: [(kind, html)] kind ∈ ok/wn/xx"""
    cls = {"ok": "", "wn": ' class="wn"', "xx": ' class="xx"'}
    return "<ul class='ck'>" + "".join(f"<li{cls[k]}>{t}</li>" for k, t in items) + "</ul>"


def bignums(items: list[tuple[str, str, str]]) -> str:
    """items: [(標題, 大數字, 副註)]"""
    return ('<div class="bignums">'
            + "".join(f'<div class="bn"><div class="k">{k}</div><div class="v">{v}</div>'
                      f'<div class="d">{d}</div></div>' for k, v, d in items) + "</div>")


PAL = ["#2f6db5", "#f0a63a", "#8a63b5", "#4cae6e", "#d16a6a", "#6fc3d4"]


def donut(center: str, parts: list[tuple[str, float, str]]) -> str:
    """parts: [(名稱, 佔比, 註)] → conic-gradient 圓環+圖例"""
    stops, acc = [], 0.0
    for i, (_, pct, _n) in enumerate(parts):
        stops.append(f"{PAL[i % len(PAL)]} {acc}% {acc + pct}%")
        acc += pct
    if acc < 100:
        stops.append(f"#cfd8e3 {acc}% 100%")
    lg = "".join(f'<div><i style="background:{PAL[i % len(PAL)]}"></i>{n} <b>{p:g}%</b>'
                 f'<small>{note}</small></div>' for i, (n, p, note) in enumerate(parts))
    return (f'<div class="donutrow"><div class="donut" data-c="{center}" '
            f'style="background:conic-gradient({",".join(stops)})"></div>'
            f'<div class="lg">{lg}</div></div>')


def bars(items: list[tuple[str, float, str]], unit: str = "%") -> str:
    """items: [(標籤, 數值, 顏色)] 簡易長條圖"""
    mx = max(v for _, v, _ in items) or 1
    return ('<div class="bars">'
            + "".join(f'<div class="bar"><span class="pv">{v:g}{unit}</span>'
                      f'<i style="height:{max(6, v / mx * 64)}px;background:{c}"></i>{k}</div>'
                      for k, v, c in items) + "</div>")


def flow(boxes: list[tuple[str, str, bool]]) -> str:
    """boxes: [(主文, 小註, 是否標紅)]"""
    out = []
    for i, (t, s, hot) in enumerate(boxes):
        if i:
            out.append('<div class="farr">▼</div>')
        out.append(f'<div class="fbox{" hot" if hot else ""}">{t}'
                   + (f"<small>{s}</small>" if s else "") + "</div>")
    return f'<div class="flow">{"".join(out)}</div>'


def save_poster(code: str, date: str, html: str):
    return save_issue(f"{code}海報", date, html)

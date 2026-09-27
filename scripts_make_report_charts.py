# -*- coding: utf-8 -*-
"""報告用 PNG 圖表生成(深色面配文章閱讀頁)。跑一次輸出到 data/research_articles/img/"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "data" / "research_articles" / "img"
OUT.mkdir(parents=True, exist_ok=True)

# 深色面+字體
SURF, INK, MUTED, GRID = "#11161F", "#E6EDF3", "#8B98A8", "#26303F"
BLUE, ORANGE, BLUE_L = "#3B82F6", "#E8873A", "#93BBFB"
plt.rcParams.update({
    "font.family": "Microsoft JhengHei", "axes.unicode_minus": False,
    "figure.facecolor": SURF, "axes.facecolor": SURF,
    "text.color": INK, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 12,
})


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def bar_labels(ax, bars, fmt="{:.1f}", dy=0.0):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + dy,
                fmt.format(b.get_height()), ha="center", va="bottom",
                color=INK, fontsize=11)


# ── 3042 ① ASP 階梯(sequential 單色調深淺) ──
fig, ax = plt.subplots(figsize=(7, 3.2))
names, vals = ["800G", "1.6T\n(放量中)", "3.2T\n(2027量產)"], [1.5, 2.25, 7.0]
shades = ["#7FB0F9", "#3B82F6", "#1D5FD6"]
bars = ax.barh(names, vals, color=shades, height=0.55)
for b, v, t in zip(bars, vals, ["~1.5", "~2~2.5", "~7(4倍以上)"]):
    ax.text(v + 0.12, b.get_y() + b.get_height() / 2, f"{t} 美元",
            va="center", color=INK, fontsize=12)
ax.set_xlim(0, 8.6)
ax.set_title("光模組石英元件 ASP 階梯(法說:每機櫃時脈價值 +50%)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="y", visible=False)
_save(fig, "3042_asp.png")

# ── 3042 ② 營收組合 2025 vs 2026E ──
cats = ["AI應用", "車用電子", "行動通訊", "行動運算", "網絡通訊", "其他消費"]
y25, y26 = [11, 26, 29, 10, 9, 15], [16, 28, 24, 9, 9, 14]
fig, ax = plt.subplots(figsize=(7, 3.6))
ypos = range(len(cats))
b1 = ax.barh([y - 0.2 for y in ypos], y25, height=0.38, color=ORANGE, label="2025")
b2 = ax.barh([y + 0.2 for y in ypos], y26, height=0.38, color=BLUE, label="2026(E)")
ax.set_yticks(list(ypos), cats)
ax.invert_yaxis()
for bs in (b1, b2):
    for b in bs:
        ax.text(b.get_width() + 0.4, b.get_y() + b.get_height() / 2,
                f"{b.get_width():.0f}%", va="center", color=INK, fontsize=10)
ax.set_xlim(0, 34)
ax.legend(loc="lower right", frameon=False, labelcolor=INK)
ax.set_title("營收組合換血:雙A(AI+車用)44%,消費讓位(法說頁10)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="y", visible=False)
_save(fig, "3042_mix.png")

# ── 3042 ③ 十年 EPS 與股利 ──
yrs = list(range(2015, 2026))
eps = [3.03, 3.28, 3.11, 2.08, 2.17, 4.61, 10.06, 9.06, 5.53, 6.55, 5.28]
div = [2.5, 2.8, 2.5, 2.0, 2.5, 3.8, 7.5, 7.0, 4.5, 5.2, 4.8]
fig, ax = plt.subplots(figsize=(7.6, 3.4))
x = range(len(yrs))
ax.bar([i - 0.2 for i in x], eps, width=0.4, color=BLUE, label="EPS")
ax.bar([i + 0.2 for i in x], div, width=0.4, color=ORANGE, label="現金股利")
ax.set_xticks(list(x), [str(y) for y in yrs], fontsize=10)
ax.legend(frameon=False, labelcolor=INK)
ax.set_ylabel("元")
ax.set_title("十年 EPS 與股利:平均配息率 80%+(下檔的殖利率地板)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="x", visible=False)
_save(fig, "3042_div.png")

# ── 3055 ① 季毛利率轉折 ──
q = ["25Q1", "25Q2", "25Q3", "25Q4", "26Q1", "26Q2"]
gm = [8.59, 24.72, 1.88, 16.83, 31.88, 31.72]
fig, ax = plt.subplots(figsize=(7, 3.3))
cols = ["#5A6B84"] * 4 + [BLUE, BLUE]
bars = ax.bar(q, gm, color=cols, width=0.6)
bar_labels(ax, bars, "{:.1f}", 0.5)
ax.axvline(3.5, color=ORANGE, lw=1.2, ls="--")
ax.text(1.6, 36.2, "→ 2026/04 自有機台 SP8000S 首批出貨", color=ORANGE, fontsize=11)
ax.set_ylim(0, 41)
ax.set_ylabel("毛利率 %")
ax.set_title("蔚華科毛利率轉折:代理毛利 → 自有機台毛利(轉型的財務指紋)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="x", visible=False)
_save(fig, "3055_margin.png")

# ── 3055 ② 月營收(設備認列顛簸) ──
ym = ["25/09", "25/10", "25/11", "25/12", "26/01", "26/02", "26/03", "26/04",
      "26/05", "26/06", "26/07", "26/08"]
rev = [60.3, 12.6, 16.9, 58.7, 48.5, 8.2, 27.4, 126.1, 22.5, 13.8, 41.7, 47.6]
fig, ax = plt.subplots(figsize=(7.6, 3.3))
cols = [BLUE if v == max(rev) else "#5A6B84" for v in rev]
bars = ax.bar(ym, rev, color=cols, width=0.62)
ax.text(7, 128, "4月 126.1(+336%)\n=SP8000S 認列", ha="center", color=INK, fontsize=11)
ax.set_ylabel("百萬元")
ax.set_xticklabels(ym, rotation=45, ha="right", fontsize=9)
ax.set_title("月營收=設備認列時點,顛簸是天性(勿用「腰斬=掉單」直線推論)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="x", visible=False)
_save(fig, "3055_rev.png")

# ── 4764 ① 季度獲利轉折(雙線同軸%) ──
q4 = ["25Q3", "25Q4", "26Q1", "26Q2"]
gm4 = [17.97, 23.49, 26.53, 27.02]
op4 = [3.53, 7.74, 14.65, 14.81]
fig, ax = plt.subplots(figsize=(7, 3.3))
ax.plot(q4, gm4, "-o", color=BLUE, lw=2.2, ms=7, label="毛利率")
ax.plot(q4, op4, "-o", color=ORANGE, lw=2.2, ms=7, label="營益率")
for xx, yy in zip(q4, gm4):
    ax.text(xx, yy + 0.9, f"{yy:.1f}", ha="center", color=INK, fontsize=10)
for xx, yy in zip(q4, op4):
    ax.text(xx, yy - 2.3, f"{yy:.1f}", ha="center", color=INK, fontsize=10)
ax.set_ylim(0, 32)
ax.set_ylabel("%")
ax.legend(frameon=False, labelcolor=INK, loc="center right")
ax.set_title("雙鍵獲利結構連四季上台階(電子材料放量的指紋)",
             color=INK, fontsize=13, loc="left")
_save(fig, "4764_turn.png")

# ── 4764 ② 季EPS vs 期間股價註記 ──
eps4 = [0.24, 0.60, 1.03, 1.23]
fig, ax = plt.subplots(figsize=(7, 3.2))
bars = ax.bar(q4, eps4, color=BLUE, width=0.5)
bar_labels(ax, bars, "{:.2f}", 0.02)
ax.set_ylabel("EPS(元)")
ax.set_title("季 EPS 連四季創高——同期股價自 365 高點腰斬至 183(背離=本文命題)",
             color=INK, fontsize=12.5, loc="left")
ax.grid(axis="x", visible=False)
_save(fig, "4764_gap.png")

# ── 6218 ① 1H25 vs 1H26 ──
items = ["營業收入", "營業毛利", "營業淨利"]
h25, h26 = [722.5, 90.7, -56.3], [800.9, 183.9, 52.9]
fig, ax = plt.subplots(figsize=(7, 3.3))
x = range(3)
b1 = ax.bar([i - 0.2 for i in x], h25, width=0.4, color=ORANGE, label="1H25")
b2 = ax.bar([i + 0.2 for i in x], h26, width=0.4, color=BLUE, label="1H26")
ax.set_xticks(list(x), items)
for bs in (b1, b2):
    for b in bs:
        v = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, v + (12 if v >= 0 else -34),
                f"{v:,.0f}", ha="center", color=INK, fontsize=10)
ax.axhline(0, color=MUTED, lw=0.8)
ax.set_ylabel("百萬元")
ax.legend(frameon=False, labelcolor=INK)
ax.set_title("豪勉 1H 對比:毛利 +103%、營業淨利轉正(本業翻身是真的)",
             color=INK, fontsize=13, loc="left")
ax.grid(axis="x", visible=False)
_save(fig, "6218_1h.png")

# ── 6218 ② 營收組成 ──
seg = ["資訊網路週邊", "維修收入", "半導體代理+自製", "勞務+其他"]
pct = [69, 16, 10, 5]
fig, ax = plt.subplots(figsize=(7, 2.8))
shades6 = ["#1D5FD6", "#3B82F6", "#7FB0F9", "#B9D3FC"]
left = 0
for s, p, c in zip(seg, pct, shades6):
    ax.barh([0], [p], left=left, color=c, height=0.5)
    ax.text(left + p / 2, 0, f"{s}\n{p}%", ha="center", va="center",
            color="#FFFFFF" if p > 8 else INK, fontsize=10.5)
    left += p + 0.4
ax.set_xlim(0, 102)
ax.axis("off")
ax.set_title("1H26 營收組成:七成是資通訊維運現金牛,自製設備僅一成(重評的鑰匙)",
             color=INK, fontsize=12.5, loc="left")
_save(fig, "6218_mix.png")

print("all done ->", OUT)

"""
product_mix.py — 產品組合佔比(法說結構化數據層)
=================================================================
法說會講的「產品佔營收%」(如欣興:ABF載板 vs HDI vs 傳統PCB)結構化儲存:
  data/product_mix.json(進 git,雲端同步):
  {code: {"versions": [{"as_of": "2026-Q2", "source": "8/19法說",
                        "items": [{"產品": "...", "佔比%": 55, "毛利註記": "高"}...]}]}}
版本化:每次法說更新新增一版,舊版保留(看組合遷移軌跡)。
報告注入:analyst_report.build_digest 自動帶最新版──模型從此知道產品結構,
不再寫「產品結構待查」。
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).parent
PATH = ROOT / "data" / "product_mix.json"


def _load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def set_mix(code: str, as_of: str, source: str, items: list[dict]) -> str:
    """存一版產品組合。items: [{"產品":..., "佔比%":..., "毛利註記":...}];
    佔比合計偏離 100±15 會回警告(仍存,佔比可能只涵蓋主要產品)。"""
    d = _load()
    d.setdefault(code, {}).setdefault("versions", [])
    # 同 as_of 覆蓋(法說修正),不同 as_of append
    vers = [v for v in d[code]["versions"] if v.get("as_of") != as_of]
    vers.append({"as_of": as_of, "source": source, "items": items})
    d[code]["versions"] = sorted(vers, key=lambda v: v.get("as_of", ""))
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(float(i.get("佔比%") or 0) for i in items)
    return ("" if 85 <= total <= 115 else
            f"⚠️ 佔比合計 {total:.0f}%(偏離100——若只列主要產品屬正常,否則檢查)")


def get_mix(code: str) -> list[dict]:
    """該股全部版本(舊→新)。"""
    return _load().get(code, {}).get("versions", [])


def latest_mix(code: str) -> dict | None:
    v = get_mix(code)
    return v[-1] if v else None


def mix_digest(code: str) -> str:
    """給報告 digest 的文字包(最新版+如有舊版附遷移軌跡)。"""
    vers = get_mix(code)
    if not vers:
        return ""
    v = vers[-1]
    lines = [f"- {i.get('產品','')}:{i.get('佔比%','?')}%"
             + (f"({i.get('毛利註記')})" if i.get("毛利註記") else "")
             for i in v.get("items", [])]
    out = (f"\n【產品組合(as of {v.get('as_of')},來源:{v.get('source')})——"
           f"營收/毛利推論必須基於此結構,嚴禁寫「產品結構待查」】\n" + "\n".join(lines))
    if len(vers) >= 2:
        v0 = vers[0]
        moves = []
        old = {i.get("產品"): i.get("佔比%") for i in v0.get("items", [])}
        for i in v.get("items", []):
            p = i.get("產品")
            if p in old and old[p] != i.get("佔比%"):
                moves.append(f"{p} {old[p]}%→{i.get('佔比%')}%")
        if moves:
            out += f"\n組合遷移({v0.get('as_of')}→{v.get('as_of')}):" + ";".join(moves)
    return out

"""
report_db.py — 研究報告 SQLite 資料庫
============================================
報告不寫死在程式裡,而是一篇篇加進這個資料庫。
一開始是空的;你 add_report() 一篇,清單就多一筆。

用法:
    import report_db as rdb
    rdb.init_db()                      # 第一次建表(冪等,可重複呼叫)
    rdb.add_report({...})              # 新增一篇
    rdb.list_reports(ticker="2330")    # 查清單
    rdb.get_report("2006", "永豐", "2026-06-18")  # 取單篇完整內容
    rdb.get_sentiment("6890")          # 該股報告彙總(平均目標價/上行/情緒)
"""
from __future__ import annotations
import sqlite3
import json
import datetime as dt
from pathlib import Path

DB_PATH = Path(__file__).parent / "reports.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    """建表。冪等,重複呼叫不會出錯,不會清資料。"""
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker        TEXT NOT NULL,
            name          TEXT,
            industry      TEXT,
            broker        TEXT,
            report_type   TEXT,
            report_date   TEXT NOT NULL,        -- YYYY-MM-DD
            rating        TEXT,                 -- 買進/中立/區間操作/賣出
            close_price   REAL,
            target_price  REAL,
            report_basis  TEXT,                 -- 法說會/拜訪…
            title         TEXT,
            trade_data    TEXT,                 -- JSON
            financial_data TEXT,                -- JSON
            esg           TEXT,                 -- JSON
            source_file   TEXT,                 -- 原始 PDF 檔名(可空)
            created_at    TEXT DEFAULT (datetime('now')),
            -- 同一檔 同券商 同日期 同型 視為同一篇,避免重複入庫
            UNIQUE(ticker, broker, report_date, report_type)
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON reports(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_date ON reports(report_date)")


def add_report(r: dict) -> int:
    """
    新增一篇報告。回傳該篇 id。
    若同 ticker+broker+date+type 已存在 → 覆蓋更新(方便你重傳修正)。

    r 需要的鍵(缺的會給預設):
      ticker(必填), name, industry, broker, report_type, report_date(必填),
      rating, close_price, target_price, report_basis, title,
      trade_data(dict), financial_data(dict), esg(dict), source_file
    """
    if not r.get("ticker") or not r.get("report_date"):
        raise ValueError("ticker 與 report_date 為必填")

    payload = (
        r["ticker"], r.get("name"), r.get("industry"), r.get("broker"),
        r.get("report_type"), r["report_date"], r.get("rating"),
        r.get("close_price"), r.get("target_price"), r.get("report_basis"),
        r.get("title"),
        json.dumps(r.get("trade_data", {}), ensure_ascii=False),
        json.dumps(r.get("financial_data", {}), ensure_ascii=False),
        json.dumps(r.get("esg", {}), ensure_ascii=False),
        r.get("source_file"),
    )
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO reports
            (ticker,name,industry,broker,report_type,report_date,rating,
             close_price,target_price,report_basis,title,
             trade_data,financial_data,esg,source_file)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker,broker,report_date,report_type)
            DO UPDATE SET
              name=excluded.name, industry=excluded.industry,
              rating=excluded.rating, close_price=excluded.close_price,
              target_price=excluded.target_price, report_basis=excluded.report_basis,
              title=excluded.title, trade_data=excluded.trade_data,
              financial_data=excluded.financial_data, esg=excluded.esg,
              source_file=excluded.source_file
        """, payload)
        return cur.lastrowid


def list_reports(ticker=None, broker=None, keyword=None,
                 start=None, end=None, limit=500, newest_first=True):
    """回傳報告清單(list[dict]),空庫回傳 []。"""
    q = "SELECT * FROM reports WHERE 1=1"
    args = []
    if ticker:
        q += " AND ticker=?"; args.append(ticker)
    if broker:
        q += " AND broker=?"; args.append(broker)
    if keyword:
        q += " AND (ticker LIKE ? OR name LIKE ? OR broker LIKE ? OR title LIKE ?)"
        args += [f"%{keyword}%"] * 4
    if start:
        q += " AND report_date>=?"; args.append(str(start))
    if end:
        q += " AND report_date<=?"; args.append(str(end))
    q += f" ORDER BY report_date {'DESC' if newest_first else 'ASC'} LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(row) for row in c.execute(q, args).fetchall()]


def get_report(report_id=None, ticker=None, broker=None, report_date=None):
    """取單篇完整內容(JSON 欄位已解析回 dict)。找不到回 None。"""
    with _conn() as c:
        if report_id is not None:
            row = c.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        else:
            row = c.execute("""SELECT * FROM reports
                WHERE ticker=? AND broker=? AND report_date=?
                ORDER BY id DESC LIMIT 1""",
                (ticker, broker, report_date)).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("trade_data", "financial_data", "esg"):
        d[k] = json.loads(d[k]) if d[k] else {}
    return d


def get_sentiment(ticker: str, months: int = 3) -> dict | None:
    """
    該股分析師觀點彙總(共識)。該股近 `months` 月內無報告回 None。

    彙總規則(你的設計):
      - 時間窗:只計最近 months 月內的報告(舊的不算共識)
      - 去重:每家券商只取「最新一篇」(同家舊報告不重複計入,避免灌票)
      - 中位數:目標價用中位數彙總(不被極端值拉偏),另附最高/最低/家數
      - 上行%:用「中位數目標價」對「最新一篇報告的收盤價」計算

    回傳:
      報告數(時間窗內總篇數)、券商數(去重後家數)、
      目標價中位數 / 最高 / 最低、平均上行%、情緒指數(買進比例 -1~1)、
      明細(各家最新:broker/date/target/rating)
    """
    import statistics
    cutoff = (dt.date.today() - dt.timedelta(days=months * 31)).isoformat()
    rows = [r for r in list_reports(ticker=ticker, limit=200)
            if r["report_date"] >= cutoff]
    if not rows:
        return None

    # 每家券商只留最新一篇(rows 已依日期新→舊,第一次遇到即最新)
    latest_by_broker = {}
    for r in rows:               # 新→舊
        b = r["broker"] or "—"
        if b not in latest_by_broker:
            latest_by_broker[b] = r
    consensus = list(latest_by_broker.values())

    tps = [r["target_price"] for r in consensus if r["target_price"]]
    cps = [r["close_price"] for r in consensus if r["close_price"]]
    med_tp = round(statistics.median(tps), 2) if tps else None
    last_close = cps[0] if cps else None  # 最新一篇的收盤價
    up = round((med_tp / last_close - 1) * 100, 1) if (med_tp and last_close) else None

    score_map = {"買進": 1, "中立": 0, "區間操作": 0, "賣出": -1}
    scores = [score_map.get(r["rating"], 0) for r in consensus]
    senti = round(sum(scores) / len(scores), 2) if scores else 0

    detail = sorted(
        [{"broker": r["broker"], "date": r["report_date"],
          "target": r["target_price"], "rating": r["rating"]}
         for r in consensus],
        key=lambda d: d["date"], reverse=True)

    return {
        "報告數": len(rows),
        "券商數": len(consensus),
        "目標價中位數": med_tp,
        "目標價最高": round(max(tps), 2) if tps else None,
        "目標價最低": round(min(tps), 2) if tps else None,
        "平均上行%": up,
        "情緒指數": senti,
        "時間窗月": months,
        "明細": detail,
    }


def count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]


def all_tickers() -> list[str]:
    with _conn() as c:
        return [r[0] for r in c.execute(
            "SELECT DISTINCT ticker FROM reports ORDER BY ticker").fetchall()]


if __name__ == "__main__":
    init_db()
    print("DB ready:", DB_PATH, "| 目前報告數:", count())

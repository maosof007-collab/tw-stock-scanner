"""
add_report_cli.py — 命令列加報告 / 看統計
用法:
    python add_report_cli.py stats                # 看目前報告數
    python add_report_cli.py demo                 # 加一篇示範(東和鋼鐵)
    python add_report_cli.py add 2330 台積電 永豐 2026-06-18 買進 1100 1300
                              股號  名稱   券商  日期       建議   收盤 目標
"""
import sys
import report_db as rdb

rdb.init_db()

if len(sys.argv) < 2 or sys.argv[1] == "stats":
    print(f"目前報告數:{rdb.count()}")
    print(f"有報告的股票:{rdb.all_tickers()}")

elif sys.argv[1] == "demo":
    rid = rdb.add_report({
        "ticker": "2006", "name": "東和鋼鐵", "industry": "鋼鐵工業",
        "broker": "永豐", "report_type": "個股聚焦", "report_date": "2026-06-18",
        "rating": "買進", "close_price": 69.6, "target_price": 78.0,
        "report_basis": "法說會", "title": "東和鋼鐵 個股聚焦",
        "trade_data": {"潛在報酬率(%)": 12.07, "外資持股(%)": 18.92,
                       "投信持股(%)": 7.13, "融資使用率(%)": 0.65},
        "financial_data": {"股東權益(NT$百萬元)": 34346, "ROA(%)": 8.83,
                           "ROE(%)": 14.1, "淨負債比率(%)": 33.72},
        "esg": {"總分": "A", "SASB評分": "B+", "領導及公司治理": "A"},
        "source_file": "demo",
    })
    print(f"已加入示範報告 id={rid}")

elif sys.argv[1] == "add":
    a = sys.argv[2:]
    rid = rdb.add_report({
        "ticker": a[0], "name": a[1] if len(a) > 1 else None,
        "broker": a[2] if len(a) > 2 else None,
        "report_date": a[3], "rating": a[4] if len(a) > 4 else None,
        "close_price": float(a[5]) if len(a) > 5 else None,
        "target_price": float(a[6]) if len(a) > 6 else None,
        "report_type": "個股報告",
        "title": f"{a[1] if len(a)>1 else a[0]} 個股報告",
    })
    print(f"已加入 id={rid}|目前共 {rdb.count()} 篇")
else:
    print(__doc__)

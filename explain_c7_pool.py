# -*- coding: utf-8 -*-
"""EXPLAIN ANALYZE 原始 dump（本版本返回 explain_key/explain_value 两列）。"""
import sys
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
import duckdb
import core.c7_pool_rebuild as R

all_td = R._list_quote_dates()
target = all_td[-1]
idx = all_td.index(target)
buffer_days = 30
buffered = all_td[max(0, idx - buffer_days):]
win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
con = duckdb.connect(); con.execute("SET threads=8")
R._TMP.mkdir(parents=True, exist_ok=True)
con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
rows = con.execute("EXPLAIN ANALYZE " + R._pool_sql(win)).fetchall()
# 第二列是多行树形文本，含每算子的 timing
for k, v in rows:
    text = str(v)
    # 只打印含时间关键字的行
    for line in text.splitlines():
        if any(w in line for w in ["Time", "time", "HASH", "WINDOW", "AGGREGATE", "PROJECTION",
                                   "FILTER", "JOIN", "SCAN", "DISTINCT", "ORDER", "top", "Top"]):
            print(line[:160], flush=True)
con.close()

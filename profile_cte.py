# -*- coding: utf-8 -*-
"""逐 CTE 增量计时：WITH 到第 n 个 CTE 为止 + SELECT count(*)。buffer=30 基线。"""
import sys, re, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
import duckdb
import core.c7_pool_rebuild as R

all_td = R._list_quote_dates()
idx = all_td.index(all_td[-1])
buffered = all_td[max(0, idx - 30):]
win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
full = R._pool_sql(win)

# 找每个 CTE 的起始偏移
names = ["qx","dx","cal","base","st","cdx","sc","lead","feat","flag",
         "run6","st6","run7","st7","concepts","fwd","pool"]
starts = {}
for nm in names:
    m = re.search(r"\b%s AS \(" % re.escape(nm), full)
    starts[nm] = m.start()

body_start = starts["qx"]                      # "WITH\n" 之后
def cte_sql(n):
    end = starts[names[names.index(n)+1]] if names.index(n)+1 < len(names) else len(full)
    seg = full[body_start:end].rstrip().rstrip(',').rstrip()
    return "WITH " + seg + " SELECT count(*) FROM " + n

for n in ["st","lead","feat","flag","st7","concepts","fwd","pool"]:
    con = duckdb.connect(); con.execute("SET threads=8")
    R._TMP.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
    t0 = time.time()
    try:
        c = con.execute(cte_sql(n)).fetchone()[0]
        print("到 CTE %-9s : %6.2fs  count=%d" % (n, time.time()-t0, c), flush=True)
    except Exception as e:
        print("到 CTE %-9s : FAIL %s" % (n, str(e)[:160]), flush=True)
    con.close()

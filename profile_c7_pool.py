# -*- coding: utf-8 -*-
"""分步 profile rebuild 版 _pool_sql，把 44s 钉到具体 CTE。
对比：rebuild 值列表 IN('d1'..'dn') vs 实时版 LIMIT/OFFSET 子查询；
     以及 fwd(RANGE窗口) / run6+run7双streak / concepts 各自耗时。"""
import sys, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
import duckdb
import core.c7_pool_rebuild as R

all_td = R._list_quote_dates()
target = all_td[-1]           # 最新日（模拟线上单日补算）
idx = all_td.index(target)
for buffer_days in [15, 30, 70]:
    buf_start = max(0, idx - buffer_days)
    buffered = all_td[buf_start:]
    win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute(f"SET temp_directory='{(R._TMP).as_posix()}'")
    R._TMP.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        df = con.execute(R._pool_sql(win)).df()
        dt = time.time() - t0
        print("buffer=%3d  实际窗口=%3d日  SQL行数=%5d  耗时=%.1fs  目标日行=%d"
              % (buffer_days, len(buffered), len(df), dt,
                 len(df[df['trade_date'] == target])), flush=True)
    except Exception as e:
        print("buffer=%d FAIL %s" % (buffer_days, str(e)[:200]), flush=True)
    con.close()

# 再单独测：只跑 base+st（窗口特征），不跑 fwd/streak——定位是否 fwd 是大头
print("\n--- 分段计时（buffer=15）---", flush=True)
buf_start = max(0, idx - 15)
buffered = all_td[buf_start:]
win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
full = R._pool_sql(win)
con = duckdb.connect(); con.execute("SET threads=8")
# 阶段A：截取到 st CTE 结束（feat 之前）
part_a = full[:full.index("lead AS (")] if "lead AS (" in full else full[:full.index("feat AS (")]
part_a_sql = part_a.rstrip().rstrip(',') + " SELECT count(*) FROM st"
t0 = time.time()
try:
    n = con.execute(part_a_sql).fetchone()[0]
    print("阶段A(base+st窗口特征): %.1fs rows=%d" % (time.time()-t0, n), flush=True)
except Exception as e:
    print("阶段A FAIL", str(e)[:300], flush=True)
con.close()

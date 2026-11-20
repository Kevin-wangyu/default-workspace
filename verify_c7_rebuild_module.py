# -*- coding: utf-8 -*-
"""验证 core/c7_pool_rebuild.py::_pool_sql 与已逐股验证的快照口径一致。
只读对比，不写项目数据。"""
import sys, time
from pathlib import Path
import duckdb, pandas as pd

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
sys.path.insert(0, PROJ)
import core.c7_pool_rebuild as m

snap = pd.read_parquet(WS / "_prebuild_verify.parquet")
all_td = m._list_quote_dates()
print("SNAP rows=%d days=%d range=%s~%s" % (
    len(snap), snap.trade_date.nunique(), snap.trade_date.min(), snap.trade_date.max()))
print("ALL_TD len=%d last=%s" % (len(all_td), all_td[-1]))

win = all_td[-120:]
win_sql = "(" + ",".join("'%s'" % d for d in win) + ")"
sql = m._pool_sql(win_sql)
con = duckdb.connect(); con.execute("SET threads=8")
con.execute("SET temp_directory='%s'" % (WS / "_duckdb_tmp").as_posix())
t0 = time.time()
df = con.execute(sql).df()
con.close()
print("MY_SQL rows=%d days=%d secs=%.1f" % (len(df), df.trade_date.nunique(), time.time()-t0))

target = set(win[70:-11])   # 避开 streak 前边界 + fwd 后边界
a = df[df.trade_date.isin(target)].copy()
b = snap[snap.trade_date.isin(target)].copy()
print("TARGET days=%d a_rows=%d b_rows=%d" % (len(target), len(a), len(b)))

ka = set(zip(a.trade_date.astype(str), a.code))
kb = set(zip(b.trade_date.astype(str), b.code))
print("KEY only_my=%d only_snap=%d inter=%d" % (len(ka-kb), len(kb-ka), len(ka&kb)))

a = a.copy(); b = b.copy()
a["_k"] = a.trade_date.astype(str) + "|" + a.code.astype(str)
b["_k"] = b.trade_date.astype(str) + "|" + b.code.astype(str)
a = a.set_index("_k").sort_index()
b = b.set_index("_k").sort_index()
idx = a.index.intersection(b.index)
common = [c for c in a.columns if c in b.columns and c != "_k"]
ALL_OK = True
for c in common:
    sa, sb = a.loc[idx, c], b.loc[idx, c]
    try:
        if pd.api.types.is_numeric_dtype(sa) and pd.api.types.is_numeric_dtype(sb):
            diff = (sa.astype(float) - sb.astype(float)).abs()
            mx = diff.max()
            nd = int((diff > 1e-6).sum())
            ok = nd == 0
            print("  %-22s max_abs=%.8f n_diff>1e-6=%d %s" % (c, mx, nd, "OK" if ok else "FAIL"))
        else:
            neq = int((sa.astype(str) != sb.astype(str)).sum())
            ok = neq == 0
            print("  %-22s n_neq=%d %s" % (c, neq, "OK" if ok else "FAIL"))
        ALL_OK = ALL_OK and ok
    except Exception as e:
        print("  %-22s ERR %s" % (c, e))
        ALL_OK = False
print("VERIFY_MODULE_ALL_OK=%s" % ALL_OK)

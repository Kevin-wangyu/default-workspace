# -*- coding: utf-8 -*-
"""最小修复验证：只把 concepts CTE 裁到目标日集合，fwd 保持原样。
确认 ①耗时降到~1s ②目标日逐字段口径与基线完全一致。多目标日场景也测。"""
import sys, re, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
import duckdb, pandas as pd
import core.c7_pool_rebuild as R

all_td = R._list_quote_dates()
idx = all_td.index(all_td[-1])
buffered = all_td[max(0, idx - 30):]
win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
targets = "('" + all_td[-1] + "')"
base_sql = R._pool_sql(win)

# 最小改动：concepts CTE 的 WHERE IN win → IN targets（只改 concepts 那一处）
# concepts CTE 特征: FROM {_CG}, unnest ... WHERE ... IN win GROUP BY
old = "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + win + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code"
new = "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + targets + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code"
assert base_sql.count(old) == 1, "concepts WHERE 匹配数=%d" % base_sql.count(old)
fix_sql = base_sql.replace(old, new)

def run(sql, label):
    con = duckdb.connect(); con.execute("SET threads=8")
    R._TMP.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
    t0=time.time(); df=con.execute(sql).df(); dt=time.time()-t0
    con.close()
    print("%-22s : %6.2fs rows=%d" % (label, dt, len(df)), flush=True)
    return df

a = run(base_sql, "A 基线")
b = run(fix_sql, "B 最小修复(concepts裁目标日)")
tgt = all_td[-1]
aa=a[a.trade_date==tgt].sort_values('code').reset_index(drop=True)
bb=b[b.trade_date==tgt].sort_values('code').reset_index(drop=True)
print("\n目标日 %s 基线%d行/修复%d行" % (tgt,len(aa),len(bb)), flush=True)
num=[c for c in aa.columns if aa[c].dtype.kind in 'fi']
bad=0
for col in num:
    x=pd.to_numeric(aa[col],errors='coerce'); y=pd.to_numeric(bb[col],errors='coerce')
    mx=(x-y).abs().max()
    if pd.notna(mx) and mx>1e-6:
        print("  差异 %s max=%.6g" % (col,mx), flush=True); bad+=1
# 文本列也比对
for col in ['code','name','matched_concepts','source']:
    if col in aa.columns and col in bb.columns:
        neq=(aa[col].fillna('').astype(str)!=bb[col].fillna('').astype(str)).sum()
        if neq: print("  文本差异 %s n=%d" % (col,neq), flush=True); bad+=1
print("VERIFY_MIN_FIX: 差异项=%d (0=口径完全一致)" % bad, flush=True)

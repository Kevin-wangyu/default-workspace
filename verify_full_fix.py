# -*- coding: utf-8 -*-
"""完整修复：concepts + fwd 都裁到目标日；验证多日期(含历史稳定日)口径一致。
用于落盘到 c7_pool_rebuild.py 的 _pool_sql。"""
import sys, time
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

# 1) concepts 裁目标日
old_c = "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + win + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code"
new_c = "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + targets + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code"
assert base_sql.count(old_c)==1
fix = base_sql.replace(old_c, new_c)

# 2) fwd CTE: FROM base → FROM base WHERE d IN targets（fwd 只服务目标日）
old_f = "  FROM base\n),\npool AS ("
new_f = "  FROM base WHERE d IN " + targets + "\n),\npool AS ("
assert fix.count(old_f)==1, "fwd FROM base 匹配=%d" % fix.count(old_f)
fix = fix.replace(old_f, new_f)

def run(sql, label):
    con=duckdb.connect(); con.execute("SET threads=8")
    R._TMP.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
    t0=time.time(); df=con.execute(sql).df(); dt=time.time()-t0
    con.close(); print("%-22s : %6.2fs rows=%d"%(label,dt,len(df)),flush=True); return df

a=run(base_sql,"A 基线(全窗口)")
b=run(fix,"B 完整修复(concepts+fwd裁目标日)")
tgt=all_td[-1]
num=[c for c in a.columns if a[c].dtype.kind in 'fi']
for kind, dfa, dfb in [("目标日", a[a.trade_date==tgt], b[b.trade_date==tgt])]:
    dfa=dfa.sort_values('code').reset_index(drop=True); dfb=dfb.sort_values('code').reset_index(drop=True)
    print("%s 基线%d行/修复%d行"%(kind,len(dfa),len(dfb)),flush=True)
    bad=0
    for col in num:
        x=pd.to_numeric(dfa[col],errors='coerce'); y=pd.to_numeric(dfb[col],errors='coerce')
        mx=(x-y).abs().max()
        if pd.notna(mx) and mx>1e-6: print("  差异 %s max=%.6g"%(col,mx),flush=True); bad+=1
    for col in ['code','name','matched_concepts','source']:
        if col in dfa.columns and col in dfb.columns:
            neq=(dfa[col].fillna('').astype(str)!=dfb[col].fillna('').astype(str)).sum()
            if neq: print("  文本差异 %s n=%d"%(col,neq),flush=True); bad+=1
    print("VERIFY_FULL_FIX %s: 差异项=%d (0=完全一致)"%(kind,bad),flush=True)

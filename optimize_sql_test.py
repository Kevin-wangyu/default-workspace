# -*- coding: utf-8 -*-
"""受控实验：确认 fwd(RANGE窗口)/concepts(全窗口聚合) 是瓶颈，并验证优化版口径一致。
A) 基线完整 SQL buffer=30
B) fwd 列置 NULL（去掉4个RANGE window）→ 看耗时降幅
C) concepts 置空（去掉全窗口 unnest+string_agg）→ 看耗时降幅
D) 优化版：fwd 改 join 聚合(只target日) + concepts 只target日 → 耗时 + 与目标日历史分区逐字段对比
"""
import sys, re, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
import duckdb, pandas as pd
import core.c7_pool_rebuild as R

all_td = R._list_quote_dates()
target = all_td[-1]
idx = all_td.index(target)
buffer_days = 30
buffered = all_td[max(0, idx - buffer_days):]
win = "(" + ",".join(f"'{d}'" for d in buffered) + ")"
targets = f"('{target}')"
base_sql = R._pool_sql(win)

def run(sql, label, params=None):
    con = duckdb.connect(); con.execute("SET threads=8")
    R._TMP.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
    t0=time.time()
    try:
        df = con.execute(sql).df()
        dt=time.time()-t0
        print("%-28s : %6.2fs  rows=%d" % (label, dt, len(df)), flush=True)
        con.close(); return df
    except Exception as e:
        print("%-28s : FAIL %s" % (label, str(e)[:200]), flush=True)
        con.close(); return None

# A) 基线
dfA = run(base_sql, "A 基线(完整SELECT*)")

# B) fwd列置NULL
b = base_sql
b = b.replace(
    "CASE WHEN fw.n5=5  THEN (fw.hi5 /NULLIF(s6.close,0)-1)*100 END AS fwd_max_5d,",
    "CAST(NULL AS DOUBLE) AS fwd_max_5d,")
b = b.replace(
    "CASE WHEN fw.n10=10 THEN (fw.hi10/NULLIF(s6.close,0)-1)*100 END AS fwd_max_10d,",
    "CAST(NULL AS DOUBLE) AS fwd_max_10d,")
# 同时删掉 fwd CTE (避免它被引用触发计算——但LEFT JOIN还在，DuckDB可能优化掉)
run(b, "B fwd列置NULL")

# C) concepts 置空
c = base_sql
c = re.sub(r"string_agg\(DISTINCT t\.x, ';' ORDER BY t\.x\) AS cfs", "CAST('' AS VARCHAR) AS cfs", c)
c = re.sub(r"count\(DISTINCT t\.x\) AS n_cfs", "CAST(0 AS INT) AS n_cfs", c)
run(c, "C concepts置空")

# D) 优化版：fwd join聚合 + concepts只target日
d = base_sql
# concepts CTE 的 WHERE 换成 target
d = d.replace(
    "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + win + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code\n),\nfwd AS (",
    "WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN " + targets + "\n  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code\n),\nfwd AS (")
# fwd CTE 整体替换
fwd_new = """fwd AS (
  SELECT t.d, t.code,
    max(CASE WHEN fb.di BETWEEN t.di+1 AND t.di+5  THEN fb.high END) AS hi5,
    max(CASE WHEN fb.di BETWEEN t.di+1 AND t.di+10 THEN fb.high END) AS hi10,
    count(CASE WHEN fb.di BETWEEN t.di+1 AND t.di+5  THEN 1 END) AS n5,
    count(CASE WHEN fb.di BETWEEN t.di+1 AND t.di+10 THEN 1 END) AS n10
  FROM (SELECT d, di, code FROM base WHERE d IN """ + targets + """) t
  JOIN base fb ON fb.code=t.code AND fb.di>t.di AND fb.di<=t.di+10
  GROUP BY t.d, t.code
),"""
d = re.sub(r"fwd AS \(\n  SELECT d, di, code,.*?\n\),", fwd_new, d, count=1, flags=re.S)
# JOIN 条件去掉 di
d = d.replace("LEFT JOIN fwd fw ON fw.d=s6.trade_date AND fw.di=s6.di AND fw.code=s6.code",
              "LEFT JOIN fwd fw ON fw.d=s6.trade_date AND fw.code=s6.code")
dfD = run(d, "D 优化版(全SQL)")

# 口径对比：目标日行，基线A vs 优化D
if dfA is not None and dfD is not None:
    a = dfA[dfA['trade_date']==target].reset_index(drop=True)
    dd = dfD[dfD['trade_date']==target].reset_index(drop=True)
    print("\n目标日 %s : 基线 %d 行 / 优化 %d 行" % (target, len(a), len(dd)), flush=True)
    if len(a)==len(dd) and len(a)>0:
        a=a.sort_values('code').reset_index(drop=True)
        dd=dd.sort_values('code').reset_index(drop=True)
        num=[c for c in a.columns if a[c].dtype.kind in 'fi']
        bad=0
        for col in num:
            x=pd.to_numeric(a[col],errors='coerce'); y=pd.to_numeric(dd[col],errors='coerce')
            mx=(x-y).abs().max()
            if pd.notna(mx) and mx>1e-6:
                print("  数值差异 %s max=%.6g" % (col,mx), flush=True); bad+=1
        print("口径对比: 数值差异列=%d (0=完全一致)" % bad, flush=True)

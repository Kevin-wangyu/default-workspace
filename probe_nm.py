# -*- coding: utf-8 -*-
"""探查：确认 n×m 标签可从原始行情重算且与前序 y5/y10(m=20) 完全一致。纯读。"""
from pathlib import Path
import duckdb, json
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
p=lambda *x: str(Path(PROJ,*x)).replace("\\","/")
RM=(WS/"research_matrix.parquet").as_posix()
QG=f"read_parquet('{p('data_compact','quote','*.parquet')}',union_by_name=true)"
con=duckdb.connect(); con.execute("SET threads=8")

cols=[r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RM}')").fetchall()]
print("MATRIX ncol:",len(cols))
print("MATRIX cols:",cols)
n=con.execute(f"SELECT count(*) FROM read_parquet('{RM}')").fetchone()[0]
print("MATRIX rows:",n)
print("SPLIT:",con.execute(f"SELECT split,count(*) n,count(DISTINCT trade_date) nd FROM read_parquet('{RM}') GROUP BY split ORDER BY split").fetchall())

# 校验：原始行情重算 fwd_hi5/10，与矩阵 y5/y10(m=20) 对比
chk=con.execute(f"""
WITH qx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, close, high
  FROM {QG}
),
cal AS (SELECT d,row_number() OVER (ORDER BY d) di FROM (SELECT DISTINCT d FROM qx)),
lab AS (
  SELECT q.d trade_date,q.code,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING)/q.close-1)*100 AS fm5,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING) AS nn5,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)/q.close-1)*100 AS fm10,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn10
  FROM qx q JOIN cal c USING(d)
),
mine AS (
  SELECT trade_date,code,
    CASE WHEN nn5=5 AND fm5>=20 THEN 1 WHEN nn5=5 THEN 0 END AS y5r,
    CASE WHEN nn10=10 AND fm10>=20 THEN 1 WHEN nn10=10 THEN 0 END AS y10r,
    fm5,fm10
  FROM lab
),
m AS (SELECT trade_date,code,y5,y10,fwd_max_5d,fwd_max_10d FROM read_parquet('{RM}'))
SELECT count(*) AS n,
  count(*) FILTER (WHERE m.y5 IS NOT NULL AND mine.y5r IS NOT NULL) AS n5,
  count(*) FILTER (WHERE m.y5 IS NOT NULL AND mine.y5r IS NOT NULL AND m.y5<>mine.y5r) AS diff5,
  count(*) FILTER (WHERE m.y10 IS NOT NULL AND mine.y10r IS NOT NULL) AS n10,
  count(*) FILTER (WHERE m.y10 IS NOT NULL AND mine.y10r IS NOT NULL AND m.y10<>mine.y10r) AS diff10,
  max(abs(m.fwd_max_5d-mine.fm5)) AS maxdiff_fm5,
  max(abs(m.fwd_max_10d-mine.fm10)) AS maxdiff_fm10
FROM m JOIN mine USING(trade_date,code)
""").fetchone()
print("RECOMPUTE_CHECK n=%s n5=%s diff5=%s n10=%s diff10=%s maxdiff_fm5=%s maxdiff_fm10=%s"%chk)

# C7 池规模（用 daily_c7.py 完全一致的条件）
thr=dict(vol20=3.5238,turnover_rate=3.7,ret_5d=4.8679,lu_gap=-3.0,close_hh20_ratio=0.95,n_leader=1.0)
c7=f"""lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>={thr['vol20']} AND turnover_rate>={thr['turnover_rate']}
 AND lu_gap>={thr['lu_gap']} AND close_hh20_ratio>={thr['close_hh20_ratio']} AND ret_5d>={thr['ret_5d']}
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>={thr['n_leader']}"""
print("C7 POOL:",con.execute(f"SELECT split,count(*) n,count(DISTINCT trade_date) nd FROM read_parquet('{RM}') WHERE {c7} GROUP BY split ORDER BY split").fetchall())
print("DONE")

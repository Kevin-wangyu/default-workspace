# -*- coding: utf-8 -*-
"""验证：在矩阵自身数据上用 RANGE 窗口重算 fwd_max_n，是否与缓存 fwd_max_5d/10d 完全一致。纯读。"""
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")

q=con.execute(f"""
WITH r AS (
  SELECT trade_date,code,split,close,di,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING)/NULLIF(close,0)-1)*100 AS fm5r,
    count(*)   OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING) AS nn5r,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)/NULLIF(close,0)-1)*100 AS fm10r,
    count(*)   OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn10r,
    fwd_max_5d, fwd_max_10d, fwd_n5, fwd_n10, y5, y10
  FROM read_parquet('{RM}')
)
SELECT count(*) n,
  count(*) FILTER (WHERE fwd_max_5d IS NOT NULL AND fm5r IS NOT NULL AND abs(fwd_max_5d-fm5r)>1e-9) AS diff5,
  max(abs(fwd_max_5d-fm5r)) AS mx5,
  count(*) FILTER (WHERE fwd_max_10d IS NOT NULL AND fm10r IS NOT NULL AND abs(fwd_max_10d-fm10r)>1e-9) AS diff10,
  max(abs(fwd_max_10d-fm10r)) AS mx10,
  count(*) FILTER (WHERE fwd_n5<>nn5r) AS difnn5,
  count(*) FILTER (WHERE fwd_n10<>nn10r) AS difnn10,
  count(*) FILTER (WHERE y5 IS NOT NULL AND (CASE WHEN nn5r=5 AND fm5r>=20 THEN 1 WHEN nn5r=5 THEN 0 END)<>y5) AS dy5,
  count(*) FILTER (WHERE y10 IS NOT NULL AND (CASE WHEN nn10r=10 AND fm10r>=20 THEN 1 WHEN nn10r=10 THEN 0 END)<>y10) AS dy10
FROM r
""").fetchone()
print("SELF_RECOMPUTE n=%s diff5=%s mx5=%s diff10=%s mx10=%s difnn5=%s difnn10=%s dy5=%s dy10=%s"%q)

# 同 code 同日是否唯一
u=con.execute(f"SELECT count(*) rows, count(DISTINCT (trade_date,code)) uniq FROM read_parquet('{RM}')").fetchone()
print("UNIQUE rows=%s uniq(date,code)=%s"%(u[0],u[1]))
print("DONE")

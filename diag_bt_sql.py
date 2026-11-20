# -*- coding: utf-8 -*-
"""逐步复现 backtest_strategy 的SQL，找哪一步从15405掉到36。"""
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
D0,D1="2024-03-13","2026-11-01"
leadcols = ",\n    ".join(
    f"lead({c},{k}) OVER (PARTITION BY code ORDER BY di) AS {a}{k}"
    for k in range(1,11) for c,a in [("open","o"),("high","h"),("low","l"),("close","c")])
base=f"""WITH allx AS (
 SELECT trade_date,di,split,code,name,close AS c0,{leadcols},
  lead(di,10) OVER (PARTITION BY code ORDER BY di) AS di10,
  vol20,ret_5d,turnover_rate,n_leader_concepts,
  CAST((lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
   AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60) AS INT) c6,
  CAST((lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
   AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1) AS INT) c7
 FROM read_parquet('{RM}'))"""
for name,where in [
  ("allx全量","1=1"),
  ("区间","trade_date>='%s' AND trade_date<='%s'"%(D0,D1)),
  ("区间c6","trade_date>='%s' AND trade_date<='%s' AND c6=1"%(D0,D1)),
  ("区间c6+di10","trade_date>='%s' AND trade_date<='%s' AND c6=1 AND di10=di+10"%(D0,D1)),
  ("区间di10分布","trade_date>='%s' AND trade_date<='%s' AND c6=1"%(D0,D1)),
]:
    if name=="区间di10分布":
        q=base+f" SELECT di10-di AS gap,count(*) FROM allx WHERE {where} GROUP BY 1 ORDER BY 1 LIMIT 10"
        for r in con.execute(q).fetchall(): print(" ",name,"gap=%s n=%s"%r, flush=True)
    else:
        n=con.execute(base+f" SELECT count(*) FROM allx WHERE {where}").fetchone()[0]
        print(name,"=",n, flush=True)
# 关键：c6=1 行的 di10-di 分布（看是否 di10 因 lead 别名覆盖出错）
con.close()

# -*- coding: utf-8 -*-
"""证伪：'触发日归集'提升命中率是否只是幸存者偏差（同一股票只算首次达标那次）。纯读。
方法：按 (code, 触发组) 去重，只保留该股首次满足C7的日期；对比 整体 vs 去重后 的命中率。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb, numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
w=con.execute(f"""
WITH r AS (
  SELECT trade_date,di,split,code,
    CASE WHEN {C7} THEN 1 ELSE 0 END AS c7,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)
      /NULLIF(close,0)-1)*100 AS fmax,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn
  FROM read_parquet('{RM}')
),
v AS (SELECT * FROM r WHERE nn=10 AND split IN ('train','oos') AND c7=1),
w AS (SELECT *, CASE WHEN fmax>=20 THEN 1 ELSE 0 END AS fhit,
       min(di) OVER (PARTITION BY code) AS first_di FROM v)
SELECT split,code,di,fhit, first_di, di=first_di AS is_first FROM w
""").df()
for sp in ['train','oos']:
    s=w[w.split==sp]
    allr=s.fhit.mean(); firstr=s[s.is_first].fhit.mean()
    print(f"{sp}: 全体C7样本={len(s)} hit={allr:.4f} | 首次触发去重样本={s.is_first.sum()} hit={firstr:.4f}")
    # 触发密度：一只股平均被选几次
    print(f"  平均选中次数={len(s)/s.code.nunique():.2f} 代码数={s.code.nunique()}")
print("DONE")

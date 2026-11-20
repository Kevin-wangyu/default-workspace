# -*- coding: utf-8 -*-
"""诊断：为何区间C6候选只有36？分步看 each 条件满足数与di10完整数。"""
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
D0,D1="2024-03-13","2026-11-01"
print("schema关键列:", [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RM}') LIMIT 0").fetchall()][:20], flush=True)
q=f"""WITH x AS (
 SELECT *, lead(di,10) OVER (PARTITION BY code ORDER BY di) di10
 FROM read_parquet('{RM}')
)
SELECT
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}') n_range,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND di10=di+10) n_di10ok,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND lu_cnt_20d>=1) n_lu,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND main_net_norm>0) n_mn,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND vol20>=3.5238) n_vol,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND turnover_rate>=3.7) n_tor,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND lu_gap>=-3) n_gap,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND close_hh20_ratio>=0.95) n_hh,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND ret_5d>=4.8679) n_ret,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND ma5>ma20 AND ma20>ma60) n_bull,
 count(*) FILTER (WHERE trade_date>='{D0}' AND trade_date<='{D1}' AND n_leader_concepts>=1) n_lead
FROM x"""
r=con.execute(q).fetchone()
cols=['n_range','n_di10ok','n_lu','n_mn','n_vol','n_tor','n_gap','n_hh','n_ret','n_bull','n_lead']
for c,v in zip(cols,r): print(f" {c}={v}", flush=True)
# C6 all cond
q2=f"""WITH x AS (SELECT *, lead(di,10) OVER (PARTITION BY code ORDER BY di) di10 FROM read_parquet('{RM}'))
SELECT count(*) FILTER (WHERE lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
  AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60) n_c6,
 count(*) FILTER (WHERE lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
  AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1) n_c7
FROM x WHERE trade_date>='{D0}' AND trade_date<='{D1}'"""
r2=con.execute(q2).fetchone()
print(f" full-history lead: n_c6={r2[0]} n_c7={r2[1]}", flush=True)
con.close()

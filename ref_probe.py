# -*- coding: utf-8 -*-
"""算规则1.1综合分所需的train基准常数(vol20/ret_5d/turnover_rate)。纯读。"""
from pathlib import Path
import duckdb
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
con = duckdb.connect(); con.execute("SET threads=8")
RM = (WS / "research_matrix.parquet").as_posix()
r = con.execute(f"""
SELECT
  count(*) n,
  avg(vol20) vol_m, stddev_samp(vol20) vol_s,
  avg(ret_5d) ret_m, stddev_samp(ret_5d) ret_s,
  avg(turnover_rate) tor_m, stddev_samp(turnover_rate) tor_s
FROM read_parquet('{RM}')
WHERE split='train' AND isfinite(vol20) AND isfinite(ret_5d) AND isfinite(turnover_rate)
""").fetchone()
print("TRAIN_REF n=%d vol_m=%.6f vol_s=%.6f ret_m=%.6f ret_s=%.6f tor_m=%.6f tor_s=%.6f" % r)
# C7池自身分布(用于确认阈值稳定)
r2 = con.execute(f"""
SELECT count(*) n,
  avg(vol20) vol_m, avg(ret_5d) ret_m, avg(turnover_rate) tor_m
FROM read_parquet('{RM}')
WHERE split='train' AND lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238
  AND turnover_rate>=3.7 AND lu_gap>=-3 AND close_hh20_ratio>=0.95
  AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1
""").fetchone()
print("C7_POOL_TRAIN n=%d vol_m=%.4f ret_m=%.4f tor_m=%.4f" % r2)

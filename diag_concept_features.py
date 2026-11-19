# -*- coding: utf-8 -*-
"""诊断概念特征分布：确认"主线延续/退出榜"稀疏是构造问题还是数据事实。纯读。"""
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
print("=== 概念特征分布（train+oos，非null行）===",flush=True)
q=con.execute(f"""
SELECT
 count(*) AS n,
 count(n_strong_today) AS nn_strong_today,
 sum(CASE WHEN n_strong_today>=1 THEN 1 ELSE 0 END) AS has_strong_today,
 count(n_concept_strong_hist) AS nn_hist,
 sum(CASE WHEN n_concept_strong_hist>=1 THEN 1 ELSE 0 END) AS has_hist1,
 sum(CASE WHEN n_concept_strong_hist>=2 THEN 1 ELSE 0 END) AS has_hist2,
 min(n_concept_strong_hist) AS mn_hist, max(n_concept_strong_hist) AS mx_hist,
 avg(n_concept_strong_hist) AS av_hist,
 count(n_mainline_not_onlist) AS nn_offlist,
 sum(CASE WHEN n_mainline_not_onlist>=1 THEN 1 ELSE 0 END) AS has_offlist,
 min(n_mainline_not_onlist) AS mn_off, max(n_mainline_not_onlist) AS mx_off,
 count(n_concept_hot20) AS nn_hot20,
 sum(CASE WHEN n_concept_hot20>=1 THEN 1 ELSE 0 END) AS has_hot20,
 max(n_concept_hot20) AS mx_hot20
FROM read_parquet('{RM}') WHERE split IN ('train','oos')
""").df()
print(q.to_string(index=False),flush=True)
print("\n=== n_concept_strong_hist 取值频次(top15) ===",flush=True)
print(con.execute(f"""
SELECT n_concept_strong_hist AS v, count(*) AS n
FROM read_parquet('{RM}') WHERE split IN ('train','oos') AND n_concept_strong_hist IS NOT NULL
GROUP BY 1 ORDER BY n DESC LIMIT 15
""").df().to_string(index=False),flush=True)
print("\n=== 交叉：hist>=1 且 today=0 (退出榜候选) ===",flush=True)
print(con.execute(f"""
SELECT
 sum(CASE WHEN n_concept_strong_hist>=1 AND n_strong_today=0 THEN 1 ELSE 0 END) AS hist1_today0,
 sum(CASE WHEN n_concept_strong_hist>=1 AND n_strong_today>=1 THEN 1 ELSE 0 END) AS hist1_today1,
 sum(CASE WHEN n_concept_hot20>=1 AND n_strong_today=0 THEN 1 ELSE 0 END) AS hot20_today0,
 sum(CASE WHEN n_concept_hot20>=2 AND n_strong_today=0 THEN 1 ELSE 0 END) AS hot20ge2_today0
FROM read_parquet('{RM}') WHERE split IN ('train','oos')
""").df().to_string(index=False),flush=True)
print("\n=== 强榜面板：每日强概念数分布 ===",flush=True)
BAR='D:/Users/KFish/Desktop/Code/github-app/stockDisplay/data_compact/_tops_cache/v1/bars.parquet'
print(con.execute(f"""
SELECT min(d) AS d0, max(d) AS d1, avg(n_strong) AS av_strong, min(n_strong) AS mn, max(n_strong) AS mx
FROM (SELECT trade_date AS d, count(DISTINCT concept_name) AS n_strong
      FROM read_parquet('{BAR}') WHERE is_strong=true GROUP BY 1)
""").df().to_string(index=False),flush=True)
print("DONE",flush=True)

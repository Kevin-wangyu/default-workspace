# -*- coding: utf-8 -*-
"""查清关键字段真实取值分布：scrplus / lu_cnt / main_net_norm 是否退化、
ntile ties 伪影有多大；用【按值分桶】给出稳健 hit10。纯读。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
con = duckdb.connect()
con.execute("SET threads=8")
out = {}

for f in ["scrplus_90", "scrplus_70", "lu_cnt_20d", "lu_cnt_10d", "main_net_norm", "vol20", "turnover_rate"]:
    r = con.execute(f"""
      SELECT count(*) AS n, count("{f}") AS nn,
             count(DISTINCT "{f}") AS nd,
             count(*) FILTER (WHERE "{f}"=0) AS n_zero,
             min("{f}") AS mn, max("{f}") AS mx,
             quantile_cont("{f}", 0.25) AS q25, quantile_cont("{f}", 0.5) AS q50,
             quantile_cont("{f}", 0.75) AS q75, quantile_cont("{f}", 0.9) AS q90,
             quantile_cont("{f}", 0.99) AS q99
      FROM read_parquet('{MAT}') WHERE split='train'
    """).df().to_dict("records")[0]
    r["zero_ratio"] = round(r["n_zero"] / r["nn"], 4) if r["nn"] else None
    out[f] = r

# 按值分桶（CASE 阈值）看 scrplus 到底有没有区分力
out["scrplus_by_value"] = con.execute(f"""
  SELECT
    CASE WHEN scrplus_90 IS NULL THEN 'null'
         WHEN scrplus_90=0 THEN 'eq0'
         WHEN scrplus_90>0 AND scrplus_90<=0.5 THEN '(0,0.5]'
         WHEN scrplus_90>0.5 AND scrplus_90<=1 THEN '(0.5,1]'
         WHEN scrplus_90>1 AND scrplus_90<=5 THEN '(1,5]'
         WHEN scrplus_90>5 THEN '>5' END AS grp,
    count(*) AS n, round(avg(y10),4) AS hit10, round(avg(y5),4) AS hit5,
    min(scrplus_90) AS lo, max(scrplus_90) AS hi
  FROM read_parquet('{MAT}') WHERE split='train' AND y10 IS NOT NULL
  GROUP BY 1 ORDER BY 1
""").df().to_dict("records")

# lu_cnt_20d 精确值 -> hit10（ties 真相）
out["lucnt20_by_value"] = con.execute(f"""
  SELECT lu_cnt_20d AS v, count(*) AS n, round(avg(y10),4) AS hit10, round(avg(y5),4) AS hit5
  FROM read_parquet('{MAT}') WHERE split='train' AND y10 IS NOT NULL AND lu_cnt_20d<=12
  GROUP BY 1 ORDER BY 1
""").df().to_dict("records")

# 关键：验证 ntile b2 伪影 —— b2 是否集中在某几个日期
out["scrplus_b2_dates"] = con.execute(f"""
  WITH t AS (
    SELECT trade_date, ntile(10) OVER (ORDER BY scrplus_90) AS b
    FROM read_parquet('{MAT}') WHERE split='train' AND scrplus_90 IS NOT NULL
  )
  SELECT b, count(*) AS n, count(DISTINCT trade_date) AS nd,
         min(trade_date) AS d0, max(trade_date) AS d1
  FROM t WHERE b IN (1,2,3,10) GROUP BY b ORDER BY b
""").df().to_dict("records")

(WS / "probe_dist_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("DIST PROBE DONE")
for f in ["scrplus_90", "scrplus_70", "lu_cnt_20d", "main_net_norm"]:
    print(f, json.dumps(out[f], ensure_ascii=False))

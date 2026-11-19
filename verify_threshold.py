# -*- coding: utf-8 -*-
"""核对标签口径：用户表述'超过20%' vs 矩阵标签 '>=20%' 的差异是否实质。"""
import json
from pathlib import Path
import duckdb
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
con = duckdb.connect()
q = f"""
SELECT
  count(*) FILTER (WHERE fwd_max_10d = 20.0) AS eq20_10,
  count(*) FILTER (WHERE fwd_max_5d  = 20.0) AS eq20_5,
  count(*) FILTER (WHERE y10 = 1 AND fwd_max_10d = 20.0) AS y10_eq20,
  count(*) FILTER (WHERE y5  = 1 AND fwd_max_5d  = 20.0) AS y5_eq20,
  count(*) FILTER (WHERE y10 = 1) AS n_y10,
  count(*) FILTER (WHERE y5  = 1) AS n_y5,
  min(fwd_max_10d) FILTER (WHERE y10=1) AS min_y10,
  min(fwd_max_5d)  FILTER (WHERE y5=1)  AS min_y5,
  count(*) FILTER (WHERE fwd_max_10d IS NOT NULL) AS lab10_n,
  count(*) FILTER (WHERE fwd_max_5d  IS NOT NULL) AS lab5_n
FROM read_parquet('{MAT}')
"""
r = con.execute(q).df()
print(r.to_string(index=False))
out = json.loads(r.to_json(orient="records"))[0]
(WS / "threshold_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE threshold_check.json")

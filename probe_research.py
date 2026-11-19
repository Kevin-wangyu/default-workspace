# -*- coding: utf-8 -*-
"""研究前置探针：基准池候选字段的分位阈值、概念强榜面板、扩展标签可行性。
纯读，零写入投研项目。输出 probe_research_out.json 到工作目录。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
MAT = (WS / "matrix.parquet").as_posix()
# serve 后台进程会把 _tops_cache 归档到 data_compact；自动挑实际存在的路径
_bar_cands = [
    Path(PROJ, "data_compact", "_tops_cache", "v1", "bars.parquet"),
    Path(PROJ, "data", "_tops_cache", "v1", "bars.parquet"),
    Path(PROJ, "data_compact_sync", "_tops_cache", "v1", "bars.parquet"),
]
_bar = next((x for x in _bar_cands if x.exists()), None)
assert _bar is not None, "bars.parquet not found in any candidate path"
BARS = f"read_parquet('{str(_bar).replace(chr(92), '/')}')"
CG = f"read_parquet('{P('data_compact','concept_date','*.parquet')}', union_by_name=true)"
QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"

con = duckdb.connect()
con.execute("SET threads=8")
out = {}

# 1) 基准池候选字段在 train 上的十分位边界 + 各桶 hit10
base_fields = ["scrplus_90", "scrplus_70", "lu_cnt_20d", "lu_cnt_10d", "vol20", "turnover_rate", "main_net_norm"]
qb = {}
for f in base_fields:
    rows = con.execute(f"""
      WITH t AS (
        SELECT "{f}" AS v, y10, y5,
          CASE WHEN "{f}" IS NULL THEN NULL ELSE ntile(10) OVER (ORDER BY "{f}") END AS b
        FROM read_parquet('{MAT}') WHERE split='train' AND y10 IS NOT NULL
      )
      SELECT b, count(*) AS n, min(v) AS lo, max(v) AS hi,
             round(avg(y10),4) AS hit10, round(avg(y5),4) AS hit5
      FROM t WHERE b IS NOT NULL GROUP BY b ORDER BY b
    """).df().to_dict("records")
    qb[f] = rows
out["base_quantiles"] = qb

# 2) 概念强榜面板覆盖
out["concept_panel"] = con.execute(f"""
  SELECT count(*) AS n_rows,
         count(DISTINCT substr(CAST(trade_date AS VARCHAR),1,10)) AS n_days,
         count(DISTINCT name) AS n_concepts,
         count(*) FILTER (WHERE is_strong) AS n_strong_rows
  FROM {BARS}
""").df().to_dict("records")

# 3) 扩展标签可行性：quote 全窗口窗口函数取样（某几天某几股）
out["ext_label_probe"] = con.execute(f"""
  WITH q AS (
    SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, high, close,
           row_number() OVER (ORDER BY substr(CAST(trade_date AS VARCHAR),1,10), code) AS rn
    FROM {QG}
  )
  SELECT count(*) AS n FROM q
""").df().to_dict("records")

# 4) 交易日序号范围（用于主线延续窗口）
out["date_span"] = con.execute(f"""
  SELECT min(trade_date) AS d0, max(trade_date) AS d1, count(DISTINCT trade_date) AS nd
  FROM read_parquet('{MAT}')
""").df().to_dict("records")

# 5) scrplus 语义抽样：低分位 vs 高分位的 hit10（确认数值方向）
out["scrplus_direction"] = con.execute(f"""
  WITH t AS (
    SELECT scrplus_90, y10, ntile(10) OVER (ORDER BY scrplus_90) AS b
    FROM read_parquet('{MAT}') WHERE split='train' AND scrplus_90 IS NOT NULL AND y10 IS NOT NULL
  )
  SELECT b, round(avg(scrplus_90),3) AS mean_val, round(avg(y10),4) AS hit10
  FROM t GROUP BY b ORDER BY b
""").df().to_dict("records")

(WS / "probe_research_out.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("PROBE DONE", json.dumps({
    "concept_panel": out["concept_panel"],
    "date_span": out["date_span"],
    "ext_label_probe": out["ext_label_probe"],
}, ensure_ascii=False))

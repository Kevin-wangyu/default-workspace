# -*- coding: utf-8 -*-
"""验证 duckdb RANGE 窗口语法 + matplotlib 中文字体 + concept_date 拆分可行性。纯读。"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\probe4_out.json")
con = duckdb.connect()
res = {}

QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"

# 1) RANGE BETWEEN FOLLOWING 语法验证
try:
    d = con.execute(f"""
WITH cal AS (
  SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS di
  FROM (SELECT DISTINCT trade_date FROM {QG})
), q AS (
  SELECT a.code, a.trade_date, a.close, a.high, c.di
  FROM {QG} a JOIN cal c USING (trade_date)
  WHERE a.code IN ('600519','000001')
), w AS (
  SELECT code, trade_date, di, close,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING) AS mx5,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5 FOLLOWING) AS c5,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS mx10,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS c10
  FROM q
)
SELECT trade_date, code, close, mx5, c5, mx10, c10,
       CASE WHEN c5=5 THEN (mx5/close-1)*100 END AS fwd_max_5d,
       CASE WHEN c10=10 THEN (mx10/close-1)*100 END AS fwd_max_10d
FROM w WHERE trade_date='2024-09-30' ORDER BY code
""").df()
    res["range_window"] = {"ok": True, "rows": d.astype(object).where(__import__("pandas").notnull(d), None).to_dict("records")}
except Exception as e:
    res["range_window"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# 2) 与 concept_picks 缓存 fwd_max 对照（同一天同一批 code）
try:
    d2 = con.execute(f"""
WITH cal AS (
  SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS di
  FROM (SELECT DISTINCT trade_date FROM {QG})
), q AS (
  SELECT a.code, a.trade_date, a.close, a.high, c.di
  FROM {QG} a JOIN cal c USING (trade_date)
), w AS (
  SELECT code, trade_date, close,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS mx10,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS c10
  FROM q
), mine AS (
  SELECT code, CASE WHEN c10=10 THEN (mx10/close-1)*100 END AS my_fwd10
  FROM w WHERE trade_date='2024-09-30'
), cached AS (
  SELECT code, CAST(fwd_max_10d AS DOUBLE) AS cache_fwd10
  FROM read_parquet('{P('data','concept_picks','trade_date=2024-09-30','part.parquet')}')
  WHERE fwd_max_10d IS NOT NULL
)
SELECT count(*) AS n, avg(abs(m.my_fwd10 - c.cache_fwd10)) AS mean_abs_diff,
       max(abs(m.my_fwd10 - c.cache_fwd10)) AS max_abs_diff
FROM mine m JOIN cached c USING (code)
""").df()
    res["label_consistency"] = {"ok": True, "rows": d2.astype(object).where(__import__("pandas").notnull(d2), None).to_dict("records")}
except Exception as e:
    res["label_consistency"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# 3) concept_date 拆分（unnest string_split）与 tops_bars 概念名匹配
try:
    d3 = con.execute(f"""
WITH cd AS (
  SELECT trade_date, code, trim(x) AS cname
  FROM read_parquet('{P('data_compact','concept_date','*.parquet')}', union_by_name=true),
       unnest(string_split(concepts, ';')) AS t(x)
  WHERE trade_date='2024-09-30'
), tops AS (
  SELECT DISTINCT CAST(trade_date AS VARCHAR) AS trade_date, name AS cname
  FROM read_parquet('{P('data','_tops_cache','v1','bars.parquet')}')
  WHERE trade_date='2024-09-30'
), pool AS (
  SELECT DISTINCT cd.trade_date, cd.code FROM cd JOIN tops USING (trade_date, cname)
)
SELECT count(*) AS pool_n FROM pool
""").df()
    res["pool_match"] = {"ok": True, "rows": d3.astype(object).where(__import__("pandas").notnull(d3), None).to_dict("records")}
except Exception as e:
    res["pool_match"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# 4) 中文字体
try:
    import matplotlib
    import matplotlib.font_manager as fm
    cands = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "FangSong", "Noto Sans CJK SC", "Source Han Sans SC"]
    installed = {f.name for f in fm.fontManager.ttflist}
    res["fonts"] = {"available": [c for c in cands if c in installed],
                    "total": len(installed)}
except Exception as e:
    res["fonts"] = {"error": f"{type(e).__name__}: {e}"}

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
print("DONE")

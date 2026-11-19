# -*- coding: utf-8 -*-
"""确认：scipy / daily_pct 口径 / inf 来源 / 日历文件 / 概念→成分可行性。纯读。"""
from __future__ import annotations
import json, glob
from pathlib import Path
import duckdb, pandas as pd, numpy as np

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\probe3_out.json")
con = duckdb.connect()
res = {}

try:
    import scipy
    res["scipy"] = scipy.__version__
except Exception as e:
    res["scipy"] = f"MISSING {type(e).__name__}"

QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"
DG = f"read_parquet('{P('data_compact','daily_pct','*.parquet')}', union_by_name=true)"

def q(name, sql):
    try:
        df = con.execute(sql).df()
        res[name] = {"n": int(len(df)), "rows": df.head(10).astype(object).where(pd.notnull(df.head(10)), None).to_dict("records")}
    except Exception as e:
        res[name] = {"error": f"{type(e).__name__}: {e}"}

# daily_pct 是否有 inf / 极端值
q("daily_pct_health", f"""SELECT
 count(*) AS n,
 count(*) FILTER (WHERE isinf(pct_change)) AS n_inf,
 count(*) FILTER (WHERE isnan(pct_change)) AS n_nan,
 min(pct_change) AS mn, max(pct_change) AS mx,
 avg(pct_change) AS av
FROM {DG}""")

q("quote_pct_health", f"""SELECT
 count(*) AS n,
 count(*) FILTER (WHERE isinf(pct_change)) AS n_inf,
 count(*) FILTER (WHERE isnan(pct_change)) AS n_nan,
 min(pct_change) AS mn, max(pct_change) AS mx, avg(pct_change) AS av
FROM {QG}""")

# daily_pct 是否 = close_T/close_{T-1}-1 (在同一 code 内按日期排序)
q("daily_pct_formula_check", f"""
WITH c AS (
  SELECT code, trade_date, close,
         lag(close) OVER (PARTITION BY code ORDER BY trade_date) AS prev_close
  FROM {QG}
), j AS (
  SELECT c.code, c.trade_date, c.close, c.prev_close, d.pct_change AS dp
  FROM c JOIN {DG} d USING (code, trade_date)
  WHERE c.prev_close IS NOT NULL AND c.prev_close > 0
)
SELECT count(*) AS n,
       avg(abs((close/prev_close-1)*100 - dp)) AS mean_abs_diff,
       max(abs((close/prev_close-1)*100 - dp)) AS max_abs_diff,
       count(*) FILTER (WHERE abs((close/prev_close-1)*100 - dp) > 0.01) AS n_gt001
FROM j
""")

# 涨停阈值口径：按 code 前缀分组看 pct_change 上界
q("pct_upper_tail", f"""
SELECT CASE
  WHEN left(code,2) IN ('30','68') THEN 'cy/kc 19.8'
  WHEN left(code,1) IN ('8','4') OR left(code,2)='92' THEN 'bj 29.8'
  ELSE 'main 9.8' END AS board,
 count(*) AS n, max(pct_change) AS mx,
 count(*) FILTER (WHERE pct_change > 9.7) AS n_gt97
FROM {DG} GROUP BY 1 ORDER BY 1
""")

# 日历文件清单
cals = sorted(glob.glob(str(Path(PROJ, "**", "*calendar*.parquet")), recursive=True))
res["calendar_files"] = [str(Path(f).relative_to(PROJ)) for f in cals]
for f in cals[:3]:
    try:
        d = pd.read_parquet(f)
        res["cal_" + Path(f).name] = {"n": len(d), "cols": list(d.columns),
                                      "d0": str(d.iloc[0, 0]), "d1": str(d.iloc[-1, 0])}
    except Exception as e:
        pass

# tops_bars 概念名 与 concept_date 的 concepts 是否可对上
q("tops_concept_names", f"""SELECT count(DISTINCT name) AS n_names, min(trade_date) AS d0, max(trade_date) AS d1
FROM read_parquet('{P('data','_tops_cache','v1','bars.parquet')}')""")

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
for k, v in res.items():
    print(k, json.dumps(v, ensure_ascii=False, default=str)[:700])
print("DONE")

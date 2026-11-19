# -*- coding: utf-8 -*-
"""建模前最后一批字段确认：纯读，不写项目任何文件。"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\probe2_out.json")

con = duckdb.connect()
res = {}

def q(name, sql):
    try:
        df = con.execute(sql).df()
        res[name] = {"n": int(len(df)), "cols": list(df.columns),
                     "rows": df.head(8).astype(object).where(__import__("pandas").notnull(df.head(8)), None).to_dict("records")}
    except Exception as e:
        res[name] = {"error": f"{type(e).__name__}: {e}"}

QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"
DG = f"read_parquet('{P('data_compact','daily_pct','*.parquet')}', union_by_name=true)"
CG = f"read_parquet('{P('data_compact','concept_date','*.parquet')}', union_by_name=true)"

q("quote_daily_pct_diff", f"""
SELECT count(*) AS n,
       avg(abs(a.pct_change - b.pct_change)) AS mean_abs_diff,
       max(abs(a.pct_change - b.pct_change)) AS max_abs_diff,
       count(*) FILTER (WHERE abs(a.pct_change - b.pct_change) > 0.5) AS n_diff_gt05
FROM (SELECT trade_date, code, pct_change FROM {QG}) a
JOIN (SELECT trade_date, code, pct_change FROM {DG}) b USING (trade_date, code)
""")

q("daily_pct_range", f"SELECT min(trade_date) AS d0, max(trade_date) AS d1, count(DISTINCT trade_date) AS nd, count(*) AS n FROM {DG}")
q("quote_range", f"SELECT min(trade_date) AS d0, max(trade_date) AS d1, count(DISTINCT trade_date) AS nd, count(*) AS n FROM {QG}")

q("tops_list_types", f"""SELECT list_type, count(*) AS n, count(DISTINCT trade_date) AS nd,
       min(rank) AS r0, max(rank) AS r1, sum(CASE WHEN is_strong THEN 1 ELSE 0 END) AS n_strong
FROM read_parquet('{P('data','_tops_cache','v1','bars.parquet')}') GROUP BY 1 ORDER BY 1""")

q("tops_meta_rowtypes", f"""SELECT row_type, count(*) AS n, count(DISTINCT trade_date) AS nd
FROM read_parquet('{P('data','_tops_cache','v1','meta.parquet')}') GROUP BY 1 ORDER BY 1""")

q("market_amount_range", f"""SELECT min(trade_date) AS d0, max(trade_date) AS d1, count(*) AS n,
       min(total_amount) AS mn, max(total_amount) AS mx, avg(total_amount) AS av
FROM read_parquet('{P('data','market_amount.parquet')}')""")

q("quote_nulls", f"""SELECT
 count(*) AS n,
 count(*) FILTER (WHERE close IS NULL) AS null_close,
 count(*) FILTER (WHERE high IS NULL) AS null_high,
 count(*) FILTER (WHERE amount IS NULL) AS null_amount,
 count(*) FILTER (WHERE turnover_rate IS NULL) AS null_tor,
 count(*) FILTER (WHERE pct_change IS NULL) AS null_pct,
 count(*) FILTER (WHERE hot_rank IS NULL) AS null_hot,
 count(*) FILTER (WHERE scrplus_90 IS NULL) AS null_s90,
 count(*) FILTER (WHERE scrplus_70 IS NULL) AS null_s70,
 count(*) FILTER (WHERE huge_order_net IS NULL) AS null_huge,
 count(*) FILTER (WHERE big_order_net IS NULL) AS null_big,
 count(*) FILTER (WHERE medium_order_net IS NULL) AS null_med,
 count(*) FILTER (WHERE small_order_net IS NULL) AS null_small,
 count(*) FILTER (WHERE industry IS NULL) AS null_ind
FROM {QG}""")

q("concept_date_nulls", f"""SELECT count(*) AS n,
 count(*) FILTER (WHERE concepts IS NULL OR concepts='') AS null_or_empty,
 max(length(concepts) - length(replace(concepts,';','')) + 1) AS max_n_concepts,
 avg(length(concepts) - length(replace(concepts,';','')) + 1) AS avg_n_concepts
FROM {CG}""")

import glob as _glob
_cal = sorted(_glob.glob(str(Path(PROJ, "**", "trading_calendar.parquet")), recursive=True))
res["calendar_files"] = [str(Path(f).relative_to(PROJ)) for f in _cal]
if _cal:
    q("calendar_range", f"""SELECT min(trade_date) AS d0, max(trade_date) AS d1, count(*) AS n
FROM read_parquet('{_cal[0].replace(chr(92), '/')}')""")

# concept_picks 缓存 fwd_max 抽样（用于标签一致性校验）
q("picks_fwd_sample", f"""SELECT trade_date, code, close, fwd_max_5d, fwd_max_10d
FROM read_parquet('{P('data','concept_picks','**','*.parquet')}', hive_partitioning=true, union_by_name=true)
WHERE trade_date IN ('2024-09-30','2025-03-14','2025-08-15') AND fwd_max_10d IS NOT NULL
LIMIT 12""")

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
for k, v in res.items():
    print(k, json.dumps(v, ensure_ascii=False, default=str)[:600])
print("DONE")

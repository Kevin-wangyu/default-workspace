# -*- coding: utf-8 -*-
"""在 research_matrix 上一次性算 C7 池 streak，验证 streak>=2 真实存在。纯读。"""
from pathlib import Path
import duckdb
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS / "research_matrix.parquet").as_posix()
con = duckdb.connect(); con.execute("SET threads=8")
C7 = """(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
  AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
  AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
# 全区间算 streak
df = con.execute(f"""
WITH g AS (
  SELECT trade_date, code, CAST({C7} AS INT) c7,
         row_number() OVER (PARTITION BY code ORDER BY di) rn
  FROM read_parquet('{RM}')
),
run AS (SELECT *, di_dummy FROM g WHERE c7=1)
SELECT trade_date, code, row_number() OVER (PARTITION BY code, grp ORDER BY trade_date) streak
FROM (
  SELECT trade_date, code,
         (SELECT 1) AS di_dummy,
         di - row_number() OVER (PARTITION BY code ORDER BY di) AS grp
  FROM read_parquet('{RM}') WHERE {C7}
) t
""").df() if False else None

# 简化：直接算
df = con.execute(f"""
SELECT trade_date, code,
       row_number() OVER (PARTITION BY code, grp ORDER BY trade_date) AS streak
FROM (
  SELECT trade_date, code, di,
         di - row_number() OVER (PARTITION BY code ORDER BY di) AS grp
  FROM read_parquet('{RM}') WHERE {C7}
) t
""").df()
print("C7 rows total =", len(df))
s2 = df[df.streak >= 2]
print("streak>=2 rows =", len(s2), "  distinct dates =", s2.trade_date.nunique())
print("max streak =", df.streak.max())
# 找 streak>=2 最多的日期
top = s2.groupby("trade_date").size().sort_values(ascending=False).head(10)
print("\nTop dates with streak>=2 counts:")
for d, n in top.items():
    print(f"  {d}: {n} 只连续在池")
# 交叉测试日期
for d in ["2026-10-30", "2024-09-27", "2025-02-10"]:
    sub = s2[s2.trade_date == d]
    print(f"\n{d}: streak>=2 = {len(sub)} 只")

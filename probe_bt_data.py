# -*- coding: utf-8 -*-
"""回测前置探查：确认 research_matrix 日期覆盖、C6/C7 样本量、区间内前向路径完整性。"""
import sys
from pathlib import Path
import duckdb, numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
r=con.execute(f"SELECT min(trade_date),max(trade_date),count(*),count(DISTINCT trade_date),count(DISTINCT code) FROM read_parquet('{RM}')").fetchone()
print("矩阵: min=%s max=%s rows=%d days=%d codes=%d"%r, flush=True)
# 目标区间内各 split 天数与行数
r2=con.execute(f"""SELECT split,count(*) n,count(distinct trade_date) nd,min(trade_date),max(trade_date)
FROM read_parquet('{RM}') WHERE trade_date>='2024-03-13' AND trade_date<='2026-11-01'
GROUP BY split ORDER BY split""").fetchall()
for x in r2: print("区间split:",x, flush=True)
# 检查 di10 完整（lead di 10）
r3=con.execute(f"""WITH g AS (SELECT trade_date,di,code,lead(di,10) OVER (PARTITION BY code ORDER BY di) d10 FROM read_parquet('{RM}'))
SELECT count(*) total, count(*) FILTER (WHERE d10=di+10) complete FROM g
WHERE trade_date>='2024-03-13' AND trade_date<='2026-11-01'""").fetchone()
print("区间样本 total=%d 前向10日完整=%d"%(r3[0],r3[1]), flush=True)
con.close()

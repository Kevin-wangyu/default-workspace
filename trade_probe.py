# -*- coding: utf-8 -*-
"""操盘策略数据探查：确认前向OHLC路径/停牌/缺口口径。纯读。
研究标签 fwd_max 起点=T收盘；实盘最早T+1开盘可买。需量化可成交价口径。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect();con.execute("SET threads=8")
print("=== columns ===")
cols=[r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RM}')").fetchall()]
print(cols)
print("\n=== OHLC + volume 覆盖 ===")
q=con.execute(f"""SELECT
 count(*) n,
 count(open) n_open, count(high) n_high, count(low) n_low, count(close) n_close,
 count(volume) n_vol,
 count(*) FILTER (WHERE volume=0) n_vol0,
 count(*) FILTER (WHERE low=high) n_flat,
 min(di) mindi,max(di) maxdi
FROM read_parquet('{RM}')""").fetchone()
print(dict(zip(['n','n_open','n_high','n_low','n_close','n_vol','n_vol0','n_flat','mindi','maxdi'],q)))
print("\n=== 交易日/缺口口径样例（1只票5行） ===")
samp=con.execute(f"""SELECT trade_date,code,open,high,low,close,pct_change,volume,di
FROM read_parquet('{RM}') WHERE di BETWEEN 500 AND 505 ORDER BY code LIMIT 8""").df()
print(samp.to_string(index=False))
print("\n=== T+1 可买性：涨停(open=high=close 且 pct_change>=9.8)比例 ===")
q2=con.execute(f"""SELECT
 count(*) FILTER (WHERE pct_change>=9.8) n_lu,
 count(*) FILTER (WHERE pct_change>=19.8) n_lu20,
 count(*) FILTER (WHERE volume=0) n_susp,
 count(*) n
FROM read_parquet('{RM}')""").fetchone()
print(dict(zip(['n_lu','n_lu20','n_susp','n'],q2)))
print("DONE")

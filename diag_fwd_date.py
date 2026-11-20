# -*- coding: utf-8 -*-
"""诊断 2026-10-30 fwd_max_10d 差异：研究矩阵null vs 新版有值。纯读。"""
import sys
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
import duckdb
from config import COMPACT_DIR
from pathlib import Path
QG=f"read_parquet('{(COMPACT_DIR/'quote'/'*.parquet').as_posix()}', union_by_name=true)"
RM=(Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")/'research_matrix.parquet').as_posix()
con=duckdb.connect()
print("quote max date:", con.execute(f"SELECT max(substr(CAST(trade_date AS VARCHAR),1,10)) FROM {QG}").fetchone()[0])
print("matrix max date:", con.execute(f"SELECT max(trade_date) FROM read_parquet('{RM}')").fetchone()[0])
for d in ["2026-10-30","2026-11-10"]:
    rows=con.execute(f"""SELECT substr(CAST(trade_date AS VARCHAR),1,10) dt FROM {QG}
        WHERE substr(CAST(trade_date AS VARCHAR),1,10)>? GROUP BY 1 ORDER BY 1 LIMIT 12""",[d]).fetchall()
    print(f"{d} 之后交易日: {[r[0] for r in rows]}  (n={len(rows)})")
print("\n矩阵 600261 在 2026-10-30 的 fwd 字段:")
print(con.execute(f"SELECT trade_date,fwd_max_5d,fwd_max_10d,fwd_n5,fwd_n10 FROM read_parquet('{RM}') WHERE code='600261' AND trade_date='2026-10-30'").df().to_string())
con.close()

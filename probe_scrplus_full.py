# -*- coding: utf-8 -*-
"""查穿 scrplus 全程 + 原始数据源，确认是否退化；检查 R3 条件有效性。
纯读，零写入项目。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
MAT = (WS / "matrix.parquet").as_posix()
QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"
con = duckdb.connect()
con.execute("SET threads=8")
out = {}

# 1) matrix 全区间按 split 看 scrplus
out["matrix_scrplus_by_split"] = con.execute(f"""
  SELECT split, count(*) AS n, count(scrplus_90) AS nn,
         count(DISTINCT scrplus_90) AS nd90,
         count(DISTINCT scrplus_70) AS nd70,
         min(scrplus_90) AS mn, max(scrplus_90) AS mx,
         count(*) FILTER (WHERE scrplus_90>0) AS n_pos90,
         count(*) FILTER (WHERE scrplus_70>0) AS n_pos70
  FROM read_parquet('{MAT}') GROUP BY split ORDER BY split
""").df().to_dict("records")

# 2) 原始 quote 数据源 scrplus 分布（按月文件抽样几个）
out["raw_quote_scrplus"] = con.execute(f"""
  SELECT substr(CAST(trade_date AS VARCHAR),1,7) AS ym,
         count(*) AS n, count(scrplus_90) AS nn,
         count(DISTINCT scrplus_90) AS nd,
         min(scrplus_90) AS mn, max(scrplus_90) AS mx,
         count(*) FILTER (WHERE scrplus_90>0) AS n_pos
  FROM {QG} GROUP BY 1 ORDER BY 1
""").df().to_dict("records")

# 3) R3 条件 scrplus_90>=0 在 train 的过滤效果（应该几乎恒真）
out["r3_scrplus_filter"] = con.execute(f"""
  SELECT count(*) AS n,
         count(*) FILTER (WHERE scrplus_90>=0) AS n_ge0,
         count(*) FILTER (WHERE scrplus_90>0) AS n_gt0,
         count(*) FILTER (WHERE scrplus_90 IS NULL) AS n_null
  FROM read_parquet('{MAT}') WHERE split='train'
""").df().to_dict("records")

# 4) 找 quote 里所有可能的筹码/集中度代理字段
cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {QG}").fetchall()]
out["quote_cols"] = cols

(WS / "probe_scrplus_full_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("SCRPLUS FULL DONE")
print("by_split", json.dumps(out["matrix_scrplus_by_split"], ensure_ascii=False))
print("r3_filter", json.dumps(out["r3_scrplus_filter"], ensure_ascii=False))
print("quote_cols", cols)
print("raw_quote sample", json.dumps(out["raw_quote_scrplus"][:4], ensure_ascii=False))

# -*- coding: utf-8 -*-
"""修复 c7_picks 历史分区 matched_concepts 类型不一致（list<string> vs large_string）。

问题：serve 增量写入的 10 个近期分区 matched_concepts=large_string，
      prebuild 历史 637 个分区=list<string>，4 个空分区只有 trade_date/code 两列。
      archive_month 的 union_by_name 只统一列名不统一类型 → 月合并 Conversion Error。

修复：以正确分区为模板 schema，把这 10+4 个分区用 pa.Table.from_pandas(schema=模板)
      覆盖写回（只重写 part.parquet 内容，路径不变，不删除任何文件/目录）。

用法：先 --dry-run 看清单，再正式跑。
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
C7 = PROJ / "data" / "c7_picks"
DRY = "--dry-run" in sys.argv

# 1) 找模板 schema（list<string> 的正确分区）
schema = None
template = None
for p in sorted(C7.glob("trade_date=*/part.parquet")):
    try:
        sch = pq.read_schema(p)
    except Exception:
        continue
    if "matched_concepts" in sch.names and "list" in str(sch.field("matched_concepts").type).lower():
        schema, template = sch, p
        break
assert schema is not None, "找不到 list<string> 模板分区"
print("TEMPLATE=", template.parent.name, "cols=", len(schema.names), flush=True)

# 2) 找需修复的分区：类型非 list 或缺列
bad = []
for p in sorted(C7.glob("trade_date=*/part.parquet")):
    try:
        sch = pq.read_schema(p)
    except Exception as e:
        bad.append((p, "SCHEMA_ERR:" + str(e)[:30])); continue
    if "matched_concepts" not in sch.names:
        bad.append((p, "MISSING_COL")); continue
    t = str(sch.field("matched_concepts").type).lower()
    if "list" not in t:
        bad.append((p, t))
print("NEED_FIX=", len(bad), flush=True)
for p, why in bad:
    print("  ", p.parent.name, why, flush=True)

if DRY:
    print("DRY_RUN_DONE", flush=True); sys.exit(0)

# 3) 逐分区重写（覆盖 part.parquet，不删除）
fixed = 0
for p, why in bad:
    d = p.parent.name.split("=", 1)[1]
    if why == "MISSING_COL" or why.startswith("SCHEMA_ERR"):
        # 空分区：写空表（完整 schema）
        tbl = pa.Table.from_pylist([], schema=schema)
    else:
        df = pd.read_parquet(p)
        # matched_concepts: str/list/ndarray → python list[str]
        def norm(x):
            if x is None or (isinstance(x, float) and pd.isna(x)): return []
            if hasattr(x, "tolist"): x = x.tolist()
            if isinstance(x, str): return [s for s in x.split(";") if s]
            return [str(s) for s in list(x) if s]
        df["matched_concepts"] = df["matched_concepts"].map(norm)
        # 对齐模板列（缺列补空，多余列丢弃）
        for c in schema.names:
            if c not in df.columns:
                df[c] = None
        tbl = pa.Table.from_pandas(df[[c for c in schema.names]], schema=schema, preserve_index=False)
    pq.write_table(tbl, p)   # 覆盖内容，路径不变，零删除
    fixed += 1
print("FIXED=", fixed, flush=True)
print("FIX_DONE", flush=True)

# -*- coding: utf-8 -*-
"""探查关键 parquet 文件 schema，纯读。"""
from __future__ import annotations
import sys, json, glob, os
from pathlib import Path
import pandas as pd

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\explore_schemas_out.json")

targets = {
    "quote": os.path.join(PROJ, "data", "quote", "**", "*.parquet"),
    "quote_compact": os.path.join(PROJ, "data_compact", "quote", "*.parquet"),
    "concept_date": os.path.join(PROJ, "data", "concept_date", "**", "*.parquet"),
    "concept_date_compact": os.path.join(PROJ, "data_compact", "concept_date", "*.parquet"),
    "market_amount": os.path.join(PROJ, "data", "market_amount.parquet"),
    "concept_meta": os.path.join(PROJ, "data", "concept_meta.parquet"),
    "tops_bars": os.path.join(PROJ, "data", "_tops_cache", "v1", "bars.parquet"),
    "tops_meta": os.path.join(PROJ, "data", "_tops_cache", "v1", "meta.parquet"),
    "concept_picks": os.path.join(PROJ, "data", "concept_picks", "**", "*.parquet"),
    "daily_pct": os.path.join(PROJ, "data_compact", "daily_pct", "*.parquet"),
    "industry_flow": os.path.join(PROJ, "data_compact", "industry_flow", "*.parquet"),
}

res = {}
for k, pat in targets.items():
    files = sorted(glob.glob(pat, recursive=True))
    if not files:
        res[k] = {"files": 0}
        continue
    f = files[-1]
    try:
        df = pd.read_parquet(f)
        res[k] = {
            "files": len(files),
            "last_file": os.path.relpath(f, PROJ),
            "n_rows": int(len(df)),
            "cols": list(df.columns),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
            "sample": df.head(2).astype(object).where(pd.notnull(df.head(2)), None).to_dict("records"),
        }
    except Exception as e:
        res[k] = {"files": len(files), "error": f"{type(e).__name__}: {e}"}

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
for k, v in res.items():
    print(k, "files=", v.get("files"), "rows=", v.get("n_rows"), "cols=", v.get("cols"))
print("DONE")

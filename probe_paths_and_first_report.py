# -*- coding: utf-8 -*-
"""核对：①第一次报告最优规则原始数字 ②_tops_cache bars/meta 实际路径。纯读。"""
from pathlib import Path
import json
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")

# 第一次报告关键数字
for fn in ["search_results.json","report_data.json"]:
    p=WS/fn
    if p.exists():
        d=json.loads(p.read_text(encoding="utf-8"))
        print(f"=== {fn} keys:",list(d.keys()))
        if fn=="search_results.json":
            for k in ["baseline","grade_summary"]:
                if k in d: print(f"  {k}:",json.dumps(d[k],ensure_ascii=False)[:800])
            grades=d.get("grades",[])
            if isinstance(grades,list):
                for g in grades[:2]:
                    print("  GRADE:",json.dumps(g,ensure_ascii=False)[:900])
        else:
            for k in ["baseline","recommended"]:
                if k in d: print(f"  {k}:",json.dumps(d[k],ensure_ascii=False)[:500])

print("\n=== _tops_cache 路径探测 ===")
cands=[
 PROJ/"data/_tops_cache/v1/bars.parquet",
 PROJ/"data/_tops_cache/v1/meta.parquet",
 PROJ/"data_compact/_tops_cache/v1/bars.parquet",
 PROJ/"data_compact/_tops_cache/v1/meta.parquet",
]
for p in cands:
    print(("EXISTS " if p.exists() else "MISSING"),p, (p.stat().st_size if p.exists() else ""))

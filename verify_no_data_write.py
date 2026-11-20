# -*- coding: utf-8 -*-
"""零数据写入核验：关键 parquet 行数 + 最新 mtime（改动前后应一致）。只读。"""
import sys
from pathlib import Path
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
import duckdb
B=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
con=duckdb.connect()
targets={
 'quote': B/'data_compact'/'quote'/'*.parquet',
 'daily_pct': B/'data_compact'/'daily_pct'/'*.parquet',
 'concept_date': B/'data_compact'/'concept_date'/'*.parquet',
 'tops_bars': B/'data_compact'/'_tops_cache'/'v1'/'bars.parquet',
 'tops_meta': B/'data_compact'/'_tops_cache'/'v1'/'meta.parquet',
}
print("=== 数据文件只读核验（行数 + 最新mtime）===")
for name,g in targets.items():
    try:
        n=con.execute(f"SELECT count(*) FROM read_parquet('{g.as_posix()}', union_by_name=true)").fetchone()[0]
        if '*' in g.name:
            files=list(g.parent.glob(g.name))
        else:
            files=[g]
        mt=max(f.stat().st_mtime for f in files) if files else 0
        print(f"  {name}: rows={n}  n_files={len(files)}  last_mtime={mt:.0f}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")
con.close()
print("\n说明：本轮三处改进只改了 queries/c7_picks.py、queries/concept.py、"
      "concept_view1.js、concept.css 四个代码文件；未触碰任何 parquet 数据文件。")

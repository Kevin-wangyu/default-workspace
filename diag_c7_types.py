# -*- coding: utf-8 -*-
"""探查 c7_picks 日分区 matched_concepts 的类型分布。纯读，用 pyarrow 读 schema。"""
from pathlib import Path
import pyarrow.parquet as pq
from collections import Counter
C7_POOL_DIR = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay\data\c7_picks")
rows = []
for p in sorted(C7_POOL_DIR.glob('trade_date=*/part.parquet')):
    d = p.parent.name.split('=', 1)[1]
    try:
        sch = pq.read_schema(p)
        t = str(sch.field('matched_concepts').type) if 'matched_concepts' in sch.names else 'MISSING'
        rows.append((d, t))
    except Exception as e:
        rows.append((d, 'ERR:' + str(e)[:40]))
cnt = Counter(t for _, t in rows)
print("TOTAL_PARTITIONS=", len(rows))
print("TYPE_DIST=", dict(cnt))
vc = [d for d, t in rows if 'string' in t.lower() and 'list' not in t.lower()]
lc = [d for d, t in rows if 'list' in t.lower()]
print("VARCHAR_COUNT=", len(vc), "first=", vc[:15])
print("LIST_COUNT=", len(lc), "first=", lc[:5])
print("VARCHAR_DATES_ALL=", vc)

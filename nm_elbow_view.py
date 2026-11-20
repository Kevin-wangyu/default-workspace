# -*- coding: utf-8 -*-
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"nm_analysis_out.json").read_text(encoding="utf-8"))
print("=== m=20 边际增量 hit(n)-hit(n_prev) 及 每多持1日的边际 ===")
for sp in ['train','oos']:
    print(f"-- {sp} --")
    for e in D['elbow']:
        if e['m']==20 and e['split']==sp:
            print(f"  {e['n_from']}->{e['n_to']}: Δhit={e['d_hit']*100:+.2f}pct  每多1日={e['per_day']*100:+.3f}pct/日")

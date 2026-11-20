# -*- coding: utf-8 -*-
"""读 focused_extras_out.json 拿 C6/C7 双期数字 + 近端 C6 覆盖。纯读。"""
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
d=json.loads((WS/'focused_extras_out.json').read_text(encoding='utf-8'))
print("=== thresholds:", d.get('thresholds'))
for sp in ['train','oos']:
    print(f"\n=== {sp} ===")
    for nm in ['C0 基准三类','C2 +近涨停+逼近日高','C6 C2+动量+多头(双叠加)','C7 C6+龙头概念']:
        r=d['combos'][sp].get(nm)
        if not r: continue
        y10=r['y10']; y5=r['y5']
        print(f"  {nm}: n={r['n']} hit5={y5['hit']} hit10={y10['hit']} "
              f"lift10={y10['lift']} delta10={y10['delta']} p10={y10['p']}")

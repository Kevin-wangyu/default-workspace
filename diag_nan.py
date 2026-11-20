# -*- coding: utf-8 -*-
"""定位 HTML 中 nan/None 的真实上下文（剥离 base64 后）。"""
from pathlib import Path
import re
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
for name in ["C7策略_T1修正回测汇报.html","C7策略_T1修正回测汇报_仅主板.html"]:
    h=(WS/name).read_text(encoding="utf-8")
    clean=re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+","[IMG]",h)
    print("===",name,"===")
    for kw in ["nan","NaN","None","不可得"]:
        idxs=[m.start() for m in re.finditer(re.escape(kw),clean)]
        print(f"  {kw}: n={len(idxs)}")
        for i in idxs[:5]:
            print("    ..."+clean[max(0,i-60):i+60].replace("\n"," ")+"...")

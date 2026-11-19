# -*- coding: utf-8 -*-
from pathlib import Path
import re, json
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
HTML=(WS/"选股因子增量归因研究报告.html").read_text(encoding="utf-8")
CA=json.loads((WS/"combo_attribution_out.json").read_text(encoding="utf-8"))
# 占位符命中项
for pat in [r'\{\{', r'\}\}', r'None', r'nan%', r'undefined']:
    m=re.findall('.{0,40}'+pat+'.{0,40}',HTML)
    print(f"PAT {pat}: n={len(m)}", m[:2])
# 概念延续数字
v=CA['concept_branch']['train']['主线延续']['y10']
print("主线延续train y10 =",v, "-> %.1f%%"%(v*100), "in HTML:", f"{v*100:.1f}%" in HTML)
print("出现 34.4% ?", "34.4%" in HTML)
for s in re.findall(r'.{0,50}主线延续.{0,120}',HTML)[:3]: print("CTX:",s[:170])

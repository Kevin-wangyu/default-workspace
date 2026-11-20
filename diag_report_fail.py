# -*- coding: utf-8 -*-
from pathlib import Path
import re
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
html=(WS/"C7策略_单池vs双池回测汇报.html").read_text(encoding="utf-8")
body=html[html.find("<body"):]
for pat in [r"\{\{", r"\}\}", r"None", r"nan%", r"TODO", r"XXX", r"待填"]:
    for m in re.finditer(pat, body):
        s=max(0,m.start()-40); e=min(len(body),m.end()+40)
        print(f"[{pat}] ...{body[s:e]}...")

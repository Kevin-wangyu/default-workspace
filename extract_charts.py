# -*- coding: utf-8 -*-
"""把 HTML 内嵌的 7 张图导出为 PNG 文件供视觉抽检。"""
import re, base64
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
HTML=(WS/"选股因子增量归因研究报告.html").read_text(encoding="utf-8")
imgs=re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)',HTML)
names=['c1_combo','c2_robust','c3_concept','c4_lag','c5_scrplus','c6_overfit','c7_layers']
for n,s in zip(names,imgs):
    p=WS/f"chart_{n}.png"
    p.write_bytes(base64.b64decode(s))
    print(p.name,p.stat().st_size)

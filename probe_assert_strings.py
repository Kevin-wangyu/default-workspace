# -*- coding: utf-8 -*-
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
h=(WS/"复利资产曲线_交互复盘.html").read_text(encoding="utf-8")
for pat in ["hovertemplate", "customdata", "hover_html",
            "createElement('th'", "el('th'", "el('td'", "e.textContent=String(text)",
            "%{x}<extra></extra>"]:
    print(repr(pat), "->", h.count(pat))
i=h.find("hovertemplate")
print("CTX:", repr(h[i-30:i+70]))
D=json.loads((WS/"interactive_equity_data.json").read_text(encoding="utf-8"))
for tag in ["c7","dual"]:
    print(tag,"maxdiff repr =", repr(D["pools"][tag]["max_equity_diff_vs_engine"]))

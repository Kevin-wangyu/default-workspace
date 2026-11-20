# -*- coding: utf-8 -*-
"""图表质量抽检：PIL 像素级（视觉模型能力边界兜底）。"""
from __future__ import annotations
import json,base64,io
from pathlib import Path
from PIL import Image
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
CH=json.loads((WS/'elastic_charts.json').read_text(encoding='utf-8'))
allok=True
for k,b in CH.items():
    im=Image.open(io.BytesIO(base64.b64decode(b))).convert('RGB')
    a=np.array(im)
    nonwhite=(a.sum(axis=2)<720).mean()
    colors=len(np.unique(a.reshape(-1,3)//32,axis=0))
    dark=(a.mean(axis=2)<100).mean()
    # 柱状图(E1/E4)天然纯色少,散点/折线图颜色多;统一 colors>10 + 内容密度/深色文字达标
    ok=nonwhite>0.02 and colors>10 and dark>0.005
    allok &= ok
    print(f"{k}: {im.size} nonwhite={nonwhite:.3f} colors={colors} dark={dark:.4f} -> {'OK' if ok else 'FAIL'}")
print("ALL_OK" if allok else "HAS_FAIL")

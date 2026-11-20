# -*- coding: utf-8 -*-
"""复利三图像素级质检（视觉模型能力边界的兜底）。"""
import json
from pathlib import Path
from PIL import Image
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
P=json.loads((WS/"compound_charts.json").read_text(encoding="utf-8"))
ok=True
for k,p in P.items():
    im=Image.open(p).convert("RGB");a=np.asarray(im)
    nw=(a.min(axis=2)<235).mean();cols=len(np.unique(a.reshape(-1,3),axis=0))
    edge=np.concatenate([a[0].min(axis=1)<200,a[-1].min(axis=1)<200,a[:,0].min(axis=1)<200,a[:,-1].min(axis=1)<200]).mean()
    good=nw>0.02 and cols>40 and edge<0.10; ok&=good
    print(f"{k}: {im.size} nonwhite={nw:.3f} colors={cols} edge={edge:.3f} -> {'OK' if good else 'FAIL'}")
print("AUDIT_COMPOUND_CHARTS="+("ALL_OK" if ok else "HAS_FAIL"))

# -*- coding: utf-8 -*-
"""组合层三图像素级质检：非白占比/色彩数/边缘裁切（视觉模型不可用时的兜底）。"""
import io, json
from pathlib import Path
from PIL import Image
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PCH=json.loads((WS/"portfolio_charts.json").read_text(encoding="utf-8"))
ok=True
for k,p in PCH.items():
    im=Image.open(p).convert("RGB"); a=np.asarray(im)
    nonwhite=(a.min(axis=2)<235).mean()
    colors=len(np.unique(a.reshape(-1,3),axis=0))
    edge=np.concatenate([a[0].min(axis=1)<200,a[-1].min(axis=1)<200,
                         a[:,0].min(axis=1)<200,a[:,-1].min(axis=1)<200]).mean()
    good=nonwhite>0.02 and colors>40 and edge<0.10
    ok &= good
    print(f"{k}: {im.size} nonwhite={nonwhite:.3f} colors={colors} edge={edge:.3f} -> {'OK' if good else 'FAIL'}")
print("AUDIT_PORTFOLIO_CHARTS="+("ALL_OK" if ok else "HAS_FAIL"))

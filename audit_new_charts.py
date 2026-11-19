# -*- coding: utf-8 -*-
"""新4图(c8-c11)像素质检：内容密度/配色/边缘裁切。视觉模型边界下的兜底。"""
from pathlib import Path
import numpy as np
from PIL import Image
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
ok=True
for tag in ['c8','c9','c10','c11']:
    p=WS/f"chart_{tag}.png"
    im=Image.open(p).convert("RGB"); a=np.asarray(im).astype(int)
    h,w,_=a.shape
    nonwhite=float((a.min(axis=2)<235).mean())
    colors=len(np.unique(a.reshape(-1,3),axis=0))
    dark=float((a.max(axis=2)<100).mean())
    # 边缘带内容占比（检测裁切：边缘应有相当比例非白）
    edge=0.03
    bands=[a[:int(h*edge)],a[-int(h*edge):],a[:,:int(w*edge)],a[:,-int(w*edge):]]
    edge_nw=float(np.mean([(b.min(axis=2)<235).mean() for b in bands]))
    good = nonwhite>0.03 and colors>200 and edge_nw>0.01
    ok &= good
    print(f"{tag}: size={w}x{h} nonwhite={nonwhite:.3f} colors={colors} dark={dark:.4f} edge_nw={edge_nw:.3f} -> {'OK' if good else 'CHECK'}")
print("RESULT:","ALL_OK" if ok else "NEED_REVIEW")

# -*- coding: utf-8 -*-
"""n×m 六图像素质检：内容密度/配色/边缘裁切。视觉模型边界下 PIL 兜底。"""
from pathlib import Path
import numpy as np
from PIL import Image
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
ok=True
for t in ['n1','n2','n3','n4','n5','n6']:
    im=Image.open(WS/f"chart_{t}.png").convert("RGB"); a=np.asarray(im).astype(int)
    h,w,_=a.shape
    nonwhite=float((a.min(axis=2)<235).mean()); colors=len(np.unique(a.reshape(-1,3),axis=0))
    dark=float((a.max(axis=2)<100).mean()); e=0.03
    bands=[a[:int(h*e)],a[-int(h*e):],a[:,:int(w*e)],a[:,-int(w*e):]]
    edge_nw=float(np.mean([(b.min(axis=2)<235).mean() for b in bands]))
    good=nonwhite>0.03 and colors>200 and edge_nw>0.01
    ok&=good
    print(f"{t}: {w}x{h} nonwhite={nonwhite:.3f} colors={colors} dark={dark:.4f} edge_nw={edge_nw:.3f} -> {'OK' if good else 'CHECK'}")
print("RESULT:","ALL_OK" if ok else "NEED_REVIEW")

# -*- coding: utf-8 -*-
"""图表中文字渲染/内容密度像素兜底质检（视觉模型能力边界时使用）。"""
from pathlib import Path
from PIL import Image
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
fs=sorted(WS.glob('chart_t*.png'))
print("charts:",len(fs))
allok=True
for f in fs:
    im=Image.open(f).convert('RGB');a=np.array(im)
    nonwhite=float((a.min(axis=2)<230).mean())
    dark=float((a.max(axis=2)<100).mean())
    colors=len(np.unique(a.reshape(-1,3),axis=0))
    # 边缘裁切检测：四边10px内的深色像素占比（过高说明文字被切）
    h,w=a.shape[:2]
    edge=np.concatenate([a[:10].reshape(-1,3),a[-10:].reshape(-1,3),a[:,:10].reshape(-1,3),a[:,-10:].reshape(-1,3)])
    edge_dark=float((edge.max(axis=1)<100).mean())
    ok=nonwhite>0.03 and colors>50 and edge_dark<0.15
    allok&=ok
    print(f" {f.name:14s} size={im.size} nonwhite={nonwhite:.3f} dark={dark:.4f} colors={colors:5d} edge_dark={edge_dark:.4f} {'OK' if ok else 'WARN'}")
print("ALL_OK" if allok and len(fs)==5 else "CHECK")

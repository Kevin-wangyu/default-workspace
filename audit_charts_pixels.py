# -*- coding: utf-8 -*-
"""视觉模型临时不可用时的兜底质检：PIL 像素级内容密度 + 边缘裁切检测 + 字体渲染确认。"""
from pathlib import Path
from PIL import Image
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
charts=sorted(WS.glob("chart_c*.png"))

# 中文字体确认
avail={f.name for f in fm.fontManager.ttflist}
for want in ["Microsoft YaHei","SimHei","SimSun"]:
    print(f"FONT {want}: {'OK' if want in avail else 'MISSING'}")

print("\n=== 每张图像素质检 ===")
allok=True
for p in charts:
    im=Image.open(p).convert("RGB")
    a=np.asarray(im)
    h,w,_=a.shape
    # 非白像素（内容）
    nonwhite=((a<245).any(axis=2)).mean()
    colors=len(np.unique(a.reshape(-1,3),axis=0))
    dark=((a<100).all(axis=2)).mean()
    # 边缘裁切：四边各 3% 带内的非白像素比例（若过高说明内容贴边/被裁）
    bh,bw=max(1,int(h*.03)),max(1,int(w*.03))
    edge=np.concatenate([a[:bh].reshape(-1,3),a[-bh:].reshape(-1,3),
                         a[:,:bw].reshape(-1,3),a[:,-bw:].reshape(-1,3)])
    edge_nw=((edge<245).any(axis=1)).mean()
    status="OK" if (0.05<nonwhite<0.6 and colors>20 and edge_nw<0.35) else "CHECK"
    if status=="CHECK": allok=False
    print(f"{p.name:24s} {w}x{h} nonwhite={nonwhite:.3f} colors={colors:4d} dark={dark:.4f} edge_nw={edge_nw:.3f} -> {status}")
print("\nPIXEL_AUDIT:", "ALL OK" if allok else "NEEDS REVIEW")

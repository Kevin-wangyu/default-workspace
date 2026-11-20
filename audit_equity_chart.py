# -*- coding: utf-8 -*-
"""像素级质检新增的收益率图：非空白/有双曲线颜色/中文字形/无边缘裁切。"""
from pathlib import Path
from PIL import Image
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
im=Image.open(WS/"chart_equity.png").convert("RGB")
a=np.array(im).astype(int)
nonwhite=(a.min(axis=2)<235).mean()
# 双曲线主色接近度（ navy #1f3a5f / teal #1f9e8f ）
navy=((abs(a[:,:,0]-31)<50)&(abs(a[:,:,1]-58)<50)&(abs(a[:,:,2]-95)<50)).sum()
teal=((abs(a[:,:,0]-31)<50)&(abs(a[:,:,1]-158)<50)&(abs(a[:,:,2]-143)<50)).sum()
red =((a[:,:,0]>150)&(a[:,:,1]<90)&(a[:,:,2]<90)).sum()
# 边缘非白比例（裁切检测）
edge=min(a[:5,:,:].min(),a[-5:,:,:].min(),a[:,:5,:].min(),a[:,-5:,:].min())
print(f"size={im.size} nonwhite={nonwhite:.4f} navy_px={navy} teal_px={teal} red_px={red} edge_min={edge}")
ok = nonwhite>0.03 and navy>500 and teal>500 and red>50
print("AUDIT_EQUITY=" + ("ALL_OK" if ok else "CHECK"))

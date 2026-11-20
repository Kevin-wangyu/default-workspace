# -*- coding: utf-8 -*-
"""复核 C7 逐日基线：确认 170/580 到底对应哪个口径。纯读。"""
from pathlib import Path
import json
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"c7_daily_out.json").read_text(encoding="utf-8"))
daily=D['daily']
print("top keys:",list(D.keys()))
print("daily len:",len(daily))
print("sample row:",daily[0])
n=np.array([d['n'] for d in daily],dtype=float)
h10=np.array([d['hit10'] for d in daily],dtype=float)
h10v=h10[~np.isnan(h10)]
print("--- 选股数口径 ---")
print("days total:",len(daily))
print("days n==0:",int((n==0).sum()))
print("days n>=1:",int((n>=1).sum()),"占比=%.2f%%"%((n>=1).mean()*100))
print("n分布: min=%.0f med=%.0f max=%.0f mean=%.2f"%(np.nanmin(n),np.nanmedian(n),np.nanmax(n),np.nanmean(n)))
print("--- hit10 口径 (n>=1 的有效日) ---")
valid=(n>=1)&(~np.isnan(h10))
hv=h10[valid]
print("valid days:",len(hv))
print("days hit10==0 (n>=1):",int((hv==0).sum()))
print("days hit10>0:",int((hv>0).sum()))
for th in [0.25,0.5,0.6,0.7,0.75]:
    print(f"days hit10>={th:.2f}:",int((hv>=th).sum()), "占比(/all580)=%.2f%%"%((hv>=th).sum()/len(daily)*100))
print("--- 全580日(含n=0视hit=0) ---")
h10f=np.nan_to_num(h10,nan=0.0)
for th in [0.5,0.75]:
    print(f"days hit10f>={th}:",int((h10f>=th).sum()))
print("--- 170 到底对应谁 ---")
print("n>=1 days =",int((n>=1).sum()))
print("hit10>=0.5 (valid) =",int((hv>=0.5).sum()))
print("hit10>0.5 (valid) =",int((hv>0.5).sum()))
print("days_ge75+days_50_75 from overall:",D.get('overall',{}).get('days_ge75'),D.get('overall',{}).get('days_50_75'))
print("DONE")

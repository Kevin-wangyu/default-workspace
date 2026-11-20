# -*- coding: utf-8 -*-
"""策略有效性（T+1 修正后重算）：逐笔期望的统计显著性 + 成本后期望。
支持两套口径：BT_SUFFIX="" 正常 / "_main" 仅主板。只用已落盘明细，不改数字。
注意：T+1 修正后期望转负，sig 判定会自动变为"显著为负/不显著"，不沿用旧结论。
"""
from pathlib import Path
import os, json
import numpy as np, pandas as pd
from scipy import stats

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
SUFFIX = os.environ.get("BT_SUFFIX", "")
OUT = json.loads((WS/f"backtest_out{SUFFIX}.json").read_text(encoding="utf-8"))
COST = OUT["config"]["cost"]
POOLS = [("C7单池",f"backtest_detail_c7{SUFFIX}.csv"),
         ("C6+C7双池",f"backtest_detail_dual{SUFFIX}.csv")]
board = "仅主板" if SUFFIX=="_main" else "正常全市场"

print("="*78)
print(f"逐笔期望统计显著性 [{board}]（H0: 期望=0；t检验 + 95%CI）")
print("="*78)
res = {}
for g, fn in POOLS:
    d = pd.read_csv(WS/fn, encoding="utf-8-sig")
    fl = d[d["filled"].astype(bool)]
    res[g] = {}
    for seg in ["train","oos","全区间"]:
        r = fl[fl.split==seg]["ret"].dropna().values if seg!="全区间" else fl["ret"].dropna().values
        n=len(r); mean=r.mean(); sd=r.std(ddof=1); sem=sd/np.sqrt(n)
        t=mean/sem; p=2*(1-stats.t.cdf(abs(t),df=n-1))
        lo,hi=mean-1.96*sem,mean+1.96*sem
        res[g][seg]=dict(n=n,mean=round(mean,4),sd=round(sd,3),sem=round(sem,4),
                          t=round(t,2),p=round(p,4),ci95=[round(lo,4),round(hi,4)],
                          net=round(mean-COST,4),
                          sig="显著为正" if (p<0.05 and mean>0) else ("显著为负" if (p<0.05 and mean<0) else "不显著"))
        print(f"{g:10s} {seg:5s} n={n:5d} 期望={mean:+.4f}% t={t:5.2f} p={p:.4f} "
              f"95%CI=[{lo:+.4f},{hi:+.4f}] 扣成本={mean-COST:+.4f}% => {res[g][seg]['sig']}")
    print("-"*78)
(WS/f"strategy_usefulness{SUFFIX}.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"SAVED strategy_usefulness{SUFFIX}.json")

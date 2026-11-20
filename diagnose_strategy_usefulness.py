# -*- coding: utf-8 -*-
"""回答"策略是不是没用"：从逐笔明细算期望的统计显著性 + 成本后期望。
只用已落盘明细，不改任何数字。"""
from pathlib import Path
import json
import numpy as np, pandas as pd
from scipy import stats

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
COST = OUT["config"]["cost"]
POOLS = [("C7单池","backtest_detail_c7.csv"),("C6+C7双池","backtest_detail_dual.csv")]

print("="*78)
print("逐笔期望的统计显著性（H0: 期望收益=0；t检验 + 95%CI）")
print("="*78)
res = {}
for g, fn in POOLS:
    d = pd.read_csv(WS/fn, encoding="utf-8-sig")
    fl = d[d["filled"].astype(bool)]
    res[g] = {}
    for seg in ["train","oos","全区间"]:
        r = fl[fl.split==seg]["ret"].dropna().values if seg!="全区间" else fl["ret"].dropna().values
        n = len(r); mean = r.mean(); sd = r.std(ddof=1); sem = sd/np.sqrt(n)
        t = mean/sem; p = 2*(1-stats.t.cdf(abs(t), df=n-1))
        lo, hi = mean-1.96*sem, mean+1.96*sem
        net = mean - COST
        res[g][seg] = dict(n=n, mean=round(mean,4), sd=round(sd,3), sem=round(sem,4),
                           t=round(t,2), p=round(p,4), ci95=[round(lo,4),round(hi,4)],
                           net=round(net,4),
                           sig="显著为正" if (p<0.05 and mean>0) else ("显著为负" if (p<0.05 and mean<0) else "不显著"))
        print(f"{g:10s} {seg:5s} n={n:5d} 期望={mean:+.4f}% 标准差={sd:5.2f}% "
              f"t={t:5.2f} p={p:.4f} 95%CI=[{lo:+.4f},{hi:+.4f}] "
              f"扣成本={net:+.4f}% => {res[g][seg]['sig']}")
    print("-"*78)

# 盈亏比画像
print("盈亏结构（平均盈利 / 平均亏损 / 盈亏比）")
for g, fn in POOLS:
    d = pd.read_csv(WS/fn, encoding="utf-8-sig")
    r = d[d["filled"].astype(bool)]["ret"].dropna().values
    win = r[r>0]; loss = r[r<0]
    print(f"  {g}: 胜率{(r>0).mean()*100:.1f}% 平均盈利{win.mean():+.2f}% "
          f"平均亏损{loss.mean():+.2f}% 盈亏比{abs(win.mean()/loss.mean()):.2f}")
print("="*78)
(WS/"strategy_usefulness.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
print("SAVED strategy_usefulness.json")

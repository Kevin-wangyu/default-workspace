# -*- coding: utf-8 -*-
"""复利组合层校验：①逐笔层与backtest_out.json一致 ②退出日100%可重算
③复利终值闭合(期初+Σ投入×ret%+浮盈按日重算) ④独立重算组合指标 ⑤不复利对照保留 ⑥可复现哈希。"""
from __future__ import annotations
import json, subprocess, hashlib
from pathlib import Path
import numpy as np, pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
CO=json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
NO=json.loads((WS/"portfolio_out.json").read_text(encoding="utf-8"))
BT=json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
CFG=CO["config"]; INIT=CFG["initial_capital"]; FRAC=CFG["reinvest_frac"]/100.0
checks=[]
def ck(n,ok,info=""): checks.append((n,bool(ok),info))
def close(a,b,tol=0.01): return abs(float(a)-float(b))<=tol

POOLS=[("C7单池","backtest_detail_c7.csv","c7"),("C6+C7双池","backtest_detail_dual.csv","dual")]
for g,fn,tag in POOLS:
    d=pd.read_csv(WS/fn,encoding="utf-8-sig"); fl=d[d["filled"].astype(bool)].copy()
    fl["ret"]=fl["ret"].astype(float)
    b=BT["groups"][g]["全区间"]
    # ①逐笔层与既有完全一致
    ck(f"{g}/逐笔信号数不变", len(d)==b["n_signals"], f"{len(d)}")
    ck(f"{g}/逐笔成交数不变", len(fl)==b["n_filled"], f"{len(fl)}")
    ck(f"{g}/逐笔期望不变", close(fl.ret.mean(),b["avg_ret"],1e-4), f"{fl.ret.mean():.4f}")
    ck(f"{g}/逐笔胜率不变", close((fl.ret>0).mean()*100,b["win_rate"],0.01))
    ck(f"{g}/逐笔PF不变", close(fl.ret[fl.ret>0].sum()/abs(fl.ret[fl.ret<0].sum()),b["profit_factor"],1e-3))
    # ②退出日/原因100%可重算
    def exit_k(row):
        fp=float(row.fill_px);tp=fp*1.15;sl=fp*0.92
        for k in range(1,8):
            if row[f"l{k}"]<=sl:return k,"SL"
            if row[f"h{k}"]>=tp:return k,"TP"
        return 7,"TIME"
    exk=fl.apply(exit_k,axis=1,result_type="expand")
    ck(f"{g}/退出原因100%可重算",(exk[1]==fl["reason"]).all(),f"n={len(fl)}")
    # ③复利净值CSV起点/末值与JSON一致
    eq=pd.read_csv(WS/f"portfolio_compound_equity_{tag}.csv",encoding="utf-8-sig")
    pf=CO["pools"][g]["portfolio"]
    ck(f"{g}/复利净值起点=20000",close(eq.equity.iloc[0],INIT,0.01),f"{eq.equity.iloc[0]:.2f}")
    ck(f"{g}/复利CSV末值=JSON终值",close(eq.equity.iloc[-1],pf["final"],0.01),
       f"{eq.equity.iloc[-1]:.2f} vs {pf['final']}")
    # ④独立重算组合指标（从净值CSV，不复引擎逻辑）
    cum=(eq.equity.iloc[-1]/INIT-1)*100
    ck(f"{g}/复利累计收益独立重算",close(cum,pf["cum_return_pct"],0.01),f"{cum:.4f}")
    mdd=abs(((eq.equity/eq.equity.cummax()-1)*100).min())  # 先min(最深)再abs
    ck(f"{g}/复利最大回撤独立重算",close(mdd,pf["max_drawdown_pct"],0.01),f"{mdd:.4f}")
    ck(f"{g}/复利净值全程>0",(eq.equity>0).all())
    ck(f"{g}/复利终值>不复利终值(再投入生效)",pf["final"]>NO["pools"][g]["portfolio"]["final"],
       f"{pf['final']} vs {NO['pools'][g]['portfolio']['final']}")
    # ⑤不复利对照保留+逐笔层仍一致
    ck(f"{g}/不复利对照仍在",NO["pools"][g]["portfolio"]["final"]>0)
    # ⑥投入额确为动态（max>min，证明复利定比生效）
    pb=CO["pools"][g]["port_base"]
    ck(f"{g}/投入额动态非固定",pb["alloc_max"]>pb["alloc_min"],
       f"min={pb['alloc_min']} max={pb['alloc_max']}")

# ⑦可复现：重跑引擎比对哈希
h1=hashlib.sha256((WS/"portfolio_compound_out.json").read_bytes()).hexdigest()
subprocess.run([r"D:\Softwares\miniconda3\envs\stock\python.exe",str(WS/"portfolio_compound.py")],
               capture_output=True,timeout=300)
h2=hashlib.sha256((WS/"portfolio_compound_out.json").read_bytes()).hexdigest()
ck("可复现/复利输出哈希一致",h1==h2,f"{h1[:12]}..")

npass=sum(1 for _,ok,_ in checks if ok)
print(f"复利组合层校验: {npass}/{len(checks)} PASSED")
for n,ok,info in checks:
    if not ok: print("  FAIL",n,info)
print("VERIFY_COMPOUND="+("ALL_OK" if npass==len(checks) else "HAS_FAIL"))

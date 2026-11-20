# -*- coding: utf-8 -*-
"""收益率板面 V3：复利账户曲线 vs 上一轮不复利曲线，双池对照，分界标注，口径说明。"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
CO=json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
NO=json.loads((WS/"portfolio_out.json").read_text(encoding="utf-8"))
plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","SimSun"]
plt.rcParams["axes.unicode_minus"]=False; plt.rcParams["figure.dpi"]=130
NAVY,TEAL,GOLD,GREY,RED="#1f3a5f","#1f9e8f","#d4a017","#8a8f98","#c0392b"
paths={}

def load(tag,comp):
    f=WS/f"portfolio_{'compound_' if comp else ''}equity_{tag}.csv"
    x=pd.read_csv(f,encoding="utf-8-sig"); x["dt"]=pd.to_datetime(x.trade_date); return x

data={}
for tag,g in [("c7","C7单池"),("dual","C6+C7双池")]:
    data[tag]=dict(comp=load(tag,True),no=load(tag,False),g=g)

# 图1：复利账户曲线（两条）+分界
fig,ax=plt.subplots(figsize=(11,5))
for tag,col in [("c7",NAVY),("dual",TEAL)]:
    d=data[tag]; pf=CO["pools"][d["g"]]["portfolio"]
    ax.plot(d["comp"].dt,d["comp"].equity,color=col,lw=1.7,
            label=f"{d['g']} 复利 终值{pf['final']:,.0f} (+{pf['cum_return_pct']:.0f}%)")
ax.axhline(20000,color=GREY,ls=":",lw=1)
cut=data["c7"]["comp"].dt[data["c7"]["comp"].split=="train"].max()
ax.axvline(cut,color=GOLD,ls="--",lw=1.5)
ax.text(cut,ax.get_ylim()[1]*0.95," 样本内/外分界\n 2025-12-31→01-05",color=GOLD,fontsize=9,va="top")
ax.set_yscale("log"); ax.set_ylabel("账户资产（元，对数轴）")
ax.set_title("复利账户净值曲线（初始20000 · 每笔=信号日净值×20% · 最多5只 · 盈利再投入）",fontsize=11)
ax.legend(loc="upper left",fontsize=9); ax.grid(alpha=.25)
fig.tight_layout();p=WS/"chart_compound_equity.png";fig.savefig(p);plt.close(fig);paths["ce1"]=str(p)

# 图2：复利 vs 不复利对照（每池两条）
fig,axes=plt.subplots(1,2,figsize=(12,4.4))
for ax,(tag,col) in zip(axes,[("c7",NAVY),("dual",TEAL)]):
    d=data[tag]
    ax.plot(d["comp"].dt,d["comp"].equity,color=col,lw=1.7,label=f"复利 终值{CO['pools'][d['g']]['portfolio']['final']:,.0f}")
    ax.plot(d["no"].dt,d["no"].equity,color=GREY,lw=1.4,ls="--",label=f"不复利 终值{NO['pools'][d['g']]['portfolio']['final']:,.0f}")
    ax.axhline(20000,color=GREY,ls=":",lw=.8)
    ax.axvline(cut,color=GOLD,ls="--",lw=1)
    ax.set_title(d["g"]);ax.legend(fontsize=8);ax.grid(alpha=.25)
    ax.set_ylabel("账户资产（元）")
fig.suptitle("复利 vs 不复利（固定4000）——差异来源：盈利是否再投入",fontsize=11)
fig.tight_layout();p=WS/"chart_compound_vs_flat.png";fig.savefig(p);plt.close(fig);paths["ce2"]=str(p)

# 图3：每笔投入额随净值变化（证明复利定比机制）
fig,ax=plt.subplots(figsize=(11,3.8))
dual=data["dual"]; c=dual["comp"]
ax.plot(c.dt,c.equity,color=TEAL,lw=1.4,label="账户净值(右轴)" if False else "账户净值")
ax2=ax.twinx()
# 用投入额：从明细重算不可得，这里用净值×20%示意单票上限轨迹
ax2.plot(c.dt,c.equity*0.2,color=RED,lw=1.2,ls="--",label="单票上限=净值×20%")
ax.set_ylabel("账户净值（元）",color=TEAL);ax2.set_ylabel("单票上限（元）",color=RED)
ax.axvline(cut,color=GOLD,ls="--",lw=1)
ax.set_title("复利机制：单票上限随净值按比例放大（双池）",fontsize=11)
ax.grid(alpha=.25)
h1,l1=ax.get_legend_handles_labels();h2,l2=ax2.get_legend_handles_labels()
ax.legend(h1+h2,l1+l2,loc="upper left",fontsize=9)
fig.tight_layout();p=WS/"chart_compound_alloc.png";fig.savefig(p);plt.close(fig);paths["ce3"]=str(p)

(WS/"compound_charts.json").write_text(json.dumps(paths,ensure_ascii=False,indent=2),encoding="utf-8")
print("COMPOUND_CHARTS_OK",*paths.values(),sep="\n")

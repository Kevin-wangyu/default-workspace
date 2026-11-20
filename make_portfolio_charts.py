# -*- coding: utf-8 -*-
"""收益率板面 V2：起始20000、双曲线日期对齐、样本内外分界、口径说明。
数据全部来自 portfolio_equity_*.csv（组合层引擎输出），零估算。"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PO = json.loads((WS/"portfolio_out.json").read_text(encoding="utf-8"))
plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","SimSun"]
plt.rcParams["axes.unicode_minus"]=False
plt.rcParams["figure.dpi"]=130
NAVY,TEAL,GOLD,GREY="#1f3a5f","#1f9e8f","#d4a017","#8a8f98"
c7=pd.read_csv(WS/"portfolio_equity_c7.csv",encoding="utf-8-sig")
du=pd.read_csv(WS/"portfolio_equity_dual.csv",encoding="utf-8-sig")
# 按日期对齐
m=c7.merge(du,on="trade_date",suffixes=("_c7","_du"))
m["dt"]=pd.to_datetime(m.trade_date)
cut=m[m.split_c7=="train"].dt.max()
p_c7=PO["pools"]["C7单池"]["portfolio"]; p_du=PO["pools"]["C6+C7双池"]["portfolio"]
paths={}

# 图1：双资金曲线（起始20000）+ 分界线
fig,ax=plt.subplots(figsize=(11,5))
ax.plot(m.dt,m.equity_c7,color=NAVY,lw=1.6,label=f"C7单池 终值{p_c7['final']:.0f} (+{p_c7['cum_return_pct']:.1f}%)")
ax.plot(m.dt,m.equity_du,color=TEAL,lw=1.6,label=f"双池 终值{p_du['final']:.0f} (+{p_du['cum_return_pct']:.1f}%)")
ax.axhline(20000,color=GREY,ls=":",lw=1)
ax.axvline(cut,color=GOLD,ls="--",lw=1.5)
ax.text(cut,ax.get_ylim()[1]*0.96," 样本内/外分界\n 2025-12-31→01-05",color=GOLD,fontsize=9,va="top")
ax.fill_between(m.dt[m.dt<=cut],20000,m.equity_c7[m.dt<=cut],color=NAVY,alpha=.05)
ax.set_title("账户净值曲线（初始资金20000 · 每笔固定4000 · 最多5只 · 不复利线性累加 · 含浮动盈亏）",fontsize=11)
ax.set_ylabel("账户资产（元）");ax.legend(loc="upper left",fontsize=9);ax.grid(alpha=.25)
fig.tight_layout();p=WS/"chart_portfolio_equity.png";fig.savefig(p);plt.close(fig);paths["pe1"]=str(p)

# 图2：回撤曲线
fig,ax=plt.subplots(figsize=(11,3.6))
for col,color,name in [("equity_c7",NAVY,"C7单池"),("equity_du",TEAL,"双池")]:
    dd=(m[col]/m[col].cummax()-1)*100
    ax.fill_between(m.dt,dd,0,color=color,alpha=.25)
    ax.plot(m.dt,dd,color=color,lw=1,label=f"{name} 最大回撤{dd.min():.1f}%")
ax.axvline(cut,color=GOLD,ls="--",lw=1.2)
ax.set_title("账户回撤（相对历史峰值）");ax.set_ylabel("回撤 (%)")
ax.legend(loc="lower left",fontsize=9);ax.grid(alpha=.25)
fig.tight_layout();p=WS/"chart_portfolio_drawdown.png";fig.savefig(p);plt.close(fig);paths["pe2"]=str(p)

# 图3：组合层核心指标对比条形
fig,(a1,a2)=plt.subplots(1,2,figsize=(10,4))
metrics=[("cum_return_pct","累计收益 (%)",NAVY),("cagr_pct","等效年化 (%)",TEAL)]
for ax,(k,title,col) in zip([a1,a2],metrics):
    vals=[p_c7[k],p_du[k]]
    ax.bar(["C7单池","双池"],vals,color=[NAVY,TEAL])
    for i,v in enumerate(vals): ax.text(i,v+2,f"{v:.2f}%",ha="center",fontsize=10)
    ax.set_title(title);ax.grid(axis="y",alpha=.25)
fig.suptitle("组合层收益指标（线性累加口径，年化为等效换算值）",fontsize=11)
fig.tight_layout();p=WS/"chart_portfolio_metrics.png";fig.savefig(p);plt.close(fig);paths["pe3"]=str(p)

(WS/"portfolio_charts.json").write_text(json.dumps(paths,ensure_ascii=False,indent=2),encoding="utf-8")
print("PORTFOLIO_CHARTS_OK",*paths.values(),sep="\n")

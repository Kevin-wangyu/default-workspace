# -*- coding: utf-8 -*-
"""生成 C7 逐日/牛熊/两次对比图，并补齐第一次报告 R1 数字。纯读项目。"""
from __future__ import annotations
import json, base64, io
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"c7_daily_out.json").read_text(encoding="utf-8"))
RD=json.loads((WS/"report_data.json").read_text(encoding="utf-8"))
FA=json.loads((WS/"factor_attribution_out.json").read_text(encoding="utf-8"))

# --- 补齐第一次报告 R1（从 report_data.json recommended 找 merge 最高）---
first=None
rec=RD.get("recommended",{})
for k,v in rec.items():
    if not isinstance(v,dict): continue
    t10=v.get("train",{}).get("10",{})
    o10=v.get("oos",{}).get("10",{}) if isinstance(v.get("oos"),dict) else {}
    m=t10.get("merge")
    if m is not None and (first is None or m>first["merge_train"]):
        first={"label":v.get("label",""),"rule":v.get("rule",""),"theory":v.get("theory",""),
               "merge_train":m,"pool_train":t10.get("pool_n"),
               "hit_days_train":t10.get("hit_days"),"daily75_train":t10.get("daily75"),
               "merge_oos":o10.get("merge"),"pool_oos":o10.get("pool_n")}
D["first_report_r1"]=first
(WS/"c7_daily_out.json").write_text(json.dumps(D,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print("FIRST_R1",json.dumps(first,ensure_ascii=False),flush=True)

# --- 绘图样式 ---
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei']
plt.rcParams['axes.unicode_minus']=False
BLUE,ORANGE,GREEN,RED,GRAY='#1e3a5f','#e8833a','#2e8b6f','#c0392b','#95a5a6'
plt.rcParams.update({'figure.facecolor':'white','axes.facecolor':'#fafbfc','axes.grid':True,
 'grid.alpha':.3,'axes.spines.top':False,'axes.spines.right':False})
def b64(fig):
    b=io.BytesIO(); fig.savefig(b,format='png',dpi=130,bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(b.getvalue()).decode()

daily=D["daily"]
dates=[date.fromisoformat(r["date"]) for r in daily]
hit=[r["hit10"]*100 for r in daily]
nsel=[r["n"] for r in daily]
reg=[r["regime"] for r in daily]
split=[r["split"] for r in daily]
CH={}

# 图1 C7 逐日命中率时间序列（牛熊底色 + train/oos 分界 + 分档参考线）
fig,ax=plt.subplots(figsize=(14,5.4))
cmap={'牛':'#eaf5ee','熊':'#fbeef0','震荡':'#f5f6f8'}
for i in range(len(dates)-1):
    ax.axvspan(dates[i],dates[i+1],color=cmap[reg[i]],alpha=.55,lw=0)
ax.plot(dates,hit,lw=.8,color=BLUE,alpha=.8)
ax.axhline(75,color=RED,ls='--',lw=1.2,label='75% 目标线')
ax.axhline(50,color=ORANGE,ls=':',lw=1.1,label='50%')
ax.axhline(25,color=GRAY,ls=':',lw=1.1,label='25%')
# train/oos 分界
try:
    bi=split.index('oos'); ax.axvline(dates[bi],color='#333',lw=1.4,ls='-')
    ax.text(dates[bi],78,' ← 样本外 ',fontsize=9,color='#333')
except ValueError: pass
ax.set_ylabel('当日选中股的 hit10 (%)'); ax.set_ylim(0,105)
ax.set_title('图8  C7 最佳条件逐日命中率（580个交易日；底色：牛/熊/震荡）',fontsize=12,fontweight='bold')
ax.legend(loc='upper right',fontsize=9)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
plt.setp(ax.get_xticklabels(),rotation=30,ha='right',fontsize=8)
CH['c8']=b64(fig)

# 图2 月度平均命中率 + 选中数
mon=D["monthly"]
fig,ax=plt.subplots(figsize=(13,5))
xs=np.arange(len(mon))
mh=[r['hit10']*100 for r in mon]; mn=[r['n'] for r in mon]
bars=ax.bar(xs,mh,color=[BLUE if r['ym']<'2026-01' else ORANGE for r in mon],alpha=.9)
ax.axhline(35,color=GREEN,ls='--',lw=1.2,label='全期均值约34%')
ax2=ax.twinx(); ax2.plot(xs,mn,color=RED,marker='.',lw=1.2,alpha=.7,label='当月选中数(右轴)')
ax2.set_ylabel('选中股票数',color=RED); ax2.grid(False)
ax.set_xticks(xs); ax.set_xticklabels([r['ym'] for r in mon],rotation=60,ha='right',fontsize=7.5)
ax.set_ylabel('月度平均 hit10 (%)'); ax.set_ylim(0,60)
ax.set_title('图9  C7 月度表现：命中率与选中数量（蓝=训练期 橙=样本外）',fontsize=12,fontweight='bold')
ax.legend(loc='upper left',fontsize=9)
CH['c9']=b64(fig)

# 图3 牛熊震荡分组（合并命中率 + 逐日均值 + 达标天数）
br=D["by_regime"]
fig,axes=plt.subplots(1,2,figsize=(12,5))
order=['牛','震荡','熊']
colors={'牛':GREEN,'震荡':GRAY,'熊':RED}
pooled=[br[r]['pooled_hit10']*100 for r in order]
mean=[br[r]['mean_daily_hit10']*100 for r in order]
x=np.arange(3); w=.36
axes[0].bar(x-w/2,pooled,w,color=[colors[r] for r in order],alpha=.9,label='合并池命中率')
axes[0].bar(x+w/2,mean,w,color=[colors[r] for r in order],alpha=.5,label='逐日均值')
for i,(a,b) in enumerate(zip(pooled,mean)):
    axes[0].text(i-w/2,a+1,f'{a:.1f}',ha='center',fontsize=9)
axes[0].set_xticks(x); axes[0].set_xticklabels(order,fontsize=11)
axes[0].set_ylabel('hit10 (%)'); axes[0].set_ylim(0,45); axes[0].legend(fontsize=8)
axes[0].set_title('命中率：牛 / 震荡 / 熊',fontsize=11,fontweight='bold')
ge75=[br[r]['days_ge75'] for r in order]; total=[br[r]['days'] for r in order]
rate75=[a/b*100 for a,b in zip(ge75,total)]
axes[1].bar(x,rate75,color=[colors[r] for r in order],alpha=.9)
for i,(a,b,r) in enumerate(zip(ge75,total,rate75)):
    axes[1].text(i,r+.6,f'{a}/{b}天 ({r:.0f}%)',ha='center',fontsize=8.5)
axes[1].set_xticks(x); axes[1].set_xticklabels(order,fontsize=11)
axes[1].set_ylabel('逐日hit10≥75% 的天数占比 (%)'); axes[1].set_ylim(0,30)
axes[1].set_title('达标日(≥75%)分布',fontsize=11,fontweight='bold')
fig.suptitle('图10  C7 在牛市/熊市/震荡市的表现对比',fontsize=12,fontweight='bold',y=1.02)
CH['c10']=b64(fig)

# 图4 两次研究同口径对比
fig,ax=plt.subplots(figsize=(9.5,5.2))
cats=['训练期 hit10','样本外 hit10']
base_tr=FA['splits']['train']['factors']  # not needed
rd_base_tr=0.1150; rd_base_oo=0.0876  # 全市场基准（统一口径）
first_tr=first['merge_train'] if first else 0
first_oo=(first.get('merge_oos') or 0)
c7_tr=D['this_report_c7']['merge_train']; c7_oo=D['this_report_c7']['merge_oos']
x=np.arange(2); w=.25
ax.bar(x-w,[rd_base_tr*100,rd_base_oo*100],w,label='全市场基准',color=GRAY)
ax.bar(x,[first_tr*100,first_oo*100],w,label='第一次研究 R1（窄规则冲比例）',color=ORANGE)
ax.bar(x+w,[c7_tr*100,c7_oo*100],w,label='本次研究 C7（稳健可用组合）',color=BLUE)
for i,(a,b,c) in enumerate(zip([rd_base_tr*100,rd_base_oo*100],[first_tr*100,first_oo*100],[c7_tr*100,c7_oo*100])):
    ax.text(i-w,a+1,f'{a:.1f}',ha='center',fontsize=8,color='#555')
    ax.text(i,b+1,f'{b:.1f}',ha='center',fontsize=8,color=ORANGE)
    ax.text(i+w,c+1,f'{c:.1f}',ha='center',fontsize=8,color=BLUE)
ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=11)
ax.set_ylabel('hit10 (%)'); ax.set_ylim(0,50)
ax.set_title('图11  两次研究同口径对比：数字接近，但目标与稳定性不同',fontsize=12,fontweight='bold')
ax.legend(fontsize=9)
CH['c11']=b64(fig)

(WS/"c7_charts.json").write_text(json.dumps(CH,ensure_ascii=False),encoding="utf-8")
for n,s in CH.items():
    (WS/f"chart_{n}.png").write_bytes(base64.b64decode(s))
    print("CHART",n,len(s))
print("DONE")

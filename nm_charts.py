# -*- coding: utf-8 -*-
"""n×m 研究图表：命中热力图/边际递减/性价比/捕获率。matplotlib base64 内嵌。"""
from __future__ import annotations
import json, base64, io
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"nm_analysis_out.json").read_text(encoding="utf-8"))
E=json.loads((WS/"nm_enrich_out.json").read_text(encoding="utf-8"))
res=D['grid']; NS=D['config']['NS']; MS=D['config']['MS']
eff={(e['split'],e['n'],e['m']):e for e in E['eff']}

plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei']
plt.rcParams['axes.unicode_minus']=False
BLUE,ORANGE,GREEN,RED='#1e3a5f','#e8833a','#2e8b6f','#c0392b'
plt.rcParams.update({'figure.facecolor':'white','axes.facecolor':'#fafbfc',
  'axes.grid':True,'grid.alpha':.3,'axes.spines.top':False,'axes.spines.right':False})
def b64(fig):
    b=io.BytesIO(); fig.savefig(b,format='png',dpi=130,bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(b.getvalue()).decode()
def heat(ax,M,xl,yl,title,fmt='.0f',cmap='YlGnBu',vmin=None,vmax=None):
    im=ax.imshow(M,aspect='auto',cmap=cmap,vmin=vmin,vmax=vmax)
    ax.set_xticks(range(len(xl))); ax.set_xticklabels(xl)
    ax.set_yticks(range(len(yl))); ax.set_yticklabels(yl)
    ax.set_xlabel('持有期 n（交易日）'); ax.set_ylabel('涨幅目标 m（%）')
    ax.set_title(title,fontsize=11,fontweight='bold',color=BLUE)
    for i in range(len(yl)):
        for j in range(len(xl)):
            v=M[i,j]
            if not np.isnan(v):
                ax.text(j,i,format(v,fmt),ha='center',va='center',fontsize=8,
                        color='white' if v>(np.nanmax(M)*.62 if np.nanmax(M)>0 else 0) else '#222')
    return im

C={}
# ---- 图1 命中率热力图 train+oos ----
fig,axs=plt.subplots(1,2,figsize=(14,5.4))
for ax,sp in zip(axs,['train','oos']):
    M=np.array([[res[f"{sp}|{n}|{m}"]['c7_hit_rate']*100 for n in NS] for m in MS])
    im=heat(ax,M,NS,MS,f'图1  C7命中率 hit(n,m) — {"训练期" if sp=="train" else "样本外"}',cmap='YlGnBu',vmin=0,vmax=75)
fig.colorbar(im,ax=axs,shrink=.8,label='命中率 %')
fig.suptitle('命中率随 n 单调上升、随 m 单调下降（m=20 为前序口径）',fontsize=12,fontweight='bold')
C['n1']=b64(fig)

# ---- 图2 命中率随 n 曲线（边际递减）----
fig,ax=plt.subplots(figsize=(10,5.4))
for m,col in [(10,GREEN),(20,BLUE),(30,RED)]:
    for sp,ls in [('train','-'),('oos','--')]:
        ys=[res[f"{sp}|{n}|{m}"]['c7_hit_rate']*100 for n in NS]
        ax.plot(NS,ys,ls,color=col,lw=2.2,marker='o',ms=5,
                label=f'm={m}% '+('训练期' if sp=='train' else '样本外'))
ax.axvline(10,color='#888',ls=':',lw=1.5)
ax.text(10.2,5,'当前 n=10',fontsize=9,color='#666')
ax.set_xlabel('持有期 n（交易日）'); ax.set_ylabel('C7 命中率 %')
ax.set_title('图2  命中率随持有期上升但边际递减（n>10 趋缓）',fontsize=12,fontweight='bold')
ax.legend(fontsize=9,ncol=3,loc='lower right')
C['n2']=b64(fig)

# ---- 图3 性价比：gain/day ----
fig,axs=plt.subplots(1,2,figsize=(14,5.2))
# (a) n=10 各 m
x=np.arange(len(MS)); w=.38
tr=[eff[('train',10,m)]['gain_day'] for m in MS]
oo=[eff[('oos',10,m)]['gain_day'] for m in MS]
axs[0].bar(x-w/2,tr,w,label='训练期',color=BLUE); axs[0].bar(x+w/2,oo,w,label='样本外',color=ORANGE)
axs[0].set_xticks(x); axs[0].set_xticklabels([f'{m}%' for m in MS])
axs[0].set_xlabel('涨幅目标 m'); axs[0].set_ylabel('理想化每持仓日收益 %')
axs[0].set_title('图3a  n=10 固定时：m 的最优在 15~20%',fontsize=11,fontweight='bold',color=BLUE)
axs[0].legend(fontsize=9)
# (b) m=20 各 n
x2=np.arange(len(NS))
tr2=[eff[('train',n,20)]['gain_day'] for n in NS]
oo2=[eff[('oos',n,20)]['gain_day'] for n in NS]
axs[1].bar(x2-w/2,tr2,w,label='训练期',color=BLUE); axs[1].bar(x2+w/2,oo2,w,label='样本外',color=ORANGE)
axs[1].set_xticks(x2); axs[1].set_xticklabels([f'{n}' for n in NS])
axs[1].set_xlabel('持有期 n（交易日）'); axs[1].set_ylabel('理想化每持仓日收益 %')
axs[1].set_title('图3b  m=20 固定时：n 越短效率越高（但命中率越低）',fontsize=11,fontweight='bold',color=BLUE)
axs[1].legend(fontsize=9)
C['n3']=b64(fig)

# ---- 图4 捕获率热力图 train+oos ----
fig,axs=plt.subplots(1,2,figsize=(14,5.4))
for ax,sp in zip(axs,['train','oos']):
    M=np.array([[res[f"{sp}|{n}|{m}"]['capture']*100 for n in NS] for m in MS])
    im=heat(ax,M,NS,MS,f'图4  捕获率 capture(n,m) — {"训练期" if sp=="train" else "样本外"}',
            fmt='.2f',cmap='Oranges',vmin=0)
fig.colorbar(im,ax=axs,shrink=.8,label='捕获率 %')
fig.suptitle('C7命中数 ÷ 全市场命中数：随 n 增大而下降（全市场基数暴涨）',fontsize=12,fontweight='bold')
C['n4']=b64(fig)

# ---- 图5 捕获率 + 放大倍数随 n（m=20）----
fig,ax1=plt.subplots(figsize=(10,5.4))
for sp,col in [('train',BLUE),('oos',ORANGE)]:
    cap=[res[f"{sp}|{n}|20"]['capture']*100 for n in NS]
    ax1.plot(NS,cap,'-o',color=col,lw=2.3,ms=6,label=f'捕获率 {"训练" if sp=="train" else "样本外"}')
ax1.set_xlabel('持有期 n（交易日）'); ax1.set_ylabel('捕获率 %',color=BLUE)
ax2=ax1.twinx(); ax2.grid(False)
for sp,col,ls in [('train',GREEN,'-'),('oos',RED,'--')]:
    amp=[res[f"{sp}|{n}|20"]['amplification'] for n in NS]
    ax2.plot(NS,amp,ls+'s',color=col,lw=2,ms=5,label=f'放大倍数 {"训练" if sp=="train" else "样本外"}')
ax2.set_ylabel('相对放大倍数（捕获率÷C7占比）',color=GREEN)
ax1.set_title('图5  广泛性：捕获率随 n 下降，但放大倍数始终 >1',fontsize=12,fontweight='bold')
h1,l1=ax1.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
ax1.legend(h1+h2,l1+l2,fontsize=9,loc='upper right')
C['n5']=b64(fig)

# ---- 图6 收益-效率权衡散点（气泡=m）----
fig,ax=plt.subplots(figsize=(10,6))
for sp,marker,col in [('train','o',BLUE),('oos','s',ORANGE)]:
    for m in MS:
        pts=[eff[(sp,n,m)] for n in NS]
        xs=[p['hit']*100 for p in pts]; ys=[p['gain_day'] for p in pts]
        sz=[40+ m*3 for _ in pts]
        ax.scatter(xs,ys,s=sz,marker=marker,color=col,alpha=.45,edgecolors='white',lw=.6)
# 高亮推荐点
for (sp,n,m),lab in [(('train',10,20),'推荐 n10/m20'),(('oos',10,20),'')]:
    p=eff[(sp,n,m)]
    ax.scatter([p['hit']*100],[p['gain_day']],s=260,marker='*',color=RED,zorder=5,edgecolors='k',lw=.5)
ax.set_xlabel('C7 命中率 %'); ax.set_ylabel('理想化每持仓日收益 %')
ax.set_title('图6  收益—效率权衡（气泡大小=涨幅目标 m，红星=推荐 n10/m20）',fontsize=12,fontweight='bold')
C['n6']=b64(fig)

(WS/"nm_charts.json").write_text(json.dumps(C,ensure_ascii=False),encoding="utf-8")
for t in ['n1','n2','n3','n4','n5','n6']:
    (WS/f"chart_{t}.png").write_bytes(base64.b64decode(C[t]))
print("CHARTS",len(C),flush=True)
print("DONE",flush=True)

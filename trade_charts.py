# -*- coding: utf-8 -*-
"""操盘策略报告图表：5张，base64内嵌。中文字体 Microsoft YaHei。"""
from __future__ import annotations
import json, io, base64
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei'];plt.rcParams['axes.unicode_minus']=False
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
TP=pd.read_parquet(WS/'trade_path.parquet')
CH={}
def save(fig,name):
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=130,bbox_inches='tight',facecolor='white')
    plt.close(fig);CH[name]=base64.b64encode(buf.getvalue()).decode();(WS/f'chart_{name}.png').write_bytes(buf.getvalue())

C_BLUE='#2E86AB';C_ORANGE='#E67E22';C_GREEN='#27ae60';C_RED='#c0392b';C_GREY='#95a5a6'

# T1 买入时机命中率
fig,ax=plt.subplots(figsize=(10,5.4))
labels=['研究口径\n(T收盘起算)','T+1开盘\n(真实可成交)','T+1收盘','T+2开盘']
tr=[35.05,28.44,26.96,26.23];oo=[32.99,27.15,25.59,25.77]
x=np.arange(len(labels));w=0.36
b1=ax.bar(x-w/2,tr,w,label='train(2024-03~2025-12)',color=C_BLUE)
b2=ax.bar(x+w/2,oo,w,label='oos(2026-01~10)',color=C_ORANGE)
for b,v in zip(b1,tr):ax.text(b.get_x()+b.get_width()/2,v+0.6,f'{v}%',ha='center',fontsize=10)
for b,v in zip(b2,oo):ax.text(b.get_x()+b.get_width()/2,v+0.6,f'{v}%',ha='center',fontsize=10)
ax.axhline(20,ls='--',color=C_GREY,lw=1);ax.text(3.4,20.5,'m=20目标线',color=C_GREY,fontsize=9)
ax.set_ylabel('10日内最高涨幅≥20% 的命中率');ax.set_title('图1  买入时机决定命中率：研究口径 ≠ 可成交口径')
ax.set_xticks(x);ax.set_xticklabels(labels);ax.legend();ax.set_ylim(0,40);ax.grid(axis='y',alpha=.3)
save(fig,'t1')

# T2 跳空缺口分布
fig,ax=plt.subplots(figsize=(10,5))
for sp,col in [('train',C_BLUE),('oos',C_ORANGE)]:
    g=TP[TP.split==sp].gap_t1.replace([np.inf,-np.inf],np.nan).dropna()
    ax.hist(g,bins=np.arange(-12,16,0.5),histtype='step',lw=2,color=col,label=f'{sp} (均值{g.mean():.1f}%, >5%占{(g>5).mean()*100:.0f}%)',density=True)
ax.axvline(0,color='k',lw=1);ax.set_xlabel('T+1开盘相对T收盘跳空幅度(%)');ax.set_ylabel('密度')
ax.set_title('图2  追高的代价：T+1普遍高开，26%的标的开盘已涨超5%');ax.legend();ax.grid(alpha=.3)
save(fig,'t2')

# T3 买入价 vs 期望收益 & 成交率
fig,ax=plt.subplots(figsize=(10,5.4))
entries=[2,0,-2,-3,-5]
avg_tr=[-0.737,-0.724,-0.253,-0.013,1.072];avg_oo=[-0.188,-0.165,-0.050,0.192,0.315]
fill_tr=[80.8,70.2,58.1,49.2,31.8];fill_oo=[83.4,74.0,58.6,47.8,29.3]
xs=np.arange(len(entries))
ax.plot(xs,avg_tr,'o-',color=C_BLUE,lw=2,label='期望收益 train(左轴)')
ax.plot(xs,avg_oo,'s-',color=C_ORANGE,lw=2,label='期望收益 oos(左轴)')
ax.axhline(0,color='k',lw=1)
ax2=ax.twinx();ax2.plot(xs,fill_tr,'^--',color=C_GREY,lw=1.5,label='成交率 train(右轴)');ax2.set_ylabel('成交率(%)',color=C_GREY);ax2.set_ylim(0,100)
ax.set_xticks(xs);ax.set_xticklabels([f'{e:+d}%' for e in entries]);ax.set_xlabel('T+1限价买入价（相对T收盘）')
ax.set_ylabel('单笔期望收益(%)');ax.set_title('图3  不追高才有正期望：回踩越深收益越高，但成交率下降')
ln1,lb1=ax.get_legend_handles_labels();ln2,lb2=ax2.get_legend_handles_labels();ax.legend(ln1+ln2,lb1+lb2,loc='upper left',fontsize=9)
ax.grid(alpha=.3);save(fig,'t3')

# T4 排序因子双期spread
fig,ax=plt.subplots(figsize=(10,5.4))
feats=['vol20','ret_5d','bias5','turnover_rate','lu_cnt_20d','main_net_norm','mkt_up_ratio']
trs=[19.2,16.1,20.2,6.7,18.8,-5.7,-9.0];oos=[10.5,13.6,5.4,6.6,0.4,-23.4,-2.0]
y=np.arange(len(feats));h=0.38
ax.barh(y+h/2,trs,h,color=C_BLUE,label='train')
ax.barh(y-h/2,oos,h,color=C_ORANGE,label='oos')
ax.axvline(0,color='k',lw=1);ax.set_yticks(y);ax.set_yticklabels(feats)
ax.set_xlabel('池内最高档 − 最低档 的命中率差(pct)');ax.set_title('图4  池内排序：只认双期同向的波动/动量/换手，资金力度反向')
ax.legend();ax.grid(axis='x',alpha=.3);save(fig,'t4')

# T5 闭环 + 收益路径
fig,axs=plt.subplots(1,2,figsize=(12,5))
# 左：持有收益路径
for sp,col in [('train',C_BLUE),('oos',C_ORANGE)]:
    s=TP[TP.split==sp]
    axs[0].bar([0],[s.mfe10_t1open.mean()],color=col,alpha=.5,label=f'{sp} MFE均')
axs[0].bar([1],[TP[TP.split=='train'].mae10.mean()],color=C_BLUE,alpha=.9)
axs[0].bar([1],[TP[TP.split=='oos'].mae10.mean()],color=C_ORANGE,alpha=.9)
axs[0].axhline(0,color='k',lw=1);axs[0].set_xticks([0,1]);axs[0].set_xticklabels(['10日最大浮盈MFE','10日最大回撤MAE'])
axs[0].set_ylabel('相对买入价(%)');axs[0].set_title('T+1开盘追高后的收益路径');axs[0].grid(axis='y',alpha=.3)
# 右：闭环期望
grp=['train','oos'];nob=[0.803,0.164];top=[0.85,0.117]
x=np.arange(2);w=0.36
axs[1].bar(x-w/2,nob,w,color=C_GREY,label='全买(无排序)');axs[1].bar(x+w/2,top,w,color=C_GREEN,label='池内top50%排序')
for b,v in zip(axs[1].patches,nob+top):axs[1].text(b.get_x()+b.get_width()/2,b.get_height()+0.02,f'{v:.2f}',ha='center',fontsize=9)
axs[1].set_xticks(x);axs[1].set_xticklabels(grp);axs[1].axhline(0,color='k',lw=1)
axs[1].set_ylabel('单笔期望收益(%)');axs[1].set_title('回踩-5%买入闭环：排序对收益无稳定增益');axs[1].legend();axs[1].grid(axis='y',alpha=.3)
fig.suptitle('图5  收益路径与闭环验证',fontsize=14);save(fig,'t5')

(WS/'trade_charts.json').write_text(json.dumps(CH,ensure_ascii=False),encoding='utf-8')
print("图表生成完成:",list(CH.keys()))

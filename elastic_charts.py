# -*- coding: utf-8 -*-
"""弹性(n,m)机制图表：4图，base64内嵌，中文字体。
图E1 基线与各方案达标日期数对比柱状
图E2 逐日 S分 vs m20命中率散点(色=市场档) + 分档线
图E3 m20 vs m15 命中率随日期的双线 + 达标率区间
图E4 三诊断证据(n维度/触发窗口/幸存者偏差)
"""
from __future__ import annotations
import json, base64, io
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
# 中文字体
for f in ['Microsoft YaHei','SimHei','SimSun']:
    if any(f.lower() in x.name.lower() for x in font_manager.fontManager.ttflist):
        plt.rcParams['font.sans-serif']=[f]; break
plt.rcParams['axes.unicode_minus']=False
FIN=json.loads((WS/'elastic_final_out.json').read_text(encoding='utf-8'))
RULE=json.loads((WS/'elastic_rule_out.json').read_text(encoding='utf-8'))
diag=json.loads((WS/'diag_elastic_signal_out.json').read_text(encoding='utf-8'))
daily=FIN['daily']
dd=pd.DataFrame(daily)
dd['date']=pd.to_datetime(dd['trade_date'])
plt.rcParams['figure.dpi']=110

def b64(fig):
    buf=io.BytesIO(); fig.savefig(buf,format='png',bbox_inches='tight',facecolor='white'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('ascii')

charts={}
# 图E1：达标日期数对比（全580日）
sp=FIN['splits']['all']
labels=['固定\nm=20','弹性\n(极弱→m15)','固定\nm=15']
ge=[sp['固定m20']['ge50'],sp['弹性']['ge50'],sp['固定m15']['ge50']]
zero=[sp['固定m20']['zero'],sp['弹性']['zero'],sp['固定m15']['zero']]
x=np.arange(len(labels)); w=0.36
fig,ax=plt.subplots(figsize=(8,4.6))
b1=ax.bar(x-w/2,ge,w,label='≥50%日期数',color='#2E86AB')
b2=ax.bar(x+w/2,zero,w,label='hit=0日期数',color='#E07B39')
for b,v in zip(b1,ge): ax.text(b.get_x()+b.get_width()/2,v+3,str(v),ha='center',fontsize=10,fontweight='bold')
for b,v in zip(b2,zero): ax.text(b.get_x()+b.get_width()/2,v+3,str(v),ha='center',fontsize=10,fontweight='bold')
ax.axhline(170,color='#888',ls='--',lw=1); ax.text(2.45,172,'基线170',color='#666',fontsize=9,ha='right')
ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel('日期数 (总580)')
ax.set_title('达标日期数对比：降m到15是唯一有效覆盖杠杆')
ax.legend(); ax.grid(axis='y',alpha=.3)
charts['E1']=b64(fig)

# 图E2：S分 vs m20命中率散点
fig,ax=plt.subplots(figsize=(9,4.8))
cmap={'强':'#C0392B','中':'#E67E22','弱':'#2980B9'}
# 档位从 RULE 映射，S/命中率用 FIN（避免 merge 列冲突）
dang=pd.DataFrame(RULE['daily'])[['trade_date','档']].drop_duplicates()
m=dd.merge(dang,on='trade_date',how='inner')
for g,c in cmap.items():
    s=m[m['档']==g]
    ax.scatter(s['S'],s['r_h10_20'],s=14,alpha=.5,color=c,label=f'{g}档 n={len(s)}')
ax.axvline(RULE['config']['q67'],color='#C0392B',ls=':',lw=1)
ax.axvline(RULE['config']['q33'],color='#2980B9',ls=':',lw=1)
ax.axhline(0.5,color='#333',ls='--',lw=1,label='50%达标线')
ax.set_xlabel('当日市场综合分 S（越大越强）'); ax.set_ylabel('C7池 m=20 命中率')
ax.set_title('市场强弱与m20命中率：相关弱、无清晰分界 → 分档难有效')
ax.legend(fontsize=8); ax.grid(alpha=.25)
charts['E2']=b64(fig)

# 图E3：逐日 m20 vs m15 命中率双线（60日滚动均值）
s=dd.sort_values('date').copy()
s['ma20']=s['r_h10_20'].rolling(30,min_periods=10).mean()
s['ma15']=s['r_h10_15'].rolling(30,min_periods=10).mean()
fig,ax=plt.subplots(figsize=(10,4.6))
ax.plot(s['date'],s['ma20'],lw=1.4,color='#2E86AB',label='m=20 命中率(30日均)')
ax.plot(s['date'],s['ma15'],lw=1.4,color='#E07B39',label='m=15 命中率(30日均)')
ax.fill_between(s['date'],s['ma20'],s['ma15'],color='#F5B041',alpha=.25,label='降m收益差')
ax.axhline(.5,color='#333',ls='--',lw=1)
ax.axvline(pd.Timestamp('2026-01-01'),color='#999',ls=':',lw=1.2)
ax.text(pd.Timestamp('2026-01-05'),.92,'oos起点',fontsize=9,color='#666')
ax.set_ylabel('命中率'); ax.set_title('m=15恒定高于m=20：差距稳定，与市场状态无关')
ax.legend(loc='lower right',fontsize=9); ax.grid(alpha=.25)
charts['E3']=b64(fig)

# 图E4：三诊断证据
fig,axs=plt.subplots(1,3,figsize=(11,3.8))
# n维度
nd=diag['n_dim']; gs=['强','中','弱']
axs[0].bar([0,1,2],[nd[g]['n10'] for g in gs],.35,label='n=10',color='#2E86AB')
axs[0].bar([0,1,2+0],[nd[g]['n7'] for g in gs],.35,label='n=7',color='#BDC3C7')
axs[0].set_xticks(range(3)); axs[0].set_xticklabels(gs); axs[0].set_title('诊断1: n10全档优于n7'); axs[0].legend(fontsize=8); axs[0].grid(axis='y',alpha=.3)
# 触发窗口
for i,spn in enumerate(['train','oos']):
    pass
wrows=diag['window']
trn=[r for r in wrows if r['split']=='train']; oos=[r for r in wrows if r['split']=='oos']
axs[1].bar([0,1],[np.mean([r['r_today'] for r in trn]),np.mean([r['r_any3'] for r in trn])],.4,label='train',color='#2E86AB')
axs[1].bar([0,1],[np.mean([r['r_today'] for r in oos]),np.mean([r['r_any3'] for r in oos])],.4,label='oos',color='#E07B39')
axs[1].set_xticks([0,1]); axs[1].set_xticklabels(['T日','T-1/T-2归集']); axs[1].set_title('诊断2: 放宽窗口反降命中'); axs[1].legend(fontsize=8); axs[1].grid(axis='y',alpha=.3)
# 极弱市降m收益
wm=FIN['m15_days']
axs[2].bar([0,1],[wm['m20_hit'],wm['m15_hit']],.5,color=['#2E86AB','#E07B39'])
axs[2].set_xticks([0,1]); axs[2].set_xticklabels(['m=20','m=15']); axs[2].set_title('诊断3: 仅极弱市降m有效(+11pct)'); axs[2].grid(axis='y',alpha=.3)
fig.suptitle('机制诊断：为何弹性空间有限',fontsize=12,fontweight='bold')
fig.tight_layout()
charts['E4']=b64(fig)
(WS/'elastic_charts.json').write_text(json.dumps(charts,ensure_ascii=False),encoding='utf-8')
print("charts:",{k:len(v) for k,v in charts.items()})
print("DONE")

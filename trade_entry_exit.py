# -*- coding: utf-8 -*-
"""买入时机×止损止盈联合回测：追高(T+1开盘) vs 限价回踩买(挂单T收盘价±x%)。
限价单当日有效：若 T+1 最低<=挂单<=开盘 则以挂单价成交；若开盘<=挂单则以开盘成交；否则放弃(不成交)。
成交后从T+1起做止损止盈(保守:同日先止损)，持有期上限。双期验证。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_parquet(WS/'trade_path.parquet')
c0=df.c0.values; o1=df.o1.values; lo1=df.l1.values; hi1=df.h1.values
H=np.array([df[f'h{k}'].values for k in range(1,11)])
L=np.array([df[f'l{k}'].values for k in range(1,11)])
C=np.array([df[f'c{k}'].values for k in range(1,11)])
N=len(df)
SPL=df.split.values

def entry_price(limit_pct):
    """返回(成交价,是否成交)。limit_pct相对T收盘:0=平价,+2=追高2%,-3=回踩3%"""
    px=c0*(1+limit_pct/100)
    filled = (lo1<=px)  # T+1最低触及挂单价(含开盘已低于挂单)
    fill_px=np.where(o1<=px, o1, px)  # 开盘更划算则按开盘成交
    return fill_px, filled

def run(entry_pct,tp,sl,hold):
    bpx,filled=entry_price(entry_pct)
    tp_px=bpx*(1+tp/100); sl_px=bpx*(1+sl/100)
    ret=np.full(N,np.nan); reason=np.empty(N,dtype='U4')
    mfe=np.full(N,np.nan)
    for i in range(N):
        if not filled[i]: continue
        for d in range(hold):
            if L[d,i]<=sl_px[i]:
                ret[i]=sl;reason[i]='SL';break
            if H[d,i]>=tp_px[i]:
                ret[i]=tp;reason[i]='TP';break
        if np.isnan(ret[i]):
            ret[i]=(C[hold-1,i]/bpx[i]-1)*100;reason[i]='TIME'
        mfe[i]=(np.max(H[:hold,i])/bpx[i]-1)*100
    return ret,reason,filled,mfe

rows=[]
# 买入时机: 追高+2 / 平价0 / 回踩-2,-3,-5
# 止损止盈: tp 15/20, sl -5/-8, hold 7/10
for entry in [2,0,-2,-3,-5]:
    for tp in [15,20]:
        for sl in [-5,-8]:
            for hold in [7,10]:
                ret,reason,filled,mfe=run(entry,tp,sl,hold)
                rec=dict(entry=entry,tp=tp,sl=sl,hold=hold)
                for sp in ['train','oos']:
                    m=(SPL==sp)&filled
                    rs=ret[m]; rr=reason[m]
                    rec[f'{sp}_fill']=round(float(filled[SPL==sp].mean())*100,1)
                    rec[f'{sp}_win']=round(float((rs>0).mean())*100,2)
                    rec[f'{sp}_avg']=round(float(rs.mean()),3)
                    rec[f'{sp}_mfe20']=round(float((mfe[m]>=20).mean())*100,2)
                    gp=float(rs[rs>0].sum()); gl=float(abs(rs[rs<0].sum()))
                    rec[f'{sp}_pf']=round(gp/gl if gl>0 else 99,3)
                rows.append(rec)
g=pd.DataFrame(rows)
g.to_csv(WS/'entry_exit_grid.csv',index=False,encoding='utf-8-sig')
g['min_avg']=g[['train_avg','oos_avg']].min(axis=1)
print("=== 期望收益 TOP20 (要求 train&oos 均>0, 按min排序) ===")
pos=g[(g.train_avg>0)&(g.oos_avg>0)].sort_values('min_avg',ascending=False)
cols=['entry','tp','sl','hold','train_fill','train_avg','train_win','train_mfe20','train_pf','oos_fill','oos_avg','oos_win','oos_mfe20','oos_pf']
print(pos[cols].head(20).to_string(index=False) if len(pos) else "无正期望组合")
print(f"\n正期望组合数: {len(pos)}/{len(g)}")
print("\n=== 买入时机主效应 (tp15/sl-8/hold7, 各entry) ===")
print(g[(g.tp==15)&(g.sl==-8)&(g.hold==7)][['entry','train_fill','train_avg','train_mfe20','oos_fill','oos_avg','oos_mfe20']].to_string(index=False))
print("\n=== 追高vs回踩 命中率对比(tp/sl不影响mfe20, 看entry主效应) ===")
for e in [2,0,-2,-3,-5]:
    s=g[(g.entry==e)&(g.tp==15)&(g.sl==-8)&(g.hold==7)].iloc[0]
    print(f" entry={e:+d}%: 成交率 train={s.train_fill}% oos={s.oos_fill}% | MFE≥20 train={s.train_mfe20}% oos={s.oos_mfe20}% | 期望 train={s.train_avg}% oos={s.oos_avg}%")
(WS/'entry_exit_out.json').write_text(json.dumps(dict(
    positive=int(len(pos)),total=len(g),
    top=pos.head(20).to_dict('records') if len(pos) else [],
    entry_effect=g[(g.tp==15)&(g.sl==-8)&(g.hold==7)].to_dict('records')),ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE")

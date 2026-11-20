# -*- coding: utf-8 -*-
"""止损止盈回测：T+1开盘买入，盘中触发止盈/止损（保守：同日先止损），持有期上限强制平仓。
只用买入后前向OHLC路径（持仓管理，非选股前视）。参数网格 + train/oos 双期。
"""
from __future__ import annotations
import json, itertools
from pathlib import Path
import numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_parquet(WS/'trade_path.parquet')
# 买入价=T+1开盘；前向路径 O/H/L/C 1..10
buy=df.o1.values
H=np.array([df[f'h{k}'].values for k in range(1,11)])   # 10 x N
L=np.array([df[f'l{k}'].values for k in range(1,11)])
C=np.array([df[f'c{k}'].values for k in range(1,11)])
N=len(df)

def simulate(tp,sl,hold):
    """tp止盈%(>0), sl止损%(<0), hold持有天数(<=10)。返回每笔收益率%。"""
    ret=np.empty(N); exit_reason=np.empty(N,dtype='U4')
    tp_px=buy*(1+tp/100); sl_px=buy*(1+sl/100)
    for i in range(N):
        done=False
        for d in range(hold):
            hi=H[d,i]; lo=L[d,i]
            # 保守：同日既触止盈又触止损，按止损先成交
            if lo<=sl_px[i]:
                ret[i]=sl; exit_reason[i]='SL'; done=True; break
            if hi>=tp_px[i]:
                ret[i]=tp; exit_reason[i]='TP'; done=True; break
        if not done:
            ret[i]=(C[hold-1,i]/buy[i]-1)*100; exit_reason[i]='TIME'
    return ret,exit_reason

grid=[]
for tp in [15,20,25]:
    for sl in [-5,-8,-10,-12,-15]:
        for hold in [5,7,10]:
            r,er=simulate(tp,sl,hold)
            rec=dict(tp=tp,sl=sl,hold=hold)
            for sp in ['train','oos']:
                m=(df.split==sp).values
                rs=r[m]
                rec[f'{sp}_win']=round(float((rs>0).mean())*100,2)
                rec[f'{sp}_avg']=round(float(rs.mean()),3)
                rec[f'{sp}_tp']=round(float((er[m]=='TP').mean())*100,1)
                rec[f'{sp}_sl']=round(float((er[m]=='SL').mean())*100,1)
                rec[f'{sp}_time']=round(float((er[m]=='TIME').mean())*100,1)
                # 期望：正收益均值*胜率 + 负收益均值*(1-胜率)
                rec[f'{sp}_profit_factor']=round(float(rs[rs>0].sum()/abs(rs[rs<0].sum())) if (rs<0).any() else 99,3)
            # 组合目标：train/oos 期望收益都为正且接近
            grid.append(rec)
g=pd.DataFrame(grid)
(WS/'exit_grid.csv').to_csv if False else None
g.to_csv(WS/'exit_grid.csv',index=False,encoding='utf-8-sig')
# 按 train/oos 平均收益排名（要求两者都为正）
g['minavg']=g[['train_avg','oos_avg']].min(axis=1)
g['consistency']=-(g['train_avg']-g['oos_avg']).abs()
print("=== 期望收益为正的参数（按 min(train,oos) 平均收益排序）TOP15 ===")
pos=g[(g.train_avg>0)&(g.oos_avg>0)].sort_values('minavg',ascending=False)
print(pos[['tp','sl','hold','train_win','train_avg','oos_win','oos_avg','train_tp','oos_tp','train_profit_factor','oos_profit_factor']].head(15).to_string(index=False))
print("\n=== 全部为正的参数个数 ===",len(pos),"/",len(g))
print("\n=== 止损敏感度（hold=7, 各tp） ===")
for tp in [15,20,25]:
    s=g[(g.tp==tp)&(g.hold==7)][['sl','train_avg','oos_avg','train_win','oos_win','train_sl']]
    print(f" tp={tp}:\n{s.to_string(index=False)}")
print("\n=== 持有期敏感度（tp=20,sl=-10） ===")
print(g[(g.tp==20)&(g.sl==-10)][['hold','train_avg','oos_avg','train_win','oos_win','train_time']].to_string(index=False))
# 保存最佳参数完整统计
best=pos.iloc[0].to_dict() if len(pos) else None
(WS/'exit_backtest_out.json').write_text(json.dumps(dict(best=best,n_grid=len(g),n_positive=len(pos),
    top=pos.head(15).to_dict('records')),ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE -> exit_backtest_out.json")

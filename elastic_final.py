# -*- coding: utf-8 -*-
"""弹性(n,m)机制最终版：市场状态→m 映射（守高收益为默认，仅极弱市降至m15）+ 验证 lift。
关键约束（防刷数）：
 - n 恒取10（n10在全部档位严格优于n7，非杠杆）
 - m 默认20；仅当"当日市场状态极弱"且历史证明此时m20命中显著崩塌时才降m15
 - 全期 lift 必须 >1 且相对全市场放大不劣化 → 证明是真选股能力，不是放宽定义
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_csv(WS/'elastic_daily.csv')
c7dates=set(d['date'] for d in json.loads((WS/'c7_daily_out.json').read_text(encoding='utf-8'))['daily'])
df=df[df.trade_date.isin(c7dates)].reset_index(drop=True)
FEATS=['mkt_amt_ratio','mkt_ret_5d','mkt_ret_20d','mkt_up_ratio','mkt_lu','eff_hit10_lag']
X=df[FEATS].copy()
for c in FEATS:
    lo,hi=X[c].quantile(0.01),X[c].quantile(0.99); X[c]=X[c].clip(lo,hi)
tr=(df.split=='train').values
w={c:np.corrcoef(X.loc[tr,c].astype(float),df.loc[tr,'r_h10_20'].astype(float))[0,1] for c in FEATS}
mu=X[tr].mean(); sd=X[tr].std().replace(0,1)
df['S']=(((X-mu)/sd)*pd.Series(w)).sum(axis=1).astype(float)
# 规则：S 低于 train 10分位 = 极弱市 -> m15；否则 m20（守收益）
s10=float(df.loc[tr,'S'].quantile(0.10))
df['m_pick']=np.where(df.S<s10,15,20)
df['r_pick']=np.where(df.m_pick==20,df.r_h10_20,df.r_h10_15)
df['lift_pick']=np.where(df.m_pick==20,df.lift_10_20,df.lift_10_15)

def stat(v):
    v=pd.Series(v).dropna().astype(float)
    return dict(days=len(v),ge50=int((v>=0.5).sum()),ge50_pct=round(float((v>=0.5).mean())*100,2),
                zero=int((v==0).sum()),zero_pct=round(float((v==0).mean())*100,2),
                mean=round(float(v.mean()),4))

out=dict(config=dict(s10=round(s10,4),weights={c:round(w[c],4) for c in FEATS},
                     rule="S<train10分位→m15;否则m20;n恒10",n_fixed=10,
                     note="极弱市占比约10%,守高收益为默认"),
         splits={},m15_days={})
for sp in ['train','oos','all']:
    s=df if sp=='all' else df[df.split==sp]
    out['splits'][sp]=dict(
        固定m20=stat(s.r_h10_20),固定m15=stat(s.r_h10_15),弹性=stat(s.r_pick),
        弹性m20占比=round(float((s.m_pick==20).mean())*100,2),
        弹性平均m=round(float(s.m_pick.mean()),2),
        弹性lift=round(float(s.lift_pick.replace([np.inf,-np.inf],np.nan).mean()),3),
        固定m20lift=round(float(s.lift_10_20.replace([np.inf,-np.inf],np.nan).mean()),3),
    )
    o=out['splits'][sp]
    print(f"=== {sp} n={len(s)} ===")
    print(" 固定m20:",o['固定m20'])
    print(" 固定m15:",o['固定m15'])
    print(" 弹性   :",o['弹性'])
    print(" 弹性m20占比:",o['弹性m20占比'],"平均m:",o['弹性平均m'],"lift 弹性/固定:",o['弹性lift'],"/",o['固定m20lift'])
# 极弱市(S<s10)里 m20 vs m15 的命中差：证明降m有据
weak=df[df.S<s10]
out['m15_days']=dict(n=len(weak),m20_hit=round(float(weak.r_h10_20.mean()),4),
                     m15_hit=round(float(weak.r_h10_15.mean()),4),
                     m20_ge50=round(float((weak.r_h10_20>=0.5).mean())*100,2),
                     m15_ge50=round(float((weak.r_h10_15>=0.5).mean())*100,2),
                     m20_zero=round(float((weak.r_h10_20==0).mean())*100,2),
                     m15_zero=round(float((weak.r_h10_15==0).mean())*100,2))
print("极弱市(S<s10):",out['m15_days'])
out['daily']=df[['trade_date','split','n_c7','S','m_pick','r_h10_20','r_h10_15','r_pick','lift_pick']].to_dict('records')
(WS/'elastic_final_out.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print("DONE -> elastic_final_out.json")

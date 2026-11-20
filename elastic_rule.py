# -*- coding: utf-8 -*-
"""弹性(n,m)机制核心：当日市场综合分分档 -> (n,m) 映射；train 定档、oos 回放验证。
零前视：决策只用当日 T 可知市场特征；未来命中仅用于训练监督与事后评估。
候选组合限制在用户最佳范围 n∈{7,10}, m∈{15,20}。
规则逻辑（收益-命中权衡，非刷数）：强市守高收益目标 m=20；中弱市降 m=15 保命中。
对照：固定(10,20)基线、固定(10,15)、理论上限、lift(相对全市场放大)。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_csv(WS/'elastic_daily.csv')
c7=json.loads((WS/'c7_daily_out.json').read_text(encoding='utf-8'))
c7dates=set(d['date'] for d in c7['daily'])
# 对齐报告 580 日口径
df=df[df.trade_date.isin(c7dates)].reset_index(drop=True)
print("对齐后日期:",len(df),"范围:",df.trade_date.min(),df.trade_date.max(),
      "split:",df.split.value_counts().to_dict())

COMBOS={'10_20':'r_h10_20','10_15':'r_h10_15','7_20':'r_h7_20','7_15':'r_h7_15'}
df['best_hit']=df[list(COMBOS.values())].max(axis=1)
df['any_ge50']=(df['best_hit']>=0.5).astype(int)

# ---- 当日市场综合分 S（train 相关加权，正/负保留）----
FEATS=['mkt_amt_ratio','mkt_ret_5d','mkt_ret_20d','mkt_up_ratio','mkt_lu','eff_hit10_lag']
X=df[FEATS].copy()
for c in FEATS:
    lo,hi=X[c].quantile(0.01),X[c].quantile(0.99); X[c]=X[c].clip(lo,hi)
tr=(df.split=='train').values
w={c:float(np.corrcoef(X.loc[tr,c].astype(float),df.loc[tr,'r_h10_20'].astype(float))[0,1]) for c in FEATS}
mu=X[tr].mean(); sd=X[tr].std().replace(0,1)
df['S']=(((X-mu)/sd)*pd.Series(w)).sum(axis=1).astype(float)
q33=float(df.loc[tr,'S'].quantile(1/3)); q67=float(df.loc[tr,'S'].quantile(2/3))
def fen(s):
    return '强' if s>=q67 else ('中' if s>=q33 else '弱')
df['档']=df['S'].apply(fen)
print("权重:",{c:round(w[c],3) for c in FEATS},"分档线:",round(q33,3),round(q67,3))

# ---- 映射规则：强市守 m20，中弱市降 m15；n 恒取10（数据证明 n 越大命中越高，不作放宽杠杆）----
MAP={'强':'10_20','中':'10_15','弱':'10_15'}
df['pick_col']=df['档'].map(lambda g: COMBOS[MAP[g]])
df['r_pick']=df.apply(lambda r: float(r[r['pick_col']]) if pd.notna(r[r['pick_col']]) else np.nan,axis=1)
df['pick_s']=df['档'].map(MAP).map(lambda k:int(k.split('_')[0]))
df['pick_m']=df['档'].map(MAP).map(lambda k:int(k.split('_')[1]))
# lift：所选组合当日相对全市场放大
df['lift_pick']=df.apply(lambda r: float(r['lift_'+MAP[r['档']]]) if pd.notna(r['lift_'+MAP[r['档']]]) else np.nan,axis=1)
# 固定(10,20) 的 lift 对照
df['lift_10_20']=df['lift_10_20'].astype(float)

def stat(v):
    v=pd.Series(v).dropna().astype(float)
    return dict(days=len(v),ge50=int((v>=0.5).sum()),ge50_pct=round(float((v>=0.5).mean())*100,2),
                ge75=int((v>=0.75).sum()),ge75_pct=round(float((v>=0.75).mean())*100,2),
                zero=int((v==0).sum()),zero_pct=round(float((v==0).mean())*100,2),
                mean=round(float(v.mean()),4),median=round(float(v.median()),4))

out=dict(config=dict(q33=round(q33,4),q67=round(q67,4),weights={c:round(w[c],4) for c in FEATS},
                     mapping=MAP,rationale="强市守m20高收益;中弱市降m15保命中;n恒10(单调,非放宽杠杆)",
                     align_days=len(df),c7_days=len(c7dates)),
         splits={},档举证={})
for sp in ['train','oos','all']:
    sub=df if sp=='all' else df[df.split==sp]
    S=dict(
        固定10_20=stat(sub['r_h10_20']),
        固定10_15=stat(sub['r_h10_15']),
        弹性规则=stat(sub['r_pick']),
        理论上限=stat(sub['best_hit']),
        any_ge50=dict(days=len(sub),cnt=int(sub.any_ge50.sum()),pct=round(float(sub.any_ge50.mean())*100,2)),
        档分布=sub['档'].value_counts().to_dict(),
        选目标m分布=sub['pick_m'].value_counts().to_dict(),
        弹性平均目标m=round(float(sub['pick_m'].mean()),2),
        弹性lift均值=round(float(sub['lift_pick'].replace([np.inf,-np.inf],np.nan).mean()),3),
        固定10_20_lift均值=round(float(sub['lift_10_20'].replace([np.inf,-np.inf],np.nan).mean()),3),
        选股数=dict(min=int(sub.n_c7.min()),med=float(sub.n_c7.median()),mean=round(float(sub.n_c7.mean()),2),max=int(sub.n_c7.max())),
    )
    out['splits'][sp]=S
    print(f"\n=== {sp} (n={len(sub)}) ===")
    print("  固定(10,20):",S['固定10_20'])
    print("  固定(10,15):",S['固定10_15'])
    print("  弹性规则  :",S['弹性规则'])
    print("  理论上限  :",S['理论上限'])
    print("  any_ge50  :",S['any_ge50'])
    print("  档分布:",S['档分布'],"选m:",S['选目标m分布'],"平均目标m:",S['弹性平均目标m'])
    print("  lift 弹性/固定:",S['弹性lift均值'],"/",S['固定10_20_lift均值'])
# 档位举证：每档 m20 vs m15 命中（证明分档对收益-命中权衡有区分度）
for g in ['强','中','弱']:
    sub=df[df['档']==g]
    out['档举证'][g]=dict(n=len(sub),
        m20_hit=round(float(sub['r_h10_20'].mean()),4),
        m20_ge50_pct=round(float((sub['r_h10_20']>=0.5).mean())*100,2),
        m20_zero_pct=round(float((sub['r_h10_20']==0).mean())*100,2),
        m15_hit=round(float(sub['r_h10_15'].mean()),4),
        m15_ge50_pct=round(float((sub['r_h10_15']>=0.5).mean())*100,2),
        lift_m20=round(float(sub['lift_10_20'].replace([np.inf,-np.inf],np.nan).mean()),3),
        S_med=round(float(sub.S.median()),3))
    print(f"档[{g}] n={len(sub)} m20hit={out['档举证'][g]['m20_hit']} m20ge50={out['档举证'][g]['m20_ge50_pct']}% "
          f"m15hit={out['档举证'][g]['m15_hit']} m15ge50={out['档举证'][g]['m15_ge50_pct']}% lift_m20={out['档举证'][g]['lift_m20']}")
out['daily']=df[['trade_date','split','n_c7','S','档','pick_s','pick_m','r_h10_20','r_h10_15','r_h7_20','r_h7_15','r_pick','lift_pick','best_hit','any_ge50']].to_dict('records')
(WS/'elastic_rule_out.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE -> elastic_rule_out.json")

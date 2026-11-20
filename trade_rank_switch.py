# -*- coding: utf-8 -*-
"""股池内排序因子 + 切换策略（新进vs重复/池持续性）+ 突发情形量化。纯读。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd, duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_parquet(WS/'trade_path.parquet')
# 用回踩-5%买入的 MFE≥20 作为"值得买"标签（买入时机固定后，看哪些股池特征能预判）
bpx=df.c0.values*0.95
mfe20=(np.max(np.array([df[f'h{k}'].values for k in range(1,11)]),axis=0)/bpx-1)*100>=20
fill=(df.l1<=bpx)
df['mfe20']=mfe20; df['fill']=fill
SPL=df.split.values

print("=== 股池内排序因子：分5档看 MFE≥20 比例 (T日可知特征) ===")
FEATS=['vol20','lu_cnt_20d','main_net_norm','ret_5d','turnover_rate','n_leader_concepts',
       'close_hh20_ratio','bias5','mkt_amt_ratio','mkt_up_ratio']
rankres={}
for f in FEATS:
    v=df[f].replace([np.inf,-np.inf],np.nan)
    row={}
    for sp in ['train','oos']:
        m=(SPL==sp)&fill&v.notna().values
        sub=pd.DataFrame({'v':v[m],'y':df.mfe20[m].values})
        try:
            sub['q']=pd.qcut(sub.v,5,labels=False,duplicates='drop')
            qs=sub.groupby('q').y.agg(['mean','size'])
            row[sp]={'q1':round(float(qs['mean'].iloc[0])*100,1),'q5':round(float(qs['mean'].iloc[-1])*100,1),
                     'spread':round(float(qs['mean'].iloc[-1]-qs['mean'].iloc[0])*100,1)}
        except Exception as e:
            row[sp]={'err':str(e)[:30]}
    rankres[f]=row
    print(f" {f:18s} train q1={row['train'].get('q1')}% q5={row['train'].get('q5')}% spread={row['train'].get('spread')}pct | "
          f"oos q1={row['oos'].get('q1')}% q5={row['oos'].get('q5')}% spread={row['oos'].get('spread')}pct")

# 池持续性：该股连续几日留在C7
print("\n=== 池持续性（连续在C7天数）===")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect();con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
con.execute(f"""CREATE VIEW c7flag AS SELECT trade_date,di,code,CAST({C7} AS INT) AS c7 FROM read_parquet('{RM}')""")
# 连续在池：用窗口累计（简单法：向前数连续c7=1的天数）
pers=con.execute(f"""
WITH x AS (SELECT *, c7 FROM c7flag),
g AS (SELECT *, row_number() OVER (PARTITION BY code ORDER BY di) rn FROM x),
run AS (SELECT *, di - rn + 100000 AS grp_id FROM g WHERE c7=1),
cnt AS (SELECT code,di, count(*) OVER (PARTITION BY code,grp_id ORDER BY di) AS streak FROM run)
SELECT di,code,streak FROM cnt
""").df()
df=df.merge(pers[['di','code','streak']],on=['di','code'],how='left')
df['new_in']=df.streak==1
for sp in ['train','oos']:
    m=(SPL==sp)&fill
    s1=df[m&df.new_in]; s2=df[m&(df.streak>=2)]
    print(f" {sp}: 新进池(n={len(s1)}) MFE≥20={s1.mfe20.mean()*100:.1f}% | 连续在池(n={len(s2)}) MFE≥20={s2.mfe20.mean()*100:.1f}% "
          f"| 新进占比={s1.new_in.mean() if False else (m & df.new_in).sum()/m.sum()*100:.1f}%")

# 突发：大盘急跌日（mkt_ret_20d<-5）C7池表现
print("\n=== 突发：大盘急跌日 ===")
for sp in ['train','oos']:
    m=(SPL==sp)&fill
    calm=df[m&(df.mkt_ret_20d>=-5)]; crash=df[m&(df.mkt_ret_20d<-5)]
    print(f" {sp}: 常态(n={len(calm)}) MFE≥20={calm.mfe20.mean()*100:.1f}% | 大盘20日跌>5%(n={len(crash)}) MFE≥20={crash.mfe20.mean()*100:.1f}%")

# T+1涨停无法买入比例
print("\n=== T+1涨停(无法买入)比例 ===")
for sp in ['train','oos']:
    m=SPL==sp
    print(f" {sp}: T+1涨停占比={df[m].t1_limitup.mean()*100:.2f}%")

out=dict(rank=rankres,
         persist={sp:dict(new_n=int(((SPL==sp)&fill&df.new_in).sum()),
                          new_hit=round(float(df[(SPL==sp)&fill&df.new_in].mfe20.mean())*100,2),
                          old_n=int(((SPL==sp)&fill&(df.streak>=2)).sum()),
                          old_hit=round(float(df[(SPL==sp)&fill&(df.streak>=2)].mfe20.mean())*100,2)) for sp in ['train','oos']},
         crash={sp:dict(calm_hit=round(float(df[(SPL==sp)&fill&(df.mkt_ret_20d>=-5)].mfe20.mean())*100,2),
                        crash_n=int(((SPL==sp)&fill&(df.mkt_ret_20d<-5)).sum()),
                        crash_hit=round(float(df[(SPL==sp)&fill&(df.mkt_ret_20d<-5)].mfe20.mean())*100,2)) for sp in ['train','oos']},
         t1_lu={sp:round(float(df[SPL==sp].t1_limitup.mean())*100,2) for sp in ['train','oos']})
(WS/'trade_rank_switch_out.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE")

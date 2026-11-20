# -*- coding: utf-8 -*-
"""操盘策略：构建C7池前向路径表——真实可成交买入价口径 + MFE/MAE/触顶日 + 缺口。
零前视：所有决策信号当日可知；前向路径仅用于事后评估成交/止损止盈。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb, numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
t0=time.time()
# 前向12日 OHLC，用 lead 按 di（停牌极少，di连续校验）
leadcols=[]
for k in range(1,13):
    for c,alias in [('open','o'),('high','h'),('low','l'),('close','c')]:
        leadcols.append(f"lead({c},{k}) OVER (PARTITION BY code ORDER BY di) AS {alias}{k}")
lead_sql=",\n    ".join(leadcols)
sql=f"""
WITH r AS (
  SELECT trade_date,di,split,code,name,close AS c0,
    {lead_sql},
    lead(di,1) OVER (PARTITION BY code ORDER BY di) AS di1,
    lead(di,10) OVER (PARTITION BY code ORDER BY di) AS di10,
    {C7} AS c7,
    vol20, main_net_norm, lu_cnt_20d, ret_5d, turnover_rate, n_leader_concepts,
    close_hh20_ratio, bias5, lu_gap, mkt_ret_20d, mkt_amt_ratio, mkt_up_ratio,
    is_limit_up, board, pct_change, ma5, ma20, ma60
  FROM read_parquet('{RM}')
)
SELECT * FROM r WHERE split IN ('train','oos') AND di10=di+10
"""
raw=con.execute(sql).df()
print("前向完整样本:",len(raw),"c7列命中:",int(raw['c7'].sum()),"sec=%.1f"%(time.time()-t0))
# Python端重新评估C7（避免SQL布尔列歧义），与矩阵口径完全一致
cond=(raw.lu_cnt_20d>=1)&(raw.main_net_norm>0)&(raw.vol20>=3.5238)&(raw.turnover_rate>=3.7)&\
     (raw.lu_gap>=-3)&(raw.close_hh20_ratio>=0.95)&(raw.ret_5d>=4.8679)&\
     (raw.ma5>raw.ma20)&(raw.ma20>raw.ma60)&(raw.n_leader_concepts>=1)
print("Python重算C7命中:",int(cond.sum()))
df=raw[cond].reset_index(drop=True)
print("C7路径样本:",len(df))
print("di连续校验 di1=di+1:",int((df.di1==df.di+1).sum()),"/",len(df))

# 买入价口径（% 收益，相对买入价）
# 1) 研究口径：c0 -> max(h[T+1..T+n])  （起点T收盘，含未实现）
# 2) T+1开盘买入：o1 -> max(h[T+1..T+n])（真实最早可成交）
# 3) T+1收盘买入：c1 -> max(h[T+2..T+n])
# 4) T+2开盘买入：o2 -> max(h[T+2..T+n])
H=[df[f'h{k}'].values for k in range(1,11)]
H=np.array(H)  # 10 x N
df['gap_t1']=(df.o1/df.c0-1)*100            # T+1开盘相对T收盘跳空
df['mfe10_study']=(np.nanmax(H[:10],axis=0)/df.c0.values-1)*100
df['mfe10_t1open']=(np.nanmax(H[:10],axis=0)/df.o1.values-1)*100
H2=H[1:10]  # T+2..T+10
df['mfe10_t1close']=(np.nanmax(H2,axis=0)/df.c1.values-1)*100
df['mfe10_t2open']=(np.nanmax(H2,axis=0)/df.o2.values-1)*100
# 7日口径
df['mfe7_t1open']=(np.nanmax(H[:7],axis=0)/df.o1.values-1)*100
df['mfe7_study']=(np.nanmax(H[:7],axis=0)/df.c0.values-1)*100
# MFE/MAE（T+1开盘买入，10日）
L=np.array([df[f'l{k}'].values for k in range(1,11)])
C=np.array([df[f'c{k}'].values for k in range(1,11)])
df['mae10']=(np.nanmin(L,axis=0)/df.o1.values-1)*100
df['ret10_t1open']=(C[9]/df.o1.values-1)*100   # 持有到第10日收盘的收益
# 触顶日：max high 出现在第几日
df['peak_day']=np.nanargmax(H[:10],axis=0)+1
# T+1涨停无法买入：T+1涨幅=(c1/c0-1)*100 >= 该股涨停阈值(近似用is_limit_up等价)
df['t1_pct']=(df.c1/df.c0-1)*100
df['t1_limitup']=df['t1_pct']>=9.8

def rate(mask,col,th=20):
    s=df.loc[mask,col].dropna()
    return len(s),(s>=th).mean() if len(s) else np.nan, s.median() if len(s) else np.nan
print("\n=== 买入口径命中率 (m=20) ===")
for sp in ['train','oos']:
    mk=df.split==sp
    print(f"-- {sp} (n={mk.sum()}) --")
    for col in ['mfe10_study','mfe10_t1open','mfe10_t1close','mfe10_t2open','mfe7_study','mfe7_t1open']:
        n,r,med=rate(mk,col)
        print(f"  {col:16s}: hit20={r*100:5.2f}%  median_mfe={med:5.2f}%")
print("\n=== 跳空缺口 gap_t1 (T+1开盘 vs T收盘) ===")
for sp in ['train','oos']:
    g=df.loc[df.split==sp,'gap_t1'].dropna()
    print(f" {sp}: mean={g.mean():.2f}% median={g.median():.2f}% p10={g.quantile(.1):.2f}% p90={g.quantile(.9):.2f}% "
          f">5%占比={(g>5).mean()*100:.1f}% <-5%占比={(g<-5).mean()*100:.1f}%")
print("\n=== MFE/MAE/触顶日 (T+1开盘买入,10日) ===")
for sp in ['train','oos']:
    s=df[df.split==sp]
    print(f" {sp}: MFE10均={s.mfe10_t1open.mean():.1f}% MAE10均={s.mae10.mean():.1f}% "
          f"触顶日均={s.peak_day.mean():.2f} 触顶≤3日占比={(s.peak_day<=3).mean()*100:.1f}% "
          f"持有10日收益均={s.ret10_t1open.mean():.2f}%")
# 保存路径表（供止损止盈/排序复用）
df.to_parquet(WS/'trade_path.parquet',index=False)
prof=dict(n=len(df),train=int((df.split=='train').sum()),oos=int((df.split=='oos').sum()),
          buy_compare={sp:{c:round(rate(df.split==sp,c)[1]*100,2) for c in ['mfe10_study','mfe10_t1open','mfe10_t1close','mfe10_t2open','mfe7_t1open']} for sp in ['train','oos']},
          gap={sp:dict(mean=round(float(df[df.split==sp].gap_t1.mean()),3),med=round(float(df[df.split==sp].gap_t1.median()),3),
                       gt5=round(float((df[df.split==sp].gap_t1>5).mean())*100,2),ltm5=round(float((df[df.split==sp].gap_t1<-5).mean())*100,2)) for sp in ['train','oos']},
          sec=round(time.time()-t0,1))
(WS/'trade_path_profile.json').write_text(json.dumps(prof,ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE -> trade_path.parquet")

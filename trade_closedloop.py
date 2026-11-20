# -*- coding: utf-8 -*-
"""策略闭环验证：回踩-5%买入 + 池内综合排序(top50%) + 止损止盈(tp15/sl-8/hold7)。
排序方向在train确定，固定后oos验证（无前视）。对比：无排序 vs 排序。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df=pd.read_parquet(WS/'trade_path.parquet')
# 池持续性 merge
RM=(WS/'research_matrix.parquet').as_posix()
import duckdb
con=duckdb.connect();con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
pers=con.execute(f"""
WITH g AS (SELECT di,code,CAST({C7} AS INT) c7,row_number() OVER (PARTITION BY code ORDER BY di) rn FROM read_parquet('{RM}')),
run AS (SELECT *,di-rn AS grp FROM g WHERE c7=1)
SELECT di,code,count(*) OVER (PARTITION BY code,grp ORDER BY di) streak FROM run
""").df()
df=df.merge(pers[['di','code','streak']],on=['di','code'],how='left')

# 回踩-5%买入
c0=df.c0.values;bpx=c0*0.95
filled=df.l1.values<=bpx
H=np.array([df[f'h{k}'].values for k in range(1,11)])
L=np.array([df[f'l{k}'].values for k in range(1,11)])
C=np.array([df[f'c{k}'].values for k in range(1,11)])
mfe20=(np.max(H,axis=0)/bpx-1)*100>=20
# 收益(tp15/sl-8/hold7)
tp,sl,hold=15,-8,7
tp_px=bpx*1.15; sl_px=bpx*0.92
ret=np.full(len(df),np.nan);reason=np.empty(len(df),dtype='U4')
for i in range(len(df)):
    if not filled[i]:continue
    for d in range(hold):
        if L[d,i]<=sl_px[i]:ret[i]=sl;reason[i]='SL';break
        if H[d,i]>=tp_px[i]:ret[i]=tp;reason[i]='TP';break
    if np.isnan(ret[i]):ret[i]=(C[hold-1,i]/bpx[i]-1)*100;reason[i]='TIME'
df['filled']=filled;df['mfe20']=mfe20;df['ret']=ret

# 综合排序分（train确定方向：vol20↑ ret_5d↑ turnover↑ streak↑；用train分位归一）
def zscore(v,ref):
    return (v-np.nanmean(ref))/np.nanstd(ref)
tr=(df.split=='train').values&filled
vol_ref=df.loc[tr,'vol20'].values; ret_ref=df.loc[tr,'ret_5d'].values; tor_ref=df.loc[tr,'turnover_rate'].values
score=(zscore(df.vol20.values,vol_ref)+zscore(df.ret_5d.values,ret_ref)+
       zscore(df.turnover_rate.values,tor_ref)+0.5*zscore(df.streak.fillna(1).values,np.ones(tr.sum())))
df['score']=score

print("=== 闭环：回踩-5%买入，池内排序top50% ===")
out={}
for sp in ['train','oos']:
    m=df.split==sp
    base=df[m&filled]
    # 每日取score top50%（模拟每日资金有限）
    def top_half(sub):
        parts=[]
        for d,g in sub.groupby('di'):
            k=max(1,int(len(g)*0.5))
            parts.append(g.nlargest(k,'score'))
        return pd.concat(parts) if parts else sub.iloc[0:0]
    top=top_half(base)
    rec=dict(
        base_n=len(base),top_n=len(top),
        base_mfe20=round(float(base.mfe20.mean())*100,2),top_mfe20=round(float(top.mfe20.mean())*100,2),
        base_ret=round(float(base.ret.mean()),3),top_ret=round(float(top.ret.mean()),3),
        base_win=round(float((base.ret>0).mean())*100,2),top_win=round(float((top.ret>0).mean())*100,2))
    out[sp]=rec
    print(f" {sp}: 无排序(n={rec['base_n']}) MFE≥20={rec['base_mfe20']}% 期望={rec['base_ret']}% 胜率={rec['base_win']}%")
    print(f"       top50%(n={rec['top_n']}) MFE≥20={rec['top_mfe20']}% 期望={rec['top_ret']}% 胜率={rec['top_win']}%")

# 持续在池 vs 新进（回踩买入口径）
print("\n=== 切换依据：连续在池 vs 新进（回踩买入口径，双期）===")
for sp in ['train','oos']:
    m=(df.split==sp)&filled
    old=df[m&(df.streak>=2)];new=df[m&(df.streak==1)]
    print(f" {sp}: 连续在池(n={len(old)}) 期望={old.ret.mean():.3f}% MFE≥20={old.mfe20.mean()*100:.1f}% | "
          f"新进(n={len(new)}) 期望={new.ret.mean():.3f}% MFE≥20={new.mfe20.mean()*100:.1f}%")

(WS/'trade_closedloop_out.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE")

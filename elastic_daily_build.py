# -*- coding: utf-8 -*-
"""弹性(n,m)机制：构建逐日宽表——每日 C7 池在4个(n,m)组合的命中率 + 当日可知市场特征。
n∈{7,10}, m∈{15,20}（用户约束：最佳范围内 n7~10/m15~20）。纯读，零前视。
市场特征全部 T 日可知（build_matrix.py 中滚动/当日统计），mkt_hit5/10 含未来标签禁用。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb, numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
t0=time.time()
sql=f"""
WITH r AS (
  SELECT trade_date, split, code,
    CASE WHEN {C7} THEN 1 ELSE 0 END AS c7,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 7 FOLLOWING)
      /NULLIF(close,0)-1)*100 AS fmax7,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)
      /NULLIF(close,0)-1)*100 AS fmax10,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn10,
    mkt_ret_5d, mkt_ret_10d, mkt_ret_20d, mkt_amt_ratio, mkt_lu, mkt_lu_ma5,
    mkt_up_ratio, mkt_pct_mean, eff_hit10_lag, eff_hit5_lag, mkt_amount, mkt_n
  FROM read_parquet('{RM}')
),
v AS (SELECT * FROM r WHERE nn10=10 AND split IN ('train','oos'))
SELECT trade_date, max(split) AS split,
  count(*) FILTER (WHERE c7=1) AS n_c7,
  count(*) FILTER (WHERE c7=1 AND fmax10>=20) AS h10_20,
  count(*) FILTER (WHERE c7=1 AND fmax10>=15) AS h10_15,
  count(*) FILTER (WHERE c7=1 AND fmax10>=10) AS h10_10,
  count(*) FILTER (WHERE c7=1 AND fmax7>=20)  AS h7_20,
  count(*) FILTER (WHERE c7=1 AND fmax7>=15)  AS h7_15,
  count(*) FILTER (WHERE c7=1 AND fmax7>=10)  AS h7_10,
  count(*) FILTER (WHERE c7=0) AS n_mkt,
  count(*) FILTER (WHERE c7=0 AND fmax10>=20) AS m10_20,
  count(*) FILTER (WHERE c7=0 AND fmax10>=15) AS m10_15,
  count(*) FILTER (WHERE c7=0 AND fmax7>=20)  AS m7_20,
  count(*) FILTER (WHERE c7=0 AND fmax7>=15)  AS m7_15,
  max(mkt_ret_5d) AS mkt_ret_5d, max(mkt_ret_10d) AS mkt_ret_10d,
  max(mkt_ret_20d) AS mkt_ret_20d, max(mkt_amt_ratio) AS mkt_amt_ratio,
  max(mkt_lu) AS mkt_lu, max(mkt_lu_ma5) AS mkt_lu_ma5,
  max(mkt_up_ratio) AS mkt_up_ratio, max(mkt_pct_mean) AS mkt_pct_mean,
  max(eff_hit10_lag) AS eff_hit10_lag, max(eff_hit5_lag) AS eff_hit5_lag,
  max(mkt_amount) AS mkt_amount, max(mkt_n) AS mkt_n
FROM v GROUP BY trade_date ORDER BY trade_date
"""
df=con.execute(sql).df()
for c in ['h10_20','h10_15','h10_10','h7_20','h7_15','h7_10']:
    df['r_'+c]=df[c]/df['n_c7'].replace(0,np.nan)
for c in ['m10_20','m10_15','m7_20','m7_15']:
    df['r_'+c]=df[c]/df['n_mkt'].replace(0,np.nan)
# lift（C7命中率 / 当日全市场命中率），逐组合
for k in ['10_20','10_15','7_20','7_15']:
    df['lift_'+k]=df['r_h'+k]/df['r_m'+k].replace(0,np.nan)
df.to_csv(WS/'elastic_daily.csv',index=False,encoding='utf-8-sig')
print("days:",len(df),"split:",df['split'].value_counts().to_dict(),"sec=%.1f"%(time.time()-t0))
print("n_c7: min=%d med=%.0f max=%d mean=%.2f"%(df.n_c7.min(),df.n_c7.median(),df.n_c7.max(),df.n_c7.mean()))
cols=['r_h10_20','r_h10_15','r_h10_10','r_h7_20','r_h7_15','r_h7_10']
for sp in ['train','oos']:
    d=df[df.split==sp]
    print(f"-- {sp} (n={len(d)}) mean hit --",{c:round(d[c].mean(),4) for c in cols})
    print(f"   ge50%日期:",{c:int((d[c]>=0.5).sum()) for c in cols})
    print(f"   ==0日期:",{c:int((d[c]==0).sum()) for c in cols})
# 市场特征分布
feats=['mkt_ret_5d','mkt_ret_20d','mkt_amt_ratio','mkt_lu','mkt_lu_ma5','mkt_up_ratio','mkt_pct_mean','eff_hit10_lag']
print("-- 市场特征缺失率 --",{c:round(df[c].isna().mean(),4) for c in feats})
print("-- 市场特征分位(train) --")
for c in feats:
    q=df[df.split=='train'][c].quantile([0,.25,.5,.75,1]).values
    print(f"  {c}: {[round(float(x),3) for x in q]}")
print("DONE")

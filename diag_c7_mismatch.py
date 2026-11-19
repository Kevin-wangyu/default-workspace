# -*- coding: utf-8 -*-
"""RCA: 对比 2024-09-27 matrix 与 live 各特征逐字段值，定位 MISMATCH 根因。纯读。"""
from pathlib import Path
import duckdb, numpy as np, pandas as pd
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT=(WS/"research_matrix.parquet").as_posix()
p=lambda *x: str(Path(PROJ,*x)).replace("\\","/")
con=duckdb.connect(); con.execute("SET threads=8")

QG=f"read_parquet('{p('data_compact','quote','*.parquet')}',union_by_name=true)"
DG=f"read_parquet('{p('data_compact','daily_pct','*.parquet')}',union_by_name=true)"
CG=f"read_parquet('{p('data_compact','concept_date','*.parquet')}',union_by_name=true)"
META=f"read_parquet('{p('data_compact','_tops_cache','v1','meta.parquet')}')"

# matrix 当日全量特征
mcols="code,lu_cnt_20d,main_net_norm,vol20,turnover_rate,lu_gap,close_hh20_ratio,ret_5d,ma5,ma20,ma60,n_leader_concepts,pct_change"
m=con.execute(f"SELECT {mcols} FROM read_parquet('{MAT}') WHERE trade_date='2024-09-27'").df()
codes=list(m["code"])[:3]  # 取3只样本
print("matrix sample codes:",codes)

live_sql=f"""
WITH
qx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d,code,name,close,high,amount,
 turnover_rate,pct_change,huge_order_net,big_order_net FROM {QG}),
dx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d,code,
 CASE WHEN isfinite(pct_change) THEN pct_change END AS pct_change FROM {DG}),
cal AS (SELECT d,row_number() OVER (ORDER BY d) AS di FROM (SELECT DISTINCT d FROM qx)),
base AS (SELECT q.*,c.di,d.pct_change AS daily_pct,
 CASE WHEN left(q.code,2) IN ('30','68') THEN 19.8
 WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8 ELSE 9.8 END AS lu_thr
 FROM qx q JOIN cal c USING(d) LEFT JOIN dx d ON q.d=d.d AND q.code=d.code),
st AS (SELECT b.*,avg(close) OVER w5 ma5,avg(close) OVER w20 ma20,avg(close) OVER w60 ma60,
 stddev_samp(daily_pct) OVER w20 vol20,max(high) OVER w20 hh20,lag(close,5) OVER wc close_5d_ago,
 sum(CASE WHEN daily_pct>=lu_thr-0.15 AND daily_pct IS NOT NULL THEN 1 ELSE 0 END) OVER w20 lu_cnt_20d
 FROM base b WINDOW wc AS(PARTITION BY code ORDER BY di),
 w5 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
 w20 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
 w60 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)),
cdx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d,code,trim(t.x) cname FROM {CG},unnest(string_split(concepts,';')) t(x)),
sc AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d,concept_name cname,max(score) score FROM {META} WHERE row_type='score' GROUP BY 1,2),
lead AS (SELECT x.d,x.code,count(DISTINCT x.cname) FILTER(WHERE s.score>=0.8) n_leader_concepts FROM cdx x LEFT JOIN sc s ON x.d=s.d AND x.cname=s.cname GROUP BY x.d,x.code),
feat AS (SELECT st.d trade_date,st.code,st.lu_cnt_20d,
 (coalesce(st.huge_order_net,0)+coalesce(st.big_order_net,0))/NULLIF(st.amount,0) main_net_norm,
 st.vol20,st.turnover_rate,st.pct_change-st.lu_thr lu_gap,st.close/NULLIF(st.hh20,0) close_hh20_ratio,
 (st.close/NULLIF(st.close_5d_ago,0)-1)*100 ret_5d,st.ma5,st.ma20,st.ma60,
 coalesce(ld.n_leader_concepts,0) n_leader_concepts,st.pct_change
 FROM st LEFT JOIN lead ld ON st.d=ld.d AND st.code=ld.code)
SELECT {','.join('code,'+c for c in mcols.split(',') if c!='code').replace('code,code,','code,')} FROM feat
WHERE trade_date='2024-09-27' AND code IN ({','.join(repr(c) for c in codes)})
"""
try:
    l=con.execute(live_sql).df()
except Exception as e:
    print("LIVE SQL ERROR:",e)
    # 退化为 SELECT *
    l=con.execute(live_sql.replace(live_sql[live_sql.index("SELECT {",live_sql.index("feat AS")):] if False else live_sql,"SELECT * FROM feat WHERE trade_date='2024-09-27' AND code IN ("+','.join(repr(c) for c in codes)+")")).df()

print("live cols:",list(l.columns))
j=m[m.code.isin(codes)].merge(l,on='code',suffixes=('_m','_l'))
pd.set_option('display.width',250,'display.max_columns',60)
for c in ['lu_cnt_20d','main_net_norm','vol20','turnover_rate','lu_gap','close_hh20_ratio','ret_5d','ma5','ma20','ma60','n_leader_concepts','pct_change']:
    a=j.get(c+'_m'); b=j.get(c+'_l')
    if a is None or b is None:
        print(c,"MISSING ONE SIDE"); continue
    d=(~np.isclose(a.values.astype(float),b.values.astype(float),rtol=1e-6,atol=1e-6,equal_nan=True))
    print(f"{c:20s} differ={d.sum()}/{len(j)}  matrix={list(np.round(a.values,3))}  live={list(np.round(b.values,3))}")
print("DONE")

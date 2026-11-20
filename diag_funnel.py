# -*- coding: utf-8 -*-
"""近端完整条件漏斗：2026-11-19 逐条件累计通过数，定位真正卡点。纯读。"""
import sys
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
import duckdb
from config import COMPACT_DIR
from queries import c7_picks as C
QG=C._QG; DG=C._DG; CG=C._CG; META=C._META
D='2026-11-19'
con=duckdb.connect(); con.execute("SET threads=8")
sql=f"""
WITH
alld AS (SELECT DISTINCT substr(CAST(trade_date AS VARCHAR),1,10) d FROM {QG}),
calall AS (SELECT d,row_number() OVER(ORDER BY d) di FROM alld),
tdi AS (SELECT di FROM calall WHERE d=substr('{D}',1,10)),
win AS (SELECT d FROM calall,tdi WHERE calall.di BETWEEN tdi.di-124 AND tdi.di),
qx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,name,close,high,amount,
       turnover_rate,pct_change,huge_order_net,big_order_net FROM {QG}
       WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN (SELECT d FROM win)),
dx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,
       CASE WHEN isfinite(pct_change) THEN pct_change END pct_change FROM {DG}
       WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN (SELECT d FROM win)),
cal AS (SELECT d,row_number() OVER(ORDER BY d) di FROM (SELECT DISTINCT d FROM qx)),
base AS (SELECT q.*,c.di,d.pct_change daily_pct,
  CASE WHEN left(q.code,2) IN ('30','68') THEN 19.8 WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8 ELSE 9.8 END lu_thr
 FROM qx q JOIN cal c USING(d) LEFT JOIN dx d ON q.d=d.d AND q.code=d.code),
st AS (SELECT b.*,avg(close) OVER w5 ma5,avg(close) OVER w20 ma20,avg(close) OVER w60 ma60,
  stddev_samp(daily_pct) OVER w20 vol20,max(high) OVER w20 hh20,lag(close,5) OVER wc close_5d_ago,
  sum(CASE WHEN daily_pct>=lu_thr-0.15 AND daily_pct IS NOT NULL THEN 1 ELSE 0 END) OVER w20 lu_cnt_20d
 FROM base b WINDOW wc AS(PARTITION BY code ORDER BY di),
  w5 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
  w20 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
  w60 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)),
cdx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,trim(t.x) cname FROM {CG},
        unnest(string_split(concepts,';')) t(x)
        WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN (SELECT d FROM cal)),
sc AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,concept_name cname,max(score) score
       FROM {META} WHERE row_type='score' GROUP BY 1,2),
lead AS (SELECT x.d,x.code,count(DISTINCT x.cname) FILTER(WHERE s.score>=0.8) n_leader
         FROM cdx x LEFT JOIN sc s ON x.d=s.d AND x.cname=s.cname GROUP BY x.d,x.code),
feat AS (SELECT st.*,coalesce(ld.n_leader,0) n_leader_concepts,
  (coalesce(huge_order_net,0)+coalesce(big_order_net,0))/nullif(amount,0) main_net_norm,
  daily_pct-lu_thr lu_gap,close/nullif(hh20,0) close_hh20_ratio,
  (close/nullif(close_5d_ago,0)-1)*100 ret_5d FROM st LEFT JOIN lead ld ON st.d=ld.d AND st.code=ld.code)
SELECT count(*) tot,
 sum(CAST(lu_cnt_20d>=1 AS INT)) c_lu,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AS INT)) c_fund,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AS INT)) c_vol,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AS INT)) c_tor,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AND lu_gap>=-3 AS INT)) c_gap,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AS INT)) c_hh,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AS INT)) c_ret,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60 AS INT)) c_ma,
 sum(CAST(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1 AS INT)) c_lead
FROM feat WHERE d=substr('{D}',1,10)
"""
r=con.execute(sql).fetchone()
labels=['tot','c_lu','c_fund','c_vol','c_tor','c_gap','c_hh','c_ret','c_ma','c_lead']
print(f"=== 完整条件漏斗（{D}）逐条件累计通过 ===")
for lab,val in zip(labels,r):
    print(f"  {lab}: {val}")
con.close()

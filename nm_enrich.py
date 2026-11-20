# -*- coding: utf-8 -*-
"""补充：收益效率(m×hit)、边际效率、日级捕获率、约束下最优。读 nm_analysis_out.json + 矩阵。"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"nm_analysis_out.json").read_text(encoding="utf-8"))
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
res=D['grid']; NS=D['config']['NS']; MS=D['config']['MS']

# ---- 1) 收益效率表 ----
eff=[]
for split in ['train','oos']:
    for n in NS:
        for m in MS:
            r=res.get(f"{split}|{n}|{m}")
            if not r or r['c7_hit_rate'] is None: continue
            h=r['c7_hit_rate']
            eff.append(dict(split=split,n=n,m=m,hit=round(h,4),
                            gain_trade=round(m*h,3),        # 理想化单次收益 = m × 命中率
                            gain_day=round(m*h/n,4)))        # 理想化每持仓日收益

# 各口径最优
best={}
for split in ['train','oos']:
    es=[e for e in eff if e['split']==split]
    best[f"{split}_gain_trade"]=max(es,key=lambda x:x['gain_trade'])
    best[f"{split}_gain_day"]=max(es,key=lambda x:x['gain_day'])
    # 约束：命中率≥30% 时最优 gain_day
    best[f"{split}_gain_day_hit30"]=max([e for e in es if e['hit']>=0.30],key=lambda x:x['gain_day'])
    # 约束：m>=20 时最优 gain_day
    best[f"{split}_gain_day_m20"]=max([e for e in es if e['m']>=20],key=lambda x:x['gain_day'])

# ---- 2) 日级捕获率（m=20，对每日先算 c7命中/全市场命中，再按日聚合） ----
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
daycap=[]
for n in [5,10,15]:
    sql=f"""
    WITH r AS (
      SELECT split,trade_date,
        max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND {n} FOLLOWING)/NULLIF(close,0)-1 AS fr,
        count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND {n} FOLLOWING) AS nn,
        CASE WHEN {C7} THEN 1 ELSE 0 END c7
      FROM read_parquet('{RM}')
    ),
    d AS (SELECT split,trade_date,
            count(*) FILTER(WHERE nn={n} AND fr>=0.20 AND c7=1) c7hit,
            count(*) FILTER(WHERE nn={n} AND fr>=0.20) allhit
          FROM r GROUP BY split,trade_date)
    SELECT split,
      sum(c7hit) c7hit, sum(allhit) allhit,
      sum(c7hit)*1.0/nullif(sum(allhit),0) cap_pooled,
      avg(CASE WHEN allhit>0 THEN c7hit*1.0/allhit END) cap_daymean,
      count(*) FILTER(WHERE allhit>0) nd_with_hit,
      count(*) FILTER(WHERE c7hit>0) nd_c7hit
    FROM d WHERE split IN ('train','oos') GROUP BY split ORDER BY split
    """
    for row in con.execute(sql).fetchall():
        daycap.append(dict(n=n,split=row[0],c7hit=row[1],allhit=row[2],
                           cap_pooled=round(row[3],6) if row[3] is not None else None,
                           cap_daymean=round(row[4],6) if row[4] is not None else None,
                           nd_with_hit=row[5],nd_c7hit=row[6]))

out=dict(eff=eff,best=best,daycap=daycap,
         meta=D['meta'])
(WS/"nm_enrich_out.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")

print("=== 理想化收益 m×hit（单次）/ 每持仓日 m×hit/n ===")
for split in ['train','oos']:
    print(f"-- {split} (m=20 行) --")
    for n in NS:
        e=[x for x in eff if x['split']==split and x['n']==n and x['m']==20][0]
        print(f"  n={n:>2}: hit={e['hit']*100:5.1f}%  gain/trade={e['gain_trade']:.2f}%  gain/day={e['gain_day']:.3f}%")
    print(f"-- {split} (n=10 各 m) --")
    for m in MS:
        e=[x for x in eff if x['split']==split and x['n']==10 and x['m']==m][0]
        print(f"  m={m:>2}: hit={e['hit']*100:5.1f}%  gain/trade={e['gain_trade']:.2f}%  gain/day={e['gain_day']:.3f}%")
print("=== 各口径最优 ===")
for k,v in best.items():
    print(f"  {k}: n={v['n']} m={v['m']} hit={v['hit']*100:.1f}% gain/day={v['gain_day']:.3f}%")
print("=== 日级捕获率(m=20) ===")
for d in daycap:
    print(f"  n={d['n']:>2} {d['split']}: cap_pooled={d['cap_pooled']*100:.3f}% cap_daymean={d['cap_daymean']*100:.3f}% days_c7hit={d['nd_c7hit']}/{d['nd_with_hit']}")
print("DONE")

# -*- coding: utf-8 -*-
"""诊断：市场分档对 (a) n 维度 (b) 1-2日触发滞后叠加 是否真有区分度。纯读。
若市场状态无法区分"哪天用哪个n/是否放宽触发窗口"→ 弹性机制在 better定义上不成立，如实报告。
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd, duckdb
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/'research_matrix.parquet').as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""

# (a) 各档 n 维度：用逐日宽表(已有r_h7_20/r_h10_20)
df=pd.read_csv(WS/'elastic_daily.csv')
c7dates=set(d['date'] for d in json.loads((WS/'c7_daily_out.json').read_text(encoding='utf-8'))['daily'])
df=df[df.trade_date.isin(c7dates)].reset_index(drop=True)
# 用上一版S重算分档（同 elastic_rule 口径）
FEATS=['mkt_amt_ratio','mkt_ret_5d','mkt_ret_20d','mkt_up_ratio','mkt_lu','eff_hit10_lag']
X=df[FEATS].copy()
for c in FEATS:
    lo,hi=X[c].quantile(0.01),X[c].quantile(0.99); X[c]=X[c].clip(lo,hi)
tr=(df.split=='train').values
w={c:np.corrcoef(X.loc[tr,c].astype(float),df.loc[tr,'r_h10_20'].astype(float))[0,1] for c in FEATS}
mu=X[tr].mean(); sd=X[tr].std().replace(0,1)
df['S']=(((X-mu)/sd)*pd.Series(w)).sum(axis=1).astype(float)
q33,q67=df.loc[tr,'S'].quantile(1/3),df.loc[tr,'S'].quantile(2/3)
df['档']=df.S.apply(lambda s:'强' if s>=q67 else ('中' if s>=q33 else '弱'))

print("=== (a) 各档 n 维度 (m=20) ===")
for g in ['强','中','弱']:
    sub=df[df['档']==g]
    print(f"档[{g}] n={len(sub)} n10hit={sub.r_h10_20.mean():.4f} n7hit={sub.r_h7_20.mean():.4f} "
          f"n10>n7天数={int((sub.r_h10_20>sub.r_h7_20).sum())} n7>n10天数={int((sub.r_h7_20>sub.r_h10_20).sum())}")
print("→ 若 n10 恒优于 n7，则 n 不是可弹性调节的杠杆")

# (b) 触发日归集：某股 T 满足C7，但 provenance 用 T 或 T-1/T-2 触发的 fwd_max
print("\n=== (b) 触发窗口归集：T日 vs T-1/T-2触发 (m=20,n=10) ===")
# 对每天，计算 C7(T) 命中(已有) + C7(T-1)/C7(T-2) 标的在 T 日的 fwd_max命中
# 用 SQL：每日 C7 触发集合(近3日并集) 与 T日 fwd_max 标签
sql=f"""
WITH r AS (
  SELECT trade_date,di,split,code,
    CASE WHEN {C7} THEN 1 ELSE 0 END AS c7,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)
      /NULLIF(close,0)-1)*100 AS fmax,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn
  FROM read_parquet('{RM}')
),
v AS (SELECT * FROM r WHERE nn=10 AND split IN ('train','oos')),
trig AS (
  SELECT trade_date, code,
    max(c7) AS c7_any3,   -- T,T-1,T-2 任一触发(用 di 窗口)
    max(c7) AS c7_today
  FROM (SELECT * FROM v) GROUP BY trade_date,code
)
SELECT count(*) FROM v LIMIT 1
"""
# 简化：直接在 python 里用 pivot（C7 状态按 code,di）
cols=['di','trade_date','split','code','c7_any3','fmax_hit']
w=con.execute(f"""
WITH r AS (
  SELECT trade_date,di,split,code,
    CASE WHEN {C7} THEN 1 ELSE 0 END AS c7,
    (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING)
      /NULLIF(close,0)-1)*100 AS fmax,
    count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS nn
  FROM read_parquet('{RM}')
),
v AS (SELECT * FROM r WHERE nn=10 AND split IN ('train','oos')),
w AS (
  SELECT *, max(c7) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 2 PRECEDING AND CURRENT ROW) AS c7_any3,
    CASE WHEN fmax>=20 THEN 1 ELSE 0 END AS fhit
  FROM v
)
SELECT di,trade_date,split,code,c7,c7_any3,fhit FROM w
""").df()
print("rows:",len(w))
# 按日聚合：T日C7命中 vs 近3日触发并集命中
g=w.groupby(['trade_date','split']).agg(
    n_today=('c7','sum'),hit_today=('fhit',lambda s: 0),
).reset_index()
# 正确：命中仅在 c7=1(today) 或 c7_any3=1 的行上算
w['f_today']=w['c7']*w['fhit']; w['f_any3']=w['c7_any3']*w['fhit']
g=w.groupby(['trade_date','split']).agg(n_today=('c7','sum'),f_today=('f_today','sum'),
                                        n_any3=('c7_any3','sum'),f_any3=('f_any3','sum')).reset_index()
g['r_today']=g.f_today/g.n_today.replace(0,np.nan); g['r_any3']=g.f_any3/g.n_any3.replace(0,np.nan)
g=g[g.trade_date.isin(c7dates)]
print("触发窗口对命中率影响:")
for sp in ['train','oos']:
    s=g[g.split==sp]
    print(f" {sp}: today={s.r_today.mean():.4f} any3={s.r_any3.mean():.4f} 提升={100*(s.r_any3.mean()-s.r_today.mean()):.2f}pct "
          f"| n_today均={s.n_today.mean():.1f} n_any3均={s.n_any3.mean():.1f}")
# 市场分档 × 窗口提升
g['档']=g.trade_date.map(df.set_index('trade_date')['档']).values
for gname in ['强','中','弱']:
    s=g[g['档']==gname]
    print(f" 档[{gname}] n={len(s)} today={s.r_today.mean():.4f} any3={s.r_any3.mean():.4f} "
          f"window_gain={100*(s.r_any3.mean()-s.r_today.mean()):.2f}pct")
out=dict(n_dim={g:dict(n=len(df[df['档']==g]),n10=float(df[df['档']==g].r_h10_20.mean()),
                      n7=float(df[df['档']==g].r_h7_20.mean())) for g in ['强','中','弱']},
         window=g[['trade_date','split','n_today','n_any3','r_today','r_any3','档']].to_dict('records'))
(WS/'diag_elastic_signal_out.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print("\nDONE")

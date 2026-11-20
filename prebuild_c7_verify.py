# -*- coding: utf-8 -*-
"""全量预计算 C6/C7 合并池：复用 c7_picks.py 确切口径，一次扫全量算所有交易日。
先验证：①与 c7_picks._compute 逐股一致（C7 子集）②与 research_matrix 集合一致
③近端 C6 补充数量。验证通过后再落地缓存。不修改任何原始数据。
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import duckdb, pandas as pd

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
sys.path.insert(0, PROJ)
from config import COMPACT_DIR, DATA_DIR

QG = f"read_parquet('{(COMPACT_DIR / 'quote' / '*.parquet').as_posix()}', union_by_name=true)"
DG = f"read_parquet('{(COMPACT_DIR / 'daily_pct' / '*.parquet').as_posix()}', union_by_name=true)"
CG = f"read_parquet('{(COMPACT_DIR / 'concept_date' / '*.parquet').as_posix()}', union_by_name=true)"
BARS = f"read_parquet('{(COMPACT_DIR / '_tops_cache' / 'v1' / 'bars.parquet').as_posix()}')"
META = f"read_parquet('{(COMPACT_DIR / '_tops_cache' / 'v1' / 'meta.parquet').as_posix()}')"

THR = dict(lu_cnt_20d=1.0, main_net_norm=0.0, vol20=3.5238, turnover_rate=3.7,
           lu_gap=-3.0, close_hh20_ratio=0.95, ret_5d=4.8679, n_leader_concepts=1.0)
Z = dict(vol_m=3.010096, vol_s=1.639706, ret_m=0.848288, ret_s=7.840214,
         tor_m=4.794629, tor_s=5.705012)

# 前8条件（C6）= C7 去掉龙头概念；C7 = C6 AND n_leader>=1
C6COND = f"""lu_cnt_20d >= {THR['lu_cnt_20d']}
  AND main_net_norm > {THR['main_net_norm']}
  AND vol20 >= {THR['vol20']}
  AND turnover_rate >= {THR['turnover_rate']}
  AND lu_gap >= {THR['lu_gap']}
  AND close_hh20_ratio >= {THR['close_hh20_ratio']}
  AND ret_5d >= {THR['ret_5d']}
  AND ma5 > ma20 AND ma20 > ma60"""

SQL = f"""
WITH
qx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, name, close, high,
         amount, turnover_rate, pct_change, huge_order_net, big_order_net
  FROM {QG}
),
dx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code,
         CASE WHEN isfinite(pct_change) THEN pct_change END AS pct_change
  FROM {DG}
),
cal AS (SELECT d, row_number() OVER (ORDER BY d) AS di FROM (SELECT DISTINCT d FROM qx)),
base AS (
  SELECT q.*, c.di, d.pct_change AS daily_pct,
    CASE WHEN left(q.code,2) IN ('30','68') THEN 19.8
         WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8
         ELSE 9.8 END AS lu_thr
  FROM qx q JOIN cal c USING (d)
  LEFT JOIN dx d ON q.d=d.d AND q.code=d.code
),
st AS (
  SELECT b.*,
    avg(close) OVER w5  AS ma5,
    avg(close) OVER w20 AS ma20,
    avg(close) OVER w60 AS ma60,
    stddev_samp(daily_pct) OVER w20 AS vol20,
    max(high) OVER w20 AS hh20,
    lag(close,5) OVER wc AS close_5d_ago,
    sum(CASE WHEN daily_pct >= lu_thr-0.15 AND daily_pct IS NOT NULL THEN 1 ELSE 0 END)
        OVER w20 AS lu_cnt_20d
  FROM base b
  WINDOW wc AS (PARTITION BY code ORDER BY di),
         w5  AS (PARTITION BY code ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW),
         w20 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
         w60 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
),
cdx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, trim(t.x) AS cname
  FROM {CG}, unnest(string_split(concepts,';')) AS t(x)
),
sc AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, concept_name AS cname,
         max(score) AS score FROM {META} WHERE row_type='score' GROUP BY 1,2
),
lead AS (
  SELECT x.d, x.code, count(DISTINCT x.cname) FILTER (WHERE s.score>=0.8) AS n_leader_concepts
  FROM cdx x LEFT JOIN sc s ON x.d=s.d AND x.cname=s.cname
  GROUP BY x.d, x.code
),
feat AS (
  SELECT st.d AS trade_date, st.di, st.code, st.name, st.daily_pct AS pct_change,
    st.close, st.amount, st.lu_cnt_20d,
    (coalesce(st.huge_order_net,0)+coalesce(st.big_order_net,0))/NULLIF(st.amount,0) AS main_net_norm,
    st.vol20, st.turnover_rate, st.daily_pct - st.lu_thr AS lu_gap,
    st.close/NULLIF(st.hh20,0) AS close_hh20_ratio,
    (st.close/NULLIF(st.close_5d_ago,0)-1)*100 AS ret_5d,
    st.ma5, st.ma20, st.ma60,
    coalesce(ld.n_leader_concepts,0) AS n_leader_concepts
  FROM st LEFT JOIN lead ld ON st.d=ld.d AND st.code=ld.code
),
flag AS (
  SELECT *, CAST(({C6COND}) AS INT) AS c6,
            CAST(({C6COND} AND n_leader_concepts >= {THR['n_leader_concepts']}) AS INT) AS c7
  FROM feat
),
run6 AS (SELECT *, di - row_number() OVER (PARTITION BY code ORDER BY di) AS grp FROM flag WHERE c6=1),
st6 AS (SELECT *, row_number() OVER (PARTITION BY code,grp ORDER BY di) AS s6 FROM run6),
run7 AS (SELECT *, di - row_number() OVER (PARTITION BY code ORDER BY di) AS grp FROM flag WHERE c7=1),
st7 AS (SELECT *, row_number() OVER (PARTITION BY code,grp ORDER BY di) AS s7 FROM run7),
concepts AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code,
         string_agg(DISTINCT t.x, ';' ORDER BY t.x) AS cfs,
         count(DISTINCT t.x) AS n_cfs
  FROM {CG}, unnest(string_split(concepts,';')) AS t(x)
  GROUP BY substr(CAST(trade_date AS VARCHAR),1,10), code
),
fwd AS (
  SELECT d, di, code,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5  FOLLOWING) AS hi5,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS hi10,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5  FOLLOWING) AS n5,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS n10
  FROM base
),
pool AS (
  SELECT s6.trade_date, s6.code, s6.name, s6.close, s6.pct_change, s6.turnover_rate,
    s6.vol20, s6.ret_5d, s6.lu_cnt_20d, s6.main_net_norm, s6.n_leader_concepts,
    s6.lu_gap, s6.close_hh20_ratio, s6.ma5, s6.ma20, s6.ma60,
    CASE WHEN s7.code IS NOT NULL THEN 'C7' ELSE 'C6' END AS source,
    CASE WHEN s7.code IS NOT NULL THEN s7.s7 ELSE s6.s6 END AS streak_days,
    coalesce(c.cfs,'') AS matched_concepts, coalesce(c.n_cfs,0) AS n_concepts,
    CASE WHEN fw.n5=5  THEN (fw.hi5 /NULLIF(s6.close,0)-1)*100 END AS fwd_max_5d,
    CASE WHEN fw.n10=10 THEN (fw.hi10/NULLIF(s6.close,0)-1)*100 END AS fwd_max_10d,
    ((s6.vol20-{Z['vol_m']})/{Z['vol_s']}) + ((s6.ret_5d-{Z['ret_m']})/{Z['ret_s']})
      + ((s6.turnover_rate-{Z['tor_m']})/{Z['tor_s']}) AS c7_score
  FROM st6 s6
  LEFT JOIN st7 s7 ON s6.trade_date=s7.trade_date AND s6.code=s7.code
  LEFT JOIN concepts c ON c.d=s6.trade_date AND c.code=s6.code
  LEFT JOIN fwd fw ON fw.d=s6.trade_date AND fw.di=s6.di AND fw.code=s6.code
  WHERE s6.c6=1
)
SELECT * FROM pool ORDER BY trade_date, c7_score DESC
"""
if __name__ == "__main__":
    con = duckdb.connect(); con.execute("SET threads=8")
    con.execute(f"SET temp_directory='{(WS/'_duckdb_tmp').as_posix()}'")
    t0 = time.time()
    df = con.execute(SQL).df()
    print(f"FULL_COMPUTE seconds={time.time()-t0:.1f} rows={len(df)} days={df.trade_date.nunique()}")
    print("date_range", df.trade_date.min(), df.trade_date.max())
    print("source counts", df.source.value_counts().to_dict())
    # 近14交易日 C6 补充
    recent = sorted(df.trade_date.unique())[-14:]
    r = df[df.trade_date.isin(recent)].groupby(['trade_date','source']).size().unstack(fill_value=0)
    for d in recent:
        c7 = r.loc[d].get('C7',0) if d in r.index else 0
        c6 = r.loc[d].get('C6',0) if d in r.index else 0
        print(f"  {d}: C7={c7} C6补充={c6} 合计={c7+c6}")
    # 与 c7_picks._compute 逐股对比（C7 子集）
    from queries import c7_picks
    for d in recent[:3] + [sorted(df.trade_date.unique())[200], sorted(df.trade_date.unique())[400]]:
        live = c7_picks._compute(d)
        live_codes = set(x['code'] for x in live)
        pre_c7 = set(df[(df.trade_date==d)&(df.source=='C7')].code)
        inter = live_codes & pre_c7
        print(f"VERIFY {d}: live_n={len(live_codes)} preC7_n={len(pre_c7)} inter={len(inter)} "
              f"only_live={len(live_codes-pre_c7)} only_pre={len(pre_c7-live_codes)}")
    df.to_parquet((WS/'_prebuild_verify.parquet').as_posix(), index=False)
    print("SAVED _prebuild_verify.parquet")

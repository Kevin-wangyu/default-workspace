# -*- coding: utf-8 -*-
"""C7 优化 A/B：原版(_compute) vs 优化版(仅取目标日前120天算窗口)，
验证①结果完全一致 ②耗时下降。纯读，不改任何项目文件。"""
import sys, time
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
import duckdb
from config import COMPACT_DIR
from queries import c7_picks as C

DATES = ["2026-10-30", "2026-05-08", "2024-09-27", "2024-03-15"]
QG=C._QG; DG=C._DG; CG=C._CG; BARS=C._BARS; META=C._META; THR=C.THR; z=C.ZREF
COND=C._c7_cond()


def compute_fast(trade_date, lookback=125):
    con=duckdb.connect(); con.execute("SET threads=8")
    try:
        # 先定目标日 di
        tdi=con.execute(f"""WITH d AS (SELECT DISTINCT substr(CAST(trade_date AS VARCHAR),1,10) d FROM {QG}),
          x AS (SELECT d,row_number() OVER(ORDER BY d) di FROM d)
          SELECT di FROM x WHERE d=substr(?,1,10)""",[trade_date]).fetchone()[0]
        lo=max(1, tdi-lookback)
        sql=f"""
        WITH
        qx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,name,close,high,amount,
                 turnover_rate,pct_change,huge_order_net,big_order_net
               FROM {QG} WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN
                 (SELECT d FROM (SELECT DISTINCT substr(CAST(trade_date AS VARCHAR),1,10) d FROM {QG})
                  ORDER BY d LIMIT {lookback} OFFSET {lo}) ),
        dx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,
                 CASE WHEN isfinite(pct_change) THEN pct_change END pct_change
               FROM {DG}),
        cal AS (SELECT d,row_number() OVER(ORDER BY d) di FROM
                 (SELECT DISTINCT d FROM qx)),
        base AS (SELECT q.*,c.di,d.pct_change daily_pct,
                 CASE WHEN left(q.code,2) IN ('30','68') THEN 19.8
                      WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8
                      ELSE 9.8 END lu_thr
                 FROM qx q JOIN cal c USING(d)
                 LEFT JOIN dx d ON q.d=d.d AND q.code=d.code),
        st AS (SELECT b.*,avg(close) OVER w5 ma5,avg(close) OVER w20 ma20,avg(close) OVER w60 ma60,
                 stddev_samp(daily_pct) OVER w20 vol20,max(high) OVER w20 hh20,
                 lag(close,5) OVER wc close_5d_ago,
                 sum(CASE WHEN daily_pct>=lu_thr-0.15 AND daily_pct IS NOT NULL THEN 1 ELSE 0 END) OVER w20 lu_cnt_20d
               FROM base b
               WINDOW wc AS(PARTITION BY code ORDER BY di),
                 w5 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
                 w20 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
                 w60 AS(PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)),
        cdx AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,trim(t.x) cname
                FROM {CG},unnest(string_split(concepts,';')) t(x)
                WHERE substr(CAST(trade_date AS VARCHAR),1,10) IN (SELECT d FROM cal)),
        sc AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,concept_name cname,max(score) score
               FROM {META} WHERE row_type='score' GROUP BY 1,2),
        lead AS (SELECT x.d,x.code,count(DISTINCT x.cname) FILTER(WHERE s.score>=0.8) n_leader_concepts
                 FROM cdx x LEFT JOIN sc s ON x.d=s.d AND x.cname=s.cname GROUP BY x.d,x.code),
        feat AS (SELECT st.d trade_date,st.di,st.code,st.name,st.daily_pct pct_change,st.close,st.amount,
                   st.lu_cnt_20d,(coalesce(st.huge_order_net,0)+coalesce(st.big_order_net,0))/NULLIF(st.amount,0) main_net_norm,
                   st.vol20,st.turnover_rate,st.daily_pct-st.lu_thr lu_gap,
                   st.close/NULLIF(st.hh20,0) close_hh20_ratio,
                   (st.close/NULLIF(st.close_5d_ago,0)-1)*100 ret_5d,
                   st.ma5,st.ma20,st.ma60,coalesce(ld.n_leader_concepts,0) n_leader_concepts
                 FROM st LEFT JOIN lead ld ON st.d=ld.d AND st.code=ld.code),
        flag AS (SELECT *,CAST(({COND}) AS INT) c7 FROM feat),
        run AS (SELECT *,di-row_number() OVER(PARTITION BY code ORDER BY di) grp FROM flag WHERE c7=1),
        streak AS (SELECT *,row_number() OVER(PARTITION BY code,grp ORDER BY di) streak_days FROM run),
        concepts AS (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,
                       string_agg(DISTINCT t.x,';' ORDER BY t.x) cfs,count(DISTINCT t.x) n_cfs
                     FROM {CG},unnest(string_split(concepts,';')) t(x)
                     WHERE substr(CAST(trade_date AS VARCHAR),1,10)=substr(?,1,10)
                     GROUP BY 1,2)
        SELECT s.code,s.streak_days,
          ((s.vol20-{z['vol_m']})/{z['vol_s']})+((s.ret_5d-{z['ret_m']})/{z['ret_s']})+
          ((s.turnover_rate-{z['tor_m']})/{z['tor_s']}) c7_score
        FROM streak s LEFT JOIN concepts c ON c.d=s.trade_date AND c.code=s.code
        WHERE s.trade_date=substr(?,1,10) ORDER BY c7_score DESC
        """
        df=con.execute(sql,[trade_date,trade_date]).df()
        return [(str(r.code),int(r.streak_days),round(float(r.c7_score),4)) for r in df.itertuples(index=False)]
    finally:
        con.close()


print("=== C7 原版 vs 优化版 A/B（结果一致性 + 耗时）===")
for d in DATES:
    t=time.perf_counter(); orig=C._compute(d); t_orig=(time.perf_counter()-t)*1000
    t=time.perf_counter(); fast=compute_fast(d); t_fast=(time.perf_counter()-t)*1000
    o_keys=sorted([(p["code"],p["streak_days"],p["c7_score"]) for p in orig])
    f_keys=sorted(fast)
    same = o_keys==f_keys
    print(f"[{d}] 原版={t_orig:.0f}ms 优化={t_fast:.0f}ms 加速={t_orig/max(t_fast,1):.2f}x "
          f"n={len(orig)}/{len(fast)} 结果一致={same}")
    if not same:
        print(f"   原仅有: {set(o_keys)-set(f_keys)}")
        print(f"   优仅有: {set(f_keys)-set(o_keys)}")
print("\n=== 稳定日 lru_cache 命中精确测（2024-09-27）===")
C.clear_cache()
d="2024-09-27"
t=time.perf_counter(); C.get_c7_picks(d); print(f"  第1次(fresh)={(time.perf_counter()-t)*1000:.0f}ms")
t=time.perf_counter(); C.get_c7_picks(d); print(f"  第2次(cache)={(time.perf_counter()-t)*1000:.0f}ms")
print("\nAB_DONE")

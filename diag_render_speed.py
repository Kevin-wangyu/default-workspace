# -*- coding: utf-8 -*-
"""concept 页面三端点耗时分解（纯读）。定位慢在哪一步。"""
import sys, time
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")

import duckdb
from config import COMPACT_DIR
from queries import c7_picks

DATES = ["2026-10-30", "2026-05-08", "2024-09-27"]
QG = f"read_parquet('{(COMPACT_DIR/'quote'/'*.parquet').as_posix()}', union_by_name=true)"
DG = f"read_parquet('{(COMPACT_DIR/'daily_pct'/'*.parquet').as_posix()}', union_by_name=true)"
CG = f"read_parquet('{(COMPACT_DIR/'concept_date'/'*.parquet').as_posix()}', union_by_name=true)"


def timing(label, fn):
    t = time.perf_counter()
    r = fn()
    dt = time.perf_counter() - t
    print(f"  {label}: {dt*1000:.0f} ms")
    return r, dt


# ── 1. 三端点整体耗时（从项目根运行）──
import queries as Q
print("=== 端点整体耗时 ===")
for d in DATES:
    print(f"\n[{d}]")
    try:
        _, t1 = timing("get_concept_date_top10", lambda: Q.get_concept_date_top10(d))
    except Exception as e:
        print(f"  date_top10 ERROR {e}")
    try:
        _, t2 = timing("get_limit_up_ladder", lambda: Q.get_limit_up_ladder(d, 2))
    except Exception as e:
        print(f"  ladder ERROR {e}")
    c7_picks.clear_cache()
    r3, t3 = timing("c7_picks FRESH(_compute)", lambda: c7_picks._compute(d))
    # 第二次（缓存）
    t = time.perf_counter(); c7_picks.get_c7_picks(d); c7_picks.get_c7_picks(d)
    tl2 = (time.perf_counter()-t)/2*1000
    print(f"  c7_picks 稳定缓存命中(估): {tl2:.0f} ms  (FRESH n={len(r3)})")

# ── 2. C7 _compute 内部各步骤拆解 ──
print("\n\n=== C7 _compute 内部步骤拆解（2026-10-30）===")
d = "2026-10-30"
con = duckdb.connect(); con.execute("SET threads=8")
steps = [
    ("A 扫quote全量建base",
     f"SELECT count(*) FROM (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,close,high,amount,turnover_rate,pct_change,huge_order_net,big_order_net FROM {QG})"),
    ("B 窗口特征(ma/vol/lu_cnt)全量",
     f"""SELECT count(*) FROM (
       SELECT code, avg(close) OVER w20 ma20, stddev_samp(pct_change) OVER w20 vol20
       FROM (SELECT substr(CAST(trade_date AS VARCHAR),1,10) d,code,close,pct_change FROM {QG})
       WINDOW w20 AS (PARTITION BY code ORDER BY d ROWS BETWEEN 19 PRECEDING AND CURRENT ROW))"""),
    ("C 扫concept_date全量+unnest",
     f"SELECT count(*) FROM (SELECT code, unnest(string_split(concepts,';')) x FROM {CG})"),
    ("D 仅目标日前60交易日quote",
     f"""WITH d AS (SELECT DISTINCT substr(CAST(trade_date AS VARCHAR),1,10) d FROM {QG}),
       rc AS (SELECT d,row_number() OVER(ORDER BY d) di FROM d),
       tgt AS (SELECT di FROM rc WHERE d=substr('{d}',1,10))
       SELECT count(*) FROM (SELECT q.* FROM {QG} q, tgt WHERE substr(CAST(q.trade_date AS VARCHAR),1,10) IN (SELECT d FROM rc WHERE di BETWEEN tgt.di-59 AND tgt.di))"""),
    ("E 仅目标日concept_date",
     f"SELECT count(*) FROM {CG} WHERE substr(CAST(trade_date AS VARCHAR),1,10)=substr('{d}',1,10)"),
]
for label, sql in steps:
    try:
        _, _ = timing(label, lambda s=sql: con.execute(s).fetchone())
    except Exception as e:
        print(f"  {label} ERROR {e}")
con.close()
print("\nDIAG_DONE")

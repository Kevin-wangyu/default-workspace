# -*- coding: utf-8 -*-
"""
构造全市场稠密特征矩阵（零写入投研项目）。
候选池 = 全市场所有股票，不是概念交集池（用户 m00151 明确）。
所有筛选特征在 T 日收盘后可知；fwd_* 仅作标签/验收，绝不参与筛选。
输出：matrix.parquet + matrix_profile.json（均在工作目录）。
"""
from __future__ import annotations
import json, time, sys
from pathlib import Path
import duckdb, pandas as pd

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
MAT = (WS / "matrix.parquet").as_posix()
TMP = (WS / "_duckdb_tmp").as_posix()
Path(TMP).mkdir(exist_ok=True)

QG = f"read_parquet('{P('data_compact','quote','*.parquet')}', union_by_name=true)"
DG = f"read_parquet('{P('data_compact','daily_pct','*.parquet')}', union_by_name=true)"
CG = f"read_parquet('{P('data_compact','concept_date','*.parquet')}', union_by_name=true)"
BARS = f"read_parquet('{P('data','_tops_cache','v1','bars.parquet')}')"
META = f"read_parquet('{P('data','_tops_cache','v1','meta.parquet')}')"
MKTAMT = f"read_parquet('{P('data','market_amount.parquet')}')"

con = duckdb.connect()
con.execute(f"SET temp_directory='{TMP}'")
con.execute("SET threads=8")

SQL = f"""
WITH
-- 统一日期字符串（兼容 'YYYY-MM-DD' 与 hive 分区 timestamp）
qx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d,
         code, name, industry, open, high, low, close, volume, amount,
         turnover_rate,
         scrplus_90, scrplus_70,
         huge_order_net, big_order_net, medium_order_net, small_order_net
  FROM {QG}
),
dx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code,
         CASE WHEN isfinite(pct_change) THEN pct_change END AS pct_change
  FROM {DG}
),
-- 全局交易日序号（以实际有行情的交易日为准）
cal AS (
  SELECT d, row_number() OVER (ORDER BY d) AS di
  FROM (SELECT DISTINCT d FROM qx)
),
base AS (
  SELECT q.*, c.di, d.pct_change,
    CASE
      WHEN left(q.code,2) IN ('30','68') THEN 19.8
      WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8
      ELSE 9.8 END AS lu_thr
  FROM qx q
  JOIN cal c USING (d)
  LEFT JOIN dx d ON q.d=d.d AND q.code=d.code
),
-- 全市场逐日状态（当日可知）
day0 AS (
  SELECT d, di,
    count(*) AS mkt_n,
    count(*) FILTER (WHERE pct_change > 0) AS mkt_up,
    count(*) FILTER (WHERE pct_change >= lu_thr - 0.15 AND pct_change IS NOT NULL) AS mkt_lu,
    avg(pct_change) AS mkt_pct_mean,
    sum(amount) AS mkt_amount_calc
  FROM base GROUP BY d, di
),
-- 官方市场总额
ma0 AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, total_amount AS mkt_amount
  FROM {MKTAMT}
),
day1 AS (
  SELECT a.*, b.mkt_amount,
    a.mkt_amount_calc,
    a.mkt_up::DOUBLE / NULLIF(a.mkt_n,0) AS mkt_up_ratio
  FROM day0 a LEFT JOIN ma0 b USING (d)
),
-- 市场状态滚动量（全部只用 di <= 当前 的数据）
mkt AS (
  SELECT *,
    avg(mkt_amount)   OVER (ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW) AS mkt_amt_ma5,
    avg(mkt_amount)   OVER (ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS mkt_amt_ma20,
    avg(mkt_lu)       OVER (ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW) AS mkt_lu_ma5,
    avg(mkt_pct_mean) OVER (ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW) AS mkt_pct_ma5,
    sum(mkt_pct_mean) OVER (ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW) AS mkt_ret_5d,
    sum(mkt_pct_mean) OVER (ORDER BY di ROWS BETWEEN 9  PRECEDING AND CURRENT ROW) AS mkt_ret_10d,
    sum(mkt_pct_mean) OVER (ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS mkt_ret_20d
  FROM day1
),
mkt2 AS (
  SELECT *, mkt_amount / NULLIF(mkt_amt_ma20,0) AS mkt_amt_ratio
  FROM mkt
),
-- 个股窗口特征（只用 T 及之前，天然可知）
stock AS (
  SELECT b.*,
    avg(close) OVER w5  AS ma5,
    avg(close) OVER w10 AS ma10,
    avg(close) OVER w20 AS ma20,
    avg(close) OVER w60 AS ma60,
    stddev_samp(pct_change) OVER w20 AS vol20,
    max(high)   OVER w20 AS hh20,
    avg(turnover_rate) OVER w5  AS tor_ma5,
    avg(amount)        OVER w20 AS amt_ma20,
    sum(coalesce(huge_order_net,0)+coalesce(big_order_net,0)) OVER w5 AS main_net5,
    sum(CASE WHEN pct_change >= lu_thr-0.15 AND pct_change IS NOT NULL THEN 1 ELSE 0 END) OVER w10 AS lu_cnt_10d,
    sum(CASE WHEN pct_change >= lu_thr-0.15 AND pct_change IS NOT NULL THEN 1 ELSE 0 END) OVER w20 AS lu_cnt_20d,
    lag(close,5)  OVER wc AS close_5d_ago,
    lag(close,10) OVER wc AS close_10d_ago,
    lag(close,20) OVER wc AS close_20d_ago,
    lag(di,20)    OVER wc AS di_20d_ago
  FROM base b
  WINDOW
    wc  AS (PARTITION BY code ORDER BY di),
    w5  AS (PARTITION BY code ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW),
    w10 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 9  PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
),
-- 标签：未来 5 / 10 个交易日内 high 最大值相对 close_T（RANGE 按全局交易日序号，复刻 _build_forward_map）
lab AS (
  SELECT s.*,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5  FOLLOWING) AS fwd_hi5,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 5  FOLLOWING) AS fwd_n5,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS fwd_hi10,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING) AS fwd_n10
  FROM stock s
),
-- 当日全市场 base rate（含未来数据，仅作报告对照，禁止作筛选条件）
dayhit AS (
  SELECT d, di,
    avg(CASE WHEN fwd_n5=5  THEN (CASE WHEN (fwd_hi5 /close-1)*100 >= 20 THEN 1.0 ELSE 0.0 END) END) AS mkt_hit5,
    avg(CASE WHEN fwd_n10=10 THEN (CASE WHEN (fwd_hi10/close-1)*100 >= 20 THEN 1.0 ELSE 0.0 END) END) AS mkt_hit10
  FROM lab GROUP BY d, di
),
-- 赚钱效应滞后版：起点 s 的 10 日窗口覆盖 [s+1,s+10]，T 日可知要求 s+10 <= T-1，故只取 di-30..di-11
effect AS (
  SELECT d, di,
    avg(mkt_hit10) OVER (ORDER BY di ROWS BETWEEN 30 PRECEDING AND 11 PRECEDING) AS eff_hit10_lag,
    avg(mkt_hit10) OVER (ORDER BY di ROWS BETWEEN 20 PRECEDING AND 11 PRECEDING) AS eff_hit10_lag_s,
    avg(mkt_hit5)  OVER (ORDER BY di ROWS BETWEEN 30 PRECEDING AND 11 PRECEDING) AS eff_hit5_lag
  FROM dayhit
),
-- 概念聚集度（当日可知）：概念数 + 命中当日三榜热概念数/最高分/龙头概念数
cd AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code,
         length(concepts) - length(replace(concepts,';','')) + 1 AS n_concepts
  FROM {CG}
),
cdx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, trim(t.x) AS cname
  FROM {CG}, unnest(string_split(concepts,';')) AS t(x)
),
hot AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, name AS cname,
         max(CASE WHEN is_strong THEN 1 ELSE 0 END) AS is_strong
  FROM {BARS} GROUP BY 1,2
),
scores AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, concept_name AS cname,
         max(score) AS score
  FROM {META} WHERE row_type='score' GROUP BY 1,2
),
hotstock AS (
  SELECT x.d, x.code,
    count(DISTINCT x.cname) FILTER (WHERE h.cname IS NOT NULL) AS n_hot_concepts,
    max(s.score) AS max_concept_score,
    count(DISTINCT x.cname) FILTER (WHERE s.score >= 0.8) AS n_leader_concepts,
    max(coalesce(h.is_strong,0)) AS in_strong_concept
  FROM cdx x
  LEFT JOIN hot h    ON x.d=h.d AND x.cname=h.cname
  LEFT JOIN scores s ON x.d=s.d AND x.cname=s.cname
  GROUP BY x.d, x.code
),
-- 汇总
fin AS (
  SELECT
    l.d AS trade_date, l.di, l.code, l.name, l.industry,
    CASE WHEN left(l.code,2) IN ('30','68') THEN 'cy_kc'
         WHEN left(l.code,1) IN ('8','4') OR left(l.code,2)='92' THEN 'bj'
         ELSE 'main' END AS board,
    l.open, l.high, l.low, l.close, l.volume, l.amount, l.turnover_rate, l.pct_change, l.lu_thr,
    l.huge_order_net, l.big_order_net, l.medium_order_net, l.small_order_net,
    coalesce(l.huge_order_net,0)+coalesce(l.big_order_net,0) AS main_net,
    (coalesce(l.huge_order_net,0)+coalesce(l.big_order_net,0)) / NULLIF(l.amount,0) AS main_net_norm,
    coalesce(l.huge_order_net,0) / NULLIF(l.amount,0) AS huge_norm,
    coalesce(l.small_order_net,0) / NULLIF(l.amount,0) AS small_norm,
    l.scrplus_90, l.scrplus_70,
    coalesce(c.n_concepts,0) AS n_concepts,
    coalesce(hs.n_hot_concepts,0) AS n_hot_concepts,
    hs.max_concept_score,
    coalesce(hs.n_leader_concepts,0) AS n_leader_concepts,
    coalesce(hs.in_strong_concept,0) AS in_strong_concept,
    l.ma5, l.ma10, l.ma20, l.ma60,
    l.close/NULLIF(l.ma5,0)-1  AS bias5,
    l.close/NULLIF(l.ma20,0)-1 AS bias20,
    CASE WHEN l.ma5>l.ma20 THEN 1 ELSE 0 END AS ma5_gt_ma20,
    CASE WHEN l.ma20>l.ma60 THEN 1 ELSE 0 END AS ma20_gt_ma60,
    l.close/NULLIF(l.hh20,0) AS close_hh20_ratio,
    l.vol20,
    (l.close/NULLIF(l.close_5d_ago,0)-1)*100  AS ret_5d,
    (l.close/NULLIF(l.close_10d_ago,0)-1)*100 AS ret_10d,
    (l.close/NULLIF(l.close_20d_ago,0)-1)*100 AS ret_20d,
    l.lu_cnt_10d, l.lu_cnt_20d,
    l.tor_ma5, l.turnover_rate/NULLIF(l.tor_ma5,0) AS tor_ratio,
    l.amt_ma20, l.amount/NULLIF(l.amt_ma20,0) AS amt_ratio,
    l.main_net5,
    CASE WHEN l.pct_change >= l.lu_thr-0.15 THEN 1 ELSE 0 END AS is_limit_up,
    l.pct_change - l.lu_thr AS lu_gap,
    m.mkt_amount, m.mkt_amount_calc, m.mkt_n, m.mkt_up_ratio, m.mkt_lu, m.mkt_pct_mean,
    m.mkt_amt_ma5, m.mkt_amt_ma20, m.mkt_amt_ratio,
    m.mkt_lu_ma5, m.mkt_pct_ma5, m.mkt_ret_5d, m.mkt_ret_10d, m.mkt_ret_20d,
    dh.mkt_hit5, dh.mkt_hit10,
    e.eff_hit10_lag, e.eff_hit10_lag_s, e.eff_hit5_lag,
    CASE WHEN l.fwd_n5=5  THEN (l.fwd_hi5 /l.close-1)*100 END AS fwd_max_5d,
    CASE WHEN l.fwd_n10=10 THEN (l.fwd_hi10/l.close-1)*100 END AS fwd_max_10d,
    l.fwd_n5, l.fwd_n10,
    CASE WHEN l.fwd_n5=5  THEN CASE WHEN (l.fwd_hi5 /l.close-1)*100 >= 20 THEN 1 ELSE 0 END END AS y5,
    CASE WHEN l.fwd_n10=10 THEN CASE WHEN (l.fwd_hi10/l.close-1)*100 >= 20 THEN 1 ELSE 0 END END AS y10,
    CASE WHEN l.d <= '2025-12-31' THEN 'train'
         WHEN l.d <= '2026-10-31' THEN 'oos'
         ELSE 'tail' END AS split
  FROM lab l
  LEFT JOIN mkt2 m   ON l.di=m.di
  LEFT JOIN dayhit dh ON l.di=dh.di
  LEFT JOIN effect e ON l.di=e.di
  LEFT JOIN cd c     ON l.d=c.d AND l.code=c.code
  LEFT JOIN hotstock hs ON l.d=hs.d AND l.code=hs.code
)
SELECT * FROM fin ORDER BY di, code
"""

t0 = time.time()
print("building matrix ...", flush=True)
con.execute(f"COPY ({SQL}) TO '{MAT}' (FORMAT PARQUET, COMPRESSION ZSTD)")
print(f"written in {time.time()-t0:.1f}s -> {MAT}", flush=True)

# ---- profile ----
prof = {}
prof["path"] = MAT
prof["build_seconds"] = round(time.time() - t0, 1)
n = con.execute(f"SELECT count(*) FROM read_parquet('{MAT}')").fetchone()[0]
prof["n_rows"] = int(n)
prof["n_days"] = int(con.execute(f"SELECT count(DISTINCT trade_date) FROM read_parquet('{MAT}')").fetchone()[0])
prof["n_codes"] = int(con.execute(f"SELECT count(DISTINCT code) FROM read_parquet('{MAT}')").fetchone()[0])
prof["d0"], prof["d1"] = con.execute(f"SELECT min(trade_date), max(trade_date) FROM read_parquet('{MAT}')").fetchone()

cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{MAT}')").fetchall()]
null_expr = ", ".join([f'count(*) FILTER (WHERE "{c}" IS NULL) AS "{c}"' for c in cols])
nulls = con.execute(f"SELECT {null_expr} FROM read_parquet('{MAT}')").df().iloc[0].to_dict()
prof["null_rate"] = {c: round(float(v) / n, 5) for c, v in nulls.items()}

prof["split_counts"] = con.execute(f"""SELECT split, count(*) AS n,
  count(DISTINCT trade_date) AS nd,
  round(avg(y5),4) AS hit5, round(avg(y10),4) AS hit10
FROM read_parquet('{MAT}') GROUP BY split ORDER BY split""").df().to_dict("records")

prof["label_consistency"] = con.execute(f"""
WITH mine AS (
  SELECT code, fwd_max_10d FROM read_parquet('{MAT}') WHERE trade_date='2024-09-30'
), cached AS (
  SELECT code, CAST(fwd_max_10d AS DOUBLE) AS cf
  FROM read_parquet('{P('data','concept_picks','trade_date=2024-09-30','part.parquet')}')
  WHERE fwd_max_10d IS NOT NULL
)
SELECT count(*) AS n, max(abs(m.fwd_max_10d - c.cf)) AS max_abs_diff
FROM mine m JOIN cached c USING (code)
""").df().to_dict("records")

prof["y_monotone"] = con.execute(f"""SELECT
  count(*) FILTER (WHERE y5 IS NOT NULL AND y10 IS NOT NULL AND y5=1 AND y10=0) AS n_y5_not_y10,
  count(*) FILTER (WHERE y5 IS NOT NULL AND y10 IS NOT NULL) AS n_both
FROM read_parquet('{MAT}')""").df().to_dict("records")

prof["day_hit_dist"] = con.execute(f"""SELECT
  count(*) AS nd,
  count(*) FILTER (WHERE mkt_hit10 >= 0.75) AS nd_ge75,
  count(*) FILTER (WHERE mkt_hit10 >= 0.50 AND mkt_hit10 < 0.75) AS nd_50_75,
  count(*) FILTER (WHERE mkt_hit10 >= 0.25 AND mkt_hit10 < 0.50) AS nd_25_50,
  round(avg(mkt_hit10),4) AS mean_hit10, round(avg(mkt_hit5),4) AS mean_hit5
FROM (SELECT DISTINCT trade_date, mkt_hit10, mkt_hit5 FROM read_parquet('{MAT}') WHERE mkt_hit10 IS NOT NULL)""").df().to_dict("records")

(WS / "matrix_profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("rows", prof["n_rows"], "days", prof["n_days"], "codes", prof["n_codes"], prof["d0"], prof["d1"])
print("split", json.dumps(prof["split_counts"], ensure_ascii=False))
print("label_consistency", json.dumps(prof["label_consistency"], ensure_ascii=False))
print("y_monotone", json.dumps(prof["y_monotone"], ensure_ascii=False))
print("day_hit_dist", json.dumps(prof["day_hit_dist"], ensure_ascii=False))
print("null_rate top:", json.dumps(sorted(prof["null_rate"].items(), key=lambda x: -x[1])[:14], ensure_ascii=False))
print("DONE")

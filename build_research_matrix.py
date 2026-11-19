# -*- coding: utf-8 -*-
"""构造增量归因研究矩阵（零写入投研项目）。

在 matrix.parquet 基础上追加：
 (1) 概念"主线延续"特征（从 bars.parquet 历史强榜构造，T 日可知）
     - strong_today: 个股所属概念当日是否为强概念
     - n_strong_today: 当日强概念数
     - n_mainline_not_onlist: 主线未结束但退出榜单的概念数（过去10日强榜>=3 且今日不在榜）
     - max_strong_hist10: 所属概念过去10日最大强榜天数
 (2) 1-2 日放宽标签：y7 = 窗口 T+1..T+7（5日+2），y12 = T+1..T+12（10日+2）
     baseline 价仍为 close_T（触发日），仅观察窗口放宽，无前视。
 (3) 保留 matrix 全部当日可知因子与 y5/y10。

输出 research_matrix.parquet（仅工作目录）。
"""
from __future__ import annotations
import time, json
from pathlib import Path
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
P = lambda *p: str(Path(PROJ, *p)).replace("\\", "/")
MAT = (WS / "matrix.parquet").as_posix()
OUT = (WS / "research_matrix.parquet").as_posix()
TMP = (WS / "_duckdb_tmp2").as_posix()
Path(TMP).mkdir(exist_ok=True)

_bar_cands = [
    Path(PROJ, "data_compact", "_tops_cache", "v1", "bars.parquet"),
    Path(PROJ, "data", "_tops_cache", "v1", "bars.parquet"),
    Path(PROJ, "data_compact_sync", "_tops_cache", "v1", "bars.parquet"),
]
_bar = next((x for x in _bar_cands if x.exists()), None)
assert _bar is not None, "bars.parquet not found"
BARS = f"read_parquet('{str(_bar).replace(chr(92), '/')}')"
CG = f"read_parquet('{P('data_compact','concept_date','*.parquet')}', union_by_name=true)"

con = duckdb.connect()
con.execute(f"SET temp_directory='{TMP}'")
con.execute("SET threads=8")

SQL = f"""
WITH
-- 概念强榜日面板
bars_day AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, name AS cname,
         max(CASE WHEN is_strong THEN 1 ELSE 0 END) AS strong_today
  FROM {BARS} GROUP BY 1,2
),
cal AS (SELECT d, row_number() OVER (ORDER BY d) AS di FROM (SELECT DISTINCT d FROM bars_day)),
-- 概念历史强榜天数（只用 <= 当前日，RANGE 按日序号）
concept_hist AS (
  SELECT b.d, b.cname, b.strong_today,
    coalesce(sum(b.strong_today) OVER (
      PARTITION BY b.cname ORDER BY c.di
      RANGE BETWEEN 10 PRECEDING AND 1 PRECEDING),0) AS strong_hist_10d,
    coalesce(sum(b.strong_today) OVER (
      PARTITION BY b.cname ORDER BY c.di
      RANGE BETWEEN 20 PRECEDING AND 1 PRECEDING),0) AS strong_hist_20d
  FROM bars_day b JOIN cal c USING(d)
),
-- 个股当日所属概念（拆解分号串）
cdx AS (
  SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, trim(t.x) AS cname
  FROM {CG}, unnest(string_split(concepts,';')) AS t(x)
),
-- 聚合到个股：主线延续特征
sc AS (
  SELECT x.d, x.code,
    count(DISTINCT x.cname) FILTER (WHERE coalesce(h.strong_today,0)=1) AS n_strong_today,
    count(DISTINCT x.cname) FILTER (WHERE h.strong_hist_10d>=3) AS n_concept_strong_hist,
    count(DISTINCT x.cname) FILTER (WHERE h.strong_hist_10d>=3 AND coalesce(h.strong_today,0)=0) AS n_mainline_not_onlist,
    coalesce(max(h.strong_hist_10d),0) AS max_strong_hist10,
    count(DISTINCT x.cname) FILTER (WHERE h.strong_hist_20d>=5) AS n_concept_hot20
  FROM cdx x
  LEFT JOIN concept_hist h ON x.d=h.d AND x.cname=h.cname
  GROUP BY x.d, x.code
),
-- 扩展窗口标签（T+1..T+7 / T+1..T+12，baseline=close_T）
labx AS (
  SELECT *,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 7  FOLLOWING) AS fwd_hi7,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 7  FOLLOWING) AS fwd_n7,
    max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 12 FOLLOWING) AS fwd_hi12,
    count(*)  OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND 12 FOLLOWING) AS fwd_n12
  FROM read_parquet('{MAT}')
),
fin AS (
  SELECT m.*,
    coalesce(s.n_strong_today,0) AS n_strong_today,
    coalesce(s.n_concept_strong_hist,0) AS n_concept_strong_hist,
    coalesce(s.n_mainline_not_onlist,0) AS n_mainline_not_onlist,
    coalesce(s.max_strong_hist10,0) AS max_strong_hist10,
    coalesce(s.n_concept_hot20,0) AS n_concept_hot20,
    CASE WHEN l.fwd_n7=7  THEN CASE WHEN (l.fwd_hi7 /m.close-1)*100>=20 THEN 1 ELSE 0 END END AS y7,
    CASE WHEN l.fwd_n12=12 THEN CASE WHEN (l.fwd_hi12/m.close-1)*100>=20 THEN 1 ELSE 0 END END AS y12,
    CASE WHEN l.fwd_n7=7  THEN (l.fwd_hi7 /m.close-1)*100 END AS fwd_max_7d,
    CASE WHEN l.fwd_n12=12 THEN (l.fwd_hi12/m.close-1)*100 END AS fwd_max_12d
  FROM read_parquet('{MAT}') m
  LEFT JOIN sc s ON m.trade_date=s.d AND m.code=s.code
  LEFT JOIN labx l ON m.trade_date=l.trade_date AND m.code=l.code AND m.di=l.di
)
SELECT * FROM fin ORDER BY di, code
"""

t0 = time.time()
print("building research matrix ...", flush=True)
con.execute(f"COPY ({SQL}) TO '{OUT}' (FORMAT PARQUET, COMPRESSION ZSTD)")
print(f"written in {time.time()-t0:.1f}s -> {OUT}", flush=True)

n = con.execute(f"SELECT count(*) FROM read_parquet('{OUT}')").fetchone()[0]
cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{OUT}')").fetchall()]
print("rows", n, "cols", len(cols), flush=True)

prof = {
    "path": OUT, "n_rows": int(n), "n_cols": len(cols), "build_seconds": round(time.time()-t0,1),
    "new_cols": [c for c in cols if c in ("n_strong_today","n_concept_strong_hist","n_mainline_not_onlist",
                                          "max_strong_hist10","n_concept_hot20","y7","y12","fwd_max_7d","fwd_max_12d")],
}
prof["by_split"] = con.execute(f"""
  SELECT split, count(*) AS n,
    round(avg(y5),4) AS hit5, round(avg(y7),4) AS hit7,
    round(avg(y10),4) AS hit10, round(avg(y12),4) AS hit12
  FROM read_parquet('{OUT}') GROUP BY split ORDER BY split
""").df().to_dict("records")
prof["concept_feat_cover"] = con.execute(f"""
  SELECT
    count(n_strong_today) AS nn_strong_today,
    count(n_mainline_not_onlist) AS nn_mainline,
    max(n_strong_today) AS mx_strong_today,
    max(n_mainline_not_onlist) AS mx_mainline,
    count(*) FILTER (WHERE n_strong_today>0) AS n_has_strong,
    count(*) FILTER (WHERE n_mainline_not_onlist>0) AS n_has_mainline
  FROM read_parquet('{OUT}')
""").df().to_dict("records")
(WS / "research_matrix_profile.json").write_text(
    json.dumps(prof, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("by_split", json.dumps(prof["by_split"], ensure_ascii=False), flush=True)
print("concept_cover", json.dumps(prof["concept_feat_cover"], ensure_ascii=False), flush=True)
print("DONE", flush=True)

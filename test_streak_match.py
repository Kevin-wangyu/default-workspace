# -*- coding: utf-8 -*-
"""验证模块 streak 标注与 research_matrix 口径一致（规则5.1验收）。纯读。"""
import sys
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
from queries import c7_picks
import duckdb
from pathlib import Path

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS / "research_matrix.parquet").as_posix()
con = duckdb.connect(); con.execute("SET threads=8")
C7 = """(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
  AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
  AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""

for d in ["2026-05-08", "2026-06-22", "2025-12-08"]:
    # 模块输出
    picks = c7_picks.get_c7_picks(d)["data"]["picks"]
    mod = {p["code"]: (p["streak_days"], p["is_streak2"]) for p in picks}
    # 矩阵口径
    ref = con.execute(f"""
    SELECT code, streak FROM (
      SELECT trade_date, code,
             row_number() OVER (PARTITION BY code, grp ORDER BY trade_date) AS streak
      FROM (SELECT trade_date, code, di,
                   di - row_number() OVER (PARTITION BY code ORDER BY di) AS grp
            FROM read_parquet('{RM}') WHERE {C7}) t
    ) WHERE trade_date='{d}' AND streak>=2
    """).df()
    ref_streak = dict(zip(ref.code, ref.streak))
    mod_streak2 = {c for c,(s,ok) in mod.items() if ok}
    print(f"\n=== {d} 模块n={len(picks)} 矩阵streak>=2 n={len(ref_streak)} ===")
    print(f"  模块is_streak2: {sorted(mod_streak2)}")
    print(f"  矩阵streak>=2 : {sorted(ref_streak)}")
    print(f"  模块streak明细: {[(p['code'],p['streak_days']) for p in picks if p['streak_days']>=2]}")
    print(f"  一致: {set(ref_streak)==mod_streak2}")

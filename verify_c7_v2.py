# -*- coding: utf-8 -*-
"""验证改造后端：①结果口径与研究矩阵一致 ②fwd_max列正确 ③耗时下降。纯读。"""
import sys, time, math
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")


def isnull(v):
    return v is None or (isinstance(v, float) and math.isnan(v))
import duckdb
from queries import c7_picks as C
from pathlib import Path
RM = (Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")/'research_matrix.parquet').as_posix()

C7 = """(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
  AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
  AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""

con=duckdb.connect(); con.execute("SET threads=8")
print("=== 新版 _compute vs 研究矩阵：C7池 code + fwd_max 对比 ===")
all_ok=True
for d in ["2026-10-30","2026-05-08","2024-09-27","2024-03-15"]:
    t=time.perf_counter(); picks=C._compute(d); dt=(time.perf_counter()-t)*1000
    new={p['code']:(p['fwd_max_5d'],p['fwd_max_10d']) for p in picks}
    # 研究矩阵：同日 C7 池的 fwd_max
    ref=con.execute(f"""SELECT code, fwd_max_5d, fwd_max_10d, fwd_n10 FROM read_parquet('{RM}')
        WHERE trade_date=? AND {C7}""",[d]).df()
    ref_map={str(r.code):(None if isnull(r.fwd_max_5d) else round(float(r.fwd_max_5d),2),
                          None if isnull(r.fwd_max_10d) else round(float(r.fwd_max_10d),2),
                          int(r.fwd_n10) if not isnull(r.fwd_n10) else 0)
             for r in ref.itertuples(index=False)}
    codes_ok = set(new)==set(ref_map)
    # fwd_max_5d 严格一致；fwd_max_10d 需考虑"矩阵构建时未来数据不足"的推进差异
    real_mismatch=[]; advance_note=[]
    for c,(n5,n10) in new.items():
        r5,r10,rn10 = ref_map[c]
        if n5 != r5: real_mismatch.append((c,'fwd5',n5,r5))
        if n10 != r10:
            if r10 is None and rn10<10 and n10 is not None:
                advance_note.append(c)   # 矩阵当时不足10日，新版数据推进后补全：正确
            else:
                real_mismatch.append((c,'fwd10',n10,r10))
    val_ok = codes_ok and not real_mismatch
    all_ok &= val_ok
    n_fwd5 = sum(1 for v in new.values() if v[0] is not None)
    n_fwd10 = sum(1 for v in new.values() if v[1] is not None)
    print(f"[{d}] n={len(picks)} code一致={codes_ok} 口径一致={val_ok} "
          f"耗时={dt:.0f}ms fwd5非空={n_fwd5} fwd10非空={n_fwd10} "
          f"数据推进补全={len(advance_note)}只")
    if not codes_ok:
        print(f"   仅新版:{set(new)-set(ref_map)} 仅矩阵:{set(ref_map)-set(new)}")
    for m in real_mismatch: print(f"   REAL_MISMATCH {m}")
con.close()

print("\n=== 端点返回新字段检查 ===")
r=C.get_c7_picks("2026-05-08")
p=r['data']['picks'][0]
print(f"  字段含 fwd_max_5d={'fwd_max_5d' in p} fwd_max_10d={'fwd_max_10d' in p}")
print(f"  样例 {p['code']}: fwd_max_5d={p['fwd_max_5d']} fwd_max_10d={p['fwd_max_10d']}")
print(f"  future_info标记={r['meta']['future_info']} (仅指选股条件无前视；复盘列是展示用)")
print("\nVERIFY_V2="+("ALL_OK" if all_ok else "FAILED"))

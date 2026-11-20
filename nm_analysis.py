# -*- coding: utf-8 -*-
"""
指标一/二：n×m 参数网格分析（train/oos 双期，矩阵自身重算 fwd_max，零前视）。
- 指标一：C7 池命中比例随 n,m 变化 + 性价比寻优
- 指标二：捕获率 = C7命中数 / 全市场命中数（当时市场环境下）+ 相对放大倍数
全部用 daily_pct 口径（矩阵 close/high 均前复权一致），fwd_* 仅作标签。纯读。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb, numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")

NS=[3,5,7,10,12,15,20,25]
MS=[10,15,20,25,30,40,50]
C7="""(lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
 AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
 AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1)"""
mcols=",".join([f"count(*) FILTER (WHERE fmax>={m}) AS h{m}" for m in MS])

grid=[]
t0=time.time()
for n in NS:
    sql=f"""
    WITH r AS (
      SELECT split, trade_date, code, CASE WHEN {C7} THEN 1 ELSE 0 END AS c7,
        (max(high) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND {n} FOLLOWING)
         /NULLIF(close,0)-1)*100 AS fmax,
        count(*) OVER (PARTITION BY code ORDER BY di RANGE BETWEEN 1 FOLLOWING AND {n} FOLLOWING) AS nn
      FROM read_parquet('{RM}')
    ),
    v AS (SELECT * FROM r WHERE nn={n} AND split IN ('train','oos'))
    SELECT split, c7, count(*) AS pool_n, {mcols}
    FROM v GROUP BY split, c7 ORDER BY split, c7
    """
    df=con.execute(sql).df()
    for _,row in df.iterrows():
        for m in MS:
            grid.append(dict(n=n,m=m,split=row['split'],c7=int(row['c7']),
                             pool_n=int(row['pool_n']),hit_n=int(row[f'h{m}'])))
    print(f"n={n} done ({time.time()-t0:.1f}s)",flush=True)

# 整理为网格
def lookup(n,m,split,c7):
    for g in grid:
        if g['n']==n and g['m']==m and g['split']==split and g['c7']==c7: return g
    return None

res={}
for split in ['train','oos']:
    for n in NS:
        for m in MS:
            c=lookup(n,m,split,1); a=lookup(n,m,split,0)
            if not c or not a: continue
            c7_hit=c['hit_n']/c['pool_n'] if c['pool_n'] else None
            mkt_hit=a['hit_n']/a['pool_n'] if a['pool_n'] else None
            tot_hit=c['hit_n']+a['hit_n']
            tot_pool=c['pool_n']+a['pool_n']
            capture=c['hit_n']/tot_hit if tot_hit else None       # 指标二：捕获率
            c7_share=c['pool_n']/tot_pool if tot_pool else None   # C7 选股占比
            ampl=(capture/c7_share) if (capture is not None and c7_share) else None  # 相对放大
            res[f"{split}|{n}|{m}"]=dict(
                split=split,n=n,m=m,c7_pool=c['pool_n'],c7_hit_n=c['hit_n'],
                c7_hit_rate=round(c7_hit,6) if c7_hit is not None else None,
                mkt_hit_n=a['hit_n'],mkt_pool=a['pool_n'],
                mkt_hit_rate=round(mkt_hit,6) if mkt_hit is not None else None,
                lift=round(c7_hit/mkt_hit,3) if (c7_hit is not None and mkt_hit) else None,
                capture=round(capture,6) if capture is not None else None,
                c7_share=round(c7_share,8) if c7_share is not None else None,
                amplification=round(ampl,2) if ampl is not None else None)

# ---- 性价比寻优（指标一）----
# 定义：Score = hit(n,m) × (m/20)^alpha / (n/10)^beta；基准 alpha=1(收益线性), beta=1(时间线性)
# 另给：日化效率 hit/n；边际递减 elbow（每 m 下 hit 随 n 的边际增量）
perf=[]
for split in ['train','oos']:
    for alpha in [1.0]:
        for beta in [1.0]:
            for n in NS:
                for m in MS:
                    r=res.get(f"{split}|{n}|{m}")
                    if not r or r['c7_hit_rate'] is None: continue
                    h=r['c7_hit_rate']
                    score=h*(m/20)**alpha/(n/10)**beta
                    daily=h/n
                    perf.append(dict(split=split,n=n,m=m,hit=round(h,4),
                                     score=round(score,5),daily_eff=round(daily,5)))

# elbow：每个 m 下，hit(n) 边际增量（相邻 n 的差 / 天数差）
elbow=[]
for split in ['train','oos']:
    for m in MS:
        hs=[(n,res[f"{split}|{n}|{m}"]['c7_hit_rate']) for n in NS if res.get(f"{split}|{n}|{m}")]
        for i in range(1,len(hs)):
            dn=hs[i][0]-hs[i-1][0]
            dh=hs[i][1]-hs[i-1][1]
            elbow.append(dict(split=split,m=m,n_from=hs[i-1][0],n_to=hs[i][0],
                              d_hit=round(dh,4),per_day=round(dh/dn,5)))

out=dict(config=dict(NS=NS,MS=MS,C7=C7,
                     score_formula="hit × (m/20)^alpha / (n/10)^beta, alpha=beta=1",
                     capture_formula="C7_hit_n / (C7_hit_n + market_hit_n)",
                     amplification_formula="capture / (C7_pool / total_pool)"),
         grid=res,perf=perf,elbow=elbow,
         meta=dict(rows=con.execute(f"SELECT count(*) FROM read_parquet('{RM}')").fetchone()[0],
                   seconds=round(time.time()-t0,1)))
(WS/"nm_analysis_out.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")

# 摘要打印（m=20 基线 + 各 m 最优 n）
print("=== 指标一：C7 命中比例 hit(n,m) ===")
for split in ['train','oos']:
    print(f"-- {split} --")
    for m in MS:
        s=" ".join(f"n{n}:{res[f'{split}|{n}|{m}']['c7_hit_rate']*100:.1f}%" for n in NS)
        print(f"  m={m:>2}: {s}")
print("=== 性价比 Score 最优 (alpha=beta=1) ===")
for split in ['train','oos']:
    ps=sorted([p for p in perf if p['split']==split],key=lambda x:-x['score'])[:6]
    print(f"-- {split} --",[(p['n'],p['m'],p['hit'],p['score']) for p in ps])
print("=== 指标二：捕获率 capture(n,m), m=20 ===")
for split in ['train','oos']:
    print(f"-- {split} --")
    for n in NS:
        r=res[f"{split}|{n}|20"]
        print(f"  n={n:>2}: capture={r['capture']*100:.3f}%  c7_share={r['c7_share']*100:.4f}%  ampl={r['amplification']}x  lift={r['lift']}")
print("DONE",out['meta'])

# -*- coding: utf-8 -*-
"""补充：①退出榜主线未结束的宽松口径对照（扩样本）②强榜持续性宏观证据。纯读。"""
from __future__ import annotations
import json, math
from pathlib import Path
import duckdb, numpy as np
from scipy import stats
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
BAR='D:/Users/KFish/Desktop/Code/github-app/stockDisplay/data_compact/_tops_cache/v1/bars.parquet'
con=duckdb.connect(); con.execute("SET threads=8")
use="""split,trade_date,code,lu_cnt_20d,main_net_norm,vol20,turnover_rate,lu_gap,
 close_hh20_ratio,ret_5d,n_leader_concepts,n_strong_today,n_concept_strong_hist,
 n_mainline_not_onlist,max_strong_hist10,n_concept_hot20,y5,y7,y10,y12"""
df=con.execute(f"SELECT {use} FROM read_parquet('{RM}')").df()
D={c:df[c].to_numpy() for c in df.columns}
tr=D["split"]=="train"; oos=D["split"]=="oos"
def f(a): return np.nan_to_num(np.asarray(a,float),nan=0.,posinf=0.,neginf=0.)
def rate(m,y):
    v=D[y][m]; v=v[~np.isnan(v)]; return (float(v.mean()),int(v.size)) if v.size else (float('nan'),0)
def zt(p1,n1,p0,n0):
    if n1<1 or n0<1: return 0.,1.
    pp=(p1*n1+p0*n0)/(n1+n0); se=math.sqrt(max(pp*(1-pp)*(1/n1+1/n0),1e-15))
    z=(p1-p0)/se; return round(z,2),round(float(2*(1-stats.norm.cdf(abs(z)))),6)
V7=float(np.nanquantile(D["vol20"][tr],.70)); T6=float(np.nanquantile(D["turnover_rate"][tr],.60))
R80=float(np.nanquantile(D["ret_5d"][tr],.80))
base=(f(D["lu_cnt_20d"])>=1)&(f(D["main_net_norm"])>0)&(f(D["vol20"])>=V7)&(f(D["turnover_rate"])>=T6)
near=f(D["lu_gap"])>=-3; high=f(D["close_hh20_ratio"])>=.95
mom=f(D["ret_5d"])>=R80; bull=(f(D["ma5_gt_ma20"]).astype(int)+f(D["ma20_gt_ma60"]).astype(int)>=2) if "ma5_gt_ma20" in D else np.zeros(len(df),bool)
c2=base&near&high
c6=base&near&high&mom  # 多头列本次未取，用 C4 动量组合近似

out={}
# ①退出榜主线未结束：三档定义 × 基准池/全样本 × train/oos
DEFS={
 "严格(构造标志n_mainline_not_onlist>=1)": f(D["n_mainline_not_onlist"])>=1,
 "宽松(近10日强>=1 且 当日不在强榜)": (f(D["n_concept_strong_hist"])>=1)&(f(D["n_strong_today"])==0),
 "近20日热榜>=1 且 当日不在强榜": (f(D["n_concept_hot20"])>=1)&(f(D["n_strong_today"])==0),
}
for sp,mask in [("train",tr),("oos",oos)]:
    for poolname,pool in [("全样本",mask),("基准池C0",mask&base),("进攻池C2",mask&c2)]:
        bp=rate(pool,"y10")[0]
        key=f"{sp}/{poolname}"
        out.setdefault("offlist_defs",{})[key]={"pool_n":int(pool.sum()),"pool_hit10":round(bp,4)}
        for dn,cond in DEFS.items():
            mm=pool&cond; p,n=rate(mm,"y10"); p5,n5=rate(mm,"y5")
            z,pv=zt(p,n,bp,rate(pool,"y10")[1])
            out["offlist_defs"][key][dn]={"n":int(n),"hit10":round(p,4) if n else None,
                "delta10":round(p-bp,4) if n else None,"p":pv,"hit5":round(p5,4) if n5 else None}

# ②强榜持续性宏观证据
try:
    persist=con.execute(f"""
      SELECT count(*) AS n_days,
             round(avg(n_strong),2) AS avg_strong_per_day,
             min(n_strong) AS min_strong, max(n_strong) AS max_strong
      FROM (SELECT trade_date, count(DISTINCT name) AS n_strong
            FROM read_parquet('{BAR}') WHERE is_strong=true GROUP BY 1)
    """).df().to_dict("records")
    out["strong_list_persistence"]=persist
except Exception as e:
    out["strong_list_persistence"]={"error":str(e)}

# ③历史强概念当日仍在榜比例（微观持续性，train+oos）
m=(tr|oos)
h1=f(D["n_concept_strong_hist"])>=1
out["concept_persistence_micro"]={
  "hist_ge1_n":int((m&h1).sum()),
  "hist_ge1_and_today_strong_n":int((m&h1&(f(D["n_strong_today"])>=1)).sum()),
  "hist_ge1_and_today_offlist_n":int((m&h1&(f(D["n_strong_today"])==0)).sum()),
}
out["concept_persistence_micro"]["stay_rate"]=round(
  out["concept_persistence_micro"]["hist_ge1_and_today_strong_n"]/max(out["concept_persistence_micro"]["hist_ge1_n"],1),4)

(WS/"final_supp_out.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print("OFFLIST",json.dumps(out["offlist_defs"],ensure_ascii=False,indent=1),flush=True)
print("PERSIST",json.dumps(out["strong_list_persistence"],ensure_ascii=False),flush=True)
print("MICRO",json.dumps(out["concept_persistence_micro"],ensure_ascii=False),flush=True)
print("DONE",flush=True)

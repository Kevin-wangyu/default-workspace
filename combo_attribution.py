# -*- coding: utf-8 -*-
"""组合递进归因 + 因子稳健性判定（纯读，零写入项目）。

1) 在固定基准池上按经济逻辑逐层叠加有效因子，train/oos × y5/y7/y10/y12 双口径。
2) 概念两口径分支：当日强榜 vs 主线延续（含退出榜未结束）——按用户 m00575。
3) 滞后处理：y5/y10=当日进攻；y7/y12=放宽2日窗口（触发日归集）。
4) 因子稳健性：从 factor_attribution_out.json 读 17 因子，判 train/oos 同号显著性。
所有阈值 train 定、oos 直接套用；mkt_hit5/10 前视字段不入池。
"""
from __future__ import annotations
import json, math
from pathlib import Path
import duckdb
import numpy as np
from scipy import stats

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS / "research_matrix.parquet").as_posix()
con = duckdb.connect()
con.execute("SET threads=8")

use = """split,trade_date,code,
 lu_cnt_20d,main_net_norm,vol20,turnover_rate,lu_gap,close_hh20_ratio,ret_5d,
 n_leader_concepts,n_strong_today,n_concept_strong_hist,n_mainline_not_onlist,
 ma5_gt_ma20,ma20_gt_ma60,eff_hit10_lag,mkt_amt_ratio,small_norm,tor_ratio,
 scrplus_90,y5,y7,y10,y12"""
df = con.execute(f"SELECT {use} FROM read_parquet('{RM}')").df()
D = {c: df[c].to_numpy() for c in df.columns}
tr = D["split"] == "train"
oos = D["split"] == "oos"
def f(a): return np.nan_to_num(np.asarray(a,float), nan=0.0, posinf=0.0, neginf=0.0)
def q(a,p,mask=None):
    x = D[a][mask] if mask is not None else D[a]
    return float(np.nanquantile(x,p))

def rate(mask,y):
    v = D[y][mask]; v = v[~np.isnan(v)]
    return (float(v.mean()), int(v.size)) if v.size else (float("nan"),0)
def zt(p1,n1,p0,n0):
    if n1<1 or n0<1: return 0.0,1.0
    pp=(p1*n1+p0*n0)/(n1+n0); se=math.sqrt(max(pp*(1-pp)*(1/n1+1/n0),1e-15))
    z=(p1-p0)/se; return round(z,2),round(float(2*(1-stats.norm.cdf(abs(z)))),6)

# train 定阈值
V7,T6 = q("vol20",0.70,tr), q("turnover_rate",0.60,tr)
R80   = q("ret_5d",0.80,tr)
E70   = q("eff_hit10_lag",0.70,tr)
S30   = q("small_norm",0.30,tr)
base = (f(D["lu_cnt_20d"])>=1)&(f(D["main_net_norm"])>0)&(f(D["vol20"])>=V7)&(f(D["turnover_rate"])>=T6)

# 逐层叠加（每层累加，非互斥）
near_limit = f(D["lu_gap"])>=-3
near_high  = f(D["close_hh20_ratio"])>=0.95
leader     = f(D["n_leader_concepts"])>=1
momentum   = f(D["ret_5d"])>=R80
bull_align = (f(D["ma5_gt_ma20"]).astype(int)+f(D["ma20_gt_ma60"]).astype(int)>=2)
market_warm= (f(D["eff_hit10_lag"])>=E70)&(f(D["mkt_amt_ratio"])>=1.0)
small_out  = f(D["small_norm"])<=S30

LAYERS = {
 "L0 基准池(情绪+资金+高波动)": base,
 "L1 +近涨停(进攻启动)": base&near_limit,
 "L2 +逼近日高(突破前夜)": base&near_limit&near_high,
 "L3 +龙头概念": base&near_limit&near_high&leader,
 "L4a +当日强榜(概念口径A)": base&near_limit&near_high&(f(D["n_strong_today"])>=1),
 "L4b +主线延续(概念口径B)": base&near_limit&near_high&(f(D["n_concept_strong_hist"])>=2),
 "L5 +短期动量(R80)": base&near_limit&near_high&leader&momentum,
 "L5' +多头排列": base&near_limit&near_high&leader&bull_align,
 "L5'' +市场暖(滞后赚钱+量能)": base&near_limit&near_high&leader&market_warm,
 "L5''' +小单流出": base&near_limit&near_high&leader&small_out,
 "L6 全叠加(动量+多头+市场+小单)": base&near_limit&near_high&leader&momentum&bull_align&market_warm&small_out,
}

def table(split_mask, base_mask):
    bp5,bn5=rate(base_mask,"y5"); bp10,bn10=rate(base_mask,"y10")
    out={}
    for name,gmask in LAYERS.items():
        m = gmask & split_mask   # 必须与当前 split 相交，否则 train/oos 退化为同一全样本
        r={"n":int(m.sum())}
        for y in ["y5","y7","y10","y12"]:
            p,n=rate(m,y); z,pv=zt(p,n, bp5 if y=="y5" else bp10, bn5 if y=="y5" else bn10)
            r[y]={"hit":round(p,4) if n else None,"n":n,
                  "lift":round(p/(bp5 if y in("y5","y7") else bp10),3) if n and p==p else None,
                  "delta":round(p-(bp5 if y in("y5","y7") else bp10),4) if n else None,
                  "z":z,"p":pv}
        out[name]=r
    return out
res={"thresholds":{"vol20_q70":round(V7,4),"turnover_q60":round(T6,4),
                   "ret5_q80":round(R80,4),"eff_hit_lag_q70":round(E70,4),"small_norm_q30":round(S30,4)},
     "train":table(tr&base,tr&base), "oos":table(oos&base,oos&base)}

# 概念两口径互斥对照（在 L2 池上）
for sp,mask in [("train",tr),("oos",oos)]:
    m=mask&base&near_limit&near_high
    res.setdefault("concept_branch",{})[sp]={
      "当日强榜": {"n":int((m&(f(D["n_strong_today"])>=1)).sum()),
                   **{y:round(rate(m&(f(D["n_strong_today"])>=1),y)[0],4) for y in ["y5","y7","y10","y12"]}},
      "主线延续": {"n":int((m&(f(D["n_concept_strong_hist"])>=2)).sum()),
                   **{y:round(rate(m&(f(D["n_concept_strong_hist"])>=2),y)[0],4) for y in ["y5","y7","y10","y12"]}},
      "退出榜但主线未结束": {"n":int((m&(f(D["n_mainline_not_onlist"])>=1)).sum()),
                   **{y:(round(rate(m&(f(D["n_mainline_not_onlist"])>=1),y)[0],4) if rate(m&(f(D["n_mainline_not_onlist"])>=1),y)[1] else None) for y in ["y5","y7","y10","y12"]}},
    }

# 稳健性判定：读单因子结果
fa=json.loads((WS/"factor_attribution_out.json").read_text(encoding="utf-8"))
rob={}
for name,row in fa["splits"]["train"]["factors"].items():
    a=row["y10"]; b=fa["splits"]["oos"]["factors"][name]["y10"]
    da=a["delta"]; db=b["delta"]
    sig_a = a["p"] is not None and a["p"]<0.05
    sig_b = b["p"] is not None and b["p"]<0.05
    same = (da is not None and db is not None and da*db>0)
    if same and sig_a and sig_b: verdict="稳健有效"
    elif same and (sig_a or sig_b): verdict="方向一致/单侧显著"
    elif da is not None and db is not None and da*db<0: verdict="样本内外反向(不稳定)"
    else: verdict="无显著"
    rob[name]={"train_delta10":da,"oos_delta10":db,"train_p":a["p"],"oos_p":b["p"],"verdict":verdict}
res["robustness"]=rob

(WS/"combo_attribution_out.json").write_text(json.dumps(res,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print("THR",json.dumps(res["thresholds"],ensure_ascii=False),flush=True)
for sp in ["train","oos"]:
    print(f"=== {sp} ===",flush=True)
    for name,r in res[sp].items():
        print(f"{name}: n={r['n']} hit10={r['y10']['hit']} lift10={r['y10']['lift']} d10={r['y10']['delta']} p={r['y10']['p']} | hit5={r['y5']['hit']} hit12={r['y12']['hit']}",flush=True)
print("CONCEPT_BRANCH",json.dumps(res["concept_branch"],ensure_ascii=False),flush=True)
print("ROBUSTNESS",flush=True)
for n,r in rob.items(): print(f"  {n}: {r['verdict']} (tr={r['train_delta10']}/p={r['train_p']} oos={r['oos_delta10']}/p={r['oos_p']})",flush=True)
print("DONE",flush=True)

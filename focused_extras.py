# -*- coding: utf-8 -*-
"""聚焦补充实验（纯读）：①动量+多头双叠加最优组合 ②主线未结束宽松定义扩样本
③scrplus 真值轨道增量 ④滞后归因 ⑤各层逐日达标占比。输出 focused_extras_out.json。
"""
from __future__ import annotations
import json, math
from pathlib import Path
import duckdb, numpy as np
from scipy import stats

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS/"research_matrix.parquet").as_posix()
con = duckdb.connect(); con.execute("SET threads=8")
use="""split,trade_date,code,lu_cnt_20d,main_net_norm,vol20,turnover_rate,lu_gap,
 close_hh20_ratio,ret_5d,n_leader_concepts,n_strong_today,n_concept_strong_hist,
 n_mainline_not_onlist,max_strong_hist10,ma5_gt_ma20,ma20_gt_ma60,scrplus_90,
 eff_hit10_lag,mkt_amt_ratio,y5,y7,y10,y12"""
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
leader=f(D["n_leader_concepts"])>=1; mom=f(D["ret_5d"])>=R80
bull=(f(D["ma5_gt_ma20"]).astype(int)+f(D["ma20_gt_ma60"]).astype(int)>=2)
strong_today=f(D["n_strong_today"])>=1
mainline=f(D["n_concept_strong_hist"])>=2                 # 严格：近10日强>=2
mainline_loose=f(D["n_concept_strong_hist"])>=1            # 宽松：近10日强>=1
offlist_loose=(f(D["n_mainline_not_onlist"])>=1)|((f(D["n_concept_strong_hist"])>=1)&(~strong_today))
maintained=f(D["max_strong_hist10"])>=5                    # 概念历史峰值强
out={"thresholds":{"vol20_q70":round(V7,4),"turnover_q60":round(T6,4),"ret5_q80":round(R80,4)}}

# ① 双叠加最优组合（固定 train 阈值，train/oos 同套）
COMBOS={
 "C0 基准三类": base,
 "C1 +近涨停": base&near,
 "C2 +近涨停+逼近日高": base&near&high,
 "C3 C2+龙头概念": base&near&high&leader,
 "C4 C2+动量": base&near&high&mom,
 "C5 C2+多头": base&near&high&bull,
 "C6 C2+动量+多头(双叠加)": base&near&high&mom&bull,
 "C7 C6+龙头概念": base&near&high&mom&bull&leader,
 "C8 C2+主线延续(宽松)": base&near&high&mainline_loose,
 "C9 C6+主线延续(宽松)": base&near&high&mom&bull&mainline_loose,
 "C10 C2+逼近日高+概念热(主线延续严格)": base&near&high&mainline,
}
for sp,mask in [("train",tr),("oos",oos)]:
    bp=rate(mask&base,"y10")[0]; bp5=rate(mask&base,"y5")[0]
    rows={}
    for nm,g in COMBOS.items():
        m=g&mask; r={"n":int(m.sum())}
        for y in ["y5","y7","y10","y12"]:
            p,n=rate(m,y); b=bp5 if y in("y5","y7") else bp
            z,pv=zt(p,n,b,rate(mask&base,y)[1])
            r[y]={"hit":round(p,4) if n else None,"lift":round(p/b,3) if n and b>0 else None,
                  "delta":round(p-b,4) if n else None,"p":pv,"z":z,"n":n}
        rows[nm]=r
    out.setdefault("combos",{})[sp]=rows

# ② 概念"退出榜但主线未结束"宽松定义 + 对照（在 C2 池上）
for sp,mask in [("train",tr),("oos",oos)]:
    m=mask&base&near&high
    grp={
      "无概念": ~strong_today & ~mainline_loose,
      "当日强榜(非延续)": strong_today & ~mainline,
      "主线延续(严格,当日强)": mainline & strong_today,
      "主线延续但已退出强榜": mainline & ~strong_today,           # 用户核心关注：涨跌并存
      "宽松主线退出(>=1且当日不在榜)": offlist_loose & ~strong_today,
    }
    out.setdefault("concept_offlist",{})[sp]={
      gn:{"n":int((m&gm).sum()), **{y:(round(rate(m&gm,y)[0],4) if rate(m&gm,y)[1] else None) for y in ["y5","y7","y10","y12"]}}
      for gn,gm in grp.items()}

# ③ scrplus 真值轨道（2026-04+）在基准池 + 最优组合上的增量
scr_base=oos&base&(df["trade_date"].to_numpy()>="2026-04-01")
pos=f(D["scrplus_90"])>0
scr_thr=float(np.nanquantile(D["scrplus_90"][scr_base&pos],.5))
out["scrplus_track"]={
 "note":"scrplus 仅 2026-04+ 有真值；train 全 0 不可用；此处在 oos 基准池内检验真实筹码集中度增量",
 "median":round(scr_thr,3),
 "n_base_2026apr":int(scr_base.sum()),
 "n_with_scrplus":int((scr_base&pos).sum()),
}
rows={}
for nm,g in {"基准池":base,"近涨停":base&near,"双叠加":base&near&high&mom&bull,
             "双叠加+龙头":base&near&high&mom&bull&leader}.items():
    m0=scr_base&g; m1=m0&(f(D["scrplus_90"])>=scr_thr)
    r0=rate(m0,"y10"); r1=rate(m1,"y10")
    r5_0=rate(m0,"y5"); r5_1=rate(m1,"y5")
    z,pv=zt(r1[0],r1[1],r0[0],r0[1])
    rows[nm]={"n_all":r0[1],"hit10_all":round(r0[0],4),"n_high":r1[1],
              "hit10_high":round(r1[0],4),"delta10":round(r1[0]-r0[0],4),"p":pv,
              "hit5_all":round(r5_0[0],4),"hit5_high":round(r5_1[0],4)}
out["scrplus_track"]["layers"]=rows

# ④ 滞后归因：C6 双叠加按触发日逐档窗口概率（train/oos）
out["lag_curve"]={}
for sp,mask in [("train",tr),("oos",oos)]:
    m=mask&COMBOS["C6 C2+动量+多头(双叠加)"]
    out["lag_curve"][sp]={"n":int(m.sum()),
      **{y:round(rate(m,y)[0],4) for y in ["y5","y7","y10","y12"]},
      "gain_5to7":round(rate(m,"y7")[0]-rate(m,"y5")[0],4),
      "gain_10to12":round(rate(m,"y12")[0]-rate(m,"y10")[0],4)}

(WS/"focused_extras_out.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print("THR",json.dumps(out["thresholds"],ensure_ascii=False),flush=True)
for sp in ["train","oos"]:
    print(f"=== {sp} combos ===",flush=True)
    for nm,r in out["combos"][sp].items():
        print(f"{nm}: n={r['n']} hit10={r['y10']['hit']} lift10={r['y10']['lift']} | hit5={r['y5']['hit']} hit12={r['y12']['hit']}",flush=True)
    print(f"--- concept offlist {sp} ---",flush=True)
    for gn,r in out["concept_offlist"][sp].items():
        print(f"  {gn}: n={r['n']} hit10={r['y10']} hit5={r['y5']}",flush=True)
print("SCRPLUS",json.dumps(out["scrplus_track"],ensure_ascii=False),flush=True)
print("LAG",json.dumps(out["lag_curve"],ensure_ascii=False),flush=True)
print("DONE",flush=True)

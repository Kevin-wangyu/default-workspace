# -*- coding: utf-8 -*-
"""C7 最佳推荐条件的逐日表现回放 + 牛熊分组统计 + 两次研究同口径对比。纯读。"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb, numpy as np, pandas as pd
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")

cols=[r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{RM}')").fetchall()]
print("has mkt_ret_20d:", "mkt_ret_20d" in cols, "has mkt_pct_ma5:", "mkt_pct_ma5" in cols)

use="""trade_date,split,code,name,lu_cnt_20d,main_net_norm,vol20,turnover_rate,
 lu_gap,close_hh20_ratio,ret_5d,ma5_gt_ma20,ma20_gt_ma60,n_leader_concepts,
 y5,y10,mkt_hit10,mkt_hit5,mkt_ret_20d,mkt_pct_mean"""
df=con.execute(f"SELECT {use} FROM read_parquet('{RM}')").df()
def f(a): return np.nan_to_num(np.asarray(a,float),nan=0.,posinf=0.,neginf=0.)

# train 定阈值（与 focused_extras 完全一致）
tr=df["split"].values=="train"
V7=float(np.nanquantile(df["vol20"].values[tr],.70))
T6=float(np.nanquantile(df["turnover_rate"].values[tr],.60))
R80=float(np.nanquantile(df["ret_5d"].values[tr],.80))
cond=(f(df["lu_cnt_20d"])>=1)&(f(df["main_net_norm"])>0)&(f(df["vol20"])>=V7)&(f(df["turnover_rate"])>=T6)&\
     (f(df["lu_gap"])>=-3)&(f(df["close_hh20_ratio"])>=.95)&(f(df["ret_5d"])>=R80)&\
     (f(df["ma5_gt_ma20"]).astype(int)+f(df["ma20_gt_ma60"]).astype(int)>=2)&\
     (f(df["n_leader_concepts"])>=1)
sel=df[cond].copy()
sel["hit10"]=sel["y10"]; sel["hit5"]=sel["y5"]

# 逐日聚合（只保留有未来标签的日子）
daily=sel.groupby("trade_date").agg(
    n=("code","size"), hit10=("hit10","mean"), hit5=("hit5","mean"),
    split=("split","first"), mkt_hit10=("mkt_hit10","first"),
    mkt_ret_20d=("mkt_ret_20d","first"), mkt_pct_mean=("mkt_pct_mean","first")
).reset_index().sort_values("trade_date")
daily=daily[daily["hit10"].notna()].copy()

def regime(r):
    if pd.isna(r): return "震荡"
    return "牛" if r>2 else ("熊" if r<-2 else "震荡")
daily["regime"]=daily["mkt_ret_20d"].apply(regime)

def stats(g):
    if len(g)==0: return {}
    h=g["hit10"].values
    return {
      "days":int(len(g)),
      "total_picks":int(g["n"].sum()),
      "mean_daily_hit10":round(float(np.nanmean(h)),4),
      "median_daily_hit10":round(float(np.nanmedian(h)),4),
      "min_daily_hit10":round(float(np.nanmin(h)),4),
      "max_daily_hit10":round(float(np.nanmax(h)),4),
      "pooled_hit10":round(float(g["hit10"].fillna(0).dot(g["n"])/g["n"].sum()),4),
      "days_ge75":int((h>=.75).sum()), "days_50_75":int(((h>=.5)&(h<.75)).sum()),
      "days_25_50":int(((h>=.25)&(h<.5)).sum()), "days_lt25":int((h<.25).sum()),
      "mean_picks_per_day":round(float(g["n"].mean()),1),
      "median_picks_per_day":round(float(g["n"].median()),1),
    }

out={"thresholds":{"vol20":round(V7,4),"turnover_rate":round(T6,4),"ret_5d":round(R80,4),
                   "lu_gap":-3,"close_hh20_ratio":0.95,"ma_bull":"ma5>ma20>ma60","n_leader_concepts":1},
     "daily":[{"date":r.trade_date,"n":int(r.n),"hit10":round(float(r.hit10),4),
               "hit5":round(float(r.hit5),4) if pd.notna(r.hit5) else None,
               "split":r.split,"mkt_hit10":round(float(r.mkt_hit10),4) if pd.notna(r.mkt_hit10) else None,
               "regime":r.regime} for r in daily.itertuples()]}
out["by_split"]={sp:stats(g) for sp,g in daily.groupby("split")}
out["by_regime"]={rg:stats(g) for rg,g in daily.groupby("regime")}
out["overall"]=stats(daily)

# 月度聚合（制图用）
daily["ym"]=daily["trade_date"].str[:7]
monthly=daily.groupby("ym").agg(n=("n","sum"),hit10=("hit10","mean"),days=("n","size")).reset_index()
out["monthly"]=[{"ym":r.ym,"n":int(r.n),"hit10":round(float(r.hit10),4),"days":int(r.days)} for r in monthly.itertuples()]

# ---- 两次研究同口径对比 ----
sr=json.loads((WS/"search_results.json").read_text(encoding="utf-8"))
rd=json.loads((WS/"report_data.json").read_text(encoding="utf-8"))
# 第一次报告 R1 = C_25-50% grade 第一条
grades=sr.get("grades",[])
first_r1=None
for g in grades:
    if isinstance(g,dict) and g.get("train",{}).get("10",{}).get("merge",0)>0.40:
        first_r1={"merge_train":g["train"]["10"]["merge"],"pool_train":g["train"]["10"].get("pool_n"),
                  "daily75_train":g["train"]["10"].get("daily75"),"hit_days_train":g["train"]["10"].get("hit_days"),
                  "oos10":g.get("oos",{}).get("10",{}).get("merge") if isinstance(g.get("oos"),dict) else None}
        first_r1["label"]=g.get("label","")
        first_r1["rule"]=g.get("rule","")
        break
out["first_report_r1"]=first_r1
out["this_report_c7"]={"merge_train":out["by_split"].get("train",{}).get("pooled_hit10"),
                       "merge_oos":out["by_split"].get("oos",{}).get("pooled_hit10"),
                       "pool_train":out["by_split"].get("train",{}).get("total_picks"),
                       "daily75_train_days":out["by_split"].get("train",{}).get("days_ge75")}

(WS/"c7_daily_out.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
print("THR",json.dumps(out["thresholds"],ensure_ascii=False))
print("OVERALL",json.dumps(out["overall"],ensure_ascii=False))
print("BY_SPLIT",json.dumps(out["by_split"],ensure_ascii=False))
print("BY_REGIME",json.dumps(out["by_regime"],ensure_ascii=False))
print("FIRST_R1",json.dumps(first_r1,ensure_ascii=False))
print("THIS_C7",json.dumps(out["this_report_c7"],ensure_ascii=False))
print("MONTHLY_first/last",out["monthly"][0],out["monthly"][-1])
print("DONE")

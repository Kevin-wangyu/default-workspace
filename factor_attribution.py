# -*- coding: utf-8 -*-
"""增量归因分析（核心脚本，纯读零写入项目）。

在"情绪+资金/筹码集中+高波动"三类条件基准池上，逐一/组合检验新增因子
对 hit(未来N日最大涨幅>20%) 的提升；train/oos 双口径 + z 检验 + 5/10/放宽7/12。

口径防护：
 - 所有筛选因子 T 日可知；mkt_hit5/10 含未来数据，禁止入池。
 - 市场状况只用 eff_hit10_lag/eff_hit5_lag（过去11-30日，T日可知）。
 - scrplus 在 train 全 0，单列 oos(2026-04+) 轨道单独检验。
 - 滞后处理：y5/y10=当日进攻窗口；y7/y12=放宽2日观察窗口（触发日归集）。
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

# 载入必要列到 numpy
cols_needed = """split,trade_date,di,code,
  lu_cnt_20d,lu_cnt_10d,is_limit_up,main_net_norm,huge_norm,small_norm,
  vol20,turnover_rate,ret_5d,ret_10d,bias5,bias20,close_hh20_ratio,
  ma5_gt_ma20,ma20_gt_ma60,tor_ratio,lu_gap,amt_ratio,
  n_strong_today,in_strong_concept,n_concept_strong_hist,n_mainline_not_onlist,
  max_strong_hist10,n_concept_hot20,n_hot_concepts,n_leader_concepts,n_concepts,
  eff_hit10_lag,eff_hit5_lag,mkt_amt_ratio,mkt_ret_5d,mkt_lu_ma5,mkt_up_ratio,
  y5,y7,y10,y12"""
df = con.execute(f"SELECT {cols_needed} FROM read_parquet('{RM}')").df()
D = {c: df[c].to_numpy() for c in df.columns}
N = len(df)
print("loaded rows", N, flush=True)

def finite(a):
    a = np.asarray(a, dtype=float)
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)

def ztest(p1, n1, p0, n0):
    if n1 < 1 or n0 < 1: return 0.0, 1.0
    pp = (p1*n1 + p0*n0)/(n1+n0)
    se = math.sqrt(max(pp*(1-pp)*(1/n1+1/n0), 1e-15))
    z = (p1-p0)/se
    return round(z,2), round(float(2*(1-stats.norm.cdf(abs(z)))),6)

def rate(mask, ycol):
    y = D[ycol][mask]
    y = y[~np.isnan(y)]
    return (float(y.mean()), int(y.size)) if y.size else (float("nan"), 0)

# ---- 基准池阈值（train 定，固定）----
# 三类条件操作化：情绪=近期涨停 ; 资金/筹码集中=主力净额占比>0 ; 高波动=vol20>=q7 且 换手>=q6
tr = D["split"] == "train"
V7 = float(np.nanquantile(D["vol20"][tr], 0.70))
T6 = float(np.nanquantile(D["turnover_rate"][tr], 0.60))
BASE_COND = (finite(D["lu_cnt_20d"]) >= 1) & (finite(D["main_net_norm"]) > 0) & \
            (finite(D["vol20"]) >= V7) & (finite(D["turnover_rate"]) >= T6)

base_info = {"vol20_q70": round(V7,4), "turnover_q60": round(T6,4),
             "conditions": "lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=q70 AND turnover_rate>=q60"}

# 候选新增因子：(名字, mask, 经济逻辑)
FACTORS = {
 "概念-当日强榜": (finite(D["n_strong_today"])>=1, "个股当日所属概念命中强概念榜"),
 "概念-热榜数>=2": (finite(D["n_hot_concepts"])>=2, "所属概念命中三榜的数量>=2（资金聚集广度）"),
 "概念-龙头概念>=1": (finite(D["n_leader_concepts"])>=1, "所属概念concept_score>=0.8（龙头概念）"),
 "概念-主线延续(历史强>=2)": (finite(D["n_concept_strong_hist"])>=2, "所属概念过去10日强榜>=2（主线未走完）"),
 "概念-主线未结束但退出榜单": (finite(D["n_mainline_not_onlist"])>=1, "主线概念今日退出强榜但近10日强>=3（涨跌并存：未被榜单剔除前已上车）"),
 "概念-最大历史强度>=5": (finite(D["max_strong_hist10"])>=5, "所属概念近10日强榜天数>=5"),
 "市场-滞后赚钱效应高": (finite(D["eff_hit10_lag"])>=float(np.nanquantile(D["eff_hit10_lag"][tr],0.7)), "过去11-30日全市场赚钱效应高位（T日可知）"),
 "市场-量能放大": (finite(D["mkt_amt_ratio"])>=1.0, "当日市场成交额/20日均>1（放量）"),
 "市场-短期趋势向上": (finite(D["mkt_ret_5d"])>0, "市场近5日累计涨幅>0（趋势向上）"),
 "市场-涨停情绪": (finite(D["mkt_lu_ma5"])>=float(np.nanquantile(D["mkt_lu_ma5"][tr],0.7)), "市场近5日均涨停家数高位"),
 "其他-短期动量": (finite(D["ret_5d"])>=float(np.nanquantile(D["ret_5d"][tr],0.8)), "个股近5日涨幅高分位（强者恒强）"),
 "其他-逼近日高": (finite(D["close_hh20_ratio"])>=0.95, "收盘价接近20日最高（突破前夜）"),
 "其他-多头排列": (finite(D["ma5_gt_ma20"]).astype(int)+finite(D["ma20_gt_ma60"]).astype(int)>=2, "ma5>ma20>ma60 多头趋势"),
 "其他-小单流出": (finite(D["small_norm"])<=float(np.nanquantile(D["small_norm"][tr],0.3)), "小单净流出低分位（散户离场/筹码集中）"),
 "其他-换手放大": (finite(D["tor_ratio"])>=float(np.nanquantile(D["tor_ratio"][tr],0.7)), "当日换手/5日均放大"),
 "其他-近涨停": (finite(D["lu_gap"])>=-3, "当日涨幅距涨停<=3个点（进攻启动）"),
 "其他-资金力度高分位": (finite(D["main_net_norm"])>=float(np.nanquantile(D["main_net_norm"][tr],0.8)), "主力净额占比高分位（资金聚集强化）"),
}

def analyze(split_name, split_mask):
    m = split_mask & BASE_COND
    base = {y: rate(m, y) for y in ["y5","y7","y10","y12"]}
    res = {"split": split_name, "base_n": int(m.sum()), "base_rates": base}
    fac = {}
    for name,(cond,logic) in FACTORS.items():
        mm = m & cond
        row = {"logic": logic, "n": int(mm.sum()), "cover": round(float(mm.sum())/max(int(m.sum()),1),4)}
        for y in ["y5","y7","y10","y12"]:
            p1,n1 = rate(mm, y); p0,n0 = base[y]
            z,pv = ztest(p1,n1,p0,n0)
            row[y] = {"hit": round(p1,4) if n1 else None, "lift": round(p1/p0,3) if (n1 and p0==p0 and p0>0) else None,
                      "delta": round(p1-p0,4) if n1 else None, "z": z, "p": pv, "n": n1}
        fac[name] = row
    res["factors"] = fac
    return res

out = {"base_info": base_info,
       "splits": {
          "train": analyze("train", D["split"]=="train"),
          "oos": analyze("oos", D["split"]=="oos"),
          "all": analyze("all", np.ones(N,dtype=bool)),
       }}

# 概念两口径对照：当日强榜 vs 主线未结束（互斥分解）在 train/oos
def concept_decomp(split_mask, tag):
    m = split_mask & BASE_COND
    groups = {
      "无强概念": m & (finite(D["n_strong_today"])==0) & (finite(D["n_concept_strong_hist"])<2),
      "仅当日强榜(非延续)": m & (finite(D["n_strong_today"])>=1) & (finite(D["n_concept_strong_hist"])<2),
      "主线延续(含退出榜)": m & (finite(D["n_concept_strong_hist"])>=2),
      "其中:退出榜但主线未结束": m & (finite(D["n_mainline_not_onlist"])>=1),
    }
    r = {}
    for gname,mm in groups.items():
        r[gname] = {"n":int(mm.sum()), **{y:round(rate(mm,y)[0],4) if rate(mm,y)[1] else None for y in ["y5","y7","y10","y12"]}}
    return r
out["concept_decomposition"] = {
  "train": concept_decomp(D["split"]=="train","train"),
  "oos": concept_decomp(D["split"]=="oos","oos"),
}

# 滞后敏感性：基准池 y5 vs y7 / y10 vs y12（train/oos）
out["lag_sensitivity"] = {}
for sp,mask in [("train",D["split"]=="train"),("oos",D["split"]=="oos")]:
    m = mask & BASE_COND
    out["lag_sensitivity"][sp] = {
      "y5":round(rate(m,"y5")[0],4), "y7":round(rate(m,"y7")[0],4),
      "y10":round(rate(m,"y10")[0],4), "y12":round(rate(m,"y12")[0],4)}

# scrplus 真实值区间（oos 2026-04+）单独轨道
scr_valid = (D["split"]=="oos") & (df["trade_date"].to_numpy() >= "2026-04-01")
BASE_OOS = (D["split"]=="oos") & BASE_COND
scr_m = BASE_OOS & scr_valid & (finite(D["main_net_norm"])>0)
out["scrplus_track"] = {
  "note":"scrplus train 全0，仅 2026-04+ 有真实值；在 oos 基准池内按 scrplus_90 分位二分",
  "n_valid_in_base": int(scr_m.sum()),
}
# 从 research matrix 直接取 scrplus_90 分位
scr90 = con.execute(f"SELECT scrplus_90 FROM read_parquet('{RM}') WHERE split='oos' AND trade_date>='2026-04-01' AND scrplus_90>0").df()["scrplus_90"].to_numpy()
if len(scr90)>10:
    med = float(np.median(scr90))
    out["scrplus_track"]["median"] = round(med,3)
    # 需要 scrplus 列在读到的 df 里没取，单独查 mask 太重；用 SQL 直接算
    out["scrplus_track"]["sql_result"] = con.execute(f"""
      WITH b AS (
        SELECT lu_cnt_20d,main_net_norm,vol20,turnover_rate,scrplus_90,y5,y7,y10,y12
        FROM read_parquet('{RM}')
        WHERE split='oos' AND trade_date>='2026-04-01'
          AND lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>={V7:.6f} AND turnover_rate>={T6:.6f}
          AND scrplus_90>0
      ), t AS (SELECT *, ntile(2) OVER (ORDER BY scrplus_90) AS g FROM b)
      SELECT g, count(*) AS n, round(avg(y5),4) AS hit5, round(avg(y7),4) AS hit7,
             round(avg(y10),4) AS hit10, round(avg(y12),4) AS hit12,
             min(scrplus_90) AS lo, max(scrplus_90) AS hi
      FROM t GROUP BY g ORDER BY g
    """).df().to_dict("records")

(WS / "factor_attribution_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("BASE_INFO", json.dumps(base_info, ensure_ascii=False), flush=True)
for sp in ["train","oos"]:
    s = out["splits"][sp]
    print(f"--- {sp} base_n={s['base_n']} rates="+
          json.dumps({k:round(v[0],4) for k,v in s['base_rates'].items()}), flush=True)
    top = sorted(s["factors"].items(), key=lambda kv: -(kv[1]["y10"]["delta"] or -9))[:6]
    for name,row in top:
        print(f"  {name}: n={row['n']} d10={row['y10']['delta']} lift10={row['y10']['lift']} p={row['y10']['p']}", flush=True)
print("CONCEPT_DECOMP train", json.dumps(out["concept_decomposition"]["train"],ensure_ascii=False), flush=True)
print("LAG_SENS", json.dumps(out["lag_sensitivity"],ensure_ascii=False), flush=True)
print("SCRPLUS", json.dumps(out["scrplus_track"],ensure_ascii=False), flush=True)
print("DONE", flush=True)

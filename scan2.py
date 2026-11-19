# -*- coding: utf-8 -*-
"""
修正版个股信号扫描（ntile 子查询）+ 市场状态高命中日画像（仅描述/制图，不作筛选条件）。
日期字段 = 复盘横轴 + 牛熊表现标注，不作为选股条件（用户 m00171）。
纯读，输出 scan2_out.json。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb, numpy as np

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
OUT = WS / "scan2_out.json"
con = duckdb.connect()
con.execute("SET threads=8")
M = f"read_parquet('{MAT}')"

stock_cols = ["close", "pct_change", "turnover_rate", "tor_ratio", "amt_ratio", "amt_ma20",
              "main_net_norm", "huge_norm", "small_norm", "scrplus_90", "scrplus_70",
              "bias5", "bias20", "close_hh20_ratio", "vol20",
              "ret_5d", "ret_10d", "ret_20d", "lu_cnt_10d", "lu_cnt_20d",
              "n_concepts", "n_hot_concepts", "n_leader_concepts", "in_strong_concept",
              "lu_gap"]
binary_cols = ["is_limit_up", "ma5_gt_ma20", "ma20_gt_ma60"]

res = {}
base = con.execute(f"SELECT count(*) AS n, avg(y10) AS hit10, avg(y5) AS hit5 FROM {M} WHERE split='train' AND y10 IS NOT NULL").df().iloc[0]
res["train_base"] = {"n": int(base.n), "hit10": round(float(base.hit10), 4), "hit5": round(float(base.hit5), 4)}

scan = {}
for c in stock_cols:
    sql = f"""
WITH t AS (
  SELECT "{c}" AS v, y10, y5 FROM {M}
  WHERE split='train' AND y10 IS NOT NULL AND "{c}" IS NOT NULL AND isfinite("{c}")
), b AS (
  SELECT v, y10, y5, ntile(10) OVER (ORDER BY v) AS bkt FROM t
)
SELECT bkt, count(*) AS n, min(v) AS lo, max(v) AS hi,
       avg(y10) AS hit10, avg(y5) AS hit5
FROM b GROUP BY bkt ORDER BY bkt
"""
    try:
        d = con.execute(sql).df()
        bs = [{"b": int(r.bkt), "n": int(r.n), "lo": round(float(r.lo), 4), "hi": round(float(r.hi), 4),
               "hit10": round(float(r.hit10), 4), "hit5": round(float(r.hit5), 4)} for r in d.itertuples()]
        best10 = max(bs, key=lambda x: x["hit10"])
        best5 = max(bs, key=lambda x: x["hit5"])
        scan[c] = {"buckets": bs, "best_hit10": best10, "best_hit5": best5,
                   "lift10": round(best10["hit10"] / float(base.hit10), 3),
                   "lift5": round(best5["hit5"] / float(base.hit5), 3),
                   "q1_hit10": bs[0]["hit10"], "q10_hit10": bs[-1]["hit10"],
                   "monotone_hit10": all(bs[i]["hit10"] <= bs[i+1]["hit10"] + 0.01 for i in range(len(bs)-1))}
    except Exception as e:
        scan[c] = {"error": f"{type(e).__name__}: {e}"}

for c in binary_cols:
    d = con.execute(f"""
SELECT "{c}" AS b, count(*) AS n, avg(y10) AS hit10, avg(y5) AS hit5
FROM {M} WHERE split='train' AND y10 IS NOT NULL AND "{c}" IS NOT NULL GROUP BY 1 ORDER BY 1
""").df()
    scan[c] = {"buckets": [{"b": int(r.b), "n": int(r.n),
                            "hit10": round(float(r.hit10), 4), "hit5": round(float(r.hit5), 4)} for r in d.itertuples()]}
res["stock_scan"] = scan

# 市场状态：高 base-rate 日的画像（仅描述/制图，不作为筛选条件）
day = con.execute(f"""
SELECT DISTINCT trade_date, di, split, mkt_hit5, mkt_hit10,
       mkt_amount, mkt_amt_ratio, mkt_lu, mkt_lu_ma5, mkt_up_ratio,
       mkt_pct_mean, mkt_ret_5d, mkt_ret_10d, mkt_ret_20d,
       eff_hit10_lag, eff_hit10_lag_s
FROM {M} WHERE mkt_hit10 IS NOT NULL ORDER BY di
""").df()
hi = day[day.mkt_hit10 >= 0.50]
res["high_days"] = {"n": int(len(hi)),
                     "rows": [{"date": str(r.trade_date), "hit10": round(float(r.mkt_hit10), 3),
                               "hit5": round(float(r.mkt_hit5), 3) if np.isfinite(r.mkt_hit5) else None,
                               "mkt_amount": float(r.mkt_amount) if np.isfinite(r.mkt_amount) else None,
                               "mkt_amt_ratio": round(float(r.mkt_amt_ratio), 3) if np.isfinite(r.mkt_amt_ratio) else None,
                               "mkt_lu": int(r.mkt_lu) if np.isfinite(r.mkt_lu) else None,
                               "mkt_ret_5d": round(float(r.mkt_ret_5d), 2) if np.isfinite(r.mkt_ret_5d) else None}
                              for r in hi.itertuples()]}
# 按月聚合 base rate（用于牛熊横轴图）
day["ym"] = day.trade_date.astype(str).str[:7]
monthly = day.groupby("ym").agg(hit10=("mkt_hit10", "mean"), hit5=("mkt_hit5", "mean"),
                                 amt=("mkt_amount", "mean")).reset_index()
res["monthly"] = [{"ym": r.ym, "hit10": round(float(r.hit10), 4), "hit5": round(float(r.hit5), 4),
                    "amt": round(float(r.amt)/1e12, 3)} for r in monthly.itertuples()]

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("train base", res["train_base"])
print("top by lift10:")
for c, v in sorted(scan.items(), key=lambda x: -(x[1].get("lift10", 0) or 0))[:20]:
    print(" ", c, "lift10", v.get("lift10"), "best_b", (v.get("best_hit10") or {}).get("b"),
          "best_hit10", (v.get("best_hit10") or {}).get("hit10"),
          "q1", v.get("q1_hit10"), "q10", v.get("q10_hit10"))
print("high days", res["high_days"]["n"], [x["date"] for x in res["high_days"]["rows"]])
print("DONE")

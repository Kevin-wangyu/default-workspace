# -*- coding: utf-8 -*-
"""
两层信号扫描（纯读 duckdb，输出小 JSON）：
A. 日级别：市场状态指标分位桶 → mkt_hit10/mkt_hit5 均值（验证日期窗口可否由当日可知指标定义）
B. 个股级别：候选指标分位桶 → y10/y5 均值（筛掉无区分度维度）
不修改投研项目任何文件。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
OUT = WS / "scan_signals_out.json"

con = duckdb.connect()
con.execute("SET threads=8")
M = f"read_parquet('{MAT}')"

res = {}

# ---------- A. 日级别 ----------
day_cols = ["mkt_amount", "mkt_amt_ratio", "mkt_amt_ma20", "mkt_lu", "mkt_lu_ma5",
            "mkt_up_ratio", "mkt_pct_mean", "mkt_pct_ma5", "mkt_ret_5d", "mkt_ret_10d",
            "mkt_ret_20d", "eff_hit10_lag", "eff_hit10_lag_s", "eff_hit5_lag"]

# 日表（669 行）取到 python，用 numpy 算相关/分桶
day = con.execute(f"""
SELECT DISTINCT trade_date, di, split,
       mkt_hit5, mkt_hit10, {', '.join(day_cols)}
FROM {M} WHERE mkt_hit10 IS NOT NULL ORDER BY di
""").df()

import numpy as np
res["A_day_n"] = int(len(day))
res["A_day_range"] = [str(day.trade_date.min()), str(day.trade_date.max())]
day_scan = {}
for c in day_cols + ["mkt_hit5"]:
    v = day[c].to_numpy(dtype=float)
    h = day["mkt_hit10"].to_numpy(dtype=float)
    ok = np.isfinite(v) & np.isfinite(h)
    vv, hh = v[ok], h[ok]
    if len(vv) < 30:
        day_scan[c] = {"n": int(len(vv)), "note": "insufficient"}
        continue
    # Pearson + Spearman(用秩)
    pr = float(np.corrcoef(vv, hh)[0, 1])
    rv = np.argsort(np.argsort(vv)).astype(float)
    rh = np.argsort(np.argsort(hh)).astype(float)
    sr = float(np.corrcoef(rv, rh)[0, 1])
    # 5 分位桶
    qs = np.quantile(vv, [0, .2, .4, .6, .8, 1.0])
    buckets = []
    for i in range(5):
        lo, hi = qs[i], qs[i+1]
        m = (vv >= lo) & (vv <= hi if i == 4 else vv < hi)
        buckets.append({"q": f"q{i+1}", "lo": round(float(lo), 4), "hi": round(float(hi), 4),
                        "n": int(m.sum()), "hit10": round(float(hh[m].mean()), 4) if m.sum() else None})
    day_scan[c] = {"n": int(len(vv)), "pearson": round(pr, 4), "spearman": round(sr, 4),
                   "buckets": buckets}
res["A_day_scan"] = day_scan

# 高 base rate 日的市场状态画像 vs 其余日
hi = day[day.mkt_hit10 >= 0.50]
lo = day[day.mkt_hit10 < 0.50]
res["A_high_days"] = {"n": int(len(hi)), "dates": [str(x) for x in hi.trade_date.tolist()],
                      "hit10": [round(float(x), 3) for x in hi.mkt_hit10.tolist()]}
prof = {}
for c in day_cols:
    a = hi[c].to_numpy(dtype=float); b = lo[c].to_numpy(dtype=float)
    a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
    prof[c] = {"high_mean": round(float(a.mean()), 4) if len(a) else None,
               "rest_mean": round(float(b.mean()), 4) if len(b) else None,
               "high_pctl_in_all": round(float((b < a.mean()).mean()), 4) if len(a) and len(b) else None}
res["A_high_vs_rest"] = prof

# ---------- B. 个股级别（train 期，有双标签） ----------
stock_cols = ["close", "pct_change", "turnover_rate", "tor_ratio", "amt_ratio", "amt_ma20",
              "main_net_norm", "huge_norm", "small_norm", "scrplus_90", "scrplus_70",
              "bias5", "bias20", "close_hh20_ratio", "vol20",
              "ret_5d", "ret_10d", "ret_20d", "lu_cnt_10d", "lu_cnt_20d",
              "n_concepts", "n_hot_concepts", "n_leader_concepts", "in_strong_concept",
              "lu_gap"]
binary_cols = ["is_limit_up", "ma5_gt_ma20", "ma20_gt_ma60"]

stock_scan = {}
for c in stock_cols:
    expr = f"""
WITH t AS (
  SELECT "{c}" AS v, y10, y5 FROM {M}
  WHERE split='train' AND y10 IS NOT NULL AND "{c}" IS NOT NULL AND isfinite("{c}")
)
SELECT ntile(10) OVER (ORDER BY v) AS b, count(*) AS n,
       avg(v) AS mean_v, min(v) AS lo, max(v) AS hi,
       avg(y10) AS hit10, avg(y5) AS hit5
FROM t GROUP BY b ORDER BY b
"""
    try:
        d = con.execute(expr).df()
        stock_scan[c] = {"overall_hit10": round(float(d.hit10.mean()), 4),
                         "buckets": [{"b": int(r.b), "n": int(r.n), "lo": round(float(r.lo), 4),
                                      "hi": round(float(r.hi), 4),
                                      "hit10": round(float(r.hit10), 4),
                                      "hit5": round(float(r.hit5), 4)} for r in d.itertuples()]}
    except Exception as e:
        stock_scan[c] = {"error": f"{type(e).__name__}: {e}"}

for c in binary_cols:
    d = con.execute(f"""
SELECT "{c}" AS b, count(*) AS n, avg(y10) AS hit10, avg(y5) AS hit5
FROM {M} WHERE split='train' AND y10 IS NOT NULL AND "{c}" IS NOT NULL
GROUP BY 1 ORDER BY 1
""").df()
    stock_scan[c] = {"buckets": [{"b": int(r.b), "n": int(r.n),
                                  "hit10": round(float(r.hit10), 4),
                                  "hit5": round(float(r.hit5), 4)} for r in d.itertuples()]}

res["B_stock_scan"] = stock_scan

# 全局 train base rate
res["B_train_base"] = con.execute(f"""
SELECT count(*) AS n, round(avg(y10),4) AS hit10, round(avg(y5),4) AS hit5
FROM {M} WHERE split='train' AND y10 IS NOT NULL
""").df().to_dict("records")

OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("day_n", res["A_day_n"], "high_days", res["A_high_days"]["n"])
print("day pearson/spearman (top by |spearman|):")
for c, v in sorted(day_scan.items(), key=lambda x: -abs(x[1].get("spearman", 0) or 0))[:12]:
    print(" ", c, "pearson", v.get("pearson"), "spearman", v.get("spearman"),
          "q5_hit", v.get("buckets", [{}]*5)[4].get("hit10"), "q1_hit", v.get("buckets", [{}])[0].get("hit10"))
print("stock scan (top lift):")
for c, v in sorted(stock_scan.items(), key=lambda x: -max([b["hit10"] for b in x[1].get("buckets", [{"hit10":0}])] or [0]))[:14]:
    bs = v.get("buckets", [])
    mx = max([b["hit10"] for b in bs] or [0])
    print(" ", c, "overall", v.get("overall_hit10"), "best_bucket", mx, "n_buckets", len(bs))
print("train base", res["B_train_base"])
print("DONE")

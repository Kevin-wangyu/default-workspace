# -*- coding: utf-8 -*-
"""市场级 base rate 探查：纯读 quote parquet，向量化算 fwd_max_Nd，零写入投研项目。
目的：确认数据实际覆盖范围、缺失情况、以及"日期"是否天然是有效抓手。
输出：explore_market_out.json（工作目录）
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
sys.path.insert(0, PROJ)

import pandas as pd
import numpy as np
from core.db import _q_df, QUOTE_GLOB

OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\explore_market_out.json")

t0 = time.time()
# 一次读全量 quote（只取需要的列）
df = _q_df(f"""
    SELECT trade_date, code, close, high, amount, turnover_rate, hot_rank,
           pct_change, huge_order_net, big_order_net
    FROM read_parquet({QUOTE_GLOB}, hive_partitioning=true, union_by_name=true)
""")
print("read rows:", len(df), "elapsed:", round(time.time()-t0,1))
df["trade_date"] = df["trade_date"].astype(str).str[:10]
df = df.sort_values(["code", "trade_date"]).reset_index(drop=True)

dates = sorted(df["trade_date"].unique())
result = {
    "n_rows": int(len(df)),
    "n_codes": int(df["code"].nunique()),
    "n_dates": len(dates),
    "date_min": dates[0],
    "date_max": dates[-1],
    "hot_rank_nonnull": int(df["hot_rank"].notna().sum()),
    "hot_rank_null_pct": round(float(df["hot_rank"].isna().mean()), 4),
    "close_null_pct": round(float(df["close"].isna().mean()), 4),
    "high_null_pct": round(float(df["high"].isna().mean()), 4),
}

# 向量化：每只股票未来 N 日 high 最大值（不含当日）
def add_fwd_max(g, close_col="close"):
    h = g["high"].astype("float64")
    c = g[close_col].astype("float64")
    out = {}
    for N in (5, 10):
        # h_shift[t] = high[t+1]；反转 rolling 得到 [t+1..t+N] 的最大
        hs = h.shift(-1)
        fmax = hs[::-1].rolling(N, min_periods=N).max()[::-1]
        g[f"fwd_max_{N}d"] = (fmax / c - 1.0) * 100.0
    return g

df = df.groupby("code", group_keys=False).apply(add_fwd_max)
print("fwd computed elapsed:", round(time.time()-t0,1))

# 每日全市场 base rate
grp = df.groupby("trade_date")
daily = []
for d, g in grp:
    v5 = g["fwd_max_5d"].dropna()
    v10 = g["fwd_max_10d"].dropna()
    daily.append({
        "d": d,
        "n": int(len(g)),
        "n5": int(len(v5)),
        "n10": int(len(v10)),
        "hit5": round(float((v5 > 20).mean()), 3) if len(v5) else None,
        "hit10": round(float((v10 > 20).mean()), 3) if len(v10) else None,
    })
daily_sorted = sorted(daily, key=lambda x: x["d"])
result["daily"] = daily_sorted

# 统计：有多少交易日全市场 base rate >= 0.75
h10 = [x for x in daily_sorted if x["hit10"] is not None]
h5 = [x for x in daily_sorted if x["hit5"] is not None]
result["summary"] = {
    "n_days_with_hit10": len(h10),
    "n_days_hit10_ge_075": sum(1 for x in h10 if x["hit10"] >= 0.75),
    "n_days_hit10_ge_050": sum(1 for x in h10 if x["hit10"] >= 0.50),
    "max_hit10": max((x["hit10"] for x in h10), default=None),
    "max_hit10_date": max(h10, key=lambda x: x["hit10"])["d"] if h10 else None,
    "mean_hit10": round(float(np.mean([x["hit10"] for x in h10])), 3) if h10 else None,
    "n_days_hit5_ge_075": sum(1 for x in h5 if x["hit5"] >= 0.75),
    "max_hit5": max((x["hit5"] for x in h5), default=None),
    "max_hit5_date": max(h5, key=lambda x: x["hit5"])["d"] if h5 else None,
    "mean_hit5": round(float(np.mean([x["hit5"] for x in h5])), 3) if h5 else None,
}
# top10 高 base rate 日期
result["top_days_hit10"] = sorted(h10, key=lambda x: x["hit10"], reverse=True)[:15]

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE elapsed:", round(time.time()-t0,1))
print("range:", result["date_min"], "~", result["date_max"], "dates:", result["n_dates"])
print("hot_rank_null_pct:", result["hot_rank_null_pct"], "close_null_pct:", result["close_null_pct"])
print("summary:", json.dumps(result["summary"], ensure_ascii=False))
print("top_days_hit10:", [(x["d"], x["hit10"]) for x in result["top_days_hit10"][:10]])

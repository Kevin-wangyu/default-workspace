# -*- coding: utf-8 -*-
"""验证 C6 补充不牺牲命中质量：用快照的 fwd_max 复盘列统计合并池 vs C7/C6 分层命中。"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
df = pd.read_parquet(WS/"_prebuild_verify.parquet")
df = df[df.split.eq("train") | df.split.eq("oos")] if "split" in df.columns else df

def rate(g, col):
    v = g[col].dropna()
    return (v >= 20).mean() if len(v) else float('nan'), len(v)

print("=== 合并池分层命中率（未来N日最高涨幅≥20%，复盘列）===")
for sp, g in [("ALL", df)]:
    for label, gg in [("C7严选", g[g.source=="C7"]), ("C6补充", g[g.source=="C6"]), ("合并池", g)]:
        h5,n5 = rate(gg,"fwd_max_5d"); h10,n10 = rate(gg,"fwd_max_10d")
        print(f"  {label}: n={len(gg)} hit5={h5*100:.2f}%(n5={n5}) hit10={h10*100:.2f}%(n10={n10})")

# 近端有完整 fwd 标签的日期
recent = sorted(df.trade_date.unique())[-20:]
sub = df[df.trade_date.isin(recent)]
print(f"\n=== 近20交易日(n={len(sub)}) ===")
for label, gg in [("C7严选", sub[sub.source=="C7"]), ("C6补充", sub[sub.source=="C6"]), ("合并池", sub)]:
    h10,n10 = rate(gg,"fwd_max_10d")
    print(f"  {label}: n={len(gg)} hit10={h10*100:.2f}%(n={n10})" if n10 else f"  {label}: n={len(gg)} hit10=NA(未来数据未到)")

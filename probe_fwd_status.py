# -*- coding: utf-8 -*-
"""探查近期缓存分区 fwd_max_10d 完整性 + 距数据末尾交易日数。纯读。"""
from pathlib import Path
import pandas as pd
import duckdb
C7 = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay\data\c7_picks")
QD = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay\data\quote")
con = duckdb.connect()
# 全交易日列表（从日分区目录）
tds = sorted(p.parent.name.split('=',1)[1] for p in QD.glob('trade_date=*/part.parquet'))
print("N_TRADE_DAYS=", len(tds), "LAST=", tds[-3:])
# 最近15天分区的 fwd 状态
recent = tds[-15:]
for d in recent:
    p = C7 / f"trade_date={d}" / "part.parquet"
    if not p.exists():
        print(d, "NO_PARTITION"); continue
    df = pd.read_parquet(p)
    if df.empty:
        print(d, "EMPTY", "cols=", list(df.columns)); continue
    f10 = df['fwd_max_10d'] if 'fwd_max_10d' in df.columns else pd.Series([None]*len(df))
    f5 = df['fwd_max_5d'] if 'fwd_max_5d' in df.columns else pd.Series([None]*len(df))
    pos = tds.index(d)
    dist_end = len(tds)-1-pos
    print(f"{d} n={len(df)} f10_nonnull={f10.notna().sum()}/{len(df)} "
          f"f5_nonnull={f5.notna().sum()}/{len(df)} dist_from_end={dist_end} "
          f"mc_type={df['matched_concepts'].map(type).iloc[0].__name__ if 'matched_concepts' in df.columns else 'NA'}")
con.close()

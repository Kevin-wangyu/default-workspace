# -*- coding: utf-8 -*-
"""探查：①board 字段取值分布（确定主板口径）②当日回转成因（退出循环 d=0）"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb, pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
con=duckdb.connect(); con.execute("SET threads=8")
# board 分布
q1=con.execute(f"""SELECT board, count(*) n, count(DISTINCT code) codes
    FROM read_parquet('{RM}') GROUP BY board ORDER BY n DESC""").df()
print("BOARD_DIST:")
print(q1.to_string(index=False))
# code 前缀分布（交叉验证主板定义）
q2=con.execute(f"""SELECT substr(code,1,3) p3, count(DISTINCT code) codes, any_value(board) board
    FROM read_parquet('{RM}') GROUP BY p3 ORDER BY codes DESC LIMIT 30""").df()
print("\nPREFIX_DIST:")
print(q2.to_string(index=False))
con.close()
# 当日回转成因：读逐笔明细，k=1 的退出原因
for tag in ["c7","dual"]:
    d=pd.read_csv(WS/f"backtest_detail_{tag}.csv",encoding="utf-8-sig",dtype={"code":str})
    fl=d[d["filled"].astype(bool)].copy()
    print(f"\n[{tag}] 成交 {len(fl)} 笔")
    # 用退出日-di 推算k（明细里有 di 和 k_exit 吗？看列）
    print("  列名:", list(d.columns))
    if "k_exit" in d.columns:
        k1=fl[fl.k_exit==1]
        print(f"  k=1(当日回转) {len(k1)} 笔, 原因分布: {k1.reason.value_counts().to_dict()}")

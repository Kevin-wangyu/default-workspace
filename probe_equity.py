# -*- coding: utf-8 -*-
"""探查逐笔明细：成交笔数/日期/ret完整性，确认与backtest_out.json对齐。"""
from pathlib import Path
import json
import pandas as pd
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
for g, f in [("C7单池","backtest_detail_c7.csv"),("C6+C7双池","backtest_detail_dual.csv")]:
    d = pd.read_csv(WS/f, encoding="utf-8-sig")
    fl = d[d["filled"].astype(bool)]
    print("==", g)
    print("  总行", len(d), " 成交", len(fl), " json_n_filled", OUT["groups"][g]["全区间"]["n_filled"])
    print("  成交ret非空", int(fl["ret"].notna().sum()), " 成交ret空", int(fl["ret"].isna().sum()))
    print("  信号日范围", d.trade_date.min(), d.trade_date.max())
    print("  成交日范围", fl.trade_date.min(), fl.trade_date.max(), " 成交不同日数", fl.trade_date.nunique())
    print("  split成交", fl.split.value_counts().to_dict())
    print("  ret范围", round(fl.ret.min(),3), round(fl.ret.max(),3))
print("区间", OUT["config"]["D0"], OUT["config"]["D1"])

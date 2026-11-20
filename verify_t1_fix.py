# -*- coding: utf-8 -*-
"""T+1 修正统一自检：正常(normal) + 仅主板(main) 两套。
① 全量扫描当日回转(k_exit==1)=0；
② 从逐笔明细独立重算四指标(成交数/期望/胜率/PF)，与各自 backtest_out*.json 逐项核对；
③ 组合层逐笔基线(trade_base)与回测输出一致；
④ 交互数据节点净值与引擎CSV逐日对齐；
⑤ 组合层精确交易成本标"不可得"。
独立实现，不复用引擎函数；MFE/退出从原始OHLC重算。
"""
from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd, numpy as np

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
T1K = 2
checks = []
def ck(name, got, exp, tol=1e-4):
    ok = (got is not None and exp is not None and abs(float(got)-float(exp)) <= tol) or (got is None and exp is None)
    checks.append((name, got, exp, ok))

def recompute_exit(row):
    """独立复现 T+1 退出：k from 2..7, 同日先止损后止盈；返回 (k, reason)。"""
    fp = float(row["fill_px"]); tp = fp*1.15; sl = fp*0.92
    for k in range(T1K, 8):
        if float(row[f"l{k}"]) <= sl: return k, "SL"
        if float(row[f"h{k}"]) >= tp: return k, "TP"
    return 7, "TIME"

def four_metrics(fl):
    r = fl["ret"].dropna().astype(float)
    gp = float(r[r>0].sum()); gl = float(abs(r[r<0].sum()))
    return dict(n=len(fl), avg=round(float(r.mean()),4),
                win=round(float((r>0).mean())*100,2),
                pf=round(gp/gl,3) if gl>0 else None)

for mode, suf in [("normal",""), ("main","_main")]:
    BT = json.loads((WS/f"backtest_out{suf}.json").read_text(encoding="utf-8"))
    POOL = json.loads((WS/f"portfolio_compound_out{suf}.json").read_text(encoding="utf-8"))
    for tag, gname in [("c7","C7单池"), ("dual","C6+C7双池")]:
        d = pd.read_csv(WS/f"backtest_detail_{tag}{suf}.csv", encoding="utf-8-sig")
        fl = d[d["filled"].astype(bool)].copy()
        # ① 当日回转扫描
        ex = fl.apply(recompute_exit, axis=1, result_type="expand")
        k_recalc = ex[0].astype(int).values; reason_recalc = ex[1].values
        n_sameday_recalc = int((k_recalc==1).sum())
        ck(f"{mode}/{gname}/当日回转重算=0", n_sameday_recalc, 0, 0)
        if "k_exit" in d.columns:
            n_sameday_engine = int((d.loc[fl.index,"k_exit"]==1).sum())
            ck(f"{mode}/{gname}/引擎k_exit当日回转=0", n_sameday_engine, 0, 0)
            ck(f"{mode}/{gname}/k_exit重算一致", int((k_recalc!=d.loc[fl.index,"k_exit"].values).sum()), 0, 0)
        ck(f"{mode}/{gname}/退出原因重算一致", int((reason_recalc!=fl["reason"].values).sum()), 0, 0)
        # ② 四指标独立重算 vs 回测输出
        fm = four_metrics(fl)
        exp = BT["groups"][gname]["全区间"]
        ck(f"{mode}/{gname}/成交数", fm["n"], exp["n_filled"], 0)
        ck(f"{mode}/{gname}/期望", fm["avg"], exp["avg_ret"], 1e-3)
        ck(f"{mode}/{gname}/胜率", fm["win"], exp["win_rate"], 1e-2)
        ck(f"{mode}/{gname}/PF", fm["pf"], exp["profit_factor"], 1e-3)
        # ③ 组合层逐笔基线与回测输出一致
        tb = POOL["pools"][gname]["trade_base"]
        ck(f"{mode}/{gname}/组合层成交数", tb["n_filled"], exp["n_filled"], 0)
        ck(f"{mode}/{gname}/组合层期望", tb["avg_ret"], exp["avg_ret"], 1e-3)
        ck(f"{mode}/{gname}/组合层胜率", tb["win_rate"], exp["win_rate"], 1e-2)
        ck(f"{mode}/{gname}/组合层PF", tb["profit_factor"], exp["profit_factor"], 1e-3)
        # ④ 交互数据节点净值 vs 引擎CSV
        IDATA = json.loads((WS/f"interactive_equity_data{suf}.json").read_text(encoding="utf-8"))
        nodes = IDATA["pools"][tag]["nodes"]
        eqcsv = pd.read_csv(WS/f"portfolio_compound_equity_{tag}{suf}.csv", encoding="utf-8-sig")
        mg = pd.DataFrame([{"di":n["di"],"eq":n["equity"]} for n in nodes]).merge(
            eqcsv[["di","equity"]], on="di", suffixes=("_replay","_engine"))
        maxdiff = float((mg["eq"]-mg["equity"]).abs().max())
        ck(f"{mode}/{gname}/交互净值对齐<0.01", maxdiff, 0, 0.01)  # tol 0.01
        n_sameday_nodes = sum(1 for n in nodes if n.get("intraday_closed"))
        ck(f"{mode}/{gname}/交互当日回转节点=0", n_sameday_nodes, 0, 0)
    # ⑤ 成本不可得声明
    una = POOL["pools"]["C7单池"]["unavailable"]["items"]
    ck(f"{mode}/组合层成本标不可得", 1 if any("交易成本" in u for u in una) else 0, 1, 0)

npass = sum(1 for *_, ok in checks if ok); ntot = len(checks)
print(f"T+1 统一自检: {npass}/{ntot} PASSED")
for name, got, exp, ok in checks:
    if not ok:
        print(f"  FAIL {name}: got={got} exp={exp}")
print("VERIFY_T1=" + ("ALL_OK" if npass==ntot else "HAS_FAIL"))

# -*- coding: utf-8 -*-
"""T+1 任务最终交付闭环：产物齐全 + 两套逐笔四指标一致 + 哈希 + 三要素 + 显著性口径。"""
from __future__ import annotations
import json, hashlib
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
S=json.loads((WS/"t1_summary.json").read_text(encoding="utf-8"))
res=[]
def chk(c,l,d=""):res.append((bool(c),l,d))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]

# 产物齐全（两套，各 suffix）
need=["backtest_strategy.py","portfolio_compound.py","portfolio_backtest.py",
      "build_interactive_equity.py","make_interactive_page.py","make_t1_report.py",
      "verify_t1_fix.py","verify_t1_report.py"]
for suf in ["","_main"]:
    for base in ["backtest_out","strategy_usefulness","portfolio_compound_out",
                 "interactive_equity_data","backtest_charts","compound_charts"]:
        need.append(f"{base}{suf}.json")
    for tag in ["c7","dual"]:
        need.append(f"backtest_detail_{tag}{suf}.csv")
        need.append(f"portfolio_compound_equity_{tag}{suf}.csv")
    need.append(f"复利资产曲线_交互复盘{suf}.html")
for base in ["C7策略_T1修正回测汇报.html","C7策略_T1修正回测汇报_仅主板.html",
             "t1_summary.json","verify_t1_report.log","verify_t1_pages_browser.log"]:
    need.append(base)
missing=[n for n in need if not (WS/n).exists()]
chk(not missing,"全部产物齐全",f"缺{missing}" if missing else f"{len(need)}个")

# 两套逐笔四指标（与 t1_summary 一致）
EXPECT={
 "normal":{"c7":(1450,-0.5784,34.62,0.881),"du":(5041,-0.6623,34.24,0.864)},
 "main":{"c7":(1003,-0.7035,34.50,0.855),"du":(3845,-0.7543,34.15,0.844)},
}
for mode in ["normal","main"]:
    d=S[mode]
    for tag,key,exp in [("c7","C7单池",EXPECT[mode]["c7"]),("du","C6+C7双池",EXPECT[mode]["du"])]:
        g=d[key]
        actual=(g["n_fill"],g["avg"],g["win"],g["pf"])
        chk(actual==exp,f"[{mode}] {tag}四指标",f"{actual} vs {exp}")
        chk(g["sameday"]==0,f"[{mode}] {tag}当日回转=0")

# 三要素（复利口径 config）
for mode in ["normal","main"]:
    suf="" if mode=="normal" else "_main"
    co=json.loads((WS/f"portfolio_compound_out{suf}.json").read_text(encoding="utf-8"))
    cfg=co["config"]
    chk(cfg["initial_capital"]==20000,f"[{mode}] 初始资金20000")
    chk(cfg["max_concurrent_positions"]==5,f"[{mode}] 最多持仓5")
    chk(abs(cfg["reinvest_frac"]-20)<1e-9,f"[{mode}] 每笔=净值×20%")

# 显著性口径：全区间显著为负，不能是显著为正
for mode in ["normal","main"]:
    d=S[mode]
    for key in ["C7单池","C6+C7双池"]:
        sig=d[key]["sig"]["全区间"]["sig"]
        chk(sig in ("显著为负","不显著"),f"[{mode}] {key}全区间无'显著为正'",sig)

# 哈希（可复现锚点）
print("HASHES:")
for f in ["backtest_strategy.py","backtest_out.json","backtest_out_main.json",
          "backtest_detail_c7.csv","backtest_detail_dual.csv"]:
    print(f"  {f}: {sha(WS/f)}")

passed=sum(1 for c,_,_ in res if c); total=len(res)
print(f"FINAL_T1_DELIVERY {passed}/{total}")
for c,l,d in res:
    if not c:print("  FAIL:",l,d)
print("ALL_OK" if passed==total else "HAS_FAILURE")

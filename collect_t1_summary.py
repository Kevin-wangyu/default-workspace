# -*- coding: utf-8 -*-
"""汇总两套口径核心数字，供报告生成使用（只读）。"""
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
S={}
for mode,suf in [("normal",""),("main","_main")]:
    bt=json.loads((WS/f"backtest_out{suf}.json").read_text(encoding="utf-8"))
    co=json.loads((WS/f"portfolio_compound_out{suf}.json").read_text(encoding="utf-8"))
    su=json.loads((WS/f"strategy_usefulness{suf}.json").read_text(encoding="utf-8"))
    one={}
    for g in ["C7单池","C6+C7双池"]:
        full=bt["groups"][g]["全区间"]
        one[g]=dict(
            n_sig=full["n_signals"], n_fill=full["n_filled"], fill=full["fill_rate"],
            avg=full["avg_ret"], win=full["win_rate"], pf=full["profit_factor"],
            mfe20=full["mfe20_hold7"], tp=full["exit_TP"], sl=full["exit_SL"], time=full["exit_TIME"],
            sameday=full["n_sameday_roundtrip"],
            train=dict(n=bt["groups"][g]["train"]["n_filled"],avg=bt["groups"][g]["train"]["avg_ret"],
                       win=bt["groups"][g]["train"]["win_rate"],pf=bt["groups"][g]["train"]["profit_factor"]),
            oos=dict(n=bt["groups"][g]["oos"]["n_filled"],avg=bt["groups"][g]["oos"]["avg_ret"],
                     win=bt["groups"][g]["oos"]["win_rate"],pf=bt["groups"][g]["oos"]["profit_factor"]),
            port=co["pools"][g]["portfolio"],
            sig=su[g],
        )
    S[mode]=one
(WS/"t1_summary.json").write_text(json.dumps(S,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(S,ensure_ascii=False,indent=2))
